#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源码卫生门禁 —— 挡「看着对、其实永远不生效」的那一类写法。

**为什么单独一道。** 这个仓库里最常见的失败不是崩溃，是**静默失效**：
一条规则、一个正则、一个 CSS 变量看起来在那儿，实际上永远不触发，
而所有门禁都是绿的。

  S1 字面控制符：用 heredoc 写 Python 时，正则里的 \\b 会被折成**字面退格符**
     （0x08）。`\\$[A-Z]{1,5}\\b` 变成 `\\$[A-Z]{1,5}\x08`，永远匹配不上。
     本会话踩了三次：check_coach 的 C5（q.hints 检查半年没生效）、
     check_coach 的 C10、server 的证券代码打码（$AAPL 完全没打上）。
     每次都是「规则在那儿、是绿的、但不工作」。

  S2 空的正则字符类与永假分支：`[^]`、`(?!)`、`if False:`。

用法: python tools/check_src.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# 扫所有会跑的源码。dist/build 是产物，evidence 是归档原档，都不扫。
SCAN_DIRS = ("tools", "server", "src")
SCAN_EXT = (".py", ".js", ".go", ".html", ".css")
CTRL = {"\x07": "\\a 响铃", "\x08": "\\b 退格", "\x0b": "\\v 纵向制表", "\x0c": "\\f 换页"}


def files():
    for d in SCAN_DIRS:
        p = ROOT / d
        if not p.exists():
            continue
        for f in sorted(p.rglob("*")):
            if f.is_file() and f.suffix in SCAN_EXT and "__pycache__" not in str(f):
                yield f


def endpoint_coverage():
    """E1 前端调的每个后端端点，主线实现里必须存在。

    这条挡的是一次真实的漂移：STRUCTURE.md 声明 `main.go` 是主线，
    而我给 Python 版加了 /api/v1/review-note 与 mask_pii 之后没动 Go 版。
    结果是**声明的主实现没有打码**——部署它，用户的持仓金额与联系方式
    原样进第三方模型、原样入库，而 D3 裁决明确禁止这件事。

    主线是谁由 docs/STRUCTURE.md 说，不写死在这里：改了主线，规则跟着变。
    """
    fe = ""
    for rel in ("src/template.html", "src/parts/court.js", "src/parts/story.js"):
        f = ROOT / rel
        if f.exists():
            fe += f.read_text(encoding="utf-8")
    called = sorted(set(re.findall(r"/api/v[\d]+/[\w-]+", fe)))
    if not called:
        return []
    doc = (ROOT / "docs" / "STRUCTURE.md")
    if not doc.exists():
        return ["E1 找不到 docs/STRUCTURE.md，无法确定哪份是主线"]
    m = re.search(r"\*\*`(server/[\w.]+|[\w.]+)`\s*是主线\*\*", doc.read_text(encoding="utf-8"))
    if not m:
        return ["E1 docs/STRUCTURE.md 没有用「**`x` 是主线**」标明主线后端 —— "
                "两份实现并存却不说哪份权威，就是下一次漂移的入口"]
    name = m.group(1).split("/")[-1]
    primary = ROOT / "server" / name
    if not primary.exists():
        return [f"E1 STRUCTURE.md 声明主线是 {name}，但 server/{name} 不存在"]
    impl = primary.read_text(encoding="utf-8")
    # **查路由注册，不查字符串出现。**
    # 第一版只判 `e not in impl`，而我刚往 main.go 的头部注释里写了
    # 「没有 /api/v1/review-note」——规则于是「找到了」这个端点，变异测试没抓住。
    # 这正是本仓反复栽的「只查形状不查真值」，在一道专门防漂移的门禁里又犯一次。
    impl = re.sub(r"/\*.*?\*/", "", impl, flags=re.S)
    impl = re.sub(r"(?m)^\s*(?://|#)[^\n]*", "", impl)
    miss = []
    for e in called:
        # Go: HandleFunc("/api/…"  ｜ Python: self.path == "/api/…" / startswith("/api/…"
        if not re.search(r"(?:HandleFunc|path\s*[!=]=|startswith)\s*\(?\s*[\"']"
                         + re.escape(e), impl):
            miss.append(e)
    if miss:
        return [f"E1 前端调了 {' '.join(miss)}，主线实现 server/{name} 里没有 —— "
                "前端会一直拿到 404 或静默回落，而没有任何东西会喊一声"]
    print(f"INFO : E1 前端调的 {len(called)} 个端点在主线 server/{name} 里都存在 ✓")
    return []


