# 目录登记表

> **这是目录的唯一真源。** SPEC_DEV.md 曾另有一棵重复的树、和这份互相冲突，已删除。
>
> **纪律**：新建任何目录前先在此登记一行。仓库根不新增一级目录。
> 这条纪律有执行者：`tools/validate.py` **R26** 把本表第一列和 `git ls-files`
> 实际存在的目录做对差——未登记即 ERROR，登记了却不存在即 WARN。
>
> （R26 之前，这句「validate.py 报 ERROR」在文档里写了很久而门禁并不存在。
> 本仓库的原则是：**不写没做的事**。要么做出来，要么改措辞。）

| 路径 | 用途 | 谁写 | 谁读 | 生命周期 |
|---|---|---|---|---|
| `design/` | 设计令牌单一真源（tokens.json）+ 字面值棘轮基线（token-debt.json） | 人 | build.py、check_a11y.py、check_tokens.py | 长期 |
| `content/ch1/` | 第一章内容与数字账本（site.json + facts.json） | 人 | build.py、validate.py | 长期 |
| `content/stories/` | 故事幕的骨架层，每个 `<case_id>/case.json` | 人（LLM 起草后人审） | build.py | 长期 |
| `content/current/` | 时事管线产物（staging，未签字，**产物不入构建**） | fetch_current.py | 人（签字后才入 content/stories） | ⏸ 待法律评估，见 DEBT.md D6 |
| `evidence/` | 原档存档 + sha256 锚定 | 取数管线 | validate.py | 永久，只增不改 |
| `src/` | `template.html`（单文件骨架，含 `<!--#part:xxx-->` 占位） | 人 | build.py | 长期 |
| `src/parts/` | 源码分片，扁平 `<模块>.{css,js}`，构建期按占位符拼装 | 人 | build.py | 长期 |
| `tools/` | 常驻工具：build / validate / check_a11y / check_budget / check_js / check_tokens / fetch_current / render_review | 人 | 人、CI | 长期 |
| `tools/_archive/oneoff/` | 已执行完毕的一次性内容注入脚本，命名 `YYYYMMDD-用途.py` | — | 归档查阅 | 永久保留，不可重跑 |
| `server/` | 轻后端。`main.go` 是主线，`server.py` 是零依赖联调用 | 人 | 部署 | 长期 |
| `docs/` | 文档，四层：契约 / 裁决 / 记录 / 已取代。索引见 `docs/README.md` | 人 | 人 | 长期 |
| `docs/adr/` | 架构决策记录 `NNNN-标题.md`。被重新争论过的问题只在这里定案 | 人 | 人 | 永久 |
| `docs/records/` | 审计留档（勘误 / 数据核定 / 审图），不管代码 | 人 | 人 | 永久 |
| `docs/_superseded/` | 已被取代的文档，文件头必须写明被谁取代 | 人 | 人 | 永久 |
| `docs/CHECKLISTS/` | 开工前八问等清单 | 人 | 人 | 长期 |
| `dist/` | 构建产物（单文件 index.html） | build.py | 交付 | gitignore |
| `build/` | 其它生成物（如 `build/review/` 的内容审阅稿） | render_review.py | 人 | gitignore |

## 三条目录规则

1. **仓库根不新增一级目录。** 新东西落进上表已有的一级目录之一。
2. **产物不进 git。** `dist/` 与 `build/` 都在 `.gitignore` 里。
   内容审阅稿曾是 `docs/` 里最大的文件，它是 `render_review.py` 的产物，已移出。
3. **一次性脚本不许留在 scratchpad。** 写进 `tools/_archive/oneoff/`，
   命名带日期。它们是一次性内容注入的**执行快照**，供审计查阅——
   权威的可追溯记录是 git 历史与 `docs/records/数据核定_第一章.md`，不是这些脚本。
