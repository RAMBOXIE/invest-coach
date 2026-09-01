#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教练闭环门禁 —— 检查这东西到底是「教练」还是「会观察你的课程」。

其它门禁查的是**内容对不对**（出处、数字、无障碍、体积）。
这一道查的是**产品成不成立**：一套内容再准确，如果诊断出的毛病不改变
用户下一步做什么，它就只是一门带仪表盘的课，不是教练。

七条判据（C1–C7）。每一条都对着源码查真值，不查形状——
`--selftest` 会逐条把源码改坏，验证对应的规则真的会红。

    python tools/check_coach.py
    python tools/check_coach.py --selftest    # 变异测试：每条规则自己会不会失灵
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TPL = ROOT / "src" / "template.html"
PARTS = ROOT / "src" / "parts"
SITE = ROOT / "content" / "ch1" / "site.json"

ERRORS, WARNS, INFOS = [], [], []


def err(c, m):
    ERRORS.append(f"{c} {m}")


def warn(c, m):
    WARNS.append(f"{c} {m}")


def ok(c, m):
    INFOS.append(f"{c} {m}")


def sources():
    s = TPL.read_text(encoding="utf-8")
    for f in sorted(PARTS.glob("*.js")):
        s += "\n" + f.read_text(encoding="utf-8")
    return s


def body_of(src, name):
    """抓一个函数的完整函数体（按大括号配平，不靠缩进）。"""
    m = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", src)
    if not m:
        m = re.search(r"(?:window\.)?" + re.escape(name) + r"\s*=\s*function\s*\([^)]*\)\s*\{", src)
    if not m:
        return None
    i, depth = m.end(), 1
    while i < len(src) and depth:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
        i += 1
    return src[m.end():i - 1]


def quizzes(site):
    """站点里所有的题：屏内题、混淆对复训题、闭卷锚题。"""
    out = []
    for n in site["nodes"]:
        for sc in n.get("screens", []):
            if sc.get("quiz"):
                out.append((n["id"], "screen", sc["quiz"]))
        for a in n.get("x_anchors", []):
            if isinstance(a, dict) and a.get("quiz"):
                out.append((n["id"], "anchor", a["quiz"]))
    for it in site.get("x_review_bank", []):
        if it.get("quiz"):
            out.append((it.get("pair_id", "?"), "review", it["quiz"]))
    return out


# ────────────────────────────────────────────────────────────────────
def c1_diagnose(src):
    """C1 诊断采集：判断**习惯**（不是知识点对错）确实被记下来了。"""
    b = body_of(src, "updateProfile")
    if not b:
        return err("C1", "找不到 updateProfile —— 没有任何地方在记录用户的判断习惯")
    # 查数据流，不查词频：三个计数器必须真的**被写入**。
    # 早先这里 grep "opt.verdict" 就算过——但那个词在条件判断里也出现，
    # 把写入语句删掉规则照样绿。变异测试当场抓到了。
    need = {"判断倾向计数器": r"p\[opt\.verdict\]\s*=",
            "过度自信计数器": r"p\.over\+\+|p\.over\s*=",
            "样本数": r"p\.n\+\+"}
    miss = [k for k, pat in need.items() if not re.search(pat, b)]
    if miss:
        return err("C1", f"updateProfile 没有采集：{'/'.join(miss)}")
    if not re.search(r"wrong\+\+", src):
        return err("C1", "没有任何地方累加混淆对的错误次数")
    ok("C1", "诊断采集 判断习惯（verdict/over/n）+ 混淆对错次 均已入库 ✓")


