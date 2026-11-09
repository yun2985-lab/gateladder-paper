"""Source .159 HELD_BLOCK / START / TP on exact .158 A2-common paper engine.
Engine29 bank/partial repayment remains inherited. Source adopt uses configurable START.
"""
import math
from decimal import Decimal,ROUND_HALF_EVEN
from engine158 import Engine158
from engine156 import StartGate156
from engine29 import D
from engine5 import TICK
class StartGate159(StartGate156):
 def rescue_tick(s,t,o,h,l,c):
     s.tri_tick(t,o,h,l,c)
     if getattr(s,'warm',False): return
     for buy in (True,False):
         r=s.cr[buy]; roi=s.side_roi(buy,c); sd='L' if buy else 'S'
         if r['phase']=='active' and s.held_block159 and roi is not None:s.adopt159(buy,r,t,c)
         if r['phase']!='active':
             if roi is not None and roi<=s.start_roi159:
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
                 s.crlog.append(dict(t=t,side=sd,start_roi=round(roi,2),adds=0)); s.rescues.append(dict(t=t,side=sd,roi=round(roi,2),adds=0,held=len(held),normal_auto_count156=len(normal),normal_auto_ids156=[p['id'] for p in normal],held_initial_g0_159={str(p['id']):str(s.realized_gross152.get(p['id'],D(0))) for p in held},initial_held_quantities159={str(p['id']):p['n'] for p in held},initial_held_trade_index159=len(s.trades)))
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

def trade_roi159(mark,entry,buy):
 if entry<=0 or mark<=0:return None
 return ((D(mark)/D(entry)).quantize(D('0.000000000001'),rounding=ROUND_HALF_EVEN)-1)*100*3*(1 if buy else -1)

class Engine159(Engine158,StartGate159):
 def __init__(s,*a,held_block=False,start_roi=-1.5,rescue_tp=38,**kw):
  super().__init__(*a,**kw)
  if start_roi not in (-1.5,-3) or rescue_tp not in (38,60):raise ValueError('Unreviewed159settings')
  s.version='0.9.159';s.held_block159=held_block;s.start_roi159=start_roi;s.rescue_tp159=rescue_tp
  s.adoption_log159=[];s.adoption_rows159=[];s.adoption_batches159=0;s.adoption_contracts159=0
 def held_open159(s,buy,r=None):
  r=s.cr[buy] if r is None else r;ids=set(r.get('held',[]))
  return [p for p in s.pos if p['id'] in ids and p['buy']==buy and p['strat']!='cyc' and p['n']>0]
 def rescue_blocks(s,buy):
  return super().rescue_blocks(buy) and (not s.held_block159 or bool(s.held_open159(buy)))
 def set_exits(s,p,mode):
  super().set_exits(p,mode)
  if mode=='cyc' and s.rescue_tp159!=38:
   target=p['entry']+(s.rescue_tp159 if p['buy'] else -s.rescue_tp159)
   target=(math.ceil(target/TICK-1e-9) if p['buy'] else math.floor(target/TICK+1e-9))*TICK
   p['tps']=[(target,p['n'])];p['tpi']=0
 def adopt159(s,buy,r,t,mark):
  if not s.held_block159 or r['phase']!='active' or mark<=0:return 0
  have=set(r.get('held',[]));count=0;session=s._session_record152(buy,r)
  for p in s.normal_auto156(buy):
   if p['id'] in have or p.get('rhold'):continue
   roi=trade_roi159(mark,p['entry'],buy)
   if roi is None or roi>D(s.start_roi159):continue
   cash_before=s.cash;fees_before=s.fees;g0=s.realized_gross152.get(p['id'],D(0));before=s.bank152(buy,r);old_ids=list(r.get('held',[]));old_g0={str(k):str(v) for k,v in r.get('held_g0_152',{}).items()}
   p['tps_h']=list(p['tps']);p['tps']=p['tps'][:p['tpi']];p['rhold']=True
   r.setdefault('held',[]).append(p['id']);r.setdefault('held_g0_152',{})[p['id']]=g0;have.add(p['id'])
   ev=dict(t=t,decision_asof=t+60000,side='L' if buy else 'S',session=r['started'],id=p['id'],entry=p['entry'],remaining_contracts=p['n'],initial_contracts=p['n0'],mark=mark,roi=str(roi),threshold=str(s.start_roi159),g0=str(g0),trade_index_before=len(s.trades),cash_before=cash_before,cash_after=s.cash,fees_before=fees_before,fees_after=s.fees,bank_before=str(before),bank_after=str(s.bank152(buy,r)),held_before=old_ids,held_after=list(r['held']),old_g0=old_g0)
   assert s.bank152(buy,r)==before and s.cash==cash_before and s.fees==fees_before
   s.adoption_log159.append(ev);s.adoption_rows159.append(ev);s.adoption_contracts159+=p['n'];count+=1
   if session is not None:
    session.setdefault('adopted_held_ids159',[]).append(p['id']);session.setdefault('adopted_held_g0_159',{})[str(p['id'])]=str(g0)
   s.log(t,'HELD ADOPT159 '+str(ev))
  if count:s.adoption_batches159+=1
  return count
