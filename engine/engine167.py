"""pt202u PAPER round2/5: exact B5 plus isolated TP/OFF or MA market switch."""
import copy,math
from engine166 import Engine166,identity166,TF166
from engine8 import TAKER
from engine4 import MMR
class Engine167(Engine166):
 def __init__(s,*a,ma_market_frames=None,market_frames=None,**kw):
  if market_frames:raise ValueError('Break MARKET_FRAMES remains OFF')
  frames=set(ma_market_frames or [])
  if frames-{'15m','1h'}:raise ValueError('Unreviewed MA market frame')
  s.ma_market_frames167=frames;s.ma_market_entries167={};s.ma_market_decisions167=[]
  kw.setdefault('off',['mat:15m']);super().__init__(*a,ma_market_frames=[],market_frames=[],**kw);s.version='0.9.167'
 def target167(s,name,sg):return (sg['f']==15 and name=='ma_slots' and '15m' in s.ma_market_frames167) or (sg['f']==60 and '1h' in s.ma_market_frames167)
 def pending154(s):
  out=super().pending154()
  return [r for r in out if not (r[1] in ('ma_slots','mt_slots') and s.target167(r[1],r[2]))]
 def market_ma167(s,t,o):
  if not s.ma_market_frames167 or getattr(s,'warm',False):return
  s.cancel_off166()
  for name,prefix,group,mode in [('ma_slots','ma','ma','ma'),('mt_slots','mt','mat','mt')]:
   for sg in list(getattr(s,name)):
    if not s.target167(name,sg) or sg.get('filled') or t<sg['frm']:continue
    sg['filled']=True;ev=dict(t=t,signal_time=sg['frm'],expiry=sg['frm']+60000,group=group,frame=sg['f'],period=sg['period'],side='L' if sg['buy'] else 'S',open=o,outcome='EXPIRED',entry_id=None)
    if t<=sg['frm']+60000 and t<sg['until']:
     buy=sg['buy'];s.filter_totals154['placement_attempts']+=1;rs=s.reasons154(buy,o);s.decision155(buy,'market','MA_MARKET167',sg,o)
     if rs:s.count154('placement_rejected',rs,t,buy,'MA_MARKET167');ev.update(outcome='FILTER',reasons=rs)
     elif s.capped(buy,o):ev['outcome']='NORMAL_CAP'
     elif s.rescue_blocks(buy):ev['outcome']='SIDE_BLOCK'
     elif any(p['buy']==buy and p['strat'] in ('pat%d'%sg['f'],'ma%d'%sg['f'],'mt%d'%sg['f']) and abs(p['entry']-o)<100 for p in s.pos):ev['outcome']='DUPLICATE_100'
     else:
      ev.update(pre_free=s.free(o),pre_equity=s.equity(o),pre_exposure=s.side_share(buy,o));prev=s._fr;s._fr=TAKER
      try:p=super().open(t,prefix+str(sg['f']),buy,o,info='SMA%d %s %dm MA_MARKET167'%(sg['period'],'turn' if group=='ma' else 'touch',sg['f']),limit=True,notional=max(0,s.free(o))*.03*3,exitmode=mode)
      finally:s._fr=prev
      if p:
       ev.update(outcome='ENTERED',entry_id=p['id'],entry=p['entry'],qty=p['qty'],fee=p['fee'],tp=p['tps'][0][0]);s.ma_market_entries167[p['id']]=copy.deepcopy(ev);s.entry_audit154[p['id']]['execution167']='MARKET_OPEN_TAKER_NO_SLIP';s.entry_audit154[p['id']]['signal167']=copy.deepcopy(ev)
      else:ev['outcome']='INHERITED_GUARD_OR_SIZE'
    s.ma_market_decisions167.append(ev)
 def exits(s,t,o,h,l,c):
  if not s.ma_market_frames167 or getattr(s,'warm',False):return super().exits(t,o,h,l,c)
  before=len(s.m1_entries162m)+len(s.ma_market_entries167);s.market_m1_162m(t,o);s.market_ma167(t,o)
  if len(s.m1_entries162m)+len(s.ma_market_entries167)>before:
   for side in (True,False):
    worst=l if side else h
    if s.equity(worst)<=sum(p['entry']*p['qty']*MMR for p in s.pos):
     for p in list(s.pos):s.close(t,p,p['n'],worst,'LIQUIDATION (total loss)')
     s.cash=min(s.cash,0);s.liq=True;s.m1_liqbar162m=t;s.log(t,'LIQUIDATED');return
  return super().exits(t,o,h,l,c)
 def limits(s,*a):
  if not s.ma_market_frames167:return super().limits(*a)
  hidden={}
  for name in ('ma_slots','mt_slots'):
   old=getattr(s,name);hidden[name]=[sg for sg in old if s.target167(name,sg)];setattr(s,name,[sg for sg in old if not s.target167(name,sg)])
  try:return super().limits(*a)
  finally:
   for name,rows in hidden.items():getattr(s,name).extend(sg for sg in rows if not sg.get('filled') and sg['frm']+60000>=a[0])
