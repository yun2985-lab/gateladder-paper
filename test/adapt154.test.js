const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const GL = require('../adapt154.js');

const FLAGS = {
  A: { TREND: true, RSI: true, STRETCH: false, UNTIL_ZERO: false, SIDE_BLOCK: true },
  B: { TREND: true, RSI: true, STRETCH: false, UNTIL_ZERO: false, SIDE_BLOCK: false },
  C: { TREND: true, RSI: true, STRETCH: true, UNTIL_ZERO: false, SIDE_BLOCK: true },
  D: { TREND: true, RSI: true, STRETCH: false, UNTIL_ZERO: true, SIDE_BLOCK: true },
  E: { TREND: true, RSI: true, STRETCH: true, UNTIL_ZERO: false, SIDE_BLOCK: false },
};

function variant(id, availability, extra) {
  return Object.assign({
    id: id,
    name: id === 'A' ? 'A (앱 기본)' : id,
    flags: FLAGS[id],
    data_path: id + '/data.json',
    entries_path: id + '/entries_0.9.154_' + id + '.csv',
    monthly_path: id + '/monthly.csv',
    report_path: id + '/report.json',
    entries_available: true,
    monthly_available: true,
    report_available: true,
    availability: availability,
  }, extra || {});
}

function manifest(availability) {
  return {
    version: '0.9.154',
    updated: '2026-11-08T06:15:21.001324+09:00',
    start: '2025-11-04 00:00:00 KST',
    cutoff: '2026-11-07 23:54:00 KST',
    seed: 1000,
    variants: ['A', 'B', 'C', 'D', 'E'].map(function (id) { return variant(id, availability); }),
  };
}

test('requested switch matrix matches the published experiment', function () {
  assert.deepEqual(GL.REQUESTED.A.flags, FLAGS.A);
  assert.equal(GL.REQUESTED.A.name, 'A (앱 기본)');
  ['B', 'C', 'D', 'E'].forEach(function (id) { assert.deepEqual(GL.REQUESTED[id].flags, FLAGS[id]); });
  assert.equal(GL.MANIFEST_URL, 'https://raw.githubusercontent.com/yun2985-lab/gateladder-paper/data_0154/data.json');
  assert.ok(!GL.MANIFEST_URL.includes('data_y1'));
  assert.ok(!GL.MANIFEST_URL.includes('data_latest'));
});

test('nested availability governs downloads and flat flags are ignored', function () {
  const parsed = GL.parseManifest(manifest({ data: true, entries: false, monthly: false, report: false }));
  assert.equal(parsed.ok, true);
  parsed.slots.forEach(function (slot) {
    assert.equal(slot.available.present, true);
    assert.equal(slot.available.data, true);
    assert.equal(slot.available.entries, false);
    assert.equal(slot.available.monthly, false);
    assert.equal(slot.available.report, false);
    const plan = GL.downloadPlan(slot, {
      downloads: { entries: 'https://evil.example/secret.csv', monthly: slot.paths.monthly, report: { href: 'https://evil.example/r.json' } },
      run_phase: 'REPLAY',
      frozen_report_available: false,
    });
    assert.deepEqual(plan.map(function (item) { return item.state; }), ['unavailable', 'unavailable', 'unavailable']);
    assert.ok(plan.every(function (item) { return !item.href; }));
    const html = GL.renderPanel({
      view: 'ready',
      selected: slot.id,
      slots: [Object.assign({}, slot, {
        fetchStatus: { code: 'ok', label: '받음' },
        phase: { code: 'replay', label: '재생 중', frozen: false },
        fresh: { text: '1분 미만', stale: false },
        progress: 13.2,
        metrics: GL.metricsOf({ equity_rebate: 1, normal_entry_counts: { L: 0, S: 1 } }),
      })],
      downloads: plan.map(function (item) { return GL.finalizeDownload(item, true); }),
      report: { state: 'none' },
      manifest: parsed.manifest,
      manifestUpdated: parsed.updated,
    });
    assert.equal(html.includes('<a '), false);
    assert.equal(html.includes('evil.example'), false);
    assert.match(html, /진입 CSV: 없음/);
    assert.match(html, /월별 CSV: 없음/);
    assert.match(html, /보고서 JSON: 없음/);
    assert.match(html, /동결 보고서가 아직 없습니다/);
  });
});

