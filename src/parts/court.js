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
    if (!p.n) return '我还不了解你。做一个案例，我就开始认识你的判断习惯了。';
    const bits = [];
    if (p.risky >= 2 && p.risky > p.prudent) bits.push('你倾向于顺着叙事走：前面的案例里有 ' + p.risky + ' 次选了跟随');
    if (p.hasty >= 2) bits.push('你有 ' + p.hasty + ' 次在证据还不够时就下了定性结论');
    if (p.prudent >= 2) bits.push('你多数时候会先求证再下结论，这是好习惯');
    if (p.over >= 1) bits.push('有 ' + p.over + ' 次你标了「很有把握」却判错——这是校准要治的病');
    if (p.broke >= 2) bits.push('你已经在追问中找出了 ' + p.broke + ' 处说法，说明你会用证据');
    if (p.noRecord >= 1) bits.push('你问出过「档里没有」，这比问出答案更难');
    return bits.length ? bits.join('；') + '。' : '目前看不出稳定的模式。再做一个案例。';
  };

  /* 教练对「这一次选择」的解读：离线规则合成，接后端后由 LLM 基于同样的结构化信号改写 */
  window.choiceReading = function (story, opt, conf, stats, prior) {
    const p = prior || profile();
    const confT = conf >= .95 ? '很有把握' : conf >= .75 ? '比较有把握' : '没把握';
    const v = opt.verdict;
    let head, body;
    if (v === 'prudent') {
      head = '你先把问题留在了桌上。';
      body = conf >= .95
        ? '你对调查方向很有把握，这没问题。只是别让这份把握悄悄变成对结论的确信；查证的意义，正是允许结果推翻你。'
        : '你给出的把握程度和手上的材料差不多。先把下一步查什么写清楚，比抢一个结论有用。';
    } else if (v === 'risky') {
      head = '你先信了这个故事。';
      body = conf >= .95
        ? '而且没有给自己留下退路。回头看刚才的材料：哪一条事实一旦不成立，就足以让你改口？'
        : '你选了“' + confT + '”，说明疑问其实还在。下次别只给信心打折，直接写下：我还缺哪一条材料？';
    } else {
      head = '你把疑点直接写成了结论。';
      body = '现在的材料只够让你继续查，还不够定性。先说清楚哪项证据能证实或推翻它，再决定要不要把话说满。';
    }
    const extra = [];
    const acted = stats ? (stats.pressed || 0) + (stats.broke || 0) : 0;
    if (story && story.interrogation) {
      if (!acted) extra.push('你还没追问就做了判断。下一个现场先多问一轮，看看几句话能不能同时成立。');
      else if (stats.broke > 0) extra.push('你在追问里找出了 ' + stats.broke + ' 处矛盾。这个判断来自你自己挖出的证据。');
      else extra.push('你追问了 ' + stats.pressed + ' 次，还没找到矛盾。试试拿手上的数字去顶他的说法。');
      if (stats && stats.noRecord > 0) extra.push('你还碰到过 ' + stats.noRecord + ' 次“档里没有”。知道材料回答不了什么，也是一种进展。');
    }
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
      // 关掉抽屉再点一次「先质问」不是重新开庭——原来这里无条件新建 st，
      // 把已经戳穿的证词、追问记录、stats 全部抹掉，还没有任何提示。
      // 而 stats 正是后面教练解读要读的东西（story.js 在揭示拍读 __court.stats）。
      const prev = window.__court;
      const st = (prev && prev.story === story) ? prev
        : { story, I, i: 0, log: [], used: new Set(), unlocked: new Set(['t1']),
            stats: { pressed: 0, broke: 0, noRecord: 0 } };
      st.onClose = onClose;
      window.__court = st;
      window.__sheetClose = onClose || null;
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
        <span class="ct-av">${ic('me')}</span>
        <div class="ct-who"><div class="ct-nm">${w.name}</div><div class="ct-role">${w.role}</div></div>
        <button class="ct-x" id="ct-x">${ic('close')} 回到决策</button>
      </div>
      <p class="ct-rule">${w.rule}</p>
      <p class="ct-rule">${(typeof BACKEND !== 'undefined' && BACKEND && st.story.x_discuss !== false)
        ? '<span class="llm-tag">【LLM 扮演 · ' + w.name + '】</span>直接问他时，回答由 AI 用他当年的口吻、只凭这份材料推演，会标红。带行号的陈述才是他真写过的。'
        : '<span class="llm-tag off">【LLM 扮演 · 未连接】</span>现在直接问他，只能匹配到他写过的原话。接上后端后，他会用当年的口吻和你讨论为什么这样决策。'}</p>`;
    if (!st.log.length) h += `<p class="ct-open">${I.opening}</p><p class="ct-how">${I.howto}</p>`;
    h += st.log.map(entry => `
      <div class="ct-turn">
        ${entry.you ? `<div class="ct-you">${entry.you}</div>` : ''}
        <div class="ct-say${entry.broke ? ' broke' : ''}${entry.llm ? ' llm' : ''}">
          ${entry.broke ? `<div class="ct-bang">${ic('alert')} 该说法与材料矛盾</div>` : ''}
          ${entry.llm ? `<div class="llm-tag">【LLM 扮演 · ${w.name} 说】</div>` : ''}
          <div class="ct-txt">${entry.text}</div>
          ${entry.llm
            ? `<div class="ct-src">AI 基于这份材料推演的口吻，不是原档逐字。要看他真写过的，用上面带行号的陈述。</div>`
            : `<div class="ct-src">${ic('doc')} ${entry.src} · <span class="ct-ln">${entry.line}</span></div>`}
        </div>
        ${voc(entry.coach)}
      </div>`).join('');

    if (cur) {
      h += `<div class="ct-turn"><div class="ct-say"><div class="ct-txt">${cur.text}</div>
        <div class="ct-src">${ic('doc')} ${cur.src} · <span class="ct-ln">${cur.line}</span></div></div></div>
        <div class="ct-acts">
          ${cur.press && !st.used.has(cur.id + ':press') ? `<button class="ct-btn press" data-press="${cur.id}">${ic('search')} 追问这一句</button>` : ''}
          <button class="ct-btn evi" data-evi="${cur.id}">${ic('scale')} 提出证据</button>
          ${st.visible().length > st.i + 1 ? `<button class="ct-btn nxt" data-nx="1">下一条陈述 →</button>` : ''}
        </div>`;
    } else {
      h += `<p class="ct-done">追问结束。</p>`;
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
    const x = document.getElementById('ct-x');
    if (x) x.onclick = () => { window.__sheetClose = st.onClose || null; closeSheet(); };
    const inp = document.getElementById('ct-in'), go = document.getElementById('ct-go');
    if (st.asking) { inp.disabled = true; go.disabled = true; go.textContent = '问…'; }
    go.onclick = () => { if (!st.asking && inp.value.trim()) freeAsk(inp.value.trim()); };
    inp.onkeydown = e => { if (e.key === 'Enter' && !st.asking && inp.value.trim()) freeAsk(inp.value.trim()); };
    box.scrollTop = box.scrollHeight;
  }

  function showCards(tid) {
    const st = window.__court, I = st.I;
    const cur = st.visible().find(x => x.id === tid);
    const h = `<h3 style="margin:0 0 4px;font-size:17px">${ic('scale')} 提出证据</h3>
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

  /* 当事人能看见的材料：只有 reveal 之前的当年内容。
     结局不喂给他，他就说不出结局。这是材料闸，出口闸在服务端（check_discuss）。 */
  function eraMaterial() {
    const st = window.__court, story = st.story, I = st.I;
    const kinds = story.beats.map(b => b.kind);
    const ri = kinds.indexOf('reveal');
    const pre = ri < 0 ? story.beats : story.beats.slice(0, ri);
    const SKIP = { kind: 1, id: 1, src: 1, line: 1, fact: 1, accession: 1, anchors: 1, orig: 1, options: 1, verdict: 1, canon: 1, _note: 1 };
    const out = [];
    const strip = t => String(t).replace(/<[^>]+>/g, '');
    (function walk(o) {
      if (typeof o === 'string') { if (o.trim()) out.push(strip(o)); return; }
      if (Array.isArray(o)) { o.forEach(walk); return; }
      if (o && typeof o === 'object') Object.keys(o).forEach(k => { if (!SKIP[k]) walk(o[k]); });
    })(pre);
    const w = story.cast[0] || {};
    [w.intro, I.opening].forEach(t => { if (t) out.push(strip(t)); });
    (I.testimony || []).forEach(t => {
      out.push(strip(t.text));
      if (t.press) out.push(strip(t.press.text));
      (t.breaks || []).forEach(b => out.push(strip(b.text)));
    });
    (I.cards || []).forEach(c => out.push(strip(c.t)));
    if (I.no_record) out.push(strip(I.no_record.text));
    return out.join(String.fromCharCode(10));
  }

  /* 决策人复盘对话（登记簿 #10）：LLM 以当事人身份、当年口吻回答；任何一环失败返回 null。 */
  function discussFree(q) {
    const st = window.__court, story = st.story;
    if (typeof BACKEND === 'undefined' || !BACKEND || story.x_discuss === false) return Promise.resolve(null);
    const history = [];
    st.log.forEach(e => { if (e.llm && e.you) { history.push({ role: 'user', content: e.you }); history.push({ role: 'assistant', content: e.text }); } });
    const w = story.cast[0] || {};
    const ctl = new AbortController();
    const tm = setTimeout(() => ctl.abort(), 20000);
    return fetch(BACKEND + '/api/v1/discuss', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: ctl.signal,
      body: JSON.stringify({ device: S.device, case_id: story.case_id, era: story.era,
        persona: { name: w.name, role: w.role, intro: w.intro, rule: w.rule },
        material: eraMaterial(), history: history.slice(-6), question: q })
    }).then(r => r.json()).then(d => { clearTimeout(tm); return (d && d.text) ? d.text : null; })
      .catch(() => { clearTimeout(tm); return null; });
  }

  /* 自由提问：先让当事人用当年口吻回答（#10）；拿不到（没后端 / 超时 / 出口检查丢弃）
     就回落到逐字匹配（#8）：LLM 只挑一条他真写过的原话，或本地关键词。 */
  function freeAsk(q) {
    const st = window.__court;
    if (st.asking) return;          // 在飞行中
    st.asking = true;
    st.log.push({ you: q, text: '……', src: '—', line: '—', coach: '' });
    draw();
    discussFree(q).then(text => {
      if (text) {
        st.asking = false;
        st.log.pop();
        st.stats.pressed++;
        st.log.push({ you: q, text: text, src: 'AI 推演', line: '', coach: '', llm: true });
        track && track('court_discuss', { case: st.story.case_id });
        save && save();
        draw();
        return null;
      }
      return routeFree(q);
    }).then(r => {
      if (!r) return;
      st.asking = false;
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
    }).catch(() => {
      // 复位是必须的：漏掉的话一次异常就把输入框永久锁死，
      // 用户看到一个灰掉的「问…」，没有任何办法让它回来。
      st.asking = false;
      if (st.log.length && st.log[st.log.length - 1].text === '……') st.log.pop();
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
        for (const k of ['应收', '现金', '收入', '第四季度', '烧烤', '杠杆', '季中', '股', '对价', '生意', '账期', '经销商', '渠道', '库存', 'bill', 'repo']) {
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
