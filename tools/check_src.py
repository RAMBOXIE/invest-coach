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

    print(f"INFO : 扫描 {n} 个源码文件")
    for e in errors:
        print("ERROR:", e)
    if not errors:
        print("INFO : S1 无字面控制符 ✓  S2 无永假构造 ✓")
    print("SRC:", "FAIL" if errors else "PASS")
    return 1 if errors else 0


def selftest():
    """变异测试：往一个源码文件里塞一个字面退格符，看规则会不会红。"""
    import subprocess
    f = ROOT / "tools" / "check_src.py"
    orig = f.read_text(encoding="utf-8")
    try:
        f.write_text(orig + "\n# " + chr(8) + "\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(f)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        ok = "ERROR: S1" in r.stdout
        print("  " + ("✓ 塞一个字面退格符 → 规则正确报错"
                      if ok else "✗ 塞了却没报错 —— 这条规则是摆设"))
        return 0 if ok else 1
    finally:
        f.write_text(orig, encoding="utf-8")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(selftest() if "--selftest" in sys.argv else main())
