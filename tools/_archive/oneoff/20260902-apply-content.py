#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性：把 build/newcontent/out-*.json 合并写回 site.json。

写的是四样东西：
  bank     → x_review_bank 追加条目
  pairs    → 对应节点的 x_pairs 追加混淆对
  anchors  → 对应节点的 x_anchors 设为闭卷题 id
  screens  → find-filings 的 screens

写回前逐条校验，任一不合格整体拒绝：
  - x_id 全站唯一
  - x_pair == pair_id，且该 pair 确实存在（含本次新增的）
  - 复习题按最严标准：confidence / 恰好 3 hints / 有 na 选项 / 恰好 1 个 ok
  - anchors 指向的 id 必须在 bank 里
  - 每对每面 ≥2 道

用法: python tools/_archive/oneoff/20260902-apply-content.py [--dry]
"""
import glob
import json
import pathlib
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[3]
SITE = ROOT / "content" / "ch1" / "site.json"
SRC = ROOT / "build" / "newcontent"

# 混淆对属于哪个节点（与审图 v2 附录 A5 一致）
PAIR_OWNER = {
    "ts-p1": "three-statements", "gr-p1": "growth-rate", "ff-p1": "find-filings",
    "ab-p1": "accrual-basis", "ar-p1": "receivables", "cf-p1": "ocf",
    "br-p1": "base-rate", "fs-p1": "falsification", "cl-p1": "checklist-after",
}


def main(dry):
    d = json.loads(SITE.read_text(encoding="utf-8"))
    by = {n["id"]: n for n in d["nodes"]}
    bank, pairs, anchors, screens = [], {}, {}, None
    for f in sorted(SRC.glob("out-*.json")):
        o = json.loads(f.read_text(encoding="utf-8"))
        bank += o.get("bank", [])
        pairs.update(o.get("pairs", {}))
        anchors.update(o.get("anchors", {}))
        if o.get("screens"):
            screens = o["screens"]

    bad = []
    have_ids = {i["quiz"]["x_id"] for i in d["x_review_bank"]}
    have_ids |= {s["quiz"]["x_id"] for n in d["nodes"] for s in n.get("screens", [])
                 if s.get("quiz")}
    known_pairs = {p["id"] for n in d["nodes"] for p in n.get("x_pairs") or []} | set(pairs)

    for it in bank:
        q = it.get("quiz") or {}
        L = f"{it.get('pair_id')}/{it.get('side')}/{q.get('x_id')}"
        if q.get("x_id") in have_ids:
            bad.append(f"{L}: x_id 与现有重复")
        have_ids.add(q.get("x_id"))
        if it.get("side") not in ("a", "b"):
            bad.append(f"{L}: side 非法")
        if it.get("pair_id") not in known_pairs:
            bad.append(f"{L}: pair_id 不存在")
        if q.get("x_pair") != it.get("pair_id"):
            bad.append(f"{L}: x_pair 与 pair_id 不一致")
        if q.get("x_kind") != "review":
            bad.append(f"{L}: x_kind 不是 review")
        if not q.get("confidence"):
            bad.append(f"{L}: 缺 confidence")
        if len(q.get("hints") or []) != 3:
            bad.append(f"{L}: hints 不是 3 条")
        opts = q.get("opts") or []
        if not any(o.get("na") for o in opts):
            bad.append(f"{L}: 缺「无法判断」选项")
        if sum(1 for o in opts if o.get("ok")) != 1:
            bad.append(f"{L}: ok 不是恰好 1 个")
        if not q.get("fb"):
            bad.append(f"{L}: 缺 fb")

    for pid, p in pairs.items():
        if pid not in PAIR_OWNER:
            bad.append(f"混淆对 {pid} 不在审图 v2 登记的九对里")
        for k in ("id", "look", "a", "b", "key"):
            if not p.get(k):
                bad.append(f"混淆对 {pid} 缺 {k}")

    new_ids = {i["quiz"]["x_id"] for i in bank}
    for nid, ids in anchors.items():
        if nid not in by:
            bad.append(f"anchors 指向不存在的节点 {nid}")
        for i in ids:
            if i not in new_ids:
                bad.append(f"{nid} 的闭卷题 {i} 不在本次 bank 里")
        if len(ids) < 2:
            bad.append(f"{nid} 的闭卷题不足 2 道")

    # 每对每面 ≥2
    cnt = Counter((i["pair_id"], i["side"]) for i in d["x_review_bank"] + bank)
    for pid in known_pairs:
        for side in ("a", "b"):
            if cnt[(pid, side)] < 2:
                bad.append(f"混淆对 {pid} 的 {side} 面只有 {cnt[(pid, side)]} 道（要求 ≥2）")

    if bad:
        print(f"拒绝写回，{len(bad)} 处不合格：")
        for b in bad[:20]:
            print("  ", b)
        return 1

    if dry:
        print(f"预演通过：bank +{len(bank)}，混淆对 +{len(pairs)}，"
              f"闭卷题 {len(anchors)} 个节点，屏 {len(screens or [])} 个")
        return 0

    d["x_review_bank"] += bank
    for pid, p in pairs.items():
        by[PAIR_OWNER[pid]].setdefault("x_pairs", []).append(p)
    for nid, ids in anchors.items():
        by[nid]["x_anchors"] = ids
    if screens:
        by["find-filings"]["screens"] = screens
    SITE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已写回：bank +{len(bank)}（共 {len(d['x_review_bank'])}），"
          f"混淆对 +{len(pairs)}，{len(anchors)} 个节点配了闭卷题，"
          f"find-filings 屏 {len(screens or [])} 个")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main("--dry" in sys.argv))
