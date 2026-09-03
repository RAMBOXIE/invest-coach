#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D10：把 48 道题的干扰项落地（执行快照，不可重跑）。

工作流产出 scratchpad/d10_out/<x_id>.json，这个脚本把它们写进 site.json。
**落地前逐条自查**——agent 交的东西不能直接信：

  A1 idx 必须指向一个非正确、非「无法判断」的选项（改错位置等于篡改答案键）
  A2 不许出现题干与该选项原文里都没有的数字（数字账本门禁 R12/S6 之外再挡一道，
     因为它们只覆盖真实公司语境，教学题里的编造数字挡不住）
  A3 不许出现黑话与禁用写法（check_style 的棘轮会挡，但这里先挡一次好定位）
  A4 至少有一个被改的干扰项**严格长于**正确项——这是这次改动的全部目的
  A5 答案键（ok / na / mis）一个都不许变

用法: python tools/_archive/oneoff/20260903-d10-干扰项重写.py [--apply]
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
SITE = ROOT / "content" / "ch1" / "site.json"
OUT = pathlib.Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else None

JARGON = ("红旗", "亮旗", "降旗", "喊旗", "双阳", "一阳一阴", "阳性", "案卷", "判卷", "案主",
          "定罪", "质问", "证词", "出庭", "戳穿", "实锤", "铁证", "点亮", "通关", "闯关",
          "终局", "对决", "连胜", "彩蛋", "打怪", "满血", "锚题", "混淆对", "复训", "雷区",
          "判据", "步差", "两条腿", "欠条", "拉满", "认怂", "颗粒度", "闭环")
BADSTYLE = (("——", "破折号"), ("**", "星号加粗"), ("真正", "空洞强调"),
            ("恰恰", "AI 高频转折"), ("唯一", "绝对化强调"))
# 只认**数值**，不认量词。第一版把中文数字单字全算数字，于是「多半」「一下」
# 这类词被判成「凭空写了一个数字」。要挡的是编造的数值（+38%、3 亿、45 天），
# 判据是「数字后面跟着单位」——单字量词不构成一个数值主张。
NUM = re.compile(r"[0-9]+(?:[.,][0-9]+)*\s*(?:%|个百分点|个点|倍|成|天|年|月|季|亿|万|元)?"
                 r"|[一二三四五六七八九十百千]+\s*(?:倍|成|天|亿|万|元|个点|个百分点)")
plain = lambda s: re.sub(r"<[^>]+>", "", s or "")


def items(site):
    out = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("opts") and o.get("x_kind"):
                out.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(site)
    return out


def main():
    site = json.loads(SITE.read_text(encoding="utf-8"))
    byid = {q.get("x_id"): q for q in items(site)}
    files = sorted(OUT.glob("*.json"))
    applied, refused, skipped = [], [], []
    for f in files:
        p = json.loads(f.read_text(encoding="utf-8"))
        qid, rw = p.get("x_id"), p.get("rewrites") or []
        q = byid.get(qid)
        if not q:
            refused.append((qid, "题不存在")); continue
        if not rw:
            skipped.append((qid, "核验者判为不该改")); continue
        opts = q["opts"]
        stem = plain(q.get("q"))
        bad = []
        for r in rw:
            i, t = r.get("idx"), plain(r.get("t"))
            if not isinstance(i, int) or i < 0 or i >= len(opts):
                bad.append(f"idx {i} 越界"); continue
            o = opts[i]
            if o.get("ok"):
                bad.append(f"idx {i} 指向正确项")           # A1
            if o.get("na"):
                bad.append(f"idx {i} 指向「无法判断」")      # A1
            src_nums = set(NUM.findall(stem)) | set(NUM.findall(plain(o.get("t"))))
            new_nums = [n for n in NUM.findall(t) if n not in src_nums]
            if new_nums:
                bad.append(f"idx {i} 出现新数字 {new_nums[:3]}")   # A2
            for w in JARGON:
                if w in t:
                    bad.append(f"idx {i} 含黑话「{w}」")            # A3
            for w, why in BADSTYLE:
                if w in t:
                    bad.append(f"idx {i} 含{why}「{w}」")           # A3
        if bad:
            refused.append((qid, "；".join(bad[:4]))); continue
        # A4 至少一条严格长于正确项
        corr = max(len(plain(o["t"])) for o in opts if o.get("ok"))
        if not any(len(plain(r["t"])) > corr for r in rw):
            refused.append((qid, f"最长的改写仍不超过正确项（{corr} 字）")); continue
        # A5 落地：只写 t
        keys_before = [(o.get("ok"), o.get("na"), o.get("mis")) for o in opts]
        for r in rw:
            # 全库 199 条选项文案没有一条以句号结尾；改写稿偶尔会带上，统一掉。
            opts[r["idx"]]["t"] = r["t"].rstrip().rstrip("。")
        keys_after = [(o.get("ok"), o.get("na"), o.get("mis")) for o in opts]
        assert keys_before == keys_after, f"{qid} 答案键被改动"
        applied.append(qid)
    print(f"落地 {len(applied)} 道；拒收 {len(refused)} 道；核验者主动跳过 {len(skipped)} 道")
    for qid, why in refused:
        print(f"  拒收 {qid}：{why}")
    for qid, why in skipped:
        print(f"  跳过 {qid}：{why}")
    if "--apply" in sys.argv and applied:
        SITE.write_text(json.dumps(site, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已写回 {SITE}")
    else:
        print("（未加 --apply，只做自查）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
