"""GateLadder 0.9.124 = engine13 (0.9.115+3pp, size switch at SWITCH, all user settings: rebate 0.7, maker 0.018%/taker 0.042%,
breakeven OFF, fib 0.722, no SL, fixed 3x) + app 0.9.116..0.9.124 trading changes:
- 0.9.121 DropGuard: no new 1m LONG (line breakout 1m, fib 1m, triangle 1m, RSI 1m) while price (bar open) is >=1% below the
  highest high of the previous 60 1m bars; 1m line-breakout long signals wait (not consumed) meanwhile.
- 0.9.121 1m parallel-channel longs off; line-breakout (not fib) skipped when an open line trade of the same frame/side is within $100.
- 0.9.122/123 loss rescue: auto trades open at rescue start are HELD (their TPs suspended) until 100% recovery
  (held price result incl. pre-start loss + filled rescue adds' closed price profit >= 0), then closed at the current price.
  No user answer to the 24h question in paper -> keeps holding. Without held trades: ROI>=0 ends as before.
- 0.9.124 TP: fib 1m/15m +40, fib 1h +100, line breakout 15m +100, others +50 (new entries).
- 0.9.116 ($1000-away limit cancel/re-place) has no effect on 1m-bar fills -> not modelled. Office app/widgets: display only."""
import math, collections
import engine5 as E5
from engine5 import tat, TICK, LEV
from engine13 import Engine13, SWITCH
M1LONG=('pat1','fib1','tri1','rsi1')
def tp_off(strat):
    if strat in ('fib1','fib15'): return 40
    if strat in ('fib60','pat15'): return 100
    return 50
class Mix124:
    def _init124(s): s._h60=collections.deque(maxlen=60); s._drop=False; s._dropmsg=None
    def on_1m(s,b):
        if not hasattr(s,'_h60'): s._init124()
        o=b[1]; hi=max(s._h60) if s._h60 else 0
        d=hi>0 and (hi-o)/hi>=0.01
        if d!=s._drop and not getattr(s,'warm',False): s.log(b[0],'DROPGUARD %s'%('1시간 고점 -1% · 1분 롱 신규 진입 쉼' if d else '하락 쉬기 끝'))
        s._drop=d
        super().on_1m(b); s._h60.append(b[2])
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        if buy and strat in M1LONG and getattr(s,'_drop',False) and not getattr(s,'warm',False): return None
        return super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
    def set_exits(s,p,mode):
        if mode=='pat':
            d=1 if p['buy'] else -1; x=p['entry']+d*tp_off(p['strat'])
            x=math.ceil(x/TICK-1e-9)*TICK if p['buy'] else math.floor(x/TICK+1e-9)*TICK
            p['tps']=[(x,p['n'])]; p['be']=False
        else: super().set_exits(p,mode)
    def limits(s,t,o,h,l,c):
        hide={}
        if not getattr(s,'warm',False):
            for f in s.sigs:
                blk=t//E5.FR[f]*E5.FR[f]
                for buy in (True,False):
                    keep=[];out=[]
                    for sg in s.sigs[f][buy]:
                        skip=False
                        if f==1 and buy and (sg['rule']=='channel' or getattr(s,'_drop',False)): skip=True
                        elif not sg.get('filled') and not sg.get('void'):
                            px=tat(sg['line'],blk) if 'line' in sg else sg['price']
                            if any(p['strat']=='pat%d'%f and p['buy']==buy and abs(p['entry']-px)<100 for p in s.pos): skip=True
                        (out if skip else keep).append(sg)
                    if out: hide[(f,buy)]=out; s.sigs[f][buy]=keep
        try: super().limits(t,o,h,l,c)
        finally:
            for (f,buy),out in hide.items(): s.sigs[f][buy]=s.sigs[f][buy]+out
    # ---- 0.9.122 rescue hold
    def _recovery(s,buy,r,px):
        sg=1 if buy else -1; ids=set(r.get('held',[])); rec=0.0
        for p in s.pos:
            if p['id'] in ids: rec+=(px-p['entry'])*p['qty']*sg
        for tr in s.trades[r.get('ntr',0):]:
            if tr['strat']=='cyc' and tr['side']==('L' if buy else 'S') and tr['t']>=r['started']:
                rec+=(tr['exit']-tr['entry'])*tr['qty']*sg
        return rec
    def rescue_tick(s,t,o,h,l,c):
        s.tri_tick(t,o,h,l,c)
        if getattr(s,'warm',False): return
        for buy in (True,False):
            r=s.cr[buy]; roi=s.side_roi(buy,c); sd='L' if buy else 'S'
            if r['phase']!='active':
                if roi is not None and roi<=-3:
                    r.update(phase='active',started=t,adds=0,ticks=None,lastAdd=None,slot=None,ntr=len(s.trades))
                    held=[p for p in s.pos if p['buy']==buy and p['strat']!='cyc' and p['n']>0]
                    for p in held: p['tps_h']=p['tps']; p['tps']=p['tps'][:p['tpi']]; p['rhold']=True
                    r['held']=[p['id'] for p in held]
                    s.crlog.append(dict(t=t,side=sd,start_roi=round(roi,2),adds=0)); s.rescues.append(dict(t=t,side=sd,roi=round(roi,2),adds=0,held=len(held)))
                    s.log(t,'CYCLE RESCUE START %s ROI %.2f%% · 물린 거래 %d건 100%% 회복까지 보유'%(sd,roi,len(held)))
                continue
            ids=set(r.get('held') or [])
            hp=[p for p in s.pos if p['id'] in ids]
            if roi is None or (not ids and roi>=0) or (ids and not hp):
                r['phase']='watch'; r['slot']=None; r['held']=[]; s.rescues[-1]['done']=t
                s.log(t,'CYCLE RESCUE END %s %s adds %d'%(sd,'flat' if roi is None else 'ROI %.2f%%'%roi,r['adds'])); continue
            if ids:
                rec=s._recovery(buy,r,c)
                if rec>=0:
                    at=math.floor(c/TICK)*TICK if buy else math.ceil(c/TICK)*TICK
                    for p in hp: s.close(t,p,p['n'],at,'rescue_hold_100%',limit=True)
                    r['phase']='watch'; r['slot']=None; r['held']=[]; s.rescues[-1]['done']=t
                    s.log(t,'CYCLE RESCUE END %s 손실 100%% 회복 (+%.2f) · 물린 거래 %d건 %.1f에 정리 · adds %d'%(sd,rec,len(hp),at,r['adds']))
class Engine15(Mix124,Engine13):
    def __init__(s,*a,**k):
        super().__init__(*a,**k); s.version='0.9.124+3pp'; s._init124()
