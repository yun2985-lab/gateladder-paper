""".158 source parameter switches on exact .156A2 paper behavior; no new entry/rescue policy."""
import math
from decimal import Decimal,ROUND_HALF_UP
from engine156 import Engine156
from engine5 import cr_step,LEV,TICK

def near158(prices,price,gap=.003):
 q=Decimal(str(price));g=Decimal(str(gap))
 for x in prices:
  o=Decimal(str(x))
  if o>0 and ((q-o).copy_abs()/o).quantize(Decimal('0.00000001'),rounding=ROUND_HALF_UP)<g:return x
 return None

class Engine158(Engine156):
 def __init__(s,*a,rescue_max_open=20,rescue_gap=.003,rescue_margin_pct=50,rescue_size_pct=3,open_limit=True,**kw):
  if not open_limit:raise ValueError('Requested .158 comparison requires OPEN_LIMIT ON')
  if rescue_max_open not in (10,20) or rescue_gap not in (.003,.01) or rescue_margin_pct not in (40,50) or rescue_size_pct not in (2,3):raise ValueError('Unreviewed .158 rescue settings')
  super().__init__(*a,**kw);s.version='0.9.158'
  s.rescue_settings158=dict(max_open=rescue_max_open,gap_ratio=rescue_gap,margin_threshold_pct=rescue_margin_pct,size_available_pct=rescue_size_pct,open_limit=open_limit)
  s.rescue_order_audit158=[];s.rescue_size_audit158=[]
 def open_adds(s,buy):
  r=s.cr[buy]
  return [p for p in super().open_adds(buy) if p.get('cycle_session152')==r.get('started')]
 def cr_bar(s,t):
  if getattr(s,'warm',False):return
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
  for buy in (True,False):
   r=s.cr[buy];sl=r['slot']
   if not sl or t<sl['blk']:continue
   if l<=sl['px'] if buy else h>=sl['px']:
    # Keep exact baseline raw2% x3 -> inherited .5 -> inherited3 transform.
    # open() scales only rescue notional by requested2/3 or3/3.
    N=max(0,s.free(sl['px']))*.02*LEV;cap=s.rescue_settings158['max_open']
    p=s.open(t,'cyc',buy,sl['px'],info='cycle rescue add %d total; open %d/%d @%.1f'%(r['adds']+1,len(s.open_adds(buy))+1,cap,sl['px']),limit=True,notional=N,exitmode='cyc')
    r['slot']=None
    if p:
     r['adds']+=1;r['lastAdd']=sl['px']
     for rs in reversed(s.rescues):
      if rs['t']==r.get('started') and rs['side']==('L' if buy else 'S'):rs['adds']=r['adds'];break
     s.log(t,'CYCLE ADD OPEN %s total%d open%d/%d'%('L' if buy else 'S',r['adds'],len(s.open_adds(buy)),cap))
 def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
  audit=None
  if strat=='cyc' and notional is not None:
   audit=dict(t=t,side='L' if buy else 'S',price=px,available=max(0,s.free(px)),size_pct=s.rescue_settings158['size_available_pct'],raw_baseline_notional=notional)
   notional*=s.rescue_settings158['size_available_pct']/3
  p=super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
  if p is not None and audit is not None:
   audit.update(id=p['id'],contracts=p['n0'],qty=p['n0']*.0001,entry_fee=p['fee'],session=p.get('cycle_session152'));s.rescue_size_audit158.append(audit)
  return p
