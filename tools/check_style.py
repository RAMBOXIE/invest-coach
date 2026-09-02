#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文风门禁 —— 挡行业黑话与 AI 腔，只减不增。

产品要求：**只用清晰的专业语言。** 两类东西要挡：

1. **黑话**：比喻性、江湖气、游戏化的词（红旗、实锤、对决、点亮、通关…）。
   有些词在代码里做内部命名没问题，用户读不到；这里**只数用户能读到的文案**。
2. **AI 腔**：不是错，是密度问题。破折号抒情、「不是 X，是 Y」的对偶、
   正文里加粗当格言——单看每一句都通顺，密度一高，通篇就有一股机器味。
   基线建立时实测：68,914 字里 304 个破折号，平均每 227 字一个。

棘轮策略与 check_tokens 相同：记录基线，**只挡新增**。改好一处降一处
（`--update` 写回，只允许下降）。

用法:
  python tools/check_style.py            # 校验
  python tools/check_style.py --update   # 把当前计数写回基线（只允许下降）
  python tools/check_style.py --list 破折号   # 列出某一项的全部命中，带定位
  python tools/check_style.py --selftest      # 变异测试
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = ROOT / "design" / "style-debt.json"
SITE = ROOT / "content" / "ch1" / "site.json"
STORIES = ROOT / "content" / "stories"
UI = [ROOT / "src" / "template.html", ROOT / "src" / "parts" / "court.js",
      ROOT / "src" / "parts" / "story.js"]

# 用户读不到的字段：内部 id、类型标记、出处、机器用的键。数它们等于逼人改代码去凑数字。
SKIP_KEYS = {
    "id", "x_id", "case_id", "pair_id", "kind", "x_kind", "type", "fact", "src",
    "line", "accession", "sha256", "url", "x_covers", "x_anchors", "x_pair",
    "knowledge_node", "twin_case_ref", "side", "icon", "avatar", "domain",
    "x_version", "cv", "era", "status", "verdict", "label",
    "_note", "note", "x_note", "x_prov", "sources", "source", "textbook", "x_cite",
    "canon",           # 正典是教材原话，不是我们的文案
    "match",           # 匹配用户输入的关键词，用户读不到；改了会让匹配失效
}

# ── 黑话表：用户能读到的比喻/江湖气/游戏化用词 ──────────────────────
JARGON = {
    # 军事 + 医学：两层比喻叠在一起（先解码「旗」，再解码「阳」）
    "红旗": "按语境改：两个被命名的检测项→「异常信号一/二」；「红旗成立」→「信号成立」；"
            "文献引用处写「Schilit 所称 red flags（财务预警信号）」，明示是引文",
    "亮旗": "改「判定信号成立，转入核查」，短处用「转入核查」",
    "降旗": "改「解除疑点」",
    "喊旗": "改「直接认定」",
    "双阳": "改「两个信号同时成立」",
    "一阳一阴": "改「只有一个信号成立」",
    "阳性": "改「成立」",
    # 法庭角色扮演
    "案卷": "改「材料」「财报材料」",
    "判卷": "改「分析」（「开始判卷」→「开始分析」）",
    "案主": "改「案例公司」，多数处可整句删掉",
    "定罪": "改「下造假结论」「认定舞弊」",
    "质问": "改「追问」",
    "证词": "改「陈述」「他写过的话」",
    "出庭": "改「可追问的人」",
    "戳穿": "改「与材料矛盾」",
    "实锤": "改「确证」",
    "铁证": "改「已可下结论」",
    # 游戏化
    "点亮": "改「通过」「已掌握」",
    "通关": "改「做完第一章」",
    "闯关": "改「练习」",
    "终局": "改「综合判断」",
    "对决": "改「对照」",
    "连胜": "改「连续答对」",
    "彩蛋": "改直述",
    "打怪": "改直述",
    "满血": "改直述",
    # 内部术语泄漏到用户可见处
    "锚题": "用户可见处改「闭卷题」；字段名 x_anchors 与代码内注释不动",
    "混淆对": "用户可见处改「易混题」「这组易混概念」；字段名 x_pairs 不动",
    "复训": "改「复习」",
    "雷区": "改「你最常判错的地方」",
    "判据": "改「判断依据」",
    "幕": "案例的戏剧化量词，用户可见处改「案例」；case_id/x_stories 等内部命名不动",
    # 自造伪术语（被当成既有会计名词在用）
    "步差": "改「增速差」；表示比值时写「增速比」",
    "两条腿": "首次引入的比喻可留，此后改「两个增速」",
    "欠条": "首次引入可留，此后改「应收账款」",
    # 网络口语
    "拉满": "改「完全满足」",
    "认怂": "改「回避」",
    "颗粒度": "改「具体程度」",
    "闭环": "改直述",
}

# ── AI 腔：密度指标 ────────────────────────────────────────────
FLAVOR = {
    "破折号": (r"——", "句末用破折号接一句升华。中文专业写作里它应当罕见"),
    "不是X是Y": (r"不是[^，。！？\n]{1,14}[，,]\s*(?:是|而是)", "对偶句式，密度一高就假"),
    "一回事": (r"是[^，。\n]{0,8}一回事", "「A 是一回事，B 是另一回事」"),
    "才是": (r"[这那]才是", "「这才是真正的…」"),
    "正文加粗": (r"\*\*[^*\n]+\*\*", "正文里加粗当格言用"),
    "恰恰": (r"恰恰", "转折强调词，AI 高频"),
    "唯一": (r"唯一", "绝对化强调"),
    "真正": (r"真正", "空洞强调"),
}


