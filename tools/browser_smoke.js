// 浏览器冒烟：走一遍完整回路，确认改动没有改坏任何链路。
//
// 用法：cp tools/browser_smoke.js dist/_smoke.js，然后在页面控制台里
//   const s = await fetch('/_smoke.js').then(r=>r.text()); eval(s)
// 不进构建（build.py 只读 src/），也不该进：它是开发期的验收工具。
(function () {
  var errs = [];
  window.onerror = function (m) { errs.push(String(m)); };
  var out = {};
  var JARGON = ['红旗', '点亮', '锚题', '复训', '案卷', '判卷', '混淆对', '雷区',
                '双阳', '一阳一阴', '步差', '终局', '实锤', '质问', '证词', '戳穿'];
  var seen = {};
  function sweep() {
    var t = document.body.innerText;
    JARGON.forEach(function (w) { if (t.indexOf(w) >= 0) seen[w] = 1; });
  }

  localStorage.removeItem('invest-coach:ch1');
  S = fresh(); lit = new Set(); render();
  var pick = document.querySelector('[data-tone]'); if (pick) pick.click();
  out['1_队首'] = document.querySelector('.hero')
    ? document.querySelector('.hero').innerText.slice(0, 90) : '(无 hero)';
  sweep();

  // ── 基础节点现在也要过闭卷题 ──
  function runNode(id) {
    openNode(id);
    if (!R) return { err: '打不开 ' + id };
    var steps = [], sawAnchor = false, anchorQ = null;
    for (var g = 0; g < 20 && R; g++) {
      var st = R.steps[R.step];
      steps.push(st);
      if (st === 'anchor') { sawAnchor = true; if (R.anchor) anchorQ = R.anchor.quiz.q.slice(0, 44); }
      var body = document.getElementById('stage-body');
      if (!body) break;
      var cf = body.querySelector('[data-cf]:not(.on),[data-af]:not(.on)');
      if (cf) cf.click();
      // 一律选正确项，走到底
      var q = (st === 'anchor' && R.anchor) ? R.anchor.quiz
            : (st === 'conclude' && R.mainQ) ? R.mainQ[R.quizIdx] : null;
      if (q) {
        var shown = shownOpts(q);
        var i = shown.findIndex(function (o) { return o.ok; });
        var sel = '[data-' + (st === 'anchor' ? 'a' : 'o') + ']';
        var btns = body.querySelectorAll(sel);
        if (btns[i]) btns[i].click();
      }
      var nb = document.querySelector('#stage-foot .cta:not([disabled])');
      if (!nb) break;
      nb.click();
    }
    sweep();
    return { 步骤: steps.join(' → '), 有闭卷题: sawAnchor, 闭卷题: anchorQ, 通过: lit.has(id) };
  }

  out['2_三张表的分工'] = runNode('three-statements');
  out['3_去哪找年报'] = runNode('find-filings');

  // ── 答错时显示的是针对这个选项的归因，不是通用串 ──
  S = fresh(); lit = new Set();
  S.profile = { tone: 'value', n: 0, prudent: 0, risky: 0, hasty: 0, over: 0, under: 0,
                pressed: 0, broke: 0, noRecord: 0, seenCases: [] };
  render(); openNode('growth-rate');
  while (R && R.steps[R.step] !== 'conclude') {
    var b0 = document.querySelector('#stage-foot .cta:not([disabled])');
    if (!b0) break; b0.click();
  }
  if (R && R.steps[R.step] === 'conclude') {
    var q2 = R.mainQ[R.quizIdx], sh = shownOpts(q2);
    var wi = sh.findIndex(function (o) { return !o.ok; });
    var cf2 = document.querySelector('#stage-body [data-cf]'); if (cf2) cf2.click();
    document.querySelectorAll('#stage-body [data-o]')[wi].click();
    out['4_答错显示的话'] = (document.querySelector('#stage-body .fb') || {}).textContent || '(无)';
    out['5_该选项标注的why'] = sh[wi].why || '(没标)';
    out['6_是否用了通用串'] = /^不对。要不要看一级提示/.test(out['4_答错显示的话']);
    out['7_误解已记账'] = JSON.stringify(S.mis);
  }

  out['8_残留黑话'] = Object.keys(seen);
  out['9_报错'] = errs;
  return out;
})();
