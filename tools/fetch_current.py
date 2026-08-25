#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B 轨时事案卷管线（规格 §5）。核心筛选零 LLM，全部确定性计算。

  L0 采集   EDGAR full-text search 找 comment letters（UPLOAD）
  L1 指标   companyfacts 确定性重算红旗指标（五道防呆）
  L2 绑定   候选必须命中官方文书（UPLOAD/AAER）才准出题
  L3 出稿   生成候选案卷 JSON → staging，等人工签字

用法:
  python tools/fetch_current.py --scan          # 扫最近的 comment letters
  python tools/fetch_current.py --cik 320193    # 对指定 CIK 算指标
  python tools/fetch_current.py --build         # 产出候选案卷到 content/current/staging.json

SEC 要求：User-Agent 带联系方式；官方限速 10 req/s，本工具限 5 req/s。
"""
import json, sys, time, argparse, pathlib, urllib.request, urllib.parse, gzip, io

UA = "invest-coach-edu contact@invest-coach.example"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "content" / "current"
_last = [0.0]

def get(url, host_json=False):
    """限速 5 req/s 的 GET。"""
    gap = time.time() - _last[0]
    if gap < 0.2:
        time.sleep(0.2 - gap)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Encoding": "gzip, deflate",
        "Host": urllib.parse.urlparse(url).netloc})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    _last[0] = time.time()
    return json.loads(raw) if host_json else raw.decode("utf-8", "replace")


# ---------- L0：找 comment letters ----------
TOPICS = ["accounts receivable", "revenue recognition", "days sales outstanding",
          "cash flow from operations", "bill and hold"]

def scan(limit=10):
    """EDGAR 全文检索 UPLOAD（SEC 发出的 comment letter）。"""
    hits = []
    for q in TOPICS:
        url = ("https://efts.sec.gov/LATEST/search-index?q=" + urllib.parse.quote(f'"{q}"') +
               "&forms=UPLOAD")
        try:
            d = get(url, True)
        except Exception as e:
            print(f"  [{q}] 检索失败: {e}")
            continue
        for h in (d.get("hits", {}).get("hits") or [])[:limit]:
            s = h.get("_source", {})
            acc = (h.get("_id") or "").split(":")[0]
            hits.append({"topic": q, "cik": (s.get("ciks") or [""])[0],
                         "company": (s.get("display_names") or [""])[0],
                         "filed": s.get("file_date"), "accession": acc,
                         "url": f"https://www.sec.gov/Archives/edgar/data/{int((s.get('ciks') or ['0'])[0])}/{acc.replace('-','')}/{acc}-index.htm"})
        print(f"  [{q}] {len(d.get('hits',{}).get('hits') or [])} 条")
    return hits


# ---------- L1：确定性指标（五道防呆） ----------
TAGS = {
    "rev": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
            "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "ar":  ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent", "AccountsReceivableGrossCurrent"],
    "ni":  ["NetIncomeLoss"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities"],
}
MIN_REV = 1e8       # 防呆④ 规模下限：季度收入 ≥ $1 亿
MIN_AR = 5e6        # 防呆④ 应收基数 ≥ $500 万
BAD_SIC = tuple(str(i) for i in range(6000, 7000))   # 防呆⑤ 排除金融业

def facts_for(cik):
    cik10 = str(int(cik)).zfill(10)
    return get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json", True)

def series(cf, keys, annual=True):
    """取原始申报值（防呆②：不信聚合，回原始 filing，同 end 取最早 filed）。"""
    us = cf.get("facts", {}).get("us-gaap", {})
    for k in keys:
        if k not in us:
            continue
        out = {}
        for unit, arr in (us[k].get("units") or {}).items():
            if not unit.startswith("USD"):
                continue
            for it in arr:
                form, end, val = it.get("form"), it.get("end"), it.get("val")
                if form not in ("10-K", "10-Q") or end is None:
                    continue
                if annual and it.get("start"):
                    days = (_d(end) - _d(it["start"])).days
                    if not (330 <= days <= 400):
                        continue
                prev = out.get(end)
                if prev is None or it.get("filed", "9") < prev["filed"]:
                    out[end] = {"val": val, "filed": it.get("filed", ""), "form": form, "tag": k}
        if out:
            return k, dict(sorted(out.items()))
    return None, {}

def _d(s):
    import datetime
    return datetime.date.fromisoformat(s)

def metrics(cik):
    """返回红旗指标；全部确定性计算，不经任何模型。"""
    cf = facts_for(cik)
    name = cf.get("entityName", "")
    tag_rev, rev = series(cf, TAGS["rev"])
    tag_ar, ar = series(cf, TAGS["ar"], annual=False)     # 时点数无 start
    tag_ni, ni = series(cf, TAGS["ni"])
    tag_ocf, ocf = series(cf, TAGS["ocf"])
    if len(rev) < 2 or len(ar) < 2:
        return {"cik": cik, "name": name, "ok": False, "why": "收入或应收序列不足两期"}
    re_k = list(rev)[-2:]
    ar_k = [k for k in ar if k in rev] or list(ar)
    ar_k = ar_k[-2:]
    # 防呆① 两期同 tag
    if rev[re_k[0]]["tag"] != rev[re_k[1]]["tag"] or ar[ar_k[0]]["tag"] != ar[ar_k[1]]["tag"]:
        return {"cik": cik, "name": name, "ok": False, "why": "跨期 tag 漂移，不可比"}
    r0, r1 = rev[re_k[0]]["val"], rev[re_k[1]]["val"]
    a0, a1 = ar[ar_k[0]]["val"], ar[ar_k[1]]["val"]
    if r1 < MIN_REV or a1 < MIN_AR:
        return {"cik": cik, "name": name, "ok": False, "why": f"规模低于下限（收入 {r1:,.0f} / 应收 {a1:,.0f}）"}
    if not r0 or not a0:
        return {"cik": cik, "name": name, "ok": False, "why": "基期为零"}
    g_rev, g_ar = (r1 - r0) / r0, (a1 - a0) / a0
    dso0, dso1 = a0 / r0 * 365, a1 / r1 * 365
    out = {"cik": cik, "name": name, "ok": True,
           "periods": [re_k[0], re_k[1]], "tag_rev": tag_rev, "tag_ar": tag_ar,
           "rev": [r0, r1], "ar": [a0, a1],
           "g_rev": round(g_rev * 100, 1), "g_ar": round(g_ar * 100, 1),
           "gap_x": round(g_ar / g_rev, 2) if g_rev > 0 else None,
           "dso": [round(dso0, 1), round(dso1, 1)]}
    if ni and ocf:
        nk = [k for k in ni if k in ocf]
        if nk:
            k = nk[-1]
            out["ni"], out["ocf"], out["ni_ocf_period"] = ni[k]["val"], ocf[k]["val"], k
    # 红旗规则（确定性）
    flags = []
    if g_rev > 0 and g_ar > g_rev * 1.8:
        flags.append("应收增速为收入的 1.8 倍以上")
    if dso1 > dso0 * 1.15:
        flags.append(f"回款天数拉长 {round(dso1-dso0,1)} 天")
    if out.get("ni", 0) > 0 and out.get("ocf", 1) < 0:
        flags.append("净利为正而经营现金流为负")
    out["flags"] = flags
    return out


# ---------- L3：候选案卷 ----------
def build(cands):
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []
    for m in cands:
        if not m.get("ok") or not m.get("flags"):
            continue
        rows = [{"k": "收入增速", "a": f"{m['g_rev']:+.1f}%", "b": ""},
                {"k": "应收增速", "a": f"{m['g_ar']:+.1f}%", "b": "", "flagA": 1},
                {"k": "回款天数（期末口径）", "a": f"{m['dso'][0]} → {m['dso'][1]} 天", "b": "",
                 "flagA": 1 if m['dso'][1] > m['dso'][0] else 0}]
        if "ni" in m:
            rows.append({"k": "净利 / 经营现金流",
                         "a": f"{m['ni']/1e6:,.0f}M / {m['ocf']/1e6:,.0f}M", "b": "",
                         "flagA": 1 if m["ni"] > 0 > m["ocf"] else 0})
        cases.append({
            "id": f"cur-{m['cik']}-{m['periods'][1]}",
            "company": m["name"], "cik": m["cik"],
            "status": "regulator_asked" if m.get("letter") else "none",
            "asof": m["periods"][1],
            "brief": "监管刚就这个科目向这家公司提过问。读数字，看监管在问什么——不做定性判断。",
            "panels": [{"kind": "cmp", "title": f"{m['periods'][0]} → {m['periods'][1]}",
                        "cols": [m["name"][:14], ""], "rows": rows},
                       {"kind": "note", "t": "机器算出的形状：" + "；".join(m["flags"])}],
            "letter": m.get("letter"),
            "provenance": {"source": "SEC XBRL companyfacts（原始申报值）",
                           "tags": {"revenue": m["tag_rev"], "receivables": m["tag_ar"]},
                           "computed_by": "tools/fetch_current.py（确定性，无 LLM）"},
            "gate": {"signed_off": False,
                     "blockers": ["需人工签字", "需三件套同框（官方提问原文 + 公司回复 + 原档数字）",
                                  "题干只能问机制不能问定性"]}})
    p = OUT / "staging.json"
    p.write_text(json.dumps({"generated_note": "候选案卷 · 未签字不得上线",
                             "count": len(cases), "cases": cases}, ensure_ascii=False, indent=1),
                 encoding="utf-8")
    print(f"\n候选案卷 {len(cases)} 个 → {p}")
    return cases


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--cik", action="append", default=[])
    ap.add_argument("--build", action="store_true")
    a = ap.parse_args()
    letters = []
    if a.scan or a.build:
        print("L0 采集 · EDGAR 全文检索 comment letters（UPLOAD）")
        letters = scan()
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "letters.json").write_text(json.dumps(letters, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  共 {len(letters)} 条 → {OUT/'letters.json'}")
    ciks = a.cik or [l["cik"] for l in letters if l.get("cik")][:8]
    res = []
    if ciks:
        print("\nL1 指标 · 确定性重算（五道防呆，零 LLM）")
        for c in dict.fromkeys(ciks):
            try:
                m = metrics(c)
            except Exception as e:
                m = {"cik": c, "ok": False, "why": f"取数失败 {e}"}
            lt = next((l for l in letters if l.get("cik") == c), None)
            if lt:
                m["letter"] = {"filed": lt["filed"], "topic": lt["topic"], "url": lt["url"]}
            res.append(m)
            print(("  ✓ " if m.get("ok") else "  · ") + f"{m.get('name') or c}: " +
                  (f"收入 {m['g_rev']:+.1f}% / 应收 {m['g_ar']:+.1f}% / DSO {m['dso'][0]}→{m['dso'][1]} · " +
                   ("旗:" + "|".join(m["flags"]) if m["flags"] else "无旗") if m.get("ok") else m.get("why", "")))
    if a.build:
        build(res)