test('availability true still needs a verified file and rejects foreign hrefs', function () {
  const parsed = GL.parseManifest(manifest({ data: true, entries: true, monthly: false, report: true }));
  const slot = parsed.slots[0];
  const plan = GL.downloadPlan(slot, {
    downloads: { entries: 'https://evil.example/entries.csv' },
    run_phase: 'FROZEN',
    frozen_report_available: true,
  });
  const entries = plan[0];
  const monthly = plan[1];
  const report = plan[2];
  assert.equal(entries.state, 'check');
  assert.equal(entries.href, GL.RAW_ROOT + 'A/entries_0.9.154_A.csv');
  assert.equal(entries.finalMode, 'frozen');
  assert.equal(monthly.state, 'unavailable');
  assert.equal(report.state, 'check');
  assert.equal(report.href, GL.RAW_ROOT + 'A/report.json');
  const broken = GL.finalizeDownload(entries, false);
  const ready = GL.finalizeDownload(entries, true);
  const html = GL.renderPanel({
    view: 'ready', selected: 'A', slots: parsed.slots.map(function (s) {
      return Object.assign({}, s, { fetchStatus: { code: 'ok', label: '받음' }, phase: GL.phaseOf({ run_phase: 'FROZEN' }), fresh: { text: '1분 미만' }, metrics: null });
    }),
    downloads: [broken, GL.finalizeDownload(monthly, true), ready && GL.finalizeDownload(report, true)],
    report: { state: 'broken' },
    manifest: parsed.manifest,
  });
  assert.match(html, /진입 CSV: 파일을 확인하지 못함/);
  assert.match(html, /월별 CSV: 없음/);
  assert.match(html, /보고서 JSON \(동결\)/);
  assert.match(html, /보고서를 불러오지 못했습니다/);
  assert.equal(html.includes('evil.example'), false);
  assert.equal((html.match(/<a /g) || []).length, 1);
});

test('replay payload metrics are read and missing ones stay absent', function () {
  const picked = GL.metricsOf({
    ret_rebate_pct: 0.845,
    equity_rebate: 1008.45,
    mdd_pct: 0.691,
    mdd_raw_pct: 0.691,
    mdd_rebate_exact_pct: 0.651661,
    max_margin_usage_pct: 22.02,
    normal_entry_counts: { L: 0, S: 156 },
    normal_L: 999,
    filter_counts: {
      TREND: { placement_rejected: 2292, pending_cancelled: 0, blocked_side_minutes: 17500 },
      RSI: { placement_rejected: 90, pending_cancelled: 14, blocked_side_minutes: 480 },
      STRETCH: { placement_rejected: 0, pending_cancelled: 0, blocked_side_minutes: 0 },
    },
    filter_totals: { placement_attempts: 4069, placement_rejected: 2357, pending_cancelled: 14, side_minutes: 35000 },
    rescue_stats: { count: 12, max_h: 8589, avg_h: 727.7 },
    repayment_by_target153: { HELD: { events: 17, contracts: 17 }, OLD_ADDS: { events: 0, contracts: 0 } },
    repayment_events152: 17,
    margin50_skips: 0,
    margin50_skips_by_side: { L: 0, S: 0 },
    monthly: [{ month: '2025-11', start: 1000, end: 1002.51, pnl_pct: 0.251, pnl_usdt: 2.51, trades: 475, wins: 428 }],
    progress: 13.2,
    run_phase: 'REPLAY',
    frozen_report_available: false,
  });
  assert.equal(picked.values.normal_L, 0);
  assert.equal(picked.values.normal_S, 156);
  assert.equal(picked.sources.normal_L, 'normal_entry_counts.L');
  assert.equal(picked.values.ret_rebate_pct, 0.845);
  assert.equal(picked.values.mdd_raw_pct, 0.691);
  assert.equal(picked.values.mdd_rebate_exact_pct, 0.651661);
  assert.equal(picked.values.rescue_count, 12);
  assert.equal(picked.values.margin50_skips, 0);
  assert.equal(picked.values.held_events, 17);
  assert.equal(picked.values.old_adds_contracts, 0);
  assert.equal(Object.prototype.hasOwnProperty.call(picked.values, 'rescue_net_pnl'), false);
  assert.equal(Object.prototype.hasOwnProperty.call(picked.values, 'trapped_count'), false);
  assert.equal(picked.filters.TREND.map(function (p) { return p.key; }).join(','), 'placement_rejected,pending_cancelled,blocked_side_minutes');
  assert.equal(picked.totals[0].value, 4069);
  assert.equal(GL.phaseOf({ run_phase: 'REPLAY', progress: 13.2, frozen_report_available: false }).label, '재생 중');
  assert.equal(GL.phaseOf({ run_phase: 'LIVE', frozen_report_available: true }).label, '실시간 (동결 이후)');
  const html = GL.renderPanel({
    view: 'ready', selected: 'A',
    slots: [{
      id: 'A', name: 'A (앱 기본)', published: true, requestedFlags: FLAGS.A, flags: FLAGS.A, flagsDiffer: false,
      fetchStatus: { code: 'ok', label: '받음' },
      phase: GL.phaseOf({ run_phase: 'REPLAY', progress: 13.2 }),
      fresh: { text: '1분 미만 · 2026-11-08 06:15', stale: false },
      progress: 13.2,
      metrics: picked,
    }],
    downloads: null,
    report: { state: 'none' },
    manifest: {},
  });
  assert.match(html, /재생 중/);
  assert.match(html, /<th>환급 수익률 %<\/th>/);
  assert.match(html, /진입 거절 2292/);
  assert.match(html, /일반 진입 롱/);
  assert.equal(html.includes('구출 순손익'), false);
  assert.equal(html.includes('종료 시 갇힌 수'), false);
});

