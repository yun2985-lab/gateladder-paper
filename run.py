#!/usr/bin/env python3
"""GateLadder paper backtest - one run per call (portable, Windows/macOS/Linux).

    python run.py --config configs/W4_Y2025.json --out results/W4_Y2025

Replays historical BTCUSDT USDT-M 1-minute bars through the exact GateLadder paper
engine (engine4 ... engine173) with the same loop as the original Linux runners
(warm-up, 2500-bar chunks, same per-chunk audit flushes), then writes
report.json / summary.json / trades.csv / entries.csv / monthly.csv / equity.csv /
equity_minutes.csv / events.log / repayments.csv / open_positions_end.csv / run_meta.json.

Prints one progress line per chunk:
    PROGRESS 47.6% bar 2025-04-26 14:40 KST eq_raw 981.18 eq_rebate 1012.40 mdd_raw 5.16% elapsed 812s
Exit code 0 = finished, 2 = config/data error, 1 = engine error.
Paper/simulation only: no network access, no exchange keys, no live trading.
"""
import argparse
import csv
import hashlib
import importlib
import json
import os
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'engine'))
sys.path.insert(0, str(ROOT))

from gl import kst  # noqa: E402
from gl import data as gdata  # noqa: E402

CHUNK = 2500  # identical to the original runners (affects audit flush points only)
PARAM_GROUPS = ('settings155', 'rescue_params158', 'params159', 'params162', 'params162m', 'params167',
                'params169', 'params170', 'params171', 'params172', 'params173')
TRADE_COLS = ['t_in', 't', 'id', 'strat', 'side', 'entry', 'exit', 'qty', 'pnl', 'pnl_rebate', 'pnl_pct_margin',
              'pnl_pct_equity', 'result', 'why', 'info']


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def resolve(p, cfg_dir):
    p = Path(p)
    if p.is_absolute():
        return p
    for base in (ROOT, cfg_dir):
        if (base / p).exists():
            return (base / p).resolve()
    return (ROOT / p).resolve()


def period(cfg):
    if 'start_ms' in cfg:
        start = int(cfg['start_ms'])
    else:
        start = kst.parse(cfg['start_kst'])
    if 'end_ms' in cfg:
        end = int(cfg['end_ms'])
    else:
        s = cfg['end_kst'].strip()
        end = kst.parse(s)
        if len(s) == 10:  # date only = whole day inclusive
            end += 86400000
    if start % 60000 or end % 60000 or end <= start:
        raise ValueError('start/end must be whole minutes and end > start')
    return start, end


def peak_rss_mb():
    try:
        import resource
        r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(r / 1024 / (1024 if sys.platform == 'darwin' else 1), 1)
    except Exception:
        pass
    try:  # Windows
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t),
                        ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t),
                        ('PeakPagefileUsage', ctypes.c_size_t)]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return round(c.PeakWorkingSetSize / 1048576, 1)
    except Exception:
        return None


