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
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "ch1" / "site.json"
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


def main(argv):
    backend = None
    if "--backend" in argv:
        backend = argv[argv.index("--backend") + 1]

    r = subprocess.run([sys.executable, str(ROOT / "tools" / "validate.py"), str(CONTENT)])
    if r.returncode != 0:
        print("校验 FAIL —— 拒绝构建")
        return 1

    tpl = TPL.read_text(encoding="utf-8")
    tpl = tpl.replace("/*__TOKENS__*/", css_vars())
    tpl = parts(tpl)
    if tpl.count(DATA_MARKER) != 1:
        print(f"模板中占位符 {DATA_MARKER} 不是恰好一次")
        return 1

    data = json.loads(CONTENT.read_text(encoding="utf-8"))
    # 溯源徽标需要事实条目：把 facts.json 的 facts 按 id 注入 SITE.x_facts（只读展示用）
    fp = CONTENT.parent / "facts.json"
    if fp.exists():
        data["x_facts"] = {f["id"]: f for f in json.loads(fp.read_text(encoding="utf-8")).get("facts", [])}
    st = load_stories()
    if st:
        data["x_stories"] = st
        print(f"故事幕: {len(st)} 个（{', '.join(s['case_id'] for s in st)}）")
    # </ 转义防止 JSON 字符串意外闭合 <script>
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = tpl.replace(DATA_MARKER, payload)

    if BACKEND_MARKER in html:
        html = html.replace(BACKEND_MARKER, json.dumps(backend) if backend else "null")
    elif backend:
        print("提示: 模板尚无后端占位符，--backend 参数被忽略（第 3 步模板改造后生效）")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"构建完成: {OUT}（{OUT.stat().st_size / 1024:.1f} KB）")

    # SPEC_DEV.md §9：任一门禁 FAIL 即拒绝构建（产物已写出，但退出码非零，CI/DoD 会挡住）
    for gate in ("check_js.py", "check_a11y.py", "check_budget.py", "check_tokens.py"):
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