def c2_prescribe(src):
    """C2 诊断→处方：**这一条是教练和课程的分水岭。**

    诊断信号必须能改变「现在做这个」是什么。只把毛病显示出来不算——
    仪表盘也能显示。判据：存在 prescribe()，在 plan() 里被调用，
    且它的产物真的进了队列 q（而不是只挂在返回值上供抽屉展示）。
    """
    pb = body_of(src, "prescribe")
    if not pb:
        return err("C2", "没有 prescribe() —— 诊断到的毛病不改变用户下一步做什么，"
                         "这是「带仪表盘的课程」而不是教练")
    if not re.search(r"profile\(\)|S\.profile", pb):
        return err("C2", "prescribe() 没有读判断习惯画像，它不是在开处方")
    planb = body_of(src, "plan")
    if not planb:
        return err("C2", "找不到 plan()")
    if not re.search(r"\bprescribe\s*\(", planb):
        return err("C2", "plan() 没有调用 prescribe() —— 处方没有接进调度")
    m = re.search(r"const\s+(\w+)\s*=\s*prescribe\s*\(", planb)
    if not m:
        return err("C2", "prescribe() 的返回值没有被接住")
    var = m.group(1)
    push = re.search(r"q\.push\s*\(\s*" + re.escape(var) + r"\b", planb)
    if not push:
        return err("C2", f"prescribe() 的产物 {var} 没有进队列 q —— 诊断仍然只是展示")
    # 处方必须排在固定课程项之前，否则它永远不可能成为队首
    for other in re.finditer(r"q\.push\s*\(\s*\{", planb):
        if other.start() < push.start():
            return err("C2", "处方被排在了固定课程项之后 —— 那它永远不会是队首")
    if not re.search(r"\breason\b", pb):
        return err("C2", "处方没有携带理由字段 —— 教练开处方必须说明为什么是这一件")
    ok("C2", "诊断→处方 prescribe() 读画像、进队列、排在课程项之前、带理由 ✓")


def c3_objective(src):
    """C3 判决客观（ADR 0001）：判对错的路径里不许有 LLM。"""
    hits = []
    for fn in ("recordFirst", "drawQuiz", "drawAnchor", "drawReview"):
        b = body_of(src, fn)
        if b and re.search(r"ask-coach|/api/v1/ask", b):
            hits.append(fn)
    if hits:
        return err("C3", f"判分路径里出现了 LLM 调用：{'/'.join(hits)}（违反 ADR 0001）")
    n_lit = len(re.findall(r"\blit\.add\s*\(", src))
    if n_lit != 1:
        return err("C3", f"lit.add 出现 {n_lit} 次 —— 点亮入口必须唯一，否则绕得过锚题")
    ok("C3", "判决客观 判分不经 LLM；点亮入口唯一 ✓")


def c4_attribution(src, site):
    """C4 归因反馈：答完必须解释为什么，不能只判对错。

    **这条规则刻意只查它真查得动的部分。** 「反馈有没有回应错误选项」是语义判断：
    试过两版机器判据都不成立——查纠错词（不是/而非/错在）能被一句夸奖随手绕过；
    查字符重合度则连明明点名了「应付账款」「预收款」的反馈都判不出来，
    因为中文里回应一个选项不需要复述它的字面。

    所以机器在这里只保证三件**能验的事**：反馈存在、篇幅撑得住选项数、
    没有跨题复用的套话。**「这条反馈是否真的解释了错的那个为什么错」交给 G2 人工签字**——
    见 tools/sign.py。假装机器能判它，比承认判不了更危险。
    """
    qs = quizzes(site)
    if not qs:
        return err("C4", "站点里一道题都没有")
    nofb = [f"{nid}/{q.get('x_id', '?')}" for nid, _, q in qs if not (q.get("fb") or "").strip()]
    if nofb:
        return err("C4", f"{len(nofb)} 道题没有反馈：{', '.join(nofb[:4])}")
    # 篇幅：一句「对。」撑不起三个选项的归因
    thin = [f"{nid}/{q.get('x_id', '?')}" for nid, _, q in qs
            if len(q.get("fb", "")) < 12 * max(1, len(q.get("opts", [])))]
    if thin:
        return err("C4", f"{len(thin)} 道题的反馈过短、不足以解释各选项：{', '.join(thin[:6])}")
    # 套话：不同的题共用同一句反馈，说明它没在解释这道题
    seen = {}
    for nid, _, q in qs:
        seen.setdefault(q.get("fb", ""), []).append(f"{nid}/{q.get('x_id', '?')}")
    dup = {k: v for k, v in seen.items() if len(v) > 1}
    if dup:
        first = list(dup.values())[0]
        return err("C4", f"{len(dup)} 句反馈被多道题复用（套话）：{', '.join(first[:4])}")
    ok("C4", f"归因反馈 {len(qs)} 道题：反馈齐全、篇幅相称、无跨题套话 ✓"
             "（是否真的回应了错误选项 → G2 人工）")


