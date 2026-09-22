/* 真实事件故事播放器。
   叙事、数据与角色约束来自 case.json；历史原话、史实摘要和 AI 推演必须明确分层。 */
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
      rpgAction: null, rpgDraft: null, rpgReturn: null, rpgPressure: null, rpgHistory: [] };
    el.classList.add('show');
    track('story_open', { case: STORY.case_id });
    draw();
  };
  function close() {
    // 先关闭证据抽屉，再退出故事，避免遮罩残留拦住首页交互。
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
    if (p.kind === 'list' || !Array.isArray(p.cols)) {
      return `<div class="ev ev-list">${p.title ? `<div class="ev-list-title">${esc(p.title)}</div>` : ''}${(p.rows || []).map(r =>
        `<div class="ev-list-row"><span>${esc(r.k || '')}</span><strong>${md(r.v || r.a || '')}</strong>${r.fact ? factButton(r.fact, '核对来源') : ''}</div>`
      ).join('')}</div>`;
    }
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
    if (typeof list === 'string') return `<div class="derv text"><div class="d"><div class="v">${md(list)}</div></div></div>`;
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
    if (!ST) return;
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
    if (n) n.onclick = () => {
      track('story_beat', { case: STORY.case_id, beat: b.id });
      if (ST.i + 1 >= STORY.beats.length) return close();
      ST.i++; draw();
    };
  }

  function rpgText(value) { return value; }
  function rpgBeat(id) { return STORY.beats.find(b => b.id === id); }
  function drawRpgFinish() {
    ST.mode = 'legacy';
    ST.i = STORY.beats.findIndex(x => x.kind === 'reveal');
    if (ST.i < 0) ST.i = 0;
    draw();
  }

  /* ===== 史料驱动 RPG v2 =====
     旧播放器保留给已经进入「历史翻牌」的兼容拍；进入事件后的体验只读 case.json，
     不再用前端翻译表改写故事，也不再让生成式画外音替代证据。 */
  function rpgScene() { return (STORY.rpg.scenes || []).find(s => s.id === ST.sceneId); }
  function activeRole() { return (STORY.rpg.roles || []).find(r => r.id === ST.role) || {}; }
  function rpgActions(s) { return (s.actions || []).filter(a => !a.roles || a.roles.includes(ST.role)); }
  function deliberation(s, a) { return ((STORY.rpg.deliberations || {})[`${s.id}.${a.id}`] || {}); }
  function scrollRpgTo(selector) {
    requestAnimationFrame(() => {
      const node = bodyEl.querySelector(selector);
      if (node) bodyEl.scrollTop = Math.max(0, node.offsetTop - 24);
    });
  }
  function roleValue(v) { return v && typeof v === 'object' && !Array.isArray(v) ? (v[ST.role] || v.default || '') : (v || ''); }
  function sceneLines(s) {
    const byPath = s.path_lines && ST.rpgPath ? s.path_lines[ST.rpgPath] : null;
    return byPath || (s.role_lines && s.role_lines[ST.role]) || s.lines || [];
  }
  function factButton(id, label) {
    return id ? `<button class="rpg-source" data-f="${esc(id)}">${ic('link')} ${esc(label || '查看原始材料')}</button>` : '';
  }
  function timelineHTML(items) {
    if (!items || !items.length) return '';
    return `<section class="rpg-timeline"><div class="rpg-section-label">事情走到这里</div>${items.map(x =>
      `<div class="rpg-time"><time>${esc(x.date)}</time><div><b>${esc(x.title || '')}</b><p>${md(x.text || '')}</p>${factButton(x.fact, '核对来源')}</div></div>`).join('')}</section>`;
  }
  function briefingHTML(items) {
    const visible = items || [];
    if (!visible.length) return '';
    const focus = activeRole().focus || {};
    return `<section class="rpg-ledger"><div class="rpg-section-label">案头数据${focus.knowledge ? ` · 用来判断${esc(focus.knowledge)}` : ''}</div>${visible.map(x =>
      `<article class="rpg-number${!x.roles || x.roles.includes(ST.role) ? ' is-focus' : ''}"><span>${esc(x.label)}</span><strong>${esc(x.value)}</strong>${x.note ? `<p>${md(x.note)}</p>` : ''}${factButton(x.fact, '查看口径与出处')}</article>`).join('')}</section>`;
  }
  function termsHTML(ids) {
    const all = STORY.rpg.glossary || [];
    const items = (ids || []).map(id => all.find(x => x.id === id)).filter(Boolean);
    return items.length ? `<div class="rpg-terms"><span>本节术语</span>${items.map(x => `<button data-term="${esc(x.id)}">${esc(x.term)}？</button>`).join('')}</div>` : '';
  }
  function decisionFrame(s) {
    const known = roleValue(s.known), unknown = roleValue(s.unknown), decision = roleValue(s.decision) || s.prompt;
    if (!known && !unknown && !decision) return '';
    return `<section class="rpg-frame"><div><span>已经知道</span><p>${md(known || '材料已经列在上方。')}</p></div>
      <div><span>仍不知道</span><p>${md(unknown || '结果尚未发生。')}</p></div>
      <div class="ask"><span>你必须决定</span><p>${md(decision || '下一步做什么？')}</p></div></section>`;
  }
  function roleBrief() {
    const r = activeRole();
    const f = r.focus || {}, term = (STORY.rpg.glossary || []).find(x => x.term === f.knowledge);
    const knowledge = term
      ? `<button class="rpg-focus-term" data-term="${esc(term.id)}">${esc(f.knowledge)} ${ic('right')}</button>`
      : `<strong>${esc(f.knowledge || '')}</strong>`;
    return `<section class="rpg-mission"><div class="rpg-section-label">你的席位 · ${esc(r.title || '')}</div>
      <p>${md(r.brief || r.goal || '')}</p>${f.knowledge ? `<div class="rpg-focus"><div><span>这次要学会</span>${knowledge}</div>
      <div><span>先看哪组数</span><b>${esc(f.watch || '')}</b></div><div><span>这些数说明什么</span><p>${md(f.read || '')}</p></div></div>` : ''}
      <dl><div><dt>你要交付</dt><dd>${esc(r.win_condition || r.goal || '')}</dd></div><div><dt>最容易看错</dt><dd>${esc(r.risk || r.pressure || '')}</dd></div></dl></section>`;
  }
  function continuityHTML() {
    const last = ST.rpgHistory && ST.rpgHistory[ST.rpgHistory.length - 1];
    if (!last || !last.assumption || !last.verify) return '';
    return `<section class="rpg-continuity"><div class="rpg-section-label">上一决定还没结束</div>
      <p><b>${esc(last.label)}</b>把一个前提带进了现在：${md(last.assumption)}</p>
      <p><span>这一段继续追</span>${md(last.verify)}</p></section>`;
  }
  function rpgEvidenceV2(ids) {
    return (ids || []).map(rpgBeat).filter(Boolean).map(b => {
      if (b.panel) return `<section class="rpg-legacy-evidence"><div class="rpg-section-label">当时的材料</div>${evPanel(b.panel)}${derived(b.derived)}</section>`;
      if (b.quote) return docQuote(b.quote);
      return '';
    }).join('');
  }
  function resultHTML(a) {
    const d = deliberation(rpgScene(), a);
    const used = roleValue(a.evidence_used), missed = roleValue(a.evidence_missed), tradeoff = roleValue(a.tradeoff);
    return `<section class="rpg-audit"><div class="rpg-section-label">决策复盘</div><h3>${esc(a.result_title || '局面改变了')}</h3>
      <p class="rpg-outcome">${md(a.consequence || '')}</p><dl>
      ${used ? `<div><dt>你用到的证据</dt><dd>${md(used)}</dd></div>` : ''}${missed ? `<div><dt>你漏掉的证据</dt><dd>${md(missed)}</dd></div>` : ''}${tradeoff ? `<div><dt>这一步的代价</dt><dd>${md(tradeoff)}</dd></div>` : ''}</dl>
      ${d.lesson ? `<p class="rpg-takeaway"><b>${esc(activeRole().focus?.knowledge || '知识落点')}</b>${md(d.lesson)}</p>` : ''}
      ${a.narration ? `<p class="rpg-afterword"><b>继续往下想</b>${md(a.narration)}</p>` : ''}</section>`;
  }
  function deliberationHTML(s, a) {
    const d = deliberation(s, a), focus = activeRole().focus || {};
    return `<section class="rpg-deliberation"><div class="rpg-section-label">决策草稿 · ${esc(focus.knowledge || '先把理由写清')}</div>
      <h3>${esc(a.label)}</h3><p class="rpg-draft-prompt">${md(a.prompt || '')}</p>
      <div class="rpg-reasoning"><div><span>它依赖的前提</span><p>${md(d.assumption || '')}</p></div>
      <div><span>确认前要核对</span><p>${md(d.verify || '')}</p></div></div>
      <p class="rpg-draft-note">这里还没有标准答案。你是在决定：是否愿意带着这两个条件承担后果。</p>
      <div class="rpg-draft-actions"><button id="rpg-redraft">换个方案</button><button id="rpg-confirm">确认这个选择</button></div></section>`;
  }
  function dialogueButton(s) {
    if ((!STORY.interrogation && !STORY.rpg.dialogue) || s.dialogue === false) return '';
    const who = STORY.rpg.dialogue || (STORY.cast && STORY.cast[0]);
    return `<button class="rpg-dialogue" id="rpg-dialogue">${ic('me')} 向${esc(who?.name || '当事人')}追问
      <small>原话带出处；自由回答会标明为受材料约束的 AI 推演</small></button>`;
  }
  function openRpgDialogue() {
    if (STORY.interrogation) return Court.open(STORY, drawRpg);
    const d = STORY.rpg.dialogue; if (!d) return;
    ST.dialogueHistory = ST.dialogueHistory || [];
    const renderTalk = () => {
      sheet(`<div class="term-sheet"><div class="eyebrow">受史料约束的人物推演</div><h3>${esc(d.name)}</h3>
        <p class="tip">${esc(d.notice || '以下回答是 AI 根据本故事列出的当年材料进行的人物推演，不是本人原话。材料没有写的内容，人物应明确说不知道。')}</p>
        <div class="rpg-talk-log">${ST.dialogueHistory.map(x => `<div><b>${x.who === 'you' ? '你' : esc(d.name)}</b><p>${esc(x.text)}</p></div>`).join('')}</div>
        <div class="qchips">${(d.prompts || []).map((x, i) => `<button data-talk-prompt="${i}">${esc(x.q)}</button>`).join('')}</div>
        <div class="askin"><input id="rpg-talk-in" placeholder="继续追问……" autocomplete="off"><button id="rpg-talk-go">问</button></div></div>`, true);
      const box = document.getElementById('sheet');
      box.querySelectorAll('[data-talk-prompt]').forEach(b => b.onclick = () => askRpgDialogue((d.prompts[+b.dataset.talkPrompt] || {}).q, renderTalk));
      const input = document.getElementById('rpg-talk-in'), go = document.getElementById('rpg-talk-go');
      go.onclick = () => input.value.trim() && askRpgDialogue(input.value.trim(), renderTalk);
      input.onkeydown = e => { if (e.key === 'Enter' && input.value.trim()) askRpgDialogue(input.value.trim(), renderTalk); };
    };
    renderTalk();
  }
  function askRpgDialogue(question, redraw) {
    const d = STORY.rpg.dialogue, exact = (d.prompts || []).find(x => x.q === question);
    const rerender = redraw;
    ST.dialogueHistory.push({ who: 'you', text: question });
    const fallback = () => { ST.dialogueHistory.push({ who: 'persona', text: exact?.a || d.no_record || '这份材料没有写到这个问题。' }); rerender(); };
    if (typeof BACKEND === 'undefined' || !BACKEND) return fallback();
    const material = (d.material || []).join('\n');
    const history = ST.dialogueHistory.slice(0, -1).map(x => ({ role: x.who === 'you' ? 'user' : 'assistant', content: x.text }));
    fetch(BACKEND + '/api/v1/discuss', { method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ device:S.device, case_id:STORY.case_id, persona:{name:d.name,role:d.role}, era:STORY.era, material, history, question })
    }).then(x => x.json()).then(x => { ST.dialogueHistory.push({ who:'persona', text:x.text || exact?.a || d.no_record || '这份材料没有写到这个问题。' }); rerender(); }).catch(fallback);
  }
  function drawRpg() {
    const r = STORY.rpg;
    if (!ST.role) return drawRpgRoles();
    const s = rpgScene();
    if (!s) return drawRpgFinish();
    const available = rpgActions(s), action = available.find(a => a.id === ST.rpgAction), draft = available.find(a => a.id === ST.rpgDraft), final = s.final === true;
    const actions = action || draft ? '' : available.map(a => `<button class="rpg-action" data-rpg-action="${esc(a.id)}">
      <span class="rpg-action-kind">${esc(a.kind || '行动')}</span><b>${esc(a.label)}</b><small>${esc(a.prompt || '')}</small></button>`).join('');
    const conf = final && action ? `<div class="rpg-confidence"><span>你对这个判断有多大把握？</span><div class="seg2">${CONF.map(c => `<button data-rpg-conf="${c.v}" class="${ST.conf === c.v ? 'on' : ''}">${c.t}</button>`).join('')}</div></div>` : '';
    const nextDisabled = final ? !action || ST.conf == null : !action;
    const sceneIndex = (r.scenes || []).findIndex(x => x.id === s.id);
    const phase = s.eyebrow || (sceneIndex === 0 ? '故事开始' : final ? '故事高潮' : '故事发展');
    const lines = sceneLines(s);
    bodyEl.innerHTML = `<header class="rpg-scene-head"><div class="eyebrow">${esc(phase)}</div><div class="rpg-scene-meta"><span>${esc(s.place || '')}</span><span>${esc(s.time || '')}</span></div><h2>${esc(s.title)}</h2></header>
      ${continuityHTML()}${roleBrief()}${briefingHTML(s.briefings)}${rpgEvidenceV2(s.evidence)}
      ${(Array.isArray(lines) ? lines : [lines]).map(x => `<p class="ln">${md(x)}</p>`).join('')}${sceneIndex === 0 ? timelineHTML(r.timeline) : termsHTML(s.terms || [])}
      ${dialogueButton(s)}${action ? resultHTML(action) : draft ? deliberationHTML(s, draft) : `${decisionFrame(s)}<div class="rpg-actions">${actions}</div>`}`;
    const nextScene = action && (r.scenes || []).find(x => x.id === action.next);
    const nextLabel = final ? '翻开历史记录' : (nextScene?.final ? '进入关键时刻' : '让时间继续');
    footEl.innerHTML = action ? `${conf}<button class="sty-cta" id="rpg-next" ${nextDisabled ? 'disabled' : ''}>${nextLabel}</button>` : '';
    dotsEl.innerHTML = (r.scenes || []).map((x, i) => `<i class="${i < sceneIndex ? 'done' : x.id === s.id ? 'on' : ''}"></i>`).join('');
    bindRpg(s);
  }
  function drawRpgRoles() {
    const r = STORY.rpg;
    bodyEl.innerHTML = `<header class="rpg-role-head"><div class="eyebrow">进入真实事件</div><h2>${esc(STORY.title)}</h2><p>${md(STORY.hook || r.premise || '')}</p></header>
      <div class="rpg-role-list">${(r.roles || []).map(x => `<button class="rpg-role-choice" data-rpg-role="${esc(x.id)}"><span>扮演</span><b>${esc(x.title)}</b><p>${esc(x.brief || x.goal || '')}</p><small>${esc(x.win_condition || x.pressure || '')}</small></button>`).join('')}</div>
      <p class="rpg-truth-note">历史结果不会因你改变；你改变的是进入事件的席位、能先看到的材料，以及必须承担的决策责任。</p>`;
    footEl.innerHTML = '';
    dotsEl.innerHTML = `<i class="on"></i>${(r.scenes || []).map(() => '<i></i>').join('')}`;
    bodyEl.querySelectorAll('[data-rpg-role]').forEach(x => x.onclick = () => {
      ST.role = x.dataset.rpgRole; ST.sceneId = r.initial_scene; ST.rpgAction = null; ST.rpgDraft = null; ST.rpgPath = null; ST.rpgHistory = [];
      track('story_role', { case: STORY.case_id, role: ST.role }); draw(); bodyEl.scrollTop = 0;
    });
  }
  function bindRpg(s) {
    bindFacts();
    bodyEl.querySelectorAll('[data-term]').forEach(x => x.onclick = () => {
      const g = (STORY.rpg.glossary || []).find(y => y.id === x.dataset.term);
      if (g) sheet(`<div class="term-sheet"><div class="eyebrow">说人话</div><h3>${esc(g.term)}</h3><p>${md(g.plain)}</p>${g.example ? `<p class="tip">放进这次事件：${md(g.example)}</p>` : ''}</div>`);
    });
    const talk = document.getElementById('rpg-dialogue');
    if (talk) talk.onclick = openRpgDialogue;
    bodyEl.querySelectorAll('[data-rpg-action]').forEach(x => x.onclick = () => {
      ST.rpgDraft = x.dataset.rpgAction; track('story_deliberation', { case: STORY.case_id, scene: s.id, action: ST.rpgDraft, role: ST.role }); draw(); scrollRpgTo('.rpg-deliberation');
    });
    const redraft = document.getElementById('rpg-redraft');
    if (redraft) redraft.onclick = () => { ST.rpgDraft = null; draw(); scrollRpgTo('.rpg-actions'); };
    const confirm = document.getElementById('rpg-confirm');
    if (confirm) confirm.onclick = () => {
      ST.rpgAction = ST.rpgDraft; ST.rpgDraft = null;
      const a = rpgActions(s).find(y => y.id === ST.rpgAction);
      if (s.final && a && ['a', 'b', 'c'].includes(a.id)) ST.pick = a.id;
      track('story_action', { case: STORY.case_id, scene: s.id, action: ST.rpgAction, role: ST.role }); draw(); scrollRpgTo('.rpg-audit');
    };
    footEl.querySelectorAll('[data-rpg-conf]').forEach(x => x.onclick = () => { ST.conf = +x.dataset.rpgConf; draw(); });
    const next = document.getElementById('rpg-next');
    if (next) next.onclick = () => {
      const a = rpgActions(s).find(y => y.id === ST.rpgAction); if (!a) return;
      const d = deliberation(s, a);
      ST.rpgHistory.push({ scene: s.id, action: a.id, label: a.label, assumption: d.assumption, verify: d.verify });
      if (s.final || a.next === '__legacy_reveal') {
        S.storyLearning = S.storyLearning || {};
        S.storyLearning[STORY.case_id] = { goal: STORY.rpg.learning_goal || STORY.learning_goal, skills: STORY.rpg.learning_skills || STORY.skills || [], role: ST.role, path: ST.rpgHistory, at: Date.now() };
        save(); track('story_learning_checkpoint', { case: STORY.case_id, skills: (STORY.rpg.learning_skills || STORY.skills || []).length });
        ST.mode = 'legacy'; ST.i = STORY.beats.findIndex(x => x.kind === 'reveal'); if (ST.i < 0) ST.i = 0;
      } else { ST.rpgPath = ST.rpgAction; ST.sceneId = a.next; ST.rpgAction = null; ST.rpgDraft = null; }
      draw(); bodyEl.scrollTop = 0;
    };
  }

  window.render_game_to_text = function () {
    if (!ST) return JSON.stringify({ screen: 'story-list' });
    const s = ST.mode === 'rpg' ? rpgScene() : STORY.beats[ST.i];
    const r = activeRole(), focus = r.focus || {};
    return JSON.stringify({ case_id: STORY.case_id, mode: ST.mode, role: ST.role,
      scene: s && s.id, title: s && s.title, draft: ST.rpgDraft, action: ST.rpgAction,
      focus: focus.knowledge ? { knowledge:focus.knowledge, watch:focus.watch, read:focus.read } : null,
      carry: ST.rpgHistory && ST.rpgHistory.length ? ST.rpgHistory[ST.rpgHistory.length - 1] : null,
      options: ST.mode === 'rpg' && s ? rpgActions(s).map(a => ({ id: a.id, label: a.label })) : [] });
  };
  window.advanceTime = function () {};

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

  /* 历史时间线只陈列当时可知信息；来源与行号跟在事件后面。 */
  function ctxStrip(items) {
    if (!items || !items.length) return '';
    return `<div class="ctx"><div class="ctx-h">当时</div>${items.map(c =>
      `<div class="ctx-i"><span class="ctx-d">${c.date}</span><span class="ctx-t">${md(c.t)}</span>${c.src ? `<span class="ctx-s">${c.src}${c.line ? ' · ' + c.line : ''}</span>` : ''}</div>`).join('')}</div>`;
  }

  /* S0 冷开场 */
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

  /* 旧故事兼容拍：展示决策后的直接后果。 */
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

  /* S1/S2 证据页 */
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

  /* S3 决策与信心记录 */
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

  /* S4 历史翻牌 */
  function bReveal(b) {
    const q = b.quote || b.record_summary;
    const sourceCard = b.quote ? docQuote(q)
      : `<div class="doc"><div class="dh"><span>${ic('doc')} 史实摘要 · ${q.src}</span><span class="ln">${q.line}</span></div><div class="dt">${q.text}</div></div>`;
    const factButton = b.quote && b.quote.fact ? `<div class="qchips"><button data-f="${b.quote.fact}">${ic('link')} 查看原档</button></div>` : '';
    return {
      body: `<div class="eyebrow">${beatPhase(b)}</div><h2>${b.title}</h2>
        ${sourceCard}
        ${b.lines.map(l => `<p class="ln">${md(l)}</p>`).join('')}
        ${factButton}
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">回看我的决定</button>`,
      bind() { bindFacts(); }
    };
  }

  /* S5 对照复盘与方法提炼 */
  function bContrast(b) {
    const dec = STORY.beats.find(x => x.kind === 'decision');
    const mine = (dec.options || []).find(o => o.id === ST.pick) || { t: '未选择', kind: '未记录' };
    const confT = (CONF.find(c => c.v === ST.conf) || {}).t || '未记录';
    if (!ST.logged) {
      ST.logged = true;
      track('story_decision', { case: STORY.case_id, pick: ST.pick, verdict: mine.verdict, conf: ST.conf });
      const cs = (window.__court && window.__court.story === STORY) ? window.__court.stats : { pressed: 0, broke: 0, noRecord: 0 };
      ST.stats = cs;
      ST.prior = JSON.parse(JSON.stringify(profile()));
      // 同一故事只更新一次判断画像；重玩仍保留当次复盘状态。
      S.storySeen = S.storySeen || {};
      if (!S.storySeen[STORY.case_id]) {
        S.storySeen[STORY.case_id] = true;
        updateProfile(STORY.case_id, mine, ST.conf, cs);
      }
      // 此处先存选择，完成标记由 finish() 统一写入。
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

  /* S6 方法抽象 */
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

  /* S7 迁移题：保留旧故事的兼容渲染。 */
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
    // 完成故事后，把对应易混概念加入复习队列。
    if (typeof ensurePair === 'function') {
      const n = byId[node];
      let pairs = (n && n.x_pairs || []).filter(p => p.id);
      if (!pairs.length) {
        // 若当前节点没有直接配对题，向下一层节点寻找可迁移的复习题。
        const down = (SITE.edges || []).filter(e => e.from === node).map(e => byId[e.to]).filter(Boolean);
        pairs = down.flatMap(d => (d.x_pairs || []).filter(p => p.id)).slice(0, 2);
      }
      pairs.forEach(p => ensurePair(p.id));
      if (!pairs.length) console.warn('故事没有可加入复习队列的配对题', STORY.case_id, node);
      save();
    }
    // RPG v2 在历史对照页后即可完成；旧方法页仍由兼容播放器处理。
    S.story = S.story || {};
    S.story[STORY.case_id] = Object.assign(
      { at: Date.now() }, (S.storyPick || {})[STORY.case_id], { done: 1 });
    save();
    track('story_finish', { case: STORY.case_id });
    document.getElementById('sty-toprac').onclick = () => {
      close();
      // 回到与本故事关联的知识节点。
      if (typeof openNode === 'function') openNode(node);
    };
    document.getElementById('sty-back').onclick = close;
  }

  /* 人物追问由 court.js 统一负责；本文件只保留故事进入点与回调。 */
})();
