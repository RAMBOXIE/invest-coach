# 轻后端（第 3 步实现）

设计契约见 `docs/工程化规范.md` §3。要点：Go 单二进制 + SQLite（DSN 可切 MySQL），仅两个职责：

- `POST /api/v1/events` — 匿名遥测（device_id + schema_version + events[]，append-only）
- `POST /api/v1/ask-coach` — 「问教练」LLM 代理（上下文锁定本题材料与 canon；禁前瞻信号/个股建议/收益承诺；每 device 每日 20 问限流；全量日志留存）
- `GET /health`

部署：现有常开机器 + cloudflared named tunnel（免费）出固定 HTTPS 域名。前端后端地址为构建常量；后端不可达时前端静默降级（问教练按钮隐藏、事件本地暂存）。