def c5_transfer(src, site):
    """C5 迁移证明：点亮必须靠闭卷锚题——换公司、不给提示。"""
    m = re.search(r"\blit\.add\s*\(", src)
    if not m:
        return err("C5", "找不到点亮点")
    ctx = src[max(0, m.start() - 900):m.start()]
    if "anchor" not in ctx.lower():
        return err("C5", "唯一的点亮点不在锚题路径里 —— 看完材料就能点亮，没有迁移证明")
    # 锚题渲染函数是 an()。早先这里写的是 drawAnchor —— 函数不存在，
    # body_of 返回 None，整条检查**静默跳过**，规则形同虚设。变异测试抓到了。
    ab = body_of(src, "an")
    if ab is None:
        return err("C5", "找不到锚题渲染函数 an() —— C5 无法验证，视为不通过")
    # 查机制不查字面：an() 正文里本来就写着「也不给提示」这句话给用户看。
    if re.search(r"S\.hints\+\+|q\.hints|data-h(?:int)?=", ab):
        return err("C5", "锚题里接了提示机制 —— 闭卷就不该给提示")
    deep = [n for n in site["nodes"] if n.get("x_anchors")]
    bad = [n["id"] for n in deep if len(n.get("x_anchors", [])) < 2]
    if bad:
        return err("C5", f"锚题池不足 2 道（重来一次就是同一道题）：{', '.join(bad)}")
    ok("C5", f"迁移证明 点亮唯一入口是闭卷锚题；{len(deep)} 个深层节点锚题池 ≥2 ✓")


def c9_no_position_tell(src, site):
    """C9 答案位置不能泄题 —— 这条规则是一个真实漏洞的形状。

    C5 只验了「点亮的唯一入口是闭卷锚题」，**没验这道锚题只有会做的人能做对**。
    审计发现：52 道题的正确答案全部排在第 1 位，而四个渲染点都按 q.opts 原序输出。
    闭着眼睛点第一项 → 100% 首答正确率、满分 Brier、点亮全部 14 个节点。
    首答正确率、校准分、迁移证明三样测量同时失效，而 C5 当时是绿的。

    形状对了不等于真值对了：一道选择题只有在**位置不携带答案信息**时才是测量。
    """
    qs = quizzes(site)
    if not qs:
        return err("C9", "站点里一道题都没有")
    # 渲染必须打乱，否则内容里的位置就是答案
    for fn in ("shownOpts",):
        if body_of(src, fn) is None:
            return err("C9", f"没有 {fn}() —— 选项按内容原序渲染，位置即答案")
    # shownOpts 自己要读 q.opts 来构造排列，那是正当用法；把它的函数体挖掉再数。
    helper = body_of(src, "shownOpts")
    outside = src.replace(helper, "") if helper else src
    raw = len(re.findall(r"q\.opts\.map\s*\(", outside))
    if raw:
        return err("C9", f"还有 {raw} 处直接渲染 q.opts（未经打乱）—— 那几道题的位置仍然泄题")
    idx = len(re.findall(r"q\.opts\[\s*i\s*\]", outside))
    if idx:
        return err("C9", f"还有 {idx} 处用显示下标直接索引 q.opts —— "
                         "打乱之后这会取到**另一个选项**，判分就错了")
    # 内容侧也报出来：打乱之后位置不再泄题，但答案全压在一个位置说明出题时没注意
    first = sum(1 for _, _, q in qs
                if q.get("opts") and q["opts"][0].get("ok"))
    if first == len(qs):
        warn("C9", f"{len(qs)}/{len(qs)} 道题的正确答案写在第 1 位。"
                   "渲染已打乱所以不泄题，但出题时应当自然分散")
    ok("C9", f"位置不泄题 选项渲染经 shownOpts() 打乱，"
             f"无残留的原序渲染或原序索引 ✓（内容侧首位占比 {first}/{len(qs)}）")


