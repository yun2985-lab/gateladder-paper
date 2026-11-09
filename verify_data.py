#!/usr/bin/env python3
"""Verify shipped data files and (optionally) that the inputs derived from them are bit-identical to the
pickled inputs of the original runs (.168-.173).

    python verify_data.py            # file SHA256 + numeric content hashes (seconds)
    python verify_data.py --derive   # + rebuild Y2024/Y2025 seeds, SMA tables, replay minutes (~20 s)
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from gl import data as gd  # noqa: E402
from gl import kst  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--derive', action='store_true')
    a = ap.parse_args(argv)
    man = json.loads((ROOT / 'data' / 'MANIFEST.json').read_text(encoding='utf-8'))
    ok = True
    for name, x in man['files'].items():
        p = ROOT / 'data' / name
        if not p.exists():
            print('MISSING', name)
            ok = False
            continue
        fs = hashlib.sha256(p.read_bytes()).hexdigest()
        cs = gd.content_sha256(p)
        good = cs == x['content_sha256']
        print('%-40s file_sha256 %s content %s' % (name, 'OK' if fs == x['sha256'] else 'differs(zip metadata?)', 'OK' if good else 'MISMATCH'))
        ok &= good
    if a.derive:
        for y, d in man['derived'].items():
            files = [ROOT / f for f in d['minute_files']]
            P = gd.prepare(files, kst.parse(d['start_kst']), kst.parse(d['end_kst_exclusive']))
            got = dict(filters_seed=gd.canonical_sha256(P['gate_seed']), strategy_seed=gd.canonical_sha256(P['strategy_seed']),
                       sma_table=gd.canonical_sha256(P['sma_table']), replay_minutes=gd.canonical_sha256(P['feed']._c))
            for k, v in got.items():
                good = v == d[k]
                ok &= good
                print('%s %-15s %s' % (y, k, 'OK (identical to original pickle)' if good else 'MISMATCH'))
    print('PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
