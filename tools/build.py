#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建器: content/ch1/site.json 注入 src/template.html 的 /*__DATA__*/null 占位符
→ dist/index.html（单文件交付物，file:// 双击可用）。内部先跑校验器，FAIL 即拒绝构建。

用法: python tools/build.py [--backend https://your-tunnel.example.com]
--backend 注入轻后端地址常量（模板改造后生效；未提供则前端保持降级态）。
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "ch1" / "site.json"
TPL = ROOT / "src" / "template.html"
OUT = ROOT / "dist" / "index.html"
DATA_MARKER = "/*__DATA__*/null"
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
    if tpl.count(DATA_MARKER) != 1:
        print(f"模板中占位符 {DATA_MARKER} 不是恰好一次")
        return 1

    data = json.loads(CONTENT.read_text(encoding="utf-8"))
    # 溯源徽标需要事实条目：把 facts.json 的 facts 按 id 注入 SITE.x_facts（只读展示用）
    fp = CONTENT.parent / "facts.json"
    if fp.exists():
        data["x_facts"] = {f["id"]: f for f in json.loads(fp.read_text(encoding="utf-8")).get("facts", [])}
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
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main(sys.argv[1:]))
