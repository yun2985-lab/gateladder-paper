"""Minute data loading and deterministic derivation of every engine input.

Everything the engine needs is derived from 1-minute BTCUSDT USDT-M futures bars
(Binance fapi/v1/klines, open time in epoch ms, OHLC float64):

  * replay minutes      : [warm_start, end)                (list of [t,o,h,l,c])
  * filter seed         : completed UTC 1h/4h/1d bars in [first, warm_start),
                          first = (warm_start - 70 days) floored to the frame
  * strategy seed       : last <=300 of the 1h/4h filter-seed bars that start
                          at or after warm_start - 260 bars
  * SMA table (.169+)   : 4h SMA120 / 1d SMA50 on UTC buckets built from ALL
                          minutes in the data files before `end`

warm_start = (start - 13 days) floored to a 4h UTC boundary (inherited from the
original runners). This reproduces bit-for-bit the pickled inputs used by the
original .168-.173 runs (checked in verify_data.py against data/MANIFEST.json).
"""
import bisect
import pickle
from pathlib import Path

import numpy as np

MIN = 60000
DAY = 86400000
H4 = 14400000


def warm_start(start_ms):
    return (start_ms - 13 * DAY) // H4 * H4


def seed_first(ws, frame_min):
    span = frame_min * MIN
    return (ws - 70 * DAY) // span * span


def load_npz(path):
    z = np.load(path)
    t = z['t'].astype(np.int64)
    v = np.stack([z['o'], z['h'], z['l'], z['c']], axis=1).astype(np.float64)
    assert len(t) == len(v)
    if len(t) > 1 and not np.all(np.diff(t) > 0):
        raise ValueError('%s: timestamps not strictly increasing' % path)
    return t, v


def merge(paths):
    """Later files override earlier ones on identical open times."""
    T = V = None
    for p in paths:
        t, v = load_npz(p)
        if T is None:
            T, V = t, v
            continue
        allT = np.concatenate([T, t])
        allV = np.concatenate([V, v])
        order = np.argsort(allT, kind='stable')
        allT, allV = allT[order], allV[order]
        keep = np.r_[allT[1:] != allT[:-1], True]
        T, V = allT[keep], allV[keep]
    if T is None:
        raise ValueError('no minute files configured')
    return T, V


class DataCoverageError(RuntimeError):
    pass


def check_contiguous(T, a, b, what):
    i0 = np.searchsorted(T, a)
    i1 = np.searchsorted(T, b)
    seg = T[i0:i1]
    expected = (b - a) // MIN
    if len(seg) != expected or (len(seg) and (seg[0] != a or seg[-1] != b - MIN)):
        have = (int(T[0]), int(T[-1])) if len(T) else None
        gaps = []
        if len(seg) > 1:
            d = np.nonzero(np.diff(seg) != MIN)[0][:5]
            gaps = [(int(seg[k]), int(seg[k + 1])) for k in d]
        from .kst import fmt
        raise DataCoverageError(
            '%s needs every 1m bar from %s to %s KST (exclusive) but data has %d of %d bars (data covers %s ~ %s KST, first gaps %s). '
            'Extend data with fetch_data.py or choose a later start / earlier end.' % (
                what, fmt(a), fmt(b), len(seg), expected, fmt(have[0]) if have else None, fmt(have[1]) if have else None,
                [(fmt(x), fmt(y)) for x, y in gaps]))


def resample(T, V, a, b, frame_min):
    """Completed UTC frame bars from minutes in [a, b)."""
    span = frame_min * MIN
    i0, i1 = np.searchsorted(T, a), np.searchsorted(T, b)
    t, v = T[i0:i1], V[i0:i1]
    if not len(t):
        return []
    bk = t // span * span
    keys, first, counts = np.unique(bk, return_index=True, return_counts=True)
    out = []
    for k, s, n in zip(keys, first, counts):
        if n != frame_min:
            continue
        seg = v[s:s + n]
        out.append([int(k), float(seg[0, 0]), float(seg[:, 1].max()), float(seg[:, 2].min()), float(seg[-1, 3])])
    return out


