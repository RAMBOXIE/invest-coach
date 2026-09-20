#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""invest-coach 轻后端 · Python 版（零第三方依赖，标准库即可跑）。

与 server/main.go 同契约。两个职责：
  POST /api/v1/events     匿名遥测
  POST /api/v1/ask-coach   追问的语义路由
  POST /api/v1/review-note 教练读你写的那段推理，写回一段话
  POST /api/v1/discuss     决策人复盘对话（幕里当事人，当年口吻）
  POST /api/v1/next-steps  D14：答对「无法判断」后，教练讨论下一步该去查什么（只谈方法）

**ask-coach 的关键设计：LLM 只返回命中的陈述 id，绝不生成台词。**
人物说的每一句永远来自前端已冻结的 case.json。所以模型物理上无法编造
事实、数字与公司名，它只回答「用户想问的是哪一条」。

**review-note 是另一回事，它必须生成散文。** 走 ADR-0001 铺好的那条路：
只回应开放文本、不计分、只作第二意见、判分仍由前端规则完成。
「事实不出自 LLM」这条铁律在这里不能靠提示词，靠的是出口检查——
模型输出里出现的每一个数字都必须在我们喂给它的已核定材料里出现过，
否则整条丢弃、回落本地反馈。见 OUT_NUM 与 check_note。

跑起来：
    set CLAUDE_API_KEY=sk-ant-...          # Windows: set / PowerShell: $env:
    python server/server.py                # 默认 :8971
然后重新构建前端，把地址烧进去：
    python tools/build.py --backend http://localhost:8971
"""
import json, os, re, sqlite3, sys, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_KEY = os.environ.get("CLAUDE_API_KEY", "")
MODEL = os.environ.get("IC_MODEL", "claude-haiku-4-5-20251001")
PORT = int(os.environ.get("PORT", "8971"))
DB_PATH = os.environ.get("DB_PATH", "")           # 空则不落库
DAILY_PER_DEVICE = 60                              # 成本控制，不是安全控制
MAX_Q = 200

# ── Origin 收口 ──────────────────────────────────────────────
#
# 从 main.go 搬过来的唯一一样 Python 版没有的东西。原来的分工是
# 「Go 收口、可以对公网；Python 不收口、只准本机」——而 2026-09-02 起
# 主线是 Python 版（Go 版没有打码）。于是「主线」既是唯一能部署的那份，
# 又是唯一不收口的那份。两份实现，谁也不完整。
#
# 这不是身份认证：curl 想伪造 Origin 随时可以。它挡的是「别的网页把
# 这台服务当成免费的模型代理」，和 DAILY_PER_DEVICE 是同一类东西。
# 真正的边界是出口检查（check_note）与 id 白名单，那两条挡的是内容。
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]


def origin_ok(origin):
    """空表 = 开发模式，全放行（启动时会喊一声）。

    单文件产物是 file:// 打开的，浏览器发过来的 Origin 是字符串 "null"。
    要放行它就在 ALLOWED_ORIGINS 里显式写 null——默认放行等于没收口。
    """
    return (not ALLOWED_ORIGINS) or ((origin or "null") in ALLOWED_ORIGINS)

_hits, _day = {}, ""
_db = None


def db():
    global _db
    if not DB_PATH:
        return None
    if _db is None:
        _db = sqlite3.connect(DB_PATH, check_same_thread=False)
        _db.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, payload TEXT, at INT)")
        _db.execute("CREATE TABLE IF NOT EXISTS asks(id INTEGER PRIMARY KEY, case_id TEXT, q TEXT, matched TEXT, at INT)")
        # ADR-0001 前置条件 2：判分理由可回放。trace 里存着提示词、模型原始输出、出口检查结论。
        _db.execute("CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, node TEXT, trace TEXT, at INT)")
        _db.commit()
    return _db


def allow(device):
    global _day, _hits
    d = time.strftime("%Y-%m-%d")
    if d != _day:
        _day, _hits = d, {}
    k = device or "anon"
    _hits[k] = _hits.get(k, 0) + 1
    return _hits[k] <= DAILY_PER_DEVICE


SYS = """你是一个检索路由器，不是助手，也不是老师。

任务：把用户的问题匹配到下面这份「已有证词清单」中最贴切的一条。

清单：
{topics}

