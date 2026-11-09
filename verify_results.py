#!/usr/bin/env python3
"""Check a finished run against the frozen reference values of the original Linux runs.

    python verify_results.py results/W4_Y2025            # name taken from summary.json
    python verify_results.py results/W4_Y2025 --name W4_Y2025

PASS requires rebate return, raw return, raw MDD, exact-rebate MDD, max margin (all to 3 decimals as reported)
AND exact equity_raw (6 decimals) and closed-trade record count to match expected/frozen_baselines.json.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('outdir')
    ap.add_argument('--name')
    a = ap.parse_args(argv)
    s = json.loads((Path(a.outdir) / 'summary.json').read_text(encoding='utf-8'))
    name = a.name or s['name']
    exp = json.loads((ROOT / 'expected' / 'frozen_baselines.json').read_text(encoding='utf-8'))
    if name not in exp:
        print('no frozen reference for', name, '- available:', ', '.join(sorted(exp)))
        return 2
    x = exp[name]
    checks = [('return_rebate70_pct', s['return_rebate70_pct'], x['return_rebate70_pct'], 3),
              ('return_raw_pct', s['return_raw_pct'], x['return_raw_pct'], 3),
              ('mdd_raw_pct', s['mdd_raw_pct'], x['mdd_raw_minute_pct'], 3),
              ('mdd_rebate_exact_pct', s['mdd_rebate_exact_pct'], x['mdd_rebate70_exact_minute_pct'], 3),
              ('max_margin_pct', s['max_margin_pct'], x['max_margin_usage_pct'], 3),
              ('equity_raw_end', s['equity_raw_end'], x['equity_raw'], 6),
              ('trades_closed_records', s['trades_closed_records'], x['trades_closed_records'], 0)]
    ok = True
    for k, got, want, nd in checks:
        good = round(got, nd) == round(want, nd)
        ok &= good
        print('%-24s got %-14s expected %-14s %s' % (k, round(got, nd), round(want, nd), 'OK' if good else 'MISMATCH'))
    print('PASS' if ok else 'FAIL', name)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
