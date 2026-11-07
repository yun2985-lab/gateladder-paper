/* 0.9.154 dashboard adapter.
   Published contract (data_0154/data.json):
   {
     version: '0.9.154',
     updated: ISO-8601 with +09:00,
     start, cutoff, seed,
     variants: [{
       id, name,
       flags: {TREND,RSI,STRETCH,UNTIL_ZERO,SIDE_BLOCK},
       data_path, entries_path, monthly_path, report_path,
       availability: {data, entries, monthly, report}  // these booleans govern links
     }]
   }
   Flat entries_available / monthly_available / report_available are ignored.
   availability.* must be strictly true. False or missing does not become a download,
   even if a path or payload downloads.href is present.
   Variant data.json is the existing dashboard shape plus
   variant_id, flags, filter_counts, filter_totals, normal_entry_counts, downloads.
   filter_counts.TREND|RSI|STRETCH use placement_rejected, pending_cancelled, blocked_side_minutes.
   normal_entry_counts is {L,S}. downloads hrefs are used only when availability for that file is true.
   entries/monthly/report stay unavailable until the publisher marks them true after a verified final export.
   Price candles may be absent; the page says so instead of inventing bars.
   No numeric baseline is hardcoded. manifest.baseline is shown only when verified === true.
*/
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.GL154 = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const RAW_ROOT = 'https://raw.githubusercontent.com/yun2985-lab/gateladder-paper/data_0154/';
  const IDS = ['A', 'B', 'C', 'D', 'E'];
  const FLAG_KEYS = ['TREND', 'RSI', 'STRETCH', 'UNTIL_ZERO', 'SIDE_BLOCK'];
  const REQUESTED = {
    A: { name: 'A (앱 기본)', flags: { TREND: true, RSI: true, STRETCH: false, UNTIL_ZERO: false, SIDE_BLOCK: true } },
    B: { name: 'B', flags: { TREND: true, RSI: true, STRETCH: false, UNTIL_ZERO: false, SIDE_BLOCK: false } },
    C: { name: 'C', flags: { TREND: true, RSI: true, STRETCH: true, UNTIL_ZERO: false, SIDE_BLOCK: true } },
    D: { name: 'D', flags: { TREND: true, RSI: true, STRETCH: false, UNTIL_ZERO: true, SIDE_BLOCK: true } },
    E: { name: 'E', flags: { TREND: true, RSI: true, STRETCH: true, UNTIL_ZERO: false, SIDE_BLOCK: false } },
  };
  const METRIC_LABELS = {
    ret_rebate_pct: '환급 수익률 %',
    equity_rebate: '환급 자산',
    mdd_raw_pct: '원시 MDD %',
    mdd_rebate_exact_pct: '환급 MDD %',
    max_margin_usage_pct: '최대 증거금 %',
    normal_L: '일반 진입 롱',
    normal_S: '일반 진입 숏',
    rescue_count: '구출 횟수',
    rescue_net_pnl: '구출 순손익',
    rescue_max_h: '구출 최장 h',
    repayment_events: '상환 이벤트',
    repayment_contracts: '상환 계약',
    held_events: 'HELD 상환 이벤트',
    held_contracts: 'HELD 상환 계약',
    old_adds_events: 'OLD_ADDS 상환 이벤트',
    old_adds_contracts: 'OLD_ADDS 상환 계약',
    trapped_count: '종료 시 갇힌 수',
    trapped_unrealized: '종료 시 미실현',
    margin50_skips: '50% 건너뜀',
    margin50_skips_L: '50% 건너뜀 롱',
    margin50_skips_S: '50% 건너뜀 숏',
  };
  const FILTER_PARTS = [
    ['placement_rejected', '진입 거절'],
    ['pending_cancelled', '취소'],
    ['blocked_side_minutes', '분'],
    ['placement_attempts', '진입 시도'],
    ['blocks_L', '롱 차단'],
    ['blocks_S', '숏 차단'],
    ['cancels', '취소'],
    ['minutes', '분'],
    ['blocked', '차단'],
    ['count', '건수'],
  ];
  const TOTAL_PARTS = [
    ['placement_attempts', '진입 시도'],
    ['placement_rejected', '진입 거절'],
    ['pending_cancelled', '취소'],
    ['side_minutes', '분'],
  ];
  const COMMON_SPEC = [
    'A부터 E까지 같은 시드로 따로 재생합니다. 기준 엔진은 29, 0.9.152 입니다. 0.9.153이 아닙니다.',
    '구출 3%, 동시 20개, 간격 0.3%, 익절 +38.',
    '새 구출을 넣기 전 증거금 50% 관문.',
    '일반 방향 20%, MA 터치, 볼린저 없음, 반등 3%, 고정 3배, 환급 70%.',
    '필터는 일반 자동 진입에만 적용하고 구출에는 적용하지 않습니다.',
    'TREND: 완료된 4시간 SMA120보다 가격이 낮으면 롱을 막고, 높으면 숏을 막습니다.',
    'RSI: 완료된 1시간 RSI14가 75보다 크면 롱을 막고, 25보다 작으면 숏을 막습니다.',
    'STRETCH: 완료된 일봉 SMA50의 1.10배를 넘으면 롱을 막고, 0.90배보다 낮으면 숏을 막습니다.',
    'UNTIL_ZERO 켜짐(1): 0.9.153. 처음 잡은 물량이 없어도 그 방향 수익률이 0보다 낮으면 구출을 유지하고, 24시간이 지난 추가분을 갚습니다.',
    'UNTIL_ZERO 꺼짐(0): 0.9.152. 처음 잡은 물량이 없어지면 구출을 끝냅니다.',
    'SIDE_BLOCK 켜짐(1): 구출이 진행 중인 방향의 일반 진입을 막습니다.',
    'SIDE_BLOCK 꺼짐(0): 필터와 개수 제한 안에서 일반 진입을 허용합니다.',
    '시드 1000 USDT, 시작 2025-11-04 00:00 KST, 고정 종료 2026-11-07 23:54 KST.',
    '검증이 끝난 최종은 동결하고, 그 다음 자동으로 실시간을 이어 갑니다.',
    '비교용 숫자 기준선은 매니페스트에 baseline.verified가 true로 온 경우에만 씁니다. 0.9.152 실적을 화면에 넣어 두지 않았습니다.',
  ];

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function has(obj, key) {
    return !!obj && Object.prototype.hasOwnProperty.call(obj, key);
  }
  function safeRel(p) {
    if (typeof p !== 'string' || !p || p.length > 240) return null;
    if (p.includes('\\') || p.includes('..') || p.includes('://') || p.startsWith('/') || p.startsWith('//')) return null;
    if (!/^[A-Za-z0-9._/-]+$/.test(p)) return null;
    if (p.split('/').some(function (seg) { return seg === '' || seg === '.' || seg === '..'; })) return null;
    return p;
  }
  function rawUrl(rel) {
    const s = safeRel(rel);
    return s ? RAW_ROOT + s : null;
  }
  function isAllowedDownloadHref(href) {
    if (typeof href !== 'string' || !href.startsWith(RAW_ROOT)) return false;
    const rest = href.slice(RAW_ROOT.length).split('?')[0].split('#')[0];
    return safeRel(rest) === rest;
  }
  function tri(v) {
    if (v === true) return true;
    if (v === false) return false;
    return null;
  }
  function flagsEqual(a, b) {
    if (!a || !b) return false;
    return FLAG_KEYS.every(function (k) { return a[k] === b[k]; });
  }
  function normalizeFlags(f) {
    if (!f || typeof f !== 'object' || Array.isArray(f)) return null;
    const out = {};
    let any = false;
    FLAG_KEYS.forEach(function (k) {
      if (k in f) {
        out[k] = f[k] === true || f[k] === 1;
        if (f[k] === false || f[k] === 0) out[k] = false;
        any = true;
      } else out[k] = null;
    });
    return any ? out : null;
  }
  function flagBits(flags) {
    if (!flags) return '게시된 스위치 없음';
    return FLAG_KEYS.map(function (k) {
      const v = flags[k];
      return k + ' ' + (v === true ? '켜짐' : v === false ? '꺼짐' : '없음');
    }).join(' · ');
  }
  function readAvailability(published) {
    const none = { present: false, data: false, entries: false, monthly: false, report: false };
    const a = published && published.availability;
    if (!a || typeof a !== 'object' || Array.isArray(a)) return none;
    return {
      present: true,
      data: a.data === true,
      entries: a.entries === true,
      monthly: a.monthly === true,
      report: a.report === true,
    };
  }
  function normalizeVariant(id, published) {
    const req = REQUESTED[id];
    if (!published) {
      return {
        id: id, name: req.name, requestedFlags: req.flags, published: false, flags: null, flagsDiffer: null,
        paths: { data: null, entries: null, monthly: null, report: null },
        rawPaths: { data: null, entries: null, monthly: null, report: null },
        available: { present: false, data: false, entries: false, monthly: false, report: false }, stale: false, error: null,
      };
    }
    const flags = normalizeFlags(published.flags);
    return {
      id: id,
      name: typeof published.name === 'string' && published.name.trim() ? published.name : req.name,
      requestedFlags: req.flags,
      published: true,
      flags: flags,
      flagsDiffer: flags ? !flagsEqual(flags, req.flags) : null,
      paths: {
        data: safeRel(published.data_path),
        entries: safeRel(published.entries_path),
        monthly: safeRel(published.monthly_path),
        report: safeRel(published.report_path),
      },
      rawPaths: {
        data: published.data_path || null,
        entries: published.entries_path || null,
        monthly: published.monthly_path || null,
        report: published.report_path || null,
      },
      available: readAvailability(published),
      stale: published.stale === true || published.status === 'stale',
      error: typeof published.error === 'string' ? published.error : null,
    };
  }
  function parseManifest(body) {
    if (body == null || typeof body !== 'object' || Array.isArray(body)) {
      return { ok: false, code: 'shape', message: '매니페스트가 객체가 아닙니다.', warnings: [] };
    }
    const warnings = [];
    if (body.version !== '0.9.154') {
      warnings.push(body.version ? ('매니페스트 version이 0.9.154가 아닙니다: ' + String(body.version)) : '매니페스트에 version이 없습니다.');
    }
    if (!Array.isArray(body.variants)) {
      return { ok: false, code: 'variants', message: '매니페스트에 variants 배열이 없습니다.', warnings: warnings };
    }
    const seen = new Set();
    body.variants.forEach(function (v) {
      if (!v || typeof v !== 'object' || Array.isArray(v)) {
        warnings.push('variants 항목이 객체가 아닙니다.');
        return;
      }
      if (seen.has(v.id)) warnings.push('변형 ' + String(v.id) + ' 가 중복입니다. 첫 항목을 사용합니다.');
      seen.add(v.id);
    });
    const extra = body.variants.filter(function (v) { return v && typeof v === 'object' && !IDS.includes(v.id); }).map(function (v) { return String(v.id); });
    if (extra.length) warnings.push('알 수 없는 변형 id: ' + extra.join(', '));
    const slots = IDS.map(function (id) {
      const published = body.variants.find(function (v) { return v && v.id === id; });
      return normalizeVariant(id, published);
    });
    return {
      ok: true,
      manifest: body,
      slots: slots,
      warnings: warnings,
      updated: typeof body.updated === 'string' ? body.updated : null,
    };
  }
  function emptySlots() {
    return IDS.map(function (id) {
      const slot = normalizeVariant(id, null);
      slot.fetchStatus = { code: 'missing', label: '게시되지 않음' };
      slot.phase = { code: 'unknown', label: '상태 없음', frozen: false };
      slot.fresh = { text: '갱신 시각 없음', stale: false };
      slot.progress = null;
      return slot;
    });
  }
  function parseTime(s) {
    if (typeof s !== 'string' || !s.trim()) return null;
    if (s.indexOf('T') >= 0) {
      const t = Date.parse(s);
      return Number.isNaN(t) ? null : t;
    }
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$/);
    if (!m) return null;
    const t = Date.parse(m[1] + '-' + m[2] + '-' + m[3] + 'T' + m[4] + ':' + m[5] + ':' + (m[6] || '00') + '+09:00');
    return Number.isNaN(t) ? null : t;
  }
  function ageText(delta) {
    if (delta < -120000) return '갱신 시각이 미래입니다';
    if (delta < 0) delta = 0;
    const min = Math.floor(delta / 60000);
    if (min < 1) return '1분 미만';
    if (min < 60) return min + '분 전';
    const h = Math.floor(min / 60);
    if (h < 48) return h + '시간 전';
    return Math.floor(h / 24) + '일 전';
  }
  function freshness(updated, now, explicitStale) {
    const ms = parseTime(updated);
    let text;
    if (updated == null || updated === '') text = '갱신 시각 없음';
    else if (ms == null) text = '갱신 시각 형식 오류';
    else text = ageText((now == null ? Date.now() : now) - ms) + ' · ' + String(updated);
    return { text: text, stale: explicitStale === true, ms: ms };
  }
  function isFrozen(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
    if (data.run_phase === 'FROZEN') return true;
    return data.frozen_report_available === true;
  }
  function phaseOf(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) return { code: 'unknown', label: '상태 없음', frozen: false };
    const frozen = isFrozen(data);
    if (data.run_phase === 'LIVE') return { code: 'live', label: frozen ? '실시간 (동결 이후)' : '실시간', frozen: frozen };
    if (data.run_phase === 'FROZEN') return { code: 'frozen', label: '동결', frozen: true };
    if (data.run_phase === 'REPLAY') return { code: 'replay', label: '재생 중', frozen: frozen };
    if (data.replay_complete === true) return { code: 'live', label: frozen ? '실시간 (동결 이후)' : '실시간', frozen: frozen };
    if (data.progress != null && data.replay_complete !== true) return { code: 'replay', label: '재생 중', frozen: frozen };
    return { code: 'unknown', label: '상태 없음', frozen: frozen };
  }
  function classifyVariant(input) {
    const http = input && input.http;
    const data = input && input.data;
    const slot = input && input.slot;
    const error = input && input.error;
    if (!slot || slot.published === false) return { code: 'missing', label: '게시되지 않음' };
    if (!slot.available || slot.available.present !== true) return { code: 'missing', label: 'availability 없음' };
    if (slot.available.data !== true) return { code: 'missing', label: '데이터 없음' };
    if (!slot.paths || !slot.paths.data) {
      if (slot.rawPaths && slot.rawPaths.data) return { code: 'error', label: '경로 오류' };
      return { code: 'missing', label: 'data.json 경로 없음' };
    }
    if (error && (http == null || http === 0)) return { code: 'error', label: '불러오지 못함' };
    if (http === 404) return { code: 'missing', label: '없음' };
    if (http && http !== 200) return { code: 'error', label: '불러오지 못함' };
    if (data == null) return { code: 'missing', label: '없음' };
    if (typeof data !== 'object' || Array.isArray(data)) return { code: 'error', label: '형식 오류' };
    const stale = slot.stale === true || data.stale === true || data.status === 'stale';
    if (data.status === 'error') return { code: 'error', label: '오류', detail: typeof data.error === 'string' ? data.error : '' };
    if (typeof data.error === 'string' && data.error && data.equity == null && data.progress == null && data.candles == null) {
      return { code: 'error', label: '오류', detail: data.error };
    }
    if (stale) return { code: 'stale', label: '오래됨', detail: '' };
    return { code: 'ok', label: '받음' };
  }
  function take(values, sources, ignored, key, source, val) {
    if (has(values, key)) return;
    if (typeof val === 'number' && Number.isFinite(val)) {
      values[key] = val;
      sources[key] = source;
      return;
    }
    if (typeof val === 'string' && val.trim() !== '') ignored.push(source);
  }
  function filterParts(node) {
    if (typeof node === 'number' && Number.isFinite(node)) return [{ key: 'value', label: '제공된 값', value: node }];
    if (!node || typeof node !== 'object' || Array.isArray(node)) return [];
    const parts = [];
    FILTER_PARTS.forEach(function (pair) {
      if (typeof node[pair[0]] === 'number' && Number.isFinite(node[pair[0]])) parts.push({ key: pair[0], label: pair[1], value: node[pair[0]] });
    });
    return parts;
  }
  function filtersOf(data) {
    const src = (data && data.filter_counts) || (data && data.filters) || (data && data.summary && data.summary.filters);
    const out = {};
    if (!src || typeof src !== 'object' || Array.isArray(src)) return out;
    ['TREND', 'RSI', 'STRETCH'].forEach(function (name) {
      if (has(src, name)) {
        const parts = filterParts(src[name]);
        if (parts.length) out[name] = parts;
      }
    });
    return out;
  }
  function filterTotalsOf(data) {
    const t = data && data.filter_totals;
    if (!t || typeof t !== 'object' || Array.isArray(t)) return [];
    const out = [];
    TOTAL_PARTS.forEach(function (pair) {
      if (typeof t[pair[0]] === 'number' && Number.isFinite(t[pair[0]])) out.push({ key: pair[0], label: pair[1], value: t[pair[0]] });
    });
    return out;
  }
  function metricsOf(data) {
    const values = {};
    const sources = {};
    const ignoredStrings = [];
    const empty = { values: values, sources: sources, filters: {}, totals: [], ignoredStrings: ignoredStrings, monthly: null };
    if (!data || typeof data !== 'object' || Array.isArray(data)) return empty;
    take(values, sources, ignoredStrings, 'ret_rebate_pct', 'ret_rebate_pct', data.ret_rebate_pct);
    take(values, sources, ignoredStrings, 'equity_rebate', 'equity_rebate', data.equity_rebate);
    if (!has(values, 'equity_rebate')) take(values, sources, ignoredStrings, 'equity_rebate', 'equity', data.equity);
    take(values, sources, ignoredStrings, 'mdd_raw_pct', 'mdd_raw_pct', data.mdd_raw_pct);
    if (!has(values, 'mdd_raw_pct')) take(values, sources, ignoredStrings, 'mdd_raw_pct', 'mdd_pct', data.mdd_pct);
    take(values, sources, ignoredStrings, 'mdd_rebate_exact_pct', 'mdd_rebate_exact_pct', data.mdd_rebate_exact_pct);
    take(values, sources, ignoredStrings, 'max_margin_usage_pct', 'max_margin_usage_pct', data.max_margin_usage_pct);
    const nec = data.normal_entry_counts;
    if (nec && typeof nec === 'object') {
      take(values, sources, ignoredStrings, 'normal_L', 'normal_entry_counts.L', nec.L);
      take(values, sources, ignoredStrings, 'normal_S', 'normal_entry_counts.S', nec.S);
    }
    const entrySrc = data.entries_normal || data.normal_entries || (data.summary && data.summary.entries);
    if (entrySrc && typeof entrySrc === 'object') {
      take(values, sources, ignoredStrings, 'normal_L', 'normal_L', entrySrc.normal_L != null ? entrySrc.normal_L : entrySrc.L);
      take(values, sources, ignoredStrings, 'normal_S', 'normal_S', entrySrc.normal_S != null ? entrySrc.normal_S : entrySrc.S);
    }
    take(values, sources, ignoredStrings, 'normal_L', 'normal_L', data.normal_L);
    take(values, sources, ignoredStrings, 'normal_S', 'normal_S', data.normal_S);
    const rs = data.rescue_stats && typeof data.rescue_stats === 'object' ? data.rescue_stats : {};
    take(values, sources, ignoredStrings, 'rescue_count', 'rescue_stats.count', rs.count);
    take(values, sources, ignoredStrings, 'rescue_max_h', 'rescue_stats.max_h', rs.max_h);
    take(values, sources, ignoredStrings, 'rescue_net_pnl', 'rescue_stats.net_pnl', rs.net_pnl);
    const sr = data.summary && data.summary.rescue;
    if (sr && typeof sr === 'object') {
      take(values, sources, ignoredStrings, 'rescue_count', 'summary.rescue.count', sr.count);
      take(values, sources, ignoredStrings, 'rescue_net_pnl', 'summary.rescue.net_pnl', sr.net_pnl);
      take(values, sources, ignoredStrings, 'rescue_max_h', 'summary.rescue.longest_h', sr.longest_h != null ? sr.longest_h : sr.max_h);
    }
    take(values, sources, ignoredStrings, 'rescue_net_pnl', 'rescue_net_pnl', data.rescue_net_pnl);
    let split = null;
    let splitName = null;
    if (data.repayment_by_target153 && typeof data.repayment_by_target153 === 'object') {
      split = data.repayment_by_target153;
      splitName = 'repayment_by_target153';
    } else if (data.repayment_by_target && typeof data.repayment_by_target === 'object') {
      split = data.repayment_by_target;
      splitName = 'repayment_by_target';
    } else if (data.summary && data.summary.repayment && typeof data.summary.repayment === 'object') {
      split = data.summary.repayment;
      splitName = 'summary.repayment';
    }
    if (split && splitName) {
      const held = split.HELD || split.held;
      const olds = split.OLD_ADDS || split.old_adds;
      if (held && typeof held === 'object') {
        take(values, sources, ignoredStrings, 'held_events', splitName + '.HELD.events', held.events);
        take(values, sources, ignoredStrings, 'held_contracts', splitName + '.HELD.contracts', held.contracts);
      }
      if (olds && typeof olds === 'object') {
        take(values, sources, ignoredStrings, 'old_adds_events', splitName + '.OLD_ADDS.events', olds.events);
        take(values, sources, ignoredStrings, 'old_adds_contracts', splitName + '.OLD_ADDS.contracts', olds.contracts);
      }
    }
    take(values, sources, ignoredStrings, 'repayment_events', 'repayment_events152', data.repayment_events152);
    take(values, sources, ignoredStrings, 'repayment_contracts', 'repayment_contracts152', data.repayment_contracts152);
    take(values, sources, ignoredStrings, 'repayment_events', 'repayment_events', data.repayment_events);
    take(values, sources, ignoredStrings, 'repayment_contracts', 'repayment_contracts', data.repayment_contracts);
    const trapped = data.trapped || (data.summary && data.summary.trapped);
    const trappedName = data.trapped ? 'trapped' : 'summary.trapped';
    if (trapped && typeof trapped === 'object') {
      take(values, sources, ignoredStrings, 'trapped_count', trappedName + '.count', trapped.count != null ? trapped.count : trapped.end_count);
      take(values, sources, ignoredStrings, 'trapped_unrealized', trappedName + '.unrealized', trapped.unrealized != null ? trapped.unrealized : trapped.end_unrealized);
    }
    take(values, sources, ignoredStrings, 'trapped_count', 'trapped_count', data.trapped_count);
    take(values, sources, ignoredStrings, 'trapped_unrealized', 'trapped_unrealized', data.trapped_unrealized);
    take(values, sources, ignoredStrings, 'margin50_skips', 'margin50_skips', data.margin50_skips);
    if (data.margin50_skips_by_side && typeof data.margin50_skips_by_side === 'object') {
      take(values, sources, ignoredStrings, 'margin50_skips_L', 'margin50_skips_by_side.L', data.margin50_skips_by_side.L);
      take(values, sources, ignoredStrings, 'margin50_skips_S', 'margin50_skips_by_side.S', data.margin50_skips_by_side.S);
    }
    if (data.summary && typeof data.summary.margin50_skips === 'number') {
      take(values, sources, ignoredStrings, 'margin50_skips', 'summary.margin50_skips', data.summary.margin50_skips);
    }
    return {
      values: values,
      sources: sources,
      filters: filtersOf(data),
      totals: filterTotalsOf(data),
      ignoredStrings: ignoredStrings,
      monthly: Array.isArray(data.monthly) ? data.monthly : null,
    };
  }
  function metricsFromReport(body) {
    if (!body || typeof body !== 'object' || Array.isArray(body)) return metricsOf(null);
    const base = metricsOf(body);
    function fill(extra, prefix) {
      if (!extra) return;
      Object.keys(extra.values).forEach(function (k) {
        if (!has(base.values, k)) {
          base.values[k] = extra.values[k];
          base.sources[k] = prefix + extra.sources[k];
        }
      });
      ['TREND', 'RSI', 'STRETCH'].forEach(function (name) {
        if (!base.filters[name] && extra.filters[name]) base.filters[name] = extra.filters[name];
      });
      if (!base.monthly && extra.monthly) base.monthly = extra.monthly;
      if ((!base.totals || !base.totals.length) && extra.totals && extra.totals.length) base.totals = extra.totals;
    }
    if (body.summary && typeof body.summary === 'object') fill(metricsOf(body.summary), 'summary.');
    if (body.metrics && typeof body.metrics === 'object') fill(metricsOf(body.metrics), 'metrics.');
    return base;
  }
  function baselineView(manifest) {
    if (!manifest || typeof manifest !== 'object' || !('baseline' in manifest) || manifest.baseline == null) return { row: null, note: '' };
    const b = manifest.baseline;
    if (typeof b !== 'object' || Array.isArray(b) || b.verified !== true || !b.metrics || typeof b.metrics !== 'object' || Array.isArray(b.metrics)) {
      return { row: null, note: '기준선이 매니페스트에 있으나 verified가 true가 아니라 숫자는 표시하지 않습니다.' };
    }
    const picked = metricsOf(b.metrics);
    const any = Object.keys(picked.values).length || Object.keys(picked.filters).length;
    if (!any) return { row: null, note: '검증된 기준선이나 읽을 수 있는 숫자가 없습니다.' };
    const label = typeof b.label === 'string' && b.label.trim() ? b.label : '기준선';
    return { row: { label: label, metrics: picked }, note: '' };
  }
  function explicitHref(downloads, kind) {
    if (!downloads || typeof downloads !== 'object' || Array.isArray(downloads)) return null;
    const node = downloads[kind];
    let raw = null;
    if (typeof node === 'string') raw = node;
    else if (node && typeof node === 'object' && node.available !== false) raw = node.href || node.url || node.path || null;
    if (typeof raw !== 'string' || !raw) return null;
    if (raw.indexOf('?') >= 0) raw = raw.split('?')[0];
    if (raw.indexOf(RAW_ROOT) === 0) {
      const rest = raw.slice(RAW_ROOT.length).split('#')[0];
      return safeRel(rest) ? RAW_ROOT + rest : null;
    }
    const rel = safeRel(raw);
    return rel ? RAW_ROOT + rel : null;
  }
  function downloadPlan(slot, data) {
    const frozen = isFrozen(data);
    const kinds = [['entries', '진입 CSV'], ['monthly', '월별 CSV'], ['report', '보고서 JSON']];
    const avail = slot && slot.available;
    return kinds.map(function (pair) {
      const kind = pair[0];
      const label = pair[1];
      const opened = !!(avail && avail.present === true && avail[kind] === true);
      const href = opened ? (explicitHref(data && data.downloads, kind) || (slot.paths && slot.paths[kind] ? rawUrl(slot.paths[kind]) : null)) : null;
      let state = 'unavailable';
      let finalMode = 'unknown';
      if (!opened) state = 'unavailable';
      else if (!href) state = 'bad_path';
      else {
        state = 'check';
        finalMode = frozen ? 'frozen' : 'unmarked';
      }
      return { kind: kind, label: label, path: slot && slot.paths ? slot.paths[kind] : null, href: href, flag: opened, state: state, finalMode: finalMode };
    });
  }
  function finalizeDownload(item, probed) {
    const base = { kind: item.kind, label: item.label, flag: item.flag, finalMode: item.finalMode, href: null };
    if (item.state === 'bad_path') return Object.assign({}, base, { view: 'bad_path' });
    if (item.state === 'absent' || item.state === 'unavailable') return Object.assign({}, base, { view: 'unavailable' });
    if (item.state === 'check') {
      if (probed === true) return Object.assign({}, base, { view: 'link', href: item.href || null });
      if (probed === false) return Object.assign({}, base, { view: 'broken' });
      return Object.assign({}, base, { view: 'checking' });
    }
    if (item.state === 'probe') {
      if (probed === true) return Object.assign({}, base, { view: 'link' });
      return Object.assign({}, base, { view: 'unavailable' });
    }
    return Object.assign({}, base, { view: 'unavailable' });
  }
  function linkSuffix(mode) {
    if (mode === 'frozen') return '동결';
    if (mode === 'partial') return '진행 중 · 최종 아님';
    if (mode === 'unmarked') return '열림 · 페이로드는 동결이 아님';
    return '동결 여부 없음';
  }
  function metricKeys(pickedList) {
    return Object.keys(METRIC_LABELS).filter(function (k) {
      return pickedList.some(function (p) { return p && has(p.values, k); });
    });
  }
  function filterNames(pickedList) {
    return ['TREND', 'RSI', 'STRETCH'].filter(function (n) {
      return pickedList.some(function (p) { return p && p.filters && p.filters[n]; });
    });
  }
  function fmt(v) {
    return typeof v === 'number' && Number.isFinite(v) ? String(v) : '없음';
  }
  function filterCell(parts) {
    if (!parts || !parts.length) return '없음';
    return parts.map(function (p) { return p.label + ' ' + p.value; }).join(' · ');
  }
  function renderMetrics(picked) {
    if (!picked) return '<small>없음</small>';
    const keys = Object.keys(METRIC_LABELS).filter(function (k) { return has(picked.values, k); });
    const filterHtml = ['TREND', 'RSI', 'STRETCH'].filter(function (n) { return picked.filters && picked.filters[n]; }).map(function (n) {
      return '<div class="c">' + esc(n) + '<b style="font-size:14px">' + esc(filterCell(picked.filters[n])) + '</b></div>';
    }).join('');
    const totals = picked.totals || [];
    const totalsHtml = totals.length ? '<div class="c">필터 합계<b style="font-size:14px">' + esc(totals.map(function (t) { return t.label + ' ' + t.value; }).join(' · ')) + '</b></div>' : '';
    if (!keys.length && !filterHtml && !totalsHtml && !(picked.monthly && picked.monthly.length)) return '<small>이 페이로드에서 읽을 수 있는 실험 지표가 없습니다.</small>';
    const cards = keys.map(function (k) {
      return '<div class="c" title="' + esc(picked.sources[k]) + '">' + esc(METRIC_LABELS[k]) + '<b>' + esc(picked.values[k]) + '</b></div>';
    }).join('');
    let monthly = '';
    if (picked.monthly && picked.monthly.length) {
      const rows = picked.monthly.map(function (row) {
        return '<tr>' + ['month', 'start', 'end', 'pnl_pct', 'pnl_usdt', 'trades', 'wins'].map(function (k) {
          return '<td>' + (row && row[k] != null ? esc(row[k]) : '') + '</td>';
        }).join('') + '</tr>';
      }).join('');
      monthly = '<h3>월별 (현재 페이로드)</h3><table><tr><th>월</th><th>시작</th><th>종료</th><th>손익 %</th><th>손익</th><th>거래</th><th>승</th></tr>' + rows + '</table>';
    }
    const warn = picked.ignoredStrings && picked.ignoredStrings.length
      ? '<p class="warn"><small>숫자로 오지 않아 뺀 항목: ' + esc(picked.ignoredStrings.join(', ')) + '</small></p>'
      : '';
    return '<div class="k">' + cards + filterHtml + totalsHtml + '</div>' + warn + monthly;
  }
  function renderDownloads(downloads) {
    if (!downloads) return '<div class="box" data-region="downloads"><h3>파일</h3><p><small>파일 확인 전입니다. 링크를 만들지 않습니다.</small></p></div>';
    const bits = downloads.map(function (d) {
      if (d.view === 'link') {
        if (!isAllowedDownloadHref(d.href)) return '<span>' + esc(d.label) + ': 경로를 사용할 수 없음</span>';
        return '<a href="' + esc(d.href) + '" target="_blank" rel="noopener">' + esc(d.label) + ' (' + esc(linkSuffix(d.finalMode)) + ')</a>';
      }
      if (d.view === 'broken') return '<span>' + esc(d.label) + ': 파일을 확인하지 못함</span>';
      if (d.view === 'bad_path') return '<span>' + esc(d.label) + ': 경로를 사용할 수 없음</span>';
      if (d.view === 'checking') return '<span>' + esc(d.label) + ': 확인 중</span>';
      return '<span>' + esc(d.label) + ': 없음</span>';
    }).join('<br>');
    return '<div class="box" data-region="downloads"><h3>파일</h3><p>' + bits + '</p><small>받는 링크는 매니페스트 availability가 true인 파일만 만듭니다. entries, monthly, report가 false이면 최종 동결본이 아직 없는 것입니다. 평탄한 entries_available 값은 쓰지 않습니다. 진입 CSV는 초기 번호마다 한 줄이고 구출 추가분(cyc)을 포함해야 하며, 화면의 최근 거래 표가 그 파일을 대신하지 않습니다.</small></div>';
  }
  function renderReport(report) {
    if (!report || report.state === 'none') {
      return '<div class="box" data-region="frozen"><h3>동결 보고서</h3><p>동결 보고서가 아직 없습니다.</p></div>';
    }
    if (report.state === 'broken') {
      return '<div class="box" data-region="frozen"><h3>동결 보고서</h3><p class="warn">보고서를 불러오지 못했습니다.</p></div>';
    }
    const title = report.state === 'frozen' ? '동결 보고서' : '보고서 파일 (최종 동결로 표시되지 않음)';
    const note = report.state === 'frozen'
      ? '이 숫자는 report.json에서 읽었습니다. 아래 차트는 현재 data.json입니다.'
      : '파일은 있지만 페이로드가 최종 동결이라고 하지 않습니다. 아래 차트와 섞지 않습니다.';
    return '<div class="box" data-region="frozen"><h3>' + title + '</h3><p><small>' + note + '</small></p>' + renderMetrics(report.picked) + '</div>';
  }
  function renderPanel(model) {
    model = model || {};
    const sel = IDS.includes(model.selected) ? model.selected : 'A';
    const view = model.view || 'loading';
    let status;
    if (view === 'loading') status = '<p data-region="status" class="warn">매니페스트를 불러오는 중입니다. 이 문구는 결과가 아닙니다.</p>';
    else if (view === 'not_ready') status = '<p data-region="status" class="warn">아직 게시되지 않음. data_0154/data.json 이 없습니다. 숫자를 만들지 않고 60초마다 다시 확인합니다.</p>';
    else if (view === 'error') status = '<p data-region="status" class="warn">매니페스트를 불러오지 못했습니다. ' + esc(model.errorMessage || '') + ' 결과를 표시하지 않습니다.</p>';
    else {
      const fresh = model.manifestFresh && model.manifestFresh.text ? model.manifestFresh.text : '갱신 시각 없음';
      status = '<p data-region="status">매니페스트를 받았습니다.' + (model.manifestUpdated ? (' 갱신 ' + esc(model.manifestUpdated) + ' · ' + esc(fresh)) : ' 갱신 시각 없음') + '</p>';
    }
    const warnings = (model.warnings || []).map(function (w) { return '<li>' + esc(w) + '</li>'; }).join('');
    const buttons = IDS.map(function (id) {
      return '<button type="button" data-sel="' + id + '"' + (id === sel ? ' class="on"' : '') + '>' + id + '</button>';
    }).join('');
    const spec = '<ul>' + COMMON_SPEC.map(function (line) { return '<li>' + esc(line) + '</li>'; }).join('') + '</ul>';
    const reqRows = IDS.map(function (id) {
      const f = REQUESTED[id].flags;
      return '<tr><td>' + esc(REQUESTED[id].name) + '</td>' + FLAG_KEYS.map(function (k) {
        return '<td>' + (f[k] ? '켜짐' : '꺼짐') + '</td>';
      }).join('') + '</tr>';
    }).join('');
    const slots = model.slots && model.slots.length ? model.slots : emptySlots();
    const cards = slots.map(function (slot) {
      const st = slot.fetchStatus || { code: 'missing', label: '게시되지 않음' };
      const phase = slot.phase || { label: '상태 없음' };
      const fresh = slot.fresh || { text: '갱신 시각 없음', stale: false };
      const prog = typeof slot.progress === 'number' ? ('진행 ' + slot.progress + '%') : '진행률 없음';
      const last = slot.lastBar ? (' · 현재 봉 ' + esc(slot.lastBar)) : '';
      const differ = slot.flagsDiffer ? '<div class="warn">게시된 스위치가 요청 구성과 다릅니다.</div>' : '';
      const stale = st.code === 'stale' || fresh.stale ? '<div class="warn">오래됨</div>' : '';
      const detail = slot.errorDetail ? '<div class="warn">' + esc(slot.errorDetail) + '</div>' : '';
      return '<div class="c" data-variant="' + esc(slot.id) + '"><b>' + esc(slot.name || slot.id) + '</b>'
        + '<div>' + esc(st.label) + '</div><div>' + esc(phase.label) + '</div><div>' + prog + last + '</div>'
        + '<div>' + esc(fresh.text) + '</div>' + stale + detail + differ
        + '<div><small>요청 ' + esc(flagBits(slot.requestedFlags)) + '</small></div>'
        + '<div><small>게시 ' + esc(flagBits(slot.flags)) + '</small></div></div>';
    }).join('');
    const selected = slots.find(function (s) { return s.id === sel; }) || slots[0];
    const selectedStatus = selected && selected.fetchStatus ? selected.fetchStatus.code : 'missing';
    let selectedHtml;
    if (view === 'loading' || view === 'not_ready' || view === 'error') {
      selectedHtml = '<div class="box" data-region="selected"><h3>선택 ' + esc(sel) + '</h3><p>선택한 변형의 현재 수치가 없습니다.</p></div>';
    } else if (!selected || selected.published === false || selectedStatus === 'missing') {
      selectedHtml = '<div class="box" data-region="selected"><h3>선택 ' + esc(selected ? selected.name : sel) + '</h3><p class="warn">선택한 변형의 data.json이 없습니다.</p></div>';
    } else if (selectedStatus === 'error') {
      selectedHtml = '<div class="box" data-region="selected"><h3>선택 ' + esc(selected.name) + '</h3><p class="warn">' + esc(selected.fetchStatus.label) + (selected.errorDetail ? (': ' + esc(selected.errorDetail)) : '') + '</p></div>';
    } else {
      const phase = selected.phase || { code: 'unknown', label: '상태 없음', frozen: false };
      let note = '아래 차트와 표는 선택한 변형의 현재 data.json입니다.';
      if (phase.code === 'replay') note += ' 재생이 끝나기 전입니다.';
      if (phase.code === 'live' && phase.frozen) note += ' 차트는 실시간 페이로드이고, 동결 파일은 확정본입니다.';
      if (phase.code === 'frozen') note += ' 동결 상태입니다.';
      if (selectedStatus === 'stale') note += ' 갱신이 오래됨으로 표시되어 있습니다.';
      const meta = [selected.engine, selected.version, selected.start && selected.end ? (selected.start + ' ~ ' + selected.end) : ''].filter(Boolean).join(' · ');
      selectedHtml = '<div class="box" data-region="selected"><h3>선택 ' + esc(selected.name) + '</h3><p><small>' + esc(note) + '</small></p>'
        + (meta ? ('<p><small>' + esc(meta) + '</small></p>') : '')
        + '<p>' + esc(phase.label) + ' · ' + (typeof selected.progress === 'number' ? ('진행 ' + selected.progress + '%') : '진행률 없음') + '</p>'
        + renderMetrics(selected.metrics) + '</div>';
    }
    let compare = view === 'ready'
      ? '<div class="box" data-region="compare"><h3>변형 비교</h3><p>비교할 수치가 아직 없습니다.</p></div>'
      : '<div class="box" data-region="compare"><h3>변형 비교</h3><p>비교는 변형 데이터를 받은 뒤에 표시합니다.</p></div>';
    if (view === 'ready') {
      const baseline = baselineView(model.manifest);
      const picked = slots.map(function (slot) {
        const code = slot.fetchStatus && slot.fetchStatus.code;
        if (code !== 'ok' && code !== 'stale') return null;
        return slot.metrics || null;
      });
      if (baseline.row) picked.push(baseline.row.metrics);
      const keys = metricKeys(picked);
      const fnames = filterNames(picked);
      if (!keys.length && !fnames.length) {
        compare = '<div class="box" data-region="compare"><h3>변형 비교</h3><p>비교할 수치가 아직 없습니다.</p>' + (baseline.note ? ('<p class="warn">' + esc(baseline.note) + '</p>') : '') + '</div>';
      } else {
        const head = '<tr><th>변형</th><th>상태</th><th>단계</th><th>진행</th><th>갱신</th>'
          + keys.map(function (k) { return '<th>' + esc(METRIC_LABELS[k]) + '</th>'; }).join('')
          + fnames.map(function (n) { return '<th>' + esc(n) + '</th>'; }).join('') + '</tr>';
        const body = slots.map(function (slot) {
          const code = slot.fetchStatus && slot.fetchStatus.code;
          const use = code === 'ok' || code === 'stale';
          const m = use ? slot.metrics : null;
          return '<tr><td>' + esc(slot.name || slot.id) + '</td><td>' + esc((slot.fetchStatus && slot.fetchStatus.label) || '') + '</td><td>' + esc((slot.phase && slot.phase.label) || '') + '</td><td>' + (typeof slot.progress === 'number' && use ? esc(slot.progress) : '없음') + '</td><td>' + esc((slot.fresh && slot.fresh.text) || '') + '</td>'
            + keys.map(function (k) { return '<td>' + (m && has(m.values, k) ? esc(m.values[k]) : '없음') + '</td>'; }).join('')
            + fnames.map(function (n) { return '<td>' + esc(m && m.filters && m.filters[n] ? filterCell(m.filters[n]) : '없음') + '</td>'; }).join('')
            + '</tr>';
        }).join('');
        const baseRow = baseline.row ? ('<tr><td>' + esc(baseline.row.label) + '</td><td>검증됨</td><td></td><td></td><td></td>'
          + keys.map(function (k) { return '<td>' + (has(baseline.row.metrics.values, k) ? esc(baseline.row.metrics.values[k]) : '없음') + '</td>'; }).join('')
          + fnames.map(function (n) { return '<td>' + esc(baseline.row.metrics.filters && baseline.row.metrics.filters[n] ? filterCell(baseline.row.metrics.filters[n]) : '없음') + '</td>'; }).join('')
          + '</tr>') : '';
        compare = '<div class="box" data-region="compare"><h3>변형 비교</h3>' + (baseline.note ? ('<p class="warn">' + esc(baseline.note) + '</p>') : '') + '<table>' + head + baseRow + body + '</table></div>';
      }
    }
    return '<div class="box"><h3>0.9.154 · 다섯 개 독립 1년 백테스트</h3>' + status
      + (warnings ? ('<ul class="warn">' + warnings + '</ul>') : '')
      + '<div data-region="selector" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px">' + buttons + '</div></div>'
      + '<div class="box" data-region="config"><h3>요청된 스위치 구성</h3>' + spec
      + '<table><tr><th>변형</th><th>TREND</th><th>RSI</th><th>STRETCH</th><th>UNTIL_ZERO</th><th>SIDE_BLOCK</th></tr>' + reqRows + '</table></div>'
      + '<div class="box" data-region="variants"><h3>변형별 진행 · 상태 · 갱신</h3><div class="k">' + cards + '</div></div>'
      + compare + selectedHtml + renderDownloads(model.downloads) + renderReport(model.report) + '<div id="dashErr"></div>';
  }

  return {
    RAW_ROOT: RAW_ROOT,
    MANIFEST_URL: RAW_ROOT + 'data.json',
    IDS: IDS,
    FLAG_KEYS: FLAG_KEYS,
    REQUESTED: REQUESTED,
    METRIC_LABELS: METRIC_LABELS,
    COMMON_SPEC: COMMON_SPEC,
    safeRel: safeRel,
    rawUrl: rawUrl,
    isAllowedDownloadHref: isAllowedDownloadHref,
    parseManifest: parseManifest,
    emptySlots: emptySlots,
    normalizeFlags: normalizeFlags,
    flagBits: flagBits,
    parseTime: parseTime,
    freshness: freshness,
    isFrozen: isFrozen,
    phaseOf: phaseOf,
    classifyVariant: classifyVariant,
    metricsOf: metricsOf,
    metricsFromReport: metricsFromReport,
    baselineView: baselineView,
    downloadPlan: downloadPlan,
    finalizeDownload: finalizeDownload,
    renderPanel: renderPanel,
    esc: esc,
    fmt: fmt,
  };
});
