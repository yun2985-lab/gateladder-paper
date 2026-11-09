#!/usr/bin/env python3
"""Side-by-side comparison of finished runs (reads each OUTDIR/summary.json).

Two-year style (same as the .172/.173 comparison.csv):
    python compare.py --out comparison.csv --pair W4 results/W4_Y2024 results/W4_Y2025 --pair X1 results/X1_Y2024 results/X1_Y2025

Columns: condition, Y2024_<metric>..., Y2025_<metric>..., two_year_rebate_sum_pct, both_rebate_positive,
both_raw_mdd_le_25, candidate (= both years rebate return > 0 AND both raw MDD <= 25%).
Use --labels A B to rename the two period prefixes (default Y2024 Y2025).
"""
import argparse
import csv
import json
from pathlib import Path


def load(d):
    p = Path(d) / 'summary.json'
    if not p.exists():
        raise SystemExit('missing %s (run not finished?)' % p)
    return json.loads(p.read_text(encoding='utf-8'))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', required=True)
    ap.add_argument('--pair', nargs=3, action='append', metavar=('NAME', 'DIR_A', 'DIR_B'), required=True)
    ap.add_argument('--labels', nargs=2, default=['Y2024', 'Y2025'])
    ap.add_argument('--mdd-limit', type=float, default=25.0)
    a = ap.parse_args(argv)
    la, lb = a.labels
    rows = []
    for name, da, db in a.pair:
        A, B = load(da), load(db)
        row = dict(condition=name)
        for lab, s in ((la, A), (lb, B)):
            row[lab + '_period'] = '%s ~ %s' % (s.get('start_kst'), s.get('end_kst_exclusive'))
            for k, v in s.items():
                if k in ('name', 'start_kst', 'end_kst_exclusive'):
                    continue
                row[lab + '_' + k] = v
        ra, rb = A['return_rebate70_pct'], B['return_rebate70_pct']
        row['two_year_rebate_sum_pct'] = round(ra + rb, 6)
        row['both_rebate_positive'] = ra > 0 and rb > 0
        row['both_raw_mdd_le_%g' % a.mdd_limit] = A['mdd_raw_pct'] <= a.mdd_limit and B['mdd_raw_pct'] <= a.mdd_limit
        row['candidate'] = row['both_rebate_positive'] and row['both_raw_mdd_le_%g' % a.mdd_limit]
        rows.append(row)
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(a.out, 'w', newline='', encoding='utf-8-sig') as f:  # utf-8-sig: Excel on Windows shows Korean correctly
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    best = max((r for r in rows if r['candidate']), key=lambda r: r['two_year_rebate_sum_pct'], default=None)
    for r in rows:
        print('%-8s %s %+8.3f%%  %s %+8.3f%%  sum %+8.3f%%  rawMDD %.3f/%.3f  candidate=%s' % (
            r['condition'], la, r[la + '_return_rebate70_pct'], lb, r[lb + '_return_rebate70_pct'], r['two_year_rebate_sum_pct'],
            r[la + '_mdd_raw_pct'], r[lb + '_mdd_raw_pct'], r['candidate']))
    print('best candidate by two-year sum:', best['condition'] if best else None)
    print('wrote', a.out)


if __name__ == '__main__':
    main()
