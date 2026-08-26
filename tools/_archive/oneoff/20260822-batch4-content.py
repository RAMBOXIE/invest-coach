# -*- coding: utf-8 -*-
"""批次 4：终局对决 + 你的清单 + c2 复训库 + 2 道 na 补锚题 + 新核定事实入账本。"""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = 'c:/invest-coach/'

# ---------- facts.json：新事实与新原档 ----------
fp = ROOT + 'content/ch1/facts.json'
F = json.load(open(fp, encoding='utf-8'))
F['evidence_files'].append({"file": "evidence/sunbeam-10ka-fy1997-restated.txt",
    "sha256": "62dd01d68dc4b5286d4ab2f45014d8ed090e9d7854feb62cc614de5a5d9d9935",
    "source": "Sunbeam FY1997 10-K/A（重述版）", "accession": "0000950170-98-002145"})
F['facts'] += [
 {"id": "dl-ocf", "company": "Dell", "item": "FY1998 经营现金流 vs 净利", "value": "OCF +$1,592M vs 净利 +$944M（OCF 远高于净利）", "basis": "现金流量表", "accession": "0000950134-98-003218", "line": "L1526-1536"},
 {"id": "sb-billhold", "company": "Sunbeam", "item": "bill-and-hold 销售披露", "value": "1997-12-29 时点约占合并收入 3%（公司自证于收入确认附注）", "basis": "REVENUE RECOGNITION 附注", "accession": "0000950170-98-000413", "line": "L2352-2363"},
 {"id": "sb-restated-sales", "company": "Sunbeam", "item": "重述后 1997 净销售额", "value": "$1,073.1M，+9%（档内自证「an increase of $88.9 million or 9%」）；原报 1,168.2（+18.7%）→ 蒸发 $95.1M", "basis": "重述版利润表与 MD&A", "accession": "0000950170-98-002145", "line": "L743/L995/L2080"},
 {"id": "sb-restated-ni", "company": "Sunbeam", "item": "重述后 1997 净利", "value": "$38.3M；原报 109.4 → 蒸发约 65%", "basis": "重述版利润表", "accession": "0000950170-98-002145", "line": "L758/L2101"},
 {"id": "sb-restated-ar", "company": "Sunbeam", "item": "重述后应收净额", "value": "209,754→228,460 $K（+8.9% 推算）；原报 +38.5%——重述后两条腿（+9.0%/+8.9%）完全同步", "basis": "重述版资产负债表；原/重述对照见 L4173", "accession": "0000950170-98-002145", "line": "L2152/L4173"}]
F['approved_tokens'].update({
 "1592": "dl-ocf", "944": "dl-ocf", "1362": "dl-ocf（FY1997 对照）",
 "3": "sb-billhold（约 3% 收入）", "1073.1": "sb-restated-sales", "1168.2": "sb-rev-g（原报绝对额）",
 "95.1": "sb-restated-sales（原报−重述，推算）", "9.0": "sb-restated-sales（档内自证 9%）", "9": "sb-restated-sales",
 "38.3": "sb-restated-ni", "65": "sb-restated-ni（蒸发比例，推算）", "8.9": "sb-restated-ar（推算）",
 "2006": "年份（Dell 和解涉案期）", "4": "泛指口语"})
