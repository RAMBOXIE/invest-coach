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
  function rpgBeat(id) { return STORY.beats.find(b => b.id === id); }
  function rpgActions(s) {
    return (s.actions || []).filter(a => !a.roles || a.roles.includes(ST.role));
  }
  function rpgEvidence(ids) {
    return (ids || []).map(rpgBeat).filter(Boolean).map(b => {
      if (b.panel && b.panel.kind === 'list') {
        const rows = (b.panel.rows || []).map(r => `<div class="rpg-role"><div class="rpg-kicker">${esc(r.k || '')}</div><div class="rpg-title">${esc(r.v || '')}</div></div>`).join('');
        const note = typeof b.derived === 'string' ? `<p class="rpg-pressure">${md(b.derived)}</p>` : derived(b.derived);
        return `<div class="rpg-evidence-list">${b.panel.title ? `<div class="eyebrow">${esc(b.panel.title)}</div>` : ''}${rows}</div>${note}`;
      }
      if (b.panel) return `${evPanel(b.panel)}${derived(b.derived)}`;
      if (b.quote) return docQuote(b.quote);
      return '';
    }).join('');
  }
  function rpgRoleCard() {
    const role = (STORY.rpg.roles || []).find(r => r.id === ST.role);
    return role ? `<div class="rpg-active-role"><span>当前身份</span><b>${esc(role.title)}</b><small>${esc(role.goal)}</small></div>` : '';
  }
  function drawRpg() {
    const r = STORY.rpg;
    if (!ST.role) return drawRpgRoles();
    const s = rpgScene();
    if (!s) return drawRpgFinish();
    const available = rpgActions(s);
    const action = available.find(a => a.id === ST.rpgAction);
    const final = s.final === true;
    const voice = action ? (ST.rpgVoice || action.narration || '') : '';
    const actions = action ? '' : available.map(a =>
      `<button class="rpg-action" data-rpg-action="${esc(a.id)}"><span class="rpg-action-kind">${esc(a.kind || '行动')}</span><b>${esc(a.label)}</b><small>${esc(a.prompt || '')}</small></button>`).join('');
    const conf = final && action ? `<div class="eyebrow rpg-conf-label">你对这个判断有多大把握？</div>
      <div class="seg2">${CONF.map(c => `<button data-rpg-conf="${c.v}" class="${ST.conf === c.v ? 'on' : ''}">${c.t}</button>`).join('')}</div>` : '';
    const nextDisabled = final ? !action || ST.conf == null : !action;
    bodyEl.innerHTML = `<div class="eyebrow">${esc(s.eyebrow || '现场')}</div>
      <div class="rpg-scene-meta"><span>${esc(s.place || '')}</span><span>${esc(s.time || '')}</span></div>
      <h2>${esc(s.title)}</h2>${rpgRoleCard()}
      ${(s.path_lines?.[ST.rpgPath] || s.role_lines?.[ST.role] || s.lines || []).map(x => `<p class="ln">${md(x)}</p>`).join('')}
      ${rpgEvidence(s.evidence)}
      ${action ? `<div class="rpg-result"><div class="rpg-result-title">${esc(action.result_title || '行动结果')}</div>
        <p class="ln">${md(action.consequence || '')}</p>
        <p class="rpg-pressure" id="rpg-voice-${STORY.case_id}"><b>画外音</b>${md(voice)}</p></div>` : `<div class="rpg-actions">${actions}</div>`}`;
    footEl.innerHTML = action ? `${final ? conf : ''}<button class="sty-cta" id="rpg-next" ${nextDisabled ? 'disabled' : ''}>${final ? '进入原档揭示' : '继续'}</button>` : '';
    dotsEl.innerHTML = (r.scenes || []).map(x => `<i class="${x.id === s.id ? 'on' : ''}"></i>`).join('');
    if (action) narrateChoice(action, 'rpg-voice-' + STORY.case_id);
    bindRpg(s);
  }
  function drawRpgRoles() {
    const r = STORY.rpg;
    bodyEl.innerHTML = `<div class="eyebrow">角色选择</div><h2>${esc(r.title || '选择你的身份')}</h2>
      <p class="ln">${md(r.premise || '')}</p><div class="rpg-role-list">${(r.roles || []).map(x =>
        `<button class="rpg-role-choice" data-rpg-role="${esc(x.id)}"><b>${esc(x.title)}</b><span>${esc(x.goal)}</span><small>${esc(x.pressure || '')}</small></button>`).join('')}</div>`;
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
        ST.rpgPath = ST.rpgAction; ST.rpgReturn = a.next; ST.rpgAction = 'continue'; ST.rpgVoice = null;
        ST.rpgPressure = { place: s.place, time: s.time, title: a.result_title || '选择的后果',
          lines: [`${a.label}之后，房间里的压力改变了。`],
          consequence: a.consequence, result_title: a.result_title, narration: a.narration };
        ST.sceneId = '__rpg_pressure__';
      }
      draw();
    };
  }
  function drawRpgFinish() { ST.mode = 'legacy'; draw(); }

  function learningCard(goal, skills) {
    if (!goal && !(skills || []).length) return '';
    return `<div class="rpg-learning"><div class="rpg-kicker">LEARNING TARGET</div><p>${esc(goal || '')}</p>
      <div class="rpg-skill-list">${(skills || []).map(x => `<span>${esc(x)}</span>`).join('')}</div></div>`;
  }

  function roleCard() {
    const r = STORY.rpg;
    if (!r || !r.role) return '';
    return `<div class="rpg-role"><div class="rpg-kicker">角色约束</div>
      <div class="rpg-title">${esc(r.role.title)}</div>
      <div class="rpg-goal"><b>目标</b>${esc(r.role.goal)}</div>
      <div class="rpg-goal"><b>约束</b>${esc(r.role.constraint)}</div></div>`;
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
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
        ${roleCard()}
        ${ctxStrip(b.context)}
        ${b.lines.map((l, i) => `<p class="ln${i === b.lines.length - 1 ? '' : ' dim'}">${md(l)}</p>`).join('')}
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">继续</button>`
    };
  }

  /* ???????????????????????????????????? */
  function bConsequence(b) {
    const path = (b.paths || {})[ST.pick] || {};
    const voiceId = 'rpg-voice-' + STORY.case_id;
    return {
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${path.title || b.title}</h2>
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
    target.innerHTML = vo('The narrator is connecting your choice to the pressure in this event...');
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
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
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
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
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
    return {
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
        ${docQuote(b.quote)}
        ${b.lines.map(l => `<p class="ln">${md(l)}</p>`).join('')}
        <div class="qchips"><button data-f="${b.quote.fact}">${ic('link')} 查看原档</button></div>
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">进入下一段</button>`,
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
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
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
      foot: `<button class="sty-cta" id="sty-next">继续</button>`
    };
  }

  /* S6 ???? */
  function bAbstract(b) {
    return {
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
        <div class="fade3">
          <div class="f"><div class="t">故事</div><div class="b">${b.story_form}</div></div>
          <div class="f"><div class="t">规则</div><div class="b">${b.rule}</div></div>
          <div class="f"><div class="t">公式</div><div class="b">${b.formula}</div></div>
          <div class="f tag"><div class="t">适用边界</div><div class="b">${b.label}</div></div>
        </div>
        <p class="ln dim">边界：${b.boundary}</p>
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">继续</button>`
    };
  }

  /* S7 ?????????????????? */
  function bTwin(b) {
    const answered = ST.twinOk != null;
    return {
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
        ${evPanel(b.panel)}
        <p class="ln">${b.question}</p>
        ${b.options.map((o, i) => `<button class="choice${ST.twinPick === i ? ' on' : ''}" data-t="${i}" ${answered ? 'disabled' : ''}>${o.t}</button>`).join('')}
        ${answered ? `<div class="kn"><p style="font-size:17px;line-height:1.85;margin:0">${b.fb}</p></div>` : ''}
        ${answered ? vo(b.narration) : ''}`,
      foot: answered
        ? `<button class="sty-cta" id="sty-done">完成案例</button>`
        : `<button class="sty-cta" disabled>先选择一个答案</button>`,
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