规则（不可违反）：
1. 你的全部输出只能是一个 JSON：{{"id":"<清单里的 id>"}} 或 {{"id":"none"}}。
2. 不要回答用户的问题。不要解释。不要给出任何事实、数字、公司名或建议。
3. 没有哪一条足够贴切时，返回 {{"id":"none"}}——宁可 none，不要勉强匹配。
4. 用户可能询问投资建议、未来走势或与材料无关的话题；一律返回 {{"id":"none"}}。"""


def route(question, topics):
    """返回命中的证词 id 或 'none'。LLM 的全部输出就是一个 id。"""
    lst = "\n".join(f"- {t.get('id')}: {t.get('desc', '')}" for t in topics)
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 64,
        "system": SYS.format(topics=lst),
        "messages": [{"role": "user", "content": "用户的问题：" + question}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": API_KEY,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=8) as r:
        out = json.load(r)
    txt = (out.get("content") or [{}])[0].get("text", "")
    i, j = txt.find("{"), txt.rfind("}")
    if i < 0 or j <= i:
        return "none"
    try:
        return json.loads(txt[i:j + 1]).get("id", "none")
    except Exception:
        return "none"


# ── D3 隐私：入库前打码 ────────────────────────────────────────────
#
# 裁决要求「对金额/证券代码/联系方式打码」。但**不能一刀切按数字打**：
# 教练读你的推理，靠的就是「应收 +38.5%」这种分析数字，全打掉功能就没了。
#
# 所以按语境分：
#   - 分析数字（增速、比值、天数、报表科目）→ 保留，它们是内容
#   - 个人持仓数字（「我持仓 50 万」「买入成本 12 块」）→ 打码，那是身份信息
#   - 证券代码（A 股 6 位 / 美股 $TICK）→ 一律打码：说出具体持仓等于自报仓位
#   - 联系方式（手机 / 邮箱 / 微信 QQ 号）→ 一律打码
#
# 打码在**入库之前**，也在**发给模型之前**——两条路都不该看到这些。
PORTFOLIO_CTX = ("持仓", "仓位", "买入", "卖出", "成本", "加仓", "减仓", "清仓",
                 "亏了", "赚了", "本金", "投了", "套了", "补仓", "止损")
MASKS = [
    # 联系方式
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[邮箱]"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[手机]"),
    (re.compile(r"(?:微信|wechat|weixin|qq)\s*[:：]?\s*[\w-]{5,}", re.I), "[联系方式]"),
    # 证券代码：A 股 6 位（0/3/6 开头）、港股 5 位带 HK、美股 $TICK
    (re.compile(r"(?<![\d.])(?:[036]\d{5})(?![\d.%])"), "[代码]"),
    (re.compile(r"\$[A-Z]{1,5}\b"), "[代码]"),
    (re.compile(r"\b(?:HK|hk)\.?\d{4,5}\b"), "[代码]"),
]
AMOUNT = re.compile(r"\d[\d,.]*\s*(?:万元|亿元|万|亿|元|块|美元|港币|USD|RMB)")


def mask_pii(text):
    """入库与送模型之前都走这一道。返回 (打码后的文本, 打了几处)。"""
    if not text:
        return text, 0
    n = 0
    for pat, rep in MASKS:
        text, k = pat.subn(rep, text)
        n += k
    # 金额只在**持仓语境**里打：句子里出现持仓类动词才算个人财务信息
    def amt(m):
        nonlocal n
        lo = max(0, m.start() - 18)
        if any(w in text[lo:m.end() + 18] for w in PORTFOLIO_CTX):
            n += 1
            return "[金额]"
        return m.group(0)
    text = AMOUNT.sub(amt, text)
    return text, n


# 留存期：裁决是 90 天。每次落库时顺手清一次过期的——
# 单实例部署没有定时任务，把清理挂在写入路径上是最不容易忘的做法。
RETAIN_DAYS = 90


def purge_old():
    if not db():
        return
    cut = int(time.time()) - RETAIN_DAYS * 86400
    for t in ("events", "asks", "notes"):
        db().execute(f"DELETE FROM {t} WHERE at < ?", (cut,))
    db().commit()


NOTE_SYS = """你是一个财报判断训练产品里的教练。学习者刚刚用自己的话写下了他对一份材料的判断。

你的任务：**回应他写的这段话**，帮他看清自己的推理里有什么、缺什么。