json.dump(F, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ---------- site.json ----------
p = ROOT + 'content/ch1/site.json'
d = json.load(open(p, encoding='utf-8'))
N = {n['id']: n for n in d['nodes']}

# 终局对决
cf = N['case-final']
cf['canon']['x_cite'] = "AAER 1393 / Rel. 33-7976 · 认定段；原版 10-K405 附注 bill-and-hold 披露（L2352-2363）；重述版 10-K/A（acc. 0000950170-98-002145）L743/L758/L4173"
cf['x_coach_notes'] = {
 "value": "回到方法：你的每条证据都指得回具体的表和行——两条腿、两个口袋、一行应收变动、一段附注。这就是我说的「结论长在纸上」。",
 "risk": "注意你赢在流程而不是胆子：看见、辩护、求证、组合态，一步没跳。真实世界里这套流程的对手盘，就是当年拿着同一份年报没翻附注的人。",
 "behav": "把你终局的信心档和第一案的底片摆在一起看：变化的不该是胆量，是证据。若你高信心答对了——恭喜，这次是推理不是运气。"}
cf['screens'] = [
 {"h": "终局：两家公司的简化三表", "body": "<p>还是第一案那两家公司。这次给你完整弹药（全部经原档核定）：</p><table style=\"width:100%;border-collapse:collapse;font-size:.92em\"><tr><th style=\"padding:4px;border-bottom:1px solid #8886;text-align:left\"></th><th style=\"padding:4px;border-bottom:1px solid #8886\">A 公司</th><th style=\"padding:4px;border-bottom:1px solid #8886\">B 公司</th></tr><tr><td style=\"padding:4px\">收入增速</td><td style=\"text-align:center\">+18.7%</td><td style=\"text-align:center\">+58.9%</td></tr><tr><td style=\"padding:4px\">应收增速</td><td style=\"text-align:center\"><b>+38.5%</b></td><td style=\"text-align:center\">+64.6%</td></tr><tr><td style=\"padding:4px\">净利润</td><td style=\"text-align:center\">+1.09 亿</td><td style=\"text-align:center\">+9.44 亿</td></tr><tr><td style=\"padding:4px\">经营现金流</td><td style=\"text-align:center\"><b>−820 万</b>（含卖应收 5,900 万进款）</td><td style=\"text-align:center\"><b>+15.92 亿</b></td></tr><tr><td style=\"padding:4px\">回款天数（期末口径）</td><td style=\"text-align:center\">79 → 92 天</td><td style=\"text-align:center\">42.5 → 44.0 天</td></tr><tr><td style=\"padding:4px\">附注亮点</td><td style=\"text-align:center\">期末 bill-and-hold 销售 ≈ 收入的 3%</td><td style=\"text-align:center\">回款天数自证 37→36 天（平均口径）</td></tr></table><p>单位：美元。先自己走一遍流程：两条腿 → 辩护词 → 现金作证 → 组合态。</p>", "x_covers": [1]},
 {"quiz": {"q": "终局判断：哪家更可疑？（选完请在心里备好至少两条相互独立的证据）",
   "opts": [{"t": "A 公司：双阳（应收跑赢收入 + 利润不变现金）+ 期末 bill-and-hold 披露 + 卖应收粉饰现金流", "ok": True},
            {"t": "B 公司：应收增速全场最高（+64.6%），最可疑", "ok": False},
            {"t": "信息不足，无法判断", "ok": False, "na": True}],
   "fb": "A 的证据链至少四条且互相独立：两条腿步差一倍、经营现金流为负且真实缺口更大（卖应收 5,900 万垫着）、缺口去向就是应收、附注自证期末 bill-and-hold。B 恰好相反：现金流比利润还厚（+15.92 亿 vs +9.44 亿）、回款在变快——名义步差被两条硬证据否决。这题证据是充分的，「无法判断」在这里不是答案。",
   "hints": ["别比谁涨得猛——走流程：两条腿、辩护词、现金作证", "两家的经营现金流分别说了什么？", "口径：组合态定性——A 双阳升级，B 一阳一阴降旗"],
   "confidence": True, "x_pair": "c2-p1", "x_kind": "main", "x_id": "case-final-q1"}, "x_covers": [0]},
 {"quiz": {"q": "决策题：一位投资者持有 A 公司的股票，看完这套三表与附注，TA 最像样的下一步是？",
   "opts": [{"t": "清仓或大幅减仓：双阳 + 附注留痕已是重度疑点，继续持有的举证责任在公司一边", "ok": True},
            {"t": "减仓一半并设死线：下季报的应收、经营现金流、审计意见三项，任一恶化即离场", "ok": True},
            {"t": "加仓摊低成本——利润还在涨，市场错杀", "ok": False},
            {"t": "不看报表只看股价，跌破均线再说", "ok": False}],
   "fb": "两个诚实动作都算对——重度疑点下，退出与「减仓+死线」都是证据相称的仓位动作，差别只在风险偏好。「加仓摊低」把疑点当成了折扣；「只看股价」把本章白学了。注意：评分评的是动作与证据的相称，不是后来的涨跌。",
   "hints": ["现在的证据成色和第一案时一样吗？", "重度疑点下，举证责任在谁一边？", "口径：动作与证据成色相称——疑点配求证，重度疑点配减法"],
   "confidence": True, "x_kind": "decision", "x_id": "case-final-q2"}, "x_covers": [0]},
 {"h": "揭晓：真名与官方答案", "body": "<p><b>A 公司 = Sunbeam Corporation</b>。SEC 于 2001 年认定（AAER 1393）：其 1997 年报告的 1.89 亿美元 income 中<b>至少 6,200 万来自会计舞弊</b>——cookie jar 准备冲回、guaranteed sales、不当 bill-and-hold、披露不充分的渠道塞货。</p><p>公司随后重述了报表（1998-11）：收入 1,168.2 → <b>1,073.1</b>（增速 18.7% → 9%）；净利 109.4 → <b>38.3</b>（蒸发约 65%）；应收 +38.5% → <b>+8.9%</b>。</p><p style=\"font-size:1.05em\">📌 最值得记住的一行：<b>重述后两条腿是 +9.0% 对 +8.9%——完全同步。</b>你在第一案看到的那 30 个点的步差，不是「风格激进」，就是水分本身。</p><p><b>B 公司 = Dell</b>（FY1998）。它当年的两条硬证据（现金流厚过利润、回款变快）洗清了名义步差。⚠️ 但要诚实说完：Dell 在 2010 年因 <b>2001–2006 年间</b>的披露与会计问题（Intel 独占性付款）与 SEC 达成 1 亿美元和解——与 FY1998 无关。<b>某年干净不等于永远干净：本站每个结论都只限定在材料时点。</b></p><p style=\"opacity:.75\">结果不评判决策，过程才评判——你终局的对错、你的信心档，都已进错题档案与校准分。</p>", "x_covers": [1, 2]},
 {"quiz": {"q": "最后一问：凭这套三表和附注，能否判定 A 公司管理层是「故意」造假？",
   "opts": [{"t": "信息不足，无法判断——报表能给出可疑度与求证方向；「故意」是执法与司法层面的认定（本案后来由 SEC 作出）", "ok": True, "na": True},
            {"t": "能：证据这么多，必然故意", "ok": False},
            {"t": "不能——所以之前的怀疑全都白费了", "ok": False}],
   "fb": "满分答案是「无法判断」。散户读表的产出是三样：可疑度、求证清单、仓位动作——不包括「定罪」。分清这个边界不是怂，是本事：它让你敢下判断（有证据的部分）也敢停手（没证据的部分）。这就是校准。",
   "hints": ["报表证据和「主观故意」是同一类问题吗？", "本案的「故意」最终由谁认定的？", "口径：读表给可疑度，不给罪名——边界之外选无法判断"],
   "confidence": True, "x_kind": "main", "x_id": "case-final-q3"}, "x_covers": [2]}]

# 你的清单
cl = N['checklist-after']
cl['canon']['x_cite'] = "Asare & Wright (2004), Auditing 23(2):87-108（结构化清单降低风险评估）；Pincus (1989)；Seow (2011)；Sibbald et al.（验证阶段清单纠错 0.29 vs 0.03）——见 sources「审计清单与职业怀疑文献组」"
cl['screens'] = [
 {"h": "收官：把两面旗叠成一张卡", "body": "<p>走完全章，你的工具其实只有一张口袋卡：</p><p>① <b>两条腿</b>：应收增速 vs 收入增速——步差要「持续 + 显著」才亮旗；<br>② <b>三条辩护词</b>：账期 / 模式 / 并表——有披露、算得过来才算成立；<br>③ <b>现金作证</b>：净利 vs 经营现金流 → 组合态（双阳升级 / 一阳一阴降旗）；<br>④ <b>缺口去向</b>：应收（可疑）还是存货预付（扩张）；<br>⑤ <b>换把尺子</b>：DSO 趋势，先对口径；<br>⑥ <b>读附注</b>：退货条款、bill-and-hold、卖应收。</p>", "x_covers": [0]},
 {"h": "顺序是清单的一半", "body": "<p>这张卡有一条使用说明，比内容还重要：<b>先自由判断，再用清单复核。</b></p><p>反着用会坏事——这不是修辞，是审计实验的成体系发现（出处卡可查）：拿着标准清单做<b>初判</b>的审计师，风险评估反而更低；清单越结构化，越看不见清单外的异常。而专家在<b>验证阶段</b>用清单，纠错效果十倍于对照。</p><p>清单是网，不是眼睛。先用眼睛看，再用网捞漏。</p>", "x_covers": [0, 2]},
 {"h": "现在就复核一次", "body": "<p>回想第一案：当时你只用了①（两条腿）。</p><p>拿这张卡复核当时的自己：③组合态没查（后来发现是双阳）、⑥附注没读（bill-and-hold 就写在收入确认附注里）、⑤的口径坑差点把 B 公司冤枉了。</p><p>这就是清单的正确打开方式：<b>它不替你判断，它告诉你「你还没查什么」。</b></p>", "x_covers": [1]},
 {"quiz": {"q": "这张口袋卡的正确用法是？",
   "opts": [{"t": "先凭本章练出的眼力自由判断，再用卡逐项复核查漏", "ok": True},
            {"t": "判断之前逐项打勾，勾满再下结论", "ok": False},
            {"t": "背下来，见到符合任意一条就下结论", "ok": False}],
   "fb": "先判断、后复核。「先打勾」会把你的怀疑心外包给清单（实验里它压低职业怀疑）；「见一条就下结论」把复核工具用成了定罪公式。",
   "hints": ["清单是眼睛还是网？", "审计实验里，初判用清单的人发生了什么？", "口径：清单=判断后的查漏工具"],
   "x_kind": "main", "x_id": "checklist-after-q1"}, "x_covers": [0, 2]},
 {"quiz": {"q": "你已独立判断 T 公司红旗成立。用卡复核时发现：⑥附注（退货条款）没查。下一步？",
   "opts": [{"t": "把退货条款列入求证清单，查完再定稿结论", "ok": True},
            {"t": "结论已经下了，不用回头", "ok": False},
            {"t": "清单外的事更重要，这张卡可以扔了", "ok": False}],
   "fb": "复核查出的漏项就是下一步的取证任务——这一下就是清单的全部价值。查完可能加固结论，也可能推翻它，两种都是收获。",
   "hints": ["复核的产出是什么？", "漏了一项 = 结论作废吗？", "口径：查漏 → 补证 → 再定稿；清单内查完，清单外保持警觉"],
   "x_kind": "main", "x_id": "checklist-after-q2"}, "x_covers": [1]}]

# c2 复训库 + 2 道 na 补锚题
d['x_review_bank'] += [
 {"pair_id": "c2-p1", "side": "a", "quiz": {
   "q": "复训 · 某消费品公司全案：应收增速两年为收入两倍；净利正、经营现金流负、缺口在应收；附注披露期末 bill-and-hold 销售占收入 4% 且客户可退货。定性？",
   "opts": [{"t": "重度疑点：双阳 + 附注留痕（可退货的期末 bill-and-hold 是提前确认收入的高危形态）", "ok": True},
            {"t": "正常：bill-and-hold 是准则允许的", "ok": False},
            {"t": "信息不足，无法判断", "ok": False, "na": True}],
   "fb": "bill-and-hold 本身有严格的合规条件，但「期末集中 + 可退货 + 双阳」三件事叠加，就是教科书式的提前确认收入形态。准则允许 ≠ 用法无辜——看组合，不看单项。",
   "hints": ["双阳查出来了吗？", "可退货意味着「风险与所有权」真的转移了吗？", "口径：单项合规 + 组合可疑 = 重度疑点"],
   "confidence": True, "x_pair": "c2-p1", "x_kind": "review", "x_id": "rv-c2-p1-a"}},
 {"pair_id": "c2-p1", "side": "b", "quiz": {
   "q": "复训 · 某高速成长公司全案：应收 +61% vs 收入 +55%（名义步差）；经营现金流连年高于净利润；回款天数（同口径）连续两年缩短。定性？",
   "opts": [{"t": "不亮旗：现金流与回款两条硬证据同向否决了「收入收不回」——高增长期的正常喘息", "ok": True},
            {"t": "亮旗：应收增速高于收入就是红旗一，没有例外", "ok": False},
            {"t": "信息不足，无法判断", "ok": False, "na": True}],
   "fb": "红旗一的口径是「持续且显著、且辩护词缺席」。这里两条硬证据（现金流、回款天数）都站在辩护一边——机械套用「应收>收入即旗」正是本章要治的毛病。",
   "hints": ["两条腿之外，题面还给了哪两条证据？", "它们支持红旗假设还是无辜假设？", "口径：证据同向否决时降旗——机械套公式不是判断"],
   "confidence": True, "x_pair": "c2-p1", "x_kind": "review", "x_id": "rv-c2-p1-b"}},
 {"pair_id": "rf1-p3", "side": "b", "quiz": {
   "q": "复训 · 某公司应收 +70% vs 收入 +18%；年内完成一起收购并已并表，但披露里没有备考（pro forma）口径。你的判断？",
   "opts": [{"t": "信息不足，无法判断——并表使口径不可比，且无备考数据可剔除；把「要求备考口径」记为待验证项", "ok": True, "na": True},
            {"t": "红旗成立：+70% 对 +18%，步差悬殊", "ok": False},
            {"t": "不成立：有并购就说明步差是并表造成的", "ok": False}],
   "fb": "满分答案是「无法判断」。没有备考口径，你既不能亮旗（步差可能全是并表），也不能放行（并表也可能只解释一部分）——两个方向都缺证据。诚实持疑 + 记下要看的披露，就是全部正确动作。",
   "hints": ["口径可比吗？备考数据在场吗？", "「有并购」自动等于「步差全由并表解释」吗？", "口径：口径不可比且无法剔除 → 无法判断 + 待验证清单"],
   "confidence": True, "x_pair": "rf1-p3", "x_kind": "review", "x_id": "rv-rf1-p3-b2"}},
 {"pair_id": "rf2-p2", "side": "a", "quiz": {
   "q": "复训 · 某公司今年经营现金流大幅低于净利润（首次背离）；附注与管理层讨论对原因只字未提。你的判断？",
   "opts": [{"t": "信息不足，无法判断——单年背离本身只是问号；但「无任何解释」本身要记一笔，设好下季验证点", "ok": True, "na": True},
            {"t": "红旗二成立：背离就是背离", "ok": False},
            {"t": "没事：只背离了一年而已", "ok": False}],
   "fb": "满分答案是「无法判断」。单年背离不够亮旗（口径要求持续），但也不该被「才一年」轻轻放过——解释的缺席本身是信息。问号的正确姿势：挂起 + 验证点 + 盯下一份披露怎么说。",
   "hints": ["红旗二的「持续」要件满足了吗？", "公司对背离的解释质量如何？——注意这里是「没有解释」", "口径：单年 + 无解释 = 问号挂起 + 设验证点，不亮旗也不放行"],
   "confidence": True, "x_pair": "rf2-p2", "x_kind": "review", "x_id": "rv-rf2-p2-a2"}}]

# x_prov + 版本
for nid in ('case-final', 'checklist-after'):
    N[nid]['x_prov']['model'] = "claude-opus-5（图/骨架）+ claude-fable-5（屏与题）"
d['x_version'] = "ch1-content-v1（2026-08-22）｜第一章 14/14 节点内容全部完成；复训库 10 对 24 题；重述版数字（10-K/A）与 Dell 现金流、bill-and-hold 披露均经原档核定入账本；Dell 2010 和解已按裁决在终局揭示屏披露。图 ch1-graph-v1 不动；人工签字（G1/G2）仍未进行——poc-trial 定版前必须补齐"
json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('batch4 injected: chapter content COMPLETE 14/14')
