"""0.9.169 PAPER (pt212u + t213): exact B6 (Engine167 with .167 G1 config) plus rescue-add-only survival rules and TrendNet.
Every override delegates to the unchanged Engine167 path when its rule is OFF (all rules OFF == Engine167).
Rules (rescue adds = strat 'cyc' positions that are not TrendNet adds; normal entry rules unchanged):
 pause_tf '4h'|'1d' : closed-bar SMA (4h close SMA120 / UTC-day close SMA50). Minute close > SMA => UP => no NEW short-rescue
   add orders (resting short slot cancelled); <= SMA => DOWN => no new long-rescue adds. Filled adds keep +60 TP / repay.
   Regime is computed at each minute END with that minute close and the last SMA bar CLOSED by then; placement (3m close)
   uses that end-of-minute regime, resting-slot fills in the next minute see it first (cancel before fill check).
 stale_days 30      : filled rescue add open > 30 days => market close (taker, mark -/+0.05% like repay152) at minute close.
 loss_cap_pct 10    : per side, sum of losing open rescue-add unrealized PnL > 10% equity => market close oldest losing adds.
 opp_bank           : rescue-add TP price gross on side A, while side B has an add older than 7d, is MOVED into B's repay bank
   (and removed from A's .152 HELD bank). Every closed 3m, B's oldest >7d losing adds are closed k contracts at mark-/+0.05%
   (taker) with k=floor(bank/unit), unit=.152 formula; the loss is paid from the bank (not B's own HELD bank).
 net_tf '4h'|'1d'   : TrendNet. Side in trend direction (UP=>L, DOWN=>S) with no active real rescue session gets a net
   session: first add limit at minute close -/+0.3%, then the same 3m 3-tick add rule, 0.3% gap vs open net adds, max 20
   open net adds, margin40 pre-order guard, net_size_pct of available (3 or 4), TP +60. Trend flip / real rescue start ends
   the net session (no new adds; filled adds wait for TP). Net adds are excluded from side ROI / rescue recovery accounting.
"""
import math,bisect,pickle
from decimal import Decimal,ROUND_FLOOR
from engine167 import Engine167
from engine158 import near158
from engine5 import cr_step,LEV,TICK
from engine8 import TAKER
from engine29 import D,UNIT
DAY=86400000
FORCED=('stale30d_169','losscap10_169','opprepay_169')
def _z():return {'L':0,'S':0}
class Engine169(Engine167):
 def __init__(s,*a,pause_tf=None,stale_days=None,opp_bank=False,opp_age_days=7,loss_cap_pct=None,net_tf=None,net_size_pct=3,sma_table=None,**kw):
  super().__init__(*a,**kw);s.version='0.9.169'
  assert pause_tf in (None,'4h','1d') and net_tf in (None,'4h','1d') and net_size_pct in (3,4)
  s.p169=dict(pause_tf=pause_tf,stale_days=stale_days,opp_bank=opp_bank,opp_age_days=opp_age_days,loss_cap_pct=loss_cap_pct,net_tf=net_tf,net_size_pct=net_size_pct)
  s.on169=bool(pause_tf or stale_days or opp_bank or loss_cap_pct or net_tf);s.sma169={}
  if pause_tf or net_tf:
   tab=pickle.load(open(sma_table,'rb'))
   for tf in {pause_tf,net_tf}-{None}:s.sma169[tf]=(list(tab[tf]['close_t']),list(tab[tf]['sma']))
  s.state169={};s.fill_state169={};s.end_state169={}
  s.c169=dict(pause_minutes=_z(),pause_minutes_rescue_active=_z(),pause_slot_cancels=_z(),pause_suppressed_placements=_z(),regime_changes=0,
   net_sessions=_z(),net_sessions_without_stuck_normal=_z(),net_sessions_without_any_normal=_z(),net_adds=_z(),net_margin_skips=_z(),net_gap_skips=_z(),net_first_limits=_z(),net_minutes_on=_z(),
   opp_deposits=_z(),opp_repay_events=_z(),opp_repay_contracts=_z())
  s.opp_deposit_gross169={'L':D(0),'S':D(0)};s.oppbank169={True:D(0),False:D(0)};s.bank_adj169={}
  s.forced169=[];s.net169={b:dict(on=False,sid=None,slot=None,ticks=None) for b in (True,False)};s.net_sessions169=[]
 # ---------- helpers
 def _w(s):return getattr(s,'warm',False)
 def regime169(s,tf,tend,c):
  ts,sm=s.sma169[tf];i=bisect.bisect_right(ts,tend)-1
  if i<0 or sm[i] is None:return None
  return 'UP' if c>sm[i] else 'DOWN'
 def paused169(s,buy,state):
  g=state.get(s.p169['pause_tf']);return (g=='UP' and not buy) or (g=='DOWN' and buy)
 def adds169(s,buy):return [p for p in s.pos if p['strat']=='cyc' and p['buy']==buy and p['n']>0 and not p.get('net169')]
 def netadds169(s,buy):return [p for p in s.pos if p['strat']=='cyc' and p['buy']==buy and p['n']>0 and p.get('net169')]
 # ---------- minute driver
 def step(s,b):
  if not s.on169 or s._w():return super().step(b)
  s.fill_state169=s.state169;tend=b[0]+60000;c=b[4]
  s.end_state169={tf:s.regime169(tf,tend,c) for tf in s.sma169}
  res=super().step(b)
  if s.state169 and s.end_state169!=s.state169:s.c169['regime_changes']+=1
  s.state169=s.end_state169
  for buy in (True,False):
   sd='L' if buy else 'S'
   if s.p169['pause_tf'] and s.paused169(buy,s.end_state169):
    s.c169['pause_minutes'][sd]+=1
    if s.cr[buy]['phase']=='active':s.c169['pause_minutes_rescue_active'][sd]+=1
  if s.p169['net_tf'] and not s.liq:s.net_minute169(tend,c)
  return res
 # ---------- trend pause (+ net) on placement/fill
 def cr_bar(s,t):
  if not s.on169 or s._w():return super().cr_bar(t)
  if s.p169['pause_tf']:s.cr_bar_pause169(t)
  else:super().cr_bar(t)
  if s.p169['net_tf']:s.net_bar169(t)
 def cr_bar_pause169(s,t):
  # Exact Engine158.cr_bar with ONE inserted pause check after the 3-tick hit (ticks keep updating while paused).
  bars=s.pb[3];cfg=s.rescue_settings158;cap=cfg['max_open'];gap=cfg['gap_ratio'];threshold=cfg['margin_threshold_pct']
  for buy in (True,False):
   r=s.cr[buy]
   if r['slot'] and t-r['slot']['blk']>=2*180000:r['slot']=None
   if r['phase']!='active' or len(bars)<40:continue
   signal=(r.get('started'),t)
   if s.margin50_last_block[buy]==signal:continue
   k=len(bars)-1
   if r['ticks'] is None:r['ticks']={};cr_step(r['ticks'],bars,k,buy);continue
   hit=cr_step(r['ticks'],bars,k,buy)
   if not hit or r['slot']:continue
   if s.paused169(buy,s.end_state169):
    sd='L' if buy else 'S';s.c169['pause_suppressed_placements'][sd]+=1;s.log(t,'PAUSE169 %s add suppressed (trend %s)'%(sd,s.end_state169.get(s.p169['pause_tf'])));continue
   adds=s.open_adds(buy)
   if len(adds)>=cap:continue
   px=bars[k][4];px=math.floor(px/TICK)*TICK if buy else math.ceil(px/TICK)*TICK
   near=near158([p['entry'] for p in adds],px,gap)
   if near is not None:
    s.log(t,'CYCLE add skipped %.1f within %g%% of open add %.1f'%(px,gap*100,near));continue
   mark=bars[k][4];mu=s.margin_use151(mark)
   audit=dict(t=t,side='L' if buy else 'S',session=r.get('started'),price=px,mark=mark,margin_use_pct=mu,equity=s.equity(mark),available=s.free(mark),open_ids=[p['id'] for p in adds],open_prices=[p['entry'] for p in adds],open_count=len(adds),max_open=cap,gap_ratio=gap,threshold_pct=threshold)
   if mu is not None and mu>=threshold:
    sd='L' if buy else 'S';s.margin50_skips+=1;s.margin50_skips_by_side[sd]+=1;s.margin50_last_block[buy]=signal
    s.log(t,'MARGIN%d_SKIP %s count%d usage%.10f equity%.8f available%.8f next3tick-only'%(threshold,sd,s.margin50_skips,mu,s.equity(mark),s.free(mark)))
    audit['decision']='MARGIN_SKIP';s.rescue_order_audit158.append(audit);continue
   r['slot']=dict(px=px,blk=t);audit['decision']='PLACE';s.rescue_order_audit158.append(audit)
   s.log(t,'CYCLE add limit %s %.1f (3m 3-tick; open %d/%d, gap%g%%)'%('L' if buy else 'S',px,len(adds),cap,gap*100))
 def cr_fill(s,t,o,h,l,c):
  if s.on169 and not s._w() and s.p169['pause_tf']:
   for buy in (True,False):
    if s.cr[buy]['slot'] and s.paused169(buy,s.fill_state169):
     sd='L' if buy else 'S';s.cr[buy]['slot']=None;s.c169['pause_slot_cancels'][sd]+=1;s.log(t,'PAUSE169 %s resting add limit cancelled'%sd)
  super().cr_fill(t,o,h,l,c)
  if s.on169 and not s._w() and s.p169['net_tf']:s.net_fill169(t,o,h,l,c)
 # ---------- TrendNet
 def net_can_place169(s,buy,px,mark,t):
  sd='L' if buy else 'S';adds=s.netadds169(buy)
  if len(adds)>=s.rescue_settings158['max_open']:return False
  near=near158([p['entry'] for p in adds],px,s.rescue_settings158['gap_ratio'])
  if near is not None:s.c169['net_gap_skips'][sd]+=1;return False
  mu=s.margin_use151(mark)
  if mu is not None and mu>=s.rescue_settings158['margin_threshold_pct']:
   s.c169['net_margin_skips'][sd]+=1;s.log(t,'NETSKIP169 %s margin %.4f'%(sd,mu));return False
  return True
 def net_minute169(s,tend,c):
  g=s.end_state169.get(s.p169['net_tf'])
  for buy in (True,False):
   n=s.net169[buy];sd='L' if buy else 'S'
   trend=g==('UP' if buy else 'DOWN');elig=trend and s.cr[buy]['phase']!='active'
   if n['on'] and not elig:
    rec=next(x for x in reversed(s.net_sessions169) if x['sid']==n['sid']);rec.update(done=tend,end_reason='trend_off' if not trend else 'real_rescue_active')
    n.update(on=False,slot=None,ticks=None);s.log(tend,'NET169 END %s %s'%(sd,rec['end_reason']))
   elif elig and not n['on']:
    normals=[p for p in s.pos if p['buy']==buy and p['strat']!='cyc' and p['n']>0]
    stuck=[p for p in normals if (c-p['entry'])*(1 if buy else -1)<0]
    sid=-tend;n.update(on=True,sid=sid,slot=None,ticks=None)
    s.net_sessions169.append(dict(sid=sid,side=sd,t=tend,price=c,normal_open=len(normals),stuck_normal=len(stuck),adds=0))
    s.c169['net_sessions'][sd]+=1;s.c169['net_sessions_without_stuck_normal'][sd]+=not stuck;s.c169['net_sessions_without_any_normal'][sd]+=not normals
    px=c*(1-.003) if buy else c*(1+.003);px=math.floor(px/TICK)*TICK if buy else math.ceil(px/TICK)*TICK
    if s.net_can_place169(buy,px,c,tend):n['slot']=dict(px=px,blk=tend,first=True);s.c169['net_first_limits'][sd]+=1
    s.log(tend,'NET169 START %s trend %s price %.1f stuck_normal %d first_limit %s'%(sd,g,c,len(stuck),n['slot']['px'] if n['slot'] else None))
   if n['on']:s.c169['net_minutes_on'][sd]+=1
 def net_bar169(s,t):
  bars=s.pb[3]
  for buy in (True,False):
   n=s.net169[buy]
   if n['slot'] and not n['slot'].get('first') and t-n['slot']['blk']>=2*180000:n['slot']=None
   if not n['on'] or len(bars)<40:continue
   k=len(bars)-1
   if n['ticks'] is None:n['ticks']={};cr_step(n['ticks'],bars,k,buy);continue
   hit=cr_step(n['ticks'],bars,k,buy)
   if not hit or (n['slot'] and not n['slot'].get('first')):continue
   px=bars[k][4];px=math.floor(px/TICK)*TICK if buy else math.ceil(px/TICK)*TICK
   if s.net_can_place169(buy,px,bars[k][4],t):n['slot']=dict(px=px,blk=t);s.log(t,'NET169 add limit %s %.1f'%('L' if buy else 'S',px))
 def net_fill169(s,t,o,h,l,c):
  for buy in (True,False):
   n=s.net169[buy];sl=n['slot']
   if not sl or not n['on'] or t<sl['blk']:continue
   if l<=sl['px'] if buy else h>=sl['px']:
    N=max(0,s.free(sl['px']))*.02*LEV;old=s.rescue_settings158['size_available_pct'];s.rescue_settings158['size_available_pct']=s.p169['net_size_pct']
    try:p=s.open(t,'cyc',buy,sl['px'],info='trend net add %s @%.1f'%('L' if buy else 'S',sl['px']),limit=True,notional=N,exitmode='cyc')
    finally:s.rescue_settings158['size_available_pct']=old
    n['slot']=None
    if p:
     p['net169']=True;p['cycle_session152']=n['sid'];sd='L' if buy else 'S';s.c169['net_adds'][sd]+=1
     rec=next(x for x in reversed(s.net_sessions169) if x['sid']==n['sid']);rec['adds']+=1
     if s.rescue_size_audit158 and s.rescue_size_audit158[-1].get('id')==p['id']:s.rescue_size_audit158[-1].update(net169=True,session=n['sid'])
     s.log(t,'NET169 ADD OPEN %s %.1f %dct'%(sd,p['entry'],p['n']))
 def side_roi(s,buy,px):
  if not s.p169['net_tf']:return super().side_roi(buy,px)
  ps=[p for p in s.pos if p['buy']==buy and not p.get('net169')]
  if not ps:return None
  n=sum(p['n'] for p in ps);avg=sum(p['entry']*p['n'] for p in ps)/n
  return (px/avg-1)*100*LEV*(1 if buy else -1)
 def _recovery(s,buy,r,px):
  rec=super()._recovery(buy,r,px)
  if s.p169['net_tf']:
   sg=1 if buy else -1;sd='L' if buy else 'S'
   for tr in s.trades[r.get('ntr',0):]:
    if tr.get('net169') and tr['strat']=='cyc' and tr['side']==sd and tr['t']>=r['started']:rec-=(tr['exit']-tr['entry'])*tr['qty']*sg
  return rec
 # ---------- closes / banks
 def close(s,t,p,n,price,why,limit=False):
  before=len(s.trades);res=super().close(t,p,n,price,why,limit)
  if not s.on169 or s._w():return res
  trs=s.trades[before:]
  if p.get('net169'):
   for tr in trs:tr['net169']=True
  if s.p169['opp_bank'] and p['strat']=='cyc' and not p.get('net169') and str(why).startswith('tp'):
   g=sum((D(tr.get('gross_exact152','0')) for tr in trs),D(0));other=not p['buy']
   if g>0 and any(t-q['t']>s.p169['opp_age_days']*DAY for q in s.adds169(other)):
    so='L' if other else 'S';s.oppbank169[other]+=g;s.opp_deposit_gross169[so]+=g;s.c169['opp_deposits'][so]+=1
    key=(p['buy'],p.get('cycle_session152'));s.bank_adj169[key]=s.bank_adj169.get(key,D(0))-g
    for tr in trs:tr['bank_adj169']=str(-g)
    s.log(t,'OPPBANK169 deposit to %s %s bank %s'%(so,g,s.oppbank169[other]))
  return res
 def bank152(s,buy,r):
  b=super().bank152(buy,r)
  return b+s.bank_adj169.get((buy,r.get('started')),D(0)) if s.bank_adj169 else b
 def force169(s,t,p,k,mark,why):
  px=float(D(mark)*(D('0.9995') if p['buy'] else D('1.0005')));before=len(s.trades);old=getattr(s,'_fr',None);s._fr=TAKER;age=(t-p['t'])/DAY
  try:s.close(t,p,k,px,why,limit=True)
  finally:s._fr=old
  trs=s.trades[before:];g=sum((D(tr.get('gross_exact152','0')) for tr in trs),D(0))
  for tr in trs:tr['forced169']=why
  if p['n']>0 and p['tpi']<len(p['tps']):p['tps']=p['tps'][:p['tpi']]+[(p['tps'][p['tpi']][0],p['n'])]
  row=dict(t=t,why=why,id=p['id'],side='L' if p['buy'] else 'S',entry=p['entry'],add_t=p['t'],age_days=round(age,6),contracts=k,mark=mark,price=px,gross=str(g),pnl=round(sum(tr['pnl'] for tr in trs),6),pnl_rebate=round(sum(tr['pnl_rebate'] for tr in trs),6),session=p.get('cycle_session152'))
  s.forced169.append(row);s.log(t,'FORCE169 '+str(row));return g,trs
 def rescue_tick(s,t,o,h,l,c):
  super().rescue_tick(t,o,h,l,c)
  if not s.on169 or s._w() or s.liq:return
  if s.p169['stale_days']:
   for p in sorted(s.adds169(True)+s.adds169(False),key=lambda p:(p['t'],p['id'])):
    if t-p['t']>s.p169['stale_days']*DAY:s.force169(t,p,p['n'],c,'stale30d_169')
  if s.p169['loss_cap_pct']:
   for buy in (True,False):
    sg=1 if buy else -1
    while True:
     adds=s.adds169(buy);eq=s.equity(c);loss=sum(min(0,(c-p['entry'])*p['qty']*sg) for p in adds)
     if eq<=0 or -loss<=s.p169['loss_cap_pct']/100*eq:break
     losers=sorted([p for p in adds if (c-p['entry'])*sg<0],key=lambda p:(p['t'],p['id']))
     if not losers:break
     s.force169(t,losers[0],losers[0]['n'],c,'losscap10_169')
  if s.p169['opp_bank'] and (t+60000)%180000==0:
   for buy in (True,False):
    if s.oppbank169[buy]<=0:continue
    sg=1 if buy else -1;sd='L' if buy else 'S';px=D(c)*(D('0.9995') if buy else D('1.0005'))
    for p in sorted([q for q in s.adds169(buy) if t-q['t']>s.p169['opp_age_days']*DAY and (D(c)-D(q['entry']))*sg<0],key=lambda q:(q['t'],q['id'])):
     unit=abs(D(p['entry'])-px)*UNIT+px*UNIT*D('0.0005');bank=s.oppbank169[buy]
     k=min(p['n'],int((bank/unit).to_integral_value(rounding=ROUND_FLOOR))) if bank>0 else 0
     if k<1:break
     key=(buy,p.get('cycle_session152'));g,trs=s.force169(t,p,k,c,'opprepay_169')
     s.oppbank169[buy]+=g;s.bank_adj169[key]=s.bank_adj169.get(key,D(0))-g
     for tr in trs:tr['bank_adj169']=str(-g)
     s.c169['opp_repay_events'][sd]+=1;s.c169['opp_repay_contracts'][sd]+=k
 # ---------- deterministic report block
 def summary169(s,px,end):
  def cat(tr):
   if tr['strat']!='cyc':return 'normal'
   return 'net' if tr.get('net169') else 'rescue'
  def pcat(p):return 'normal' if p['strat']!='cyc' else ('net' if p.get('net169') else 'rescue')
  pnl={}
  for sd in ('L','S'):
   for k in ('normal','rescue','net'):
    trs=[tr for tr in s.trades if tr['side']==sd and cat(tr)==k];ps=[p for p in s.pos if ('L' if p['buy'] else 'S')==sd and pcat(p)==k]
    ug=sum((px-p['entry'])*p['qty']*(1 if p['buy'] else -1) for p in ps)
    pnl[sd+'_'+k]=dict(closed_records=len(trs),realized_pnl_raw=round(sum(tr['pnl'] for tr in trs),6),realized_pnl_rebate70=round(sum(tr['pnl_rebate'] for tr in trs),6),open_count=len(ps),open_contracts=sum(p['n'] for p in ps),open_unrealized_gross=round(ug,6))
  forced={}
  for w in FORCED:
   rows=[x for x in s.forced169 if x['why']==w]
   forced[w]=dict(events=len(rows),contracts=sum(x['contracts'] for x in rows),realized_gross=round(float(sum((D(x['gross']) for x in rows),D(0))),6),realized_pnl_raw=round(sum(x['pnl'] for x in rows),6),realized_pnl_rebate70=round(sum(x['pnl_rebate'] for x in rows),6),by_side={sd:sum(x['side']==sd for x in rows) for sd in ('L','S')})
  ra=[p for p in s.pos if pcat(p)=='rescue'];na=[p for p in s.pos if pcat(p)=='net']
  ou=lambda ps:dict(count=len(ps),contracts=sum(p['n'] for p in ps),unrealized_gross=round(sum((px-p['entry'])*p['qty']*(1 if p['buy'] else -1) for p in ps),6),L=sum(p['buy'] for p in ps),S=sum(not p['buy'] for p in ps))
  ns=s.net_sessions169;dur=[((x.get('done') or end)-x['t'])/3600000 for x in ns]
  c=s.c169
  return dict(params=s.p169,pnl_by_side_kind=pnl,forced_closes=forced,rescue_adds_open_at_end=ou(ra),net_adds_open_at_end=ou(na),
   trend_pause_hours=dict(regime={k:round(v/60,4) for k,v in c['pause_minutes'].items()},while_rescue_active={k:round(v/60,4) for k,v in c['pause_minutes_rescue_active'].items()}),
   pause_slot_cancels=c['pause_slot_cancels'],pause_suppressed_placements=c['pause_suppressed_placements'],regime_changes=c['regime_changes'],
   opp_bank=dict(deposits=c['opp_deposits'],deposit_gross={k:str(v) for k,v in s.opp_deposit_gross169.items()},repay_events=c['opp_repay_events'],repay_contracts=c['opp_repay_contracts'],final_bank={'L':str(s.oppbank169[True]),'S':str(s.oppbank169[False])}),
   net=dict(sessions=c['net_sessions'],sessions_without_stuck_normal=c['net_sessions_without_stuck_normal'],sessions_without_any_normal=c['net_sessions_without_any_normal'],adds=c['net_adds'],first_limits=c['net_first_limits'],margin_skips=c['net_margin_skips'],gap_skips=c['net_gap_skips'],hours_on={k:round(v/60,4) for k,v in c['net_minutes_on'].items()},longest_session_hours=round(max(dur),6) if dur else 0,end_reasons={r:sum((x.get('end_reason') or 'ongoing')==r for x in ns) for r in ('trend_off','real_rescue_active','ongoing')}))
