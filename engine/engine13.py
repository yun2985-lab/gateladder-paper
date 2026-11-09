"""GateLadder 0.9.115+3pp = engine12 (0.9.115 + all user settings) + user 11/4: every entry +3 percentage points
for entries at/after SWITCH (earlier entries keep old sizes). Qty still seed x pct x fixed 3x.
breakout 5->8% avail, fib 2->5% avail per level, rescue add 3->6% avail, triangle 3->6% seed, RSI 1m/15m/1h 6->9% seed.
Future engines must build on this so the switch stays at SWITCH."""
from engine12 import Engine12
from engine8 import Engine8
SWITCH=1793752140000   # 2026-11-04 09:29 KST
NOTIONAL={'pat':0.08/0.04,'fib':0.05/0.01,'cyc':0.06/0.02}
PCT={'tri1':0.06,'rsi1':0.09,'rsi15':0.09,'rsi60':0.09}
class Engine13(Engine12):
    def __init__(s,*a,**k):
        super().__init__(*a,**k); s.version='0.9.115+3pp'
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        if t<SWITCH: return super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
        k='cyc' if strat=='cyc' else strat.rstrip('0123456789')
        if notional is not None and k in NOTIONAL: notional*=NOTIONAL[k]
        elif pct is not None and strat in PCT: pct=PCT[strat]
        return Engine8.open(s,t,strat,buy,px,pct,info,limit,notional,exitmode)
