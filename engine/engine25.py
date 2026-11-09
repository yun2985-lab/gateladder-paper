"""0.9.144 VERSION2 ONLY, based on engine24: remove all Bollinger trading.
Retains .143 SMA120 rescue20 gating, .141 shrink/bounce and all paper overrides.
Skipping only Mix143 BB methods avoids BB math/deque/order processing entirely.
"""
from engine24 import Engine24
from engine23 import Mix143
class Engine25(Engine24):
    def __init__(s,*a,**k):
        super().__init__(*a,**k);s.version='0.9.144 현재 비율'
        del s.bb_minutes;del s.bb_slots
    def step(s,b):return super(Mix143,s).step(b)
    def pat_bar(s,f,t):return super(Mix143,s).pat_bar(f,t)
    def limits(s,t,o,h,l,c):return super(Mix143,s).limits(t,o,h,l,c)
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        if strat.startswith('bb'):return None
        return super(Mix143,s).open(t,strat,buy,px,pct,info,limit,notional,exitmode)
    def set_exits(s,p,mode):return super(Mix143,s).set_exits(p,mode)
