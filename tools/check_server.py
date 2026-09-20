#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""后端门禁 —— 把隐私承诺跑一遍，而不是读一遍。

D3 裁决的三件事全在 server/server.py 里：按语境打码、**在送模型之前**打码、
90 天留存。D9 记的是「另一份实现（Go 版）没有这三样」。

这道门禁的存在理由：那三件事此前**从来没被执行过一次**。
代码在那儿、注释写得很清楚、没有任何东西跑过它。而这个仓库最常见的失败
就是「看着对、其实永远不生效」——打码正则里一个被 heredoc 折掉的转义
就足以让 $AAPL 原样进模型，而所有门禁都是绿的（实测发生过）。

  P1 打码分语境：持仓金额/代码/联系方式打掉，分析数字保留
  P2 出口检查：模型输出里出现材料里没有的数字，或越界措辞，整条丢弃
  P3 留存：超过 RETAIN_DAYS 的记录会被真的删掉
  P4 Origin 收口：不在白名单的来源拿不到 ACAO 头，直接 403
  P5 顺序：打码发生在**调用模型之前**，不只是入库之前

用法: python tools/check_server.py [--selftest]
"""
import importlib.util
import json
import os
import pathlib
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
ALLOW = "https://coach.example.com,null"


def load():
    """带着测试用的环境变量导入 server.py（它在 import 期读 env）。"""
    tmp = pathlib.Path(tempfile.gettempdir()) / "ic-gate.db"
    if tmp.exists():
        tmp.unlink()
    os.environ["ALLOWED_ORIGINS"] = ALLOW
    os.environ["DB_PATH"] = str(tmp)
    os.environ.pop("CLAUDE_API_KEY", None)
    spec = importlib.util.spec_from_file_location("ic_server", ROOT / "server" / "server.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m, tmp


def p1_mask(S, errors):
    keep = "应收增速 38.5%，比收入的 18.7% 快了将近一倍，DSO 从 36 天涨到 92 天"
    got, n = S.mask_pii(keep)
    if got != keep or n:
        errors.append(f"P1 分析数字被打掉了（打了 {n} 处）：{got}")
    cases = [
        ("我持仓 50 万，成本 12 块，现在亏了 8 万", ("[金额]",), ("50 万", "8 万")),
        ("我买了 600519，还有 $AAPL 和 HK00700", ("[代码]",), ("600519", "$AAPL")),
        ("加我微信 abc12345，邮箱 me@example.com，手机 13800138000",
         ("[联系方式]", "[邮箱]", "[手机]"), ("abc12345", "me@example.com", "13800138000")),
    ]
    for text, must, gone in cases:
        got, n = S.mask_pii(text)
        for tok in must:
            if tok not in got:
                errors.append(f"P1 该出现的替换 {tok} 没出现：{got}")
        for tok in gone:
            if tok in got:
                errors.append(f"P1 「{tok}」没被打掉：{got}")


def p2_exit_gate(S, errors):
    material = "收入 1,168.2，应收 295.6，增速 18.7%"
    ok_text = "你抓到了应收比收入快这一点，18.7% 那个数字用对了。下一步缺的是现金流那一栏。"
    if S.check_note(ok_text, material)[0] is None:
        errors.append("P2 合格的回应被误杀")
    for bad, why in (
        ("应收增速其实是 72.4%，你算错了。", "材料里没有的数字"),
        ("这家公司现在建议买入。", "越界措辞"),
        ("目标价 30 元。", "越界措辞"),
    ):
        text, reason = S.check_note(bad, material)
        if text is not None:
            errors.append(f"P2 该丢弃的没丢（{why}）：{bad}")


def p3_retention(S, errors):
    d = S.db()
    if d is None:
        errors.append("P3 落库没打开，留存没法验")
        return
    now = int(time.time())
    d.execute("INSERT INTO notes(node, trace, at) VALUES(?,?,?)", ("old", "{}", now - (S.RETAIN_DAYS + 1) * 86400))
    d.execute("INSERT INTO notes(node, trace, at) VALUES(?,?,?)", ("new", "{}", now))
    d.commit()
    S.purge_old()
    left = {r[0] for r in d.execute("SELECT node FROM notes").fetchall()}
    if "old" in left:
        errors.append(f"P3 超过 {S.RETAIN_DAYS} 天的记录没被删掉")
    if "new" not in left:
        errors.append("P3 把没过期的记录一起删了")


def serve(S):
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), S.H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, srv.server_address[1]


def hit(port, path, origin, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    if origin is not None:
        req.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def p4_origin(S, port, errors):
    code, hdr, _ = hit(port, "/health", "https://coach.example.com")
    if code != 200 or hdr.get("Access-Control-Allow-Origin") != "https://coach.example.com":
        errors.append(f"P4 白名单里的来源被挡了：{code} {hdr.get('Access-Control-Allow-Origin')}")
    code, hdr, _ = hit(port, "/health", "https://evil.example.com")
    if code != 403:
        errors.append(f"P4 白名单外的来源没被挡：{code}")
    if hdr.get("Access-Control-Allow-Origin"):
        errors.append("P4 白名单外的来源拿到了 ACAO 头")
    code, hdr, _ = hit(port, "/health", "null")
    if code != 200:
        errors.append(f"P4 显式写进白名单的 null（file:// 打开的产物）被挡了：{code}")


def p5_order(S, port, errors):
    """打码必须在**调用模型之前**。

    只在入库前打码，等于用户的持仓与联系方式已经进过第三方模型了；
    那时候再打码只是让我们自己的库好看。这条把 review_note 换成一个探针，
    看服务端到底把什么交给了模型那一层。
    """
    seen = {}

    def probe(note, material):
        seen["note"] = note
        return "收到。", {"raw": "收到。", "kept": True}

    S.API_KEY = "test-key-not-used"          # 让请求走到 review 分支
    real, S.review_note = S.review_note, probe
    try:
        body = json.dumps({"note": "我持仓 50 万，手机 13800138000，应收增速 38.5%",
                           "material": "应收增速 38.5%", "node": "rf1"}).encode()
        code, _, out = hit(port, "/api/v1/review-note", "null", body)
    finally:
        S.review_note = real
        S.API_KEY = ""
    got = seen.get("note")
    if got is None:
        errors.append(f"P5 请求没走到模型那一层（{code} {out[:80]}）")
        return
    if "13800138000" in got or "50 万" in got:
        errors.append(f"P5 送给模型的文本里还有原始 PII：{got}")
    if "38.5%" not in got:
        errors.append(f"P5 分析数字在送模型前被打掉了：{got}")


def p6_discuss_gate(S, errors):
    """决策人那段话的出口检查：他活在当年，说不出结局；数字只能来自材料；不荐股；不出戏。"""
    material = "1997 年净销售额 11.682 亿美元，较 1996 年增长 18.7%。应收账款 2.956 亿美元。"
    ok_text = "增长来自五个产品类别的全线增长。1997 年应收上升，源于销售增加和某些季节性账期条款。"
    if S.check_discuss(ok_text, material, 1998)[0] is None:
        errors.append("P6 合格的回应被误杀")
    for bad, why in (
        ("后来 SEC 认定这一年有舞弊。", "后见之明"),
        ("应收其实涨了 38.5%。", "材料里没有的数字"),
        ("这家公司现在值得买。", "投资建议"),
        ("作为 AI，我无法替他回答。", "出戏"),
    ):
        if S.check_discuss(bad, material, 1998)[0] is not None:
            errors.append(f"P6 该丢弃的没丢（{why}）：{bad}")


def p7_discuss_wiring(S, port, errors):
    """端点接线 + 打码先于调模型 + 人物与材料原样到达模型层。"""
    seen = {}

    def probe(persona, era, material, history, question):
        seen.update(persona=persona, era=era, material=material, question=question)
        return "这份文件里写的是发货时确认收入。", {"raw": "x", "kept": True}

    S.API_KEY = "test-key-not-used"
    real, S.discuss = S.discuss, probe
    try:
        body = json.dumps({"case_id": "sunbeam-1998", "era": 1998,
                           "persona": {"name": "Russell A. Kersh", "role": "首席财务官"},
                           "material": "1997 年净销售额 11.682 亿美元",
                           "question": "我持仓 50 万，手机 13800138000。你们为什么给经销商延长账期？"}).encode()
        code, _, out = hit(port, "/api/v1/discuss", "null", body)
    finally:
        S.discuss = real
        S.API_KEY = ""
    if code != 200 or b'"source": "llm"' not in out:
        errors.append(f"P7 /api/v1/discuss 没接通或没走到模型层（{code} {out[:80]}）")
        return
    if "13800138000" in seen.get("question", "") or "50 万" in seen.get("question", ""):
        errors.append(f"P7 送给模型的问题里还有原始 PII：{seen.get('question')}")
    if seen.get("persona", {}).get("name") != "Russell A. Kersh" or "11.682" not in seen.get("material", ""):
        errors.append("P7 人物或材料没有原样到达模型层")


def p8_nextsteps_gate(S, errors):
    """D14 出口闸 check_nextsteps：合格的方法讨论放行；荐股/出戏整条丢弃。"""
    ok_text = "先去调它过去几年的毛利率趋势，看这个差距稳不稳；再翻附注对一下成本口径。两项都对上才谈得上定价权。"
    if S.check_nextsteps(ok_text)[0] is None:
        errors.append("P8 合格的方法讨论被误杀")
    for bad, why in (
        ("这家公司现在值得买入。", "投资建议"),
        ("我给你的目标价是 200 元。", "投资建议"),
        ("作为 AI，我建议你先查财报。", "出戏"),
    ):
        if S.check_nextsteps(bad)[0] is not None:
            errors.append(f"P8 该丢弃的没丢（{why}）：{bad}")


def p8_nextsteps_wiring(S, port, errors):
    """端点接线 + 打码先于调模型 + 种子原样到达模型层。"""
    seen = {}

    def probe(seed, history, question):
        seen.update(seed=seed, question=question)
        return "先从历史趋势查起，因为定价权要看差距能不能持续。", {"raw": "x", "kept": True}

    S.API_KEY = "test-key-not-used"
    real, S.nextsteps = S.nextsteps, probe
    try:
        body = json.dumps({"quiz_id": "rv-gm-p1-b",
                           "seed": "题目：丙公司毛利率比同行高。区分线索：看差距能不能持续。该去补的证据：调历史趋势。",
                           "question": "我持仓 50 万，手机 13800138000。我该从哪一步开始查？"}).encode()
        code, _, out = hit(port, "/api/v1/next-steps", "null", body)
    finally:
        S.nextsteps = real
        S.API_KEY = ""
    if code != 200 or b'"source": "llm"' not in out:
        errors.append(f"P8 /api/v1/next-steps 没接通或没走到模型层（{code} {out[:80]}）")
        return
    if "13800138000" in seen.get("question", "") or "50 万" in seen.get("question", ""):
        errors.append(f"P8 送给模型的问题里还有原始 PII：{seen.get('question')}")
    if "调历史趋势" not in seen.get("seed", ""):
        errors.append("P8 方法种子没有原样到达模型层")


def main():
    S, dbfile = load()
    errors = []
    p1_mask(S, errors)
    p2_exit_gate(S, errors)
    p3_retention(S, errors)
    p6_discuss_gate(S, errors)
    p8_nextsteps_gate(S, errors)
    srv, port = serve(S)
    try:
        p4_origin(S, port, errors)
        p5_order(S, port, errors)
        p7_discuss_wiring(S, port, errors)
        p8_nextsteps_wiring(S, port, errors)
    finally:
        srv.shutdown()
        if S._db:
            S._db.close()
        if dbfile.exists():
            dbfile.unlink()
    for e in errors:
        print("ERROR:", e)
    if not errors:
        print("INFO : P1 打码分语境 ✓  P2 出口检查 ✓  P3 90 天留存 ✓  "
              "P4 Origin 收口 ✓  P5 打码先于调模型 ✓  P6 决策人出口检查 ✓  P7 discuss 接线 ✓  "
              "P8 next-steps 出口检查+接线 ✓")
    print("SERVER:", "FAIL" if errors else "PASS")
    return 1 if errors else 0


def selftest():
    """变异测试：把打码表清空、把出口检查改成永远放行，看门禁会不会红。"""
    import re as _re
    import subprocess
    f = ROOT / "server" / "server.py"
    orig = f.read_text(encoding="utf-8")
    # 变异要打在**功能本身**上，不能打在某一层冗余防线上。
    # 第一版两条无效：`MASKS = [] or [` 里的 `or` 会把原表还回来（等于没改），
    # `_cors` 里改 `if False:` 只废掉了一层——403 那条路仍由 _blocked 独立守着，
    # 而且 `if False:` 本身会被 check_src 的 S2 抓住。都是我自己写错了变异，
    # 不是门禁漏了。换成打在 mask 循环与 origin_ok 上。
    muts = [
        ("    for pat, rep in MASKS:", "    for pat, rep in []:", "打码表不生效"),
        ("    bad = [n for n in nums if n not in allowed", "    bad = [] or [n for n in nums if False", "出口检查永远放行"),
        ('    return (not ALLOWED_ORIGINS) or ((origin or "null") in ALLOWED_ORIGINS)',
         "    return True", "Origin 收口永远放行"),
        ("    cut = int(time.time()) - RETAIN_DAYS * 86400", "    cut = 0", "留存清理不删任何东西"),
        ("        note, nmask = mask_pii(note)", "        nmask = 0", "打码挪到调模型之后"),
        ("    for w in HINDSIGHT:", "    for w in ():", "决策人出口检查放过后见之明"),
        ('        if self.path == "/api/v1/discuss":', '        if self.path == "/api/v1/discuss-x":', "discuss 路由断线"),
    ]
    ok = 0
    try:
        for old, new, label in muts:
            assert orig.count(old) == 1, f"锚定失败：{label}"
            f.write_text(orig.replace(old, new, 1), encoding="utf-8")
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "check_server.py")],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            hit = "SERVER: FAIL" in r.stdout
            ok += hit
            first = next((l for l in r.stdout.splitlines() if l.startswith("ERROR")), r.stdout.strip()[:90])
            print(("  ✓ " if hit else "  ✗ ") + label + " → " + first[:110])
    finally:
        f.write_text(orig, encoding="utf-8")
    print(f"变异测试 {ok}/{len(muts)}")
    return 0 if ok == len(muts) else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(selftest() if "--selftest" in sys.argv else main())