def build_seeds(T, V, ws):
    filt = {}
    for f in (60, 240, 1440):
        filt[f] = resample(T, V, seed_first(ws, f), ws, f)
    strat = {f: [b for b in filt[f] if b[0] >= ws - 260 * f * MIN][-300:] for f in (60, 240)}
    return filt, strat


def build_sma(T, V, end):
    """Same algorithm as build_sma_0169.py (4h SMA120, 1d SMA50, UTC buckets)."""
    m = T < end
    t, c = T[m], V[m, 3]
    end_eff = int(t[-1]) + MIN
    tab = {}
    for tf, (fm, N) in {'4h': (H4, 120), '1d': (DAY, 50)}.items():
        bk = t // fm * fm
        keys, first = np.unique(bk, return_index=True)
        last = np.r_[first[1:] - 1, len(t) - 1]
        keys = [int(k) for k in keys]
        closes = [float(x) for x in c[last]]
        sel = [i for i, k in enumerate(keys) if k + fm <= end_eff]
        keys = [keys[i] for i in sel]
        cl = [closes[i] for i in sel]
        ct = [k + fm for k in keys]
        sma = []
        for i in range(len(cl)):
            ok = i >= N - 1 and keys[i] - keys[i - N + 1] == (N - 1) * fm
            sma.append(sum(cl[i - N + 1:i + 1]) / N if ok else None)
        tab[tf] = dict(close_t=ct, close=cl, sma=sma, bucket_ms=fm, period=N)
    return tab


class MinuteFeed:
    """Same contract as the original kcache modules: bars(start, limit)."""
    def __init__(self, rows):
        self._c = rows

    def bars(self, start, limit=None):
        i = bisect.bisect_left(self._c, [start])
        return self._c[i:i + limit] if limit else self._c[i:]


def prepare(paths, start, end):
    """Returns dict(feed, gate_seed, strategy_seed, sma_table, ws, info)."""
    T, V = merge(paths)
    ws = warm_start(start)
    first = min(seed_first(ws, f) for f in (60, 240, 1440))
    check_contiguous(T, first, end, 'warm-up seeds + replay')
    i0, i1 = np.searchsorted(T, ws), np.searchsorted(T, end)
    rows = [[int(a), float(o), float(h), float(l), float(c)] for a, (o, h, l, c) in zip(T[i0:i1].tolist(), V[i0:i1].tolist())]
    filt, strat = build_seeds(T, V, ws)
    if len(filt[60]) < 15 or len(filt[240]) < 120:
        raise DataCoverageError('not enough history before warm start for TREND/RSI filters')
    sma = build_sma(T, V, end)
    info = dict(data_first_ms=int(T[0]), data_last_ms=int(T[-1]), warm_start_ms=int(ws), seed_first_ms=int(first),
                replay_minutes=int(np.searchsorted(T, end) - np.searchsorted(T, start)), loaded_minutes=len(rows))
    for tf in ('4h', '1d'):
        ct, sm = sma[tf]['close_t'], sma[tf]['sma']
        j = bisect.bisect_right(ct, start) - 1
        info['sma_%s_ready_at_start' % tf] = bool(j >= 0 and sm[j] is not None)
    return dict(feed=MinuteFeed(rows), gate_seed=filt, strategy_seed=strat, sma_table=sma, ws=ws, info=info, arrays=(T, V))


def write_sma_pickle(tab, path):
    """engine169 takes a *path* to a pickled table; we write a fresh one per run
    with the running interpreter (portable: never shipped, never shared)."""
    with open(path, 'wb') as f:
        pickle.dump(tab, f)


def content_sha256(path):
    """Hash of the numeric content (t int64 LE + o,h,l,c float64 LE), independent of zip metadata."""
    import hashlib
    z = np.load(path)
    h = hashlib.sha256()
    h.update(z['t'].astype('<i8').tobytes())
    for k in ('o', 'h', 'l', 'c'):
        h.update(z[k].astype('<f8').tobytes())
    return h.hexdigest()


def canonical_sha256(obj):
    """Hash of a derived input object (seed dict / SMA table / minute rows) via canonical JSON."""
    import hashlib
    import json
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
