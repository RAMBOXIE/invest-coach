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
  A7 浮层层级         抽屉/遮罩必须高于每一个不透明全屏层，否则「渲染了但看不见」
  A8 点击反馈         按下 / 焦点 / 禁用三态必须存在，且不许关掉默认高亮又不补
  A9 类名对账         定义了没人用（死代码）+ 用了却没定义（静默失效）
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
    css_style_only = css   # A9 要的是真样式表；下面会往 css 里塞合成的 ._inlineN
    # 内联 style 压过任何样式表规则，却不在 <style> 里。不扫它就会出现
    # 「改了 CSS 但被内联覆盖、门禁全程 PASS」。
    inline = re.findall(r'style="([^"]*)"', html)
    if inline:
        css += "\n" + "\n".join("._inline%d{%s}" % (i, d) for i, d in enumerate(inline))

    # A1 字号下限
    for m in re.finditer(r"font-size\s*:\s*([\d.]+)px", css):
        v = float(m.group(1))
        if v < 13:
            line = css[:m.start()].count("\n") + 1
            errors.append(f"A1 字号 {v}px < 13px（CSS 第 {line} 行）——meta 下限 13px、UI 15px、叙事正文 17–19px")

    # ---- A2 对比度 ----
    # 颜色对从 tokens 的 _contrast_on_* 注记推导，实算必须与注记一致——
    # 注记写错或值漂移都会被挡下。硬编码颜色对等于门禁跟页面实际画什么无关。
    C = TOK["primitive"]["color"]
    S = TOK["semantic"]

    def deref(v):
        if not isinstance(v, str):
            return None
        m = re.fullmatch(r"\{color\.([\w-]+)\}", v)
        return C[m.group(1)] if m else (v if v.startswith("#") else None)

    surfaces = {k: deref(v) for k, v in S["surface"].items() if deref(v)}
    NEED = {"body": 7.0, "narrative": 7.0}          # 正文级 7:1，其余 4.5:1

    checked = 0
    for role, spec in S["text"].items():
        if not isinstance(spec, dict):
            continue
        fg = deref(spec.get("color"))
        if not fg:
            continue
        for k, claimed in spec.items():
            if not k.startswith("_contrast_on_"):
                continue
            surf = k[len("_contrast_on_"):]
            bg = surfaces.get(surf)
            if not bg:
                errors.append(f"A2 text.{role} 注记了 on {surf}，但 semantic.surface 里没有这个面")
                continue
            actual, need = ratio(fg, bg), NEED.get(role, 4.5)
            checked += 1
            try:
                claimed_v = float(str(claimed).split(":")[0])
            except ValueError:
                claimed_v = None
            if claimed_v is not None and abs(actual - claimed_v) > 0.05:
                errors.append(
                    f"A2 text.{role} on {surf}: 注记写 {claimed_v}:1，实算 {actual:.2f}:1"
                    "——注记与令牌值不符，改了颜色没改注记")
            if actual < need:
                errors.append(f"A2 text.{role} on {surf} = {actual:.2f}:1 < {need}:1（{fg} on {bg}）")
            else:
                infos.append(f"A2 text.{role} on {surf} = {actual:.2f}:1 ✓（需 ≥{need}）")

    # 状态色：**每一个真会被画出来的面**都要过，不只 shell 与 card——
    # 外壳渐变的深端是 paper-200，只比 shell/card 会漏掉它。
    # 场（纸/幕）由后缀决定，别混着比。
    PAPER = ("shell", "shell-alt", "card", "rule", "read", "read-alt")
    STAGE = ("stage", "stage-alt")
    for st, fg in ((k, deref(v)) for k, v in S["state"].items() if not k.startswith("_")):
        if not fg:
            continue
        faces = STAGE if st.endswith(("-on-stage", "-on-dark")) else PAPER
        for surf in faces:
            bg = surfaces.get(surf)
            if not bg:
                continue
            r = ratio(fg, bg)
            checked += 1
            if r < 4.5:
                errors.append(f"A2 state.{st} on {surf} = {r:.2f}:1 < 4.5:1")
            else:
                infos.append(f"A2 state.{st} on {surf} = {r:.2f}:1 ✓")

    if checked == 0:
        errors.append("A2 一个颜色对都没检出——tokens 的 _contrast_on_* 注记缺失，门禁形同虚设")

    # ---- A2b 实扫 CSS 里的字面文字色 ----
    # 每个用在 color: 上的字面色，至少要在某一个已定义的面上达到 4.5:1；
    # 全都不达标就是它没有合法的落脚处。这条抓的是黑名单抓不住的那一类。
    for m in re.finditer(r"\{([^{}]*)\}", css):
        block = m.group(1)
        cm = re.search(r"(?<![-\w])color\s*:\s*(#[0-9a-fA-F]{3,6})\b", block)
        if not cm:
            continue
        fg = cm.group(1)
        # 同一条规则里若自带字面背景，就按它算——比拿全局面去猜准确
        bm = re.search(r"background(?:-color)?\s*:\s*(#[0-9a-fA-F]{3,6})\b", block)
        line = css[:m.start()].count("\n") + 1
        if bm:
            r = ratio(fg, bm.group(1))
            if r < 4.5:
                errors.append(f"A2b {fg} on {bm.group(1)}（CSS 第 {line} 行）= {r:.2f}:1 < 4.5:1")
        else:
            best = max(((ratio(fg, bg), n) for n, bg in surfaces.items()), default=(0, "?"))
            if best[0] < 4.5:
                errors.append(
                    f"A2b 字面文字色 {fg}（CSS 第 {line} 行）在任何已定义的面上都不达 4.5:1"
                    f"（最好的是 {best[1]} {best[0]:.2f}:1）——改用 tokens 的语义色")

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
        errors.append("A4 命中禁用清单：@font-face（中文正文字体子集会撑破体积预算；标题子集需 ADR 豁免）")
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

    # ---- A7 浮层层级 ----
    # 不透明的全屏层若盖在抽屉之上，从它里面唤起的抽屉会「渲染正常但看不见、点不到」，
    # 而颜色/体积/字面值三类门禁全都查不出来。
    #
    # 两个实现要点：
    #   1. 同一个选择器可能出现在多条规则里（.sty 既有本体，也有 `.stage,.sty{left:96px}`）。
    #      只看第一条匹配会漏掉真正那条，所以扫全部规则再合并。
    #   2. 先剥注释——注释会被当成选择器的一部分吞进去，导致匹配失败、静默放行。
    css_nc = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def blocks_for(cls):
        out = []
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css_nc):
            sels = [x.strip() for x in m.group(1).split(",")]
            if any(re.fullmatch(re.escape(cls) + r"(::?[\w-]+(\([^)]*\))?)*", x) for x in sels):
                out.append(re.sub(r"\s+", "", m.group(2)))
        return out

    def zof(cls):
        zs = [int(z) for b in blocks_for(cls) for z in re.findall(r"z-index:(\d+)", b)]
        return max(zs) if zs else None

    def opaque_fullscreen(cls):
        bs = blocks_for(cls)
        return (any("position:fixed" in b for b in bs)
                and any("inset:0" in b for b in bs)
                and any(re.search(r"background(-color)?:(?!transparent|none)", b) for b in bs))

    z_sheet, z_scrim = zof(".sheet"), zof(".scrim")
    if z_sheet is None:
        errors.append("A7 找不到 .sheet 的 z-index——浮层层级无法校验")
    else:
        checked_layers = 0
        for sel in (".stage", ".sty"):
            z = zof(sel)
            if z is None or not opaque_fullscreen(sel):
                continue
            checked_layers += 1
            if z >= z_sheet:
                errors.append(
                    f"A7 {sel} 的 z-index {z} ≥ .sheet 的 {z_sheet}，而 {sel} 是不透明全屏层"
                    "——从它里面唤起的抽屉会被整块盖住：渲染正常、点不到、看不见")
            elif z_scrim is not None and z >= z_scrim:
                errors.append(
                    f"A7 {sel} 的 z-index {z} ≥ .scrim 的 {z_scrim}——遮罩盖不住它，点遮罩关闭失效")
            else:
                infos.append(f"A7 .sheet({z_sheet}) / .scrim({z_scrim}) 高于 {sel}({z}) ✓")
        if checked_layers < 2:
            errors.append(
                f"A7 只校验到 {checked_layers} 个全屏层，预期 2（.stage / .sty）"
                "——选择器匹配没命中，等于这道门禁没生效")

    # ---- A8 点击反馈 ----
    # 产品铁律：每个点击都要有反馈。* 里关掉了 -webkit-tap-highlight-color，
    # 不自己补 :active 的话手机上点任何东西都是零反应——这是实测过的。
    has_tap_off = re.search(r"-webkit-tap-highlight-color\s*:\s*transparent", css_nc)
    act = re.findall(r"([^{}]*:active[^{}]*)\{", css_nc)
    if has_tap_off and not act:
        errors.append("A8 关掉了 -webkit-tap-highlight-color 却没有任何 :active 规则"
                      "——手机上点任何东西都没有按下反馈")
    elif not act:
        warns.append("A8 全站没有 :active 规则")
    else:
        covered = " ".join(act)
        for el in ("button", "summary", "a[href]"):
            if el not in covered:
                errors.append(f"A8 {el} 没有按下态（:active）——它是可点元素，点了必须有反馈")
        infos.append(f"A8 按下态覆盖 {len(act)} 组选择器 ✓")
    foc = " ".join(re.findall(r"([^{}]*:focus-visible[^{}]*)\{", css_nc))
    for el in ("button", "summary", "input"):
        if el not in foc:
            errors.append(f"A8 {el} 没有 :focus-visible——键盘用户看不到自己在哪")
    if not re.search(r"(?:button|\[disabled\]|:disabled)[^{}]*\{[^{}]*cursor\s*:\s*not-allowed", css_nc):
        errors.append("A8 禁用元素没有 cursor:not-allowed——看起来还能点")

    # ---- A10 双场别名必须整套切换 ----
    #
    # 双场系统的做法是：容器重定义整套简写别名，里面的规则一律写 var(--ink) 这种，
    # 于是同一份规则在纸面和暗场都对。**前提是那一套是完整的。**
    #
    # 消融实验查出来的：.sty 与 .kn 各切了 7 个，都缺 --press。
    # 而 --press 只有一个消费者（通用按下态 box-shadow:inset ... var(--press)），
    # 缺了之后暗场里按钮按下用的是纸面的按下色——A8 要求的三态反馈在幕里一直是错的，
    # 而 A9 查的是类名对账，查不到这个；缺一个变量也不会报错，只是声明静默失效。
    ALIAS = ("--ink", "--soft", "--gold", "--bad", "--line", "--card", "--on-gold", "--press")
    for m in re.finditer(r"([.#:][\w.\-#, :()\[\]=\"']+)\{([^}]*)\}", css_nc):
        body = m.group(2)
        got = [a for a in ALIAS if re.search(re.escape(a) + r"\s*:", body)]
        if len(got) < 3:
            continue          # 不是在切换一整个场
        miss = [a for a in ALIAS if a not in got]
        if miss:
            errors.append(
                f"A10 `{m.group(1).strip()[:40]}` 切换了 {len(got)} 个双场别名却缺 "
                f"{' '.join(miss)} —— 里面的规则会拿到**另一个场**的值，"
                "而缺一个 CSS 变量不会报错，只是声明被静默丢弃")
    if not any(e.startswith("A10") for e in errors):
        infos.append(f"A10 双场别名 每个切换整套别名的容器都齐了 {len(ALIAS)} 个 ✓")

    # ---- A9 死样式 ----
    # 「定义了但没有元素会用到」的类。翻正之后这种最多：一整块 CSS 还活着，
    # 它服务的那个 DOM 已经不存在了，于是改了没反应、删了没影响。
    defined = set()
    for m in re.finditer(r"([^{}]+)\{[^{}]*\}", re.sub(r"/\*.*?\*/", "", css_style_only, flags=re.S)):
        for sel in m.group(1).split(","):
            defined |= set(re.findall(r"\.([\w-]+)", sel))
    used = set()
    for m in re.finditer(r'class="([^"]*)"', html):
        # ${...} 里是 JS 表达式，不能整段当类名——否则
        # class="v ${consist==='匹配'?'g':'b'}" 会产出「匹配」这种假类名。
        # 但表达式里的**字符串字面量**恰恰就是动态拼上去的类名
        # （' broke' / 'g' / 'b'），所以挖掉表达式的同时把里面的字面量捞出来。
        # 这比维护一份白名单可靠：新加的动态类自动被认出来。
        seg = m.group(1)
        toks = []
        for expr in re.findall(r"\$\{([^}]*)\}", seg):
            for lit in re.findall(r"'([^']*)'|\"([^\"]*)\"", expr):
                toks += (lit[0] or lit[1]).split()
        toks += re.sub(r"\$\{[^}]*\}", " ", seg).split()
        for tok in toks:
            if re.fullmatch(r"[A-Za-z][\w-]*", tok):
                used.add(tok)
    for m in re.finditer(r"classList\.(?:add|remove|toggle)\(\s*['\"]([\w-]+)", html):
        used.add(m.group(1))
    for m in re.finditer(r"className\s*=\s*['\"]([\w -]+)", html):
        used |= set(m.group(1).split())
    # 状态类由 JS 动态拼接（`chipS ${st}`、ic(name,'ic-lg')），列进白名单
    DYNAMIC = {"on", "show", "done", "open", "lit", "locked", "due", "right", "wrong",
               "naf", "good", "slim", "ghost", "dim", "off", "tag", "ic-lg", "ic-s"}
    dead = sorted(defined - used - DYNAMIC)
    if dead:
        errors.append("A9 死样式：这些类在产物里没有任何元素会用到——"
                      "改了不会有反应，删了不会有影响：" + "、".join("." + d for d in dead))
    # 反向：用了却没定义。这一类是**静默失效**——元素长得不对，而没有任何东西会报错。
    # 比死代码更危险，因为死代码至少不影响用户看到的东西。
    UNSTYLED = {"num", "i", "v", "k", "t", "b", "w"}   # 纯语义标记，本就无样式
    ghost = sorted(used - defined - UNSTYLED - DYNAMIC)
    if ghost:
        errors.append("A9 用了却没定义的类——元素会静默地长得不对，没有任何东西会报错："
                      + "、".join("." + g for g in ghost))
    if not dead and not ghost:
        infos.append(f"A9 {len(defined)} 个类双向对账通过 ✓")

    for i in infos: print("INFO :", i)
    for w in warns: print("WARN :", w)
    for e in errors: print("ERROR:", e)
    print("A11Y:", "FAIL" if errors else "PASS")
    return 1 if errors else 0

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "dist" / "index.html"))
