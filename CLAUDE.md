# invest-coach · Claude 开发指引

单文件 HTML 知识图谱学习站 + 极简 Go 后端。产品是**投资教练**：跟着教练在历史实战里做决策，
教练盯的是判断习惯而不是对错。

## 动手之前必读

**先看 [docs/README.md](docs/README.md)** —— 文档索引，四层（契约 / 裁决 / 记录 / 已取代）。
下面这几份是最常用的：

| 文档 | 什么时候读 |
|---|---|
| [DESIGN.md](DESIGN.md) | **任何视觉/样式改动之前。** 纸面翻正、双场系统、字体分工、令牌纪律 |
| [docs/SCHEMA.md](docs/SCHEMA.md) | **新增或改动任何 `x_` 内容字段之前**——未登记即构建失败 |
| [docs/STRUCTURE.md](docs/STRUCTURE.md) | **新建任何目录之前**——未登记即 `validate.py` R26 报 ERROR |
| [docs/知识可靠性与LLM边界.md](docs/知识可靠性与LLM边界.md) | 任何涉及内容、出处、判分的改动 |
| [docs/LLM_USE_REGISTRY.md](docs/LLM_USE_REGISTRY.md) | 任何引入或改动 LLM 调用的地方 |
| [docs/形态规格_故事驱动.md](docs/形态规格_故事驱动.md) | 改幕、质问台、教练解读之前 |
| [docs/SPEC_DEV.md](docs/SPEC_DEV.md) | 工程规范与门禁定义 |
| [docs/CHECKLISTS/preflight.md](docs/CHECKLISTS/preflight.md) | 每次开工之前 |

**被重新争论过的问题看 [docs/adr/](docs/adr/)。** 那里的裁决其它文档只许引用不许复述——
复述是漂移的来源，这个仓库已经因此翻过一次车（教练人格那次，见 ADR-0002）。

## 三条不可协商的铁律

1. **事实不出自 LLM。** 真实公司数字、准则条文、官方认定只能来自原档取数管线
   （EDGAR accession + 行号 → `facts.json` → 人工核定）。LLM 只解释已核定的材料，
   以及做「用户想戳哪条」的语义路由——输出只是一个 id，文本一律取自内容文件。
   **这一条是产品的立身之本，不可协商。**

   （注意：**「判分不经 LLM」是另一条，已于 2026-08-26 解除永久禁令**，
   现状是「推迟」而非禁止。代码维持确定性判分，理由是离线可用/零延迟/可复现，
   不是禁令。见 [ADR-0001](docs/adr/0001-判分不经-llm.md)——两条过去被捆在一起，
   导致真正要紧的那条反而没被单独讨论过。）
2. **令牌是视觉的单一真源。** 源码不许出现字面色值与字面字号，一律走 `var(--...)`。
   `design/tokens.json` 是真源，`design/token-debt.json` 是历史债棘轮基线。
3. **杜绝断头路，每个点击都有反馈。** 任何界面状态都必须能往前走或往回退；
   任何可点元素都必须有按下态、焦点态、禁用态。`check_a11y` A7/A8 强校验。

## 构建与门禁

```bash
python tools/build.py          # 内部先跑 validate，再跑四道门禁
```

六道关卡，任一 FAIL 即构建不合格：

- `validate.py` —— 内容/出处/图结构（R1–R25）+ 目录登记（R26）
- `check_js.py` —— J1 `node --check` 源码分片 + 产物内联 script；J2 被调用却从未声明的标识符
  （排最前：跑不起来就没必要看别的）
- `check_a11y.py` —— 对比度（从令牌注记推导 + 状态色遍历所有会被画出的面 + 实扫 CSS 与内联 style）、
  字号下限、触控目标、浮层层级（A7）、点击三态（A8）、死样式（A9）
- `check_budget.py` —— 体积与性能预算
- `check_tokens.py` —— 字面值棘轮，只减不增（`--update` 在还债后降基线）

修掉字面值之后跑 `python tools/check_tokens.py --update` 把基线降下来。

## 门禁的已知教训

写门禁的时候记住这条，它在这个仓库里犯过三次：

> **机器门禁只查形状不查真值。**

- 内容层：LLM 写的 canon 与出处必须逐条实证核验，一次全量审计查出 34 条出处问题
- 设计层：`check_a11y` 曾把颜色对硬编码在 Python 里读令牌，于是页面实际用 `#6f688a`（3.24:1）
  而门禁一路 `PASS`。现在颜色对从令牌注记推导，并实扫产物
- 可执行性：一处非法嵌套引号让 court.js 整个 IIFE 抛异常、今日页渲染成空白，
  而 a11y / budget / tokens 三道**全部 PASS**——它们只查形状，不查跑不跑得起来。
  补了 `check_js.py`
- 可解析 ≠ 能运行：批量替换把 `return 📖 …` 弄成 `returnic('book')+' …'`，语法完全合法，
  `node --check` 一路 PASS，一调用就 `ReferenceError`。补了 J2（未声明标识符扫描）
- 比较集不全：`check_a11y` 只拿 shell / card 比状态色，而外壳渐变的深端是 `paper-200`，
  四个状态色在那一端全部不达 AA。**一个面只要会被真的画出来，就得进比较集**

新增门禁时先问：**它检查的是产物，还是检查的是描述产物的那份文件？**
再问一遍：**它检查的是形状，还是检查的是能不能用？**

## 视觉改动的工作方式

`~/.claude/skills/minimalist-ui`（编辑式极简）是这个项目对口的设计技能。
**排版规则在 `~/.claude/skills/design-taste-frontend/references/directives-foundation.md` §4.1**——
那条 SERIF DISCIPLINE 值得先读，本项目在它上面栽过一次（见 DESIGN.md §4）。
但**技能不知道本项目的裁决**——纸面翻正、双场语义色、字体分工都在 `DESIGN.md`，先读那份。

改完必须实测，不能只看门禁：起个本地服务把 `dist/index.html` 跑起来，
量真实渲染的对比度（门禁看不见上下文，比如纸面 meta 色被用在暗岛里）。
`.claude/launch.json` 里有一条 `invest-coach`（`python -m http.server --directory dist`）。

实测的做法是**走一遍**，不是看一眼首屏：今日页 → 三幕各自走到底（含质问台的追问/出证）
→ 判卷台 → 图谱 → 我，移动端与 1280px 桌面各一轮，每一步都量对比度、触控高度与横向溢出。
`story.css` 那次（幕里全站用纸面令牌）**四道门禁全绿**，只有真的进到幕里才量得出来。

## 目录

```
content/     内容（ch1/site.json + facts.json、stories/*/case.json、current/ 暂缓）
evidence/    原档存档 + sha256 锚定，只增不改
design/      tokens.json 视觉真源 · token-debt.json 棘轮基线
src/         template.html + parts/*.{css,js}（构建期按 <!--#part:--> 拼装）
tools/       build / validate + 四道门禁 + fetch_current / render_review
             _archive/oneoff/ 是已执行完毕的一次性内容脚本，不可重跑
server/      轻后端：main.go 主线 · server.py 零依赖联调
docs/        四层：契约 / adr 裁决 / records 记录 / _superseded 已取代（索引 docs/README.md）
dist/ build/ 产物，都在 gitignore
```

完整登记表见 [docs/STRUCTURE.md](docs/STRUCTURE.md)。**新建目录前先登记**，
`validate.py` R26 会对差 `git ls-files`，未登记即 ERROR。
