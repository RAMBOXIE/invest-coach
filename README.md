# invest-coach 投资教练

跟着教练在历史实战里一天几分钟地做决策——教练盯的不是你对没对，而是你的判断习惯。

单文件 HTML 知识图谱学习站（改造自 [agent-graph-learning](https://github.com/Lichangfocus/agent-graph-learning)
的 learn-map，见 `NOTICE.md`）+ 极简后端（匿名遥测 + 证词语义路由）。

**仅供学习。全部内容为历史案例复盘，不构成投资建议，不含任何前瞻信号或收益承诺。**

## 跑起来

```bash
python tools/build.py
```

内部先跑内容校验，再跑四道门禁，任一 FAIL 即构建不合格。产物是
`dist/index.html`——单文件，`file://` 双击可用。

本地起服务实测（改完视觉必须实测，门禁看不见上下文）：

```bash
python -m http.server 8791 --directory dist
```

## 目录

```
content/ch1/            第一章内容源 site.json + 数字账本 facts.json（图已冻结 ch1-graph-v1）
content/stories/        三幕故事的骨架层，每幕一份 case.json
evidence/               原档存档 + sha256 锚定，只增不改
design/                 tokens.json 视觉真源 · token-debt.json 字面值棘轮基线
src/                    template.html 骨架 + parts/*.{css,js}，构建期拼装
tools/                  build / validate + 四道门禁 + fetch_current / render_review
server/                 轻后端：main.go 是主线，server.py 是零依赖联调用
docs/                   文档四层，索引见 docs/README.md
dist/                   构建产物（gitignore）
```

完整登记表与目录纪律见 [docs/STRUCTURE.md](docs/STRUCTURE.md)（`validate.py` R26 强校验）。

## 文档从哪读

**[docs/README.md](docs/README.md)** 是索引。四层：

- **契约层** —— 改代码之前要读的，[DESIGN.md](DESIGN.md) / SPEC_DEV / STRUCTURE / SCHEMA / LLM 登记簿 / 知识可靠性 / 形态规格
- **裁决层** —— `docs/adr/`，被重新争论过的问题只在这里定案
- **记录层** —— `docs/records/`，审计留档
- **已被取代** —— `docs/_superseded/`，只作历史，不要照着做

用 Claude Code 开发看 [CLAUDE.md](CLAUDE.md)。

## 状态

| 阶段 | 状态 |
|---|---|
| 第一章内容（14 节点 + 24 道复训 + 数字账本） | ✅ |
| 三幕故事（Sunbeam 1998 / Lehman 2008 / Buffett 1993）+ 质问台 | ✅ |
| 组站（模板 + 令牌管线 + 五道门禁） | ✅ |
| 后端（遥测 + 证词语义路由） | ✅ 未部署 |
| **人工逐条签字（G1/G2）** | ❌ **14/14 节点未签**，`validate --release` 会拒绝 |
| QA / `poc-trial` 定版 / 十人试用 | ❌ |

会挡住发布的欠账都在 [docs/DEBT.md](docs/DEBT.md)。

上游产品文档：`research/投资教练_收敛_v3.md`（与 xtrader 代码零耦合）。
