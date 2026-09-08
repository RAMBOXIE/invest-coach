# 交接快照

> 给接手继续开发的下一个 agent。**这份只回答一个问题:现在停在哪、接手第一件事做什么。**
> 「怎么做」全部指回契约文档,这里不复述——复述是漂移的来源(见 CLAUDE.md 与 docs/README.md)。
>
> 更新时间:2026-09-08。内容版本见 `content/ch1/site.json` 的 `x_version`。
> 这份快照会过时;不确定时,以 `git log`、`docs/DEBT.md`、`python tools/sign.py` 的当场输出为准。

---

## 一分钟现状

- **产品**:投资教练第一章「收入的水分」。15 个知识节点 + 4 个真实案例幕 + 近期财报实验区。
- **形态**:单文件 HTML(`dist/index.html`,约 441 KB)+ 零依赖 Python 轻后端(`server/server.py`)。
- **门禁**:十道全绿。`python tools/build.py` 一条命令跑完构建 + 全部门禁。
- **线上**:静态离线版已部署 https://fincoach.netlify.app (noindex,不接后端,LLM 对话是「未连接」占位)。
- **定版**:`validate --release` 现在 **FAIL**——4 个幕的签字过期了(见下,这是接手第一件事)。

## 接手第一件事:4 个幕待重签

```bash
python tools/sign.py              # 看总览:15 个节点已签,4 个幕待签
```

**为什么过期**:2026-09-06 owner 批量认可了 19 项,`--release` 一度转绿。之后(09-06/07)
给四个幕补了当事人的当年原话(Dunlap、Callan、Fuld、Buffett、Russell 的公开发言,全部锚到
新归档的 SEC 文件)。签字绑内容指纹,内容一改就自动过期——这是机制该有的样子,不是故障。
15 个知识节点没动过,签字仍有效。

**怎么处理**(这是 owner 的判断,agent 不能代签):
- 内容确实值得重签(新增的都是当事人真实原话,逐字核过) → owner 跑 `sign.py --sign <幕id> --by 名字`
- 四个幕 id:`buffett-1993` `lehman-2008` `nikola-2021` `sunbeam-1998`
- 铁律:**agent 永远不代签**(`docs/LLM_USE_REGISTRY.md` 铁律 4:机器溯源只做筛子,永不签核)。

签字面现在只剩四条人工判据,其中三条已由门禁接管,细节见
`docs/records/预审_第一章.md` 末节「这一轮之后,签字面还剩什么」。

## 这套东西的两个真实缺口(owner 已知,尚未决定)

来自 `docs/records/验收_金融教学Agent.md`。这不是 bug,是产品完整度:

