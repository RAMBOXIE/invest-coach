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

三个职责，别的一概不做（契约见 `docs/形态规格_故事驱动.md` §6）：

- `POST /api/v1/events` —— 匿名遥测，append-only
- `POST /api/v1/ask-coach` —— 追问的**语义路由**（登记簿 #8）
- `POST /api/v1/review-note` —— 教练读你写下的推理，写回两三句（登记簿 #9）

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

现有常开机器 + cloudflared named tunnel（免费、固定域名）。
`quick tunnel` 每次重启换地址，只适合临时联调。
