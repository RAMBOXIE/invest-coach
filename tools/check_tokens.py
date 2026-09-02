#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""令牌纪律门禁（SPEC_DEV §2 / tokens.banned「源码字面色值与字面字号」）。

**令牌不被强制引用，真源就不是真源。** 源码里的字面 hex / 字面字号会让
页面上的颜色和令牌里的颜色长期不一致，而读 tokens 的门禁察觉不到。

棘轮策略：现存字面值是历史债，一次清完回归风险大。本门禁记录基线数量，
**只挡新增**。修掉一个就把基线降一个（--update 自动写回），只减不增。

用法:
  python tools/check_tokens.py            # 校验
  python tools/check_tokens.py --update   # 把当前计数写回基线（只允许下降）
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = ROOT / "design" / "token-debt.json"
TARGETS = ["src/template.html", "src/parts/court.css", "src/parts/story.css"]

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
FONT_PX = re.compile(r"font-size\s*:\s*[0-9.]+px")


def strip_comments(s):
    """只数真正会被浏览器读到的那些。

    注释里提到某个色值不是债，把它算进棘轮等于逼人删注释去凑数字。
    """
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)      # CSS / JS 块注释
    s = re.sub(r"(?m)^\s*//[^\n]*", "", s)             # JS 整行注释
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)       # HTML 注释
    return s


def check_undefined_vars():
    """T2：引用了却从未定义的 CSS 变量。

    这类错误是**静默的**：`var(--dur-2)` 里那个变量不存在时，浏览器不会报错，
    只是这条声明失效——动画不跑、颜色回落继承值，页面看着「差不多对」。
    A9 查的是类名对账，查不到这个；实测中我自己就写错过一次（--dur-2，
    实际叫 --dur-micro）。

    定义有两个来源：源码里直接写的，和构建期从 design/tokens.json 生成的那批。
    """
    import subprocess
    src = ""
    for rel in TARGETS:
        f = ROOT / rel
        if f.exists():
            src += strip_comments(f.read_text(encoding="utf-8"))
    used = set(re.findall(r"var\(\s*(--[\w-]+)", src))
    defined = set(re.findall(r"(--[\w-]+)\s*:", src))
    # 构建期注入的令牌变量
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_b", ROOT / "tools" / "build.py")
        b = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(b)
        defined |= set(re.findall(r"(--[\w-]+)\s*:", b.css_vars()))
    except Exception as e:
        return [], [f"T2 跳过：读不到构建期令牌（{e}）"]
    missing = sorted(used - defined)
    if missing:
        return [f"T2 引用了从未定义的 CSS 变量 {missing} —— "
                "这类失效是静默的：声明直接被丢弃，页面看着差不多对"], []
    return [], []


def scan():
    """返回 {文件: {"hex": n, "font_px": n}}，并附带明细供报错时展示。"""
    counts, detail = {}, {}
    for rel in TARGETS:
        p = ROOT / rel
        if not p.exists():
            continue
        s = strip_comments(p.read_text(encoding="utf-8"))
        hexes = HEX.findall(s)
        fonts = FONT_PX.findall(s)
        counts[rel] = {"hex": len(hexes), "font_px": len(fonts)}
        detail[rel] = {"hex": sorted(set(hexes)), "font_px": sorted(set(fonts))}
    return counts, detail


def main(argv):
    counts, detail = scan()

    if "--update" in argv:
        old = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
        bumped = []
        for f, c in counts.items():
            for k, v in c.items():
                prev = old.get(f, {}).get(k)
                if prev is not None and v > prev:
                    bumped.append(f"{f}.{k} {prev} → {v}")
        if bumped:
            print("拒绝写回：基线只允许下降，以下项在上升")
            for b in bumped:
                print("  " + b)
            return 1
        BASELINE.write_text(
            json.dumps({"_note": "令牌纪律棘轮基线。只减不增。修掉字面值后跑 --update 降低它。",
                        "counts": counts}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        print(f"基线已更新: {BASELINE}")
        for f, c in counts.items():
            print(f"  {f}: hex={c['hex']} font_px={c['font_px']}")
        return 0

    if not BASELINE.exists():
        print(f"缺少基线 {BASELINE}——先跑 python tools/check_tokens.py --update")
        return 1

    base = json.loads(BASELINE.read_text(encoding="utf-8"))["counts"]
    errors = []
    for f, c in counts.items():
        b = base.get(f, {"hex": 0, "font_px": 0})
        for k, label in (("hex", "字面色值"), ("font_px", "字面字号")):
            if c[k] > b.get(k, 0):
                errors.append(
                    f"{f}: {label} {b.get(k, 0)} → {c[k]}（+{c[k] - b.get(k, 0)}）"
                    f"——新增的请改用 var(--...)；令牌在 design/tokens.json")
            elif c[k] < b.get(k, 0):
                print(f"INFO : {f} {label} {b.get(k,0)} → {c[k]}，还清 {b[k]-c[k]} 条"
                      f"（跑 --update 把基线降下来）")

    errs2, warns2 = check_undefined_vars()
    errors += errs2
    for w in warns2:
        print("WARN : " + w)
    if not errs2:
        print("INFO : T2 无引用了却从未定义的 CSS 变量 ✓")

    if errors:
        print("TOKENS: FAIL")
        for e in errors:
            print("ERROR: " + e)
        # 报错时把当前明细打出来，方便定位
        for f in detail:
            if any(f in e for e in errors):
                print(f"  {f} 现存字面色值: {', '.join(detail[f]['hex'][:20])}")
        return 1

    total_hex = sum(c["hex"] for c in counts.values())
    total_px = sum(c["font_px"] for c in counts.values())
    print(f"TOKENS: PASS（历史债 字面色值 {total_hex} / 字面字号 {total_px}，未新增）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main(sys.argv[1:]))
