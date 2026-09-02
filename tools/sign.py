#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""签字台 —— 人工审核（G1/G2）的工作台。

`validate --release` 会拒绝任何未签字的节点与幕。签字不是走形式：
LLM 起草的内容里曾经查出过 34 条出处问题，签字是这条防线的最后一道。

**但不要重做机器的活。** validate 的 26 条规则已经把 G1 的一半机械化了
（出处命中、类型闸、时代闸、数字必须绑账本、原档 sha256…）。
这个工具的作用是把「机器已经保证的」和「只有人能判断的」分开，
让你把注意力放在后者。

## 用法

    python tools/sign.py                      # 总览：谁签了 / 没签 / 过期
    python tools/sign.py --show rf1           # 打印一个节点的全部待审内容 + 清单
    python tools/sign.py --sign rf1 --by 名字  # 记录签字
    python tools/sign.py --show nikola-2021   # 幕同理（用 case_id）
    python tools/sign.py --sign nikola-2021 --by 名字

**没有 --sign-all。** 这是刻意的：读是一条一条读的，签字也就该一条一条签。

## 签字记录了什么

`x_prov.reviewed_by` / `reviewed_at` / `reviewed_hash`。
其中 hash 是内容指纹——**内容一改，签字自动过期**，validate 会报 ERROR 要求重审。
"""
import argparse
import datetime
import io
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "content" / "ch1" / "site.json"
STORIES = ROOT / "content" / "stories"

sys.path.insert(0, str(ROOT / "tools"))
import importlib.util
_spec = importlib.util.spec_from_file_location("_v", ROOT / "tools" / "validate.py")
_v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_v)

# 机器已经保证的——**不要在人工审核时重做这些**
MACHINE = [
    ("R4/R16", "canon.source 必须命中 sources[]，且精确到可复核的章节/页/条款号"),
    ("R14", "官方认定类主张只能挂官方认定档；准则类只能挂准则"),
    ("R15", "canon 提到的概念不得早于其出处年份（防时代错置）"),
    ("R12", "真实公司语境里的每个数字必须命中 facts.json 的数字账本"),
    ("R11b", "evidence/ 原档的 sha256 必须与账本一致（原档被改会当场报错）"),
    ("R17/R20", "深层节点必须有信心标注、三级提示、「无法判断」选项；答案键约束"),
    ("R8/R20", "混淆对必须 a/b 双面入库，且复训题的 pair 与外层一致"),
    ("R19", "教练台词的 canon_sources 必须命中 sources[]"),
    ("S6/S7", "幕：正文数字必须有出处；引文必须能在归档原档的引用行附近找到"),
    ("S7b/S7c", "幕：每条证词都有行锚或页锚；译文引文带英文原文，机器逐字核过"),
    ("R28", "账本里每个 accession 都有归档原档（例外必须写明理由）"),
    ("R31", "canon.formal 里没有我们自己的口吻——本站口径单列 canon.house，屏上分栏"),
    ("S9", "幕：reveal 之前不出现结局词"),
    ("C9/C13", "选项渲染打乱；「无法判断」90 处逐字一致；正确项最长的比例只许降"),
    ("C11", "每个错误选项都带 why + 分类法内的 mis"),
]

# 这一轮把 G1/G2 里机器能查的部分接走了，签字时只剩这四条要人判断。
HUMAN_LEFT = [
    "canon.formal 读起来是**教材的话**，不是我们自己总结的话（G1-1）",
    "归因链一句话说得完——读者能复述「为什么这个数字说明这件事」（G1-4）",
    "每个错误选项对应一个**真实的常见误解**（G2-1：机器只查了标注在不在，查不了标得对不对）",
    "混淆对的 key 真能区分 a/b —— 把 key 讲给别人听，他能据此分辨两侧（G2-3）",
]

# 只有人能判断的
G1 = [
    "canon.formal 读起来是**教材的话**，不是我们自己总结的话",
    "阈值类主张（「约 2 倍」「持续两年以上」这种）标了 L3「本站口径」，没有伪装成正典",
    "通篇没有前瞻信号、没有收益承诺、没有对某家公司「现在」的定性",
    "归因链一句话说得完——读者能复述「为什么这个数字说明这件事」",
    "真实公司的表述是**当年的**：用了当时的时态与当时可得的信息，没有后见之明",
]
G2 = [
    "每个错误选项对应一个**真实的常见误解**（不是凑数的荒谬选项）",
    "「无法判断」在该给满分的时候确实给满分，没有变成惩罚项",
    "混淆对的 key 真能区分 a/b —— 把 key 讲给别人听，他能据此分辨两侧",
    "题干里没有暗示答案的措辞（绝对化词、长度提示、语法配合）",
]


def load_nodes():
    d = json.loads(SITE.read_text(encoding="utf-8"))
    return d, {n["id"]: n for n in d["nodes"]}


def load_cases():
    out = {}
    for f in sorted(STORIES.glob("*/case.json")):
        out[f.parent.name] = (f, json.loads(f.read_text(encoding="utf-8")))
    return out


# 幕的指纹只有一份实现，在 validate.py。两处各写一份的时候，注释里写着
# 「改一处要改两处」——真到改的时候，靠的是有人记得读那句注释。
case_hash = _v.case_hash


def status(obj, h):
    pv = obj.get("x_prov") or {}
    if not pv.get("reviewed_by"):
        return "未签", ""
    if pv.get("reviewed_hash") != h:
        return "已过期", f"{pv['reviewed_by']} @ {pv.get('reviewed_at','?')}"
    return "已签", f"{pv['reviewed_by']} @ {pv.get('reviewed_at','?')}"


def cmd_list():
    _, nodes = load_nodes()
    cases = load_cases()
    rows = []
    for nid, n in nodes.items():
        if not n.get("screens"):
            continue          # 没有屏文案的节点不进签字门（R23 只对有 screens 的要求）
        st, who = status(n, _v.node_hash(n))
        rows.append(("节点", nid, st, who))
    for cid, (_, c) in cases.items():
        st, who = status(c, case_hash(c))
        rows.append(("幕", cid, st, who))
    todo = [r for r in rows if r[2] != "已签"]
    print(f"待签 {len(todo)} / 共 {len(rows)}\n")
    for kind, i, st, who in rows:
        mark = {"未签": "[ ]", "已过期": "[!]", "已签": "[x]"}[st]
        print(f"  {mark} {kind:2s} {i:18s} {st:4s} {who}")
    if todo:
        print(f"\n下一个：python tools/sign.py --show {todo[0][1]}")
    else:
        print("\n全部已签。可以跑 python tools/validate.py --release")


def show_text(o, depth=0, key=""):
    """把节点/幕里所有会被用户读到的文字摊平打印。"""
    pad = "  " * depth
    if isinstance(o, str):
        if o.strip():
            t = re.sub(r"<[^>]+>", "", o)
            print(f"{pad}{key}{t}")
    elif isinstance(o, dict):
        for k, v in o.items():
            if k in ("x_prov", "_note", "note", "x_id", "id", "kind", "fact", "x_covers"):
                continue
            if isinstance(v, str):
                show_text(v, depth, f"{k}: ")
            else:
                print(f"{pad}· {k}")
                show_text(v, depth + 1)
    elif isinstance(o, list):
        for v in o:
            show_text(v, depth)


def cmd_show(ident):
    _, nodes = load_nodes()
    cases = load_cases()
    if ident in nodes:
        obj, h, kind = nodes[ident], _v.node_hash(nodes[ident]), "节点"
    elif ident in cases:
        obj, h, kind = cases[ident][1], case_hash(cases[ident][1]), "幕"
    else:
        print(f"找不到「{ident}」。跑 python tools/sign.py 看清单")
        return 1
    st, who = status(obj, h)
    print("=" * 78)
    print(f"{kind}  {ident}   [{st}] {who}")
    print(f"内容指纹 {h}")
    print("=" * 78)
    print("\n【机器已经保证的 —— 不用你再查一遍】")
    for rid, desc in MACHINE:
        print(f"  ✓ {rid:9s} {desc}")
    print("\n【只有你能判断的 —— 这一版只剩四条】")
    for i, x in enumerate(HUMAN_LEFT, 1):
        print(f"    {i}. {x}")
    print("\n  （G1 五条 / G2 四条的全文见下；带 → 的已由门禁接管）")
    cover = {1: "R31 已挡「我们的口吻」混进 canon.formal",
             2: "R31 + canon.house：本站口径单列一栏，屏上标明「这一段不是出处的话」",
             3: "C7 已挡前瞻信号 / 荐股 / 收益承诺",
             5: "S9 已挡 reveal 之前出现结局词（当年视角不被剧透）"}
    for i, x in enumerate(G1, 1):
        print(f"    G1-{i} {x}")
        if i in cover:
            print(f"         → {cover[i]}")
    cov2 = {1: "C11 已挡「没有标注」；标得对不对仍归你",
            2: "R22 已统计「无法判断」为正确答案的占比（现 20%，目标 20–30%）",
            4: "C9 挡位置、C13 挡长度与「无法判断」文案差异"}
    for i, x in enumerate(G2, 1):
        print(f"    G2-{i} {x}")
        if i in cov2:
            print(f"         → {cov2[i]}")
    print("\n" + "─" * 78)
    print("待审内容全文：")
    print("─" * 78)
    show_text(obj)
    print("\n" + "─" * 78)
    print(f"读完且认可 → python tools/sign.py --sign {ident} --by 你的名字")
    print(f"发现问题   → 先改内容，改完指纹会变，再回来签")
    return 0


def cmd_void(reason):
    """把所有**已过期**的签字清空，恢复成「未签」。

    内容改了之后签字自动过期，validate 会报 ERROR 挡住构建。这时有两条路：
    重签，或者承认这份内容需要重新审。**内容实质变了就该走后者**——
    重签等于替审阅人断言他看过他没看过的东西，而这套机制存在的全部理由
    就是挡住这件事。

    过期（[!]）与未签（[ ]）在门禁里待遇不同：过期是 ERROR（构建被挡），
    未签是 WARN（只挡 --release）。作废之后可以继续开发，定版前必须重审。
    """
    d = json.loads(SITE.read_text(encoding="utf-8"))
    n = 0
    for node in d["nodes"]:
        if not node.get("screens"):
            continue
        st, _ = status(node, _v.node_hash(node))
        if st == "已过期":
            pv = node["x_prov"]
            pv["reviewed_by"] = pv["reviewed_at"] = pv["reviewed_hash"] = ""
            n += 1
    SITE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    for f, c in load_cases().items():
        pass
    cases = load_cases()
    for cid, (f, c) in cases.items():
        st, _ = status(c, case_hash(c))
        if st == "已过期":
            pv = c["x_prov"]
            pv["reviewed_by"] = pv["reviewed_at"] = pv["reviewed_hash"] = ""
            f.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
            n += 1
    print(f"作废 {n} 条已过期的签字：{reason}")
    print("现在它们是「未签」——构建不再被挡，但 --release 仍然拒绝定版。")
    return 0


def cmd_sign(ident, by):
    _, nodes = load_nodes()
    cases = load_cases()
    today = datetime.date.today().isoformat()
    if ident in nodes:
        d = json.loads(SITE.read_text(encoding="utf-8"))
        n = next(x for x in d["nodes"] if x["id"] == ident)
        h = _v.node_hash(n)
        pv = n.setdefault("x_prov", {})
        pv["reviewed_by"], pv["reviewed_at"], pv["reviewed_hash"] = by, today, h
        SITE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    elif ident in cases:
        f, c = cases[ident]
        h = case_hash(c)
        pv = c.setdefault("x_prov", {})
        pv.setdefault("drafted_by", "llm")
        pv.setdefault("model", "claude-opus-5")
        pv.setdefault("drafted_at", "2026-08-26")
        pv["reviewed_by"], pv["reviewed_at"], pv["reviewed_hash"] = by, today, h
        f.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        print(f"找不到「{ident}」")
        return 1
    print(f"已签：{ident} ← {by} @ {today}（指纹 {h}）")
    print("提醒：这份内容之后任何改动都会让这个签字过期，validate 会要求重审。")
    return 0


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--show", metavar="ID")
    ap.add_argument("--sign", metavar="ID")
    ap.add_argument("--by", metavar="名字")
    ap.add_argument("--void", metavar="理由",
                    help="把已过期的签字清空成未签（内容实质变了，需要重新审）")
    a = ap.parse_args()
    if a.void:
        return cmd_void(a.void)
    if a.show:
        return cmd_show(a.show)
    if a.sign:
        if not a.by:
            print("签字必须带 --by 名字。这是要记进内容文件的。")
            return 1
        return cmd_sign(a.sign, a.by)
    cmd_list()
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