这一关的已核定材料（你只能用这里面的内容，一个字都不能超出）：

{material}

规则（不可违反）：
1. **不判对错，不给分。** 判分由页面内置规则完成，不归你管。你是第二意见。
2. **不许引入任何新的事实、数字、公司名、年份。** 上面材料里没有的，
   你一个字都不能写。需要提到数字时，只能用材料里出现过的。
3. **回应他真正写了什么。** 指出他抓到了哪一条、漏了哪一条、
   哪一步推理跨过去了。不要泛泛地夸或泛泛地否定。
4. 他可能什么也没写、写得很短、或者写的和题目无关。那就如实说，不要硬夸。
5. **不给投资建议**，不评价任何公司现在值不值得买。
6. 中文，**两到三句**，不用破折号，不用「不是 X 而是 Y」这种对偶句式。
   像一个坐在旁边看他做题的人说话，不像一份评语。"""


# 出口检查用：模型输出里出现的数字
OUT_NUM = re.compile(r"\d+(?:[,.]\d+)*")


def check_note(text, material):
    """「事实不出自 LLM」是铁律，不能只写在提示词里。

    出口检查：模型写出的每一个数字，都必须在我们喂给它的已核定材料里出现过。
    不合格就整条丢弃，前端回落本地反馈——宁可没有教练回应，
    也不能让一个编出来的数字挂上「教练」两个字。
    """
    if not text or len(text) > 400:
        return None, "空或过长"
    nums = set(OUT_NUM.findall(text))
    allowed = set(OUT_NUM.findall(material))
    bad = [n for n in nums if n not in allowed and n.strip(".,") not in allowed]
    if bad:
        return None, f"出现材料里没有的数字 {bad[:3]}"
    for w in ("建议买入", "建议卖出", "目标价", "推荐"):
        if w in text:
            return None, f"出现越界措辞「{w}」"
    return text, ""


def review_note(note, material):
    """返回 (教练的话, 可回放的记录)。任一环节出问题都返回 (None, 记录)。"""
    sys_p = NOTE_SYS.format(material=material)
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 400,
        "system": sys_p,
        "messages": [{"role": "user", "content": "学习者写的：\n" + note}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": API_KEY,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.load(r)
    raw = (out.get("content") or [{}])[0].get("text", "").strip()
    text, why = check_note(raw, material)
    # ADR-0001 前置条件 2：判分理由必须可回放。存下提示词、原始输出、检查结论。
    trace = {"system": sys_p, "note": note, "raw": raw, "kept": bool(text), "rejected": why}
    return text, trace


# ── #10 决策人复盘对话 ─────────────────────────────────────────
#
# owner 2026-09-03 的产品定义：「LLM 会扮演当时事件中的关键决策人，和用户一起讨论
# 为什么当时有这样的决策。」这是 #8（只返回一个证词 id）到「能讨论」的升级，
# 也是 #5（自由散文）被放弃之后第一次把散文放回幕里。能放回来靠的是三道确定性闸：
#
#   1. 材料闸：模型看得见的只有前端喂进来的当年材料（reveal 之前的拍、他的陈述、
#      追问与出证的原文、证据卡）。结局不在里面，他就说不出结局。
#   2. 出口闸 check_discuss：数字必须出现在材料里；后见之明词、投资建议、
#      「我是 AI」式出戏，任一命中整条丢弃，前端回落到逐字原话匹配。
#   3. 标注闸（前端）：这段话在屏上标红为「LLM 扮演 · 某某说」，明写不是原档逐字；
#      带行号的陈述仍然只来自 case.json。
#
# 他讨论的是**材料里写过的理由**，不是编出来的动机。材料里没有的，他说「文件里没有写」。
DISCUSS_SYS = """你现在是 {name}，{role}。时间是 {era} 年。一位学习者在和你讨论你当时的决策与说法。

你只知道下面这些材料里写的事，一个字都不能超出：

{material}

规则（不可违反）：
1. 你不知道 {era} 年之后发生的任何事。不许说「后来」「最终」「事后」「重述」「破产」「被认定」。你活在当时。
2. 你说的每一个数字都必须来自上面的材料。材料里没有的事，如实说「这份文件里没有写」。
3. 用第一人称、当年的口吻，替你当时的决策说明理由；理由只能来自材料里你自己写过、或公司披露过的话。
   可以被追问，可以承认材料里的矛盾，但不许编造动机，不许引入材料之外的事实。
