# -*- coding: utf-8 -*-
"""形态 v2「判卷台」：为深层节点添加证据卡 / 排除项 / 自评清单 / 锚题绑定。
证据卡与排除项来自已有内容（x_pairs 的辩护词、screens 的材料行），自评清单机械转自 evidence[]。
"""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
p = 'c:/invest-coach/content/ch1/site.json'
d = json.load(open(p, encoding='utf-8'))
N = {n['id']: n for n in d['nodes']}

# ---------- 证据卡池：每张卡 = 材料里的一条可点依据 ----------
# role: support=真依据 / distractor=看似相关实则不支撑 / irrelevant=噪音
CARDS = {
 'case-first-look': [
  {"id":"c1-e1","t":"A 公司收入 +18.7%","role":"support","w":1},
  {"id":"c1-e2","t":"A 公司应收 +38.5%","role":"support","w":2},
  {"id":"c1-e3","t":"两者步差约一倍","role":"support","w":3},
  {"id":"c1-e4","t":"B 公司收入 +58.9%（涨得更猛）","role":"distractor","w":0},
  {"id":"c1-e5","t":"B 公司应收 +64.6%","role":"distractor","w":0},
  {"id":"c1-e6","t":"B 公司步差仅 1.1 倍","role":"support","w":1}],
 'rf1': [
  {"id":"rf1-e1","t":"应收增速高于收入增速","role":"support","w":2},
  {"id":"rf1-e2","t":"这个步差持续了两年以上","role":"support","w":3},
  {"id":"rf1-e3","t":"应收/收入比值逐年爬升","role":"support","w":2},
  {"id":"rf1-e4","t":"收入本身还在增长","role":"distractor","w":0},
  {"id":"rf1-e5","t":"公司规模比同行大","role":"irrelevant","w":0},
  {"id":"rf1-e6","t":"账期披露无变化","role":"support","w":2},
  {"id":"rf1-e7","t":"无并购、口径可比","role":"support","w":2}],
 'rf2': [
  {"id":"rf2-e1","t":"净利润为正且逐年增长","role":"distractor","w":0},
  {"id":"rf2-e2","t":"经营现金流连年为负","role":"support","w":3},
  {"id":"rf2-e3","t":"缺口逐年扩大","role":"support","w":2},
  {"id":"rf2-e4","t":"缺口主要堆在应收","role":"support","w":3},
  {"id":"rf2-e5","t":"缺口主要堆在存货与预付","role":"distractor","w":0},
  {"id":"rf2-e6","t":"公司毛利率高于同行","role":"irrelevant","w":0}],
 'dso': [
  {"id":"dso-e1","t":"回款天数逐年拉长","role":"support","w":3},
  {"id":"dso-e2","t":"累计拉长超过 20 天","role":"support","w":2},
  {"id":"dso-e3","t":"无客户结构或模式变化披露","role":"support","w":2},
  {"id":"dso-e4","t":"公司收入规模在变大","role":"distractor","w":0},
  {"id":"dso-e5","t":"两个来源的 DSO 口径不同","role":"support","w":2}],
 'corroborate': [
  {"id":"cor-e1","t":"红旗一阳性（应收跑赢收入）","role":"support","w":2},
  {"id":"cor-e2","t":"经营现金流为负 / 远低于净利","role":"support","w":3},
  {"id":"cor-e3","t":"现金流量表里应收变动是最大负项","role":"support","w":3},
  {"id":"cor-e4","t":"利润连年为正","role":"distractor","w":0},
  {"id":"cor-e5","t":"经营现金流健康、缺口可被存货解释","role":"support","w":2}],
 'case-final': [
  {"id":"c2-e1","t":"A 应收 +38.5% vs 收入 +18.7%（步差一倍）","role":"support","w":3},
  {"id":"c2-e2","t":"A 净利 +1.09 亿 vs 经营现金流 −820 万","role":"support","w":3},
  {"id":"c2-e3","t":"A 的经营现金流里含卖应收 5,900 万进款","role":"support","w":3},
  {"id":"c2-e4","t":"A 附注自证期末 bill-and-hold 约占收入 3%","role":"support","w":3},
  {"id":"c2-e5","t":"B 应收 +64.6%（全场最高）","role":"distractor","w":0},
  {"id":"c2-e6","t":"B 经营现金流 +15.92 亿 > 净利 +9.44 亿","role":"support","w":2},
  {"id":"c2-e7","t":"B 回款天数自证在变快","role":"support","w":2},
  {"id":"c2-e8","t":"A 的收入绝对额比 B 小","role":"irrelevant","w":0}]}