test('unverified baseline numbers are not rendered', function () {
  const parsed = GL.parseManifest(Object.assign(manifest({ data: true, entries: false, monthly: false, report: false }), {
    baseline: { verified: false, label: '0.9.152', metrics: { ret_rebate_pct: 12345.67, equity_rebate: 99999 } },
  }));
  const html = GL.renderPanel({
    view: 'ready', selected: 'A',
    slots: parsed.slots.map(function (slot) {
      return Object.assign({}, slot, {
        fetchStatus: { code: 'missing', label: '없음' },
        phase: { code: 'unknown', label: '상태 없음' },
        fresh: { text: '갱신 시각 없음', stale: false },
        metrics: null,
      });
    }),
    downloads: null,
    report: { state: 'none' },
    manifest: parsed.manifest,
  });
  assert.match(html, /verified가 true가 아니라/);
  assert.equal(html.includes('12345.67'), false);
  assert.equal(html.includes('99999'), false);
  assert.equal(html.includes('>검증됨<'), false);
});

test('not-ready and load failure do not look like results', function () {
  const loading = GL.renderPanel({ view: 'loading', selected: 'A' });
  const missing = GL.renderPanel({ view: 'not_ready', selected: 'A' });
  const bad = GL.renderPanel({ view: 'error', selected: 'B', errorMessage: 'HTTP 500' });
  assert.match(loading, /이 문구는 결과가 아닙니다/);
  assert.match(missing, /아직 게시되지 않음/);
  assert.match(missing, /숫자를 만들지 않고/);
  assert.match(bad, /결과를 표시하지 않습니다/);
  [loading, missing, bad].forEach(function (html) {
    assert.equal(html.includes('<a '), false);
    assert.match(html, /선택한 변형의 현재 수치가 없습니다/);
  });
});

test('unsafe paths and script names are not injected', function () {
  assert.equal(GL.safeRel('../data_y1/data.json'), null);
  assert.equal(GL.safeRel('https://evil.example/data.json'), null);
  assert.equal(GL.rawUrl('A/data.json'), GL.RAW_ROOT + 'A/data.json');
  const parsed = GL.parseManifest({
    version: '0.9.154',
    updated: '2026-11-08T06:15:21+09:00',
    variants: [variant('A', { data: true, entries: false, monthly: false, report: false }, { name: '<script>alert(1)</script>', data_path: 'A/../../data_latest/data.json' })],
  });
  assert.equal(parsed.slots[0].paths.data, null);
  const html = GL.renderPanel({
    view: 'ready', selected: 'A',
    slots: [Object.assign({}, parsed.slots[0], { fetchStatus: { code: 'error', label: '경로 오류' }, phase: { label: '상태 없음' }, fresh: { text: '갱신 시각 없음' } })],
    downloads: null, report: { state: 'none' }, manifest: parsed.manifest,
  });
  assert.equal(html.includes('<script>alert'), false);
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
});

