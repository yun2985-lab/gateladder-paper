"""GateLadder 0.9.108 paper engine = engine7 (0.9.106) + user's 0.9.108 settings spec (11/3):
- Fibonacci entries on 5 levels (confirmed from app screenshot): 0.382/0.5/0.618/0.722/0.786.
- Real account fee model (user approved 11/3): maker 0.018% on limit fills (entries and limit TPs), taker 0.042% on market fills.
  Fee-derived TP (cost x5) uses taker 0.042% for the assumed exit, like the app's StagedExit.
- Rebate 0.7, breakeven forced OFF (user's real account)."""
import engine4 as E4, engine6 as E6, engine7 as E7
from engine7 import Engine7
TAKER=0.00042; MAKER=0.00018
E4.FEE=TAKER; E4.REBATE=0.7; E4.F=E4.FEE*(1-E4.REBATE)
E6.MAKER_FEE=MAKER; E7.MAKER_FEE=MAKER
E7.ENTRY=(0.382,0.5,0.618,0.722,0.786)
class Engine8(Engine7):
    def __init__(s,*a,**k):
        super().__init__(*a,**k); s.version='0.9.108'; s.no_be=True
    def _with(s,limit,fn,*a,**k):
        prev=getattr(s,'_fr',None)
        if prev is None: s._fr=MAKER if limit else TAKER
        try: return fn(*a,**k)
        finally: s._fr=prev
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        return s._with(limit,super().open,t,strat,buy,px,pct,info,limit,notional,exitmode)
    def close(s,t,p,n,price,why,limit=False):
        return s._with(limit,super().close,t,p,n,price,why,limit)
