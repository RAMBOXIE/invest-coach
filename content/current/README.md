# content/current —— 时事管线 staging

`tools/fetch_current.py` 从 SEC EDGAR 拉取的问询函与申报数据落在这里。

**状态：⏸ 待法律评估，产物不入构建。** `build.py` 只读 `content/stories/`。

`*.json` 已加入 `.gitignore`：它们是未签字的半成品，不应随 commit 漂移。
签字通过的案例才移进 `content/stories/<case_id>/`。

见 [docs/DEBT.md](../../docs/DEBT.md) D6。
