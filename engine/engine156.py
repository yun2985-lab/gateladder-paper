""".156 supplied source CycleRescue.NEED_HELD -> start-only predicate, rest exact .155/.154A.
StartGate156 is inserted immediately before inherited Mix129 in MRO; Engine29's
unchanged wrapper still sets held/bank metadata and performs .152 repayment.
"""
import math
from engine155 import Engine155
from engine17 import Mix129,START_ROI
from engine5 import TICK
class StartGate156(Mix129):
 def rescue_tick(s,t,o,h,l,c):
     s.tri_tick(t,o,h,l,c)
     if getattr(s,'warm',False): return
     for buy in (True,False):
         r=s.cr[buy]; roi=s.side_roi(buy,c); sd='L' if buy else 'S'
         if r['phase']!='active':
             if roi is not None and roi<=START_ROI:
                 normal=s.normal_auto156(buy)
                 if s.need_held156 and not normal:
                     s.need_held_skips156['L' if buy else 'S']+=1
                     continue
                 r.update(phase='active',started=t,adds=0,ticks=None,lastAdd=None,slot=None,ntr=len(s.trades))
                 held=[p for p in s.pos if p['buy']==buy and p['strat']!='cyc' and p['n']>0]
                 for p in held: p['tps_h']=p['tps']; p['tps']=p['tps'][:p['tpi']]; p['rhold']=True
                 r['held']=[p['id'] for p in held]
                 for (f,key),b in s.bnc.items():
                     pass
                 s.crlog.append(dict(t=t,side=sd,start_roi=round(roi,2),adds=0)); s.rescues.append(dict(t=t,side=sd,roi=round(roi,2),adds=0,held=len(held),normal_auto_count156=len(normal),normal_auto_ids156=[p['id'] for p in normal]))
                 s.log(t,'CYCLE RESCUE START %s ROI %.2f%% · 물린 거래 %d건 100%% 회복까지 보유 · 이 방향 신규 진입 멈춤'%(sd,roi,len(held)))
             continue
         ids=set(r.get('held') or [])
         hp=[p for p in s.pos if p['id'] in ids]
         if roi is None or (not ids and roi>=0) or (ids and not hp):
             r['phase']='watch'; r['slot']=None; r['held']=[]; s.rescues[-1]['done']=t
             s.log(t,'CYCLE RESCUE END %s %s adds %d · 이 방향 자동매매 다시 시작'%(sd,'flat' if roi is None else 'ROI %.2f%%'%roi,r['adds'])); continue
         if ids:
             rec=s._recovery(buy,r,c)
             if rec>=0:
                 at=math.floor(c/TICK)*TICK if buy else math.ceil(c/TICK)*TICK
                 for p in hp: s.close(t,p,p['n'],at,'rescue_hold_100%',limit=True)
                 r['phase']='watch'; r['slot']=None; r['held']=[]; s.rescues[-1]['done']=t
                 s.log(t,'CYCLE RESCUE END %s 손실 100%% 회복 (+%.2f) · 물린 거래 %d건 %.1f에 정리 · adds %d · 이 방향 자동매매 다시 시작'%(sd,rec,len(hp),at,r['adds']))

class Engine156(Engine155,StartGate156):
 def __init__(s,*a,need_held=False,**kw):
  super().__init__(*a,**kw);s.version='0.9.156';s.need_held156=need_held
  s.need_held_skips156={'L':0,'S':0};s.blocked_minutes156={'L':0,'S':0};s.rescue_minutes156=[]
 def normal_auto156(s,buy):
  # Every normal engine-generated position is automatic; runtime has no imported manual records.
  # Explicit flags are honored for source-equivalent tests / any future imported records.
  return [p for p in s.pos if p['buy']==buy and p['n']>0 and p['strat']!='cyc' and p.get('autoEntry',True) and not p.get('manual',False) and 'rescueOwned' not in p]
 def step(s,b):
  active=not getattr(s,'warm',False)
  before=[int(s.rescue_blocks(buy)) for buy in (True,False)] if active else None
  result=super().step(b)
  if active:
   after=[int(s.rescue_blocks(buy)) for buy in (True,False)]
   s.rescue_minutes156.append([b[0],*before,*after])
   for side,blocked in zip(('L','S'),before):s.blocked_minutes156[side]+=blocked
  return result
