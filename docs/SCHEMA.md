# site.json 扩展字段登记簿（SCHEMA.md）

基契约 = agent-graph-learning 原 schema（`id/title/tag/about/reorder/sources/nodes/edges`；node 含 `canon{term,formal,source,textbook}` + `evidence[]` + `screens[]`；edge `{from,to,type∈hard|soft|cross}`）。

**规则：一切扩展字段以 `x_` 前缀命名，必须先登记在本文件，`tools/validate.py` 按白名单强校验，未登记即 ERROR。**

## 顶层

| 字段 | 类型 | 说明 | 状态 |
|---|---|---|---|
| `x_note` | string | 扩展字段的人类可读说明 | 在用 |
| `x_version` | string | 内容版本（如 ch1-graph-v1） | 在用 |
| `x_coaches` | array | 教练原型 `{id, name, school, intro, canon_sources[], style_lines[]}`；人格字段（name/style_lines）不得用真人名，出处字段（intro/canon_sources）必须真名真书 | 第 2 步 |
| `x_review_bank` | array | 复训变体题库 `{pair_id, side: "a"\|"b", quiz}`，每对每面 ≥1 题 | 第 2 步 |

## 节点

| 字段 | 类型 | 说明 | 状态 |
|---|---|---|---|
| `x_qtype` | string | 题型（题型=节点位置的函数）；合法值：点选/多选、判断+理由多选、whole-task、决策转化、整理/排序（均规则判分） | 在用 |
| `x_level` | string | 题面材料难度 L1/L2；**有 x_level 的节点必须有 1–3 个 x_pairs**（校验器以此判定红旗/案例节点） | 在用 |
| `x_pairs` | array | 混淆对 `{id, look, a, b, key}`；`id` 自第 2 步起必填（复训与档案主键） | 在用 |
| `x_coach_notes` | object | `{coach_id → ≤80 字点评}`，仅 2 个 whole-task 节点三声道 | 第 2 步 |

## 屏 / 题

| 字段 | 类型 | 说明 | 状态 |
|---|---|---|---|
| `screens[].x_covers` | int[] | 该屏覆盖的 evidence 下标；并集须全覆盖 | 第 2 步 |
| `quiz.hints` | string[3] | 三级提示（指方向→指位置→给原则） | 第 2 步 |
| `quiz.confidence` | bool | 该题需信心标注（红旗层及以上必为 true） | 第 2 步 |
| `quiz.x_pair` | string | 题目挂靠的混淆对 id | 第 2 步 |
| `quiz.opts[].na` | bool | 「信息不足，无法判断」选项标记 | 第 2 步 |

## 负面契约

第 1–2 章白名单**永不**包含仓位/账户/收益率/净值类字段；多步场景题的场景内仓位字段随第 3–4 章设计与法律评估一并登记；账户级字段在「远期毕业场」法律评估通过前不登记（收敛文档 v3 §2.2/§2.3）。