def c6_calibration(src):
    """C6 校准闭环：过度自信必须有**行为后果**，不能只加一个计数器。"""
    if not re.search(r"S\.calib", src):
        return err("C6", "没有采集信心标注")
    if not re.search(r"over\+\+", src):
        return err("C6", "过度自信事件没有被计数")
    pb = body_of(src, "prescribe") or ""
    # 必须在**判断条件**里读它。早先只 grep "over"，而处方里
    # `S.calib.settled=pf.over` 这行清算语句也含这个词，把触发条件删掉规则照样绿。
    if not re.search(r"\.over\s*[><]", pb):
        return err("C6", "过度自信没有成为处方的触发条件 —— "
                         "标了「很有把握」却判错，系统对此毫无动作")
    # 真值：后果必须真的落地。处方本身是纯的（见 C8），所以落地在 commitPrescription()，
    # 而且必须**被点击处理器调用**——只定义不调用等于没有后果。
    cb = body_of(src, "commitPrescription")
    if cb is None:
        return err("C6", "没有 commitPrescription() —— 处方没有落地动作")
    if not re.search(r"due\s*=", cb):
        return err("C6", "commitPrescription 没有改写到期时间 —— 提前召回没有发生")
    if not re.search(r"calib\.settled\s*=", cb):
        return err("C6", "commitPrescription 没有清算过度自信 —— 同一张处方会无限重复")
    callers = [m for m in re.finditer(r"commitPrescription\s*\(", src)]
    if len(callers) < 2:      # 一次是定义处，至少还得有一个调用点
        return err("C6", "commitPrescription 从未被调用 —— 后果只是写在那里")
    ok("C6", "校准闭环 过度自信 → 处方 → 用户开始时提前召回并清算，后果已落地 ✓")


def c8_pure(src):
    """C8 处方必须是纯的 —— 这条规则是一个真实 bug 的形状。

    plan() 每次 render 会被调用多次（队首、预览、抽屉各一次）。第一版 prescribe()
    在函数体里直接清算了 over 并把混淆对挪到到期，结果是：第一次调用产出处方并
    把自己的触发条件销毁，第二次调用条件已不成立，屏幕上出现的是普通复训卡。
    机制全对、门禁全绿、用户永远看不见那张处方。

    所以：prescribe() 内不许有任何状态写入。落地在 commitPrescription()。
    """
    pb = body_of(src, "prescribe")
    if pb is None:
        return err("C8", "找不到 prescribe()")
    writes = []
    if re.search(r"\bsave\s*\(\s*\)", pb):
        writes.append("save()")
    for m in re.finditer(r"(S\.[A-Za-z_.\[\]'\"]+|a\.due|pf\.\w+)\s*=(?!=)", pb):
        writes.append(m.group(0).strip())
    if writes:
        return err("C8", f"prescribe() 里有状态写入 {writes[:3]} —— "
                         "plan() 每次 render 调多次，处方会把自己的触发条件烧掉，"
                         "第二次调用就不成立了，用户看不到这张卡")
    ok("C8", "处方纯度 prescribe() 无状态写入，多次调用结果一致 ✓")


def c7_boundary(src, site):
    """C7 不越界：教判断，不给买卖建议。"""
    text = json.dumps(site, ensure_ascii=False)
    BAD = [(r"建议(买入|卖出|持有|加仓|减仓)", "买卖建议"),
           (r"目标价|预期收益|稳赚|必涨|必跌", "收益承诺"),
           (r"推荐(买|卖|这只|该股)", "荐股")]
    for pat, what in BAD:
        m = re.search(pat, text)
        if m:
            return err("C7", f"出现{what}：…{text[max(0, m.start() - 30):m.end() + 30]}…")
    if "非投资建议" not in src and "非投资建议" not in text:
        return err("C7", "全站没有一处「非投资建议」声明")
    ok("C7", "不越界 无买卖建议/收益承诺；免责声明在位 ✓")