def pnl_basic(e, px):
    """L/S x normal/rescue PnL for engines without rules169 (B6 = Engine167)."""
    out = {}
    for sd in ('L', 'S'):
        for k in ('normal', 'rescue'):
            cat = (lambda s: s == 'cyc') if k == 'rescue' else (lambda s: s != 'cyc')
            trs = [t for t in e.trades if t['side'] == sd and cat(t['strat'])]
            ps = [p for p in e.pos if ('L' if p['buy'] else 'S') == sd and cat(p['strat'])]
            out[sd + '_' + k] = dict(closed_records=len(trs), realized_pnl_raw=round(sum(t['pnl'] for t in trs), 6),
                                     realized_pnl_rebate70=round(sum(t['pnl_rebate'] for t in trs), 6), open_count=len(ps),
                                     open_contracts=sum(p['n'] for p in ps),
                                     open_unrealized_gross=round(sum((px - p['entry']) * p['qty'] * (1 if p['buy'] else -1) for p in ps), 6))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--no-entries', action='store_true', help='skip entries.csv export (saves ~1-3 min)')
    ap.add_argument('--audit', action='store_true', help='also write large per-minute audit logs (gate/rescue/candidate, ~150MB)')
    ap.add_argument('--progress-every', type=int, default=1, help='print a PROGRESS line every N chunks of 2500 bars')
    ap.add_argument('--force', action='store_true', help='allow writing into a non-empty --out directory')
    a = ap.parse_args(argv)

    cfg_path = Path(a.config).resolve()
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    out = Path(a.out).resolve()
    if out.exists() and any(out.iterdir()) and not a.force:
        print('ERROR output directory not empty: %s (use --force)' % out, flush=True)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    t_wall0 = time.time()
    try:
        START, END = period(cfg)
        files = [resolve(p, cfg_path.parent) for p in cfg.get('minute_files', ['data/btcusdt_1m_master.npz'])]
        for p in files:
            if not p.exists():
                raise FileNotFoundError('minute file missing: %s (see data/README / fetch_data.py)' % p)
        print('PREPARE data %s period %s ~ %s KST (end exclusive)' % ([p.name for p in files], kst.fmt(START), kst.fmt(END)), flush=True)
        P = gdata.prepare(files, START, END)
    except (ValueError, KeyError, FileNotFoundError, gdata.DataCoverageError) as ex:
        print('ERROR ' + str(ex), flush=True)
        return 2

    # --- engine import (same order as the original runners: engine4, engine5, then the module)
    import engine4  # noqa: F401
    import engine5
    from engine5 import load_edits
    kst.install_engine_time_shim()
    from gl.report import build_report, summary_row
    M = importlib.import_module(cfg['engine_module'])
    from gl.overrides import apply as apply_overrides
    try:
        overrides_applied = apply_overrides(cfg.get('strategy_overrides'))
    except (ValueError, TypeError) as ex:
        print('ERROR strategy_overrides: %s' % ex, flush=True)
        return 2
    if overrides_applied:
        print('OVERRIDES %s' % json.dumps(overrides_applied, ensure_ascii=False), flush=True)
    Cls = getattr(M, cfg['engine_class'])

    kw = dict(flags=cfg['flags'])
    kw.update(cfg.get('settings155', {}))
    kw['need_held'] = cfg.get('need_held', False)
    for g in PARAM_GROUPS[1:]:
        if g in cfg:
            for k, v in cfg[g].items():
                if k in kw:
                    print('ERROR duplicate engine switch %s' % k, flush=True)
                    return 2
                kw[k] = v
    sma_path = None
    if 'params169' in cfg:
        sma_path = out / '_sma_table.pkl'
        gdata.write_sma_pickle(P['sma_table'], sma_path)
        kw['sma_table'] = str(sma_path)
    init_eq = float(cfg.get('initial_equity', 1000.0))
    edits_path = resolve(cfg['edits'], cfg_path.parent) if cfg.get('edits') else None
    gate_seed = {f: [list(b) for b in v] for f, v in P['gate_seed'].items()}
    try:
        e = Cls(init_eq, load_edits(str(edits_path)) if edits_path else {}, True, gate_seed=gate_seed, **kw)
    except (ValueError, TypeError, AssertionError) as ex:
        print('ERROR config rejected by %s: %r (see SWITCHES.md for allowed values)' % (cfg['engine_class'], ex), flush=True)
        return 2

    feed = P['feed']
    ws = P['ws']
    for f in (60, 240):
        b = [list(x) for x in P['strategy_seed'][f]]
        e.pb[f] = [x for x in b if x[0] + f * 60000 <= ws][-300:]
    e.warm = True
    for b in feed.bars(ws):
        if b[0] >= START:
            break
        e.step(b)
        e.last = b[0]
    e.warm = False
    e.eq = []
    e.peak = init_eq
    e.mdd = 0
    e.max_mu = 0
    e.events = []
    e.started = START
    for f in e.sigs:
        e.sigs[f] = {True: [], False: []}
    if e.last != START - 60000:
        print('ERROR warm-up did not reach start minute', flush=True)
        return 2

    ev_f = open(out / 'events.log', 'w', encoding='utf-8', newline='\n')
    ev_f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + 'INIT %s %s: warm done, replay %s ~ %s KST\n' % (cfg['engine_module'], getattr(e, 'version', ''), kst.fmt(START), kst.fmt(END)))
    acct_f = open(out / 'equity_minutes.csv', 'w', encoding='utf-8', newline='')
    acct_w = csv.writer(acct_f)
    acct_w.writerow(['t', 'equity_raw', 'rebate_total', 'margin', 'price', 'margin50_skips'])
    audit = {}
    if a.audit:
        ad = out / 'audit'
        ad.mkdir(exist_ok=True)
        audit = {n: open(ad / n, 'w', encoding='utf-8', newline='') for n in
                 ('rescue_orders158.jsonl', 'rescue_sizes158.jsonl', 'held_adoptions159.jsonl', 'rescue_minutes156.csv', 'gate_minutes155.csv', 'candidate_audit155.jsonl')}

    from gl.patinfo import patinfo

    def save():
        """Same state side effects as the original runner's save(): flush (and clear) every audit buffer,
        refresh the dashboard pattern snapshot. Pure file outputs (state.pkl etc.) are skipped."""
        if e.acct151_rows:
            acct_w.writerows(e.acct151_rows)
            e.acct151_rows = []
        for attr, name in (('adoption_rows159', 'held_adoptions159.jsonl'), ('rescue_order_audit158', 'rescue_orders158.jsonl'), ('rescue_size_audit158', 'rescue_sizes158.jsonl')):
            rows = getattr(e, attr, None)
            if rows is None:
                continue
            if name in audit:
                audit[name].writelines(json.dumps(r) + '\n' for r in rows)
            setattr(e, attr, [])
        for attr, name in (('rescue_minutes156', 'rescue_minutes156.csv'), ('gate_minutes155', 'gate_minutes155.csv')):
            rows = getattr(e, attr, None)
            if rows:
                if name in audit:
                    csv.writer(audit[name]).writerows(rows)
                setattr(e, attr, [])
        if getattr(e, 'candidate_audit155', None):
            if 'candidate_audit155.jsonl' in audit:
                audit['candidate_audit155.jsonl'].writelines(json.dumps(r, default=str) + '\n' for r in e.candidate_audit155)
            e.candidate_audit155 = []
        try:
            e.snap['pat'] = patinfo(e)
            e.snap.pop('pat_err', None)
        except Exception as ex:
            e.snap['pat_err'] = repr(ex)[:200]

    save()
    span = END - START
    chunks = 0
    t_run0 = time.time()
    try:
        while True:
            new = [b for b in feed.bars(e.last + 60000, CHUNK) if b[0] > e.last and b[0] < END]
            if not new and e.last + 60000 < END:
                raise RuntimeError('minute data ended at %s before end %s' % (kst.fmt(e.last), kst.fmt(END)))
            lines = []
            for b in new:
                ne = len(e.events)
                e.step(b)
                e.last = b[0]
                for (tt, m) in e.events[ne:]:
                    lines.append(kst.fmt(tt, '%Y-%m-%d %H:%M KST ') + m + '\n')
                e.events = e.events[-200:]
            if lines:
                ev_f.writelines(lines)
            if new:
                save()
            chunks += 1
            if a.progress_every > 0 and (chunks % a.progress_every == 0 or e.last + 60000 >= END):
                px = e.last_mark151[1] if e.last_mark151 else 0
                raw = e.equity(px) if px else e.cash
                print('PROGRESS %.1f%% bar %s KST eq_raw %.2f eq_rebate %.2f mdd_raw %.2f%% elapsed %ds' % (
                    (e.last + 60000 - START) / span * 100, kst.fmt(e.last), raw, raw + e.rebate, e.mdd * 100, time.time() - t_run0), flush=True)
            if e.last + 60000 >= END:
                assert e.last + 60000 == END
                break
    except Exception as ex:
        ev_f.write('FATAL %r\n' % (ex,))
        ev_f.close()
        acct_f.close()
        print('ERROR engine %r' % (ex,), flush=True)
        raise
    t_run = time.time() - t_run0

    rcfg = dict(version=getattr(e, 'version', ''), module=cfg['engine_module'], source_sha256=sha256(Path(M.__file__)),
                start=START, replay_end_ms=END, comparison_baselines=cfg.get('comparison_baselines', {}),
                params162=cfg.get('params162', {}), variant=cfg.get('name', cfg_path.stem), params167=cfg.get('params167', {}))
    report = build_report(e, rcfg)
    save()  # original runner saves once more after capturing completion
    ev_f.close()
    acct_f.close()
    for f in audit.values():
        f.close()
    px = e.last_mark151[1]
    if 'rules169' not in report:
        report['pnl_by_side_kind_basic'] = pnl_basic(e, px)
    summ = summary_row(report)
    if 'rules169' not in report:
        for k, vv in report['pnl_by_side_kind_basic'].items():
            summ['pnl_rebate_' + k] = vv['realized_pnl_rebate70']
            summ['open_unreal_' + k] = vv['open_unrealized_gross']
            summ['open_count_' + k] = vv['open_count']
    summ['trades_closed_records'] = len(e.trades)
    summ['entries'] = e.nid
    summ['equity_raw_end'] = report['equity_raw']
    summ['equity_rebate70_end'] = report['equity_rebate70']
    report['summary'] = summ

    with open(out / 'report.json', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    with open(out / 'summary.json', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(dict(name=rcfg['variant'], start_kst=kst.fmt(START), end_kst_exclusive=kst.fmt(END), **summ), f, ensure_ascii=False, indent=2, default=str)
    with open(out / 'trades.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=TRADE_COLS, extrasaction='ignore')
        w.writeheader()
        w.writerows(e.trades)
    with open(out / 'equity.csv', 'w', newline='', encoding='utf-8') as f:
        f.write('t,equity,price\n')
        f.writelines('%d,%s,%s\n' % x for x in e.eq)
    with open(out / 'monthly.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(report['monthly'][0]) if report['monthly'] else ['month'])
        w.writeheader()
        w.writerows(report['monthly'])
    with open(out / 'repayments.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(e.repayment_log152[0]) if e.repayment_log152 else ['t', 'side', 'contracts'])
        w.writeheader()
        w.writerows(e.repayment_log152)
    with open(out / 'open_positions_end.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['id', 'strat', 'side', 'entry_time_kst', 'entry', 'qty_btc', 'contracts', 'unrealized_gross_at_end', 'mark_price'])
        for p in e.pos:
            w.writerow([p['id'], p['strat'], 'L' if p['buy'] else 'S', kst.fmt(p['t']), p['entry'], p['qty'], p['n'],
                        round((px - p['entry']) * p['qty'] * (1 if p['buy'] else -1), 6), px])

    ent_val = None
    t_ent = 0.0
    if not a.no_entries:
        print('EXPORT entries.csv ...', flush=True)
        t0 = time.time()
        from gl.entries import export
        T, V = P['arrays']
        m = T < END
        ent_val = export(e, rcfg, report, out / 'events.log', out / 'equity_minutes.csv', T[m], V[m], out, rcfg['version'])
        t_ent = time.time() - t0
    if sma_path and sma_path.exists():
        sma_path.unlink()

    import numpy
    import pandas
    meta = dict(name=rcfg['variant'], config=str(cfg_path), config_sha256=sha256(cfg_path), engine=dict(module=cfg['engine_module'], cls=cfg['engine_class'], version=rcfg['version'], source_sha256=rcfg['source_sha256']),
                start_ms=START, end_ms_exclusive=END, start_kst=kst.fmt(START), end_kst_exclusive=kst.fmt(END), data=dict(files={p.name: sha256(p) for p in files}, **P['info']),
                edits_sha256=sha256(edits_path) if edits_path else None, strategy_overrides=overrides_applied, override_refused_entries=getattr(e, 'override_refused', 0), replay_seconds=round(t_run, 1), entries_seconds=round(t_ent, 1), total_seconds=round(time.time() - t_wall0, 1), peak_rss_mb=peak_rss_mb(),
                python=sys.version.split()[0], platform=platform.platform(), numpy=numpy.__version__, pandas=pandas.__version__,
                headline=dict(return_rebate70_pct=report['return_rebate70_pct'], return_raw_pct=report['return_raw_pct'], mdd_raw_minute_pct=report['mdd_raw_minute_pct'],
                              mdd_rebate70_exact_minute_pct=report['mdd_rebate70_exact_minute_pct'], max_margin_usage_pct=report['max_margin_usage_pct'],
                              equity_raw=report['equity_raw'], trades_closed_records=len(e.trades), entries=e.nid),
                entries_validation=dict(rows=ent_val['rows'], exact_total_minus_report=ent_val['exact_total_minus_report']) if ent_val else None)
    mods = {}
    for n, mod in list(sys.modules.items()):
        fp = getattr(mod, '__file__', None)
        if fp and (n.startswith('engine') or n == 'gl' or n.startswith('gl.')):
            mods[n] = str(Path(fp).resolve())
    meta['loaded_package_modules'] = len(mods)
    meta['foreign_modules'] = {n: p for n, p in mods.items() if not Path(p).is_relative_to(ROOT)}
    with open(out / 'run_meta.json', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, default=str)
    print('DONE %s rebate %+.3f%% raw %+.3f%% rawMDD %.3f%% rebateMDD %.3f%% maxMargin %.3f%% trades %d equity_raw %.6f time %ds' % (
        rcfg['variant'], report['return_rebate70_pct'], report['return_raw_pct'], report['mdd_raw_minute_pct'], report['mdd_rebate70_exact_minute_pct'],
        report['max_margin_usage_pct'], len(e.trades), report['equity_raw'], time.time() - t_wall0), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
