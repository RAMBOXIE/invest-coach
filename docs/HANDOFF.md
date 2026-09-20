# 交接快照

> 给接手继续开发的下一个 agent。**这份只回答一个问题:现在停在哪、接手第一件事做什么。**
> 「怎么做」全部指回契约文档,这里不复述——复述是漂移的来源(见 CLAUDE.md 与 docs/README.md)。
>
> 更新时间:2026-09-20。内容版本见 `content/ch1/site.json` 与 `content/ch2/site.json` 的 `x_version`。
> 这份快照会过时;不确定时,以 `git log`、`docs/DEBT.md`、`python tools/sign.py` 的当场输出为准。

---

## 仓库地址

**没有远程仓库。** 这是纯本地 git 仓库,`git remote -v` 是空的,从未推到 GitHub/GitLab/任何地方。
本机路径:`C:\invest-coach`(Windows)。

**要交接给另一台机器/另一个 agent 会话,你需要先做以下之一**:
1. 建一个远程仓库(GitHub/GitLab 私有库),`git remote add origin <url>` 后 `git push -u origin main`;
2. 或者直接把整个 `C:\invest-coach` 目录复制/共享给对方(注意 `evidence/` 里的 SEC 原档、`content/` 里的内容都要一起带,`dist/` `publish/` `.netlify/` 不用带,会自动重新构建)。

`git log --oneline` 有完整历史(46+ 次提交),分支只有 `main`,工作区目前是干净的。

## 一分钟现状

- **产品**:投资教练。**两章**——第一章「看穿假账」(证伪:15 节点 + 5 个真实案例幕)、
  第二章「一家公司好在哪」(证实:8 节点,好市多 EDGAR 案例)。
- **形态**:单文件 HTML(`dist/index.html`,约 535KB 原始 / 172KB gzip)+ 零依赖 Python 轻后端(`server/server.py`)。
- **门禁**:十道全绿。`python tools/build.py` 一条命令跑完构建 + 全部门禁,同时生成:
  - `dist/index.html` —— 离线分发用,目录里还混着旧版本/说明文件/zip(不要整个 dist/ 发布)
  - `publish/`(只含 `index.html` + `_headers`)—— **专供部署**,每次构建自动清空重建
- **线上**:静态版已部署 https://fincoach.netlify.app (noindex,不接后端,LLM 相关格子显示「未连接,本地占位」)。
  重新部署命令:`netlify deploy --prod --dir=C:\invest-coach\publish --site=9fc2d12a-a693-46f3-aad0-ce2c9ba723c5`
  (**必须在你自己已登录 Netlify CLI 的终端里跑**——这个 agent 会话读不到你的登录态)。
- **定版**:第一章 15 节点、第二章 8 节点和 5 个真实案例幕均已有内容哈希定版记录；故事幕来源为 `automated-gates`。
  (见下,这是接手第一件事)。

## 定版状态：五幕已清零

```bash
python tools/sign.py              # 看总览
```

当前输出:15 节点(第一章)+ 8 节点(第二章)+5 个故事幕均已定版:
`buffett-1993` `lehman-2008` `luckin-2020`(瑞幸,新增)`nikola-2021` `sunbeam-1998`。

`luckin-2020` 是本轮周期里新加的第五幕(中概股造假案,详见 `docs/DEBT.md` 第二章与本土化规划一节),
内容继续改动时，哈希会自动过期；重新运行 `python tools/sign.py --sign-all-stories --by automated-gates` 即可在门禁通过后重新定版。

**怎么处理**(这是 owner 的判断,agent 不能代签):
- `python tools/render_review.py` 生成审阅稿一次读完,或 `python tools/sign.py --show <幕id>` 逐条看
- owner 认可后:`python tools/sign.py --sign <幕id> --by 名字`
- 铁律:**agent 永远不代签**(`docs/LLM_USE_REGISTRY.md` 铁律 4:机器溯源只做筛子,永不签核)

