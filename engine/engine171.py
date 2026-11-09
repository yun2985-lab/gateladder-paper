"""0.9.171 PAPER (pt217u): exact 0.9.170 U4 (Engine170 div1m_off=True, pause_mode='B') plus isolated switches. All OFF == Engine170 U4.
 bounce_short_off : 1m trendline-touch bounce SHORT normal entries (strat 'pat1', info contains '추세선 닿으면 반대', side S) refused at open
                    (engine17 bounce family; long bounce kept). Applied in every phase like Engine166 OFF.
 max_normal_side 2: a NEW normal entry (strat!='cyc') is refused when >=2 normal positions of that side are already open (n>0).
                    Hooked at s.open (all limit/market s.open paths) AND at capped() (the M1MARKET/MA-market paths call super().open,
                    so they are blocked by the inherited pre-open cap check and logged as NORMAL_CAP). Replay phase only. Counted.
 slope_bars 12    : Pause-B slope compares SMA120[i] with SMA120[i-12] (12 closed 4h bars, contiguous) instead of i-6.
 rescue_size_pct 4 / rescue_margin_pct 50: overrides rescue_settings158 after inherited validation (add size % of available; margin pause %).
"""
import bisect
from engine170 import Engine170,H4
from engine166 import identity166
class Engine171(Engine170):
 def __init__(s,*a,bounce_short_off=False,max_normal_side=None,slope_bars=6,rescue_size_pct171=None,rescue_margin_pct171=None,**kw):
  assert bounce_short_off in (True,False) and max_normal_side in (None,2) and slope_bars in (6,12) and rescue_size_pct171 in (None,4) and rescue_margin_pct171 in (None,50)
  super().__init__(*a,**kw);s.version='0.9.171'
  assert s.p170['pause_mode']=='B' and s.p170['div1m_off'] and not s.p170['sl_pct']
  if rescue_size_pct171:s.rescue_settings158['size_available_pct']=rescue_size_pct171
  if rescue_margin_pct171:s.rescue_settings158['margin_threshold_pct']=rescue_margin_pct171
  s.p171=dict(bounce_short_off=bounce_short_off,max_normal_side=max_normal_side,slope_bars=slope_bars,rescue_size_pct=s.rescue_settings158['size_available_pct'],rescue_margin_pct=s.rescue_settings158['margin_threshold_pct'])
  s.c171=dict(bounce_short_refused=0,max2_blocked_open={'L':0,'S':0},max2_blocked_market={'L':0,'S':0})
 def n_normal171(s,buy):return sum(1 for p in s.pos if p['buy']==buy and p['strat']!='cyc' and p['n']>0)
 def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
  if s.p171['bounce_short_off'] and strat=='pat1' and not buy and '추세선 닿으면 반대' in (info or ''):
   s.c171['bounce_short_refused']+=1;s.log(t,'OFF171 bounce S refused');return None
  if s.p171['max_normal_side'] and strat!='cyc' and not s._w() and s.n_normal171(buy)>=s.p171['max_normal_side']:
   ident=identity166(strat,info);off=bool(ident and s.disabled166(*ident))
   if not off and not (s.p170['div1m_off'] and ((strat=='pat1' and '다이버전스' in (info or '')) or strat=='rsi1')):
    sd='L' if buy else 'S';s.c171['max2_blocked_open'][sd]+=1;s.log(t,'MAX2_171 %s %s blocked'%(sd,strat));return None
  return super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
 def capped(s,buy,px):
  r=super().capped(buy,px)
  if not r and s.p171['max_normal_side'] and not s._w() and s.n_normal171(buy)>=s.p171['max_normal_side']:
   s.c171['max2_blocked_market']['L' if buy else 'S']+=1;return True
  return r
 def regime169(s,tf,tend,c):
  k=s.p171['slope_bars'] if hasattr(s,'p171') else 6
  if k==6:return super().regime169(tf,tend,c)
  ts,sm=s.sma169[tf];i=bisect.bisect_right(ts,tend)-1
  if i<0 or sm[i] is None:return None
  if i<k or sm[i-k] is None or ts[i]-ts[i-k]!=k*H4:return None
  if c>sm[i] and sm[i]>sm[i-k]:return 'UP'
  if c<=sm[i] and sm[i]<sm[i-k]:return 'DOWN'
  return 'NEUTRAL'
 def summary171(s,px,end):
  g=s.summary170(px,end);c=s.c171
  g['rules171']=dict(params=s.p171,bounce_short_refused=c['bounce_short_refused'],max2_blocked=dict(open=c['max2_blocked_open'],market=c['max2_blocked_market'],total=sum(c['max2_blocked_open'].values())+sum(c['max2_blocked_market'].values())))
  return g
