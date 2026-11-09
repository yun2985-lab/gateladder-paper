#!/usr/bin/env python3
"""Download Binance USDT-M futures BTCUSDT 1-minute klines (public endpoint, no API key) into a
data npz usable in a config's "minute_files" list.

    # rebuild the shipped master file (2024-08-01 00:00 ~ 2026-11-08 23:59 KST) and verify it
    python fetch_data.py --master --verify
    # extra / newer months for custom periods (then add the file AFTER the master in minute_files)
    python fetch_data.py --start "2026-11-01 00:00" --end "2026-12-01 00:00" --out data/extra_2026_11.npz

Source: https://fapi.binance.com/fapi/v1/klines (symbol BTCUSDT, interval 1m, limit 1500), same
endpoint as the original runs. Only fully closed candles are kept. Output keys: t (open time, epoch
ms, int64), o, h, l, c (float64). Volume is not used by the engine and is not stored.

NOTE: data/btcusdt_1m_Y2025_engine_input.npz cannot be re-downloaded bit-for-bit: its last days
(2026-11-04 13:45 ~ 2026-11-07 23:02 KST, 242 bars) came from the live 1m cache of the original
paper runs and differ slightly from Binance's final candles. Keep the shipped file to reproduce Y2025.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from gl import kst  # noqa: E402
from gl.data import content_sha256  # noqa: E402

URL = 'https://fapi.binance.com/fapi/v1/klines'
MASTER = dict(start=1722438000000, end=1794150000000, out='data/btcusdt_1m_master.npz')


def fetch(start, end, sleep=0.12):
    import requests
    s = requests.Session()
    rows = []
    t = start
    while t < end:
        for i in range(6):
            try:
                r = s.get(URL, params=dict(symbol='BTCUSDT', interval='1m', startTime=t, endTime=end - 1, limit=1500), timeout=(5, 20))
                r.raise_for_status()
                d = r.json()
                break
            except Exception:
                if i == 5:
                    raise
                time.sleep(2 * (i + 1))
        if not d:
            break
        rows += [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4])] for k in d]
        t = int(d[-1][0]) + 60000
        print('FETCH %s %d rows' % (kst.fmt(t), len(rows)), flush=True)
        time.sleep(sleep)
    now = int(time.time() * 1000)
    rows = [r for r in rows if r[0] + 60000 <= now and start <= r[0] < end]
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--master', action='store_true', help='rebuild data/btcusdt_1m_master.npz range')
    ap.add_argument('--start', help='KST "YYYY-MM-DD HH:MM" (inclusive)')
    ap.add_argument('--end', help='KST "YYYY-MM-DD HH:MM" (exclusive)')
    ap.add_argument('--out')
    ap.add_argument('--verify', action='store_true', help='compare content hash with data/MANIFEST.json')
    a = ap.parse_args(argv)
    if a.master:
        start, end, out = MASTER['start'], MASTER['end'], a.out or MASTER['out']
    else:
        if not (a.start and a.end and a.out):
            ap.error('--start, --end and --out are required (or use --master)')
        start, end, out = kst.parse(a.start), kst.parse(a.end), a.out
    out = Path(out)
    if not out.is_absolute():
        out = ROOT / out
    rows = fetch(start, end)
    if not rows:
        raise SystemExit('no data returned')
    A = np.array(rows, dtype=np.float64)
    T = np.array([r[0] for r in rows], dtype=np.int64)
    gaps = np.nonzero(np.diff(T) != 60000)[0]
    if len(gaps):
        print('WARNING %d gaps, first: %s' % (len(gaps), [(kst.fmt(int(T[i])), int(T[i + 1] - T[i]) // 60000 - 1) for i in gaps[:5]]))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + '.tmp.npz')
    np.savez_compressed(tmp, t=T, o=A[:, 1], h=A[:, 2], l=A[:, 3], c=A[:, 4])
    tmp.replace(out)
    ch = content_sha256(out)
    print('WROTE %s rows %d %s ~ %s KST content_sha256 %s' % (out, len(T), kst.fmt(int(T[0])), kst.fmt(int(T[-1])), ch))
    if a.verify:
        man = json.loads((ROOT / 'data' / 'MANIFEST.json').read_text(encoding='utf-8'))
        want = man['files'].get(out.name, {}).get('content_sha256')
        print('VERIFY', 'MATCH' if ch == want else 'DIFFERENT (expected %s)' % want)
        return 0 if ch == want else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