test('data availability false does not count as a loaded variant', function () {
  const parsed = GL.parseManifest(manifest({ data: false, entries: false, monthly: false, report: false }));
  const status = GL.classifyVariant({ slot: parsed.slots[0], http: 200, data: { equity: 5, progress: 1 } });
  assert.equal(status.code, 'missing');
  assert.equal(status.label, '데이터 없음');
});

test('stale is explicit and replay progress is not treated as stale by age', function () {
  const fresh = GL.freshness('2026-11-08T06:15:21+09:00', Date.parse('2026-11-08T06:20:21+09:00'), false);
  assert.match(fresh.text, /5분 전/);
  assert.equal(fresh.stale, false);
  const wall = GL.freshness('2026-11-08 06:15', Date.parse('2026-11-08T06:16:00+09:00'), false);
  assert.equal(wall.stale, false);
  assert.match(wall.text, /1분 미만|1분 전/);
  const marked = GL.freshness('2026-11-08 06:15', Date.parse('2026-11-08T06:16:00+09:00'), true);
  assert.equal(marked.stale, true);
});

test('dashboard source keeps v1 and v2 on their branches and adds the 0.9.154 tab', function () {
  const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
  assert.match(html, /<button id="tb1" onclick="setV\(1\)">버전1 · 11\/2~<\/button>/);
  assert.match(html, /<button id="tb2" onclick="setV\(2\)">버전2 · 1년 백테스트<\/button>/);
  assert.match(html, /<button id="tb154" onclick="setV\(154\)">0\.9\.154<\/button>/);
  assert.equal(html.includes('버전3'), false);
  assert.match(html, /if\(V==154\)\{load154\(seq\);return;\}/);
  const fetchAt = html.indexOf("fetch(R+(V==2?'data_y1':'data_latest')+Q");
  const branchAt = html.indexOf('if(V==154){load154(seq);return;}');
  assert.ok(branchAt > 0 && fetchAt > branchAt);
  assert.match(html, /최신 소스만 적용/);
  assert.match(html, /버전2 · 1년 백테스트/);
});

test('published data_0154 manifest matches the nested availability contract', { timeout: 120000 }, async function () {
  const res = await fetch(GL.MANIFEST_URL + '?t=' + Date.now());
  assert.equal(res.status, 200);
  const body = await res.json();
  const parsed = GL.parseManifest(body);
  assert.equal(parsed.ok, true);
  assert.equal(body.version, '0.9.154');
  assert.equal(parsed.warnings.length, 0);
  assert.deepEqual(parsed.slots.map(function (s) { return s.id; }), ['A', 'B', 'C', 'D', 'E']);
  for (const slot of parsed.slots) {
    assert.equal(slot.available.present, true);
    assert.equal(typeof slot.available.data, 'boolean');
    assert.equal(slot.flagsDiffer, false);
    assert.ok(slot.paths.data);
    const dataRes = await fetch(GL.rawUrl(slot.paths.data) + '?t=' + Date.now());
    assert.equal(dataRes.status, slot.available.data ? 200 : 404);
    if (!slot.available.data) continue;
    const data = await dataRes.json();
    assert.equal(data.variant_id, slot.id);
    assert.equal(data.version, '0.9.154');
    assert.ok(data.engine);
    assert.ok(data.filter_counts && data.normal_entry_counts);
    const picked = GL.metricsOf(data);
    assert.equal(picked.values.normal_L, data.normal_entry_counts.L);
    assert.equal(picked.values.normal_S, data.normal_entry_counts.S);
    assert.equal(picked.filters.TREND[0].key, 'placement_rejected');
    assert.equal(Object.prototype.hasOwnProperty.call(picked.values, 'rescue_net_pnl'), Object.prototype.hasOwnProperty.call(data.rescue_stats || {}, 'net_pnl') || typeof data.rescue_net_pnl === 'number');
    const phase = GL.phaseOf(data);
    assert.ok(['replay', 'live', 'frozen', 'unknown'].includes(phase.code));
    const plan = GL.downloadPlan(slot, data);
    ['entries', 'monthly', 'report'].forEach(function (kind, i) {
      if (slot.available[kind] !== true) {
        assert.equal(plan[i].state, 'unavailable');
        assert.equal(plan[i].href, null);
      } else {
        assert.equal(plan[i].state, 'check');
        assert.ok(plan[i].href && plan[i].href.startsWith(GL.RAW_ROOT));
      }
    });
  }
});
