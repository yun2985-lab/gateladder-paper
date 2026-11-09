"""pt196u TF/group TP and OFF overlay on exact B4. Annual fees unchanged."""
import re,math
from engine164 import Engine164
TF166={15:'15m',60:'1h',240:'4h'}
def identity166(strat,info=''):
 m=re.fullmatch(r'(ma|mt|fib|pat)(\d+)',strat)
 if not m:
  other=re.fullmatch(r'([a-zA-Z_]+)(\d+)',strat)
  return ('other',int(other[2]),None) if other else None
 group={'ma':'ma','mt':'mat','fib':'fib','pat':'break'}[m[1]];f=int(m[2]);p=re.search(r'SMA(20|60|120)\b',info)
 return group,f,int(p[1]) if p else None
class Engine166(Engine164):
 def __init__(s,*a,tp_set=None,off=None,market_frames=None,ma_market_frames=None,**kw):
  if market_frames or ma_market_frames:raise ValueError('Future market-frame switches MUST remain OFF')
  s.tp_set166=dict(tp_set or {});s.off166=set(off or []);s.off_events166=[];s.off_seen166=set();s.origins166={}
  for k,v in s.tp_set166.items():
   if not re.fullmatch(r'(ma|mat|fib|break|other):(15m|1h|4h)',k) or not isinstance(v,(int,float)) or v<=0:raise ValueError('Unreviewed TP_SET')
  for k in s.off166:
   if not re.fullmatch(r'(ma(?:20|60|120)?|mat(?:20|60|120)?|fib|break|other):(15m|1h|4h)',k):raise ValueError('Unreviewed OFF')
  super().__init__(*a,**kw);s.version='0.9.166'
 def disabled166(s,g,f,p=None):
  tf=TF166.get(f);return bool(tf and (f'{g}:{tf}' in s.off166 or (p is not None and f'{g}{p}:{tf}' in s.off166)))
 def cancel_off166(s):
  if not s.off166:return
  for name,g in (('ma_slots','ma'),('mt_slots','mat')):
   for sg in getattr(s,name,[]):
    if not sg.get('filled') and s.disabled166(g,sg['f'],sg.get('period')):
     sg['filled']=True;key=(g,sg['f'],sg.get('period'),sg['frm'],sg['buy'])
     if key not in s.off_seen166:s.off_seen166.add(key);s.off_events166.append(dict(group=g,frame=sg['f'],period=sg.get('period'),signal_time=sg['frm'],side='L' if sg['buy'] else 'S',reason='PATTERN_OFF'))
  for f in getattr(s,'sigs',{}):
   for buy in (True,False):
    for group,signals in [('break',s.sigs[f][buy]),('fib',list(s.fsig[f][buy].values()))]:
     for sg in signals:
      if not sg.get('void') and not sg.get('filled') and s.disabled166(group,f):sg['void']=True;s.off_events166.append(dict(group=group,frame=f,period=None,signal_time=sg.get('frm'),side='L' if buy else 'S',reason='PATTERN_OFF'))
  for sg in getattr(s,'bnc',{}).values():
   if not sg.get('done') and s.disabled166('other',sg.get('f')):sg['done']=True
 def pending154(s):s.cancel_off166();return super().pending154()
 def pat_bar(s,*a):
  r=super().pat_bar(*a);s.cancel_off166();return r
 def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
  ident=identity166(strat,info)
  if ident and s.disabled166(*ident):return None
  p=super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
  if p and ident:s.origins166[p['id']]=dict(group=ident[0],frame=ident[1],period=ident[2],info=info)
  return p
 def set_exits(s,p,mode):
  ident=identity166(p['strat'],p['info']);key=f'{ident[0]}:{TF166.get(ident[1])}' if ident else None
  if key not in s.tp_set166:return super().set_exits(p,mode)
  d=1 if p['buy'] else -1;x=p['entry']+d*s.tp_set166[key];x=(math.ceil(x/.1-1e-9) if d==1 else math.floor(x/.1+1e-9))*.1;p['tps']=[(x,p['n'])];p['be']=False
