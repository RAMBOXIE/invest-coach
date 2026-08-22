#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""invest-coach 内容门禁校验器。

用法: python tools/validate.py [path/to/site.json]
规则编号对应 docs/工程化规范.md §5。ERROR 非零退出（build.py 据此拒绝构建）。
第 2 步才生效的规则（x_covers 全覆盖、quiz 结构、review_bank 覆盖、pair id 必填）
在对应字段尚为空时降级为 WARN 提示，字段一旦出现即全量校验。
"""
import json
import sys
import pathlib
from collections import defaultdict

TOP_X = {"x_note", "x_version", "x_coaches", "x_review_bank"}
NODE_X = {"x_qtype", "x_level", "x_pairs", "x_coach_notes"}
EDGE_TYPES = {"hard", "soft", "cross"}
PAIR_FIELDS = ("look", "a", "b", "key")


def validate(path):
    errors, warns = [], []
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    ids = [n.get("id") for n in nodes]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        errors.append(f"重复节点 id: {sorted(dup)}")
    nmap = {n["id"]: n for n in nodes}
    src_names = {s.get("name") for s in data.get("sources", [])}

    # R9 顶层 x_ 白名单
    for k in data:
        if k.startswith("x_") and k not in TOP_X:
            errors.append(f"未登记的顶层字段: {k}（先登记 docs/SCHEMA.md）")

    # 边基础检查
    hard, adj_all, adj_hard = [], defaultdict(list), defaultdict(list)
    for e in edges:
        f, t, ty = e.get("from"), e.get("to"), e.get("type")
        if f not in nmap or t not in nmap:
            errors.append(f"边引用不存在的节点: {f} -> {t}")
            continue
        if ty not in EDGE_TYPES:
            errors.append(f"非法边类型 {ty}: {f} -> {t}")
        if f == t:
            errors.append(f"自环: {f}")
        adj_all[f].append(t)
        if ty == "hard":
            hard.append((f, t))
            adj_hard[f].append(t)

    # R1 无环（全边集）
    color = {}

    def dfs(u):
        color[u] = 1
        for v in adj_all[u]:
            if color.get(v) == 1:
                return True
            if color.get(v, 0) == 0 and dfs(v):
                return True
        color[u] = 2
        return False

    if any(color.get(i, 0) == 0 and dfs(i) for i in nmap):
        errors.append("图中存在环")

    # R1b hard 边层深严格单调
    for f, t in hard:
        lf, lt = nmap[f].get("ageStart", 0), nmap[t].get("ageStart", 0)
        if not lf < lt:
            errors.append(f"hard 边层深未严格递增: {f}(L{lf}) -> {t}(L{lt})")

    # R2 hard 闭包传递冗余
    def reachable(u, banned):
        seen, stack = set(), [u]
        while stack:
            x = stack.pop()
            for v in adj_hard[x]:
                if (x, v) == banned:
                    continue
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        return seen

    for f, t in hard:
        if t in reachable(f, (f, t)):
            errors.append(f"传递冗余 hard 边: {f} -> {t}")

    # R3 根节点
    has_in = {t for _, t in hard}
    roots = [i for i in nmap if i not in has_in]
    if not roots:
        errors.append("没有根节点（所有节点都有 hard 入边）")

    # 逐节点检查
    screens_pending = 0
    for n in nodes:
        nid = n.get("id", "?")
        # R4 canon 完整且 source 命中 sources[]
        c = n.get("canon") or {}
        for k in ("term", "formal", "source", "textbook"):
            if not c.get(k):
                errors.append(f"{nid}: canon.{k} 为空")
        if c.get("source") and c["source"] not in src_names:
            errors.append(f"{nid}: canon.source「{c['source']}」未命中 sources[]")
        # R5 evidence 2–3 条
        ev = n.get("evidence") or []
        if not 2 <= len(ev) <= 3:
            errors.append(f"{nid}: evidence {len(ev)} 条（要求 2–3）")
        # R9 节点 x_ 白名单
        for k in n:
            if k.startswith("x_") and k not in NODE_X:
                errors.append(f"{nid}: 未登记的节点字段 {k}")
        # R10 name 长度
        if len(n.get("name", "")) > 7:
            warns.append(f"{nid}: name 超过 7 字")
        # R7 有 x_level 的节点（红旗/案例）必须有 1–3 个混淆对
        if "x_level" in n:
            ps = n.get("x_pairs") or []
            if not 1 <= len(ps) <= 3:
                errors.append(f"{nid}: 带 x_level 的节点需 1–3 个 x_pairs，现有 {len(ps)}")
            for i, p in enumerate(ps):
                for k in PAIR_FIELDS:
                    if not p.get(k):
                        errors.append(f"{nid}: x_pairs[{i}].{k} 为空")
                if not p.get("id"):
                    warns.append(f"{nid}: x_pairs[{i}] 缺 id（第 2 步起必填）")
        # R5b/R6 屏与题（字段出现即校验）
        screens = n.get("screens") or []
        if not screens:
            screens_pending += 1
        covered = set()
        for si, s in enumerate(screens):
            for k in s:
                if k.startswith("x_") and k != "x_covers":
                    errors.append(f"{nid}: screens[{si}] 未登记字段 {k}")
            covered.update(s.get("x_covers", []))
            q = s.get("quiz")
            if q:
                opts = q.get("opts") or []
                if len(opts) < 2 or not any(o.get("ok") for o in opts):
                    errors.append(f"{nid}: screens[{si}] quiz 需 ≥2 选项且 ≥1 正确")
        if screens and any("quiz" in s for s in screens):
            if covered and covered != set(range(len(ev))):
                errors.append(f"{nid}: x_covers 未全覆盖 evidence（已覆盖 {sorted(covered)}）")

    # R8 复训题库：增量门禁——screens 已填的节点，其混淆对必须 a/b 双面入库（ERROR）；
    # screens 未填节点的混淆对缺库仅 WARN（批次推进中允许）。库内 quiz 结构一并校验。
    bank = data.get("x_review_bank") or []
    seen_sides = defaultdict(set)
    for bi, item in enumerate(bank):
        seen_sides[item.get("pair_id")].add(item.get("side"))
        q = item.get("quiz") or {}
        opts = q.get("opts") or []
        if len(opts) < 2 or not any(o.get("ok") for o in opts):
            errors.append(f"x_review_bank[{bi}]（{item.get('pair_id')}/{item.get('side')}）quiz 需 ≥2 选项且 ≥1 正确")
    for n in nodes:
        for p in n.get("x_pairs") or []:
            pid = p.get("id")
            if not pid:
                continue
            sides = seen_sides.get(pid, set())
            if sides != {"a", "b"}:
                msg = f"混淆对 {pid} 复训库未齐 a/b 双面（现有 {sorted(sides) or '无'}）"
                if n.get("screens"):
                    errors.append(msg)
                else:
                    warns.append(msg + "（该节点 screens 未填，暂不强制）")

    if screens_pending:
        warns.append(f"{screens_pending} 个节点 screens 为空（第 2 步待填）")

    print(f"nodes={len(nodes)} edges={len(edges)}(hard={len(hard)}) roots={sorted(roots)}")
    for w in warns:
        print("WARN :", w)
    for e in errors:
        print("ERROR:", e)
    print("RESULT:", "FAIL" if errors else "PASS")
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    default = pathlib.Path(__file__).resolve().parent.parent / "content" / "ch1" / "site.json"
    sys.exit(validate(sys.argv[1] if len(sys.argv) > 1 else default))
