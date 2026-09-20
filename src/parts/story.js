/* ????? ? ????
   ???????????? STORY ??????case.json?????????????
   ????????????????????LLM ???????????? */
(function () {
  'use strict';

  const md = s => String(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const STORIES = SITE.x_stories || [];
  if (!STORIES.length) return;
  let STORY = STORIES[0];

  const el = document.getElementById('sty');
  const bodyEl = document.getElementById('sty-body');
  const footEl = document.getElementById('sty-foot');
  const dotsEl = document.getElementById('sty-dots');

  let ST = null;  // {i, pick, conf, twinOk, asked:[], done:Set}

  window.openStory = function (cid) {
    STORY = STORIES.find(s => s.case_id === cid) || STORIES[0];
    ST = { i: 0, pick: null, conf: null, twinOk: null, asked: [], seen: new Set(),
      mode: STORY.rpg && STORY.rpg.scenes ? 'rpg' : 'legacy',
      role: null, sceneId: STORY.rpg && STORY.rpg.initial_scene || null, rpgPath: null,
      rpgAction: null, rpgVoice: null, rpgReturn: null, rpgPressure: null };
    el.classList.add('show');
    track('story_open', { case: STORY.case_id });
    draw();
  };
  function close() {
    // ????????????z-index 79/80 ??????????????????
    // ??????????????? closeSheet ???????? onClose?
    window.__sheetClose = null;
    if (typeof closeSheet === 'function') closeSheet();
    el.classList.remove('show'); ST = null;
    window.__court = null;
    if (typeof render === 'function') render();
    if (typeof flush === 'function') flush();
  }
  document.getElementById('sty-x').onclick = close;

  const F = id => (SITE.x_facts || {})[id];

  function dots() {
    dotsEl.innerHTML = STORY.beats.map((_, i) =>
      `<i class="${i === ST.i ? 'on' : (i < ST.i ? 'done' : '')}"></i>`).join('');
  }

  function evPanel(p) {
    if (!p) return '';
    let h = `<div class="ev"><div class="hd"><span></span><span>${p.cols[0]}</span><span>${p.cols[1]}</span></div>`;
    for (const r of p.rows) {
      h += `<div class="rw"><span>${r.k}</span>` +
           `<span class="v${r.flagA ? ' flag' : ''}">${r.a}</span>` +
           `<span class="v${r.flagB ? ' flag' : ''}">${r.b}</span></div>`;
    }
    return h + '</div>';
  }
  function derived(list) {
    if (!list || !list.length) return '';
    return `<div class="derv">` + list.map(d =>
      `<div class="d"><div class="k">${d.k}</div><div class="v${d.flag ? ' flag' : ''}">${d.v}</div></div>`).join('') + `</div>`;
  }
  function docQuote(q) {
    return `<div class="doc"><div class="dh"><span>${ic('doc')} ${q.src}</span><span class="ln">${q.line}</span></div>
      <div class="dt">${q.text}</div></div>`;
  }
  function readingHTML(mine) {
    if (!mine || !mine.verdict) return '';
    const r = choiceReading(STORY, mine, ST.conf, ST.stats || { pressed: 0, broke: 0 }, ST.prior);
    const nm = coachName();
    return `<div class="reading"><div class="rd-hd"><span class="rd-av">${ic('coach')}</span>
        <span class="rd-nm">${nm}的解读</span></div>
      <p class="rd-h">${md(r.head)}</p><p class="rd-b">${md(r.body)}</p>
      ${r.extra.map(x => `<p class="rd-x">${md(x)}</p>`).join('')}</div>`;
  }
  function vo(t) {
    const c = (typeof coachName === "function") ? coachName() : "你的教练";
    return t ? `<div class="vo"><span class="who">${c}</span><span class="txt">${t}</span></div>` : '';
  }

  function draw() {
    if (!ST) return;   // ??????????????ST ? null
    if (ST.mode === 'rpg') return drawRpg();
    const b = STORY.beats[ST.i];
    ST.seen.add(b.id);
    dots();
    const R = ({
      cold_open: bCold, evidence: bEvid, decision: bDec,
      consequence: bConsequence, reveal: bReveal, contrast: bContrast, abstract: bAbstract, twin: bTwin
    })[b.kind](b);
    bodyEl.innerHTML = R.body;
    footEl.innerHTML = R.foot;
    bodyEl.scrollTop = 0;
    R.bind && R.bind();
    const n = document.getElementById('sty-next');
    if (n) n.onclick = () => { ST.i++; track('story_beat', { case: STORY.case_id, beat: b.id }); draw(); };
  }

  /* ===== ???? RPG ?? =====
     rpg.scenes ??????????????????????????????
     ????????????????????????? reveal beat ??? */
  function rpgScene() {
    if (ST.sceneId === '__rpg_pressure__') {
      const p = ST.rpgPressure || {};
      return { id: '__rpg_pressure__', eyebrow: '选择之后', place: p.place || '事件现场', time: p.time || '此刻',
        title: p.title || '后果正在发生', lines: p.lines || [], evidence: p.evidence || [],
        actions: [{ id: 'continue', kind: '后果', label: '继续前进', prompt: '看看你的选择如何改变局面',
          consequence: p.consequence || '', result_title: p.result_title || '选择的代价', narration: p.narration || '', next: ST.rpgReturn }] };
    }
    return (STORY.rpg.scenes || []).find(s => s.id === ST.sceneId);
  }
  const RPG_ZH = {
    'Before the decision':'决定之前','Historical decision room':'历史决策现场','The pressure is rising':'压力正在上升',
    'The second decision':'第二个决定','Investment committee':'投资委员会','The window is closing':'窗口正在关闭',
    'Build the evidence chain':'建立证据链','Evidence':'证据','Shortcut':'捷径','Risk budget':'风险预算','Conviction':'确信',
    'Research':'研究','Narrative':'叙事','Impulse':'冲动','Build the evidence chain before committing':'先建立证据链，再投入资金',
    'Trust the strongest narrative':'相信最有说服力的故事','Write the failure case first':'先写失败情形','Let the story decide':'让故事替你决定',
    'Test pricing power':'检验定价权','Define capital returns':'界定资本回报','Protect intrinsic value':'保护内在价值',
    'Test look-through analysis':'检验穿透分析','Define credit risk':'界定信用风险','Protect model limits':'守住模型边界',
    'Test observation to hypothesis':'检验从观察到假设的链条','Define growth quality':'界定增长质量','Protect valuation discipline':'守住估值纪律',
    'Test turnover':'检验周转效率','Define unit economics':'界定单位经济学','Protect quality versus price':'守住质量与价格的边界',
    'Test macro constraints':'检验宏观约束','Define catalysts':'界定催化因素','Protect risk budget':'守住风险预算',
    'Turn the story into variables you can verify.':'把故事拆成可以核对的变量。','The story is popular, simple, and emotionally convincing.':'这个故事流行、简单，而且很有感染力。',
    'Define the evidence that would change your mind.':'先定义什么证据会让你改变判断。','The opportunity feels too obvious to delay.':'机会看起来太明显，已经不容拖延。',
    'The story becomes a model':'故事变成了模型','The narrative goes first':'叙事抢在证据之前','The failure case gets a seat':'失败情形也坐上了桌面',
    'Conviction outruns evidence':'确信跑在证据前面','A useful story creates a question that can be falsified.':'有用的故事会变成一个可以被证伪的问题。',
    'Good decisions preserve the ability to make the next decision.':'好的决定会保留做出下一次决定的能力。','The most dangerous shortcut is the one that feels like courage.':'最危险的捷径，往往感觉最像勇气。',
    'You gain speed but lose the evidence chain. The next pressure is to explain what your shortcut cannot see.':'你获得了速度，却失去了证据链。接下来的压力，是解释这条捷径看不见什么。',
    'Confidence is not evidence just because many people share it.':'很多人相信，不会让确信变成证据。',
    'You turn pricing power into a checklist. The next decision must answer what drives the business and what can break it.':'你把定价权拆成核查清单。下一步必须回答：什么驱动这门生意，又有什么会击穿它。',
    'You turn look-through analysis into a checklist. The next decision must answer what drives the business and what can break it.':'你把穿透分析拆成核查清单。下一步必须回答：什么驱动这门生意，又有什么会击穿它。',
    'You turn observation to hypothesis into a checklist. The next decision must answer what drives the business and what can break it.':'你把从观察到假设的过程拆成核查清单。下一步必须回答：什么驱动这门生意，又有什么会击穿它。',
    'You turn turnover into a checklist. The next decision must answer what drives the business and what can break it.':'你把周转效率拆成核查清单。下一步必须回答：什么驱动这门生意，又有什么会击穿它。',
    'You turn macro constraints into a checklist. The next decision must answer what drives the business and what can break it.':'你把宏观约束拆成核查清单。下一步必须回答：什么驱动这门生意，又有什么会击穿它。',
    'You keep capital returns separate from the final price. The decision is now auditable even if the outcome is uncertain.':'你把资本回报和最终价格分开。即使结果不确定，这个决定也已经可以复核。',
    'You keep credit risk separate from the final price. The decision is now auditable even if the outcome is uncertain.':'你把信用风险和最终价格分开。即使结果不确定，这个决定也已经可以复核。',
    'You keep growth quality separate from the final price. The decision is now auditable even if the outcome is uncertain.':'你把增长质量和最终价格分开。即使结果不确定，这个决定也已经可以复核。',
    'You keep unit economics separate from the final price. The decision is now auditable even if the outcome is uncertain.':'你把单位经济学和最终价格分开。即使结果不确定，这个决定也已经可以复核。',
    'You keep catalysts separate from the final price. The decision is now auditable even if the outcome is uncertain.':'你把催化因素和最终价格分开。即使结果不确定，这个决定也已经可以复核。',
    'Evidence table':'证据表','What must be verified?':'哪些内容必须核对？','Information available then':'当时能看到的信息',
    'Historical record':'历史原档','The result is not the lesson':'结果不是要点','Debrief':'复盘','What the method adds':'这套方法多做了什么',
    'Transferable method':'可以迁移的方法','Method card':'方法卡','A reusable decision loop':'一套可以复用的判断循环',
    'Turn an exciting story into a falsifiable question, then price the uncertainty.':'把令人兴奋的故事变成可证伪的问题，再给不确定性定价。',
    'The room wants a decision before every uncertainty is resolved.':'现场要求现在就决定，所有不确定性还没有消失。',
    'Your choice':'你的选择','The public record preserves the decision context, the evidence, and the consequences.':'公开原档保留了决策背景、证据和后果。',
    'History lets you inspect the ending. The skill is learning what could have been known before the ending.':'历史让你看见结局；关键训练是，结局发生前你本来能知道什么。'
  };
  function rpgText(value) { return typeof value === 'string' ? (RPG_ZH[value] || value) : value; }
  function rpgBeat(id) { return STORY.beats.find(b => b.id === id); }
  function rpgActions(s) {
    return (s.actions || []).filter(a => !a.roles || a.roles.includes(ST.role));
  }
  function rpgDecisionGuide(s, available) {
    if (!available.length) return '';
    const prompt = rpgText(s.prompt) || '如果这场会议由你拍板，你先做哪一步？';
    return `<div class="rpg-guide"><div class="rpg-kicker">轮到你了</div><p>${md(prompt)}</p>
      <small>按此刻的判断选。结果出现后，再看自己漏了什么。</small></div>`;
  }
  const RPG_SCENE_ZH = {
    'buffett-coke-1988': ['管理层把品牌、渠道和全球增长摆上桌面。你的任务，是把掌声拆成可以核对的经营变量。','先从单位经济学开始：客户愿意持续为哪一部分付钱？'],
    'burry-mortgage-2007': ['一只结构化证券经过评级和分散化，看起来很安全。你的任务，是沿着现金流找到实际的付款人。','先看借款人、合同条款，以及损失会从哪里开始。'],
    'lynch-fidelity-1985': ['货架上的产品很受欢迎，自己的生活也能感受到它。这个观察只有变成可检验的问题，才有投资价值。','先写下假设，再去年报里找能支持或推翻它的数字。'],
    'munger-costco-1999': ['仓库里堆着低价、快周转的商品。单看毛利率，解释不了这套生意如何运转。','先看顾客得到的价值、周转速度，以及维持规模需要多少资本。'],
    'soros-gbp-1992': ['市场听见政府要守住一种货币。你的任务，是找出承诺背后的工具、约束和代价。','先看制度约束，不要先跟着最响亮的标题走。']
  };
  const RPG_TITLE_ZH = {
    'buffett-coke-1988':'亚特兰大：品牌到底值多少钱？','burry-mortgage-2007':'评级背后的住房贷款','lynch-fidelity-1985':'购物车里的线索',
    'munger-costco-1999':'仓库里那个一美元的问题','soros-gbp-1992':'伦敦：哪一种约束会赢？'
  };
  const RPG_SECOND_ZH = {
    'buffett-coke-1988':['把好生意和买入价格分开。','再好的系统，也不能替你免除价格纪律。'],
    'burry-mortgage-2007':['把模型结果和底层现金流分开。','模型可以整洁，调查不能因此结束。'],
    'lynch-fidelity-1985':['把日常观察和原始证据分开。','增长必须同时出现在收入、利润、现金和合理价格里。'],
    'munger-costco-1999':['把经营质量和估值分开。','一套优秀的系统，也不能成为忽略价格的理由。'],
    'soros-gbp-1992':['把方向判断和仓位大小分开。','观点正确，也可能因为没有定义亏损预算而失败。']
  };
  function rpgLines(s) {
    const lines = s.lines || [];
    const translated = RPG_SCENE_ZH[STORY.case_id];
    if (translated && s.id === 'decision-room') return translated;
    const second = RPG_SECOND_ZH[STORY.case_id];
    return second && s.id === 'pressure-room' ? [second[1]] : lines.map(rpgText);
  }
  function rpgEvidence(ids) {
    return (ids || []).map(rpgBeat).filter(Boolean).map(b => {
      if (b.panel && b.panel.kind === 'list') {
        const rows = (b.panel.rows || []).map(r => `<div class="rpg-role"><div class="rpg-kicker">${esc(rpgText(r.k || ''))}</div><div class="rpg-title">${esc(rpgText(r.v || ''))}</div></div>`).join('');
        const note = typeof b.derived === 'string' ? `<p class="rpg-pressure">${md(b.derived)}</p>` : derived(b.derived);
        return `<div class="rpg-evidence-list">${b.panel.title ? `<div class="eyebrow">${esc(rpgText(b.panel.title))}</div>` : ''}${rows}</div>${note}`;
      }
      if (b.panel) return `${evPanel(b.panel)}${derived(b.derived)}`;
      if (b.quote) return docQuote(b.quote);
      return '';
    }).join('');
  }
  function rpgRoleCard() {
    const role = (STORY.rpg.roles || []).find(r => r.id === ST.role);
    const goals = { researcher:'核对证据链', risk:'定义失败边界', allocator:'保护资本安全边界' };
    return role ? `<div class="rpg-active-role"><span>当前身份</span><b>${esc(rpgText(role.title))}</b><small>${esc(rpgText(role.goal) || goals[role.id] || '把判断落到证据上')}</small></div>` : '';
  }
  function drawRpg() {
    const r = STORY.rpg;
    if (!ST.role) return drawRpgRoles();
    const s = rpgScene();
    if (!s) return drawRpgFinish();
    const available = rpgActions(s);
    const action = available.find(a => a.id === ST.rpgAction);
    const final = s.final === true;
    const voice = action ? (ST.rpgVoice || rpgText(action.narration) || '') : '';
    const actions = action ? '' : available.map(a =>
      `<button class="rpg-action" data-rpg-action="${esc(a.id)}"><span class="rpg-action-kind">${esc(rpgText(a.kind || '行动'))}</span><b>${esc(rpgText(a.label))}</b><small>${esc(rpgText(a.prompt || ''))}</small></button>`).join('');
    const conf = final && action ? `<div class="eyebrow rpg-conf-label">你对这个判断有多大把握？</div>
      <div class="seg2">${CONF.map(c => `<button data-rpg-conf="${c.v}" class="${ST.conf === c.v ? 'on' : ''}">${c.t}</button>`).join('')}</div>` : '';
    const nextDisabled = final ? !action || ST.conf == null : !action;
    const nextScene = action && (r.scenes || []).find(x => x.id === action.next);
    const nextLabel = final ? '揭开历史结果' : (nextScene?.eyebrow === '故事高潮' ? '进入最后决定' : '继续看局势怎么变');
    const sceneIndex = (r.scenes || []).findIndex(x => x.id === s.id);
    const basePhase = sceneIndex === 0 ? '故事开始' : (final ? '故事高潮' : '故事发展');
    const ownPhase = rpgText(s.eyebrow || '');
    const scenePhase = ownPhase && !['故事开始', '故事发展', '故事高潮'].includes(ownPhase)
      ? `${basePhase} · ${ownPhase}` : (ownPhase || basePhase);
    bodyEl.innerHTML = `<div class="eyebrow">${esc(rpgText(scenePhase))}</div>
      <div class="rpg-scene-meta"><span>${esc(rpgText(s.place || ''))}</span><span>${esc(rpgText(s.time || ''))}</span></div>
      <h2>${esc(s.id === 'pressure-room' && RPG_SECOND_ZH[STORY.case_id] ? RPG_SECOND_ZH[STORY.case_id][0] : (RPG_TITLE_ZH[STORY.case_id] && s.id === 'decision-room' ? RPG_TITLE_ZH[STORY.case_id] : rpgText(s.title)))}</h2>${rpgRoleCard()}
      ${(s.path_lines?.[ST.rpgPath] || s.role_lines?.[ST.role] || rpgLines(s)).map(x => `<p class="ln">${md(rpgText(x))}</p>`).join('')}
      ${rpgEvidence(s.evidence)}
      ${action ? `<div class="rpg-result"><div class="rpg-kicker">发生了什么</div><div class="rpg-result-title">${esc(rpgText(action.result_title || '行动结果'))}</div>
        <p class="ln">${md(rpgText(action.consequence || ''))}</p>
        <p class="rpg-pressure" id="rpg-voice-${STORY.case_id}"><b>画外音</b>${md(voice)}</p></div>` : `${rpgDecisionGuide(s, available)}<div class="rpg-actions">${actions}</div>`}`;
    footEl.innerHTML = action ? `${final ? conf : ''}<button class="sty-cta" id="rpg-next" ${nextDisabled ? 'disabled' : ''}>${nextLabel}</button>` : '';
    dotsEl.innerHTML = (r.scenes || []).map(x => `<i class="${x.id === s.id ? 'on' : ''}"></i>`).join('');
    if (action) narrateChoice(action, 'rpg-voice-' + STORY.case_id);
    bindRpg(s);
  }
  function drawRpgRoles() {
    const r = STORY.rpg;
    const goals = { researcher:'核对证据链', risk:'定义失败边界', allocator:'保护资本安全边界' };
    const pressure = { researcher:'现场催你先给出依据。', risk:'大家都在奖励确信。', allocator:'机会看起来正在消失。' };
    bodyEl.innerHTML = `<div class="eyebrow">角色选择</div><h2>${esc(STORY.title || '选择你的身份')}</h2>
      <p class="ln">${md(STORY.hook || r.premise || '')}</p><div class="rpg-role-list">${(r.roles || []).map(x =>
        `<button class="rpg-role-choice" data-rpg-role="${esc(x.id)}"><b>${esc(rpgText(x.title))}</b><span>${esc(rpgText(x.goal) || goals[x.id])}</span><small>${esc(rpgText(x.pressure || '') || pressure[x.id])}</small></button>`).join('')}</div>`;
    bodyEl.insertAdjacentHTML('afterbegin', learningCard(STORY.rpg.learning_goal || STORY.learning_goal, STORY.rpg.learning_skills || STORY.skills));
    footEl.innerHTML = '';
    dotsEl.innerHTML = `<i class="on"></i>${(r.scenes || []).map(() => '<i></i>').join('')}`;
    bodyEl.querySelectorAll('[data-rpg-role]').forEach(x => x.onclick = () => {
      ST.role = x.dataset.rpgRole; ST.sceneId = r.initial_scene; ST.rpgAction = null; ST.rpgPath = null;
      track('story_role', { case: STORY.case_id, role: ST.role }); draw();
    });
  }
  function bindRpg(s) {
    bodyEl.querySelectorAll('[data-rpg-action]').forEach(x => x.onclick = () => {
      ST.rpgAction = x.dataset.rpgAction;
      const a = rpgActions(s).find(y => y.id === ST.rpgAction);
      if (s.final && a && ['a', 'b', 'c'].includes(a.id)) ST.pick = a.id;
      track('story_action', { case: STORY.case_id, scene: s.id, action: ST.rpgAction, role: ST.role });
      draw();
    });
    footEl.querySelectorAll('[data-rpg-conf]').forEach(x => x.onclick = () => { ST.conf = +x.dataset.rpgConf; draw(); });
    const next = document.getElementById('rpg-next');
    if (next) next.onclick = () => {
      const a = rpgActions(s).find(y => y.id === ST.rpgAction);
      if (!a) return;
      if (s.id === '__rpg_pressure__') {
        ST.sceneId = a.next; ST.rpgAction = null; ST.rpgPressure = null;
      } else if (s.final || a.next === '__legacy_reveal') {
        if (STORY.rpg && (STORY.rpg.learning_goal || STORY.learning_goal || STORY.skills)) {
          S.storyLearning = S.storyLearning || {};
          S.storyLearning[STORY.case_id] = { goal: STORY.rpg.learning_goal || STORY.learning_goal, skills: STORY.rpg.learning_skills || STORY.skills || [], at: Date.now() };
          save();
          track('story_learning_checkpoint', { case: STORY.case_id, skills: (STORY.rpg.learning_skills || STORY.skills || []).length });
        }
        ST.mode = 'legacy'; ST.i = STORY.beats.findIndex(x => x.kind === 'reveal');
        if (ST.i < 0) ST.i = 0;
      } else {
        ST.rpgPath = ST.rpgAction; ST.sceneId = a.next; ST.rpgAction = null; ST.rpgVoice = null;
      }
      draw();
    };
  }
  function drawRpgFinish() { ST.mode = 'legacy'; draw(); }

  function learningCard(goal, skills) {
    if (!goal && !(skills || []).length) return '';
    return `<div class="rpg-learning"><div class="rpg-kicker">学习目标</div><p>${esc(rpgText(goal || ''))}</p>
      <div class="rpg-skill-list">${(skills || []).map(x => `<span>${esc(rpgText(x))}</span>`).join('')}</div></div>`;
  }

  function roleCard() {
    const r = STORY.rpg;
    if (!r || !r.role) return '';
    return `<div class="rpg-role"><div class="rpg-kicker">角色约束</div>
      <div class="rpg-title">${esc(r.role.title)}</div>
      <div class="rpg-goal"><b>目标</b>${esc(r.role.goal)}</div>
      <div class="rpg-goal"><b>约束</b>${esc(r.role.constraint)}</div></div>`;
  }

  function beatPhase(b) {
    const phase = {
      cold_open: '故事开始', evidence: '故事发展', consequence: '故事发展',
      decision: '故事高潮', reveal: '历史翻牌', contrast: '收获',
      abstract: '收获', twin: '尾声'
    }[b.kind] || '故事发展';
    const own = (b.eyebrow || '').trim();
    const standard = new Set(['故事开始', '故事发展', '故事高潮', '历史翻牌', '收获', '尾声']);
    return own && !standard.has(own) ? `${phase} · ${own}` : phase;
  }

  /* ????????owner ??????????????????????????
     ?????????????????????????????????????? */
  function ctxStrip(items) {
    if (!items || !items.length) return '';
    return `<div class="ctx"><div class="ctx-h">当时</div>${items.map(c =>
      `<div class="ctx-i"><span class="ctx-d">${c.date}</span><span class="ctx-t">${md(c.t)}</span>${c.src ? `<span class="ctx-s">${c.src}${c.line ? ' ? ' + c.line : ''}</span>` : ''}</div>`).join('')}</div>`;
  }

  /* S0 ??? */
  function bCold(b) {
    return {
      body: `<div class="eyebrow">${beatPhase(b)}</div><h2>${b.title}</h2>
        ${roleCard()}
        ${ctxStrip(b.context)}
        ${b.lines.map((l, i) => `<p class="ln${i === b.lines.length - 1 ? '' : ' dim'}">${md(l)}</p>`).join('')}
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">看看局势怎么变</button>`
    };
  }

  /* ???????????????????????????????????? */
  function bConsequence(b) {
    const path = (b.paths || {})[ST.pick] || {};
    const voiceId = 'rpg-voice-' + STORY.case_id;
    return {
      body: `<div class="eyebrow">${beatPhase(b)}</div><h2>${path.title || b.title}</h2>
        <div class="rpg-consequence"><p class="ln">${md(path.body || '')}</p>
          <p class="rpg-pressure"><b>画外音</b>${md(path.pressure || '')}</p></div>
        <div id="${voiceId}">${vo(path.narration || '')}</div>`,
      foot: `<button class="sty-cta" id="sty-next">继续</button>`,
      bind() { narrateChoice(path, voiceId); }
    };
  }

  function narrateChoice(path, targetId) {
    const r = STORY.rpg, target = document.getElementById(targetId);
    if (!r || !r.narrator || !target || typeof BACKEND === 'undefined' || !BACKEND) return;
    target.innerHTML = vo('先别急着往下翻。画外音正在把你的选择放回当时的处境里。');
    const ctl = new AbortController();
    const tm = setTimeout(() => ctl.abort(), 12000);
    fetch(BACKEND + '/api/v1/story-narrate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: ctl.signal,
      body: JSON.stringify({ device: S.device, case_id: STORY.case_id,
        narrator: r.narrator, choice: path.title || path.label, pressure: path.pressure || path.consequence,
        seed: path.narration, question: '请解释这次选择带来的压力。' })
    }).then(x => x.json()).then(d => {
      clearTimeout(tm);
      if (d && d.text && target) target.innerHTML = vo(esc(d.text));
    }).catch(() => clearTimeout(tm));
  }

  /* S1/S2 ??? */
  function bEvid(b) {
    return {
      body: `<div class="eyebrow">${beatPhase(b)}</div><h2>${b.title}</h2>
        ${evPanel(b.panel)}${derived(b.derived)}
        <div class="qchips">${(b.panel.rows || []).filter(r => r.fact).map(r =>
          `<button data-f="${r.fact}">${ic('link')} ${r.k}</button>`).join('')}</div>
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">查看下一页</button>`,
      bind() { bindFacts(); }
    };
  }
  function bindFacts() {
    bodyEl.querySelectorAll('[data-f]').forEach(x => x.onclick = () => {
      const f = F(x.dataset.f);
      if (!f) return;
      sheet(`<h3 style="margin:0 0 8px;font-size:17px">${ic('link')} 原档事实</h3>
        <p style="font-size:17px;line-height:1.8"><b>${f.item}</b><br>${f.value}</p>
        <p class="tip">依据：${f.basis || '未填写'}<br>出处：${f.accession || '未填写'} · ${f.line || ''}<br>公司：${f.company || '未填写'}</p>
        <p class="tip">这条证据来自已归档的原始材料。</p>`);
    });
  }

  /* S3 ?? ?? ???????? */
  function bDec(b) {
    const picked = ST.pick != null, conf = ST.conf != null;
    return {
      body: `<div class="eyebrow">${beatPhase(b)}</div><h2>${b.title}</h2>
        <p class="ln">${b.prompt}</p>
        ${b.ask_enabled && STORY.interrogation ? (() => {
          const c = window.__court && window.__court.story === STORY ? window.__court.stats : null;
          const acted = c ? (c.pressed || 0) + (c.broke || 0) : 0;
          const label = !acted
            ? `向${STORY.cast[0].name}追问 · ${STORY.interrogation.testimony.length} 条陈述`
            : `已追问${STORY.cast[0].name} · ${c.pressed} 次${c.broke ? ` · 找到破绽 ${c.broke} 处` : ''}`;
          return `<button class="askbtn${acted ? ' done' : ''}" id="sty-ask">${ic('scale')} ${label}</button>`;
        })() : ''}
        ${b.options.map(o => `<button class="choice${ST.pick === o.id ? ' on' : ''}" data-p="${o.id}">
            <span class="kd">${o.kind}</span>${o.t}</button>`).join('')}
        ${picked ? `<div class="eyebrow" style="margin-top:20px">信心</div>
          <div class="seg2">${CONF.map(c => `<button data-cf="${c.v}" class="${ST.conf === c.v ? 'on' : ''}">${c.t}</button>`).join('')}</div>` : ''}`,
      foot: `<button class="sty-cta" id="sty-next" ${picked && conf ? '' : 'disabled'}>确认判断</button>`,
      bind() {
        bodyEl.querySelectorAll('[data-p]').forEach(x => x.onclick = () => { ST.pick = x.dataset.p; draw(); });
        bodyEl.querySelectorAll('[data-cf]').forEach(x => x.onclick = () => { ST.conf = +x.dataset.cf; draw(); });
        const a = document.getElementById('sty-ask');
        if (a) a.onclick = () => Court.open(STORY, () => draw());
      }
    };
  }

  /* S4 ?? */
  function bReveal(b) {
    const factButton = b.quote.fact ? `<div class="qchips"><button data-f="${b.quote.fact}">${ic('link')} 查看原档</button></div>` : '';
    return {
      body: `<div class="eyebrow">${beatPhase(b)}</div><h2>${b.title}</h2>
        ${docQuote(b.quote)}
        ${b.lines.map(l => `<p class="ln">${md(l)}</p>`).join('')}
        ${factButton}
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">回看我的决定</button>`,
      bind() { bindFacts(); }
    };
  }

  /* S5 ???? + knowhow */
  function bContrast(b) {
    const dec = STORY.beats.find(x => x.kind === 'decision');
    const mine = (dec.options || []).find(o => o.id === ST.pick) || { t: '未选择', kind: '?' };
    const confT = (CONF.find(c => c.v === ST.conf) || {}).t || '?';
    if (!ST.logged) {
      ST.logged = true;
      track('story_decision', { case: STORY.case_id, pick: ST.pick, verdict: mine.verdict, conf: ST.conf });
      const cs = (window.__court && window.__court.story === STORY) ? window.__court.stats : { pressed: 0, broke: 0, noRecord: 0 };
      ST.stats = cs;
      ST.prior = JSON.parse(JSON.stringify(profile()));   // ????????????????
      // ???????**???**??? contrast ???????????? S ??
      // ST ?? openStory ?????? ST ????????????????????
      // ??????????????
      S.storySeen = S.storySeen || {};
      if (!S.storySeen[STORY.case_id]) {
        S.storySeen[STORY.case_id] = true;
        updateProfile(STORY.case_id, mine, ST.conf, cs);
      }
      // ??????????????????**?????????**??
      // ????? finish() ? S.story[cid]????????
      S.storyPick = S.storyPick || {};
      S.storyPick[STORY.case_id] = { pick: ST.pick, verdict: mine.verdict, conf: ST.conf, at: Date.now() };
      save();
    }
    return {
      body: `<div class="eyebrow">${beatPhase(b)}</div><h2>${b.title}</h2>
        <div class="trio">
          <div class="c you"><div class="lbl">${b.columns.you}</div>
            <div class="hd2">${mine.t}</div>
            <div class="dt2">信心：${confT}</div></div>
          <div class="c"><div class="lbl">${b.columns.them}</div>
            <div class="hd2">${b.them.t}</div><div class="dt2">${b.them.detail}</div></div>
          <div class="c canon"><div class="lbl">${b.columns.canon}</div>
            <div class="hd2">${b.canon.t}</div><div class="dt2">${b.canon.detail}<br><span style="opacity:.75">${b.canon.src}</span></div></div>
        </div>
        ${readingHTML(mine)}
        <div class="kn"><h3>带走的方法</h3><ul>${b.knowhow.map(k => `<li>${md(k)}</li>`).join('')}</ul></div>
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">把方法说清楚</button>`
    };
  }

  /* S6 ???? */
  function bAbstract(b) {
    const story = b.story_form ? `<div class="f"><div class="t">这次的故事</div><div class="b">${b.story_form}</div></div>` : '';
    const boundary = b.boundary ? `<p class="ln dim">什么时候不能这么用：${b.boundary}</p>` : '';
    return {
      body: `<div class="eyebrow">${beatPhase(b)}</div><h2>${b.title}</h2>
        <div class="fade3">
          ${story}
          <div class="f"><div class="t">下次先问</div><div class="b">${b.rule}</div></div>
          <div class="f"><div class="t">记住这条关系</div><div class="b">${b.formula}</div></div>
          <div class="f tag"><div class="t">检查顺序</div><div class="b">${b.label}</div></div>
        </div>
        ${boundary}
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">换个现场试一次</button>`
    };
  }

  /* S7 ?????????????????? */
  function bTwin(b) {
    const answered = ST.twinOk != null;
    return {
      body: `<div class="eyebrow">${beatPhase(b)}</div><h2>${b.title}</h2>
        ${evPanel(b.panel)}
        <p class="ln">${b.question}</p>
        ${b.options.map((o, i) => `<button class="choice${ST.twinPick === i ? ' on' : ''}" data-t="${i}" ${answered ? 'disabled' : ''}>${o.t}</button>`).join('')}
        ${answered ? `<div class="kn"><p style="font-size:17px;line-height:1.85;margin:0">${b.fb}</p></div>` : ''}
        ${answered ? vo(b.narration) : ''}`,
      foot: answered
        ? `<button class="sty-cta" id="sty-done">收下这次判断</button>`
        : `<button class="sty-cta" disabled>先做出你的选择</button>`,
      bind() {
        bodyEl.querySelectorAll('[data-t]').forEach(x => x.onclick = () => {
          const i = +x.dataset.t;
          ST.twinPick = i; ST.twinOk = !!b.options[i].ok;
          track('story_twin', { case: STORY.case_id, correct: ST.twinOk ? 1 : 0 });
          draw();
        });
        const d = document.getElementById('sty-done');
        if (d) d.onclick = finish;
      }
    };
  }

  function finish() {
    const node = STORY.knowledge_node;
    bodyEl.innerHTML = `<div class="fin">
      <div class="fin-ic">${ic('doc')}</div>
      <h2>案例完成</h2>
      <p class="ln">你已经把这次事件里的判断、证据和后果走完了一遍。</p>
      <p class="ln dim">把这套方法带到下一份真实年报里。</p>
      ${vo('下一次遇到相似材料，先问：我现在看到的是事实、解释，还是愿望？')}</div>`;
    footEl.innerHTML = `<button class="sty-cta" id="sty-toprac">回到现场</button>
      <div style="height:8px"></div>
      <button class="sty-cta ghost" id="sty-back">查看档案</button>`;
    // ???? ? ???????????????????
    if (typeof ensurePair === 'function') {
      const n = byId[node];
      let pairs = (n && n.x_pairs || []).filter(p => p.id);
      if (!pairs.length) {
        // ??????base-rate / falsification?????????
        // ????? cross ????????????????????????????
        const down = (SITE.edges || []).filter(e => e.from === node).map(e => byId[e.to]).filter(Boolean);
        pairs = down.flatMap(d => (d.x_pairs || []).filter(p => p.id)).slice(0, 2);
      }
      pairs.forEach(p => ensurePair(p.id));
      if (!pairs.length) console.warn('??', STORY.case_id, '???????', node, '???????');
      save();
    }
    // ?????????????????????contrast ?????????
    // ??? abstract / twin ???????????????????????
    // ?????????????????????????????????????????
    S.story = S.story || {};
    S.story[STORY.case_id] = Object.assign(
      { at: Date.now() }, (S.storyPick || {})[STORY.case_id], { done: 1 });
    save();
    track('story_finish', { case: STORY.case_id });
    document.getElementById('sty-toprac').onclick = () => {
      close();
      // ??????????? openNode?????????????????????
      // ??????????????????????????? openNode ????
      if (typeof openNode === 'function') openNode(node);
    };
    document.getElementById('sty-back').onclick = close;
  }

  /* ===== ????????????? ===== */
  /* ?????????openAsk / drawAsk / turnHTML / ask / resolveQA / matchQA?????
     ??????????case.json ? ask ??????????????????
     ?court.js?????????????????????????????????????
     ????????????????????????? 2026-08-26? */
})();