# ---------- 排除项（三条辩护词，逐条判定） ----------
RULEOUT = {
 'rf1': [
  {"id":"rf1-r1","t":"账期变了：大客户压账期，欠条自然变厚","verdict":"excluded","fb":"题面说账期披露无变化——这条辩护词用不上。"},
  {"id":"rf1-r2","t":"模式换了：转向分期/租赁，比值一次跳台阶","verdict":"excluded","fb":"逐年爬升不是一次跳变，模式切换解释不了这个形状。"},
  {"id":"rf1-r3","t":"并表了：收购把别人的应收带进来","verdict":"excluded","fb":"题面说无并购，口径可比。"}],
 'rf2': [
  {"id":"rf2-r1","t":"扩张备货：缺口是存货和预付吃掉的","verdict":"excluded","fb":"缺口去向题面写明是应收，不是存货。"},
  {"id":"rf2-r2","t":"季节/跨期：大单发货与回款错开一年","verdict":"excluded","fb":"连续三年、缺口还在扩大——跨期解释不了持续性。"},
  {"id":"rf2-r3","t":"行业惯例：这个行业本来现金流就差","verdict":"insufficient","fb":"题面没给同行对比，这条既排不掉也证不实——它该进你的求证清单。"}],
 'case-final': [
  {"id":"c2-r1","t":"账期/渠道结构变化","verdict":"insufficient","fb":"材料没给账期披露——排不掉，但它也不是主要疑点。"},
  {"id":"c2-r2","t":"扩张期备货吃现金","verdict":"excluded","fb":"缺口去向是应收不是存货，且还靠卖应收垫了 5,900 万。"},
  {"id":"c2-r3","t":"季节性错位，次年回正","verdict":"excluded","fb":"附注自证期末 bill-and-hold 占收入 3%——期末冲量是主动行为，不是季节。"}]}

DEEP = [n for n in d['nodes'] if 'x_level' in n]
for n in DEEP:
    nid = n['id']
    if nid in CARDS:
        n['x_cards'] = CARDS[nid]
    if nid in RULEOUT:
        n['x_ruleout'] = RULEOUT[nid]
    # 自评清单：机械转自 evidence[]（本就是「可观察的掌握证据」）
    n['x_selfcheck'] = [{"id": f"{nid}-sc{i+1}", "t": ev} for i, ev in enumerate(n.get('evidence', []))]

# ---------- 锚题绑定：每个深层节点指定 ≥2 个换壳锚题（来自复训库，换公司） ----------
ANCHOR = {
 'case-first-look': ['rv-c1-p1-a', 'rv-c1-p1-b'],
 'rf1': ['rv-rf1-p1-a', 'rv-rf1-p2-a', 'rv-rf1-p3-b2'],
 'rf2': ['rv-rf2-p1-a', 'rv-rf2-p2-a2'],
 'dso': ['rv-dso-p1-a', 'rv-dso-p2-b'],
 'corroborate': ['rv-cor-p1-a', 'rv-cor-p1-b'],
 'case-final': ['rv-c2-p1-a', 'rv-c2-p1-b']}
bank_ids = {it['quiz']['x_id'] for it in d.get('x_review_bank', [])}
for nid, ids in ANCHOR.items():
    missing = [i for i in ids if i not in bank_ids]
    assert not missing, (nid, missing)
    N[nid]['x_anchors'] = ids

d['x_note'] += " ｜ v2「判卷台」新增：x_cards（证据卡池，role=support/distractor/irrelevant）、x_ruleout（排除辩护词，verdict=excluded/not_excluded/insufficient）、x_selfcheck（自评清单，转自 evidence[]）、x_anchors（锚题 id，来自复训库=换公司换壳，点亮的唯一条件）。"
d['x_version'] = "ch1-content-v2（2026-08-25）｜判卷台形态：6 个深层节点补齐证据卡/排除项/自评清单/锚题绑定；基础 5 节点走两拍。图 ch1-graph-v1 不动；人工签字仍未进行"
json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f"深层节点 {len(DEEP)}：cards={sum(1 for n in DEEP if 'x_cards' in n)} ruleout={sum(1 for n in DEEP if 'x_ruleout' in n)} selfcheck={sum(1 for n in DEEP if 'x_selfcheck' in n)} anchors={sum(1 for n in DEEP if 'x_anchors' in n)}")
