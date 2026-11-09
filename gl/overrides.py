"""Optional strategy overrides (config key "strategy_overrides"). EXPERIMENTAL / not part of any frozen round.

Every key is OFF by default. With no key set, apply() changes NOTHING (no patch is installed), so
results are bit-identical to the original engine. Each override replaces one engine constant or adds a
filter at the single common order entry point (Engine8.open), only for the current process.

keys (see SWITCHES.md section 4):
  disable_strats   list[str]  refuse NEW normal entries whose strat is listed ('pat1','fib15','tri1','ma60',...)
  disable_rules    list[str]  refuse NEW normal entries whose entry text contains any substring
                              (e.g. "추세선 닿으면 반대", "추세선 돌파 리테스트", "5파동 피보나치", "M1MARKET", "triangle")
  size_scale       dict       multiply the order size of normal entries; key = exact strat ('pat1') or family
                              prefix ('pat','fib','tri','rsi','ma','mt'); exact strat wins. 1.0 = unchanged
  tp_usdt          dict       TP distance (USDT) for exit-mode 'pat' entries (trendline breakout/bounce pat*, fib*),
                              key = exact strat; replaces engine15.tp_off. params167.tp_set (group:frame) still has priority
  fib_levels       list[float] Fibonacci retracement levels (engine7.ENTRY); default 0.382,0.5,0.618,0.722,0.786,0.886
  fib_uses         int        max fills per fib level (engine7.FIB_USES), default 3
  retest_bars      int        breakout-retest signal lifetime in bars of its frame (engine5.RETEST), default 15
  bounce_slope     float      min |slope| USDT/h for touch-reverse ('bounce') lines and against-slope breakout block (engine17.SLOPE), default 20
  bounce_uses      int        max trades per bounce line (engine17.BUSES), default 3
  triangle_enabled bool       1m triangle breakout on/off (engine4.ENABLED['tri1']), default true
"""

KNOWN = ('disable_strats', 'disable_rules', 'size_scale', 'tp_usdt', 'fib_levels', 'fib_uses', 'retest_bars',
         'bounce_slope', 'bounce_uses', 'triangle_enabled')


def apply(ov):
    """Install overrides. Returns a dict describing what was changed (empty = nothing patched)."""
    if not ov:
        return {}
    bad = set(ov) - set(KNOWN)
    if bad:
        raise ValueError('unknown strategy_overrides keys: %s' % sorted(bad))
    import engine4
    import engine5
    import engine7
    import engine8
    import engine15
    import engine17
    done = {}
    if ov.get('fib_levels') is not None:
        lv = tuple(float(x) for x in ov['fib_levels'])
        if not lv or any(not 0 < x < 1 for x in lv):
            raise ValueError('fib_levels must be in (0,1)')
        engine7.ENTRY = lv
        done['fib_levels'] = lv
    if ov.get('fib_uses') is not None:
        engine7.FIB_USES = int(ov['fib_uses'])
        done['fib_uses'] = engine7.FIB_USES
    if ov.get('retest_bars') is not None:
        engine5.RETEST = int(ov['retest_bars'])
        done['retest_bars'] = engine5.RETEST
    if ov.get('bounce_slope') is not None:
        engine17.SLOPE = float(ov['bounce_slope'])
        done['bounce_slope'] = engine17.SLOPE
    if ov.get('bounce_uses') is not None:
        engine17.BUSES = int(ov['bounce_uses'])
        done['bounce_uses'] = engine17.BUSES
    if ov.get('triangle_enabled') is not None:
        engine4.ENABLED['tri1'] = bool(ov['triangle_enabled'])
        done['triangle_enabled'] = engine4.ENABLED['tri1']
    if ov.get('tp_usdt'):
        table = {str(k): float(v) for k, v in ov['tp_usdt'].items()}
        orig_tp = engine15.tp_off

        def tp_off(strat, _orig=orig_tp, _t=table):
            return _t[strat] if strat in _t else _orig(strat)
        engine15.tp_off = tp_off
        done['tp_usdt'] = table
    dis_s = set(ov.get('disable_strats') or [])
    dis_r = list(ov.get('disable_rules') or [])
    scale = {str(k): float(v) for k, v in (ov.get('size_scale') or {}).items()}
    if dis_s or dis_r or scale:
        orig_open = engine8.Engine8.open

        def open(s, t, strat, buy, px, pct=None, info='', limit=False, notional=None, exitmode=None):
            if strat != 'cyc' and not getattr(s, 'warm', False):
                if strat in dis_s or any(r in (info or '') for r in dis_r):
                    s.override_refused = getattr(s, 'override_refused', 0) + 1
                    return None
                k = strat if strat in scale else strat.rstrip('0123456789')
                if k in scale:
                    if notional is not None:
                        notional *= scale[k]
                    elif pct is not None:
                        pct *= scale[k]
            return orig_open(s, t, strat, buy, px, pct, info, limit, notional, exitmode)
        engine8.Engine8.open = open
        done.update(disable_strats=sorted(dis_s), disable_rules=dis_r, size_scale=scale)
    return done
