// 手机端体检：在真实视口下量实际渲染结果。
//
// 静态 CSS 检查（check_a11y 的 A3）查的是声明的 min-height，
// 查不出**算出来**的尺寸、横向溢出、以及元素撑破容器。这个脚本量真值。
//
// 用法：cp tools/mobile_audit.js dist/_m.js，把视口设成手机尺寸，然后
//   const s = await fetch('/_m.js').then(r=>r.text()); eval(s)
(function () {
  const VW = innerWidth, VH = innerHeight;
  const rep = {};

  function scan(label) {
    const out = { 屏: label, 问题: [] };
    const doc = document.documentElement;

    // 1) 横向溢出：页面能不能左右拖
    if (doc.scrollWidth > VW + 1) {
      const wide = [...document.querySelectorAll('*')].filter(e => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && (r.right > VW + 1 || r.left < -1)
          && getComputedStyle(e).position !== 'fixed';
      }).slice(0, 6).map(e => {
        const r = e.getBoundingClientRect();
        return `${e.className || e.tagName}(${Math.round(r.left)}→${Math.round(r.right)})`;
      });
      out.问题.push(`横向溢出 ${doc.scrollWidth}px > 视口 ${VW}px：${wide.join(', ')}`);
    }

    // 2) 触控目标实际尺寸
    const small = [...document.querySelectorAll('button,a,input,label,[data-o],[data-a],[data-cf],[data-c]')]
      .filter(e => {
        const r = e.getBoundingClientRect();
        const cs = getComputedStyle(e);
        if (!(r.width > 0 && r.height > 0) || cs.display === 'none' || cs.visibility === 'hidden')
          return false;
        // 被 label 包住的 input，真正的触控目标是那个 label：点标签任何一处都生效。
        // 只要 label 够大就不算缺陷，否则会把合规的写法报成问题。
        const lab = e.tagName === 'INPUT' ? e.closest('label') : null;
        if (lab && lab.getBoundingClientRect().height >= 44) return false;
        return r.height < 44 || r.width < 24;
      })
      .map(e => {
        const r = e.getBoundingClientRect();
        return `${(e.className || e.tagName).toString().slice(0, 22)} ${Math.round(r.width)}×${Math.round(r.height)}`;
      });
    if (small.length) out.问题.push(`触控目标小于 44px 高：${[...new Set(small)].slice(0, 6).join(' | ')}`);

    // 3) 正文字号
    const tiny = [...document.querySelectorAll('p,li,span,div,td,button,label')]
      .filter(e => {
        if (!e.textContent.trim() || e.children.length) return false;
        const fs = parseFloat(getComputedStyle(e).fontSize);
        const r = e.getBoundingClientRect();
        return r.height > 0 && fs > 0 && fs < 12;
      })
      .map(e => `${(e.className || e.tagName).toString().slice(0, 20)} ${getComputedStyle(e).fontSize}`);
    if (tiny.length) out.问题.push(`字号小于 12px：${[...new Set(tiny)].slice(0, 5).join(' | ')}`);

    // 4) 撑破容器：子元素比父容器宽
    const burst = [...document.querySelectorAll('.cmp,.panel,.card-c,.opt,.fb,.coach,.draft,.opt-in')]
      .filter(e => e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflowX === 'visible')
      .map(e => `${e.className} 内容 ${e.scrollWidth} > 容器 ${e.clientWidth}`);
    if (burst.length) out.问题.push(`内容撑破容器且没有横向滚动：${burst.slice(0, 4).join(' | ')}`);

    // 5) 被固定元素遮住的可点元素（底部标签栏 / 悬浮按钮）
    //
    // **必须先把元素滚进视口再量。** 第一版没滚，于是把「只是还在折叠线以下」
    // 当成了「被盖住」，报了一串假阳性（包括「重置全部进度」，实测它完全可达）。
    // elementFromPoint 在视口外返回的是别的东西，量出来的是噪音。
    //
    // 另外：全屏覆盖层（判卷台 / 案例）开着的时候，底层被盖是设计如此，不算问题。
    const overlay = ['stage', 'sty'].some(id => {
      const e = document.getElementById(id);
      return e && getComputedStyle(e).display !== 'none'
        && e.getBoundingClientRect().height > 100;
    });
    const scope = overlay ? '#stage button:not([disabled]), #sty button:not([disabled])'
                          : '.app button:not([disabled]), .app label, .tabbar button';
    const covered = [];
    for (const e of document.querySelectorAll(scope)) {
      const r0 = e.getBoundingClientRect();
      if (r0.height === 0 || getComputedStyle(e).visibility === 'hidden') continue;
      // 折叠着的 <details> 里的东西不该算：它有布局盒但用户看不见，
      // scrollIntoView 对它也是空操作（实测滚动停在 0）。
      // 第一版没排除，于是把折叠抽屉里的教练卡报成「被标签栏盖住」；
      // 实测用户点开抽屉再滚到底，那张卡完全可点。
      const det = e.closest('details');
      if (det && !det.open) continue;
      e.scrollIntoView({ block: 'center' });
      const r = e.getBoundingClientRect();
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      if (cx < 0 || cx > VW || cy < 0 || cy > VH) continue;
      const top = document.elementFromPoint(cx, cy);
      if (top && top !== e && !e.contains(top) && !top.contains(e)) {
        covered.push(`${(e.className || e.id || e.tagName).toString().slice(0, 22)}「${e.textContent.trim().slice(0, 12)}」被 ${(top.className || top.tagName).toString().slice(0, 18)} 盖住`);
      }
    }
    if (covered.length) out.问题.push(`滚进视口后仍点不到：${covered.slice(0, 4).join(' | ')}`);

    if (!out.问题.length) out.问题 = '无';
    return out;
  }

  // ── 逐屏走 ──
  localStorage.removeItem('invest-coach:ch1');
  S = fresh(); lit = new Set(); render();
  rep.a_选教练 = scan('首次进入·选教练');
  const pick = document.querySelector('[data-tone]'); if (pick) pick.click();
  rep.b_今日 = scan('今日');
  TAB = 'atlas'; render(); rep.c_图谱 = scan('图谱');
  TAB = 'me'; render(); rep.d_我 = scan('我');
  TAB = 'today'; render();

  // 深层节点：材料 → 先写 → 挑证据 → 排除 → 下结论 → 自评 → 回顾 → 闭卷题
  lit = new Set(['three-statements', 'growth-rate', 'accrual-basis', 'receivables', 'ocf',
                 'case-first-look', 'base-rate', 'find-filings']);
  S.lit = [].slice.call(lit); render();
  openNode('rf1');
  const seen = {};
  for (let g = 0; g < 22 && R; g++) {
    const st = R.steps[R.step];
    if (!seen[st]) { rep['e_' + st] = scan('深层节点·' + st); seen[st] = 1; }
    const body = document.getElementById('stage-body');
    if (!body) break;
    const cf = body.querySelector('[data-cf]:not(.on),[data-af]:not(.on)'); if (cf) cf.click();
    const q = (st === 'anchor' && R.anchor) ? R.anchor.quiz
            : (st === 'conclude' && R.mainQ) ? R.mainQ[R.quizIdx] : null;
    if (q) {
      const shown = shownOpts(q);
      const i = shown.findIndex(o => o.ok);
      const btns = body.querySelectorAll('[data-' + (st === 'anchor' ? 'a' : 'o') + ']');
      if (btns[i]) btns[i].click();
    }
    if (st === 'write') {
      const t = document.getElementById('st-draft');
      if (t) { t.value = '应收增速比收入快了一倍，现金流没跟上'; t.dispatchEvent(new Event('input')); }
      const w = document.getElementById('st-wdone'); if (w) w.click();
      rep.e_write_教练回应 = scan('深层节点·先写·教练已回应');
    }
    const nb = document.querySelector('#stage-foot .cta:not([disabled])');
    if (!nb) break;
    nb.click();
  }
  if (document.getElementById('stage')) document.getElementById('stage').classList.remove('show');

  // 案例（暗场，宽面板最多）
  R = null; render();
  if (typeof openStory === 'function') {
    openStory('nikola-2021');
    rep.f_案例首屏 = scan('案例·开场');
    for (let g = 0; g < 3; g++) {
      const b = document.querySelector('#sty .cta:not([disabled]), #sty button.cta');
      if (!b) break; b.click();
    }
    rep.g_案例面板 = scan('案例·数据面板');
    const sty = document.getElementById('sty'); if (sty) sty.classList.remove('show');
  }

  rep._视口 = VW + '×' + VH;
  return rep;
})();
