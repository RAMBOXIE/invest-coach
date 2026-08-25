/* 质问系统（逆转裁判式）+ 个人教练画像。
   铁律：人物说的每一句都是 case.json 里的原档逐字；LLM 只做「用户想戳哪条」的语义路由
   与「教练对你这次选择的解读」，永不生成人物台词、数字或公司名。 */
(function () {
  'use strict';

  /* ============ 个人教练：不是扮演者，是了解你的人 ============ */
  const TONES = [
    { id: 'value', k: '多讲数字与出处', d: '每个结论都要能指回原档的哪一行' },
    { id: 'risk', k: '多讲求证与流程', d: '先假设它有问题，把求证链走完' },
    { id: 'behav', k: '多讲我自己的偏差', d: '盯你的把握感和你重复犯的错' }
  ];
  window.TONES = TONES;

  function profile() {
    S.profile = S.profile || { tone: null, n: 0, prudent: 0, risky: 0, hasty: 0,
      over: 0, under: 0, pressed: 0, broke: 0, noRecord: 0, seenCases: [] };
    return S.profile;
  }
  window.profile = profile;

  /* 画像 → 一句针对这个人的话（离线由规则合成；接后端后由 LLM 改写措辞，事实不变） */
  window.profileLine = function () {
    const p = profile();
    if (!p.n) return '我还不了解你。读一幕，我就开始认识你的判断习惯了。';
    const bits = [];
    if (p.risky >= 2 && p.risky > p.prudent) bits.push('你倾向于顺着叙事走——三幕里有 ' + p.risky + ' 次选了跟随');
    if (p.hasty >= 2) bits.push('你有 ' + p.hasty + ' 次在证据还不够时就下了定性结论');
    if (p.prudent >= 2) bits.push('你多数时候会先求证再下结论，这是好习惯');
    if (p.over >= 1) bits.push('有 ' + p.over + ' 次你标了「很有把握」却判错——这是校准要治的病');
    if (p.broke >= 2) bits.push('你已经在质问里戳穿了 ' + p.broke + ' 处说法，说明你会用证据');
    if (p.noRecord >= 1) bits.push('你问出过「档里没有」，这比问出答案更难');
    return bits.length ? bits.join('；') + '。' : '目前看不出稳定的模式——再读一幕。';
  };

  /* 教练对「这一次选择」的解读：离线规则合成，接后端后由 LLM 基于同样的结构化信号改写 */
  window.choiceReading = function (story, opt, conf, stats, prior) {
    const p = prior || profile();
    const confT = conf >= .95 ? '很有把握' : conf >= .75 ? '比较有把握' : '没把握';
    const v = opt.verdict;
    let head, body;
    if (v === 'prudent') {
      head = '你选了求证。';
      body = conf >= .95
        ? '而且标了「很有把握」——注意：<b>对「我要去查」这件事有把握是合理的</b>，但别把它读成「我已经知道答案了」。求证的价值恰恰在于你还不知道。'
        : '把握标在「' + confT + '」，和你手上的证据量是匹配的。这一条比选对更重要：<b>结论强度要配得上材料强度。</b>';
    } else if (v === 'risky') {
      head = '你顺着叙事走了。';
      body = conf >= .95
        ? '而且是「很有把握」。这正是这一幕想给你的那一下——<b>叙事的说服力和证据的强度，是两回事。</b>刚才那些数字里，有一条你没有追下去。'
        : '你标的是「' + confT + '」，说明你心里其实有点犹豫。<b>那点犹豫就是信号</b>——下次让它变成一个具体的求证动作，而不是一个折扣。';
    } else {
      head = '你直接下了定性结论。';
      body = '手上的材料支撑「这里有疑点、要去查」，还不支撑「所以它有问题」。<b>把疑点当判决，和把疑点当空气，是同一种错误的两个方向。</b>';
    }
    const extra = [];
    const acted = stats ? (stats.pressed || 0) + (stats.broke || 0) : 0;
    if (!acted) extra.push('你没有质问他一句就下了判断——<b>下一幕试着先押他几轮</b>，你会发现证词里有裂缝。');
    else if (stats.broke > 0) extra.push('你在质问里戳穿了 ' + stats.broke + ' 处说法——<b>你的判断是建立在自己挖出来的证据上的</b>，这比选对选项值钱。');
    else extra.push('你追问了 ' + stats.pressed + ' 次但没戳穿任何一句——<b>试试「提出证据」</b>，用你手上的数字去顶他的说法。');
    if (stats && stats.noRecord > 0) extra.push('你还问出过 ' + stats.noRecord + ' 次「档里没有」——<b>这比问出答案更难</b>，它是在划材料的边界。');
    if (p.n >= 1 && v === 'risky' && p.risky >= 1) extra.push('这已经是你第 ' + (p.risky + 1) + ' 次选择跟随叙事了。<b>我会记住这一点。</b>');
    return { head, body, extra };
  };

  window.updateProfile = function (story, opt, conf, stats) {
    const p = profile();
    p.n++;
    p[opt.verdict] = (p[opt.verdict] || 0) + 1;
    if (conf >= .95 && opt.verdict !== 'prudent') p.over++;
    if (conf <= .55 && opt.verdict === 'prudent') p.under++;
    p.pressed += (stats && stats.pressed) || 0;
    p.broke += (stats && stats.broke) || 0;
    p.noRecord += (stats && stats.noRecord) || 0;
    if (!p.seenCases.includes(story)) p.seenCases.push(story);
    save();
  };

  /* ============ 质问 ============ */
  window.Court = {
    open(story, onClose) {
      const I = story.interrogation;
      if (!I) return;
      const st = { story, I, i: 0, log: [], used: new Set(), unlocked: new Set(['t1']),
                   stats: { pressed: 0, broke: 0, noRecord: 0 }, onClose };
      window.__court = st;
      // 已解锁的证词按顺序出场
      st.visible = () => I.testimony.filter(t => !t.locked || st.unlocked.has(t.id));
      draw();
    }
  };

  function esc(s) { return String(s); }
  function voc(t) {
    const nm = (typeof coachName === 'function') ? coachName() : '教练';
    return t ? `<div class="vo"><span class="who">${nm}</span><span class="txt">${t}</span></div>` : '';
  }

  function draw() {
    const st = window.__court, I = st.I, w = st.story.cast[0];
    const cur = st.visible()[st.i];
    let h = `<div class="ct-head">
        <span class="ct-av">${w.avatar}</span>
        <div><div class="ct-nm">${w.name}</div><div class="ct-role">${w.role}</div></div>
      </div>
      <p class="ct-rule">${w.rule}</p>`;
    if (!st.log.length) h += `<p class="ct-open">${I.opening}</p><p class="ct-how">${I.howto}</p>`;
    h += st.log.map(entry => `
      <div class="ct-turn">
        ${entry.you ? `<div class="ct-you">${entry.you}</div>` : ''}
        <div class="ct-say${entry.broke ? ' broke' : ''}">
          ${entry.broke ? '<div class="ct-bang">❗ 说法被戳穿</div>' : ''}
          <div class="ct-txt">${entry.text}</div>
          <div class="ct-src">📄 ${entry.src} · <span class="ct-ln">${entry.line}</span></div>
        </div>
        ${voc(entry.coach)}
      </div>`).join('');

    if (cur) {
      h += `<div class="ct-turn"><div class="ct-say"><div class="ct-txt">${cur.text}</div>
        <div class="ct-src">📄 ${cur.src} · <span class="ct-ln">${cur.line}</span></div></div></div>
        <div class="ct-acts">
          ${cur.press && !st.used.has(cur.id + ':press') ? `<button class="ct-btn press" data-press="${cur.id}">🔍 追问这一句</button>` : ''}
          <button class="ct-btn evi" data-evi="${cur.id}">⚖️ 提出证据</button>
          ${st.visible().length > st.i + 1 ? `<button class="ct-btn nxt" data-nx="1">下一句证词 →</button>` : ''}
        </div>`;
    } else {
      h += `<p class="ct-done">质问结束。</p>`;
    }
    h += `<div class="askin"><input id="ct-in" placeholder="或者直接问他……" autocomplete="off"><button id="ct-go">问</button></div>`;
    sheet(h, true);
    bind();
  }

  function bind() {
    const st = window.__court, box = document.getElementById('sheet');
    box.querySelectorAll('[data-press]').forEach(b => b.onclick = () => {
      const t = st.visible().find(x => x.id === b.dataset.press);
      st.used.add(t.id + ':press'); st.stats.pressed++;
      st.log.push({ you: '「这一句，能说得再具体点吗？」', text: t.press.text, src: t.press.src, line: t.press.line, coach: t.press.coach });
      track && track('court_press', { case: st.story.case_id, t: t.id });
      draw();
    });
    box.querySelectorAll('[data-nx]').forEach(b => b.onclick = () => { st.i++; draw(); });
    box.querySelectorAll('[data-evi]').forEach(b => b.onclick = () => showCards(b.dataset.evi));
    const inp = document.getElementById('ct-in');
    document.getElementById('ct-go').onclick = () => { if (inp.value.trim()) freeAsk(inp.value.trim()); };
    inp.onkeydown = e => { if (e.key === 'Enter' && inp.value.trim()) freeAsk(inp.value.trim()); };
    box.scrollTop = box.scrollHeight;
  }

  function showCards(tid) {
    const st = window.__court, I = st.I;
    const cur = st.visible().find(x => x.id === tid);
    const h = `<h3 style="margin:0 0 4px;font-size:17px">⚖️ 提出证据</h3>
      <p class="tip">挑一张你手上的证据，去戳他刚才那句话。选错不扣分——但选对了，他就得改口。</p>
      ${I.cards.map(c => `<button class="ct-card" data-card="${c.id}">${c.t}</button>`).join('')}
      <button class="cta ghost" id="ct-back" style="margin-top:10px">先不提</button>`;
    sheet(h, true);
    const box = document.getElementById('sheet');
    box.querySelectorAll('[data-card]').forEach(b => b.onclick = () => present(cur, b.dataset.card));
    document.getElementById('ct-back').onclick = draw;
  }

  function present(cur, cardId) {
    const st = window.__court;
    const card = st.I.cards.find(c => c.id === cardId);
    const hit = (cur.breaks || []).find(b => b.card === cardId);
    if (hit) {
      st.stats.broke++;
      if (hit.unlock) st.unlocked.add(hit.unlock);
      st.log.push({ you: `「那这个呢——${card.t}」`, text: hit.text, src: hit.src, line: hit.line, coach: hit.coach, broke: true });
      // 戳穿后自动推进到下一条可见证词
      const vis = st.visible();
      const idx = vis.findIndex(x => x.id === (hit.unlock || cur.id));
      st.i = hit.unlock ? Math.max(0, idx) : Math.min(st.i + 1, vis.length);
      track && track('court_break', { case: st.story.case_id, t: cur.id, card: cardId });
    } else {
      st.log.push({ you: `「那这个呢——${card.t}」`, text: st.I.no_record.text, src: '—', line: '—', coach: '这张卡戳不动那句话——它们讲的不是同一件事。<b>换一张，或者先追问一次把他的说法逼得更具体。</b>' });
      track && track('court_miss', { case: st.story.case_id, t: cur.id, card: cardId });
    }
    draw();
  }

  /* 自由提问：有后端走 LLM 语义路由（只返回 id），否则本地关键词 */
  function freeAsk(q) {
    const st = window.__court;
    st.log.push({ you: q, text: '……', src: '—', line: '—', coach: '' });
    draw();
    routeFree(q).then(r => {
      st.log.pop();
      if (r.kind === 'press') {
        const t = st.visible().find(x => x.id === r.tid) || st.visible()[st.i] || st.I.testimony[0];
        st.stats.pressed++;
        st.log.push({ you: q, text: t.press ? t.press.text : t.text, src: t.press ? t.press.src : t.src, line: t.press ? t.press.line : t.line, coach: t.press ? t.press.coach : '' });
      } else {
        st.stats.noRecord++;
        st.log.push({ you: q, text: st.I.no_record.text, src: '—', line: '—', coach: st.I.no_record.coach });
      }
      track && track('court_free', { case: st.story.case_id, kind: r.kind, via: r.via });
      save && save();
      draw();
    });
  }
  function routeFree(q) {
    const st = window.__court;
    const local = () => {
      const s = q.toLowerCase();
      let best = null, len = 0;
      for (const t of st.I.testimony) {
        const keys = [t.text, t.press && t.press.text].filter(Boolean).join('');
        for (const k of ['应收', '现金', '收入', '第四季度', '烧烤', '杠杆', '季中', '股', '对价', '生意', 'bill', 'repo']) {
          if (s.includes(k) && keys.indexOf(k) >= 0 && k.length > len) { len = k.length; best = t; }
        }
      }
      return best ? { kind: 'press', tid: best.id, via: 'local' } : { kind: 'none', via: 'local' };
    };
    if (typeof BACKEND === 'undefined' || !BACKEND) return Promise.resolve(local());
    const topics = st.I.testimony.map(t => ({ id: t.id, desc: (t.text || '').replace(/<[^>]+>/g, '').slice(0, 60) }));
    const ctl = new AbortController();
    const tm = setTimeout(() => ctl.abort(), 6000);
    return fetch(BACKEND + '/api/v1/ask-coach', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: ctl.signal,
      body: JSON.stringify({ device: S.device, case_id: st.story.case_id, question: q, topics })
    }).then(r => r.json()).then(d => {
      clearTimeout(tm);
      if (d.id && d.id !== 'none' && st.I.testimony.some(t => t.id === d.id)) return { kind: 'press', tid: d.id, via: 'llm' };
      return { kind: 'none', via: 'llm' };
    }).catch(() => { clearTimeout(tm); return local(); });
  }
})();
