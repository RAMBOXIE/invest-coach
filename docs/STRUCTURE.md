# 目录登记表

> **纪律**：新建任何目录前先在此登记一行。未登记的目录 `validate.py` 报 ERROR。仓库根不新增一级目录。

| 路径 | 用途 | 谁写 | 谁读 | 生命周期 |
|---|---|---|---|---|
| `design/` | 设计令牌单一真源（tokens.json） | 人 | build.py、check_a11y.py | 长期 |
| `content/ch1/` | 第一章内容与数字账本 | 人 + oneoff 脚本 | build.py、validate.py | 长期 |
| `content/stories/<case_id>/` | 故事骨架层（case.json + facts.json） | 人（LLM 起草后人审） | build.py、validate.py | 长期 |
| `content/current/` | 时事管线产物（staging，未签字） | fetch_current.py | 人（签字后才入 content/stories） | 滚动 |
| `evidence/` | 原档存档 + sha256 锚定 | 取数管线 | validate.py | 永久，只增不改 |
| `src/shell.html` | 单文件骨架，含 `<!--#part:xxx-->` 占位 | 人 | build.py | 长期 |
| `src/parts/` | 源码分片（css/*.css、js/*.js），构建期拼装 | 人 | build.py | 长期 |
| `tools/` | 常驻工具（build/validate/fetch_current/check_*） | 人 | 人、CI | 长期 |
| `tools/oneoff/` | 一次性脚本，命名 `YYYYMMDD-用途.py`；**内容变更的唯一可追溯记录** | 人 | 归档查阅 | 永久保留 |
| `docs/` | 规范、规格、勘误、审阅稿 | 人 | 人 | 长期 |
| `docs/CHECKLISTS/` | 开工前八问等清单 | 人 | 人 | 长期 |
| `docs/adr/` | 架构决策记录 `NNNN-标题.md` | 人 | 人 | 永久 |
| `dist/` | 构建产物 | build.py | 交付 | gitignore |
| `content/stories/sunbeam-1998/` | 首个故事幕：case.json（骨架冻结，引文逐字带行号） | 人 | build.py、validate.py | 长期 |
