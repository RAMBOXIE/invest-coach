#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JS 语法门禁。

颜色、体积、字面值三类门禁检查的是产物的**形状**，没有一道检查产物
**跑不跑得起来**。这一道补上可执行性。

检查三处：
  J1a src/parts/*.js —— 分片本身能不能解析
  J1b dist 产物里每一段 <script> —— 拼装后的结果（分片各自合法，拼起来未必）
  J2  产物里被**调用**却从未声明过的标识符

J1 查「能不能解析」，J2 查「叫的那个名字存不存在」。
后者是必要的：`returnic('book')` 这种（批量替换吃掉一个空格）语法完全合法，
`node --check` 一路 PASS，一到运行就 ReferenceError。

需要 node。找不到 node 时给 WARN 并放行（不因环境缺失卡住构建），
但 CI 必须有 node，否则这道门禁形同虚设。

用法: python tools/check_js.py [dist/index.html]
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent


def check(node, src, label):
    """把 src 写成临时 .js 交给 node --check。返回错误串或 None。"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as f:
        f.write(src)
        tmp = f.name
    try:
        r = subprocess.run([node, "--check", tmp], capture_output=True, text=True)
        if r.returncode == 0:
            return None
        err = (r.stderr or r.stdout).replace(tmp, label)
        # 只留前几行，够定位就行
        return "\n".join(err.strip().split("\n")[:6])
    finally:
        try:
            pathlib.Path(tmp).unlink()
        except OSError:
            pass


# CSS 函数名会出现在模板字符串里，长得跟调用一模一样；浏览器全局也不在源码里声明。
KNOWN = set("""
Object Array String Number Boolean Math JSON Date RegExp Map Set WeakMap WeakSet Promise Proxy Reflect Symbol
Error TypeError RangeError SyntaxError BigInt Intl structuredClone queueMicrotask
parseInt parseFloat isNaN isFinite encodeURIComponent decodeURIComponent encodeURI decodeURI atob btoa
escape unescape
setTimeout setInterval clearTimeout clearInterval requestAnimationFrame cancelAnimationFrame
fetch alert confirm prompt addEventListener removeEventListener dispatchEvent
AbortController FormData Headers Request Response URL URLSearchParams IntersectionObserver
MutationObserver ResizeObserver TextEncoder TextDecoder Blob File FileReader Image Audio Worker
getComputedStyle matchMedia scrollTo scrollBy open close postMessage
var not repeat calc clamp minmax url rgb rgba hsl hsla linear-gradient radial-gradient
translate translateX translateY translateZ scale rotate cubic-bezier steps env attr counter
""".split())
KEYWORDS = set("""if for while switch catch return typeof new delete void do else try finally throw
case in of await yield function class super this with instanceof""".split())


def undeclared(src):
    """被调用却从未声明的标识符。先剥注释再扫，只看调用点。"""
    s = re.sub(r"//[^\n]*", "", src)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    called = set(re.findall(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(", s))
    declared = set()
    declared |= set(re.findall(r"\bfunction\s+([A-Za-z_$][\w$]*)", s))
    declared |= set(re.findall(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)", s))
    declared |= set(re.findall(r"\bwindow\.([A-Za-z_$][\w$]*)\s*=", s))
    declared |= set(re.findall(r"\b([A-Za-z_$][\w$]*)\s*=\s*(?:function|\()", s))
    declared |= set(re.findall(r"\bclass\s+([A-Za-z_$][\w$]*)", s))
    return sorted(called - declared - KEYWORDS - KNOWN)


def main(path):
    node = shutil.which("node")
    if not node:
        print("WARN : 找不到 node，JS 语法门禁跳过——CI 必须装 node，否则这道门禁形同虚设")
        return 0

    errors = []

    # 1) 源码分片
    parts = sorted((ROOT / "src" / "parts").glob("*.js"))
    for f in parts:
        e = check(node, f.read_text(encoding="utf-8"), str(f.relative_to(ROOT)))
        if e:
            errors.append(e)

    # 2) 产物里的每一段 <script>（拼装后才暴露的问题）
    p = pathlib.Path(path)
    if p.exists():
        html = p.read_text(encoding="utf-8")
        blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
        for i, b in enumerate(blocks):
            if not b.strip():
                continue
            e = check(node, b, f"{p.name} 第 {i + 1} 段 <script>")
            if e:
                errors.append(e)
        print(f"INFO : 检查 {len(parts)} 个分片 + {len(blocks)} 段内联 script")
        # J2：整份产物合起来看，谁调用了一个谁都没声明过的名字
        unk = undeclared("\n".join(blocks))
        for u in unk:
            errors.append(f"J2 调用了从未声明的 `{u}(` —— 语法合法但运行必 ReferenceError。"
                          "若它确是浏览器全局或 CSS 函数名，加进 check_js.py 的 KNOWN")

    if errors:
        print("JS: FAIL")
        for e in errors:
            print("ERROR: " + e)
        return 1
    print("JS: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "dist" / "index.html"))