1. **决策人复盘对话(登记簿 #10 / ADR-0004)从未在真模型上验证过。**
   代码、三道确定性闸(材料/出口/标红)、门禁(check_server P6/P7)都在,但只在**无 key 的后端**
   上验过接线。提示词的口吻、出口检查的误杀率、当事人会不会在追问下编动机——都要拿真 key
   跑十几轮对话才知道。这是「LLM 扮演决策人」这个产品定义能不能成立的关键验证,还没做。

2. **三处留给 owner 裁决的开放问题**(见 `docs/records/预审_第一章.md`「留给你裁的」):
   `rv-ff-p1-b2` 的「无法判断」用法与同组相反;两个混淆对(ts-p1/cf-p1)覆盖面偏窄;32 条 nit。
   批量签字**没有**覆盖这三处,它们仍开着。

## 线上部署:现状与「怎么让 LLM 活起来」

- **现在这版**:纯静态,`BACKEND=null`,零上传零外链。LLM 两处(先写屏的教练回应、追问当事人)
  显示「未连接,本地占位」。**怎么部署这版**:`server/README.md` 部署一节(构建三步 + Netlify 拖拽/CLI)。
- **要让 LLM 对话活起来**:把 `server.py` 暴露到公网(cloudflared named tunnel),
  用 `python tools/build.py --backend https://域名` 重新构建,`ALLOWED_ORIGINS` 设成前端域名。
  代价:用 owner 的 Anthropic key,目前只有每设备每天 60 次的成本闸。理由与红线全在 `server/README.md`。
- **绝对不要做的事**:把 `server.py` 改写成 Netlify Functions(JS)。Netlify 不支持 Python 运行时,
  用 JS 重写四个端点 = 制造第二份隐私关键代码实现,正是刚还掉的 D9。理由记在 `server/README.md` 部署一节。

## 下一步开发方向(不是发布阻断,是产品增量)

按对产品定义的贡献排序,细节见 `docs/records/验收_金融教学Agent.md` 末节与 `docs/ROADMAP.md`:

1. **拿真 key 跑 #10 十几轮**,调提示词、量出口检查的误杀/漏杀率。不做这步,「LLM 扮演决策人」仍是纸面。
2. **第二章**:ROADMAP 里内容配比的短板(全是造假案、干净公司只有 Dell/Moderna 两个负样本)。
3. **实验区扩容**:`fetch_current.py` 的确定性管线已上线三卷,可加卷(每卷要过五道防呆判据)。

## 这个仓库栽过的坑(接手前值得知道,能省半天)

这些是本仓反复撞上的失败模式,已固化成门禁,但新代码仍可能踩:

- **「机器门禁只查形状不查真值」**——本仓栽过八次的同一个坑。加门禁前必问两句
  (CLAUDE.md「加门禁之前先问两句」),且必须带 `--selftest` 变异测试。
- **heredoc 折转义**:用 bash heredoc 写 Python 补丁脚本时,正则里的 `\b` 会被折成字面退格符 0x08,
  正则从此永不匹配而门禁照样绿。对策:正则用 `(?<!\d)`/`(?!\d)` 代替 `\b`;补丁脚本反斜杠用 `chr(92)` 拼。
  `check_src.py` 的 S1 全仓扫这类控制符。
- **内容里的 `**` 不渲染**:node/幕的正文是纯文本,加粗要用 `<b>`,写 `**` 会原样显示给用户。
- **豁免表会把要删的东西藏起来**:`check_style` 的 SKIP_KEYS 曾把整个 canon 子树跳过,
  于是报「黑话 0 处」而正典卡里有六个「红旗」。加豁免时问:被豁免的东西用户读不读得到?
- **降级 WARN 也是静默放行**:S7 找不到原档时曾只报 WARN 就放行,六份原档因此从没被核过。
  「检查还在,但它什么也没查」是这里最贵的失败。

## 关键文件地图(细节看 STRUCTURE.md)

| 要改什么 | 去哪 | 先读 |
|---|---|---|
| 知识节点内容/题目 | `content/ch1/site.json` | SCHEMA.md(x_ 字段白名单)|
| 真实案例幕 | `content/stories/<id>/case.json` | 形态规格_故事驱动.md |
| 数字账本/原档登记 | `content/ch1/facts.json` + `evidence/` | 知识可靠性与LLM边界.md |
| 前端骨架/逻辑 | `src/template.html` + `src/parts/*.{css,js}` | DESIGN.md(改样式前必读)|
| 后端/隐私/LLM 端点 | `server/server.py` | server/README.md + LLM_USE_REGISTRY.md |
| 门禁 | `tools/check_*.py` `validate.py` | CLAUDE.md「加门禁之前先问两句」|
| 视觉令牌 | `design/tokens.json` | 令牌是视觉唯一真源,源码不许字面色值/字号 |

## 验证清单(接手后先跑一遍,确认环境干净)

```bash
python tools/build.py                    # 十道门禁,应全 PASS,产物 <450KB
python tools/validate.py --selftest      # 门禁自检,应 7/7
python tools/check_coach.py --selftest   # 应 13/13
python tools/sign.py                      # 应显示「待签 4 / 共 19」(4 个幕)
git log --oneline -5                      # 最近提交,对照本文档的「更新时间」判断是否已过时
```