## 这一个周期做完的东西(D11–D15,详见 docs/DEBT.md)

| # | 是什么 | 状态 |
|---|---|---|
| D11 | 前端多章架构(合并方案:`x_chapter` 标章 + `stateOf` 章闸) | ✅ 完成并验证 |
| D12 | 单文件体积天花板 —— 改盯 gzip 而非原始 KB,设触发线 250KB | ✅ 数据驱动定案,不建懒加载 |
| D13 | 第二章 8 节点内容 + 好市多 EDGAR 案例 + 人工签字 | ✅ owner 已签字 |
| D14 | 教练在「缺证据」处上场(答对 na 题后讨论下一步查什么) | ✅ 完成,判分仍归规则 |
| D15 | 第一章 18 道 na 题回填 `x_next`(D14 的种子字段) | 🔲 待办,不阻断 |

**D14 是本轮唯一的新 LLM 用途**,已登记 `LLM_USE_REGISTRY.md` #11,门禁 `check_server` P8 + `check_coach` C14。
静态部署上这一格显示确定性清单(标「本地占位」);接后端后由 `/api/v1/next-steps` 端点接管讨论。

## 这套东西的三个真实缺口(owner 已知,尚未决定)

来自 `docs/records/验收_金融教学Agent.md`,不是 bug,是产品完整度:

