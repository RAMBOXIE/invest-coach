#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reddit 需求调研取证 —— 走 Arctic Shift 归档 API 拉真实帖子。

**为什么是脚本而不是让 LLM 去搜。** WebFetch 对 reddit.com 是 API 层硬封的
（"The following domains are not accessible to our user agent: ['reddit.com']"），
LLM 只能靠搜索引擎摘要拼证据，而那是编造 URL 风险最高的路子。
这个产品的卖点是可溯源，调研环节不能自己破例。

所以：**检索由这个脚本做**（permalink / score / 时间戳全部来自 API 原始响应），
**解读由 LLM 做**。LLM 拿到的是语料文件，不是搜索框——编不出不存在的帖子。

## 用法

    python tools/fetch_reddit.py out.json            # 主查询集
    python tools/fetch_reddit.py out.json --round2   # 追加第二轮角度

## 三条实测出来的注意事项

1. **短语要短。** "read financial statements" 一次命中 29 条；
   "learn to read financial statements" 只命中 1 条。长短语几乎搜不到东西。
2. **query 是松散匹配**，返回里大量噪音——脚本会在本地再筛一道
   （标题或正文里真的包含该短语才留）。
3. **并发别超过 2。** 4 线程实测 428/482 组查询被限流失败，
   而同样的查询单发立刻返回。这是自己把自己限流了，不是 API 的问题。

## 下一步：中文语料

