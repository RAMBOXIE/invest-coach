# Git 交付说明

Git 是本项目唯一的交付源。本项目不依赖 Netlify，也不把部署平台作为验收条件。

## 当前版本目标

- 十个真实金融事件 RPG 故事。
- 每个故事都有角色、历史场景、证据、行动、压力后果、第二轮决策和真实档案回收。
- 每个故事声明学习目标与技能，完成终局决策后写入本地学习记录。
- LLM 画外音通过 `server/server.py` 的 `/api/v1/story-narrate` 接入；没有后端或模型密钥时使用冻结旁白回落，不改变事实与结局。

## 从 Git 体验

```powershell
git clone https://github.com/RAMBOXIE/invest-coach.git
cd invest-coach
python tools/build.py
python tools/sign.py
python server/server.py
```

然后访问 `http://127.0.0.1:8791/`。对外测试前必须运行：

```powershell
python tools/validate.py --stories --release
python tools/check_server.py --selftest
```

## 内容变更纪律

新增故事必须放在 `content/stories/<case-id>/case.json`，通过故事门禁后运行：

```powershell
python tools/sign.py --sign-all-stories --by automated-gates
```

这里的自动定版只记录机器门禁和内容哈希，不代表人工背书；故事事实仍必须绑定可复核原档或明确的公开来源说明。
