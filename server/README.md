# 轻后端

## 一份实现

`server.py`，标准库跑，零第三方依赖。

原来有两份：`main.go`（声明的主线、可部署）与 `server.py`（联调用、不收口）。
2026-09-02 查出来主线那份**没有打码**——部署它等于用户的持仓金额与联系方式
原样进第三方模型、原样入库，而这正是 D3 裁决明令禁止的。于是主线改成了 Python 版。

**接着把 Go 版删了。** 理由不是「Python 更好」，是**两份实现的差异只能靠形状比对**：
门禁能查「端点在不在」，查不了「这份的打码和那份等价」。而这台机器没有 Go，
补出来的隐私代码编译不了、跑不了、验不了——写一段没验过的打码代码放在主线上，
比只有一份实现危险得多。Go 版唯一比 Python 版多的东西（`ALLOWED_ORIGINS`
Origin 收口）已经搬过来了。要回滚看 git 历史。

环境变量：`CLAUDE_API_KEY`（未设则 ask-coach 直接回 none）、`DB_PATH`（空则不落库）、
`ALLOWED_ORIGINS`（逗号分隔；**空表示全放行，只可用于本机联调**；
file:// 打开的产物 Origin 是字符串 `null`，要放行就显式写 `null`）、`PORT`（默认 8971）。

隐私承诺（D3）不靠读代码确认，靠跑一遍：

```bash
python tools/check_server.py            # P1 打码分语境 / P2 出口检查 / P3 90 天留存 / P4 Origin 收口 / P5 打码先于调模型
python tools/check_server.py --selftest # 变异测试：把这五样逐个弄坏，看门禁会不会红
```

四个职责，别的一概不做（契约见 `docs/形态规格_故事驱动.md` §6）：

- `POST /api/v1/events` —— 匿名遥测，append-only
- `POST /api/v1/ask-coach` —— 追问的**语义路由**（登记簿 #8）：只返回一个证词 id，作为 #10 的回落
- `POST /api/v1/review-note` —— 教练读你写下的推理，写回两三句（登记簿 #9）
- `POST /api/v1/discuss` —— **决策人复盘对话**（登记簿 #10，ADR-0004）：LLM 以幕里的当事人身份、
  当年口吻，只凭前端喂进来的 reveal 之前的材料回答；出口检查 `check_discuss` 挡材料外的数字、
  后见之明、荐股、出戏，任一命中整条丢弃，前端回落到 #8

## 关键设计：LLM 只返回 id，不生成答案

请求带上该幕已冻结语料的「可问方向」清单；LLM 的**全部输出**是 `{"id":"..."}`。
答案文本永远由前端从 `case.json` 里取。所以：

- LLM 物理上无法编造事实、数字与公司名——它不产出文本
- 返回的 id 不在清单里 → 服务端直接作废
- 无后端 / 超时 6s / 返回 none → 前端静默回落本地关键词匹配，**离线可用**

## 跑起来

```bash
export CLAUDE_API_KEY=sk-ant-...                 # 未设置则 ask-coach 直接返回 none（前端回落）
export DB_PATH=ic.db                             # 可选；未设置则不落库，仅作代理
export ALLOWED_ORIGINS=https://your.domain       # 对公网暴露前必须设
python server/server.py                          # 默认 :8971
```

前端构建时把地址烧进去：

```bash
python tools/build.py --backend https://your-tunnel.example.com
```

## 部署

分两件事：**前端静态托管**与**后端进程**。它们的部署方式不一样，别混在一起想。

### 前端：静态托管（Netlify / 任意静态托管）

产物是单个 HTML，不需要构建环境、不需要运行时。

```bash
python tools/build.py                 # 不带 --backend：BACKEND=null，纯离线
# 产物在 dist/index.html；dist/netlify/ 是可直接拖拽的部署目录
```

`dist/netlify/` 里带 `netlify.toml`，只做一件事：**`X-Robots-Tag: noindex` + robots.txt**。
内容里有真实人物姓名与 SEC 认定段落，而 `validate --release` 在 19 项签字完成之前是 FAIL。
签字完成之前，这个站点只应当靠链接分享，不应当出现在搜索结果里。

CSP 也在那份配置里收口过：产物零外部加载，所以除了内联 script/style 必需的
`'unsafe-inline'`，其余全部 `'self'`。**接后端时要把该域名加进 `connect-src`**，否则请求会被浏览器挡掉。

仓库没有 git 远端且 `dist/` 在 `.gitignore` 里，所以 Netlify 的 git 自动部署需要先推仓库，
并把构建命令设成 `python tools/build.py`（好处是十道门禁在 CI 里跑，不合格就部署不了）。
不想推仓库就拖拽 `dist/netlify/`，或 `netlify deploy --dir=dist/netlify --prod`。

### 后端：**不要**改写成 serverless Functions

Netlify Functions 只支持 JavaScript / TypeScript / Go，**不支持 Python**。
把 `server.py` 的四个端点改写成 JS，等于制造**第二份隐私关键代码的实现**
（`mask_pii` / `check_note` / `check_discuss`）——而这正是 D9 记的那笔债：
两份实现的差异只能靠形状比对，门禁查得了「端点在不在」，查不了「这份的打码和那份等价」。
2026-09-02 删掉 Go 版就是为了还这笔债，不要用 JS 再借一次。

serverless 还有第二个硬伤：没有本地磁盘。sqlite 的三张表、90 天留存的 `purge_old`、
以及 ADR-0001 前置条件 2 要求的「判分理由可回放」的 trace，都得换成外部存储。

**正确的切法**：静态托管只托前端，`server.py` 仍是唯一实现，跑在一台常开机器上
（现有常开机器 + cloudflared named tunnel，免费、固定域名；`quick tunnel` 每次重启换地址，
只适合临时联调）。前端构建时用 `--backend https://你的域名` 指过去，
同时把 `ALLOWED_ORIGINS` 设成前端所在的域名——否则那台服务就是谁都能调的公开模型代理。

