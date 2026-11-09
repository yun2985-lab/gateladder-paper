"""Independent .154 variants. Engine29 baseline; optional exact Engine30 rescue semantics.
Filters run minute OPEN before fills; completed HTF update after on_1m, before close-bar signals.
New close-bar limits checked at close; no OHLC future used for minute-open cancellation.
"""
from engine30 import Engine30
from engine4 import SLIP
from collections import deque
import math
DEFAULT=dict(TREND=True,RSI=True,STRETCH=False,UNTIL_ZERO=False,SIDE_BLOCK=True)
class Gates154:
 def __init__(s,seed=None):
  s.h4=deque(maxlen=120);s.day=deque(maxlen=50);s.prev=None;s.gain=s.loss=0.;s.n=0;s.rsi=None;s.asof={};s.agg={}
  if seed:
   for frame in (60,240,1440):
    for b in seed[frame]:s.accept(frame,b)
 def accept(s,f,b):
  if b[0]+f*60000<=s.asof.get(f,0):return
  s.asof[f]=b[0]+f*60000
  if f==240:s.h4.append(b[4])
  elif f==1440:s.day.append(b[4])
  else:
   if s.prev is not None:
    d=b[4]-s.prev;s.n+=1;g=max(d,0);l=max(-d,0)
    if s.n<=14:
     s.gain+=g;s.loss+=l
     if s.n==14:s.gain/=14;s.loss/=14
    else:s.gain=(s.gain*13+g)/14;s.loss=(s.loss*13+l)/14
    if s.n>=14:s.rsi=(50 if s.gain==0 else 100) if s.loss==0 else 100-100/(1+s.gain/s.loss)
   s.prev=b[4]
 def minute(s,b):
  t=b[0]
  for f in (60,240,1440):
   span=f*60000;st=t//span*span;a=s.agg.get(f)
   if a is None or a[0]!=st:a=[st,b[1],b[2],b[3],b[4],1]
   else:a[2]=max(a[2],b[2]);a[3]=min(a[3],b[3]);a[4]=b[4];a[5]+=1
   s.agg[f]=a
   if t+60000==st+span and a[5]==f:s.accept(f,a)
 def values(s):return dict(TREND=sum(s.h4)/120 if len(s.h4)==120 else None,RSI=s.rsi,STRETCH=sum(s.day)/50 if len(s.day)==50 else None)
 def reasons(s,price,buy,flags):
  v=s.values();out=[]
  for key in ('TREND','RSI','STRETCH'):
   if not flags[key]:continue
   x=v[key]
   if x is None:raise RuntimeError('FILTER WARMUP MISSING '+key)
   if key=='TREND':bad=price<x if buy else price>x
   elif key=='RSI':bad=x>75 if buy else x<25
   else:bad=price>x*1.10 if buy else price<x*.90
   if bad:out.append(key)
  return out
class Engine154(Engine30):
 def __init__(s,*a,flags=None,gate_seed=None,**k):
  s.flags154=dict(DEFAULT if flags is None else flags)
  super().__init__(*a,stale_enabled=s.flags154['UNTIL_ZERO'],**k);s.version='0.9.154';s.gates154=Gates154(gate_seed);s.gate_t154=None;s.gate_px154=None
  s.filter_counts154={key:{'placement_rejected':0,'pending_cancelled':0,'blocked_side_minutes':0} for key in ('TREND','RSI','STRETCH')}
  s.filter_totals154=dict(placement_attempts=0,placement_rejected=0,pending_cancelled=0,side_minutes=0);s.normal_counts154={'L':0,'S':0};s.entry_audit154={};s.filter_log154=[]
 def rescue_blocks(s,buy):return s.flags154['SIDE_BLOCK'] and super().rescue_blocks(buy)
 def reasons154(s,buy,price=None):return s.gates154.reasons(s.gate_px154 if price is None else price,buy,s.flags154)
 def count154(s,kind,reasons,t,buy,family):
  s.filter_totals154[kind]+=1
  for reason in reasons:s.filter_counts154[reason][kind]+=1
  if reasons:
   ev=dict(t=t,kind=kind,side='L' if buy else 'S',family=family,reasons=reasons);s.filter_log154.append(ev);s.log(t,'FILTER154 '+str(ev))
 def pending154(s):
  live={p['id'] for p in s.pos};out=[]
  for f in s.sigs:
   for buy in (True,False):
    for sg in s.sigs[f][buy]:
     if not sg.get('void') and not sg.get('filled') and not sg.get('dormant') and sg.get('until',float('inf'))>s.gate_t154:out.append((buy,'pat',sg,'void'))
    for sg in s.fsig[f][buy].values():
     if sg.get('busy') in live:sg['_gate_pending154']=False;continue
     if not sg.get('void') and not sg.get('filled'):out.append((buy,'fib',sg,'void'))
  for key,b in s.bnc.items():
   if b.get('busy') in live:b['_gate_pending154']=False;continue
   if not b.get('done') and b.get('uses',0)<3:out.append((b['buy'],'bounce',b,'done'))
  for name in ('ma_slots','mt_slots'):
   for sg in getattr(s,name,[]):
    if not sg.get('filled') and sg.get('until',float('inf'))>s.gate_t154:out.append((sg['buy'],name,sg,'filled'))
  return out
 def sync154(s):
  if getattr(s,'warm',False) or s.gate_px154 is None:return
  reasons={buy:s.reasons154(buy) for buy in (True,False)}
  for buy,fam,sg,cancelkey in s.pending154():
   old=sg.get('_gate_pending154',False);rs=reasons[buy]
   if not old:s.filter_totals154['placement_attempts']+=1
   if rs:
    s.count154('pending_cancelled' if old else 'placement_rejected',rs,s.gate_t154,buy,fam);sg[cancelkey]=True;sg['_gate_pending154']=False
   else:sg['_gate_pending154']=True
 def step(s,b):
  s.gate_t154=b[0];s.gate_px154=b[1]
  if not getattr(s,'warm',False):
   for buy in (True,False):
    rs=s.reasons154(buy);s.filter_totals154['side_minutes']+=1
    for r in rs:s.filter_counts154[r]['blocked_side_minutes']+=1
   s.sync154()
  return super().step(b)
 def on_1m(s,b):
  super().on_1m(b);s.gates154.minute(b);s.gate_t154=b[0]+60000;s.gate_px154=b[4]
 def pat_bar(s,f,t):
  super().pat_bar(f,t);s.sync154()
 def limits(s,*a):
  s.sync154();return super().limits(*a)
 def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
  active=not getattr(s,'warm',False)
  if active and strat!='cyc':
   rs=s.reasons154(buy,None if limit else px)
   if rs:
    s.filter_totals154['placement_attempts']+=1;s.count154('placement_rejected',rs,t,buy,'fill_guard' if limit else 'market');return None
   if not limit:s.filter_totals154['placement_attempts']+=1
  actual=px if limit else px*(1+SLIP if buy else 1-SLIP)
  audit=dict(t=t,free=s.free(actual),equity=s.equity(actual),side_exposure_pct=s.side_share(buy,px),margin_usage_pct=s.margin_use151(actual),rescue_active=s.cr[buy]['phase']=='active',gate_values=s.gates154.values(),gate_asof=dict(s.gates154.asof)) if active else None
  p=super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
  if p and active:
   audit.update(first_tp=p['tps'][0][0] if p['tps'] else None,entry=p['entry'],n=p['n0'],fee=p['fee']);s.entry_audit154[p['id']]=audit
   if strat!='cyc':s.normal_counts154['L' if buy else 'S']+=1
  return p