1. **决策人复盘对话(登记簿 #10 / ADR-0004)从未在真模型上验证过。** D14(#11)也是同样处境——
   代码、确定性闸、门禁都在,但只在**无 key 的后端**上验过接线,提示词口吻/出口检查误杀率
   /当事人会不会在追问下编动机,都要拿真 key 跑十几轮才知道。
2. **D15**:第一章 18 道 na 题还没接上 D14(见上表)。
3. **第二章的三个案例节点欠账**(细节见 `docs/records/审图_第二章.md`):无。第二章 8 节点已全部填完签字,
   这条缺口已随本轮清空——只是留意后续新章节要重复这套流程(图冻结→内容→EDGAR→门禁→签字)。

## 下一步开发方向(不是发布阻断,是产品增量)

按对产品定义的贡献排序,细节见 `docs/ROADMAP.md`:

1. **拿真 key 跑 #10/#11 十几轮**,调提示词、量出口检查的误杀/漏杀率。不做这步,「LLM 扮演决策人」
   和「教练缺证据讨论」都仍是纸面能力。
2. **D15 回填**:第一章 na 题补 `x_next`,需要随一次内容重审一起做(会作废现有签字)。
3. **第三章**:上第三章前先看 D12 的触发线(gzip 250KB),现在(两章)172KB,大概率还有 2-3 章空间;
   到线才需要做「离线单文件 + 托管按章懒加载」的双目标构建,不要在此之前动这个架构。
4. **实验区扩容**:`fetch_current.py` 的确定性管线已上线三卷,可加卷(每卷要过五道防呆判据)。

## 线上部署要点

- **现在这版**:纯静态,`BACKEND=null`,零上传零外链。LLM 相关格子(先写屏教练回应/追问当事人/
  D14 下一步讨论)显示「未连接,本地占位」。
- **部署命令**:`python tools/build.py` 生成 `publish/`(干净目录,只含 2 个文件),然后
  `netlify deploy --prod --dir=C:\invest-coach\publish --site=9fc2d12a-a693-46f3-aad0-ce2c9ba723c5`。
  **不要用 `netlify deploy` 默认交互流程**——它会读到 `.netlify/netlify.toml` 里危险的整仓 publish 路径,
  也可能在未 link 目录时提示「新建项目」(千万别选,会开一个新站)。
- **要让 LLM 对话活起来**:把 `server.py` 暴露到公网(cloudflared named tunnel),
  用 `python tools/build.py --backend https://域名` 重新构建,`ALLOWED_ORIGINS` 设成前端域名。
  代价:用 owner 的 Anthropic key,目前只有每设备每天 60 次的成本闸。理由与红线全在 `server/README.md`。
- **绝对不要做的事**:把 `server.py` 改写成 Netlify Functions(JS)。Netlify 不支持 Python 运行时,
  用 JS 重写端点 = 制造第二份隐私/LLM 关键代码实现,正是已还掉的 D9 债重新生根。

## 这个仓库栽过的坑(接手前值得知道,能省半天)

这些是本仓反复撞上的失败模式,已固化成门禁,但新代码仍可能踩:

- **「机器门禁只查形状不查真值」**——本仓栽过至少九次的同一个坑(本轮又添两次:check_style/
  check_coach 曾写死只查第一章,合并多章后第二章被静默漏检)。加门禁前必问两句
  (CLAUDE.md「加门禁之前先问两句」),且必须带 `--selftest` 变异测试。
- **部署路径的默认值可能是灾难**:`.netlify/netlify.toml` 的默认 `publish` 一度指向整个仓库根目录,
  照它发布会把源码/`evidence/`/`docs/`/`tools/` 全传到公网。本轮已修(见 `netlify.toml` + `publish/`),
  但类似的「工具默认值 = 危险」模式值得在别处也留意。
- **heredoc 折转义**:用 bash heredoc 写 Python 补丁脚本时,正则里的 `\b` 会被折成字面退格符 0x08,
  正则从此永不匹配而门禁照样绿。对策:正则用 `(?<!\d)`/`(?!\d)` 代替 `\b`;补丁脚本反斜杠用 `chr(92)` 拼。
  `check_src.py` 的 S1 全仓扫这类控制符。
- **内容里的 `**` 不渲染**:node/幕的正文是纯文本,加粗要用 `<b>`,写 `**` 会原样显示给用户。
- **降级 WARN 也是静默放行**:S7 找不到原档时曾只报 WARN 就放行,好几份原档因此从没被核过。
  「检查还在,但它什么也没查」是这里最贵的失败。
- **na 题的选项长度会泄题**:「无法判断」是正确答案时,多写一句解释就等于把答案印在选项长度上
  (C13 门禁挡这个,但改内容时容易手滑踩回去,本轮改 D14 时踩过三次)。

## 关键文件地图(细节看 STRUCTURE.md)

| 要改什么 | 去哪 | 先读 |
|---|---|---|
| 第一章知识节点/题目 | `content/ch1/site.json` | SCHEMA.md(x_ 字段白名单)|
| 第二章知识节点/题目 | `content/ch2/site.json` | 同上 + `docs/records/审图_第二章.md` |
| 真实案例幕 | `content/stories/<id>/case.json` | 形态规格_故事驱动.md |
| 数字账本/原档登记 | `content/ch{1,2}/facts.json` + `evidence/` | 知识可靠性与LLM边界.md |
| 前端骨架/逻辑 | `src/template.html` + `src/parts/*.{css,js}` | DESIGN.md(改样式前必读)|
| 后端/隐私/LLM 端点 | `server/server.py` | server/README.md + LLM_USE_REGISTRY.md |
| 门禁 | `tools/check_*.py` `validate.py` | CLAUDE.md「加门禁之前先问两句」|
| 视觉令牌 | `design/tokens.json` | 令牌是视觉唯一真源,源码不许字面色值/字号 |
| 部署配置 | 根 `netlify.toml` | 不要用 `.netlify/netlify.toml` 的默认值 |

## 验证清单(接手后先跑一遍,确认环境干净)

```bash
python tools/build.py                    # 十道门禁,应全 PASS,产物 gzip <250KB
python tools/validate.py --selftest      # 门禁自检,应 7/7
python tools/check_coach.py --selftest   # 应 13/13
python tools/check_server.py --selftest  # 应 7/7
python tools/sign.py                     # 应显示 待签 0
git log --oneline -6                     # 最近提交,对照本文档判断是否已过时
```
