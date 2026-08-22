# invest-coach 投资教练

跟着你选的教练，在历史实战里一天几分钟地做决策——教练盯的不是你对没对，而是你的判断习惯。

单文件 HTML 知识图谱学习站（改造自 [agent-graph-learning](https://github.com/Lichangfocus/agent-graph-learning) 的 learn-map，见 `NOTICE.md`）+ 极简 Go 后端（匿名遥测 + 「问教练」LLM 代理）。产品定义与全部裁决见 `docs/`。

**仅供学习。全部内容为历史案例复盘，不构成投资建议，不含任何前瞻信号或收益承诺。**

## 使用

```bash
# 校验内容（ERROR 非零即失败）
python tools/validate.py

# 构建（内部先跑校验）→ dist/index.html，单文件，file:// 双击可用
python tools/build.py
```

## 目录

```
content/ch1/site.json   # 第一章「财报红旗·收入的水分」内容源（图已审定冻结 ch1-graph-v1）
src/template.html       # learn-map 模板（改造中）
tools/                  # build.py 注入构建 ｜ validate.py 门禁校验
server/                 # 轻后端（Go，见 docs/工程化规范.md §3）
docs/                   # 产品体验与用户流程 ｜ 工程化规范 ｜ 审图 ｜ SCHEMA.md
```

## 开发路线

第 2 步填内容（进行中）→ 第 3 步组站（模板改造 + 后端）→ QA → `poc-trial` 定版 → 十人试用。上游产品文档：`C:\Xtrader\research\投资教练_收敛_v3.md`（与 xtrader 代码零耦合）。