def llm_use_registered():
    """E2 每个调模型的函数，都必须在 LLM_USE_REGISTRY.md 里被点到名。

    登记簿开头写着「任何新的 LLM 用途必须先在本表登记，未登记即违规」——
    而上一轮我实现并上线了 review-note（运行时**散文**生成，正是 #5 被放弃的
    那一类），没有登记。一条没有执行者的规矩，在需要它的那一次就不会生效。

    判据取「调用点所在的函数名出现在登记簿里」：加一个新的模型调用，
    要么给它登记一行，要么门禁红。
    """
    reg = ROOT / "docs" / "LLM_USE_REGISTRY.md"
    if not reg.exists():
        return ["E2 找不到 docs/LLM_USE_REGISTRY.md"]
    doc = reg.read_text(encoding="utf-8")
    calls, errs = [], []
    for f in sorted((ROOT / "server").glob("*.py")):
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(lines):
            if "anthropic.com" not in ln or ln.lstrip().startswith("#"):
                continue
            for j in range(i, -1, -1):
                m = re.match(r"\s*def\s+(\w+)", lines[j])
                if m:
                    calls.append((f.name, m.group(1), j + 1))
                    break
            else:
                errs.append(f"E2 {f.name}:{i+1} 模型调用不在任何函数里，无法登记")
    for fname, fn, line in calls:
        if fn not in doc:
            errs.append(f"E2 {fname}:{line} 的 `{fn}()` 会调模型，但 LLM_USE_REGISTRY.md "
                        "里没有点到它的名 —— 登记簿写着「未登记即违规」，这条就是它的执行者")
    if not errs and calls:
        print(f"INFO : E2 {len(calls)} 个模型调用点（{'、'.join(c[1] for c in calls)}）都已登记 ✓")
    return errs


def main():
    errors, n = [], 0
    for f in files():
        n += 1
        try:
            s = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = f.relative_to(ROOT).as_posix()
        for i, ch in enumerate(s):
            if ch in CTRL:
                line = s[:i].count("\n") + 1
                ctx = s[max(0, i - 40):i + 12].replace("\n", "\\n")
                errors.append(
                    f"S1 {rel}:{line} 出现字面控制符 {CTRL[ch]}（0x{ord(ch):02x}）"
                    f"…{ctx}… —— 多半是正则里的转义被 heredoc 吃掉了，"
                    "这条正则永远匹配不上，而规则看起来仍然是绿的")
        # 本文件的文档里举了这两个构造做例子，扫自己会误报。
        body = s.split('"""', 2)[-1] if rel == "tools/check_src.py" else s
        for m in re.finditer(r"\[\^\]|\(\?\!\)", body):
            line = s[:m.start()].count("\n") + 1
            errors.append(f"S2 {rel}:{line} 出现永不匹配的构造 `{m.group(0)}`")
        for m in re.finditer(r"(?m)^\s*if\s+False\s*:", s):
            line = s[:m.start()].count("\n") + 1
            errors.append(f"S2 {rel}:{line} 出现 `if False:` 永假分支")

    errors += endpoint_coverage()
    errors += llm_use_registered()
    print(f"INFO : 扫描 {n} 个源码文件")
    for e in errors:
        print("ERROR:", e)
    if not errors:
        print("INFO : S1 无字面控制符 ✓  S2 无永假构造 ✓")
    print("SRC:", "FAIL" if errors else "PASS")
    return 1 if errors else 0


def selftest():
    """变异测试：三条规则逐个弄坏，看门禁会不会红。

    E1/E2 原来只在写的时候手动验过一次，验完就没了。规矩是「每加一条规则
    都要证明它会失灵」——而证明必须能重跑，否则半年后没人知道它还灵不灵。
    """
    import subprocess

    def run():
        return subprocess.run([sys.executable, str(ROOT / "tools" / "check_src.py")],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout

    me = ROOT / "tools" / "check_src.py"
    srv = ROOT / "server" / "server.py"
    doc = ROOT / "docs" / "STRUCTURE.md"
    files = {f: f.read_text(encoding="utf-8") for f in (me, srv, doc)}
    cases = [
        ("S1", "往源码里塞一个字面退格符",
         me, lambda t: t + "\n# " + chr(8) + "\n"),
        ("E1", "把主线声明改回没有打码的那份实现",
         doc, lambda t: t.replace("**`server.py` 是主线**", "**`main.go` 是主线**", 1)),
        ("E2", "加一个没登记的模型调用",
         srv, lambda t: t + '\n\ndef grade_with_llm(x):\n'
                            '    return urllib.request.Request("https://api.anthropic.com/v1/messages")\n'),
    ]
    bad = 0
    try:
        for code, desc, f, mut in cases:
            f.write_text(mut(files[f]), encoding="utf-8")
            hit = f"ERROR: {code}" in run()
            bad += not hit
            print("  " + ("✓ " if hit else "✗ ") + f"{code} {desc} → "
                  + ("规则正确报错" if hit else "改坏了却没报错，这条规则是摆设"))
            f.write_text(files[f], encoding="utf-8")
    finally:
        for f, t in files.items():
            f.write_text(t, encoding="utf-8")
    print("SELFTEST:", "FAIL" if bad else f"PASS（{len(cases)} 条）")
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(selftest() if "--selftest" in sys.argv else main())
