#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""invest-coach 内容门禁校验器。

用法: python tools/validate.py [path/to/site.json]
ERROR 非零退出（build.py 据此拒绝构建）。
第 2 步才生效的规则（x_covers 全覆盖、quiz 结构、review_bank 覆盖、pair id 必填）
在对应字段尚为空时降级为 WARN 提示，字段一旦出现即全量校验。
"""
import hashlib
import html
import json
import re
import subprocess
import sys
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOP_X = {"x_note", "x_version", "x_coaches", "x_review_bank", "x_lab", "x_facts", "x_stories", "x_chapters"}
NODE_X = {"x_qtype", "x_level", "x_pairs", "x_coach_notes", "x_prov", "x_cards", "x_ruleout", "x_selfcheck", "x_anchors", "x_casefile", "x_chapter"}
QUIZ_X = {"x_pair", "x_kind", "x_id", "x_next"}
COACH_X = {"x_identity"}
# R12 触发词：出现这些词的字符串会被当作「真实公司语境」，其中的数字必须命中数字账本。
# 只列 Sunbeam/Dell 是个潜在漏洞——语料里还有 Nikola、Moderna、伯克希尔、雷曼，
# 往节点里放一个它们的例子，数字就完全不过账本检查。case.json 那边有更严的 S6 兜着，
# site.json 这边没有。补齐。
REAL_MARKERS = ("Sunbeam", "Dell", "Nikola", "Moderna", "Berkshire", "Lehman",
                "伯克希尔", "雷曼", "A 公司", "B 公司", "本章案主", "案主",
                "Costco", "好市多")
# 这些不是「教学数字」，是出处标识，不该要求绑 fact（与 S6 的豁免保持一致）：
# 申报号 0000950170-98-000413 ｜ 日期 2001-05-15 ｜ 行号 L1192 ｜ 年份 1997 年
PROV_TOKENS = re.compile(r"\d{10}-\d\d-\d{6}|\d{4}-\d\d-\d\d|\d{4}-\d\d(?!\d)|L\d+(?:[–-]L?\d+)?|"
                         r"\d+\s*年|\d{1,2}\s*月(?!\s*\d)|Item\s*\d+[A-C]?|p\.\d+")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")  # S7 日期归一化用，顺序即月份号
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
        errors.append(f"{loc}: 题内出现 llm/judge 相关键或值——"
                      "判分当前由确定性规则完成，这把锁挡的是「悄悄把判分接进 LLM」。"
                      "LLM 判分已不是永久禁区（docs/adr/0001），真要做时连同本锁一起改")
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


CASE_CORE = ("title", "subtitle", "hook", "cast", "beats", "knowledge_node",
             # interrogation 一度不在指纹里——而审问屏上全是「他写过的话」，
             # 是幕里最需要人核对的内容。不在指纹里就意味着：签完字之后
             # 把证词整段换掉，签字仍然有效，没有任何东西会喊一声。
             "interrogation")


def case_hash(c):
    """幕的内容指纹。签字绑它，内容一改签字自动过期。

    只有这一份实现。以前 validate 与 sign 各写一份，注释里写着「改一处要改两处」
    ——那是一句提醒，不是执行者。sign.py 现在直接调这个。
    """
    core = {k: c.get(k) for k in CASE_CORE}
    return hashlib.sha256(json.dumps(core, ensure_ascii=False,
                                     sort_keys=True).encode()).hexdigest()[:16]


TAG = re.compile(r"<[^>]+>")
NUMTOK = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")


# R28 允许不归档的原档，以及为什么。**空理由不算理由**，规则会拒绝。
# 这张表是「哪些引文没有机器背书」的唯一清单——不写在这里，它就只是一句
# 谁也不会去数的 WARN。原来六条 accession 没有归档，S7 对它们全部降级放行。
UNARCHIVED_OK = {
    # 2026-09-03 之前这里有 BRK-2007-letter（版权）。owner 裁决要用当事人的原话，
    # 两封信经 Wayback 取回入 evidence/，只作核对存档、不进产物，豁免撤销。
}


def check_evidence_coverage(F, errors):
    """R28：facts.json 里每条事实引用的 accession，都必须有归档原档。

    为什么单独一条：S7（引文锚定）在找不到原档时**只报 WARN 然后放行**，
    而这正是这个仓库反复栽的那种失败——检查还在，但它什么也没查。
    实测有六条 accession 从来没有归档：SEC 对 Sunbeam 的认定书、对 Dell 的
    和解、雷曼三份财报。也就是说产品里最硬的几句话（「SEC 认定至少 6,200 万
    来自舞弊」）从来没有任何东西核对过它是不是真在那份文件里。

    例外必须进 UNARCHIVED_OK 并写明理由，且理由一旦失效（文件其实归档了）
    这条规则会反过来要求删掉例外——例外表不许自己长草。
    """
    have = {e.get("accession") for e in F.get("evidence_files", [])}
    used = {}
    for f in F.get("facts", []):
        if f.get("accession"):
            used.setdefault(f["accession"], []).append(f["id"])
    for acc, fids in sorted(used.items()):
        if acc in have:
            continue
        why = UNARCHIVED_OK.get(acc)
        if not why:
            errors.append(
                f"R28 accession「{acc}」（{len(fids)} 条事实：{'、'.join(fids[:3])}）没有归档原档 —— "
                "S7 对它只会报 WARN 然后放行，这些引文的逐字性没有任何东西在查。"
                "要么把原档存进 evidence/ 并登记 sha256，要么进 UNARCHIVED_OK 并写明为什么不能归档")
    for acc, why in UNARCHIVED_OK.items():
        if not (why or "").strip():
            errors.append(f"R28 UNARCHIVED_OK 里「{acc}」没写理由——没有理由的豁免就是漏网")
        if acc in have:
            errors.append(f"R28 UNARCHIVED_OK 里的「{acc}」其实已经归档了，把这条例外删掉")
    if not errors:
        print(f"INFO : R28 {len(used)} 个 accession，{len(used) - len(UNARCHIVED_OK & used.keys())} 个有归档原档，"
              f"{len(UNARCHIVED_OK & used.keys())} 个有书面豁免 ✓")


def check_facts(data, facts_path, errors, warns):
    """R12：真实公司语境中的数字必须命中数字账本；R11b：原档 sha256 必须与账本一致。"""
    import hashlib
    fp = pathlib.Path(facts_path)
    if not fp.exists():
        errors.append("缺少数字账本 content/ch1/facts.json")
        return
    facts = json.loads(fp.read_text(encoding="utf-8"))
    check_evidence_coverage(facts, errors)
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
        visible = PROV_TOKENS.sub(" ", TAG.sub(" ", s))
        for tok in NUMTOK.findall(visible):
            if tok.replace(",", "") not in allowed:
                errors.append(f"R12 {loc}: 真实公司语境出现未登记数字「{tok}」——先核定进 facts.json")

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
        # x_casefile 是深层节点真正上屏的材料面板（screens 在它面前只是「补课」），
        # 里面全是真实公司数字，此前却不在 R12 的扫描范围里。补进来。
        walk({k: n.get(k) for k in ("desc", "screens", "x_pairs", "x_coach_notes", "x_casefile")}, n["id"])
    walk(data.get("x_review_bank", []), "bank")



def check_dirs():
    """R26：docs/STRUCTURE.md 的登记表 vs 仓库里真实存在的目录。

    未登记即 ERROR（纪律有执行者），登记了却不存在即 WARN（表过期了）。
    只看被 git 跟踪的文件所在的目录——忽略 dist/ build/ __pycache__ 这类产物。
    """
    root = pathlib.Path(__file__).resolve().parent.parent
    doc = root / "docs" / "STRUCTURE.md"
    if not doc.exists():
        return ["R26 找不到 docs/STRUCTURE.md——目录登记表是目录的唯一真源"], []
    registered = set()
    for m in re.finditer(r"^\|\s*`([^`]+)`", doc.read_text(encoding="utf-8"), re.M):
        registered.add(m.group(1).strip().rstrip("/"))
    try:
        # -z 才能拿到未转义的路径：默认输出会把非 ASCII 文件名整条用引号加八进制转义
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True,
                             text=True, encoding="utf-8", errors="replace")
        if out.returncode != 0:
            return [], ["R26 跳过：git ls-files 不可用"]
        tracked = [f for f in out.stdout.split(chr(0)) if f.strip()]
    except OSError:
        return [], ["R26 跳过：找不到 git"]

    IGNORE = {".claude", ".github"}
    actual = set()
    for f in tracked:
        parts = f.split("/")[:-1]
        for i in range(len(parts)):
            d = "/".join(parts[: i + 1])
            if parts[0] in IGNORE:
                break
            actual.add(d)

    def covered(d):
        # 登记 content/stories/ 即覆盖它下面的每一个 <case_id>/；
        # 同时纯粹的父目录（content/ 之于 content/ch1/）也算覆盖——
        # 登记的是「放什么东西的地方」，不是路径上的每一节。
        return any(d == r or d.startswith(r + "/") or r.startswith(d + "/")
                   for r in registered)

    errs = [f"R26 目录 `{d}/` 未在 docs/STRUCTURE.md 登记——先登记再建目录"
            for d in sorted(actual) if not covered(d)]
    # dist/ 与 build/ 是产物目录，登记了但不进 git、本地也可能还没生成——不算过期
    PRODUCED = {"dist", "build"}
    wrns = [f"R26 登记表里的 `{r}/` 在仓库里不存在——表过期了"
            for r in sorted(registered)
            if "." not in r.split("/")[-1] and r not in PRODUCED
            and not (root / r).exists()]
    if not errs and not wrns:
        print(f"INFO : R26 目录登记 {len(actual)} 个实际目录全部已登记 ✓")
    return errs, wrns



def check_doclinks():
    """R27：文档之间的相对链接必须解析得到。

    重组文档最容易把交叉引用改断，而断链没人会当场发现。
    """
    root = pathlib.Path(__file__).resolve().parent.parent
    SKIP = {".git", "dist", "build", "node_modules", "__pycache__", "evidence"}
    bad = []
    n = 0
    for md in root.rglob("*.md"):
        if any(part in SKIP for part in md.relative_to(root).parts):
            continue
        for m in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", md.read_text(encoding="utf-8")):
            target = m.group(1).split("#")[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            n += 1
            if not (md.parent / target).resolve().exists():
                bad.append(f"R27 断链 {md.relative_to(root).as_posix()} -> {target}")
    if not bad:
        print(f"INFO : R27 文档链接 {n} 条全部可解析 ✓")
    return bad



# ---------- 幕的校验（--stories） ----------
BEAT_KINDS = ["cold_open", "evidence", "evidence", "decision", "reveal",
              "contrast", "abstract", "twin"]
BEAT_REQ = {
    "cold_open": ["eyebrow", "title", "lines"],
    "evidence":  ["eyebrow", "title", "panel"],
    "decision":  ["eyebrow", "title", "prompt", "options"],
    "reveal":    ["eyebrow", "title", "lines"],
    "contrast":  ["eyebrow", "title", "columns", "them", "canon", "knowhow"],
    "abstract":  ["eyebrow", "title", "rule", "label", "boundary", "formula"],
    "twin":      ["eyebrow", "title", "panel", "question", "options", "fb"],
}
# 这些数字是叙事里正常出现的年份/序号，不要求绑 fact
NUM_OK = re.compile(r"^(19|20)\d\d$|^[1-9]$|^1[0-2]$")



def norm(s):
    """归一化：空白压平 + 花体标点换直体。

    PDF 抽出来的文本用 U+2010 连字符与弯引号（quarter‐end / Lehman’s），
    键盘敲出来的是直体。逐字比对前不归一，正确的引文也会判成对不上。
    """
    s = re.sub(r"[‐‑‒–—−]", "-", s)
    s = re.sub(r"[‘’‛]", "'", s)
    s = re.sub(r"[“”]", '"', s)
    s = re.sub(r"[   ]", " ", s)
    return re.sub(r"\s+", " ", s)


def sig(tok):
    """数字 → 有效数字串。1,073.1 → 10731；10.73 → 1073；50.0 → 5"""
    d = str(tok).replace(",", "").replace(".", "").lstrip("0")
    return d.rstrip("0") or ("0" if str(tok).strip("0.,") == "" else "")


def sig_match(tok, pool, minlen=3):
    """内容里的数字与已核定事实互为前缀即算有出处（容许单位换算与取整）。"""
    a = sig(tok)
    if len(a) < minlen:
        return False
    return any(a.startswith(b) or b.startswith(a) for b in pool if len(b) >= minlen)


def validate_stories(release=False):
    """S1–S6：幕的结构、出处与数字纪律。

    以前 build.py 只对 content/ch1/site.json 跑校验，三幕（现在的主体验，
    含真人姓名与逐字原档引文）从未过任何内容门禁。
    """
    root = pathlib.Path(__file__).resolve().parent.parent
    facts_p = root / "content" / "ch1" / "facts.json"
    F = json.loads(facts_p.read_text(encoding="utf-8"))
    fact_ids = {f["id"] for f in F["facts"]}
    approved = set(F.get("approved_tokens", {}))
    # 已核定事实里出现过的所有数字串，都算「有出处」
    for f in F["facts"]:
        for tok in re.findall(r"[\d][\d,\.]*", f.get("value", "") + " " + f.get("basis", "")):
            approved.add(tok.strip(".,"))
    # 事实用 $M / $K 登记，文案用「亿 / 万」写——同一个数字两种单位，
    # 字符串相等比不出来。改按**有效数字**比：把逗号、小数点、末尾零去掉，
    # 只要内容里的数字与某条已核定事实的有效数字互为前缀（≥3 位），就算有出处。
    # 这允许换算与合理取整，但编造的数字仍然对不上任何一条。
    approved_sig = {sig(x) for x in approved if sig(x)}
    ev_files = {e["file"] for e in F["evidence_files"]}
    accs = {e["accession"] for e in F["evidence_files"]}

    errors, warns = [], []
    cases = sorted((root / "content" / "stories").glob("*/case.json"))
    if not cases:
        return ["S0 找不到任何 content/stories/*/case.json"], []

    for cp in cases:
        cid = cp.parent.name
        try:
            c = json.loads(cp.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"S0 {cid}: case.json 解析失败 —— {e}")
            continue

        # S1 顶层字段
        for k in ("case_id", "title", "subtitle", "era", "hook", "knowledge_node", "cast", "beats"):
            if not c.get(k):
                errors.append(f"S1 {cid}: 缺顶层字段 {k}")
        if c.get("case_id") != cid:
            errors.append(f"S1 {cid}: case_id「{c.get('case_id')}」与目录名不一致")

        # S2 拍的种类与顺序
        kinds = [b.get("kind") for b in c.get("beats", [])]
        if kinds[:1] != ["cold_open"]:
            errors.append(f"S2 {cid}: 第一拍必须是 cold_open，实际 {kinds[:1]}")
        for need in ("decision", "reveal", "contrast", "abstract", "twin"):
            if need not in kinds:
                errors.append(f"S2 {cid}: 缺 {need} 拍")
        for b in c.get("beats", []):
            for k in BEAT_REQ.get(b.get("kind"), []):
                if not b.get(k):
                    errors.append(f"S2 {cid}/{b.get('id')}({b.get('kind')}): 缺字段 {k}")
            if b.get("kind") == "reveal" and not (b.get("quote") or b.get("record_summary")):
                errors.append(f"S2 {cid}/{b.get('id')}: reveal 必须有逐字 quote 或明确标注的 record_summary")

        # S3 决策拍的三种 verdict 必须齐
        for b in c.get("beats", []):
            if b.get("kind") == "decision":
                vs = {o.get("verdict") for o in b.get("options", [])}
                if vs != {"prudent", "risky", "hasty"}:
                    errors.append(f"S3 {cid}: decision 的 verdict 必须恰好是 prudent/risky/hasty，实际 {sorted(vs)}")
            if b.get("kind") == "twin":
                oks = [o for o in b.get("options", []) if o.get("ok")]
                if len(oks) != 1:
                    errors.append(f"S3 {cid}: twin 必须恰好一个正确选项，实际 {len(oks)} 个")

        # S4 引文必须带出处与行号
        for b in c.get("beats", []):
            q = b.get("quote")
            if q and not (q.get("src") and q.get("line")):
                errors.append(f"S4 {cid}/{b.get('id')}: quote 缺 src 或 line")

        # S7 引文锚定：引文必须能在归档原档的引用行附近找到。
        # 没有这一条，把 quote.text 换成一句编造的话，其余所有检查都会放行——
        # 而这个产品的核心承诺就是「他说的每一句都逐字来自原档」。
        #
        # 中文引文是英文原档的翻译，字符串比不了，所以比**数字**：
        # 引文里出现的每个数字，都必须出现在被引的那几行里。
        # 英文引文则直接比文本本身。
        acc2file = {e["accession"]: e["file"] for e in F["evidence_files"]}

        def window(acc, src_line, where):
            """(accession, line) → 原档里的一段文本。取不到就返回 (None, 原因)。"""
            fpath = acc2file.get(acc)
            if not fpath:
                return None, f"accession「{acc}」没有归档原档"
            ep = root / fpath
            if not ep.exists():
                errors.append(f"S7 {cid}/{where}: 原档缺失 {fpath}")
                return None, None
            if ep.suffix.lower() == ".pdf":
                # PDF 原档按页锚（line 写 "p.16"）。以前 S7 对 PDF 只能报一句
                # 「没有 L 行号」然后放行——雷曼幕最核心的两句引文（Repo 105 的规模、
                # 从未披露）就一直挂在这个豁免里，没有任何东西核对过。
                pgs = [int(x) for x in re.findall(r"p\.?\s*(\d+)", str(src_line or ""))]
                if not pgs:
                    return None, f"line「{src_line}」里没有 p.页码（PDF 原档按页锚）"
                try:
                    from pypdf import PdfReader
                except ImportError:
                    errors.append(f"S7 {cid}/{where}: 引文锚在 PDF 上但装不到 pypdf —— "
                                  "缺依赖时这条检查会静默跳过，那正是它要挡的事。"
                                  "装 pypdf，或把锚改到文本原档上")
                    return None, None
                rd = PdfReader(str(ep))
                out = []
                for pg in range(min(pgs) - 1, max(pgs) + 1):   # 取到相邻页，跨页断句也能命中
                    if 1 <= pg <= len(rd.pages):
                        out.append(rd.pages[pg - 1].extract_text() or "")
                return norm(chr(10).join(out)), None
            nums = re.findall(r"L(\d+)", str(src_line or ""))
            if not nums:
                return None, f"line「{src_line}」里没有 L 行号"
            EL = ep.read_text(encoding="utf-8", errors="replace").splitlines()
            lo, hi = int(nums[0]), int(nums[-1])
            # 原档有 .txt 也有 .html。HTML 报表里一个单元格就是一行，±6 行只看得见
            # 光秃秃的「$ 7,286」——科目名和列头都在几十行以外。按**可见字数**扩窗，
            # 一直扩到看得见约 800 字正文为止，行数窗口对 HTML 才有意义。
            pad, raw, vis = 6, "", ""
            while pad <= 150:
                raw = chr(10).join(EL[max(0, lo - pad):min(len(EL), hi + pad)])
                # HTML 实体要解码。原先只换了 &nbsp;，而 SEC 的申报文件大量使用**数字实体**
                # （&#160; &#147; &#151;）。不解码的话实体会以字面形式留在窗口里，
                # 逐字引文永远对不上——等于这一类原档的 S7 静默失效。
                vis = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
                if len(vis) >= 800:
                    break
                pad += 12
            # 「2007 年 11 月 30 日」对上原档的「November 30, 2007」：月份一边是数字一边是词。
            # 把英文月名翻成数字补进窗口，日期就能和别的数字走同一条规则——
            # 而不是把日期整类豁免掉（豁免等于「把日期换掉也没人发现」，
            # 而这条引文的全部意思就是哪个数字属于哪一天）。
            months = vis
            for i, mon in enumerate(MONTHS, 1):
                months = re.sub(mon + r"[a-z]*\.?", f" {i} ", months, flags=re.I)
            # 三份都留：raw 供文本原档逐字比，vis 供 HTML 逐字比，months 供日期比。
            # 只留 months 的话，orig 里写着 November 就永远对不上。
            return chr(10).join((raw, vis, months)), None

        def check_quote(q, where):
            """S7：引文必须能在归档原档的引用行附近找到。

            锚有两种写法：
              - 绑 fact（用这条事实的 accession + quote.line）
              - 自带 anchors:[{accession,line}]，可以多条

            为什么要 anchors：审问屏的 testimony 原本只有散文式的 src
            （「雷曼 2007 年 10-K 第 86 页」）加 line，acc2file 永远查不到，
            S7 于是只报一句 WARN 就放行——**「逐字原档引文」这一整类内容
            从来没有任何东西核对过**，而它是这个产品最硬的承诺。
            雷曼那条横跨 10-K 与两份 10-Q，所以 anchors 是列表而不是单值。
            """
            explicit = q.get("anchors")
            anchors = explicit or [{"accession": next(
                (x.get("accession") for x in F["facts"] if x["id"] == q.get("fact")), None
            ) if q.get("fact") else None, "line": q.get("line")}]
            wins, why = [], []
            for a in anchors:
                w, reason = window(a.get("accession"), a.get("line"), where)
                if w is None:
                    if reason:
                        why.append(reason)
                else:
                    wins.append(w)
            if explicit and why:
                errors.append(f"S7 {cid}/{where}: anchors 里有锚点落不到原档 —— "
                              + "；".join(why) + "。显式写了锚就必须条条都能核对")
                return
            if not wins:
                warns.append(f"S7 {cid}/{where}: 无法核对逐字性 —— "
                             + "；".join(why or ["原档缺失"]))
                return
            src_line = " / ".join(str(a.get("line")) for a in anchors)
            txt = re.sub(r"<[^>]+>", "", q.get("text") or q.get("quote") or "")
            ascii_ratio = sum(c.isascii() for c in txt) / max(1, len(txt))
            if ascii_ratio > 0.85:
                # 文案习惯用「」把整句英文包起来；引号不是原文的一部分，比对前剥掉
                probe = norm(txt).strip().strip('「」“”"' + chr(39)).strip()[:60]
                # PDF 抽文本会在词中间插空格（实测 2007 年信把 said 抽成「sa id」）。
                # 逐字性看的是字符顺序，不是空格：先按原样比，比不上再去掉全部空白比一次。
                # 改一个词仍然对不上，所以这不是放水。
                squash = lambda x: re.sub(r"\s", "", x)
                if not any(probe in norm(w) or squash(probe) in squash(norm(w)) for w in wins):
                    errors.append(f"S7 {cid}/{where}: 英文引文在原档 {src_line} 附近找不到 —— "
                                  f"「{probe[:50]}」。逐字引文不许改写")
            else:
                # S7c 译文引文必须带 orig（被译的那句英文原文）。
                #
                # 只比数字挡不住改写。实测：把 sunbeam 那句「在向客户发货时确认收入」
                # 改成「在收到货款时」——一个数字都没动，意思正好相反，S7 原样放行。
                # 而这句正是整个第一章要教的东西（权责发生制 vs 收付实现制）。
                #
                # 机器能核的是「orig 逐字在原档里」；译得准不准是人的活，
                # 在签字清单 G1 里。分工不含糊，两边都不放空。
                orig = norm(re.sub(r"<[^>]+>", "", q.get("orig") or ""))
                if not orig:
                    errors.append(f"S7c {cid}/{where}: 译文引文缺 orig（被译的英文原文片段）"
                                  " —— 只比数字的话，把引文改写成相反的意思也能过")
                elif not any(orig[:120] in norm(w) for w in wins):
                    errors.append(f"S7c {cid}/{where}: orig 在原档 {src_line} 附近逐字找不到 —— "
                                  f"「{orig[:60]}」")
                # 译文比数字。字面数字串优先；对不上再按有效数字比一次——
                # 原档记 $7,286 million 而文案写「72.86 亿美元」，字符串永远不相等，
                # 但 sig 都是 7286。允许换算与取整，编造的数字仍然对不上。
                # 日期整体核对。「2008 年 2 月 29 日」里的 2 是一位数，会被下面
                # 「有效数字 ≥2 位」的过滤扔掉——实测把 2 月改成 3 月，S7 原样放行，
                # 而这条证词的全部意思就是哪个数字属于哪一天。
                for y, mo, dd in re.findall(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", txt):
                    pats = (rf"(?<!\d){int(mo)}\D{{0,4}}{int(dd)}\D{{0,8}}{y}(?!\d)",      # Feb 29, 2008（月名已归一成数字）
                            rf"(?<!\d){y}\D{{0,4}}0?{int(mo)}\D{{0,4}}0?{int(dd)}(?!\d)")  # 2008-02-29
                    if not any(re.search(pt, norm(w)) for w in wins for pt in pats):
                        errors.append(f"S7 {cid}/{where}: 日期「{y} 年 {mo} 月 {dd} 日」"
                                      f"在原档 {src_line} 附近对不上")
                qn = [t for t in re.findall(r"[\d][\d,]*(?:\.\d+)?", txt) if len(sig(t)) >= 2]
                pool = {sig(t) for w in wins for t in re.findall(r"[\d][\d,]*(?:\.\d+)?", w)}
                pool.discard("")
                # 窗口只有几行原档，有效数字放到两位就够：「5,900 万」对「$59 million」，
                # sig 都是 59。三位下限是给全库账本（S6）用的，那边池子大、要防误配；
                # 这里池子是引用行附近那一小段，两位不会撞。
                miss = [t for t in qn
                        if not any(t.replace(",", "") in norm(w).replace(",", "") for w in wins)
                        and not sig_match(t, pool, minlen=2)]
                if miss:
                    errors.append(f"S7 {cid}/{where}: 译文引文里这些数字在原档 {src_line} 附近找不到 —— "
                                  + "、".join(miss[:6]) + "。译文可以，编造不行")

        for b in c.get("beats", []):
            if b.get("quote"): check_quote(b["quote"], f"{b.get('id')}/quote")
        # S7b 审问屏的每条 testimony 都必须可核对。
        # 屏上它长得就是「他写过的话」，逐字引自原档；一条没有锚的 testimony
        # 等于一句谁都没核对过的引文，而它挂着原档的名义。
        for i, t in enumerate((c.get("interrogation") or {}).get("testimony", [])):
            if not (t.get("anchors") or t.get("fact")):
                errors.append(f"S7b {cid}/testimony[{i}]: 既没有 anchors 也没有绑 fact —— "
                              "屏上它是「他写过的话」，必须能锚回归档原档的行")
                continue
            check_quote(t, f"testimony[{i}]")
            # press（追问后他的回答）与 breaks（被证据戳中后的改口）同样是屏上的逐字引文，
            # 此前从没被核过。没有自己的锚就继承父陈述的 accession，用自己的 line。
            parent_acc = (t.get("anchors") or [{}])[0].get("accession") or next(
                (x.get("accession") for x in F["facts"] if x["id"] == t.get("fact")), None)
            subs = ([("press", t["press"])] if t.get("press") else []) +                    [(f"breaks[{k}]", b) for k, b in enumerate(t.get("breaks") or [])]
            for tag, sub in subs:
                if not sub.get("text"):
                    continue
                q = dict(sub)
                if not (q.get("anchors") or q.get("fact")):
                    if not parent_acc:
                        errors.append(f"S7b {cid}/testimony[{i}].{tag}: 没有锚，父陈述也给不出 accession")
                        continue
                    q["anchors"] = [{"accession": parent_acc, "line": sub.get("line")}]
                check_quote(q, f"testimony[{i}].{tag}")

        # S5 每个 fact 引用都要在 facts.json 里存在
        for m in re.finditer(r'"fact"\s*:\s*"([^"]+)"', cp.read_text(encoding="utf-8")):
            if m.group(1) not in fact_ids:
                errors.append(f"S5 {cid}: 引用了不存在的 fact「{m.group(1)}」")

        # S6 数字纪律：正文里出现的数字必须能在已核定事实里找到
        # 这是幕层的 R12。少了它，一幕里可以出现任何编造的数字而无人察觉。
        txt = []
        def walk(o, in_quote=False):
            if isinstance(o, str):
                if not in_quote: txt.append(o)
            elif isinstance(o, dict):
                # **逐字引文豁免**：quote / testimony 里的数字由引文自己的 src + line 背书，
                # 那才是它们的出处。再要求它们单独绑一条 fact，等于要求把原档拆成事实条目
                # 才准引用——反而会逼人去改写原文。改写原文是这个产品最不能容忍的事。
                q = o.get("src") and (o.get("line") or o.get("accession"))
                for k, v in o.items():
                    # x_prov 是签字记录，不是正文。reviewed_hash 是 16 位十六进制，
                    # 里面必然夹着数字串——签完字 S6 就会把它当成「没有出处的真实数字」
                    # 而报错。第一次给幕签字时当场撞上了。
                    if k in ("line", "accession", "_note", "note", "x_prov"): continue
                    # orig 一并豁免：它就是原档里的那句英文，而 S7c 已经拿它
                    # 去归档原档里逐字核对过——比「这个数字在账本里」更硬的背书。
                    walk(v, in_quote or (bool(q) and k in ("text", "quote", "orig")))
            elif isinstance(o, list):
                for v in o: walk(v, in_quote)
        walk(c)
        blob = " ".join(txt)
        # 这些不是「教学数字」，是出处标识，不该要求绑 fact：
        #   申报号 0000950170-98-000413 / 日期 2001-05-15 / 行号 L1192–L1198
        #   条例号 AAER 1393、Rule 12b-2、10-K/A、Repo 105、第 18 页
        for pat in (r"\d{10}-\d\d-\d{6}", r"\d{4}-\d\d-\d\d", r"\d{4}-\d\d(?!\d)", r"L\d+(?:[–-]L?\d+)?", r"p\.\d+",
                    r"[a-z]{2}-[a-z\-]+-\d+",           # fact id：nk-rd-20 / md-ni-19
                    r"\d+\s*月\s*\d+\s*日", r"\d+\s*年",  # 中文日期
                    r"第\s*[一二三四五六七八九十\d]+\s*[季幕拍]",
                    r"AAER\s*\d+", r"LR-\d+", r"10-[KQ](?:405|/A)?", r"8-K", r"S-1",
                    r"Repo\s*105", r"Rule\s*[\d\w.-]+", r"第\s*\d+\s*[页章节]",
                    r"§\s*[\d.]+", r"\bSFAS\s*\d+", r"\bASC\s*[\d-]+"):
            blob = re.sub(pat, " ", blob)
        bad = []
        for tok in re.findall(r"(?<![\w.])[\d][\d,]*(?:\.\d+)?", blob):
            t = tok.strip(".,")
            if not t or NUM_OK.match(t) or t in approved:
                continue
            if sig_match(t, approved_sig):
                continue
            bad.append(t)
        if bad:
            errors.append(f"S6 {cid}: 这些数字在 facts.json 里找不到出处 —— "
                          + "、".join(sorted(set(bad))[:14])
                          + "。真实数字必须先入 facts.json 并绑 accession + 行号")

        # S9 剧透闸：reveal 之前不许出现结局。
        #
        # 一幕的全部教学价值在于「用当年拿得到的信息做判断」。任何一句
        # 「后来 SEC 认定…」提前出现，用户就不是在判断，是在背答案——
        # 而屏上仍然会问他「你现在怎么办」，判分照常给。
        # 这也是签字清单 G1 第 5 条（「真实公司的表述是当年的」）里
        # 机器能查的那一半。
        #
        # 只查叙事字段：decision 的选项标签里出现「认定舞弊」是**用户的选项**
        # （一个仓促结论），不是剧透，所以 options 子树整体跳过。
        SPOIL = re.compile(r"破产|退市|被起诉|重述|认定|舞弊|欺诈|后来|最终|事后|真相|判刑")
        kinds = [b.get("kind") for b in c.get("beats", [])]
        if "reveal" in kinds:
            ri = kinds.index("reveal")

            def narrative(o, out):
                if isinstance(o, dict):
                    for k, v2 in o.items():
                        if k in ("options", "kind", "id", "src", "line", "fact",
                                 "accession", "anchors", "orig", "_note"):
                            continue
                        narrative(v2, out)
                elif isinstance(o, list):
                    for v2 in o:
                        narrative(v2, out)
                elif isinstance(o, str):
                    out.append(o)

            for bi, b in enumerate(c.get("beats", [])[:ri]):
                strs = []
                narrative(b, strs)
                for t in strs:
                    m = SPOIL.search(t)
                    if m:
                        errors.append(
                            f"S9 {cid}/beats[{bi}]({b.get('kind')}): reveal 之前出现结局词"
                            f"「{m.group(0)}」——…{t[max(0, m.start() - 25):m.end() + 25]}…"
                            "。用户要用当年的信息判断，提前告诉他结局，这一幕就只剩背答案")

        # S8 断头路：屏上承诺的交互必须真的存在。
        #
        # 消融实验查出来的：nikola 的判断拍写着 ask_enabled: true，提示里说
        # 「你可以先问问这份文件」，但那一幕没有 interrogation，
        # 前端条件是 `b.ask_enabled && STORY.interrogation`，按钮永远不渲染。
        # 屏幕让用户做一件界面不提供的事——项目明令杜绝的断头路，
        # 而在此之前没有任何东西会喊一声。
        for bi, b in enumerate(c.get("beats") or []):
            if b.get("ask_enabled") and not c.get("interrogation"):
                errors.append(
                    f"S8 {cid}/beats[{bi}]: ask_enabled 为真但这一幕没有 interrogation ——"
                    "前端条件是 `ask_enabled && STORY.interrogation`，按钮不会渲染，"
                    "屏上却承诺了可以追问。要么补 interrogation，要么去掉这个承诺")

        # 签字（同 site.json 的 --release 纪律）
        pv = c.get("x_prov") or {}
        if not pv.get("reviewed_by"):
            (errors if release else warns).append(
                f"{cid}: 幕没有定版记录（x_prov.reviewed_by 为空）"
                + ("——--release 阻断" if release else "——定版前必须补"))
        # 内容改了签字必须失效。这条一度只在节点侧（R23）有，幕这边只查了
        # reviewed_by 非空——结果是给幕签完字之后正文随便改，签字永远有效，
        # 而「签字绑内容指纹」正是这套机制唯一的意义所在。
        elif pv.get("reviewed_hash"):
            h = case_hash(c)
            if h != pv["reviewed_hash"]:
                errors.append(f"{cid}: 幕的审核已过期——内容 hash 与 x_prov.reviewed_hash "
                              f"不符，改动后必须重审（现 {h}，签字时 {pv['reviewed_hash']}）")
        else:
            errors.append(f"{cid}: 幕有定版来源却没有 reviewed_hash —— "
                          "没有指纹的签字无法判断是否过期，等于没签")

    # 原档登记自检
    for e in F["evidence_files"]:
        if not (root / e["file"]).exists():
            errors.append(f"S0 facts.json 登记的原档不存在：{e['file']}")
    if not errors:
        print(f"INFO : 幕校验 {len(cases)} 个 case.json 全部通过"
              f"（{len(fact_ids)} 条已核定事实 / {len(ev_files)} 份原档 / {len(accs)} 个 accession）")
    return errors, warns


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
        # R31 正典与本站口径必须分栏。
        #
        # 这条是从签字清单 G1 的第 2 项（「阈值类主张标了本站口径，没有伪装成正典」）
        # 反推出来的：那一项当时**在数据里没有任何表示**。翻下来发现六个节点的
        # canon.formal 里混着我们自己的话（「本站教学口径…」「本节点只教…」），
        # 而屏上那张卡的标题是「正典」，正文一整段读起来都像出处说的。
        #
        # 拆成两栏之后，机器能查的部分就变成确定的：formal 里不许出现我们的口吻。
        for w in ("本站", "本节点", "我们", "⚠️"):
            if w in formal:
                errors.append(f"R31 {nid}: canon.formal 里出现「{w}」——这是我们的口吻，"
                              "不是出处的话。移到 canon.house（屏上单列「本站口径」一栏）")
        h = c.get("house")
        if h is not None and not (isinstance(h, str) and h.strip()):
            errors.append(f"R31 {nid}: canon.house 存在但为空——空的口径栏会在卡上留一个空标题")
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
            errors.append(
                f"{loc}: x_identity 为空（三套语气语料各自的思想出处，随内容归档）")
        # 早先这条规则的说明写着「被问身份时逐字输出」。**没有任何地方输出它。**
        # AI 披露实际由页脚常驻那句话承担（「通俗解释与教练点评由 AI 起草、经人工核对；
        # 判分由页面内置规则完成」）。规则说明与事实不符比规则缺失更危险：
        # 它让人以为披露这件事已经由某处代码保证了。
        # 现在 x_identity 的定位改为归档用（build 时剥离，不进产物），说明照实写。
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
    #
    # 这条挡的是作者留下的**占位符**（「数字待核」「出处待补」）。
    # 但「待核」也是正常中文的词头：「待核查的疑点」「待核实的说法」都是好措辞，
    # 而这一关教的就是「疑点要去核查」，绕开这个词等于让门禁改坏文案。
    # 撞过两次之后改成：后面紧跟 查/实/对/算 的算正常动词短语，不算占位符。
    blob = json.dumps(data, ensure_ascii=False)
    for mk in TODO_MARKERS:
        hits = [m for m in re.finditer(re.escape(mk), blob)
                if not (mk == "待核" and blob[m.end():m.end() + 1] in "查实对算")]
        if hits:
            errors.append(f"内容中出现待办标记「{mk}」——未核定内容不得进入内容源")

    # R22 「无法判断」为正确答案的占比锚（目标 20–30%，见 知识可靠性与LLM边界.md §6）
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

    # ---- R26 目录登记 ----
    # docs/STRUCTURE.md 的登记表是目录的唯一真源；这一条是它的执行者。
    errors_dir, warns_dir = check_dirs()
    errors += errors_dir
    warns += warns_dir
    errors += check_doclinks()

    print(f"nodes={len(nodes)} edges={len(edges)}(hard={len(hard)}) roots={sorted(roots)}")
    for w in warns:
        print("WARN :", w)
    for e in errors:
        print("ERROR:", e)
    print("RESULT:", "FAIL" if errors else "PASS")
    return 1 if errors else 0


def selftest():
    """变异测试：把内容逐条改坏，看对应规则会不会红。

    这个校验器有 31 条规则，此前**一条也没有可重跑的证明**。
    本仓最贵的教训是「规则在那儿、是绿的、但它什么也没查」——
    check_coach 与 check_style 早就有 --selftest，最大的那个门禁反而没有。
    这里覆盖本轮新加的五条与两条最吃重的旧规则；每加新规则就往下面加一行。
    """
    import subprocess
    SITE_P = ROOT / "content" / "ch1" / "site.json"
    FACTS_P = ROOT / "content" / "ch1" / "facts.json"
    CASE_P = ROOT / "content" / "stories" / "sunbeam-1998" / "case.json"
    orig = {f: f.read_text(encoding="utf-8") for f in (SITE_P, FACTS_P, CASE_P)}

    def run(stories):
        args = ["--stories"] if stories else [str(SITE_P)]
        return subprocess.run([sys.executable, str(pathlib.Path(__file__))] + args,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout

    def node(d, nid):
        return next(n for n in d["nodes"] if n["id"] == nid)

    def m_r12(d):
        node(d, "rf1")["desc"] += "（Sunbeam 当年的收入是 4,321.5 百万美元）"

    def m_r31(d):
        node(d, "rf2")["canon"]["formal"] += "本站教学口径：只看两年。"

    def m_r28(d):
        d["evidence_files"] = [e for e in d["evidence_files"]
                               if e["accession"] != "AAER-1393"]

    def m_s6(d):
        d["beats"][1]["title"] = "应收账款一年涨了 7,777 万"

    def m_s7c(d):
        d["interrogation"]["testimony"][2]["orig"] =             "The Company recognizes revenues at the time of payment from customers."

    def m_s7b(d):
        d["interrogation"]["testimony"][0].pop("anchors")

    def m_s9(d):
        d["beats"][1]["eyebrow"] = "后来 SEC 认定这一年有舞弊"

    CASES = [
        ("R12", "往真实公司语境里塞一个没入账本的数字", SITE_P, m_r12, False),
        ("R31", "把本站口径塞回 canon.formal", SITE_P, m_r31, False),
        ("R28", "删掉一份原档的归档登记", FACTS_P, m_r28, False),
        ("S6", "往幕的正文里塞一个编造的数字", CASE_P, m_s6, True),
        ("S7c", "把译文引文的英文原文改成原档里没有的一句", CASE_P, m_s7c, True),
        ("S7b", "拿掉一条证词的行锚", CASE_P, m_s7b, True),
        ("S9", "在 reveal 之前写出结局", CASE_P, m_s9, True),
    ]
    bad = 0
    try:
        for code, desc, f, mut, stories in CASES:
            d = json.loads(orig[f])
            mut(d)
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            hit = f"ERROR: {code}" in run(stories)
            bad += not hit
            print("  " + ("✓ " if hit else "✗ ") + f"{code} {desc} → "
                  + ("规则正确报错" if hit else "改坏了却没报错，这条规则是摆设"))
            f.write_text(orig[f], encoding="utf-8")
    finally:
        for f, t in orig.items():
            f.write_text(t, encoding="utf-8")
    print("SELFTEST:", "FAIL（门禁自身不可信）" if bad else f"PASS（{len(CASES)} 条）")
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    argv = sys.argv[1:]
    if "--selftest" in argv:
        sys.exit(selftest())
    release = "--release" in argv
    if "--stories" in argv:
        errs, wrns = validate_stories(release)
        for w in wrns:
            print("WARN :", w)
        for e in errs:
            print("ERROR:", e)
        print("STORIES:", "FAIL" if errs else "PASS")
        sys.exit(1 if errs else 0)
    args = [a for a in argv if a not in ("--release", "--stories")]
    default = pathlib.Path(__file__).resolve().parent.parent / "content" / "ch1" / "site.json"
    sys.exit(validate(args[0] if args else default, release=release))
