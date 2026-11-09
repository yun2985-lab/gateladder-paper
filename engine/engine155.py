"""Isolated .155: inherit exact .154A execution/rescue; completed daily POS30 and RSI bounds."""
from collections import deque
import copy
from engine154 import Engine154,Gates154,DEFAULT

class Gates155(Gates154):
 def __init__(s,seed=None,upper=75,lower=25,pos30=False):
  s.daily_hl155=deque(maxlen=30);s.upper155=upper;s.lower155=lower;s.pos_enabled155=pos30
  super().__init__(seed)
 def accept(s,f,b):
  fresh=b[0]+f*60000>s.asof.get(f,0)
  super().accept(f,b)
  if f==1440 and fresh:s.daily_hl155.append((b[2],b[3]))
 def values(s):
  v=super().values();v.update(POS30_H=max(x[0] for x in s.daily_hl155) if len(s.daily_hl155)==30 else None,POS30_L=min(x[1] for x in s.daily_hl155) if len(s.daily_hl155)==30 else None);return v
 def reasons(s,price,buy,flags):
  out=super().reasons(price,buy,dict(flags,RSI=False))
  if flags['RSI']:
   if s.rsi is None:raise RuntimeError('FILTER WARMUP MISSING RSI')
   if (s.rsi>s.upper155 if buy else s.rsi<s.lower155):out.append('RSI')
  if s.pos_enabled155:
   v=s.values();h,l=v['POS30_H'],v['POS30_L']
   if h is None or l is None:raise RuntimeError('FILTER WARMUP MISSING POS30')
   if h<=l:raise RuntimeError('POS30 INVALID ZERO/NEGATIVE RANGE')
   pos=(price-l)/(h-l)*100
   if (pos>90 if buy else pos<10):out.append('POS30')
  return [key for key in ('TREND','RSI','STRETCH','POS30') if key in out]

class Engine155(Engine154):
 def __init__(s,*a,rsi_upper=75,rsi_lower=25,pos30=False,**kw):
  seed=kw.get('gate_seed');super().__init__(*a,**kw)
  s.gates154=Gates155(seed,rsi_upper,rsi_lower,pos30);s.version='0.9.155'
  s.filter_counts154['POS30']={k:0 for k in ('placement_rejected','pending_cancelled','blocked_side_minutes')}
  s.blocked_unique_side_minutes155=0;s.candidate_audit155=[];s.candidate_seq155=0
  s.gate_minutes155=[]
  s.settings155=dict(rsi_upper=rsi_upper,rsi_lower=rsi_lower,pos30=pos30)
 def decision155(s,buy,kind,family,signal=None,price=None):
  px=s.gate_px154 if price is None else price;v=s.gates154.values();h,l=v['POS30_H'],v['POS30_L']
  s.candidate_seq155+=1
  ev=dict(seq=s.candidate_seq155,t=s.gate_t154,kind=kind,side='L' if buy else 'S',family=family,price=px,values=v,asof=dict(s.gates154.asof),reasons=s.reasons154(buy,px),pos30=(px-l)/(h-l)*100 if h is not None and h>l else None)
  if signal is not None:ev['signal']=copy.deepcopy({k:v for k,v in signal.items() if k!='_gate_pending154'})
  s.candidate_audit155.append(ev);return ev
 def sync154(s):
  if getattr(s,'warm',False) or s.gate_px154 is None:return
  reasons={buy:s.reasons154(buy) for buy in (True,False)}
  for buy,fam,sg,cancelkey in s.pending154():
   old=sg.get('_gate_pending154',False);rs=reasons[buy]
   if not old:
    s.filter_totals154['placement_attempts']+=1
    ev=s.decision155(buy,'placement',fam,sg);sg['_candidate155']=ev['seq']
   elif rs:s.decision155(buy,'pending_cancelled',fam,sg)
   if rs:
    s.count154('pending_cancelled' if old else 'placement_rejected',rs,s.gate_t154,buy,fam);sg[cancelkey]=True;sg['_gate_pending154']=False
   else:sg['_gate_pending154']=True
 def step(s,b):
  if not getattr(s,'warm',False):
   v=s.gates154.values();reasons=[s.gates154.reasons(b[1],buy,s.flags154) for buy in (True,False)]
   s.gate_minutes155.append([b[0],b[1],v['TREND'],v['RSI'],v['POS30_H'],v['POS30_L'],s.gates154.asof.get(60),s.gates154.asof.get(240),s.gates154.asof.get(1440),*['|'.join(rs) for rs in reasons]])
   s.blocked_unique_side_minutes155+=sum(bool(rs) for rs in reasons)
  return super().step(b)
 def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
  if not getattr(s,'warm',False) and strat!='cyc':s.decision155(buy,'fill_guard' if limit else 'market',strat,dict(info=info,limit=limit,order_price=px),None if limit else px)
  return super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
