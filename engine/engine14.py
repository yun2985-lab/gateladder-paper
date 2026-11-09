"""Version 2 (1-year backtest + live): engine13 logic with the CURRENT sizes for the whole period (no size switch):
breakout 8% / fib 5% per level / rescue 6% (available), triangle 6% / RSI 9% (seed), fixed 3x; 0.9.115 logic,
rebate 0.7, real fees, breakeven OFF, 0.722 fib. Also prunes finished Fibonacci order slots (kept as 'dead' keys) so a
year-long run does not slow down."""
import engine13 as E13
from engine13 import Engine13, NOTIONAL, PCT
from engine8 import Engine8
class FD(dict):
    def __init__(s,*a,**k): super().__init__(*a,**k); s.dead=set()
    def __contains__(s,k): return dict.__contains__(s,k) or k in s.dead
class Engine14(Engine13):
    def __init__(s,*a,**k):
        super().__init__(*a,**k); s.version='0.9.115 현재 비율'
        s.fsig={f:{True:FD(),False:FD()} for f in s.fsig}; s._pr=0
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        k='cyc' if strat=='cyc' else strat.rstrip('0123456789')
        if notional is not None and k in NOTIONAL: notional*=NOTIONAL[k]
        elif pct is not None and strat in PCT: pct=PCT[strat]
        return Engine8.open(s,t,strat,buy,px,pct,info,limit,notional,exitmode)
    def limits(s,t,o,h,l,c):
        s._pr+=1
        if s._pr%120==0:
            live={p['id'] for p in s.pos}
            for f in s.fsig:
                for b in (True,False):
                    D=s.fsig[f][b]
                    for k in [k for k,v in D.items() if v.get('void') or (v.get('filled') and v.get('busy') not in live)]:
                        del D[k]; D.dead.add(k)
        super().limits(t,o,h,l,c)
