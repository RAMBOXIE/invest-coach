/* 故事播放器 · 幕驱动。
   契约：所有数字与引文来自 STORY 的冻结骨架（case.json），运行时不生成任何事实。
   判分仍是规则引擎；教练画外音用预置文案，LLM 接入后只改措辞不改结论。 */
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
    // 抽屉和遮罩要跟着一起收：z-index 79/80 高于主界面，留着就是一块卡住的浮层。
    // 先关抽屉再清回调——反过来的话 closeSheet 会触发那个悬空的 onClose。
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
        <span class="rd-nm">${nm}读你的这一次判断</span></div>
      <p class="rd-h">${md(r.head)}</p><p class="rd-b">${md(r.body)}</p>
      ${r.extra.map(x => `<p class="rd-x">${md(x)}</p>`).join('')}</div>`;
  }
  function vo(t) {
    const c = (typeof coachName === "function") ? coachName() : "你的教练";
    return t ? `<div class="vo"><span class="who">${c}</span><span class="txt">${t}</span></div>` : '';
  }

  function draw() {
    if (!ST) return;   // 悬空的跨层回调兜底：幕已关，ST 是 null
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

  /* ===== 金融事件 RPG 引擎 =====
     rpg.scenes 是新故事契约。每个场景由处境、已知材料和行动组成；行动只改变
     玩家接下来面对的压力与信息路径，真实结局仍由冻结的 reveal beat 接管。 */
  function rpgScene() {
    if (ST.sceneId === '__rpg_pressure__') {
      const p = ST.rpgPressure || {};
      return { id: '__rpg_pressure__', eyebrow: '你的行动已经传出去', place: p.place || '事件现场', time: p.time || '几分钟后',
        title: p.title || '房间里的空气变了', lines: p.lines || [], evidence: p.evidence || [],
        actions: [{ id: 'continue', kind: '承受后果', label: '继续面对下一步', prompt: '带着这个压力回到证据桌前。',
          consequence: p.consequence || '', result_title: p.result_title || '后果已经发生', narration: p.narration || '', next: ST.rpgReturn }] };
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
    return role ? `<div class="rpg-active-role"><span>你扮演</span><b>${esc(role.title)}</b><small>${esc(role.goal)}</small></div>` : '';
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
    const conf = final && action ? `<div class="eyebrow rpg-conf-label">你对这个决定有多大把握？</div>
      <div class="seg2">${CONF.map(c => `<button data-rpg-conf="${c.v}" class="${ST.conf === c.v ? 'on' : ''}">${c.t}</button>`).join('')}</div>` : '';
    const nextDisabled = final ? !action || ST.conf == null : !action;
    bodyEl.innerHTML = `<div class="eyebrow">${esc(s.eyebrow || '事件现场')}</div>
      <div class="rpg-scene-meta"><span>${esc(s.place || '')}</span><span>${esc(s.time || '')}</span></div>
      <h2>${esc(s.title)}</h2>${rpgRoleCard()}
      ${(s.path_lines?.[ST.rpgPath] || s.role_lines?.[ST.role] || s.lines || []).map(x => `<p class="ln">${md(x)}</p>`).join('')}
      ${rpgEvidence(s.evidence)}
      ${action ? `<div class="rpg-result"><div class="rpg-result-title">${esc(action.result_title || '你的行动已经产生后果')}</div>
        <p class="ln">${md(action.consequence || '')}</p>
        <p class="rpg-pressure" id="rpg-voice-${STORY.case_id}"><b>画外音</b>${md(voice)}</p></div>` : `<div class="rpg-actions">${actions}</div>`}`;
    footEl.innerHTML = action ? `${final ? conf : ''}<button class="sty-cta" id="rpg-next" ${nextDisabled ? 'disabled' : ''}>${final ? '进入真实档案' : '继续'}</button>` : '';
    dotsEl.innerHTML = (r.scenes || []).map(x => `<i class="${x.id === s.id ? 'on' : ''}"></i>`).join('');
    if (action) narrateChoice(action, 'rpg-voice-' + STORY.case_id);
    bindRpg(s);
  }
  function drawRpgRoles() {
    const r = STORY.rpg;
    bodyEl.innerHTML = `<div class="eyebrow">进入事件</div><h2>${esc(r.title || '先决定你是谁')}</h2>
      <p class="ln">${md(r.premise || '')}</p><div class="rpg-role-list">${(r.roles || []).map(x =>
        `<button class="rpg-role-choice" data-rpg-role="${esc(x.id)}"><b>${esc(x.title)}</b><span>${esc(x.goal)}</span><small>${esc(x.pressure || '')}</small></button>`).join('')}</div>`;
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
        ST.mode = 'legacy'; ST.i = STORY.beats.findIndex(x => x.kind === 'reveal');
        if (ST.i < 0) ST.i = 0;
      } else {
        ST.rpgPath = ST.rpgAction; ST.rpgReturn = a.next; ST.rpgAction = 'continue'; ST.rpgVoice = null;
        ST.rpgPressure = { place: s.place, time: s.time, title: a.result_title || '房间里的空气变了',
          lines: [`${a.label}已经改变了下一步的压力。现在没有人能回到选择之前。`],
          consequence: a.consequence, result_title: a.result_title, narration: a.narration };
        ST.sceneId = '__rpg_pressure__';
      }
      draw();
    };
  }
  function drawRpgFinish() { ST.mode = 'legacy'; draw(); }

  function roleCard() {
    const r = STORY.rpg;
    if (!r || !r.role) return '';
    return `<div class="rpg-role"><div class="rpg-kicker">你现在不是旁观者</div>
      <div class="rpg-title">${esc(r.role.title)}</div>
      <div class="rpg-goal"><b>任务</b>${esc(r.role.goal)}</div>
      <div class="rpg-goal"><b>限制</b>${esc(r.role.constraint)}</div></div>`;
  }

  /* 「当时」时间线：owner 要求每个真实案例都带时间与当年背景，让故事有临场感。
     每条都是当年可知的事，带日期与出处（原档行号或归档文件页码）；结局不在这里。 */
  function ctxStrip(items) {
    if (!items || !items.length) return '';
    return `<div class="ctx"><div class="ctx-h">当时</div>${items.map(c =>
      `<div class="ctx-i"><span class="ctx-d">${c.date}</span><span class="ctx-t">${md(c.t)}</span>${c.src ? `<span class="ctx-s">${c.src}${c.line ? ' · ' + c.line : ''}</span>` : ''}</div>`).join('')}</div>`;
  }

  /* S0 冷开场 */
  function bCold(b) {
    return {
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
        ${roleCard()}
        ${ctxStrip(b.context)}
        ${b.lines.map((l, i) => `<p class="ln${i === b.lines.length - 1 ? '' : ' dim'}">${md(l)}</p>`).join('')}
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">翻开年报</button>`
    };
  }

  /* 选择后的后果：玩家没有改写历史，但改变了自己接下来面对的压力和信息路径。 */
  function bConsequence(b) {
    const path = (b.paths || {})[ST.pick] || {};
    const voiceId = 'rpg-voice-' + STORY.case_id;
    return {
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${path.title || b.title}</h2>
        <div class="rpg-consequence"><p class="ln">${md(path.body || '')}</p>
          <p class="rpg-pressure"><b>你承担的压力</b>${md(path.pressure || '')}</p></div>
        <div id="${voiceId}">${vo(path.narration || '')}</div>`,
      foot: `<button class="sty-cta" id="sty-next">继续翻查原档</button>`,
      bind() { narrateChoice(path, voiceId); }
    };
  }

  function narrateChoice(path, targetId) {
    const r = STORY.rpg, target = document.getElementById(targetId);
    if (!r || !r.narrator || !target || typeof BACKEND === 'undefined' || !BACKEND) return;
    const ctl = new AbortController();
    const tm = setTimeout(() => ctl.abort(), 12000);
    fetch(BACKEND + '/api/v1/story-narrate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: ctl.signal,
      body: JSON.stringify({ device: S.device, case_id: STORY.case_id,
        narrator: r.narrator, choice: path.title || path.label, pressure: path.pressure || path.consequence,
        seed: path.narration, question: '请沿着玩家刚才的选择，用画外音解释他现在承担的判断压力。' })
    }).then(x => x.json()).then(d => {
      clearTimeout(tm);
      if (d && d.text && target) target.innerHTML = vo(esc(d.text));
    }).catch(() => clearTimeout(tm));
  }

  /* S1/S2 证据幕 */
  function bEvid(b) {
    return {
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
        ${evPanel(b.panel)}${derived(b.derived)}
        <div class="qchips">${(b.panel.rows || []).filter(r => r.fact).map(r =>
          `<button data-f="${r.fact}">${ic('link')} ${r.k}</button>`).join('')}</div>
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">继续</button>`,
      bind() { bindFacts(); }
    };
  }
  function bindFacts() {
    bodyEl.querySelectorAll('[data-f]').forEach(x => x.onclick = () => {
      const f = F(x.dataset.f);
      if (!f) return;
      sheet(`<h3 style="margin:0 0 8px;font-size:17px">${ic('link')} 溯源</h3>
        <p style="font-size:17px;line-height:1.8"><b>${f.item}</b><br>${f.value}</p>
        <p class="tip">口径：${f.basis || '—'}<br>档案：${f.accession} · ${f.line}<br>公司：${f.company}</p>
        <p class="tip">这个数字不是我们写的，是从原始申报文件里取的。行号在上面，任何人都能复核。</p>`);
    });
  }

  /* S3 决策 —— 素屏，可先问人物 */
  function bDec(b) {
    const picked = ST.pick != null, conf = ST.conf != null;
    return {
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
        <p class="ln">${b.prompt}</p>
        ${b.ask_enabled && STORY.interrogation ? (() => {
          const c = window.__court && window.__court.story === STORY ? window.__court.stats : null;
          const acted = c ? (c.pressed || 0) + (c.broke || 0) : 0;
          const label = !acted
            ? `先追问 ${STORY.cast[0].name}（${STORY.interrogation.testimony.length} 条陈述）`
            : `继续追问 ${STORY.cast[0].name}（已追问 ${c.pressed} 次${c.broke ? ` · 找出矛盾 ${c.broke} 处` : ''}）`;
          return `<button class="askbtn${acted ? ' done' : ''}" id="sty-ask">${ic('scale')} ${label}</button>`;
        })() : ''}
        ${b.options.map(o => `<button class="choice${ST.pick === o.id ? ' on' : ''}" data-p="${o.id}">
            <span class="kd">${o.kind}</span>${o.t}</button>`).join('')}
        ${picked ? `<div class="eyebrow" style="margin-top:20px">你有多大把握？</div>
          <div class="seg2">${CONF.map(c => `<button data-cf="${c.v}" class="${ST.conf === c.v ? 'on' : ''}">${c.t}</button>`).join('')}</div>` : ''}`,
      foot: `<button class="sty-cta" id="sty-next" ${picked && conf ? '' : 'disabled'}>就这么定了</button>`,
      bind() {
        bodyEl.querySelectorAll('[data-p]').forEach(x => x.onclick = () => { ST.pick = x.dataset.p; draw(); });
        bodyEl.querySelectorAll('[data-cf]').forEach(x => x.onclick = () => { ST.conf = +x.dataset.cf; draw(); });
        const a = document.getElementById('sty-ask');
        if (a) a.onclick = () => Court.open(STORY, () => draw());
      }
    };
  }

  /* S4 揭晓 */
  function bReveal(b) {
    return {
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
        ${docQuote(b.quote)}
        ${b.lines.map(l => `<p class="ln">${md(l)}</p>`).join('')}
        <div class="qchips"><button data-f="${b.quote.fact}">${ic('link')} 核这个数字</button></div>
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">那我的判断呢？</button>`,
      bind() { bindFacts(); }
    };
  }

  /* S5 三列对照 + knowhow */
  function bContrast(b) {
    const dec = STORY.beats.find(x => x.kind === 'decision');
    const mine = (dec.options || []).find(o => o.id === ST.pick) || { t: '（未作答）', kind: '—' };
    const confT = (CONF.find(c => c.v === ST.conf) || {}).t || '—';
    if (!ST.logged) {
      ST.logged = true;
      track('story_decision', { case: STORY.case_id, pick: ST.pick, verdict: mine.verdict, conf: ST.conf });
      const cs = (window.__court && window.__court.story === STORY) ? window.__court.stats : { pressed: 0, broke: 0, noRecord: 0 };
      ST.stats = cs;
      ST.prior = JSON.parse(JSON.stringify(profile()));   // 快照：解读用「这一次之前」的画像
      // 画像只在这一幕**第一次**被读到 contrast 时更新一次。守卫必须落在 S 上：
      // ST 每次 openStory 都新建，挂在 ST 上的话「读过的幕」里重读一遍就二次计入，
      // 画像里的次数会大于幕的总数。
      S.storySeen = S.storySeen || {};
      if (!S.storySeen[STORY.case_id]) {
        S.storySeen[STORY.case_id] = true;
        updateProfile(STORY.case_id, mine, ST.conf, cs);
      }
      // 决策本身记下来（成绩单回放要用），但**不代表这一幕读完了**——
      // 「读完」由 finish() 写 S.story[cid]，见那里的说明。
      S.storyPick = S.storyPick || {};
      S.storyPick[STORY.case_id] = { pick: ST.pick, verdict: mine.verdict, conf: ST.conf, at: Date.now() };
      save();
    }
    return {
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
        <div class="trio">
          <div class="c you"><div class="lbl">${b.columns.you}</div>
            <div class="hd2">${mine.t}</div>
            <div class="dt2">你当时的把握：${confT}</div></div>
          <div class="c"><div class="lbl">${b.columns.them}</div>
            <div class="hd2">${b.them.t}</div><div class="dt2">${b.them.detail}</div></div>
          <div class="c canon"><div class="lbl">${b.columns.canon}</div>
            <div class="hd2">${b.canon.t}</div><div class="dt2">${b.canon.detail}<br><span style="opacity:.75">${b.canon.src}</span></div></div>
        </div>
        ${readingHTML(mine)}
        <div class="kn"><h3>你该带走的</h3><ul>${b.knowhow.map(k => `<li>${md(k)}</li>`).join('')}</ul></div>
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">看这条判断依据</button>`
    };
  }

  /* S6 抽象渐隐 */
  function bAbstract(b) {
    return {
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
        <div class="fade3">
          <div class="f"><div class="t">故事版</div><div class="b">${b.story_form}</div></div>
          <div class="f"><div class="t">判断依据</div><div class="b">${b.rule}</div></div>
          <div class="f"><div class="t">公式版</div><div class="b">${b.formula}</div></div>
          <div class="f tag"><div class="t">标签（复习用这个找你）</div><div class="b">${b.label}</div></div>
        </div>
        <p class="ln dim">边界：${b.boundary}</p>
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">最后一屏</button>`
    };
  }

  /* S7 同构第二案例（抗迁移失败的最高杠杆） */
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
        ? `<button class="sty-cta" id="sty-done">读完这个案例</button>`
        : `<button class="sty-cta" disabled>先回答</button>`,
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
      <h2>这个案例读完了</h2>
      <p class="ln">你刚才做的判断、以及这个案例里那份原档，会跟着「${STORY.beats.find(x => x.kind === 'abstract').label}」这个标签进入你的复习队列。</p>
      <p class="ln dim">下次它来找你的时候，会换一家公司——因为判据要能离开这个故事，才算是你的。</p>
      ${vo('故事负责让你记住。练习负责让你带走。两样都要。')}</div>`;
    footEl.innerHTML = `<button class="sty-cta" id="sty-toprac">去练这条判据</button>
      <div style="height:8px"></div>
      <button class="sty-cta ghost" id="sty-back">回到今日</button>`;
    // 故事读完 → 该判据进入复训队列（按标签，不按故事）
    if (typeof ensurePair === 'function') {
      const n = byId[node];
      let pairs = (n && n.x_pairs || []).filter(p => p.id);
      if (!pairs.length) {
        // 元能力节点（base-rate / falsification）自身没有混淆对：
        // 退而挂到它 cross 边指向的下游节点的混淆对上——判据仍按标签复训，不按故事
        const down = (SITE.edges || []).filter(e => e.from === node).map(e => byId[e.to]).filter(Boolean);
        pairs = down.flatMap(d => (d.x_pairs || []).filter(p => p.id)).slice(0, 2);
      }
      pairs.forEach(p => ensurePair(p.id));
      if (!pairs.length) console.warn('故事', STORY.case_id, '的判断依据节点', node, '无可挂的易混题');
      save();
    }
    // 「读完」的唯一定义点：和复训挂载同一时刻。contrast 拍写这个字段的话，
    // 用户在 abstract / twin 两拍之前退出，今日页就再也不会把这一幕排回来，
    // 而这一幕的判据一个都没进复训队列——幕的整个价值主张正是「判据要能离开这个故事」。
    S.story = S.story || {};
    S.story[STORY.case_id] = Object.assign(
      { at: Date.now() }, (S.storyPick || {})[STORY.case_id], { done: 1 });
    save();
    track('story_finish', { case: STORY.case_id });
    document.getElementById('sty-toprac').onclick = () => {
      close();
      // 「去练这条判据」曾直接 openNode，绕过图谱的硬边锁——第一幕读完就能被丢进
      // 未解锁的深层节点，那里的材料建立在还没学的前置上。锁由 openNode 自己守。
      if (typeof openNode === 'function') openNode(node);
    };
    document.getElementById('sty-back').onclick = close;
  }

  /* ===== 问人物：答案只能是原档逐字 ===== */
  /* 「问人物」子系统（openAsk / drawAsk / turnHTML / ask / resolveQA / matchQA）已删除。
     它没有任何调用入口，case.json 的 ask 语料从不上屏；它想做的事已经由质问台
     （court.js，逆转裁判式的证词—追问—出证）完整实现，两者共用同一个后端语义路由端点。
     留着一整块死代码，下一个人会以为它还在跑。删除日期 2026-08-26。 */
})();
