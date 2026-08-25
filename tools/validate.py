#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""invest-coach 内容门禁校验器。

用法: python tools/validate.py [path/to/site.json]
规则编号对应 docs/工程化规范.md §5。ERROR 非零退出（build.py 据此拒绝构建）。
第 2 步才生效的规则（x_covers 全覆盖、quiz 结构、review_bank 覆盖、pair id 必填）
在对应字段尚为空时降级为 WARN 提示，字段一旦出现即全量校验。
"""
import json
import re
import sys
import pathlib
from collections import defaultdict

TOP_X = {"x_note", "x_version", "x_coaches", "x_review_bank", "x_lab", "x_facts"}
NODE_X = {"x_qtype", "x_level", "x_pairs", "x_coach_notes", "x_prov", "x_cards", "x_ruleout", "x_selfcheck", "x_anchors", "x_casefile"}
QUIZ_X = {"x_pair", "x_kind", "x_id"}
COACH_X = {"x_identity"}
REAL_MARKERS = ("Sunbeam", "Dell", "A 公司", "B 公司", "本章案主", "案主")
EDGE_TYPES = {"hard", "soft", "cross"}
PAIR_FIELDS = ("look", "a", "b", "key")
LEVELS = {"L1", "L2"}
KINDS = {"main", "pretest", "decision", "review"}
COACH_WHEN = {"correct", "wrong", "overconfident", "underconfident", "hint_used",
              "na_honest", "na_dodge", "pair_repeat", "streak", "complete"}
# R14 类型闸：canon.formal 命中左侧词 ⇒ canon.source 的 type 必须含右侧词之一
TYPE_GATES = [
    (("SEC 认定", "SEC 指控", "AAER", "证监会认定"), ("官方认定",)),
    (("ASC ", "IFRS ", "IAS ", "五步模型"), ("会计准则",)),
]
# R15 时代闸：概念不得早于其 source 的年份
ERA = [("现金流量表", 1987), ("ASC 606", 2014), ("IFRS 15", 2014), ("DSRI", 1999), ("M-Score", 1999)]
# R21 provenance 待办标记（不是已裁撤的合规禁词扫描）
TODO_MARKERS = ("待核", "待补", "待定稿", "TODO", "推荐沿用", "候选方向")


def check_quiz(q, loc, deep, errors, warns, na_stats, qids):
    """R6/R17/R19/R20：题的结构、答案键、深层节点必备字段。"""
    for k in q:
        if k.startswith("x_") and k not in QUIZ_X:
            errors.append(f"{loc}: quiz 未登记字段 {k}")
    if "llm" in json.dumps(q).lower() or "judge" in json.dumps(q).lower():
        errors.append(f"{loc}: 题内出现 llm/judge 相关键或值（v3 §2.6 判分只能是规则引擎）")
    qid = q.get("x_id")
    if not qid:
        errors.append(f"{loc}: quiz 缺稳定 x_id（遥测/档案/勘误的主键）")
    elif qid in qids:
        errors.append(f"{loc}: x_id「{qid}」重复")
    else:
        qids.add(qid)
    kind = q.get("x_kind")
    if kind not in KINDS:
        errors.append(f"{loc}: x_kind「{kind}」不在 {sorted(KINDS)}")
    opts = q.get("opts") or []
    oks = [o for o in opts if o.get("ok")]
    nas = [o for o in opts if o.get("na")]
    if len(opts) < 2 or not oks:
        errors.append(f"{loc}: quiz 需 ≥2 选项且 ≥1 正确")
    # R20 答案键约束：只有 decision 题允许多正确（防「多标一个正确」这种一行 diff 的错知识投递）
    if kind in ("main", "pretest", "review") and len(oks) != 1:
        errors.append(f"{loc}: x_kind={kind} 必须恰有 1 个 ok:true，现有 {len(oks)}")
    if len(nas) > 1:
        errors.append(f"{loc}: 「无法判断」选项不得多于 1 个")
    # R17 深层节点（带 x_level）的正题与复训题必须有信心标注、三级提示、无法判断选项
    if deep and kind in ("main", "pretest", "review"):
        if not q.get("confidence"):
            errors.append(f"{loc}: 深层节点的 {kind} 题必须 confidence=true")
        if len(q.get("hints") or []) != 3:
            errors.append(f"{loc}: 需恰好 3 条 hints，现有 {len(q.get('hints') or [])}")
        if not nas:
            errors.append(f"{loc}: 深层节点的 {kind} 题必须含「无法判断」选项（opts[].na）")
    if not q.get("fb"):
        errors.append(f"{loc}: quiz 缺 fb（答后解释）")
    # R22 统计「无法判断」是否为正确答案，用于分布锚
    if q.get("confidence"):
        na_stats.append(bool(nas and nas[0].get("ok")))


def node_hash(n):
    """节点内容指纹：canon/desc/evidence/screens/x_pairs 任何改动都会使已有审核签字过期。"""
    import hashlib
    core = {k: n.get(k) for k in ("desc", "canon", "evidence", "screens", "x_pairs", "x_coach_notes")}
    return hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


TAG = re.compile(r"<[^>]+>")
NUMTOK = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")


def check_facts(data, facts_path, errors, warns):
    """R12：真实公司语境中的数字必须命中数字账本；R11b：原档 sha256 必须与账本一致。"""
    import hashlib
    fp = pathlib.Path(facts_path)
    if not fp.exists():
        errors.append("缺少数字账本 content/ch1/facts.json")
        return
    facts = json.loads(fp.read_text(encoding="utf-8"))
    allowed = set(facts.get("approved_tokens", {}))
    for ef in facts.get("evidence_files", []):
        f = fp.parent.parent.parent / ef["file"]
        if not f.exists():
            errors.append(f"原档缺失: {ef['file']}")
        elif hashlib.sha256(f.read_bytes()).hexdigest() != ef["sha256"]:
            errors.append(f"原档被改动（sha256 不符）: {ef['file']}")

    def scan(s, loc):
        if not isinstance(s, str) or not any(m in s for m in REAL_MARKERS):
            return
        visible = TAG.sub(" ", s)
        for tok in NUMTOK.findall(visible):
            if tok.replace(",", "") not in allowed:
                errors.append(f"{loc}: 真实公司语境出现未登记数字「{tok}」——先核定进 facts.json")

    def walk(o, loc):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{loc}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{loc}[{i}]")
        else:
            scan(o, loc)

    for n in data.get("nodes", []):
        walk({k: n.get(k) for k in ("desc", "screens", "x_pairs", "x_coach_notes")}, n["id"])
    walk(data.get("x_review_bank", []), "bank")


def validate(path, release=False):
    errors, warns = [], []
    na_stats = []
    qids = set()
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    ids = [n.get("id") for n in nodes]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        errors.append(f"重复节点 id: {sorted(dup)}")
    nmap = {n["id"]: n for n in nodes}
    src_names = {s.get("name") for s in data.get("sources", [])}
    src_types = {s.get("name"): s.get("type", "") for s in data.get("sources", [])}
    # 从 source 的 name/note 里抽出四位年份（R15 时代闸用；缺失则跳过该源的时代检查）
    src_years = {}
    for s in data.get("sources", []):
        yrs = [int(y) for y in re.findall(r"(1[89]\d\d|20\d\d)", (s.get("name") or "") + " " + (s.get("note") or ""))]
        if yrs:
            src_years[s.get("name")] = min(yrs)

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
        # R14 类型闸：官方认定类主张只能挂官方认定档，准则类只能挂准则
        formal = c.get("formal") or ""
        stype = src_types.get(c.get("source"), "")
        for triggers, need in TYPE_GATES:
            if any(t in formal for t in triggers):
                if not any(nd in stype for nd in need):
                    errors.append(
                        f"{nid}: canon.formal 含{need[0]}类主张，但 source「{c.get('source')}」的 type 是「{stype}」")
        # R16 出处必须精确到可复核的章节/页/条款（填不出章节号的弱挂靠会自然暴露）
        for k in c:
            if k.startswith("x_") and k != "x_cite":
                errors.append(f"{nid}: canon 未登记字段 {k}")
        if not c.get("x_cite"):
            warns.append(f"{nid}: canon.x_cite 为空——出处未精确到章节/页/条款，需查原档后补（禁止编造）")
        # R15 时代闸：canon 提到的概念不得早于其出处年份
        syear = src_years.get(c.get("source"))
        if syear:
            for concept, earliest in ERA:
                if concept in formal and syear < earliest:
                    errors.append(
                        f"{nid}: canon.formal 提到「{concept}」（最早 {earliest}）但 source 年份为 {syear}")
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
        deep = "x_level" in n
        if deep:
            if n.get("x_level") not in LEVELS:
                errors.append(f"{nid}: x_level「{n.get('x_level')}」不在 {sorted(LEVELS)}")
            ps = n.get("x_pairs") or []
            if not 1 <= len(ps) <= 3:
                errors.append(f"{nid}: 带 x_level 的节点需 1–3 个 x_pairs，现有 {len(ps)}")
            for i, p in enumerate(ps):
                for k in PAIR_FIELDS:
                    if not p.get(k):
                        errors.append(f"{nid}: x_pairs[{i}].{k} 为空")
                if not p.get("id"):
                    errors.append(f"{nid}: x_pairs[{i}] 缺 id")
        # R5b/R6/R17/R19/R20 屏与题
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
                check_quiz(q, f"{nid}/screens[{si}]", deep, errors, warns, na_stats, qids)
        # R18 x_covers：有 screens 就查全覆盖，空集即 ERROR（去掉旧实现的短路）
        if screens:
            if covered != set(range(len(ev))):
                errors.append(f"{nid}: x_covers 未全覆盖 evidence（已覆盖 {sorted(covered)}，需 {list(range(len(ev)))}）")
        # R23 x_prov：来源与审核签字（reviewed 为空=未审：平时 WARN，--release 时 ERROR）
        pv = n.get("x_prov") or {}
        for k in ("drafted_by", "model", "drafted_at"):
            if not pv.get(k):
                errors.append(f"{nid}: x_prov.{k} 缺失（LLM 产出必须登记来源）")
        if screens:
            if not pv.get("reviewed_by"):
                (errors if release else warns).append(f"{nid}: 未经人工审核签字（x_prov.reviewed_by 为空）" + ("" if release else "——poc-trial 定版（--release）前必须补"))
            elif pv.get("reviewed_hash") != node_hash(n):
                errors.append(f"{nid}: 审核已过期——内容 hash 与 x_prov.reviewed_hash 不符，改动后必须重审")

    # R8 复训题库：增量门禁——screens 已填的节点，其混淆对必须 a/b 双面入库（ERROR）；
    # screens 未填节点的混淆对缺库仅 WARN（批次推进中允许）。库内 quiz 结构一并校验。
    bank = data.get("x_review_bank") or []
    all_pair_ids = {p.get("id") for n in nodes for p in (n.get("x_pairs") or []) if p.get("id")}
    seen_sides = defaultdict(set)
    for bi, item in enumerate(bank):
        pid, side = item.get("pair_id"), item.get("side")
        loc = f"x_review_bank[{bi}]（{pid}/{side}）"
        seen_sides[pid].add(side)
        if side not in ("a", "b"):
            errors.append(f"{loc}: side 必须是 a 或 b")
        if pid not in all_pair_ids:
            errors.append(f"{loc}: pair_id 不存在于任何节点的 x_pairs")
        q = item.get("quiz") or {}
        # R20 复训题的 quiz.x_pair 必须与外层 pair_id 一致（防复训队列训练相反判别）
        if q.get("x_pair") != pid:
            errors.append(f"{loc}: quiz.x_pair「{q.get('x_pair')}」与外层 pair_id 不一致")
        check_quiz(q, loc, True, errors, warns, na_stats, qids)
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

    # R19 教练：canon_sources 必须命中 sources[]；when 枚举；台词长度；人格字段不得出现出处作者姓氏
    author_tokens = set()
    for nm in src_names:
        for tok in re.findall(r"[A-Z][a-zA-Z]{3,}", nm or ""):
            if tok not in ("SEC", "FASB", "IFRS", "IAS", "ASC"):
                author_tokens.add(tok)
    for ci, co in enumerate(data.get("x_coaches") or []):
        loc = f"x_coaches[{ci}]({co.get('id')})"
        for cs in co.get("canon_sources") or []:
            if cs not in src_names:
                errors.append(f"{loc}: canon_sources「{cs}」未命中 sources[]")
        if not co.get("canon_sources"):
            errors.append(f"{loc}: canon_sources 为空（学派出处必填）")
        if not co.get("x_identity"):
            errors.append(f"{loc}: x_identity 为空（AI 披露与身份自述必填，被问身份时逐字输出）")
        for k in co:
            if k.startswith("x_") and k not in COACH_X:
                errors.append(f"{loc}: 未登记的教练字段 {k}")
        persona_text = (co.get("name") or "") + " " + " ".join(l.get("t", "") for l in co.get("style_lines") or [])
        for tok in author_tokens:
            if tok in persona_text:
                errors.append(f"{loc}: 人格字段（name/style_lines）出现出处作者名「{tok}」——真人名只能出现在 intro/canon_sources")
        for li, ln in enumerate(co.get("style_lines") or []):
            if ln.get("when") not in COACH_WHEN:
                errors.append(f"{loc}: style_lines[{li}].when「{ln.get('when')}」不在枚举内")
            if len(ln.get("t") or "") > 40:
                errors.append(f"{loc}: style_lines[{li}] 超过 40 字")

    # R12/R11b 数字账本与原档指纹
    check_facts(data, pathlib.Path(path).parent / "facts.json", errors, warns)

    # R24 判卷台（v2 形态）：深层节点必须齐备证据卡/排除项/自评清单/锚题
    bank_ids = {it.get("quiz", {}).get("x_id") for it in (data.get("x_review_bank") or [])}
    ROLES = {"support", "distractor", "irrelevant"}
    VERDICTS = {"excluded", "not_excluded", "insufficient"}
    for n in nodes:
        if "x_level" not in n or not n.get("screens"):
            continue
        nid = n["id"]
        cards = n.get("x_cards") or []
        if len(cards) < 4:
            errors.append(f"{nid}: x_cards 少于 4 张（判卷台需要可挑选的证据池）")
        if not any(c.get("role") == "support" for c in cards):
            errors.append(f"{nid}: x_cards 缺 support 卡")
        if not any(c.get("role") == "distractor" for c in cards):
            errors.append(f"{nid}: x_cards 缺 distractor 卡（无干扰位则挑证据退化为全选）")
        for c in cards:
            if c.get("role") not in ROLES:
                errors.append(f"{nid}: x_cards[{c.get('id')}] role 非法")
        for r in n.get("x_ruleout") or []:
            if r.get("verdict") not in VERDICTS:
                errors.append(f"{nid}: x_ruleout[{r.get('id')}] verdict 非法")
            if not r.get("fb"):
                errors.append(f"{nid}: x_ruleout[{r.get('id')}] 缺 fb")
        sc = n.get("x_selfcheck") or []
        if len(sc) != len(n.get("evidence") or []):
            errors.append(f"{nid}: x_selfcheck 条数与 evidence 不一致")
        anchors = n.get("x_anchors") or []
        if len(anchors) < 2:
            errors.append(f"{nid}: x_anchors 少于 2 个（锚题需换壳变体防背题）")
        for a in anchors:
            if a not in bank_ids:
                errors.append(f"{nid}: 锚题 {a} 不在复训库中")

    # R25 案卷（v3）：status 枚举、面板类型、溯源徽标命中数字账本
    import json as _j, pathlib as _p
    _fp=_p.Path(path).parent/'facts.json'
    _fids=set()
    if _fp.exists():
        _fids={f["id"] for f in _j.loads(_fp.read_text(encoding="utf-8")).get("facts",[])}
    CF_STATUS={"settled","regulator_asked","teaching"}
    CF_KIND={"cmp","trend","note","quote"}
    for n in nodes:
        cf=n.get("x_casefile")
        if not cf: 
            if "x_level" in n and n.get("screens"):
                warns.append(f"{n['id']}: 深层节点缺 x_casefile（材料屏仍是旧教学屏串接）")
            continue
        if cf.get("status") not in CF_STATUS:
            errors.append(f"{n['id']}: x_casefile.status「{cf.get('status')}」不在 {sorted(CF_STATUS)}")
        if cf.get("status")!="teaching" and not cf.get("srcs"):
            errors.append(f"{n['id']}: 非 teaching 案卷必须有溯源徽标 srcs")
        for pn in cf.get("panels") or []:
            if pn.get("kind") not in CF_KIND:
                errors.append(f"{n['id']}: 案卷面板 kind「{pn.get('kind')}」非法")
        for s in cf.get("srcs") or []:
            if s.get("f") not in _fids:
                errors.append(f"{n['id']}: 溯源徽标指向未登记事实「{s.get('f')}」")

    # R21 provenance 待办标记扫描（非合规禁词扫描）
    blob = json.dumps(data, ensure_ascii=False)
    for mk in TODO_MARKERS:
        if mk in blob:
            errors.append(f"内容中出现待办标记「{mk}」——未核定内容不得进入内容源")

    # R22 「无法判断」为正确答案的占比锚（目标 20–30%，见 知识可靠性与LLM边界_v1.md §6）
    if na_stats:
        ratio = sum(na_stats) / len(na_stats)
        line = f"「无法判断」为正确答案占比 {ratio:.0%}（{sum(na_stats)}/{len(na_stats)} 道信心题，目标 20–30%）"
        if ratio < 0.10 or ratio > 0.45:
            errors.append(line + " —— 偏离一倍以上")
        elif not 0.20 <= ratio <= 0.30:
            warns.append(line)
        else:
            print("INFO :", line)

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
    args = [a for a in sys.argv[1:] if a != "--release"]
    release = "--release" in sys.argv[1:]
    default = pathlib.Path(__file__).resolve().parent.parent / "content" / "ch1" / "site.json"
    sys.exit(validate(args[0] if args else default, release=release))
