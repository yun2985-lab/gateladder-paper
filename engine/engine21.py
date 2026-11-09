"""0.9.141 BTC paper adapter on engine19. Source .139 price alerts are UI-only.
.140 separates bounce size (3% available) from established breakout sizes.
.141 after 20 rescue adds, allow that direction again at one-third entry size,
percentage rounded DOWN to 2 decimal percentage points as CycleRescue.shrink.
15% exposure cap still takes precedence. Existing overrides unchanged otherwise.
"""
import math
from engine19 import Engine19
from engine15 import Mix124
from engine13 import SWITCH
from engine5 import LEV,TICK

def shrink_fraction(frac):
    return math.floor(round(frac,10)*10000/3+1e-9)/10000

class Mix141:
    def rescue_small(s,buy):return s.cr[buy]['phase']=='active' and s.cr[buy]['adds']>=20
    def rescue_blocks(s,buy):return s.cr[buy]['phase']=='active' and s.cr[buy]['adds']<20
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        if strat!='cyc' and not getattr(s,'warm',False):
            if s.capped(buy,px) or s.rescue_blocks(buy):return None
        # Skip the superseded Mix129 rescue-until-end gate, retaining Mix124
        # drop guard and Engine13/14 historical/current size overrides below it.
        return Mix124.open(s,t,strat,buy,px,pct,info,limit,notional,exitmode)
    def _with(s,limit,fn,*args,**kwargs):
        if getattr(fn,'__name__','')=='open' and len(args)>=9:
            a=list(args);t,strat,buy,px,pct,info,lim,N,mode=a
            if strat!='cyc':
                free=max(0,s.free(px));base=free*LEV
                # Apply AFTER historical +pp overrides: bounce is now a distinct 3% rule.
                if '추세선 닿으면 반대' in info:
                    N=base*.03;pct=None
                if s.rescue_small(buy):
                    if N is not None:
                        frac=N/base if base>0 else 0;N=base*shrink_fraction(frac)
                    elif pct is not None:pct=shrink_fraction(pct)
                    info+=' [구출20회 소진 · 진입1/3]'
                a[4]=pct;a[5]=info;a[7]=N;args=tuple(a)
        return super()._with(limit,fn,*args,**kwargs)
    def cr_fill(s,t,o,h,l,c):
        before={buy:s.cr[buy]['adds'] for buy in (True,False)}
        super().cr_fill(t,o,h,l,c)
        for buy in (True,False):
            if before[buy]<20<=s.cr[buy]['adds']:
                s.log(t,'RESCUE SPENT %s: 20 adds; normal entries eligible at 1/3 (15%% exposure cap still applies)'%('L' if buy else 'S'))
    def limits(s,t,o,h,l,c):
        # Same order lifecycle as Mix138, but hold only until rescue add 20.
        hide={}
        if not getattr(s,'warm',False):
            for buy in (True,False):
                blocked=s.capped(buy,o) or s.rescue_blocks(buy)
                if blocked!=s.cap_state[buy]:
                    s.cap_state[buy]=blocked;s.log(t,'ENTRY HOLD %s %s (side %.2f%%, rescue small=%s)'%('L' if buy else 'S',blocked,s.side_share(buy,o),s.rescue_small(buy)))
                if blocked:
                    for f in s.sigs:hide[(f,buy)]=s.sigs[f][buy];s.sigs[f][buy]=[]
        # Bypass Mix138's old full-rescue gate, retain all engine17/18 execution.
        from engine17 import Mix129
        try:Mix129.limits(s,t,o,h,l,c)
        finally:
            for (f,buy),signals in hide.items():s.sigs[f][buy]=signals
        if getattr(s,'warm',False):return
        for sg in s.ma_slots:
            if sg.get('filled') or not sg['frm']<=t<sg['until']:continue
            buy=sg['buy']
            if s.capped(buy,o) or s.rescue_blocks(buy):continue
            px=math.floor(sg['price']/TICK)*TICK if buy else math.ceil(sg['price']/TICK)*TICK
            px=min(px,round(o-TICK,1)) if buy else max(px,round(o+TICK,1))
            if any(p['buy']==buy and p['strat'] in ('pat%d'%sg['f'],'ma%d'%sg['f']) and abs(p['entry']-px)<100 for p in s.pos):continue
            if l<=px if buy else h>=px:
                p=s.open(t,'ma%d'%sg['f'],buy,px,info='SMA%d turn %dm'%(sg['period'],sg['f']),limit=True,notional=max(0,s.free(px))*.03*LEV,exitmode='ma')
                if p:sg['filled']=True
        s.ma_slots=[x for x in s.ma_slots if not x.get('filled') and x['until']>t]

class Engine21(Mix141,Engine19):
    def __init__(s,*a,**k):super().__init__(*a,**k);s.version='0.9.141+3pp'
