#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建器: content/ch1/site.json 注入 src/template.html 的 /*__DATA__*/null 占位符
→ dist/index.html（单文件交付物，file:// 双击可用）。内部先跑校验器，FAIL 即拒绝构建。

用法: python tools/build.py [--backend https://your-tunnel.example.com]
--backend 注入轻后端地址常量（模板改造后生效；未提供则前端保持降级态）。
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "ch1" / "site.json"
CONTENT_CH2 = ROOT / "content" / "ch2" / "site.json"
TPL = ROOT / "src" / "template.html"
OUT = ROOT / "dist" / "index.html"
DATA_MARKER = "/*__DATA__*/null"
TOKENS = ROOT / "design" / "tokens.json"
PARTS = ROOT / "src" / "parts"
STORIES = ROOT / "content" / "stories"


def css_vars():
    """design/tokens.json → :root CSS 变量（SPEC_DEV §2：源码不许出现字面色值/字号）。

    v2 纸面翻正：shell 从 night-800 改为 paper-100，stage 保持暗（幕是唯一暗场）。
    随之 text.ui / text.meta 的前景色一并翻到 ink 侧，focus 在纸面改用 amber-700。
    """
    T = json.loads(TOKENS.read_text(encoding="utf-8"))
    P, S = T["primitive"], T["semantic"]
    v = {}

    def emit(prefix, group):
        # 跳过 _note / _retired 这类注记键与嵌套结构
        for k, val in group.items():
            if k.startswith("_") or not isinstance(val, str):
                continue
            v[f"--{prefix}-{k}"] = val

    emit("font", P["font"])
    emit("c", P["color"])
    emit("size", P["size"])
    emit("lh", P["lh"])
    emit("space", P["space"])
    emit("radius", P["radius"])
    emit("dur", P["dur"])
    emit("weight", P["weight"])
    emit("track", P["track"])

    C = P["color"]
    v.update({
        # ---- 表面（v2 翻正）----
        "--surface-shell": C["paper-100"], "--surface-shell-alt": C["paper-200"],
        "--surface-card": C["paper-50"], "--surface-rule": C["paper-200"],
        "--surface-stage": C["night-900"], "--surface-stage-alt": C["night-800"],
        "--surface-read": C["paper-50"], "--surface-read-alt": C["paper-100"],
        # ---- 文字 ----
        "--size-display": S["text"]["display"]["size"],
        "--text-display-color": C["ink-900"], "--text-title-color": C["ink-900"],
        "--text-body-color": C["ink-700"], "--text-ui-color": C["ink-700"],
        "--text-meta-color": C["ink-500"], "--text-figure-color": C["ink-900"],
        "--text-narrative-color": C["paper-50"], "--size-narrative": S["text"]["narrative"]["size"],
        "--text-meta-on-stage": C["mist-400"],
        # ---- 状态：同一语义，纸面与幕两个值 ----
        "--state-flag": C["red-500"], "--state-flag-on-dark": S["state"]["flag-on-stage"],
        "--state-clear": C["green-600"], "--state-unknown": C["blue-500"],
        "--state-focus": C["amber-700"], "--state-focus-on-stage": C["gold-400"],
        "--state-press": S["state"]["press"], "--state-press-on-stage": S["state"]["press-on-stage"],
        "--brand-violet": C["violet-500"],
        "--measure-read": S["measure"]["read"],
        "--tap-min": S["tap"]["min"], "--tap-rec": S["tap"]["rec"],
    })
    body = "\n".join(f"  {k}:{val};" for k, val in v.items())
    return ":root{\n" + body + "\n}"


def parts(html):
    """把 <!--#part:name.ext--> 换成 src/parts/name.ext 的内容。"""
    def sub(m):
        f = PARTS / m.group(1)
        if not f.exists():
            print(f"缺少源码分片: {f}")
            raise SystemExit(1)
        return f.read_text(encoding="utf-8")
    return re.sub(r"<!--#part:([\w.\-]+)-->", sub, html)


def load_stories():
    """content/stories/*/case.json → SITE.x_stories"""
    out = []
    if STORIES.exists():
        for d in sorted(STORIES.iterdir()):
            f = d / "case.json"
            if f.exists():
                out.append(json.loads(f.read_text(encoding="utf-8")))
    return out
BACKEND_MARKER = "/*__BACKEND__*/null"  # 模板改造时引入；原始上游模板没有它



# 只在开发期有意义、运行时从不渲染的字段。它们随内容一起被打进单文件产物，
# 白白占体积——而体积是 owner 裁决的硬约束。
#   x_prov  —— 人工签字与内容哈希，只给 validate --release 用
#   _note   —— 下划线前缀按约定就是开发注释
#   note    —— sources[].note 的出处批注、cast[].note 的用真名理由：
#              留在源码里有价值（审计要看），但页面从不渲染它
DEV_ONLY = (
    "x_prov",        # 人工签字与内容哈希，只给 validate --release 用
    "_note",         # 下划线前缀按约定就是开发注释
    "note",          # sources[].note 的出处批注、cast[].note 的用真名理由
    # ── 消融实验找出来的：源码里有价值，产物里没有消费者 ──
    #
    # 判据是「谁在读它」。下面这些，全仓（前端 + tools + server）搜下来
    # 只有 tools 在读，也就是说它们对**用户**是纯下载体积。
    # 不删源码：x_qtype 记录了判分方式（规则判分，是 ADR 级别的承诺），
    # reorder 记录了三处刻意偏离教科书顺序的理由，x_coach_notes 是已写好的
    # 教练点评，x_identity/canon_sources/school 是三套语气语料各自的思想出处。
    # 这些都有档案价值，但用户下载它们没有任何用处。
    # ADR-0002 §4 裁决过「x_coaches 数据留着，名字不上屏」——留在源码，不进产物。
    # orig 是被译引文的英文原文，S7c 拿它去归档原档里逐字核对。
    # 全仓搜下来只有 validate 在读——对用户是纯下载体积。留在源码里，不进产物。
    "orig",
    "anchors",       # 同上：引文的行锚/页锚，机器核对用
    "x_qtype",
    "reorder",
    "x_coach_notes",
    "x_identity",
    "canon_sources",
    "school",
)


def strip_dev(o):
    if isinstance(o, dict):
        return {k: strip_dev(v) for k, v in o.items() if k not in DEV_ONLY}
    if isinstance(o, list):
        return [strip_dev(v) for v in o]
    return o


# 教练对象里只有 id 与 style_lines 被用到。name / intro 从不渲染——
# 而 ADR-0002 §1 写的是「全站不出现教练的人名，coachName() 恒返回『你的教练』」。
#
# 把人名发到用户浏览器里，等于把 ADR 禁止出现的东西放在手边：
# 哪天有人写了 ${c.name}，页面上就冒出「账房先生」，而没有任何东西会喊一声。
# **剥掉它，ADR 就从一条约定变成结构上做不到。**
#
# 不能加进 DEV_ONLY：name 在 cast[].name、sources[].name 里都是必需的，
# 全局按键名剥会把幕里的人物名字一起剥掉。
COACH_KEEP = ("id", "style_lines")


def strip_coach_persona(data):
    cs = data.get("x_coaches")
    if not cs:
        return data
    data["x_coaches"] = [{k: v for k, v in c.items() if k in COACH_KEEP} for c in cs]
    return data


# 注释留在源码里，不进交付物。
#
# 这个仓库的注释密度是刻意的——决策的理由写在它旁边，下一个人才不会把它改回去。
# 但注释会被原样打进单文件产物，白白占体积，而体积是 owner 裁决的硬约束（320KB）。
# 实测源码里 9.2KB 是注释。
#
# 只剥三类，且都取保守规则：
#   - HTML 注释（此时 <!--#part:--> 占位符早已被替换掉）
#   - /* … */ 块注释
#   - **整行** // 注释（行首只有空白）。不碰行尾的 //，那会吃掉 https:// 这类字符串
def strip_comments(html):
    import re
    head, sep, tail = html.partition(DATA_MARKER)   # 内容负载里可能含 // 与 /*，绝不能碰
    def clean(s):
        s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
        s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
        s = re.sub(r"(?m)^[ \t]*//[^\n]*\n", "", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s
    return clean(head) + sep + clean(tail) if sep else clean(html)


def main(argv):
    backend = None
    if "--backend" in argv:
        backend = argv[argv.index("--backend") + 1]

    r = subprocess.run([sys.executable, str(ROOT / "tools" / "validate.py"), str(CONTENT)])
    if r.returncode != 0:
        print("校验 FAIL —— 拒绝构建")
        return 1
    # 幕（content/stories/*/case.json）是现在的主体验，含真人姓名与逐字原档引文，
    # 必须和 site.json 一样过内容门禁。
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "validate.py"), "--stories"])
    if r.returncode != 0:
        print("幕校验 FAIL —— 拒绝构建")
        return 1

    tpl = TPL.read_text(encoding="utf-8")
    tpl = tpl.replace("/*__TOKENS__*/", css_vars())
    tpl = parts(tpl)
    if tpl.count(DATA_MARKER) != 1:
        print(f"模板中占位符 {DATA_MARKER} 不是恰好一次")
        return 1

    data = strip_coach_persona(strip_dev(json.loads(CONTENT.read_text(encoding="utf-8"))))

    # ── 多章合并（D11）──────────────────────────────────────────
    # 第二章不是「换一份 SITE」，是把它的 nodes/edges/x_review_bank 并进同一个 SITE。
    # 第二章节点自带 ageStart 8–11 与 domain「盈利质量」，前端已按 ageStart 分层、
    # 按 edges 解锁，所以合并即渲染，**前端零改动**。这是最低侵入的多章方案：
    # 不引入第二个 SITE 对象、不改前端根逻辑（byId/PAIRS/BANK 都从单一 SITE 派生）。
    #
    # 防呆:两章 id 不许冲突——一旦某个节点/题/幕 id 撞了，前端的 byId 会静默覆盖，
    # 是典型的「只查形状不查真值」翻车点，所以在这里当场拦。
    if CONTENT_CH2.exists():
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "validate.py"), str(CONTENT_CH2)])
        if r.returncode != 0:
            print("第二章校验 FAIL —— 拒绝构建")
            return 1
        ch2 = strip_coach_persona(strip_dev(json.loads(CONTENT_CH2.read_text(encoding="utf-8"))))
        ids1 = {n["id"] for n in data["nodes"]}
        for n in ch2.get("nodes", []):
            if n["id"] in ids1:
                print(f"多章合并 FAIL：节点 id「{n['id']}」两章冲突")
                return 1
        def _rvid(item):
            return (item.get("quiz") or {}).get("x_id")
        q1 = {_rvid(q) for q in data.get("x_review_bank", [])}
        for q in ch2.get("x_review_bank", []):
            if _rvid(q) in q1:
                print(f"多章合并 FAIL：复习题 x_id「{_rvid(q)}」两章冲突")
                return 1
        data["nodes"] += ch2.get("nodes", [])
        data["edges"] += ch2.get("edges", [])
        data["x_review_bank"] = (data.get("x_review_bank") or []) + (ch2.get("x_review_bank") or [])
        data["x_coaches"] = data.get("x_coaches") or ch2.get("x_coaches")  # 教练语料共用一份
        # 章名映射：两章各自登记的 x_chapters 合并（第二章至少要给出自己的章名）
        chmap = dict(data.get("x_chapters") or {})
        chmap.update(ch2.get("x_chapters") or {})
        if chmap:
            data["x_chapters"] = chmap
        print(f"多章合并: 第二章 {len(ch2.get('nodes', []))} 节点已并入(共 {len(data['nodes'])} 节点)")

    # 溯源徽标需要事实条目：把 facts.json 的 facts 按 id 注入 SITE.x_facts（只读展示用）
    fp = CONTENT.parent / "facts.json"
    facts = {}
    if fp.exists():
        facts.update({f["id"]: f for f in json.loads(fp.read_text(encoding="utf-8")).get("facts", [])})
    fp2 = CONTENT_CH2.parent / "facts.json"
    if fp2.exists():
        facts.update({f["id"]: f for f in json.loads(fp2.read_text(encoding="utf-8")).get("facts", [])})
    data["x_facts"] = facts
    st = [strip_dev(x) for x in load_stories()]
    if st:
        data["x_stories"] = st
        print(f"故事幕: {len(st)} 个（{', '.join(s['case_id'] for s in st)}）")
    # </ 转义防止 JSON 字符串意外闭合 <script>
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = tpl.replace(DATA_MARKER, payload)

    # **必须在 strip_comments 之前。** 占位符 /*__BACKEND__*/null 本身是个块注释，
    # 剥注释那一步会把它吃掉，于是下面的 marker 判断永远不成立、--backend 被静默忽略，
    # 还会打印一句「模板尚无后端占位符」把锅推给模板。这个开关从加剥注释那天起就是死的，
    # 直到 2026-09-03 有人真的想连后端才发现。
    if BACKEND_MARKER in html:
        html = html.replace(BACKEND_MARKER, json.dumps(backend) if backend else "null")
    elif backend:
        print(f"错误: 模板里找不到占位符 {BACKEND_MARKER}，--backend 无处可烧")
        return 1

    before = len(html.encode("utf-8"))
    html = strip_comments(html)
    saved = (before - len(html.encode("utf-8"))) / 1024
    print(f"剥离源码注释: 省下 {saved:.1f} KB（注释留在 src/，不进交付物）")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"构建完成: {OUT}（{OUT.stat().st_size / 1024:.1f} KB）")

    # ── 部署产物：干净的 publish/ ──────────────────────────────
    # dist/ 里混着离线分发物（旧的「第一章离线版.html」、zip、_archive/、netlify/ 缓存…）。
    # 直接发 dist/ 会把过时/无关文件推上公网。所以另建一个**只含 index.html + _headers**
    # 的专用目录，每次构建先清空重建，杜绝任何东西悄悄搭车上线。
    HEADERS = (
        "/*\n"
        "  X-Robots-Tag: noindex, nofollow, noarchive\n"
        "  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: no-referrer\n"
        "  Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'\n")
    PUB = ROOT / "publish"
    if PUB.exists():
        shutil.rmtree(PUB)
    PUB.mkdir()
    (PUB / "index.html").write_text(html, encoding="utf-8")
    (PUB / "_headers").write_text(HEADERS, encoding="utf-8")
    print(f"部署产物: {PUB}（只含 index.html + _headers，供 netlify deploy --dir=publish）")

    # 自查：给了 --backend 就必须在产物里找得到它。
    # 上面那个坑的教训是「参数被接受了、什么也没发生、还打印了一句让你去查别处的话」——
    # 只有拿产物回头验一次，才挡得住这一类。
    if backend and backend not in OUT.read_text(encoding="utf-8"):
        print(f"错误: --backend {backend} 没有出现在产物里，后端地址没烧进去")
        return 1
    if backend:
        print(f"后端地址已烧入产物: {backend}")

    # SPEC_DEV.md §9：任一门禁 FAIL 即拒绝构建（产物已写出，但退出码非零，CI/DoD 会挡住）
    # check_server 不查产物，查后端的隐私承诺（打码 / 出口检查 / 留存 / Origin 收口）。
    # 放进同一条阻断链是因为：那三样是 D3 裁决的内容，而裁决过的东西不该靠人记得去跑。
    for gate in ("check_src.py", "check_js.py", "check_a11y.py", "check_budget.py",
                 "check_tokens.py", "check_coach.py", "check_style.py", "check_server.py"):
        g = ROOT / "tools" / gate
        if g.exists():
            rc = subprocess.run([sys.executable, str(g), str(OUT)]).returncode
            if rc != 0:
                print(f"{gate} FAIL —— 构建不合格")
                return 1
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main(sys.argv[1:]))
