#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""体积与叙事预算门禁（SPEC_DEV.md §4）。

  B1 产物体积 ≤ tokens.budget.dist_kb
  B2 判断屏叙事预算：题干 ≤180 字（防叙事挤占判断认知资源）
  B3 离线契约：运行时不得依赖外部资源（出处外链除外）
  B4 预算一致：tokens.json 的 dist_kb 必须和 SPEC_DEV §4 表里写的数字一致
用法: python tools/check_budget.py [dist/index.html]
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOK = json.loads((ROOT / "design" / "tokens.json").read_text(encoding="utf-8"))
# 允许作为「出处外链」出现的域名（点击才跳转，不是资源加载）
CITE_HOSTS = ("sec.gov", "ifrs.org", "doi.org", "archive.org", "cfainstitute.org",
              "econometricsociety.org", "mhprofessional.com", "cia.gov", "jstor.org",
              "asc.fasb.org", "openlibrary.org")

def main(path):
    errors, infos = [], []
    p = pathlib.Path(path)
    if not p.exists():
        print(f"找不到 {p}")
        return 1

    kb = p.stat().st_size / 1024
    cap = TOK["budget"]["dist_kb"]
    msg = f"B1 产物体积 {kb:.1f}KB / 预算 {cap}KB"
    (infos if kb <= cap else errors).append(msg)

    # B4 预算一致。300 → 320 的放宽最初是**静默发生**的：文档写着「≤300KB（已裁决）」，
    # tokens.json 是 320，门禁按 320 跑，三份文档谁都没改。裁决被一个 json 字段悄悄推翻，
    # 而没有任何东西会喊一声。下一次要放宽必须再走一次裁决——这条负责喊那一声。
    spec = ROOT / "docs" / "SPEC_DEV.md"
    if spec.exists():
        m = re.search(r"`dist/index\.html`\s*\|[^|]*?(\d+)\s*KB", spec.read_text(encoding="utf-8"))
        if not m:
            errors.append("B4 在 docs/SPEC_DEV.md §4 里找不到 dist/index.html 的预算数字——"
                          "文档与令牌无法对账")
        elif int(m.group(1)) != cap:
            errors.append(f"B4 tokens.json 的 dist_kb={cap}，而 SPEC_DEV §4 写的是 "
                          f"{m.group(1)}KB——预算是 owner 裁决，不许靠改 json 悄悄放宽")
        else:
            infos.append(f"B4 预算 {cap}KB：令牌与 SPEC_DEV §4 一致 ✓")

    html = p.read_text(encoding="utf-8")

    # B2 判断屏叙事预算
    over = 0
    for m in re.finditer(r'"q":"((?:[^"\\]|\\.)*)"', html):
        q = m.group(1)
        if len(q) > 180:
            over += 1
            errors.append(f'B2 判断屏叙事超预算：题干 {len(q)} 字 > 180 字 —— 「{q[:26]}…」')
    if not over:
        infos.append("B2 全部题干 ≤180 字 ✓")

    # B3 离线契约：资源加载类属性只允许 data: / 相对路径
    bad = 0
    for m in re.finditer(r'(?:src|href)\s*=\s*"(https?://[^"]+)"', html):
        u = m.group(1)
        if not any(h in u for h in CITE_HOSTS):
            bad += 1
            errors.append(f"B3 疑似运行时外部依赖：{u[:70]}")
    if not bad:
        infos.append("B3 无运行时外部依赖（出处外链除外）✓")

    for i in infos:
        print("INFO :", i)
    for e in errors:
        print("ERROR:", e)
    print("BUDGET:", "FAIL" if errors else "PASS")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "dist" / "index.html"))
