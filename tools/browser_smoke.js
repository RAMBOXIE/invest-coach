// 浏览器冒烟：走一遍完整回路，确认改动没有改坏任何链路。
//
// 用法：cp tools/browser_smoke.js dist/_smoke.js，然后在页面控制台里
//   const s = await fetch('/_smoke.js').then(r=>r.text()); eval(s)
// 不进构建（build.py 只读 src/），也不该进——它是开发期的验收工具。
(function () {
  var errs = [];
  window.onerror = function (m) { errs.push(String(m)); };
  var out = {};
  var JARGON = ['红旗', '点亮', '锚题', '复训', '案卷', '判卷', '混淆对', '雷区',
                '双阳', '一阳一阴', '步差', '终局', '实锤', '质问', '证词', '戳穿'];
  function jargonOnScreen() {
    var t = document.body.innerText;
    return JARGON.filter(function (w) { return t.indexOf(w) >= 0; });
  }
  var seenJargon = {};

  localStorage.removeItem('invest-coach:ch1');
  S = fresh(); lit = new Set(); render();
  out['1_首屏'] = document.body.innerText.slice(0, 80);
  var pick = document.querySelector('[data-tone]'); if (pick) pick.click();

  // ── 走完一个基础节点 ──
  openNode('three-statements');
  if (!R) { out.ERR = '打不开节点'; return out; }
  var steps = [];
  for (var g = 0; g < 16 && R; g++) {
    steps.push(R.steps[R.step]);
    if (R.steps[R.step] === 'conclude' && !R.done) {
      var q = R.mainQ[R.quizIdx], shown = shownOpts(q);
      var cf = document.querySelector('#stage-body [data-cf]'); if (cf) cf.click();
      var i = shown.findIndex(function (o) { return o.ok; });
      var btn = document.querySelectorAll('#stage-body [data-o]')[i];
      if (btn) btn.click();
    }
    var b = document.querySelector('#stage-foot .cta:not([disabled])');
    if (!b) break;
    b.click();
  }
  out['2_节点步骤'] = steps.join(' → ');
  out['3_节点已通过'] = lit.has('three-statements');

  // ── 三个页签都渲染得出来 ──
  ['today', 'atlas', 'me'].forEach(function (t) {
    TAB = t; render();
    out['4_' + t] = document.getElementById('view').innerText.length + ' 字';
    jargonOnScreen().forEach(function (w) { seenJargon[w] = (seenJargon[w] || 0) + 1; });
  });
  TAB = 'today'; render();

  // ── 深层节点走到闭卷题 ──
  lit = new Set(['three-statements', 'growth-rate', 'accrual-basis', 'receivables', 'ocf',
                 'case-first-look', 'base-rate']);
  S.lit = [].slice.call(lit); render();
  openNode('rf1');
  var deepSteps = [], sawAnchor = false;
  for (var g2 = 0; g2 < 24 && R; g2++) {
    var st = R.steps[R.step];
    deepSteps.push(st);
    if (st === 'anchor') sawAnchor = true;
    var body = document.getElementById('stage-body');
    if (!body) break;
    var cf2 = body.querySelector('[data-cf]:not(.on),[data-af]:not(.on)'); if (cf2) cf2.click();
    var opt = body.querySelector('[data-o]:not([disabled]),[data-a]:not([disabled])');
    if (opt) opt.click();
    var nb = document.querySelector('#stage-foot .cta:not([disabled])');
    if (!nb) { // 卡住了，看看是不是要先勾选
      var any = body.querySelector('button:not([disabled])');
      if (any && any !== opt) { any.click(); continue; }
      break;
    }
    nb.click();
  }
  out['5_深层节点步骤'] = deepSteps.join(' → ');
  out['6_走到过闭卷题'] = sawAnchor;

  // ── 案例（幕） ──
  if (typeof openStory === 'function') {
    openStory('nikola-2021');
    var sty = document.getElementById('sty');
    out['7_案例已打开'] = !!(sty && getComputedStyle(sty).display !== 'none');
    out['8_案例首屏'] = (document.querySelector('#sty') || {}).innerText
      ? document.querySelector('#sty').innerText.slice(0, 90) : '(空)';
    jargonOnScreen().forEach(function (w) { seenJargon[w] = (seenJargon[w] || 0) + 1; });
    sty.classList.remove('show');
  }

  out['9_页面上的残留黑话'] = Object.keys(seenJargon);
  out['10_报错'] = errs;
  return out;
})();