4. 不给投资建议，不评论任何股票值不值得买，不预测。
5. 中文，两到四句，不用破折号，不用「不是 X 而是 Y」这种对偶。像一个人在回答，不像一份声明。
6. 不要说你是 AI、模型或助手，不要说「作为 {name}」。屏上会另行标注这是 AI 推演，你只管以他的身份回答。"""

# 后见之明：他活在当年，这些词一出现就是出戏
HINDSIGHT = ("后来", "最终", "事后", "重述", "破产", "被认定", "认定为", "被起诉", "判刑",
             "真相", "如今", "回头看", "多年以后", "历史证明", "事实证明")
# 出戏：屏上已经标了 AI 推演，人物自己再跳出来说「我是 AI」会让用户不知道在和谁说话
BREAK_CHAR = ("作为 AI", "作为AI", "语言模型", "我是 AI", "我是AI", "AI 助手", "人工智能", "作为一个模型")
ADVICE = ("建议买入", "建议卖出", "建议持有", "目标价", "推荐", "值得买", "值得投资", "会涨", "会跌")


def check_discuss(text, material, era):
    """决策人那段话的出口检查。任一不合格整条丢弃，前端回落到逐字原话。"""
    if not text or len(text) > 600:
        return None, "空或过长"
    allowed = set(OUT_NUM.findall(material)) | {str(era)}
    bad = [n for n in set(OUT_NUM.findall(text)) if n not in allowed and n.strip(".,") not in allowed]
    if bad:
        return None, f"出现材料里没有的数字 {bad[:3]}"
    for w in HINDSIGHT:
        if w in text:
            return None, f"出现后见之明「{w}」"
    for w in ADVICE:
        if w in text:
            return None, f"出现越界措辞「{w}」"
    for w in BREAK_CHAR:
        if w in text:
            return None, f"出戏「{w}」"
    return text, ""


def discuss(persona, era, material, history, question):
    """LLM 以当事人身份回应一个问题。返回 (文本或 None, 可回放记录)。"""
    sys_p = DISCUSS_SYS.format(name=persona.get("name", "当事人"), role=persona.get("role", ""),
                               era=era, material=material)
    msgs = []
    for h in (history or [])[-6:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": str(h["content"])[:600]})
    if msgs and msgs[0]["role"] != "user":
        msgs = msgs[1:]
    msgs.append({"role": "user", "content": question})
    body = json.dumps({"model": MODEL, "max_tokens": 500, "system": sys_p, "messages": msgs}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": API_KEY,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.load(r)
    raw = (out.get("content") or [{}])[0].get("text", "").strip()
    text, why = check_discuss(raw, material, era)
    trace = {"system": sys_p, "history": msgs, "raw": raw, "kept": bool(text), "rejected": why}
    return text, trace


# ── D14：答对「无法判断」之后，教练讨论「下一步该去查什么」 ────────────────
#
# 这不是决策人复盘（那是幕里的当事人），是**教练就方法展开讨论**。用户已经由规则判为答对
# （na=正确，判分不经模型，铁律不破）；模型只在这之后讨论「为什么先查这个、具体怎么查」。
# 它拿到的只有这道题的题干、区分线索(key)、以及人工写好的固定清单(x_next)——全是方法，
# 不含任何真实公司的事实，所以模型也无从产出事实。出口闸挡投资建议与出戏。
NEXTSTEPS_SYS = """你是一位投资学习教练。学习者刚在一道题上正确判断出「信息不足、无法下结论」。
这一步的功课就是：承认证据不够，然后知道接下来该去补哪些证据。

这道题、区分这类判断的线索、以及该去查的方向如下（你只能依据这些，不得引入任何具体公司的数字或事实）：

{seed}

