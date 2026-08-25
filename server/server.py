#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""invest-coach 轻后端 · Python 版（零第三方依赖，标准库即可跑）。

与 server/main.go 同契约。两个职责：
  POST /api/v1/events     匿名遥测
  POST /api/v1/ask-coach  质问的语义路由

**关键设计：LLM 只返回命中的证词 id，绝不生成台词。**
人物说的每一句永远来自前端已冻结的 case.json。所以模型物理上无法编造
事实、数字与公司名——它只回答「用户想戳的是哪一条」。

跑起来：
    set CLAUDE_API_KEY=sk-ant-...          # Windows: set / PowerShell: $env:
    python server/server.py                # 默认 :8971
然后重新构建前端，把地址烧进去：
    python tools/build.py --backend http://localhost:8971
"""
import json, os, sqlite3, sys, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_KEY = os.environ.get("CLAUDE_API_KEY", "")
MODEL = os.environ.get("IC_MODEL", "claude-haiku-4-5-20251001")
PORT = int(os.environ.get("PORT", "8971"))
DB_PATH = os.environ.get("DB_PATH", "")           # 空则不落库
DAILY_PER_DEVICE = 60                              # 成本控制，不是安全控制
MAX_Q = 200

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
        o = self.headers.get("Origin") or "*"
        self.send_header("Access-Control-Allow-Origin", o)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._send({"ok": True, "llm": bool(API_KEY), "model": MODEL if API_KEY else None})
        else:
            self._send({"ok": False}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(min(n, 1 << 20))
        if self.path == "/api/v1/events":
            if db():
                db().execute("INSERT INTO events(payload, at) VALUES(?,?)", (raw.decode("utf-8", "replace"), int(time.time())))
                db().commit()
            return self._send({"ok": True})

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
            db().execute("INSERT INTO asks(case_id, q, matched, at) VALUES(?,?,?,?)",
                         (req.get("case_id"), q, rid, int(time.time())))
            db().commit()
        self._send({"id": rid, "source": "llm"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"invest-coach server :{PORT}  LLM={'on · ' + MODEL if API_KEY else 'off（前端会静默回落本地匹配）'}")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
