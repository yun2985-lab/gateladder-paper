"""GateLadder 0.9.108+size = engine8 (0.9.108, real fees maker 0.018%/taker 0.042%, rebate 0.7, breakeven OFF, fib 0.722)
+ user 11/3: every entry +1 percentage point, quantity always seed x fixed 3x (LEV=3 constant, independent of app leverage):
breakout(pat) 4->5% of available, fib 1->2% per level, cyc rescue add 2->3% of available, triangle 2->3% of seed, RSI 1m/15m/1h 5->6% of seed."""
from engine8 import Engine8
SCALE={'pat':0.05/0.04,'fib':0.02/0.01,'cyc':0.03/0.02}   # notional-based (free balance x pct x 3)
PCT={'tri1':0.03,'rsi1':0.06,'rsi15':0.06,'rsi60':0.06}    # seed-based
class Engine9(Engine8):
    def __init__(s,*a,**k):
        super().__init__(*a,**k); s.version='0.9.108+size'
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        k=strat.rstrip('0123456789') if strat!='cyc' else 'cyc'
        if notional is not None and k in SCALE: notional*=SCALE[k]
        elif pct is not None and strat in PCT: pct=PCT[strat]
        return super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