规则（不可违反）：
1. 只讨论方法与流程：为什么要先查这几项、具体去哪查、查到什么样算够。
2. 不给任何投资建议，不评论任何股票值不值得买，不预测涨跌，不报目标价。
3. 不编造任何具体公司的数字或事实；这里没有真实公司，只谈通用方法。
4. 中文，两到四句，像教练在点拨，不用破折号，不用「不是 X 而是 Y」这种对偶。
5. 不要说你是 AI、模型或助手；屏上会另行标注这是 AI 教练推演。"""


def check_nextsteps(text):
    """D14 出口闸：只讲方法，不许越界成投资建议或出戏。任一命中整条丢弃，前端回落到 x_next。"""
    if not text or len(text) > 600:
        return None, "空或过长"
    for w in ADVICE:
        if w in text:
            return None, f"出现越界措辞「{w}」"
    for w in BREAK_CHAR:
        if w in text:
            return None, f"出戏「{w}」"
    return text, ""


def nextsteps(seed, history, question):
    """教练就「下一步该去查什么」展开讨论。返回 (文本或 None, 可回放记录)。"""
    sys_p = NEXTSTEPS_SYS.format(seed=seed)
    msgs = []
    for h in (history or [])[-6:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": str(h["content"])[:600]})
    if msgs and msgs[0]["role"] != "user":
        msgs = msgs[1:]
    msgs.append({"role": "user", "content": question})
    body = json.dumps({"model": MODEL, "max_tokens": 500, "system": sys_p, "messages": msgs}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": API_KEY,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.load(r)
    raw = (out.get("content") or [{}])[0].get("text", "").strip()
    text, why = check_nextsteps(raw)
    return text, {"system": sys_p, "history": msgs, "raw": raw, "kept": bool(text), "rejected": why}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, obj, code=200):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)

    def _cors(self):
        o = self.headers.get("Origin")
        if not origin_ok(o):
            return          # 不发 ACAO 头，浏览器那边就拿不到响应体
        self.send_header("Access-Control-Allow-Origin", o or "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def _blocked(self):
        """Origin 不在白名单：403，不进业务逻辑，也不烧模型额度。"""
        if origin_ok(self.headers.get("Origin")):
            return False
        raw = json.dumps({"ok": False, "why": "origin not allowed"}).encode()
        self.send_response(403)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
        return True

    def do_OPTIONS(self):
        if self._blocked():
            return
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self._blocked():
            return
        if self.path == "/health":
            self._send({"ok": True, "llm": bool(API_KEY), "model": MODEL if API_KEY else None})
        else:
            self._send({"ok": False}, 404)

    def do_POST(self):
        if self._blocked():
            return
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(min(n, 1 << 20))
        if self.path == "/api/v1/events":
            if db():
                db().execute("INSERT INTO events(payload, at) VALUES(?,?)", (raw.decode("utf-8", "replace"), int(time.time())))
                db().commit()
            return self._send({"ok": True})

        if self.path == "/api/v1/review-note":
            return self._review(raw)
        if self.path == "/api/v1/discuss":
            return self._discuss(raw)
        if self.path == "/api/v1/next-steps":
            return self._nextsteps(raw)

        if self.path != "/api/v1/ask-coach":
            return self._send({"ok": False}, 404)

        try:
            req = json.loads(raw or b"{}")
        except Exception:
            return self._send({"id": "none", "source": "fallback"})

        q = (req.get("question") or "").strip()
        topics = req.get("topics") or []
        if not q or len(q) > MAX_Q or not topics or not API_KEY or not allow(req.get("device")):
            return self._send({"id": "none", "source": "fallback"})

        try:
            rid = route(q, topics)
        except Exception as e:
            sys.stderr.write(f"route err: {e}\n")
            return self._send({"id": "none", "source": "fallback"})

        # 出口白名单：只允许返回我们给过它的 id
        if rid != "none" and not any(t.get("id") == rid for t in topics):
            sys.stderr.write(f"unknown id {rid!r} — 丢弃\n")
            rid = "none"
        if db():
            mq, _ = mask_pii(q)
            db().execute("INSERT INTO asks(case_id, q, matched, at) VALUES(?,?,?,?)",
                         (req.get("case_id"), mq, rid, int(time.time())))
            db().commit()
            purge_old()
        self._send({"id": rid, "source": "llm"})

    def _review(self, raw):
        """教练读学习者写的那段推理。任何一环出问题都回 {"text": null}，
        前端据此回落到本地反馈——降级路径是 ADR-0001 的前置条件 4。"""
        try:
            req = json.loads(raw or b"{}")
        except Exception:
            return self._send({"text": None, "source": "fallback"})
        note = (req.get("note") or "").strip()
        material = (req.get("material") or "").strip()
        if (not note or len(note) > 1200 or not material or not API_KEY
                or not allow(req.get("device"))):
            return self._send({"text": None, "source": "fallback"})
        # **打码在送模型之前**，不只是入库之前。
        # 只在入库前打，等于用户的持仓和联系方式已经进过第三方模型了——
        # 那时候再打码只是让我们的数据库好看，对用户没有意义。
        note, nmask = mask_pii(note)
        try:
            text, trace = review_note(note, material)
            trace["masked"] = nmask
        except Exception as e:
            sys.stderr.write(f"review err: {e}\n")
            return self._send({"text": None, "source": "fallback"})
        if not text:
            sys.stderr.write(f"review 出口检查丢弃：{trace.get('rejected')}\n")
        if db():
            db().execute(
                "INSERT INTO notes(node, trace, at) VALUES(?,?,?)",
                (req.get("node"), json.dumps(trace, ensure_ascii=False), int(time.time())))
            db().commit()
            purge_old()
        return self._send({"text": text, "source": "llm" if text else "fallback"})

    def _discuss(self, raw):
        """决策人复盘对话。任何一环出问题都回 {"text": null}，前端回落到逐字原话匹配。"""
        try:
            req = json.loads(raw or b"{}")
        except Exception:
            return self._send({"text": None, "source": "fallback"})
        q = (req.get("question") or "").strip()
        material = (req.get("material") or "").strip()
        persona = req.get("persona") or {}
        era = req.get("era") or ""
        if (not q or len(q) > 300 or not material or not persona.get("name") or not API_KEY
                or not allow(req.get("device"))):
            return self._send({"text": None, "source": "fallback"})
        q, nmask = mask_pii(q)                      # 打码先于调模型，和 review-note 同一条纪律
        try:
            text, trace = discuss(persona, era, material, req.get("history") or [], q)
            trace["masked"] = nmask
        except Exception as e:
            print("discuss err:", e, file=sys.stderr)
            return self._send({"text": None, "source": "fallback"})
        if not text:
            print("discuss 出口检查丢弃：", trace.get("rejected"), file=sys.stderr)
        if db():
            db().execute("INSERT INTO notes(node, trace, at) VALUES(?,?,?)",
                         ("discuss:" + str(req.get("case_id")), json.dumps(trace, ensure_ascii=False), int(time.time())))
            db().commit()
            purge_old()
        return self._send({"text": text, "source": "llm" if text else "fallback"})

    def _nextsteps(self, raw):
        """D14：答对「无法判断」后的方法讨论。任何一环出问题回 {"text": null}，前端回落到 x_next。"""
        try:
            req = json.loads(raw or b"{}")
        except Exception:
            return self._send({"text": None, "source": "fallback"})
        q = (req.get("question") or "").strip()
        seed = (req.get("seed") or "").strip()      # 题干 + key + x_next，全是方法，前端拼好传入
        if (not q or len(q) > 300 or not seed or not API_KEY or not allow(req.get("device"))):
            return self._send({"text": None, "source": "fallback"})
        q, nmask = mask_pii(q)                       # 打码先于调模型，同一条纪律
        try:
            text, trace = nextsteps(seed, req.get("history") or [], q)
            trace["masked"] = nmask
        except Exception as e:
            print("nextsteps err:", e, file=sys.stderr)
            return self._send({"text": None, "source": "fallback"})
        if not text:
            print("nextsteps 出口检查丢弃：", trace.get("rejected"), file=sys.stderr)
        if db():
            db().execute("INSERT INTO notes(node, trace, at) VALUES(?,?,?)",
                         ("nextsteps:" + str(req.get("quiz_id")), json.dumps(trace, ensure_ascii=False), int(time.time())))
            db().commit()
            purge_old()
        return self._send({"text": text, "source": "llm" if text else "fallback"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"invest-coach server :{PORT}  LLM={'on · ' + MODEL if API_KEY else 'off（前端会静默回落本地匹配）'}")
    print("Origin 收口：" + ("、".join(ALLOWED_ORIGINS) if ALLOWED_ORIGINS else
          "**未设置 ALLOWED_ORIGINS——任何网页都能调这台服务，只可用于本机联调**"))
    print(f"落库：{DB_PATH or '关（仅作代理）'}　留存 {RETAIN_DAYS} 天")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
