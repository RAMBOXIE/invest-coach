#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性：导出全部错误选项供标注 why/mis，再把标注写回。

导出   python tools/_archive/oneoff/20260902-annotate-opts.py export <目录>
写回   python tools/_archive/oneoff/20260902-annotate-opts.py apply  <结果.json>

结果格式：{"<选项路径>": {"why": "...", "mis": "<误解id>"}, ...}
写回时逐条校验路径存在、选项文本未变、mis 在分类法里，任一不符整体拒绝。
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
SITE = ROOT / "content" / "ch1" / "site.json"
MIS = ROOT / "content" / "ch1" / "misconceptions.json"


def walk_quizzes(d):
    """产出 (路径前缀, quiz)。路径能唯一定位到 site.json 里的那个 quiz。"""
    for i, n in enumerate(d["nodes"]):
        for j, sc in enumerate(n.get("screens", [])):
            if sc.get("quiz"):
                yield f"nodes[{i}].screens[{j}].quiz", sc["quiz"], n["id"], n["name"]
    for k, it in enumerate(d.get("x_review_bank", [])):
        if it.get("quiz"):
            yield f"x_review_bank[{k}].quiz", it["quiz"], it.get("pair_id", "?"), "复习题"


def collect():
    d = json.loads(SITE.read_text(encoding="utf-8"))
    out = {}
    for prefix, q, owner, name in walk_quizzes(d):
        for oi, o in enumerate(q.get("opts", [])):
            if o.get("ok"):
                continue
            out[f"{prefix}.opts[{oi}]"] = {
                "所属": f"{owner}（{name}）",
                "题干": q.get("q", ""),
                "正确选项": [x.get("t") for x in q["opts"] if x.get("ok")],
                "这个错误选项": o.get("t", ""),
                "是无法判断项": bool(o.get("na")),
                "现有答后解释": q.get("fb", ""),
            }
    return d, out


def get_at(doc, path):
    toks = re.findall(r"([A-Za-z_]\w*)|\[(\d+)\]", path)
    cur = doc
    for k, i in toks:
        cur = cur[k] if k else cur[int(i)]
    return cur


def cmd_export(outdir):
    _, items = collect()
    dd = pathlib.Path(outdir)
    dd.mkdir(parents=True, exist_ok=True)
    (dd / "_all.json").write_text(json.dumps(items, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
    # 按所属节点分片，让每片语境连贯
    groups = {}
    for p, v in items.items():
        g = "bank" if p.startswith("x_review_bank") else v["所属"].split("（")[0]
        groups.setdefault(g, {})[p] = v
    # bank 太大，再切三份
    if "bank" in groups and len(groups["bank"]) > 30:
        b = groups.pop("bank")
        keys = list(b)
        n = (len(keys) + 2) // 3
        for i in range(3):
            groups[f"bank{i}"] = {k: b[k] for k in keys[i * n:(i + 1) * n]}
    for g, v in sorted(groups.items()):
        (dd / f"{g}.json").write_text(json.dumps(v, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print(f"导出 {len(items)} 个错误选项 → {dd}")
    for g, v in sorted(groups.items()):
        print(f"  {g:20s} {len(v):3d} 个")


def cmd_apply(resfile):
    res = json.loads(pathlib.Path(resfile).read_text(encoding="utf-8"))
    base = json.loads((pathlib.Path(resfile).parent / "_all.json").read_text(encoding="utf-8"))
    valid = {m["id"] for m in json.loads(MIS.read_text(encoding="utf-8"))["items"]}
    d = json.loads(SITE.read_text(encoding="utf-8"))
    bad = []
    for p, v in res.items():
        if p not in base:
            bad.append(f"未知路径 {p}")
            continue
        try:
            o = get_at(d, p)
        except Exception as e:
            bad.append(f"定位失败 {p}: {e}")
            continue
        if o.get("t") != base[p]["这个错误选项"]:
            bad.append(f"选项文本已变（有人先改过）{p}")
        if o.get("ok"):
            bad.append(f"{p} 是正确选项，不该标 why/mis")
        if not isinstance(v, dict) or not v.get("why") or not v.get("mis"):
            bad.append(f"{p} 缺 why 或 mis")
            continue
        if v["mis"] not in valid:
            bad.append(f"{p} 的 mis「{v['mis']}」不在分类法里")
        if len(v["why"]) > 80:
            bad.append(f"{p} 的 why 过长（{len(v['why'])} 字，上限 80）")
    if bad:
        print(f"拒绝写回，{len(bad)} 处不合格：")
        for b in bad[:15]:
            print("  ", b)
        return 1
    for p, v in res.items():
        o = get_at(d, p)
        o["why"] = v["why"]
        o["mis"] = v["mis"]
    SITE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"写回 {len(res)} 个选项的 why/mis")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    if sys.argv[1] == "export":
        cmd_export(sys.argv[2])
        sys.exit(0)
    sys.exit(cmd_apply(sys.argv[2]))