def run():
    src, site = sources(), json.loads(SITE.read_text(encoding="utf-8"))
    c1_diagnose(src)
    c2_prescribe(src)
    c3_objective(src)
    c4_attribution(src, site)
    c5_transfer(src, site)
    c6_calibration(src)
    c7_boundary(src, site)
    c8_pure(src)
    c9_no_position_tell(src, site)
    for i in INFOS:
        print("INFO :", i)
    for w in WARNS:
        print("WARN :", w)
    for e in ERRORS:
        print("ERROR:", e)
    print("RESULT:", "FAIL" if ERRORS else "PASS")
    return 1 if ERRORS else 0


# ────────────────────────────────────────────────────────────────────
# 变异测试：把源码逐条改坏，看对应规则会不会红。
# 仓库教训：门禁只查形状不查真值时会静默放行。每加一条规则就得证明它会失灵。
MUTATIONS = [
    ("C1", "删掉判断倾向计数器的写入", "src", r"p\[opt\.verdict\]\s*=", "p['_x'] ="),
    ("C2", "让处方不进队列", "src", r"q\.push\(rx\)", "void(rx)"),
    ("C3", "多开一个点亮入口", "src", r"lit\.add\(n\.id\)", "lit.add(n.id);lit.add(n.id)"),
    ("C4", "把一道题的反馈缩成一句空话", "site", None, None),
    ("C5", "给锚题接上提示机制", "src", r"function an\(\)\{", "function an(){S.hints++;"),
    ("C6", "删掉过度自信的触发条件", "src", r"pf\.over>\(S\.calib\.settled\|\|0\)", "false"),
    ("C7", "加一句荐股", "site", None, None),
    ("C8", "把落地动作搬回处方里（副作用回归）", "src",
     r"function prescribe\(\)\{", "function prescribe(){S.calib.settled=1;save();"),
    ("C9", "把一处渲染改回按原序输出选项", "src",
     r"body\+=shownOpts\(q\)\.map", "body+=q.opts.map"),
]


def selftest():
    import subprocess
    src_files = [TPL] + sorted(PARTS.glob("*.js"))
    orig = {f: f.read_text(encoding="utf-8") for f in src_files}
    orig_site = SITE.read_text(encoding="utf-8")
    bad = []
    for code, desc, where, pat, rep in MUTATIONS:
        try:
            if where == "src":
                hit = False
                for f in src_files:
                    t = orig[f]
                    if re.search(pat, t):
                        f.write_text(re.sub(pat, rep, t), encoding="utf-8")   # 全部替换：只改第一处等于没改坏
                        hit = True
                        break
                if not hit:
                    bad.append(f"{code} {desc}：变异目标在源码里找不到（规则可能已失效）")
                    continue
            else:
                d = json.loads(orig_site)
                if code == "C4":
                    done = False
                    for n in d["nodes"]:
                        for sc in n.get("screens", []):
                            if sc.get("quiz"):
                                sc["quiz"]["fb"] = "对。"
                                done = True
                                break
                        if done:
                            break
                else:
                    d["about"] = (d.get("about") or "") + "建议买入这只股票。"
                SITE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            r = subprocess.run([sys.executable, str(pathlib.Path(__file__))],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            if f"ERROR: {code}" not in r.stdout:
                bad.append(f"{code} {desc}：改坏了却没报错 —— **这条规则是摆设**")
            else:
                print(f"  ✓ {code} {desc} → 规则正确报错")
        finally:
            for f in src_files:
                f.write_text(orig[f], encoding="utf-8")
            SITE.write_text(orig_site, encoding="utf-8")
    print()
    if bad:
        for b in bad:
            print("ERROR:", b)
        print("RESULT: FAIL（门禁自身不可信）")
        return 1
    print(f"RESULT: PASS（{len(MUTATIONS)} 条规则全部通过变异测试）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(selftest() if "--selftest" in sys.argv else run())
