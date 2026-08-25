#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视觉与可读性门禁（SPEC_DEV.md §3/§6）。ERROR 非零退出，build.py 据此拒绝构建。

规则：
  A1 字号下限        meta ≥13px / UI ≥15px；禁止 <13px 的字面字号
  A2 对比度          从 tokens 的语义色对提取并实算，正文 ≥7:1、辅助 ≥4.5:1、图形 ≥3:1
  A3 触控目标        min-height 声明的按钮类规则 ≥44px
  A4 禁用清单        tokens.banned 里的手段一律扫描
  A5 1.4.12 抗覆盖    禁止写死高度的全屏容器（height:100vh/100dvh 用于 .stage/.scene）
  A6 reduced-motion   必须存在 prefers-reduced-motion 分支
用法: python tools/check_a11y.py [dist/index.html]
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOK = json.loads((ROOT / "design" / "tokens.json").read_text(encoding="utf-8"))

def srgb(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def lum(hexs):
    h = hexs.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b)

def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

def main(path):
    errors, warns, infos = [], [], []
    p = pathlib.Path(path)
    if not p.exists():
        print(f"找不到 {p}"); return 1
    html = p.read_text(encoding="utf-8")
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))

    # A1 字号下限
    for m in re.finditer(r"font-size\s*:\s*([\d.]+)px", css):
        v = float(m.group(1))
        if v < 13:
            line = css[:m.start()].count("\n") + 1
            errors.append(f"A1 字号 {v}px < 13px（CSS 第 {line} 行）——meta 下限 13px、UI 15px、叙事正文 17–19px")

    # A2 对比度（对 tokens 里声明过 _contrast 的语义对做实算复核）
    C = TOK["primitive"]["color"]
    pairs = [("text.meta on shell", C["mist-400"], C["night-800"], 4.5),
             ("text.narrative on stage", C["paper-50"], C["night-900"], 7.0),
             ("text.body on read", C["ink-700"], C["paper-50"], 7.0),
             ("text.ui on shell", C["paper-50"], C["night-800"], 4.5),
             ("state.flag on read", C["red-500"], C["paper-50"], 4.5),
             ("state.clear on read", C["green-500"], C["paper-50"], 4.5)]
    for name, fg, bg, need in pairs:
        r = ratio(fg, bg)
        if r < need:
            errors.append(f"A2 对比度 {name} = {r:.2f}:1 < {need}:1（{fg} on {bg}）")
        else:
            infos.append(f"A2 {name} = {r:.2f}:1 ✓（需 ≥{need}）")

    # A2b 正文里出现的裸色值若用在 color: 上，粗查是否是已知低对比色
    for bad in ("#7b749b", "#8c85ad", "#9a93b5", "#a49cc4"):
        if bad in css.lower():
            errors.append(f"A2b 出现已知低对比色 {bad}——请改用 tokens 的 text.meta（#A9B0C2, 8.8:1）")

    # A3 触控目标
    for m in re.finditer(r"min-height\s*:\s*([\d.]+)px", css):
        v = float(m.group(1))
        if 0 < v < 44:
            warns.append(f"A3 min-height {v}px < 44px——触控目标下限 44px（推荐 48px）")

    # A4 禁用清单
    for b in TOK.get("banned", []):
        key = b.split("：")[0].strip()
        if key.startswith("background-attachment") and re.search(r"background-attachment\s*:\s*fixed", css):
            errors.append("A4 命中禁用清单：background-attachment:fixed（iOS 不支持、Android 每帧整页重绘）")
    if re.search(r"@font-face", css):
        errors.append("A4 命中禁用清单：@font-face（中文正文字体子集会撑破 300KB 预算；标题子集需 ADR 豁免）")
    if re.search(r"\bparallax\b|scroll-snap-type\s*:\s*[^;]*mandatory", css):
        warns.append("A4 疑似视差/滚动劫持——需 ADR 豁免")

    # A5 1.4.12 抗覆盖：全屏容器不许写死高度
    for m in re.finditer(r"(?<!min-)height\s*:\s*100(vh|dvh|svh)\b", css):
        seg = css[max(0, m.start() - 300):m.start()]
        if not re.search(r"min-height\s*:\s*100", seg):
            errors.append(f"A5 出现 height:100{m.group(1)} 且无 min-height 兜底——WCAG 1.4.12 抗覆盖会裁切内容，改用 min-height:100svh")

    # A6 reduced-motion
    if re.search(r"transition|animation", css) and "prefers-reduced-motion" not in css:
        errors.append("A6 存在动效但缺 prefers-reduced-motion 分支")

    for i in infos: print("INFO :", i)
    for w in warns: print("WARN :", w)
    for e in errors: print("ERROR:", e)
    print("A11Y:", "FAIL" if errors else "PASS")
    return 1 if errors else 0

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "dist" / "index.html"))
