/* 故事播放器 · 幕驱动。
   契约：所有数字与引文来自 STORY 的冻结骨架（case.json），运行时不生成任何事实。
   判分仍是规则引擎；教练画外音用预置文案，LLM 接入后只改措辞不改结论。 */
(function () {
  'use strict';
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
    ST = { i: 0, pick: null, conf: null, twinOk: null, asked: [], seen: new Set() };
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
  const md = s => String(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
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
    const b = STORY.beats[ST.i];
    ST.seen.add(b.id);
    dots();
    const R = ({
      cold_open: bCold, evidence: bEvid, decision: bDec,
      reveal: bReveal, contrast: bContrast, abstract: bAbstract, twin: bTwin
    })[b.kind](b);
    bodyEl.innerHTML = R.body;
    footEl.innerHTML = R.foot;
    bodyEl.scrollTop = 0;
    R.bind && R.bind();
    const n = document.getElementById('sty-next');
    if (n) n.onclick = () => { ST.i++; track('story_beat', { case: STORY.case_id, beat: b.id }); draw(); };
  }

  /* S0 冷开场 */
  function bCold(b) {
    return {
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
        ${b.lines.map((l, i) => `<p class="ln${i === b.lines.length - 1 ? '' : ' dim'}">${l}</p>`).join('')}
        ${vo(b.narration)}`,
      foot: `<button class="sty-cta" id="sty-next">翻开年报</button>`
    };
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
            ? `先质问 ${STORY.cast[0].name}（${STORY.interrogation.testimony.length} 条证词）`
            : `继续质问 ${STORY.cast[0].name}（已追问 ${c.pressed} 次${c.broke ? ` · 戳穿 ${c.broke} 处` : ''}）`;
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
        ${b.lines.map(l => `<p class="ln">${l}</p>`).join('')}
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
      foot: `<button class="sty-cta" id="sty-next">把判据拿出来</button>`
    };
  }

  /* S6 抽象渐隐 */
  function bAbstract(b) {
    return {
      body: `<div class="eyebrow">${b.eyebrow}</div><h2>${b.title}</h2>
        <div class="fade3">
          <div class="f"><div class="t">故事版</div><div class="b">${b.story_form}</div></div>
          <div class="f"><div class="t">判据</div><div class="b">${b.rule}</div></div>
          <div class="f"><div class="t">公式版</div><div class="b">${b.formula}</div></div>
          <div class="f tag"><div class="t">标签（复训用这个找你）</div><div class="b">${b.label}</div></div>
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
        ? `<button class="sty-cta" id="sty-done">读完这一幕</button>`
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
      <h2>这一幕读完了</h2>
      <p class="ln">你刚才做的判断、以及那段藏在第 18 页的话，会跟着「${STORY.beats.find(x => x.kind === 'abstract').label}」这个标签进入你的复训队列。</p>
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
      if (!pairs.length) console.warn('故事', STORY.case_id, '的判据节点', node, '无可挂的混淆对');
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
