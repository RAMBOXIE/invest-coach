# site.json 扩展字段登记簿（SCHEMA.md）

基契约 = agent-graph-learning 原 schema（`id/title/tag/about/reorder/sources/nodes/edges`；node 含 `canon{term,formal,source,textbook}` + `evidence[]` + `screens[]`；edge `{from,to,type∈hard|soft|cross}`）。

**规则：一切扩展字段以 `x_` 前缀命名，必须先登记在本文件，`tools/validate.py` 按白名单强校验，未登记即 ERROR。**白名单校验作用于四层：顶层、节点层、canon 层、屏层、quiz 层。

**出处分层契约（详见 `知识可靠性与LLM边界.md` §3）**：每条事实断言必须落在 L1 原始档（sha256+行号+逐字引文）/ L2 正典（DOI/ISBN/条款号+页章）/ L3 本站口径（必须显式标「本章口径」）/ L4 教学措辞（豁免出处，**不豁免算术自洽**）之一；不属于任何一层不得上线。

## 顶层

| 字段 | 类型 | 说明 | 状态 |
|---|---|---|---|
| `x_note` | string | 扩展字段的人类可读说明 | 在用 |
| `x_version` | string | 内容版本（如 ch1-graph-v1） | 在用 |
| `x_coaches` | array | 教练原型 `{id, name, school, intro, canon_sources[], style_lines: [{when, t}]}`；`when ∈ correct/wrong/overconfident/underconfident/hint_used/na_honest/na_dodge/pair_repeat/streak/complete`，`t` ≤40 字；人格字段（name/style_lines）不得用真人名，出处字段（intro/canon_sources）必须真名真书 | 在用 |
| `x_review_bank` | array | 复训变体题库 `{pair_id, side: "a"\|"b", quiz}`，每对每面 ≥1 题；screens 已填节点的混淆对缺库=ERROR，未填=WARN（增量门禁）；复训变体题可为构造题（不指名真实公司、不含市场事实主张），指名真实公司时须走数字核定 | 在用 |
| `x_chapters` | object | 多章（D11）：`{章号(字符串) → 章名}`，如 `{"1":"看穿假账","2":"一家公司好在哪"}`。前端进度分章、章名展示用；只在合并后的 SITE 里出现，单章 site.json 可省略 | 在用 |

## canon

| 字段 | 类型 | 说明 | 状态 |
|---|---|---|---|
| `canon.x_cite` | string | 出处的精确定位：章/页/条款号（如 `IAS 1 §10`、`Beneish (1999), FAJ 55(5):24-36 · Table 3`、`AAER 1393 · 认定段`）。**禁止编造**——查不到就留空，R16 会以 WARN 提示 | 在用 |

## 健壮性字段（2026-08-22 裁决新增）

| 字段 | 类型 | 说明 | 状态 |
|---|---|---|---|
| `quiz.x_id` | string | 题的全局唯一稳定 id（节点题 `<node>-qN`，复训题 `rv-<pair>-<side>`）。遥测/错题档案/勘误/回滚的主键——**已发布 id 永不复用、改正确答案必须发新 id** | 在用 |
| 节点 `x_prov` | object | `{drafted_by, model, drafted_at, reviewed_by, reviewed_at, reviewed_hash}`。reviewed_hash = 节点内容指纹（validate 的 node_hash）；内容一改审核自动过期；`--release` 时未签字即 ERROR | 在用 |
| 教练 `x_identity` | string | 固定身份自述（学派原型非真人、非持牌顾问、AI 起草人工核对、思想出处、不判分不荐股不看当下）。运行时被问身份/资格时逐字输出 | 在用 |
| `content/ch1/facts.json` | 文件 | 数字账本：evidence 文件 sha256 + 事实条目（accession+行号+口径）+ 真实公司语境数字 token 白名单（R12 强制命中） | 在用 |
| `evidence/*.txt` | 文件 | EDGAR 原档存档（公有领域），sha256 由 facts.json 锚定，validate 校验防篡改/防链接腐烂 | 在用 |

## 节点

| 字段 | 类型 | 说明 | 状态 |
|---|---|---|---|
| `x_qtype` | string | 题型（题型=节点位置的函数）；合法值：点选/多选、判断+理由多选、whole-task、决策转化、整理/排序（均规则判分） | 在用 |
| `x_level` | string | 题面材料难度 L1/L2；**有 x_level 的节点必须有 1–3 个 x_pairs**（校验器以此判定红旗/案例节点） | 在用 |
| `x_pairs` | array | 混淆对 `{id, look, a, b, key}`；`id` 自第 2 步起必填（复训与档案主键） | 在用 |
| `x_coach_notes` | object | `{coach_id → ≤80 字点评}`，仅 2 个 whole-task 节点三声道 | 第 2 步 |
| `x_chapter` | int | 多章（D11）：节点所属章号。缺省=1（第一章节点不写此字段）。前端 `chOf()` 按它分章排课/算进度；第二章起每个节点须显式写 `"x_chapter": 2` | 在用 |

## 屏 / 题

| 字段 | 类型 | 说明 | 状态 |
|---|---|---|---|
| `screens[].x_covers` | int[] | 该屏覆盖的 evidence 下标；并集须全覆盖 | 第 2 步 |
| `quiz.hints` | string[3] | 三级提示（指方向→指位置→给原则） | 第 2 步 |
| `quiz.confidence` | bool | 该题需信心标注（红旗层及以上必为 true） | 第 2 步 |
| `quiz.x_pair` | string | 题目挂靠的混淆对 id | 在用 |
| `quiz.opts[].na` | bool | 「信息不足，无法判断」选项标记 | 在用 |
| `quiz.x_kind` | string | 题的角色：`main`（正题，计分）/ `pretest`（前测，不计分，第一案）/ `decision`（决策转化，可多正确）/ `review`（复训变体） | 在用 |
| `quiz.x_next` | string | D14：当「无法判断」是正确答案时，答对后给的「接下来该去查什么」方法清单（确定性内容，只讲流程不含公司事实）。前端在 na 答对时红标【LLM教练说】展示；接后端时作为 LLM 讨论的种子。**凡 na 为正确答案的题必填**（check_coach 强校验） | 在用 |

## 负面契约

第 1–2 章白名单**永不**包含仓位/账户/收益率/净值类字段；多步场景题的场景内仓位字段随第 3–4 章设计与法律评估一并登记；账户级字段在「远期毕业场」法律评估通过前不登记（收敛文档 v3 §2.2/§2.3）。

## v3 案卷化字段（2026-08-25）

| 字段 | 层级 | 说明 | 状态 |
|---|---|---|---|
| `x_casefile` | 节点 | 手机原生案卷：`{code, status:settled\|regulator_asked\|teaching, asof, brief, panels[], srcs[], letter?, disclaimer?}`；panel kind ∈ `cmp\|trend\|note\|quote`；`srcs[].f` 必须命中 facts.json（R25 强校验）。材料屏用它渲染，原教学屏降为按需「补课」抽屉 | 在用 |
| `x_lab` | 顶层 | 时事案卷（B 轨）实验室：管线自动产出、**未经人工签字**。硬性：不进错题档案、不进复训队列、不计校准分、不作锚题、不能点亮任何节点 | 在用 |
| `x_facts` | 顶层 | 构建期由 build.py 从 facts.json 注入（id → 事实条目），供溯源徽标只读展示。**不手写** | 构建注入 |