def user_text():
    """把**用户能读到的**文案摊平，返回 [(来源, 文本)]。"""
    out = []

    def walk(o, src, key=None, parent=None):
        if isinstance(o, dict):
            for k, v in o.items():
                # kind 多数时候是类型标记（quiz.x_kind、panel.kind），但在案例的
                # options[] 里装的是**屏上的分类标签**（「求证」「顺势」「定罪」）。
                # 一刀切跳过 kind，等于让一个用户天天看见的黑话词躲过门禁——
                # 「定罪」就是这么漏到线上的，截图里才看见。
                if k in SKIP_KEYS and not (k == "kind" and parent == "options"):
                    continue
                walk(v, src, k, key)
        elif isinstance(o, list):
            for v in o:
                walk(v, src, key, key)
        elif isinstance(o, str) and o.strip():
            out.append((f"{src}:{key}", o))

    walk(json.loads(SITE.read_text(encoding="utf-8")), "site.json")
    for f in sorted(STORIES.glob("*/case.json")):
        walk(json.loads(f.read_text(encoding="utf-8")), f.parent.name)
    # UI 文案：只取源码里的中文字符串字面量，注释与标识符不算
    for p in UI:
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8")
        s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
        s = re.sub(r"(?m)^\s*//[^\n]*", "", s)
        s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
        for m in re.finditer(r"['\"`]([^'\"`\n]*[一-鿿][^'\"`\n]*)['\"`]", s):
            out.append((p.name, m.group(1)))
    return out


def scan():
    items = user_text()
    counts, detail = {}, {}
    for word in JARGON:
        hits = [(src, t) for src, t in items if word in t]
        counts[word] = sum(t.count(word) for _, t in hits)
        detail[word] = hits
    for name, (pat, _) in FLAVOR.items():
        hits = [(src, t) for src, t in items if re.search(pat, t)]
        counts[name] = sum(len(re.findall(pat, t)) for _, t in items)
        detail[name] = hits
    counts["_字数"] = sum(len(t) for _, t in items)
    return counts, detail


def load_baseline():
    if not BASELINE.exists():
        return None
    return json.loads(BASELINE.read_text(encoding="utf-8")).get("counts", {})


def run():
    counts, detail = scan()
    base = load_baseline()
    chars = counts["_字数"]
    if base is None:
        print("ERROR: 没有基线文件 design/style-debt.json，先跑 --update 建立")
        return 1
    bad, better = [], []
    for k, n in sorted(counts.items()):
        if k.startswith("_"):
            continue
        b = base.get(k, 0)
        if n > b:
            why = JARGON.get(k) or FLAVOR.get(k, ("", ""))[1]
            bad.append(f"{k}：{n} 处，超过基线 {b} —— {why}")
        elif n < b:
            better.append(f"{k}：{b} → {n}")
    dash = counts.get("破折号", 0)
    density = round(chars / dash) if dash else 0
    print(f"INFO : 用户可读文案 {chars} 字；破折号 {dash} 个"
          + (f"（每 {density} 字一个）" if dash else ""))
    total_j = sum(counts.get(w, 0) for w in JARGON)
    print(f"INFO : 黑话合计 {total_j} 处；AI 腔指标合计 "
          f"{sum(counts.get(k, 0) for k in FLAVOR)} 处")
    for b in better:
        print("INFO : 已改善", b)
    for b in bad:
        print("ERROR:", b)
    print("STYLE:", "FAIL" if bad else "PASS")
    return 1 if bad else 0


def update():
    counts, _ = scan()
    base = load_baseline() or {}
    raised = [k for k, n in counts.items()
              if not k.startswith("_") and n > base.get(k, 10 ** 9)]
    if raised and base:
        print(f"ERROR: 这些项比基线高，棘轮只许下降：{', '.join(raised)}")
        return 1
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(
        {"_note": "文风棘轮基线。只减不增。改好一处跑 --update 降低它。"
                  "黑话见 check_style.py 的 JARGON，AI 腔指标见 FLAVOR。",
         "counts": counts}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"基线已写回 {BASELINE}")
    for k, v in sorted(counts.items()):
        print(f"  {k:12s} {v}")
    return 0


def show(which):
    _, detail = scan()
    hits = detail.get(which)
    if hits is None:
        print(f"没有这一项。可选：{', '.join(list(JARGON) + list(FLAVOR))}")
        return 1
    print(f"「{which}」共 {len(hits)} 处：\n")
    for src, t in hits:
        print(f"  [{src}] {t[:160]}")
    return 0


MUTATIONS = [("红旗", "site 里加一句黑话"), ("破折号", "site 里加一串破折号")]


def selftest():
    import subprocess
    orig = SITE.read_text(encoding="utf-8")
    bad = []
    for key, desc in MUTATIONS:
        try:
            d = json.loads(orig)
            add = "红旗成立" if key == "红旗" else "这样——那样——还有这样"
            d["about"] = (d.get("about") or "") + add
            SITE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            r = subprocess.run([sys.executable, str(pathlib.Path(__file__))],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace")
            if f"ERROR: {key}" not in r.stdout:
                bad.append(f"{key} {desc}：加了却没报错 —— 这条规则是摆设")
            else:
                print(f"  ✓ {key} {desc} → 规则正确报错")
        finally:
            SITE.write_text(orig, encoding="utf-8")
    print()
    for b in bad:
        print("ERROR:", b)
    print("RESULT:", "FAIL（门禁自身不可信）" if bad else
          f"PASS（{len(MUTATIONS)} 条通过变异测试）")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--list", metavar="项")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("_ignored", nargs="*", help="build.py 会把产物路径传进来，本门禁读源不读产物")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.update:
        return update()
    if a.list:
        return show(a.list)
    return run()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
