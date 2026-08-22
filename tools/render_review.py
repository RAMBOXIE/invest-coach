#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审阅稿生成器：把 site.json 里已填的内容（教练、屏、题、混淆对、复训库）
渲染成可读 Markdown，供人工逐条审核（内容管线要求）。

用法: python tools/render_review.py  → 写入 docs/review/内容审阅_当前.md
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "ch1" / "site.json"
OUT = ROOT / "docs" / "review" / "内容审阅_当前.md"


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
    if q.get("hints"):
        out.append(f"{indent}提示①{q['hints'][0]} ②{q['hints'][1]} ③{q['hints'][2]}")
    if q.get("fb"):
        out.append(f"{indent}答后解释：{q['fb']}")
    return "\n".join(out)


def main():
    d = json.loads(CONTENT.read_text(encoding="utf-8"))
    L = [f"# 内容审阅稿（自动生成，勿手改）\n\n来源：`content/ch1/site.json`（{d.get('x_version', '')}）\n"]

    if d.get("x_coaches"):
        L.append("\n## 教练（人工逐条审核：无真人名入人格字段 / 无收益承诺 / 贴学派视角 / ≤40 字）\n")
        for c in d["x_coaches"]:
            L.append(f"\n### {c['name']}（{c['school']}）\n\n{c['intro']}\n")
            for ln in c.get("style_lines", []):
                L.append(f"- `{ln['when']}` {ln['t']}")

    L.append("\n## 节点内容（已填 screens 的节点）\n")
    for n in d.get("nodes", []):
        if not n.get("screens"):
            continue
        L.append(f"\n### {n['icon']} {n['name']}（`{n['id']}`，{n['domain']}·{n['age']}）\n")
        L.append(f"> {n['desc']}\n")
        for i, s in enumerate(n["screens"], 1):
            if "quiz" in s:
                L.append(f"\n**第 {i} 屏 · 题** <sub>covers={s.get('x_covers')}</sub>\n")
                L.append(render_quiz(s["quiz"]))
            else:
                L.append(f"\n**第 {i} 屏 · {s.get('h', '')}** <sub>covers={s.get('x_covers')}</sub>\n")
                L.append(strip_html(s.get("body", "")))
        if n.get("x_coach_notes"):
            L.append("\n**三声道点评（案例节点）**\n")
            for cid, note in n["x_coach_notes"].items():
                L.append(f"- **{cid}**：{note}")
        if n.get("x_pairs"):
            L.append("\n**混淆对**\n")
            for p in n["x_pairs"]:
                L.append(f"- `{p.get('id', '（缺id）')}` 表象：{p['look']}\n  - 红旗面：{p['a']}\n  - 无辜面：{p['b']}\n  - 区分线索：{p['key']}")

    if d.get("x_review_bank"):
        L.append("\n## 复训题库\n")
        for item in d["x_review_bank"]:
            L.append(f"\n### {item['pair_id']} · {item['side']} 面\n")
            L.append(render_quiz(item["quiz"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"审阅稿已生成: {OUT}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
