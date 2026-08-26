# -*- coding: utf-8 -*-
"""③ 案卷化：为深层节点写 x_casefile（手机原生的对照卡/趋势/溯源徽标），
把原来的教学屏降为按需「补课」抽屉。所有数字来自 facts.json 已核定条目。"""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
P = 'c:/invest-coach/content/ch1/site.json'
d = json.load(open(P, encoding='utf-8'))
N = {n['id']: n for n in d['nodes']}

# panel kinds: cmp(两实体对照) / trend(多期迷你趋势) / note(要点) / quote(原档引文)
CF = {
 'case-first-look': {
  "code":"CASE-01","status":"settled","asof":"1997 财年",
  "brief":"两家公司，同一个年代，各给两行数字。哪家更让你不安？",
  "panels":[
   {"kind":"cmp","title":"两行数字","cols":["A 公司","B 公司"],
    "rows":[{"k":"收入增速","a":"+18.7%","b":"+58.9%"},
            {"k":"应收增速","a":"+38.5%","b":"+64.6%","flagA":1},
            {"k":"两条腿步差","a":"约 2.1 倍","b":"约 1.1 倍","flagA":1}]},
   {"kind":"note","t":"提醒：不是看谁涨得猛。B 涨得更猛，但它的两条腿是齐的。"}],
  "srcs":[{"t":"A 收入 +18.7%","f":"sb-rev-g"},{"t":"A 应收 +38.5%","f":"sb-ar-g"},
          {"t":"B 收入 +58.9%","f":"dl-rev-g"},{"t":"B 应收 +64.6%","f":"dl-ar-g"}]},
 'rf1': {
  "code":"DRILL-RF1","status":"teaching","asof":"构造练习",
  "brief":"E 公司三年数据。应收和收入，谁的步子更大？大到什么程度才算旗？",
  "panels":[
   {"kind":"trend","title":"E 公司三年","series":[
     {"k":"收入增速","v":["+12%","+15%","+14%"]},
     {"k":"应收增速","v":["+30%","+32%","+33%"],"flag":1},
     {"k":"步差倍数","v":["2.5×","2.1×","2.4×"],"flag":1}]},
   {"kind":"note","t":"披露：无并购、客户结构无变化。"},
   {"kind":"note","t":"本章口径：步差要「持续两年以上 + 显著」才亮旗。单季波动不算。"}],
  "srcs":[]},
 'rf2': {
  "code":"CASE-01B","status":"settled","asof":"1997 财年",
  "brief":"A 公司这一年赚了钱，钱袋子却在漏。缺口去哪了？",
  "panels":[
   {"kind":"cmp","title":"两套算法，同一门生意","cols":["A 公司 1997",""],
    "rows":[{"k":"净利润","a":"+1.09 亿美元","b":""},
            {"k":"经营现金流","a":"−820 万美元","b":"","flagA":1},
            {"k":"现金流量表内应收变动","a":"−8,460 万美元","b":"","flagA":1}]},
   {"kind":"note","t":"注意那 −820 万里还含「出售应收账款」换来的 5,900 万现金——剔掉之后约 −6,700 万。"}],
  "srcs":[{"t":"净利 109.4","f":"sb-ni"},{"t":"经营现金流 −8.2","f":"sb-ocf"},
          {"t":"应收变动 −84.6","f":"sb-ar-change"},{"t":"卖应收 59","f":"sb-securitization"}]},
 'dso': {
  "code":"DRILL-DSO","status":"teaching","asof":"1997/1998 财年",
  "brief":"同一件事的第二种算法：平均一笔货款要等几天？注意口径。",
  "panels":[
   {"kind":"cmp","title":"回款天数（本站期末口径）","cols":["A 公司","B 公司"],
    "rows":[{"k":"上一年","a":"79 天","b":"42.5 天"},
            {"k":"本年","a":"92 天","b":"44.0 天","flagA":1},
            {"k":"变化","a":"+13 天","b":"+1.5 天","flagA":1}]},
   {"kind":"note","t":"⚠️ B 公司自己在年报里算的是 37 → 36 天（平均应收口径，在变快）。同一家公司，换口径方向相反——两个数都对。"}],
  "srcs":[{"t":"A 期末口径 79→92","f":"sb-dso-ending"},{"t":"B 期末口径 42.5→44.0","f":"dl-dso-ending"},
          {"t":"B 自证 37→36","f":"dl-dso-avg"}]},
 'corroborate': {
  "code":"CASE-01C","status":"settled","asof":"1997 财年",
  "brief":"红旗一已阳性。现在去现金流量表求证——两面旗互相作证，还是互相否决？",
  "panels":[
   {"kind":"cmp","title":"组合态判定材料","cols":["A 公司",""],
    "rows":[{"k":"红旗一（应收 vs 收入）","a":"阳性 · 步差 2.1 倍","b":"","flagA":1},
            {"k":"净利 vs 经营现金流","a":"+1.09 亿 vs −820 万","b":"","flagA":1},
            {"k":"缺口最大去向科目","a":"应收账款 −8,460 万","b":"","flagA":1}]},
   {"kind":"note","t":"组合态 2×2：双阳 → 升级深查；一阳一阴 → 无辜解释概率大增，降旗转跟踪。"}],
  "srcs":[{"t":"应收变动 −84.6","f":"sb-ar-change"},{"t":"经营现金流 −8.2","f":"sb-ocf"}]},
 'case-final': {
  "code":"CASE-01F","status":"settled","asof":"1997 财年 · 终局",
  "brief":"两家公司的完整弹药摆齐了。走一遍流程：两条腿 → 辩护词 → 现金作证 → 组合态。",
  "panels":[
   {"kind":"cmp","title":"简化三表","cols":["A 公司","B 公司"],
    "rows":[{"k":"收入增速","a":"+18.7%","b":"+58.9%"},
            {"k":"应收增速","a":"+38.5%","b":"+64.6%","flagA":1},
            {"k":"净利润","a":"+1.09 亿","b":"+9.44 亿"},
            {"k":"经营现金流","a":"−820 万","b":"+15.92 亿","flagA":1,"okB":1},
            {"k":"回款天数（期末）","a":"79 → 92 天","b":"42.5 → 44.0 天","flagA":1}]},
   {"kind":"quote","t":"「在有限情形下，应客户要求，本公司可能以 bill and hold 方式销售季节性产品……于 1997 年 12 月 29 日，此类销售约占合并收入的 3%。」",
    "src":"A 公司 1997 年报 · 收入确认附注"},
   {"kind":"note","t":"B 公司年报另自证：回款天数 37 → 36 天（平均口径，在变快）。"}],
  "srcs":[{"t":"A 净利 109.4","f":"sb-ni"},{"t":"A 现金流 −8.2","f":"sb-ocf"},
          {"t":"B 现金流 +1,592","f":"dl-ocf"},{"t":"bill-and-hold 3%","f":"sb-billhold"}]}}

facts = json.load(open('c:/invest-coach/content/ch1/facts.json', encoding='utf-8'))
fids = {f['id'] for f in facts['facts']}
for nid, cf in CF.items():
    for s in cf['srcs']:
        assert s['f'] in fids, (nid, s['f'])
    N[nid]['x_casefile'] = cf

d['x_note'] += " ｜ v3 案卷化：x_casefile（code/status/asof/brief/panels[cmp|trend|note|quote]/srcs→facts.json）——材料屏改为手机原生案卷，原教学屏降为按需「补课」抽屉。"
d['x_version'] = "ch1-content-v3（2026-08-25）｜案卷化：6 个深层节点写 x_casefile，溯源徽标直连 facts.json；教学屏转按需补课。图 ch1-graph-v1 不动"
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f"案卷写入 {len(CF)} 个节点；溯源徽标全部命中 facts.json")