ROADMAP 的第一件验证是「中文语料重跑」。Arctic Shift 只有 Reddit，
雪球 / 集思录 / 知乎需要另写取数，但**分工原则照搬**：
脚本负责检索与留痕，LLM 只负责解读。
"""
import concurrent.futures as cf
import json
import pathlib
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://arctic-shift.photon-reddit.com/api"
UA = "invest-coach-demand-research/1.0 (educational product research)"
WORKERS = 2          # 4 线程会被限流，实测 428/482 组失败
LIMIT = 100

CORE = ["investing", "SecurityAnalysis", "ValueInvesting", "stocks", "StockMarket"]
PRO = ["Accounting", "AccountingStudents", "CFA", "FinancialCareers", "FPandA"]
RETAIL = ["personalfinance", "Bogleheads", "financialindependence", "wallstreetbets"]
ALL = CORE + PRO + RETAIL

# 短语要**短**：长短语几乎命中不了。(角度, 短语, subs)
QUERIES = [
    # ── A 需求存在吗 ────────────────────────────────────────────
    ("A需求", "read financial statements", ALL),
    ("A需求", "learn to read financial", CORE + PRO),
    ("A需求", "how to read a 10-K", CORE + PRO),
    ("A需求", "reading 10-K", CORE + PRO),
    ("A需求", "financial statement analysis", ALL),
    ("A需求", "how to analyze a company", CORE),
    ("A需求", "accounting red flags", CORE + PRO),
    ("A需求", "accounting fraud", CORE + PRO),
    ("A需求", "earnings quality", CORE + PRO),
    ("A需求", "how do I value a stock", CORE),
    ("A需求", "fundamental analysis how to learn", CORE),
    # ── B 现有方案与抱怨 ────────────────────────────────────────
    ("B方案", "Financial Shenanigans", CORE + PRO),
    ("B方案", "Quality of Earnings", CORE + PRO),
    ("B方案", "best book to learn", CORE + PRO),
    ("B方案", "book recommendation financial", CORE + PRO),
    ("B方案", "Damodaran", CORE + PRO),
    ("B方案", "still don't know how", CORE + PRO),
    ("B方案", "where do I practice", CORE + PRO),
    ("B方案", "how to actually apply", CORE + PRO),
    ("B方案", "CFA worth it", PRO + CORE),
    # ── C 形态偏好 ──────────────────────────────────────────────
    ("C形态", "case study", CORE + PRO),
    ("C形态", "Duolingo", ALL),
    ("C形态", "gamified", ALL),
    ("C形态", "spaced repetition", PRO + CORE),
    ("C形态", "Anki", PRO + CORE),
    ("C形态", "ChatGPT to analyze", CORE + PRO),
    ("C形态", "AI to read annual report", CORE),
    ("C形态", "AI summarize earnings", CORE),
    ("C形态", "paper trading", CORE + RETAIL),
    ("C形态", "learn by doing", CORE + PRO),
    # ── D 付费意愿与竞品 ────────────────────────────────────────
    ("D付费", "worth paying for", CORE + RETAIL),
    ("D付费", "investing course", CORE + RETAIL),
    ("D付费", "is it a scam course", CORE + RETAIL),
    ("D付费", "Seeking Alpha", CORE),
    ("D付费", "Koyfin", CORE),
    ("D付费", "TIKR", CORE),
    ("D付费", "subscription worth it", CORE),
    # ── E 谁最痛 ────────────────────────────────────────────────
    ("E人群", "Luckin", CORE + RETAIL),
    ("E人群", "Wirecard", CORE + PRO),
    ("E人群", "Nikola", CORE + RETAIL),
    ("E人群", "Enron", CORE + PRO),
    ("E人群", "should have seen it coming", CORE + RETAIL),
    ("E人群", "equity research interview", PRO),
    ("E人群", "forensic accounting", PRO + CORE),
    ("E人群", "Chinese stocks fraud", CORE),
    ("E人群", "Evergrande", CORE),
    ("E人群", "lost money on a fraud", CORE + RETAIL),
    # ── F 反面 ──────────────────────────────────────────────────
    ("F反面", "retail investors can't", CORE + RETAIL),
    ("F反面", "auditors missed", CORE + PRO),
    ("F反面", "just buy index funds", RETAIL + CORE),
    ("F反面", "waste of time", CORE + RETAIL),
    ("F反面", "already priced in", CORE + RETAIL),
    ("F反面", "efficient market", CORE + RETAIL),
    ("F反面", "stock picking doesn't work", RETAIL + CORE),
]

# ── 第二轮补：第一轮问漏的三个角度 ──────────────────────────────
QUERIES2 = [
    # G 学了之后真的改变行为了吗（比「想不想学」更硬的需求信号）
    ("G行为", "changed how I invest", CORE + RETAIL),
    ("G行为", "glad I learned", CORE + RETAIL),
    ("G行为", "avoided a stock because", CORE),
    ("G行为", "dodged a bullet", CORE + RETAIL),
    ("G行为", "red flag I noticed", CORE),
    # H 产品用的具体机制：先预测后揭晓 / 主动回忆 / 迁移
    ("H机制", "active recall", PRO + CORE),
    ("H机制", "testing effect", PRO + CORE),
    ("H机制", "predict before", CORE + PRO),
    ("H机制", "learn from mistakes investing", CORE + RETAIL),
    ("H机制", "post mortem on my trades", CORE + RETAIL),
    ("H机制", "investment journal", CORE + RETAIL),
    # I 中文/中概股视角（Reddit 上能拿到的那一点）
    ("I中文", "China stocks", CORE),
    ("I中文", "VIE structure", CORE),
    ("I中文", "reverse merger fraud", CORE),
    ("I中文", "Muddy Waters", CORE),
    ("I中文", "short seller report", CORE),
]

_lock = threading.Lock()
posts, failed, done = {}, [], [0]


def get(path, params, tries=2):
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            if d.get("error"):
                time.sleep(2 * (attempt + 1))
                continue
            return d.get("data") or []
        except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
            time.sleep(2 * (attempt + 1))
    return None


def work(job):
    lens, q, sub, total = job
    d = get("posts/search", {"subreddit": sub, "query": f'"{q}"',
                             "limit": LIMIT, "sort": "desc"})
    phrase = q.lower()
    n = 0
    with _lock:
        done[0] += 1
        if d is None:
            failed.append(f"{sub} «{q}»")
        else:
            for p in d:
                pid = p.get("id")
                if not pid or pid in posts:
                    continue
                title = p.get("title") or ""
                body = p.get("selftext") or ""
                if phrase not in (title + " " + body).lower():
                    continue          # API 的 query 是松散匹配，本地再筛一道
                posts[pid] = {
                    "lens": lens, "q": q, "sub": p.get("subreddit"),
                    "title": title, "text": body[:2200],
                    "score": p.get("score"), "ncom": p.get("num_comments"),
                    "utc": p.get("created_utc"),
                    "url": "https://www.reddit.com" + (p.get("permalink") or ""),
                }
                n += 1
        if done[0] % 10 == 0 or n:
            print(f"[{done[0]}/{total}] {lens} r/{sub} «{q[:28]}» +{n} → 共 {len(posts)}",
                  flush=True)


def main(out_path):
    QS = QUERIES + (QUERIES2 if '--round2' in sys.argv else [])
    jobs = [(lens, q, sub, 0) for lens, q, subs in QS for sub in subs]
    total = len(jobs)
    jobs = [(a, b, c, total) for a, b, c, _ in jobs]
    print(f"共 {total} 组查询，{WORKERS} 并发", flush=True)
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(work, jobs))

    items = sorted(posts.values(),
                   key=lambda x: -((x["score"] or 0) + 3 * (x["ncom"] or 0)))
    pathlib.Path(out_path).write_text(json.dumps(
        {"items": items, "failed": failed,
         "stats": {"posts": len(items), "failed_queries": len(failed),
                   "total_queries": total}}, ensure_ascii=False), encoding="utf-8")
    print(f"\n完成：{len(items)} 帖，失败 {len(failed)}/{total} → {out_path}", flush=True)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    main(sys.argv[1] if len(sys.argv) > 1 else "reddit_corpus.json")
