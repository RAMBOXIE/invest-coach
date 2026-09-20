"""把五个英文模板故事迁移为中文的三段式金融 RPG。

这是一次可重复的内容迁移：保留 case_id、事实登记和来源字段，重写用户可见叙事。
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


CASES = {
    "buffett-coke-1988": {
        "company": "可口可乐公司",
        "title": "等了五十二年的可口可乐",
        "subtitle": "1988 年 · 巴菲特终于买下自己早就看懂的生意",
        "hook": "人人都知道可口可乐。难的是回答：为什么偏偏是 1988 年，它值这个价？",
        "learning_goal": "把品牌好感拆成定价权、资本回报、现金流和买入价格。",
        "skills": ["定价权", "资本回报", "内在价值"],
        "cast": ("沃伦·巴菲特", "伯克希尔董事长", "他公开写下了这次买入的理由。故事只使用公开记录，不替他编造台词。"),
        "roles": [
            ("researcher", "消费品研究员", "把品牌魅力落到经营数字上", "大家都说这个品牌不需要解释。"),
            ("risk", "风险负责人", "找出好生意失灵的条件", "会议里没人愿意给传奇品牌泼冷水。"),
            ("allocator", "资本配置人", "判断好生意是否也有好价格", "市场刚经历崩盘，机会看起来稍纵即逝。"),
        ],
        "scenes": [
            {
                "id": "opening", "eyebrow": "故事开始", "place": "奥马哈 · 1988 年夏", "time": "买单还没有递出去",
                "title": "你认识它，不等于你看懂了它",
                "lines": ["巴菲特小时候就卖过可口可乐，五十二年后才第一次买它的股票。", "会议桌上没人怀疑品牌。大家需要回答的是：这门生意靠什么把一瓶糖水卖遍世界，而且越卖越赚钱？"],
                "actions": [
                    {"id": "follow-money", "kind": "先看生意", "label": "顺着一瓶可乐的钱往下查", "prompt": "看提价、销量、渠道和维持增长需要的资本。", "consequence": "会议从“大家都爱喝”转向“公司凭什么持续赚钱”。品牌第一次被拆成可以核对的东西。", "result_title": "熟悉感被拆开了", "narration": "喜欢产品只能让你注意到公司，不能替你完成估值。", "next": "development"},
                    {"id": "follow-fame", "kind": "先信品牌", "label": "全球第一的品牌，还需要解释吗", "prompt": "把知名度直接当成护城河。", "consequence": "讨论很快结束。所有人都同意品牌强，却没人说得出它怎样变成现金，也没人写下什么情况会让判断失效。", "result_title": "掌声盖过了问题", "narration": "最容易买贵的，往往正是人人都能讲出优点的公司。", "next": "development"},
                ],
            },
            {
                "id": "development", "eyebrow": "故事发展", "place": "伯克希尔投资会议", "time": "品牌已经过关，价格还没有",
                "title": "好生意，也可能是一笔坏买卖",
                "lines": ["海外销量正在加速，管理层把营销和资本配置拧到了一起。", "现在轮到你回答更扫兴的问题：如果买得太贵，品牌再好能不能救你？"],
                "actions": [
                    {"id": "price-it", "kind": "算清代价", "label": "先写下未来现金流，再谈愿意付多少钱", "prompt": "把增长、回报和价格放在同一张纸上。", "consequence": "你迫使会议写下假设：增长从哪里来、需要多少资本、哪一项低于预期就要重算。", "result_title": "品牌有了价格边界", "narration": "估值是在回答：这份正确判断，最多值得付出多少。", "next": "climax"},
                    {"id": "pay-up", "kind": "抢先买入", "label": "这样的公司不会便宜，先买再说", "prompt": "用稀缺性替代价格讨论。", "consequence": "仓位先建立起来，估值被推到以后。以后每一次上涨都会让原来的决定看起来更正确。", "result_title": "价格问题被留在门外", "narration": "好公司值得溢价，不等于任何溢价都值得。", "next": "climax"},
                ],
            },
            {
                "id": "climax", "eyebrow": "故事高潮", "place": "签字前的最后一页", "time": "资金今天就要拨出去", "title": "你给这笔买入写什么理由？",
                "lines": ["历史不会在今天告诉你答案。你只能用手上的经营事实和自己愿意承担的价格做决定。"], "final": True,
                "actions": [
                    {"id": "a", "kind": "带条件买入", "label": "买，但把增长假设和价格上限写清楚", "prompt": "以后用经营结果复核，不用股价替自己辩护。", "consequence": "你批准买入，同时留下三条复核线：定价权、资本回报和买入价格。", "result_title": "你买的是一套可复核的判断", "narration": "决定可以大胆，理由必须经得起以后逐条检查。", "next": "__legacy_reveal"},
                    {"id": "b", "kind": "追随名望", "label": "巴菲特都看懂了，照着买就够了", "prompt": "把决策人的名声当成自己的证据。", "consequence": "仓位建立得很快，但这套判断离开巴菲特的名字就无法独立站立。", "result_title": "你借来了结论，没有借到能力", "narration": "可以学习高手怎样想，不能拿高手的名字代替自己的证据。", "next": "__legacy_reveal"},
                    {"id": "c", "kind": "等待完美", "label": "等所有数字都确定以后再决定", "prompt": "把不确定性全部消失当成出手条件。", "consequence": "你避开了犯错，也把此刻能够判断的东西一并放弃。", "result_title": "你把谨慎变成了停顿", "narration": "投资不会给你完整答案，只会给你足够或不足的证据。", "next": "__legacy_reveal"},
                ],
            },
        ],
        "record": ("历史翻牌", "五十二年后，他终于买了", "伯克希尔 1988 年开始大举买入可口可乐，并明确表示准备长期持有。", "伯克希尔 1988、1989 年致股东信", "1988—1989 年可口可乐段", "1988 年我们大量买入可口可乐。我们持有优秀企业的一部分时，最喜欢的持有期限是永远。"),
        "lesson": ["品牌只是入口。要继续追问：它怎样提价、怎样扩张、需要多少新增资本。", "把生意质量和买入价格分开写。两者都对，才是一笔好投资。", "高手的名字可以提示方向，不能代替你自己的证据链。"],
        "method": ("把品牌拆成四个问题", "客户为什么反复购买？公司为什么能提价？增长要不要持续砸钱？现在的价格已经预支了多少未来？", "品牌价值 = 持续购买 × 定价权 × 低资本消耗", "产品受欢迎，但提价后销量下滑、资本回报下降时", "定价权 → 资本回报 → 现金流 → 买入价格"),
        "transfer": ("另一家人人都爱的品牌来了", "你第一步做什么？", ["先写下提价、销量和资本回报怎样互相验证", "先问身边有多少人喜欢它"], "受欢迎是线索。能不能提价、要花多少钱增长，才决定它是不是一门好生意。"),
    },
    "burry-mortgage-2007": {
        "company": "锡安资本与美国次级按揭市场",
        "title": "评级背后的那栋房子",
        "subtitle": "2005—2007 年 · 迈克尔·伯里拆开次贷证券",
        "hook": "债券写着高评级，最后还钱的却是一批两年后就要重定价的房贷。",
        "learning_goal": "穿透证券名称和评级，找到借款人、合同条款、重定价时点和损失路径。",
        "skills": ["穿透分析", "信用风险", "模型边界"],
        "cast": ("迈克尔·伯里", "锡安资本基金经理", "故事依据其向金融危机调查委员会提供的公开记录，不模仿本人发言。"),
        "roles": [("researcher", "抵押贷款研究员", "把债券拆回一笔笔房贷", "模型已经给出漂亮的评级。"), ("risk", "基金风控负责人", "算清保费能撑多久", "客户开始质疑为什么一直在亏保费。"), ("allocator", "基金经理", "让判断、催化时点和仓位匹配", "看对太早，也可能先被拖死。")],
        "scenes": [
            {"id": "opening", "eyebrow": "故事开始", "place": "加州圣何塞 · 2005 年", "time": "房地产还在上涨", "title": "评级说安全，合同却说两年后见", "lines": ["桌上是一只分散得很漂亮的抵押贷款证券。", "把它拆开后，你看见大量浮动利率贷款：前两年还款很轻，重定价之后才开始承受压力。"], "actions": [
                {"id": "read-loans", "kind": "拆到底层", "label": "逐笔看借款人收入、首付和重定价日期", "prompt": "别从评级开始，从谁在还钱开始。", "consequence": "债券名称消失了，桌上剩下借款人的收入、合同和两年后的月供。风险第一次有了时间表。", "result_title": "你找到了最后的付款人", "narration": "证券可以切成很多层，现金最后仍要从某个人的账户里出来。", "next": "development"},
                {"id": "trust-rating", "kind": "相信评级", "label": "既然分散又有高评级，不必逐笔看", "prompt": "把模型输出当成调查终点。", "consequence": "分析很快完成。没人再问借款人能否承受重定价后的月供。", "result_title": "整齐的模型关掉了调查", "narration": "评级描述模型里的风险，不会替你检查模型漏掉了什么。", "next": "development"},
            ]},
            {"id": "development", "eyebrow": "故事发展", "place": "锡安资本投资者电话会", "time": "保费不断流出", "title": "方向可能对，时间也可能把你耗死", "lines": ["你买下信用违约互换后，房地产没有立刻下跌。", "每个月都要付保费，投资者看到的只有亏损和一封越来越难解释的信。"], "actions": [
                {"id": "match-clock", "kind": "对准时钟", "label": "把仓位和贷款重定价时间排在一起", "prompt": "算清最坏情况下还能付多久保费。", "consequence": "你不再只讨论会不会出事，而是讨论自己能不能活到出事那天。", "result_title": "判断终于和资金期限接上了", "narration": "看对方向只是第一步，活到兑现那天才算完成。", "next": "climax"},
                {"id": "add-more", "kind": "只谈确信", "label": "既然越来越确定，就继续加大仓位", "prompt": "用确信压过持有成本。", "consequence": "风险敞口继续扩大，保费也继续流出。现在即使判断正确，客户赎回也可能先结束游戏。", "result_title": "正确观点开始威胁生存", "narration": "仓位不是观点的音量，它决定你有没有下一次决策机会。", "next": "climax"},
            ]},
            {"id": "climax", "eyebrow": "故事高潮", "place": "给投资人的最后一封解释", "time": "赎回压力已经到门口", "title": "你怎么让这笔逆向交易活下去？", "lines": ["你必须同时回答三件事：底层为什么会坏、什么时候开始坏、基金能承受多久。"], "final": True, "actions": [
                {"id": "a", "kind": "守住期限", "label": "缩到能活过重定价周期的仓位", "prompt": "让保费、赎回和催化时点都在预算里。", "consequence": "收益上限变小了，但基金保留了等到事实出现的能力。", "result_title": "你先保证自己不会提前出局", "narration": "风险预算给观点留下了足够的时间。", "next": "__legacy_reveal"},
                {"id": "b", "kind": "押满观点", "label": "把最确信的判断变成最大的仓位", "prompt": "方向正确就应该集中。", "consequence": "回报可能惊人，但赎回、保费和交易对手任何一项先出问题，都能让正确判断无法兑现。", "result_title": "你把时间风险留给了运气", "narration": "正确不等于可承受。", "next": "__legacy_reveal"},
                {"id": "c", "kind": "放弃研究", "label": "市场迟迟不动，承认自己错了", "prompt": "用短期价格检验长期信用判断。", "consequence": "你停止付保费，也在贷款开始重定价前离开了已经查清的证据链。", "result_title": "价格替你推翻了合同", "narration": "价格可以提醒你复核，不能单独证明底层现金流没有问题。", "next": "__legacy_reveal"},
            ]},
        ],
        "record": ("历史翻牌", "两年后的月供开始说话", "随着浮动利率贷款重定价，底层违约压力暴露，针对次贷证券的信用保护大幅升值。", "美国金融危机调查委员会最终报告", "第 10 章 · 迈克尔·伯里段", "房价上涨几乎没有工资和收入增长支撑；当两年期浮动利率贷款需要再融资时，住房市场将迎来最后的检验。"),
        "lesson": ["看到结构化产品，先问最后是谁还钱。", "把合同里的重定价日期变成风险时间表。", "方向、催化时点和仓位必须一起成立。"],
        "method": ("从评级一路追到借款人", "谁在还钱？合同何时变贵？什么事件触发损失？持有成本能撑多久？", "信用判断 = 偿付能力 × 合同条款 × 时间 × 仓位", "底层收入稳定、首付充足，而且压力测试覆盖重定价后的月供时", "借款人 → 合同 → 重定价 → 违约 → 仓位"),
        "transfer": ("一只新的高评级产品摆上桌", "先看哪一页？", ["先找底层付款人和触发损失的合同条款", "先看评级机构给了多少颗星"], "评级可以当索引，不能当结论。第一步永远是找到现金从哪里来。"),
    },
    "lynch-fidelity-1985": {
        "company": "富达麦哲伦基金",
        "title": "购物车里的线索",
        "subtitle": "1985 年 · 彼得·林奇从日常消费追到公司年报",
        "hook": "你在商店里发现一个爆款。它可能是一只好股票，也可能只是一个好产品。",
        "learning_goal": "把生活观察写成可证伪假设，再用增长质量和估值完成判断。",
        "skills": ["观察到假设", "增长质量", "估值纪律"],
        "cast": ("彼得·林奇", "富达麦哲伦基金经理", "故事采用其公开阐述的方法，只讲可核对的研究动作。"),
        "roles": [("researcher", "消费行业研究员", "把货架观察变成待验证的假设", "团队已经被产品体验打动。"), ("risk", "组合风控负责人", "区分产品增长和公司增长", "错过热门公司看起来比买贵更难受。"), ("allocator", "基金经理", "让增长速度和估值匹配", "基金规模要求你今天给出结论。")],
        "scenes": [
            {"id": "opening", "eyebrow": "故事开始", "place": "波士顿郊外的商场 · 1985 年", "time": "周末购物之后", "title": "你发现了产品，还没有发现股票", "lines": ["货架前排着队，身边的人都在谈同一个新产品。", "这个观察很值钱，但它只够让公司进入研究名单。"], "actions": [
                {"id": "write-hypothesis", "kind": "写成问题", "label": "先写下：它会怎样出现在下一份年报里", "prompt": "收入、同店增长、库存和利润率至少要有一项响应。", "consequence": "一句“我很喜欢”变成了四个可以被年报推翻的问题。", "result_title": "购物体验成了研究起点", "narration": "生活观察的价值，是帮你比别人更早提出问题。", "next": "development"},
                {"id": "buy-product", "kind": "凭体验下注", "label": "我自己都在买，市场一定会继续买", "prompt": "把个人体验外推成全国需求。", "consequence": "仓位有了，假设却没有。以后销量不及预期时，你甚至不知道最初判断错在哪。", "result_title": "产品体验替公司签了字", "narration": "好产品和好股票之间，还隔着公司、竞争和价格。", "next": "development"},
            ]},
            {"id": "development", "eyebrow": "故事发展", "place": "富达研究室", "time": "年报摊在桌上", "title": "增长是真的，还是货架给你的错觉？", "lines": ["你找到了收入增长，也看见库存和门店扩张。", "现在要判断：增长来自更多人反复购买，还是公司把货铺得更满？"], "actions": [
                {"id": "cross-check", "kind": "交叉核对", "label": "把收入、库存、现金和门店放在一起看", "prompt": "四个数字要讲同一个故事。", "consequence": "你开始分辨消费者真的买走了多少，而不是公司向渠道发出了多少。", "result_title": "增长有了质量", "narration": "一个数字变好叫线索，几张表互相对得上才叫证据。", "next": "climax"},
                {"id": "follow-growth", "kind": "只看增速", "label": "收入涨得够快，其他问题以后再说", "prompt": "让增长率替你完成判断。", "consequence": "故事依旧顺滑，但库存、现金和估值被排到了会议之后。", "result_title": "最快的数字赢了", "narration": "增长率告诉你跑得多快，不告诉你油从哪里来。", "next": "climax"},
            ]},
            {"id": "climax", "eyebrow": "故事高潮", "place": "麦哲伦基金下单前", "time": "你只能写一页投资理由", "title": "把这家公司讲给没逛过那家店的人听", "lines": ["如果你的判断离开个人体验就说不清，它还不是一份投资研究。"], "final": True, "actions": [
                {"id": "a", "kind": "形成假设", "label": "写清增长来源、验证数字和失效条件", "prompt": "让没见过产品的人也能复核。", "consequence": "你的投资理由不再依赖“我见过”，而依赖收入、库存、现金和价格。", "result_title": "线索终于变成了判断", "narration": "熟悉生活给你入口，财报给你刹车。", "next": "__legacy_reveal"},
                {"id": "b", "kind": "相信直觉", "label": "用户排队就是最好的研究", "prompt": "把局部观察当成完整市场。", "consequence": "你保留了故事最动人的部分，也删掉了最容易证伪它的部分。", "result_title": "你记住了队伍，忘了报表", "narration": "亲眼所见很有力量，所以更需要用数字限制它。", "next": "__legacy_reveal"},
                {"id": "c", "kind": "拒绝线索", "label": "生活观察太主观，完全不看", "prompt": "只允许报表里的数字进入研究。", "consequence": "你避免了主观偏差，也失去了比报表更早发现变化的机会。", "result_title": "你关掉了研究的雷达", "narration": "线索不负责下结论，但它负责告诉你该看哪里。", "next": "__legacy_reveal"},
            ]},
        ],
        "record": ("历史翻牌", "彼得·林奇把逛街写进了研究方法", "他反复强调普通投资者可以从日常生活发现线索，但必须继续研究公司、财务和估值。", "彼得·林奇公开演讲与富达历史资料", "公开方法节选", "先在生活中发现变化，再用公司的经营事实检查这个想法。产品是线索，不是结论。"),
        "lesson": ["先把观察写成一句能被证伪的话。", "至少用收入、库存、现金和门店中的两项交叉核对。", "产品再好，也要问价格已经反映了多少增长。"],
        "method": ("把“我喜欢”改写成“我预计”", "我预计哪个数字会变？多久会变？什么数字不变就说明我错了？", "可用假设 = 生活线索 + 财报验证 + 失效条件", "样本只是个人偏好，或者公司增长无法在财务数据中出现时", "观察 → 假设 → 财报 → 估值"),
        "transfer": ("朋友推荐了另一款爆红产品", "你怎么开始研究？", ["先写下它应该改变公司的哪几个数字", "先统计身边有多少朋友喜欢"], "身边的人能帮你发现线索，不能替你估算全国市场。"),
    },
    "munger-costco-1999": {
        "company": "好市多公司",
        "title": "薄利仓库里的厚生意",
        "subtitle": "1999 年 · 查理·芒格面对好市多的低毛利模式",
        "hook": "毛利压得这么低，看起来不像好生意。可会员却一年又一年回来。",
        "learning_goal": "理解低毛利、高周转、会员费和顾客信任如何组成同一套系统。",
        "skills": ["周转效率", "单位经济学", "质量与价格"],
        "cast": ("查理·芒格", "伯克希尔副董事长", "故事依据其公开谈论好市多的记录，不生成冒充本人的新台词。"),
        "roles": [("researcher", "零售研究员", "看清低毛利如何换来周转和续费", "同业分析习惯先比较毛利率。"), ("risk", "经营风控负责人", "找出会员飞轮会在哪断掉", "所有人都爱这门生意，坏消息很难开口。"), ("allocator", "资本配置人", "把经营质量和买入价格分开", "好公司正在被市场追捧。")],
        "scenes": [
            {"id": "opening", "eyebrow": "故事开始", "place": "好市多仓库店 · 1999 年", "time": "收银台前排着长队", "title": "毛利这么薄，利润藏在哪里？", "lines": ["货架不花哨，商品种类不多，价格压得很低。", "传统零售分析会嫌毛利率难看，可会员仍在续费，商品也转得飞快。"], "actions": [
                {"id": "trace-system", "kind": "看完整系统", "label": "从低价一路追到周转、续费和资本占用", "prompt": "别把毛利率单独拎出来。", "consequence": "低毛利不再只是少赚一点，而是吸引会员、提高周转、强化信任的起点。", "result_title": "四个零件咬在了一起", "narration": "有些优势不在某个比率里，而在几个比率怎样互相推动。", "next": "development"},
                {"id": "judge-margin", "kind": "只比毛利", "label": "毛利率低，说明议价能力弱", "prompt": "用一个比率完成定性。", "consequence": "分析表很整齐，但续费、周转和顾客信任全部被留在表外。", "result_title": "你看见了薄，没看见快", "narration": "比率没有错，错的是让一个比率替整个商业模式发言。", "next": "development"},
            ]},
            {"id": "development", "eyebrow": "故事发展", "place": "董事会材料室", "time": "竞争对手开始模仿低价", "title": "低价谁都能学，为什么系统不容易复制？", "lines": ["把价格降下来并不难。难的是在低价下仍保持周转、续费和供应商效率。", "一旦为了季度利润抬高毛利，会员对价格的信任也可能开始松动。"], "actions": [
                {"id": "protect-loop", "kind": "守住飞轮", "label": "把会员信任当成需要复核的资产", "prompt": "看续费、周转和单位资本回报是否一起稳定。", "consequence": "你给系统画出了断点：提价过度、续费下降、周转放慢，任何一项都能让飞轮失速。", "result_title": "优势终于有了失效条件", "narration": "说得出护城河会在哪里塌，才算真的看懂它。", "next": "climax"},
                {"id": "raise-margin", "kind": "追求利润", "label": "既然顾客忠诚，就把毛利提上去", "prompt": "先兑现眼前利润。", "consequence": "短期利润会更好看，但“永远占便宜”的会员感受开始被拿去变现。", "result_title": "你用飞轮换了一个漂亮季度", "narration": "商业模式最值钱的地方，往往也是管理层最容易提前兑现的地方。", "next": "climax"},
            ]},
            {"id": "climax", "eyebrow": "故事高潮", "place": "投资委员会", "time": "所有人都承认公司优秀", "title": "好公司要不要不计价格地买？", "lines": ["你已经看懂经营系统。最后一个问题与经营无关：市场给它的价格，是否已经把未来都写满了？"], "final": True, "actions": [
                {"id": "a", "kind": "质量与价格", "label": "先估飞轮能转多久，再决定最高买价", "prompt": "经营判断和价格判断各写一页。", "consequence": "你保留了对公司的欣赏，也保留了拒绝过高价格的权利。", "result_title": "好公司没有得到免检证", "narration": "质量决定你愿意持有多久，价格决定你能承受多少判断误差。", "next": "__legacy_reveal"},
                {"id": "b", "kind": "质量崇拜", "label": "系统这么好，贵一点无所谓", "prompt": "让商业模式替价格辩护。", "consequence": "你买下了优秀公司，也把很大一部分未来回报提前付给了卖方。", "result_title": "好生意吃掉了安全边界", "narration": "“长期持有”不能修复买入时已经透支的回报。", "next": "__legacy_reveal"},
                {"id": "c", "kind": "比率否决", "label": "毛利太低，直接排除", "prompt": "回到单一比率。", "consequence": "你避开了估值问题，也错过了理解系统为什么成立的机会。", "result_title": "你用一个数字关掉了研究", "narration": "筛选可以从比率开始，判断不能停在那里。", "next": "__legacy_reveal"},
            ]},
        ],
        "record": ("历史翻牌", "低毛利原来是主动选择", "好市多长期坚持有限加价和会员制，续费与周转共同支撑这套低毛利模式。", "好市多年报与查理·芒格公开记录", "会员制与经营模式节选", "低价吸引会员，续费积累信任，快速周转减少资本占用；三者组成同一套经营系统。"),
        "lesson": ["不要把低毛利自动翻译成差生意。先看它换来了什么。", "续费率、周转和资本回报要一起看。", "看懂好公司之后，仍要单独回答价格问题。"],
        "method": ("先画系统，再看单个比率", "低价带来什么？会员为什么续费？周转如何减少资本占用？哪一环先坏？", "零售飞轮 = 低价 × 信任 × 续费 × 周转", "低价没有带来复购和周转，或者扩张持续吞噬资本时", "低价 → 信任 → 续费 → 周转 → 回报"),
        "transfer": ("另一家低毛利零售商出现了", "怎样判断它是不是同一种生意？", ["看低价是否同时带来复购、周转和资本效率", "只要毛利率同样低，就按好市多估值"], "相同的毛利率可以来自竞争力，也可以来自卖不动。要看整个系统。"),
    },
    "soros-gbp-1992": {
        "company": "英格兰银行与英镑",
        "title": "英镑保卫战的最后一天",
        "subtitle": "1992 年 · 乔治·索罗斯面对英镑与政策约束",
        "hook": "政府承诺守住汇率，可国内经济已经承受不起德国式高利率。哪一边先让步？",
        "learning_goal": "把政策承诺、硬约束、催化时点和仓位风险分开判断。",
        "skills": ["宏观约束", "催化时点", "风险预算"],
        "cast": ("乔治·索罗斯", "量子基金经理", "故事只使用公开历史背景和政策记录，不模仿本人生成交易指令。"),
        "roles": [("researcher", "宏观研究员", "找出汇率承诺背后的硬约束", "政府公开说不会离开汇率机制。"), ("risk", "交易风控负责人", "把方向判断变成可承受的仓位", "波动正在放大，任何错误都很昂贵。"), ("allocator", "基金经理", "判断哪一个约束会先断", "窗口可能只剩几个小时。")],
        "scenes": [
            {"id": "opening", "eyebrow": "故事开始", "place": "伦敦 · 1992 年 9 月", "time": "英镑贴着汇率下限", "title": "政府说会守，经济却在往下掉", "lines": ["英国要在欧洲汇率机制内守住英镑，就不能让利率明显低于德国。", "可英国经济疲弱，德国统一后的高利率却迟迟不降。承诺和国内现实开始互相撕扯。"], "actions": [
                {"id": "map-constraints", "kind": "列出约束", "label": "分别写下守汇率和救经济各要付什么代价", "prompt": "看政策有没有同时满足两边的工具。", "consequence": "争论不再是“政府有没有决心”，而是“决心需要付出什么，能付多久”。", "result_title": "承诺背后出现了价格", "narration": "宏观判断先看约束，再看表态。", "next": "development"},
                {"id": "trust-promise", "kind": "相信承诺", "label": "央行既然公开表态，就不会后退", "prompt": "把政策信誉当成无限资源。", "consequence": "政府的话被当成事实，利率、衰退和外汇储备的代价没有进入判断。", "result_title": "一句承诺盖住了三重压力", "narration": "政策可以坚持很久，但很少能无限支付代价。", "next": "development"},
            ]},
            {"id": "development", "eyebrow": "故事发展", "place": "黑色星期三 · 交易室", "time": "加息和干预接连宣布", "title": "英镑还在下限，利率已经被推到极端", "lines": ["官方不断买入英镑，连续加息，又预告第二天进一步上调利率。", "市场仍不相信这套组合能维持。现在问题不只是方向，而是你敢把多少资金放在这个判断上。"], "actions": [
                {"id": "size-position", "kind": "控制仓位", "label": "按政策还能反击几次来倒推仓位", "prompt": "把追加保证金和政策突袭写进预算。", "consequence": "你仍然做空英镑，但仓位可以承受一次更猛烈的干预。", "result_title": "观点有了生存空间", "narration": "仓位给错误和波动预留了时间。", "next": "climax"},
                {"id": "max-position", "kind": "押注崩溃", "label": "矛盾这么明显，仓位越大越好", "prompt": "用逻辑强度决定仓位。", "consequence": "潜在收益被放大，任何临时协议、资本管制或政策突袭也会同样放大。", "result_title": "你把未知事件排除在预算外", "narration": "宏观逻辑可以清楚，路径仍然会很脏。", "next": "climax"},
            ]},
            {"id": "climax", "eyebrow": "故事高潮", "place": "伦敦时间傍晚", "time": "英镑仍守不住下限", "title": "哪一个约束会先断？", "lines": ["继续加息会进一步伤害国内经济；继续干预会消耗更多资金；退出机制会打破公开承诺。你必须选一个最可能先发生的变化。"], "final": True, "actions": [
                {"id": "a", "kind": "约束交易", "label": "做空英镑，但把政策反击算进仓位", "prompt": "押注约束，不押注政府会按你的时间表行动。", "consequence": "你保留了方向判断，也给突发政策留出承受空间。", "result_title": "你在交易约束", "narration": "宏观交易即使看对，也可能被只能赢一次的仓位毁掉。", "next": "__legacy_reveal"},
                {"id": "b", "kind": "孤注一掷", "label": "今晚一定退出，把仓位推到极限", "prompt": "把时点也当成确定事实。", "consequence": "方向和时点只要有一个偏差，保证金就可能先替你结束交易。", "result_title": "你把正确观点压成了单点成败", "narration": "方向、时点、仓位是三道题。答对一道，不会自动答对另外两道。", "next": "__legacy_reveal"},
                {"id": "c", "kind": "只信官方", "label": "政府不会食言，反向买入英镑", "prompt": "让承诺压过经济约束。", "consequence": "你站在了官方干预一边，却没有回答这项政策还能承担多少国内代价。", "result_title": "你买入了承诺", "narration": "承诺越强，越要问维持它的账单由谁支付。", "next": "__legacy_reveal"},
            ]},
        ],
        "record": ("历史翻牌", "当天晚上，英国退出汇率机制", "大规模干预和加息未能把英镑拉离下限，英国在当晚暂停参与欧洲汇率机制，并撤回进一步升息的决定。", "英格兰银行 1992 年第四季度公报", "1992 年 9 月货币政策操作", "维持原有汇率的预期成本已经高得无法承受，英国因此暂停英镑参与欧洲汇率机制。"),
        "lesson": ["政策表态要翻译成工具、成本和持续时间。", "方向、催化时点和仓位必须分别作答。", "宏观矛盾再清楚，也要给政策突袭留预算。"],
        "method": ("先找不能同时成立的目标", "政府承诺了什么？维持承诺要付什么？谁在承担成本？哪个条件最先到极限？", "宏观交易 = 硬约束 × 催化时点 × 可承受仓位", "政策拥有充足工具，而且国内经济能长期承受其成本时", "承诺 → 工具 → 成本 → 极限 → 仓位"),
        "transfer": ("另一种货币正在被官方保卫", "最先查什么？", ["查储备、利率、国内经济和维持承诺的成本", "查政府官员说话是否足够强硬"], "强硬措辞说明意愿，储备、利率和国内代价决定能力。"),
    },
}


def make_beats(cfg: dict) -> list[dict]:
    record_label, record_title, record_line, record_src, record_loc, record_quote = cfg["record"]
    method_title, rule, formula, boundary, label = cfg["method"]
    transfer_title, transfer_question, transfer_opts, transfer_fb = cfg["transfer"]
    final = cfg["scenes"][-1]["actions"]
    return [
        {"id": "s0", "kind": "cold_open", "eyebrow": "故事开始", "title": cfg["title"], "lines": [cfg["hook"], "你会先看到当时能看到的材料，做完决定以后，历史才会翻牌。"]},
        {"id": "s1", "kind": "evidence", "eyebrow": "故事发展", "title": "现在要盯住什么", "panel": {"kind": "cmp", "cols": ["表面说法", "继续追问"], "rows": [{"k": cfg["skills"][0], "a": "故事怎么讲", "b": "事实怎样支持"}, {"k": cfg["skills"][1], "a": "哪里最诱人", "b": "哪里会失效"}]}, "derived": [{"k": "这一段要学会", "v": cfg["learning_goal"]}]},
        {"id": "s2", "kind": "decision", "eyebrow": "故事高潮", "title": cfg["scenes"][-1]["title"], "prompt": cfg["scenes"][-1]["lines"][0], "options": [{"id": a["id"], "kind": a["kind"], "t": a["label"], "verdict": verdict} for a, verdict in zip(final, ("prudent", "risky", "hasty"))], "confidence": True},
        {"id": "s3", "kind": "reveal", "eyebrow": record_label, "title": record_title, "record_summary": {"src": record_src, "line": record_loc, "text": record_quote}, "lines": [record_line], "narration": "现在回头看你的选择。当时抓住决定局面的那条线，比猜中结局更重要。"},
        {"id": "s4", "kind": "contrast", "eyebrow": "收获", "title": "回看你刚才的决定", "columns": {"you": "你的选择", "them": "这次事件留下的方法", "canon": "历史记录"}, "them": {"t": cfg["lesson"][0], "detail": cfg["lesson"][1]}, "canon": {"t": record_line, "detail": cfg["lesson"][2], "src": record_src}, "knowhow": cfg["lesson"], "narration": "这次不用记住结局。记住下一次遇到类似材料时，你先查什么。"},
        {"id": "s5", "kind": "abstract", "eyebrow": "收获", "title": method_title, "story_form": cfg["hook"], "rule": rule, "formula": formula, "label": label, "boundary": boundary, "narration": "方法不是一句口号。它要能告诉你下一步去哪找证据。"},
        {"id": "s6", "kind": "twin", "eyebrow": "尾声", "title": transfer_title, "panel": {"kind": "cmp", "cols": ["先做什么", "为什么"], "rows": [{"k": "第一步", "a": "写下要验证的判断", "b": "避免先被故事带走"}, {"k": "第二步", "a": "写下判断失效的条件", "b": "给自己留下改口的证据"}]}, "question": transfer_question, "options": [{"id": "a", "t": transfer_opts[0], "ok": True}, {"id": "b", "t": transfer_opts[1], "ok": False}], "fb": transfer_fb, "narration": "你已经把这次事件里的方法带到了一个新现场。"},
    ]


def migrate(case_id: str, cfg: dict) -> None:
    path = ROOT / "content" / "stories" / case_id / "case.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update({k: cfg[k] for k in ("title", "subtitle", "company", "hook", "learning_goal", "skills")})
    name, role, intro = cfg["cast"]
    data["cast"] = [{"id": case_id.split("-")[0], "name": name, "avatar": "人物", "role": role, "intro": intro, "rule": "只引用公开记录；解释选择，不改写历史事实。"}]
    data["rpg"] = {
        "title": cfg["title"], "premise": cfg["hook"], "learning_goal": cfg["learning_goal"],
        "learning_skills": cfg["skills"], "roles": [{"id": rid, "title": title, "goal": goal, "pressure": pressure} for rid, title, goal, pressure in cfg["roles"]],
        "initial_scene": "opening", "narrator": {"name": "画外音", "voice": "中文，简短，像纪录片旁白。", "rule": "只解释玩家选择、现场压力和证据边界，不编造事实。"},
        "scenes": cfg["scenes"],
    }
    data["beats"] = make_beats(cfg)
    prov = data.setdefault("x_prov", {})
    prov.update({"drafted_by": "content-rewrite", "model": "historical-rpg-zh", "drafted_at": "2026-09-20"})
    for key in ("reviewed_by", "reviewed_at", "reviewed_hash"):
        prov.pop(key, None)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    for cid, config in CASES.items():
        migrate(cid, config)
        print(f"migrated {cid}")
