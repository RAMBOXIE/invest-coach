# tools/_archive

这里的东西**已经执行完毕，不可重跑**。

## oneoff/

五个一次性的内容注入脚本，命名 `YYYYMMDD-用途.py`。它们把某一批内容写进
`content/ch1/site.json` 或 `content/stories/*/case.json`，跑完就结束了。

**为什么留着**：它们里面有当时人工核定过的数字与出处，是审计线索。

**为什么不可重跑**：硬编码了绝对路径（`ROOT = 'c:/invest-coach/'`），
而且目标文件早已被后续批次改过，重跑只会破坏内容。

**权威的可追溯记录不是它们**，是：

- `git log` —— 每一次内容变更
- [`docs/records/数据核定_第一章.md`](../../docs/records/数据核定_第一章.md) —— 数字到原档行号的核定
- [`docs/records/勘误_第一章.md`](../../docs/records/勘误_第一章.md) —— 全量审计与修订台账

`docs/STRUCTURE.md` 与 `docs/SPEC_DEV.md` 曾把这些脚本称作「内容变更的**唯一**可追溯记录」，
那个说法不成立，已更正。规则本身（一次性脚本不许留在 scratchpad，必须提交）保留。
