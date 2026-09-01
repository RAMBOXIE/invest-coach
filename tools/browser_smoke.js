// 冒烟：走一遍完整回路，确认 540 条文案改写没有改坏任何链路。
// 用法：把它复制进 dist/ 再在浏览器里 fetch+eval，或直接粘进控制台。
// 不进构建（build.py 只读 src/），也不该进 —— 它是开发期的验收工具。
(function () {
  var errs = [];
  window.onerror = function (m) { errs.push(String(m)); };
  var out = {};
  localStorage.removeItem('invest-coach:ch1');
  S = fresh(); lit = new Set(); render();
  out['1_首屏'] = document.body.innerText.slice(0, 100);

  var pick = document.querySelector('[data-tone]');
  if (pick) pick.click();
  out['2_选完教练后的队首'] = document.querySelector('.hero')
    ? document.querySelector('.hero').innerText.slice(0, 130) : '(无 hero)';

  // 走一个基础节点到底
  openNode('three-statements');
  if (!R) { out['ERR'] = 'openNode 没有建立 R；stateOf=' + stateOf(byId['three-statements']); return out; }
  var steps = [];
  for (var g = 0; g < 14; g++) {
    if (!R) { steps.push('(已退出舞台)'); break; }
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
  out['3_步骤序列'] = steps.join(' → ');
  out['4_该节点是否通过'] = lit.has('three-statements');
  var sb = document.getElementById('stage-body');
  out['5_通过屏'] = sb ? sb.innerText.slice(0, 160) : '(舞台已关)';

  // 回今日，看队列
  var back = document.querySelector('#stage-foot .cta');
  if (back) back.click();
  out['6_回到今日'] = document.querySelector('.hero')
    ? document.querySelector('.hero').innerText.slice(0, 130) : '(无 hero)';

  out['7_残留黑话'] = (function () {
    var t = document.body.innerText;
    return ['红旗', '点亮', '锚题', '复训', '案卷', '判卷', '混淆对', '雷区', '双阳', '步差']
      .filter(function (w) { return t.indexOf(w) >= 0; });
  })();
  out['8_报错'] = errs;
  return out;
})();
