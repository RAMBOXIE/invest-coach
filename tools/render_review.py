#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审阅稿生成器 —— 把要签字的东西摊成一份能从头读到尾的文档。

`tools/sign.py` 是命令行签字台：一条一条 `--show`，一条一条 `--sign`。
但**读**这件事不该被命令行分成 18 次。这个脚本把同样的内容渲染成一份
Markdown，你从头读到尾，在每条末尾写「过」或写下问题，然后一次性交回。

    python tools/render_review.py            # → build/review/签字审阅稿.md
    python tools/render_review.py --content  # → build/review/内容审阅_当前.md（旧的纯内容稿）

判据（机器已保证的 / 只有人能判断的）从 sign.py 读，不在这里重抄一遍——
两处各写一份清单，迟早会对不上。
"""
import argparse
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "ch1" / "site.json"
STORIES = ROOT / "content" / "stories"
OUT_SIGN = ROOT / "build" / "review" / "签字审阅稿.md"
OUT_CONTENT = ROOT / "build" / "review" / "内容审阅_当前.md"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_sign = _load("_sign", ROOT / "tools" / "sign.py")
_v = _load("_v", ROOT / "tools" / "validate.py")


def strip_html(s):
    s = re.sub(r"<summary>(.*?)</summary>", r"【点开】\1 → ", s)
    s = re.sub(r"</p>\s*<p[^>]*>", "\n", s)
    s = re.sub(r"<tr[^>]*>", "\n| ", s)
    s = re.sub(r"</t[dh]>\s*<t[dh][^>]*>", " | ", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def render_quiz(q, indent=""):
    out = [f"{indent}**题**：{q.get('q', '')}"]
    for o in q.get("opts", []):
        mark = "✅" if o.get("ok") else "❌"
        na = "（无法判断选项）" if o.get("na") else ""
        out.append(f"{indent}- {mark} {o.get('t', '')}{na}")
    meta = []
    if q.get("x_kind"):
        meta.append(f"kind={q['x_kind']}")
    if q.get("confidence"):
        meta.append("信心三档")
    if q.get("x_pair"):
        meta.append(f"pair={q['x_pair']}")
    if meta:
        out.append(f"{indent}<sub>{' ｜ '.join(meta)}</sub>")
    for i, h in enumerate(q.get("hints", []), 1):
        out.append(f"{indent}提示{i}：{h}")
    if q.get("fb"):
        out.append(f"{indent}答后解释：{q['fb']}")
    return "\n".join(out)


# ────────────────────────── 节点 ──────────────────────────
def render_node(n, bank):
    L = [f"> {n['desc']}\n"]
    if n.get("canon"):
        c = n["canon"]
        L.append("**正典（G1 第 1 条盯这里：读起来是不是教材的话）**\n")
        L.append(f"- 术语：{c.get('term', '')}")
        L.append(f"- 正式表述：{c.get('formal', '')}")
        L.append(f"- 出处：{c.get('source', '')} ｜ {c.get('textbook', '')}")
        if c.get("x_cite"):
            L.append(f"- 定位：{c['x_cite']}")
        L.append("")
    for i, s in enumerate(n.get("screens", []), 1):
        if "quiz" in s:
            L.append(f"**第 {i} 屏 · 题** <sub>covers={s.get('x_covers')}</sub>\n")
            L.append(render_quiz(s["quiz"]) + "\n")
        else:
            L.append(f"**第 {i} 屏 · {s.get('h', '')}** <sub>covers={s.get('x_covers')}</sub>\n")
            L.append(strip_html(s.get("body", "")) + "\n")
    if n.get("x_coach_notes"):
        L.append("**教练点评**\n")
        for cid, note in n["x_coach_notes"].items():
            L.append(f"- **{cid}**：{note}")
        L.append("")
    if n.get("x_pairs"):
        L.append("**混淆对（G2 第 3 条盯这里：key 讲给别人听，他能不能据此分辨两侧）**\n")
        for p in n["x_pairs"]:
            L.append(f"- `{p.get('id', '（缺id）')}` 表象：{p['look']}")
            L.append(f"  - A 面：{p['a']}")
            L.append(f"  - B 面：{p['b']}")
            L.append(f"  - **区分线索**：{p['key']}")
        L.append("")
    anchors = [a for a in n.get("x_anchors", [])]
    if anchors:
        L.append(f"**闭卷锚题池（{len(anchors)} 道，点亮全靠它）**\n")
        for aid in anchors:
            q = bank.get(aid)
            if q:
                L.append(render_quiz(q) + "\n")
            else:
                L.append(f"- ⚠ 题库里找不到 `{aid}`\n")
    return "\n".join(L)


# ────────────────────────── 幕 ──────────────────────────
def render_case(c):
    L = [f"> **{c.get('subtitle', '')}**\n>\n> {c.get('hook', '')}\n"]
    L.append(f"挂在知识点：`{c.get('knowledge_node', '?')}`"
             + (f" ｜ 负样本：`{c['twin_case_ref']}`" if c.get("twin_case_ref") else "") + "\n")
    if c.get("cast"):
        L.append("**人物（G1 第 5 条盯这里：口吻是不是当年的，有没有后见之明）**\n")
        for p in c["cast"]:
            L.append(f"- **{p.get('name', '')}**（{p.get('role', '')}）：{p.get('intro', '')}")
            if p.get("rule"):
                L.append(f"  - 台词纪律：{p['rule']}")
        L.append("")
    for b in c.get("beats", []):
        L.append(f"---\n\n**[{b.get('kind', '')}] {b.get('eyebrow', '')} · {b.get('title', '')}**\n")
        for ln in b.get("lines", []):
            L.append(ln)
        if b.get("panel"):
            p = b["panel"]
            L.append("\n| " + " | ".join([""] + p.get("cols", [])) + " |")
            L.append("|" + "---|" * (len(p.get("cols", [])) + 1))
            for r in p.get("rows", []):
                flag = " 🚩" if r.get("flagA") or r.get("flagB") else ""
                L.append(f"| {r.get('k', '')} | {r.get('a', '')} | {r.get('b', '')}{flag} |"
                         if len(p.get("cols", [])) == 2 else
                         f"| {r.get('k', '')} | {r.get('a', '')} |")
        for d in b.get("derived", []):
            L.append(f"\n- 推导：**{d.get('k')} = {d.get('v')}**（绑 `{d.get('fact')}`）")
        if b.get("prompt"):
            L.append(f"\n判断题：{b['prompt']}")
        for o in b.get("options", []):
            tag = f"[{o.get('verdict') or ('✅' if o.get('ok') else '❌')}]"
            L.append(f"- {tag} {o.get('t', '')}")
        if b.get("question"):
            L.append(f"\n{b['question']}")
        if b.get("quote"):
            q = b["quote"]
            L.append(f"\n> 原档逐字：「{q.get('text', '')}」\n> —— {q.get('src', '')} {q.get('line', '')}")
        if b.get("canon"):
            L.append(f"\n**当年原档说了什么**：{b['canon'].get('t', '')}\n\n{b['canon'].get('detail', '')}")
        for k in b.get("knowhow", []):
            L.append(f"- {k}")
        if b.get("rule"):
            L.append(f"\n**判据**：{b['rule']}（标签「{b.get('label', '')}」）")
        if b.get("boundary"):
            L.append(f"\n**边界**：{b['boundary']}")
        if b.get("fb"):
            L.append(f"\n答后解释：{b['fb']}")
        if b.get("narration"):
            L.append(f"\n*{b['narration']}*")
        L.append("")
    return "\n".join(L)


# ────────────────────────── 签字审阅稿 ──────────────────────────
def build_sign_doc():
    d = json.loads(CONTENT.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in d["nodes"] if n.get("screens")}
    bank = {it["quiz"]["x_id"]: it["quiz"] for it in d.get("x_review_bank", [])
            if it.get("quiz", {}).get("x_id")}
    cases = _sign.load_cases()

    items = ([("节点", i, n, _v.node_hash(n)) for i, n in nodes.items()]
             + [("幕", i, c, _sign.case_hash(c)) for i, (_, c) in cases.items()])
    todo = [x for x in items if _sign.status(x[2], x[3])[0] != "已签"]

    L = [f"# 签字审阅稿 · 共 {len(items)} 条（待签 {len(todo)}）\n",
         "> 自动生成，勿手改。改内容请改 `content/`，然后重跑本脚本。\n",
         "## 怎么用这份文档\n",
         "从头读到尾。每一条末尾有一行「**判定：**」，读完在后面写「过」，"
         "或者写下你认为有问题的地方。全部读完，把结论一次性交回，"
         "我按你的判定逐条执行 `sign.py --sign`（有问题的先改内容再签）。\n",
         "**签字绑内容指纹。** 签完之后那条内容的任何改动都会让签字自动过期，"
         "`validate` 会报 ERROR 要求重审——这是签字有意义的前提。\n",
         "---\n",
         "## 【机器已经保证的 —— 不用你再查一遍】\n"]
    for rid, desc in _sign.MACHINE:
        L.append(f"- **{rid}** {desc}")
    L.append("\n此外 `check_coach.py` 的 C1–C8 保证教练闭环成立"
             "（诊断→处方回流、判分不经 LLM、点亮唯一入口是闭卷锚题、"
             "过度自信有行为后果、无买卖建议）。\n")
    L.append("## 【只有你能判断的 —— 这份文档就是为这 9 条准备的】\n")
    L.append("**G1 内容与出处**\n")
    for i, x in enumerate(_sign.G1, 1):
        L.append(f"{i}. {x}")
    L.append("\n**G2 题目**\n")
    for i, x in enumerate(_sign.G2, 1):
        L.append(f"{i}. {x}")
    L.append("\n> 其中 G2 第 1 条（错误选项是否对应真实的常见误解）机器**测不了**——"
             "试过查纠错词、查字符重合度两种判据都不成立，"
             "中文里回应一个选项不需要复述它的字面。这条完全靠你。\n")

    L.append("\n---\n\n# 待审内容\n")
    for kind, ident, obj, h in items:
        st, who = _sign.status(obj, h)
        mark = {"未签": "☐", "已过期": "⚠", "已签": "☑"}[st]
        title = obj.get("name") or obj.get("title") or ident
        L.append(f"\n## {mark} {kind}· {title} `{ident}`\n")
        L.append(f"<sub>指纹 `{h}` ｜ 状态 {st} {who}</sub>\n")
        L.append(render_case(obj) if kind == "幕" else render_node(obj, bank))
        L.append(f"\n**判定：**　　（写「过」，或写下问题）\n\n---")

    OUT_SIGN.parent.mkdir(parents=True, exist_ok=True)
    OUT_SIGN.write_text("\n".join(L) + "\n", encoding="utf-8")
    kb = OUT_SIGN.stat().st_size / 1024
    print(f"签字审阅稿已生成: {OUT_SIGN}（{kb:.0f} KB，{len(items)} 条，待签 {len(todo)}）")
    return 0


# ────────────────────────── 旧的纯内容稿 ──────────────────────────
def build_content_doc():
    d = json.loads(CONTENT.read_text(encoding="utf-8"))
    bank = {it["quiz"]["x_id"]: it["quiz"] for it in d.get("x_review_bank", [])
            if it.get("quiz", {}).get("x_id")}
    L = [f"# 内容审阅稿（自动生成，勿手改）\n\n来源：`content/ch1/site.json`（{d.get('x_version', '')}）\n"]
    if d.get("x_coaches"):
        L.append("\n## 教练\n")
        for c in d["x_coaches"]:
            L.append(f"\n### {c['name']}（{c.get('school', '')}）\n\n{c.get('intro', '')}\n")
            for ln in c.get("style_lines", []):
                L.append(f"- `{ln['when']}` {ln['t']}")
    L.append("\n## 节点内容\n")
    for n in d.get("nodes", []):
        if not n.get("screens"):
            continue
        L.append(f"\n### {n['icon']} {n['name']}（`{n['id']}`，{n['domain']}·{n['age']}）\n")
        L.append(render_node(n, bank))
    if d.get("x_review_bank"):
        L.append("\n## 复训题库\n")
        for item in d["x_review_bank"]:
            L.append(f"\n### {item['pair_id']} · {item['side']} 面\n")
            L.append(render_quiz(item["quiz"]))
    OUT_CONTENT.parent.mkdir(parents=True, exist_ok=True)
    OUT_CONTENT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"内容审阅稿已生成: {OUT_CONTENT}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--content", action="store_true", help="生成旧的纯内容稿")
    a = ap.parse_args()
    return build_content_doc() if a.content else build_sign_doc()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
