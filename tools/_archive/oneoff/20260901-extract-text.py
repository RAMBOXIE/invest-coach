#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性：把用户可读文案按 JSON 路径导出成分片，供文风重写；再把改写结果按路径写回。

导出   python tools/_archive/oneoff/20260901-extract-text.py export <输出目录>
写回   python tools/_archive/oneoff/20260901-extract-text.py apply  <改写结果.json>

改写结果格式：{"路径": "新文本", ...}。写回时逐条校验路径存在且原值仍是导出时那一份，
不一致就整体拒绝——避免两次改写互相覆盖。
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
SITE = ROOT / "content" / "ch1" / "site.json"
STORIES = ROOT / "content" / "stories"

# 不改：内部 id、机器字段、出处、正典（教材原话）、逐字引文
SKIP = {
    "id", "x_id", "case_id", "pair_id", "kind", "x_kind", "type", "fact", "src",
    "line", "accession", "sha256", "url", "x_covers", "x_anchors", "x_pair",
    "knowledge_node", "twin_case_ref", "side", "icon", "avatar", "x_version",
    "cv", "era", "status", "verdict", "_note", "note", "x_note", "x_prov",
    "sources", "source", "textbook", "x_cite", "canon", "quote", "text",
    "x_facts", "provenance",
}


def walk(obj, path, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in SKIP:
                continue
            walk(v, f"{path}.{k}", out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, f"{path}[{i}]", out)
    elif isinstance(obj, str) and obj.strip():
        out[path] = obj


def collect():
    out = {}
    walk(json.loads(SITE.read_text(encoding="utf-8")), "site", out)
    for f in sorted(STORIES.glob("*/case.json")):
        walk(json.loads(f.read_text(encoding="utf-8")), f"story:{f.parent.name}", out)
    return out


def get_root(path):
    if path.startswith("story:"):
        name = path.split(".", 1)[0][6:]
        return STORIES / name / "case.json", path.split(".", 1)[1]
    return SITE, path.split(".", 1)[1]


def set_at(doc, path, value):
    """按 a.b[0].c 定位并赋值。"""
    import re
    toks = re.findall(r"([A-Za-z_][\w]*)|\[(\d+)\]", path)
    cur = doc
    keys = [(k or int(i)) for k, i in toks]
    for k in keys[:-1]:
        cur = cur[k]
    cur[keys[-1]] = value


def get_at(doc, path):
    import re
    toks = re.findall(r"([A-Za-z_][\w]*)|\[(\d+)\]", path)
    cur = doc
    for k, i in toks:
        cur = cur[k] if k else cur[int(i)]
    return cur


def cmd_export(outdir):
    items = collect()
    d = pathlib.Path(outdir)
    d.mkdir(parents=True, exist_ok=True)
    (d / "_all.json").write_text(json.dumps(items, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    # 按顶层归属分片，让每个分片内部语境连贯
    groups = {}
    for p, t in items.items():
        if p.startswith("story:"):
            g = p.split(".", 1)[0]
        elif ".nodes[" in p:
            g = "node" + p.split(".nodes[")[1].split("]")[0].rjust(2, "0")
        elif ".x_review_bank[" in p:
            n = int(p.split(".x_review_bank[")[1].split("]")[0])
            g = f"bank{n // 8}"
        else:
            g = "top"
        groups.setdefault(g, {})[p] = t
    for g, v in sorted(groups.items()):
        (d / f"{g}.json").write_text(json.dumps(v, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    chars = sum(len(t) for t in items.values())
    print(f"导出 {len(items)} 条 / {chars} 字 → {d}")
    for g, v in sorted(groups.items()):
        print(f"  {g:22s} {len(v):4d} 条 {sum(len(t) for t in v.values()):6d} 字")


def cmd_apply(resfile):
    res = json.loads(pathlib.Path(resfile).read_text(encoding="utf-8"))
    base = json.loads((pathlib.Path(resfile).parent / "_all.json").read_text(encoding="utf-8"))
    docs, bad = {}, []
    for p, new in res.items():
        if p not in base:
            bad.append(f"未知路径 {p}")
            continue
        f, rel = get_root(p)
        if f not in docs:
            docs[f] = json.loads(f.read_text(encoding="utf-8"))
        try:
            cur = get_at(docs[f], rel)
        except Exception as e:
            bad.append(f"定位失败 {p}: {e}")
            continue
        if cur != base[p]:
            bad.append(f"原值已变（有人先改过）{p}")
    if bad:
        print(f"拒绝写回，{len(bad)} 处不一致：")
        for b in bad[:12]:
            print("  ", b)
        return 1
    n = 0
    for p, new in res.items():
        f, rel = get_root(p)
        if new != base[p]:
            set_at(docs[f], rel, new)
            n += 1
    for f, doc in docs.items():
        f.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"写回 {n} 处改动，涉及 {len(docs)} 个文件")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    if sys.argv[1] == "export":
        sys.exit(cmd_export(sys.argv[2]) or 0)
    sys.exit(cmd_apply(sys.argv[2]))
