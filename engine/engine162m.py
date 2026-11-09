"""pt172u insertion paper-only next-open M1 PatternRun market experiment on frozen B3."""
import math,copy
from engine162 import Engine162
from engine5 import tat,TICK,LEV,RNAME
from engine8 import TAKER
from engine4 import MMR
FAMILIES162M=('trend','flat','learned','manual')
class Engine162M(Engine162):
 def __init__(s,*a,m1_market=False,m1_break_tp=50,**kw):
  if m1_break_tp not in (30,50,80,120,200,300):raise ValueError('Unreviewed M1 TP')
  kw.setdefault('start_roi',-2);s.m1_market162m=m1_market;s.m1_tp162m=m1_break_tp;s.m1_context162m=None;s.m1_decisions162m=[];s.m1_entries162m={};s.m1_consumed162m=set();s.m1_liqbar162m=None
  super().__init__(*a,**kw);s.version='0.9.162M'
 def target162m(s,sg):return sg.get('rule') in FAMILIES162M and 'line' in sg
 def sync154(s):
  if not s.m1_market162m or getattr(s,'warm',False):return super().sync154()
  old={b:s.sigs[1][b] for b in (True,False)}
  for b in old:s.sigs[1][b]=[x for x in old[b] if not s.target162m(x)]
  try:return super().sync154()
  finally:
   for b in old:s.sigs[1][b]=old[b]
 def set_exits(s,p,mode):
  if mode!='m1_market162m':return super().set_exits(p,mode)
  x=p['entry']+(s.m1_tp162m if p['buy'] else -s.m1_tp162m);x=(math.ceil(x/TICK-1e-9) if p['buy'] else math.floor(x/TICK+1e-9))*TICK
  p['tps']=[(x,p['n'])];p['be']=False
 def market_m1_162m(s,t,o):
  if not s.m1_market162m or getattr(s,'warm',False):return
  for buy in (True,False):
   for sg in list(s.sigs[1][buy]):
    if not s.target162m(sg) or sg.get('m1_consumed162m') or sg.get('filled') or sg.get('void') or t<sg['frm']:continue
    sg['m1_consumed162m']=True;sg['filled']=True
    key=(buy,sg['key'])
    if key in s.m1_consumed162m:continue
    s.m1_consumed162m.add(key)
    ev=dict(t=t,side='L' if buy else 'S',family=sg['rule'],signal_id=sg['key'],signal_time=sg['frm'],expiry=min(sg['until'],sg['frm']+60000),open=o,line=copy.deepcopy(sg['line']),confirmation_tol=sg['tol'],outcome=None,entry_id=None)
    if t!=sg['frm'] or t>=sg['until']:ev['outcome']='EXPIRED'
    else:
     v=tat(sg['line'],t);ev['line_at_open']=v
     if not (o>v if buy else o<v):ev['outcome']='INSIDE_OR_EQUAL'
     else:
      s.filter_totals154['placement_attempts']+=1;rs=s.reasons154(buy,o);s.decision155(buy,'market','m1_market162m',sg,o)
      if rs:s.count154('placement_rejected',rs,t,buy,'m1_market162m');ev['outcome']='FILTER';ev['reasons']=rs
      elif s.capped(buy,o):ev['outcome']='NORMAL_CAP'
      elif s.rescue_blocks(buy):ev['outcome']='SIDE_BLOCK'
      elif any(p['buy']==buy and p['strat']=='pat1' and abs(p['entry']-o)<100 for p in s.pos):ev['outcome']='DUPLICATE_100'
      else:
       ev.update(trade_index_before=len(s.trades),pre_free=s.free(o),pre_equity=s.equity(o),pre_exposure=s.side_share(buy,o));prev=s._fr;s._fr=TAKER;s.m1_context162m=ev
       try:
        # Exact requested OPEN, no inherited market SLIP. Normal guards remain
        # in inherited chain; execution fee explicitly TAKER through _fr.
        p=super().open(t,'pat1',buy,o,info='%s 1m M1MARKET %s signal=%s'%('L' if buy else 'S',sg['rule'],sg['key']),limit=True,notional=max(0,s.free(o))*.04*LEV,exitmode='m1_market162m')
       finally:s._fr=prev;s.m1_context162m=None
       if p:
        ev['outcome']='ENTERED';ev['entry_id']=p['id'];ev.update(entry=p['entry'],qty=p['qty'],entry_fee=p['fee'],tp=p['tps'][0][0]);p['m1_market162m']=True;p['m1_signal162m']=copy.deepcopy(ev);s.m1_entries162m[p['id']]=copy.deepcopy(ev)
        s.entry_audit154[p['id']]['execution162m']='MARKET_NEXT_OPEN_TAKER_NO_SLIP';s.entry_audit154[p['id']]['signal162m']=copy.deepcopy(ev)
       else:ev['outcome']='INHERITED_GUARD_OR_SIZE'
    s.m1_decisions162m.append(ev);s.log(t,'M1MARKET162M '+str(ev))
 def exits(s,t,o,h,l,c):
  # Called after existing current-open DropGuard update, BEFORE current-bar TPs.
  # Thus new open-priced entries may TP in this same bar; other modes unchanged.
  before=len(s.m1_entries162m);s.market_m1_162m(t,o)
  if len(s.m1_entries162m)>before:
   for side in (True,False):
    worst=l if side else h
    if s.equity(worst)<=sum(p['entry']*p['qty']*MMR for p in s.pos):
     for p in list(s.pos):s.close(t,p,p['n'],worst,'LIQUIDATION (total loss)')
     s.cash=min(s.cash,0);s.liq=True;s.m1_liqbar162m=t;s.log(t,'LIQUIDATED');return
  return super().exits(t,o,h,l,c)
 def limits(s,t,*a):
  if s.m1_liqbar162m!=t:return super().limits(t,*a)
 def breakouts(s,t,*a):
  if s.m1_liqbar162m!=t:return super().breakouts(t,*a)
 def overlap(s,t,*a):
  if s.m1_liqbar162m!=t:return super().overlap(t,*a)
 def rescue_tick(s,t,*a):
  if s.m1_liqbar162m!=t:return super().rescue_tick(t,*a)
