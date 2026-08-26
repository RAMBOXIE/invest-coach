# 轻后端

## 两套实现

| 文件 | 定位 | 何时用 |
|---|---|---|
| `main.go` | **主线**，部署用 | 生产 / 隧道演示 |
| `server.py` | 零依赖联调用，同契约 | 本机快速验证，**不做 origin 收口，禁止对公网暴露** |

两者环境变量对照：`CLAUDE_API_KEY` 相同；Go 用 `DB_DSN`，Python 用 `DB_PATH`；
`ALLOWED_ORIGINS` **只有 Go 支持**。

两个职责，别的一概不做（契约见 `docs/形态规格_故事驱动.md` §6）：

- `POST /api/v1/events` —— 匿名遥测，append-only
- `POST /api/v1/ask-coach` —— 「问人物」的**语义路由**

## 关键设计：LLM 只返回 id，不生成答案

请求带上该幕已冻结语料的「可问方向」清单；LLM 的**全部输出**是 `{"id":"..."}`。
答案文本永远由前端从 `case.json` 里取。所以：

- LLM 物理上无法编造事实、数字与公司名——它不产出文本
- 返回的 id 不在清单里 → 服务端直接作废
- 无后端 / 超时 6s / 返回 none → 前端静默回落本地关键词匹配，**离线可用**

## 跑起来

```bash
export CLAUDE_API_KEY=sk-ant-...        # 未设置则 ask-coach 直接返回 none（前端回落）
export DB_DSN=file:ic.db                # 可选；未设置则不落库，仅作代理
export ALLOWED_ORIGINS=https://your.domain
go run ./server
```

前端构建时把地址烧进去：

```bash
python tools/build.py --backend https://your-tunnel.example.com
```

## 部署

现有常开机器 + cloudflared named tunnel（免费、固定域名）。
`quick tunnel` 每次重启换地址，只适合临时联调。
