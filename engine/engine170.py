"""0.9.170 PAPER (pt216u): exact 0.9.169 T1 (Engine169, pause_tf 4h) plus three isolated switches. All OFF == Engine169.
 OFF4 (config): 15m SMA20 turn, 15m SMA60 turn, 1h SMA20 turn are added to the inherited Engine166 OFF list (params167.off:
   'ma20:15m','ma60:15m','ma20:1h'; native Engine166 slot cancel + open refusal). 1m RSI divergence (div1m_off=True): normal
   entries strat 'pat1' whose info is 상승/하락 다이버전스 (RSI14 pattern) and strat 'rsi1' (RSI9 bull/bear div) are refused at open.
 sl_pct 3 : NORMAL entries only (strat!='cyc'). Minute low<=entry*(1-3%) (L) / high>=entry*(1+3%) (S), position opened in an
   EARLIER minute => market close remaining qty, base=trigger (or minute open if it already gapped through), fill base -/+0.05%
   (same market convention as repay152/force169), TAKER 0.042% fee, rebate 70%. Checked after exits/limits/rescue logic of
   that minute. If the entry is a rescue HELD member it is removed from r['held'] (and g0), so its realised loss leaves the
   rescue bank/100%-recovery accounting; if it was the last held member the session ends ('sl3_all_held_stopped_170').
 pause_mode 'T1' (unchanged .169: close>SMA120_4h => UP => short-add pause; <= => DOWN => long-add pause)
   'A' : UP only if close > SMA*1.02 (short pause), DOWN only if close < SMA*0.98 (long pause), else NEUTRAL (no pause).
   'B' : UP if close > SMA and SMA[i] > SMA[i-6] (6 closed 4h bars ago); DOWN if close <= SMA and SMA[i] < SMA[i-6]; else NEUTRAL.
   Same closed-bar table, same placement/fill timing as .169.
"""
import bisect
from engine169 import Engine169
from engine29 import D
from engine8 import TAKER
H4=14400000
class Engine170(Engine169):
 def __init__(s,*a,div1m_off=False,sl_pct=None,pause_mode='T1',**kw):
  assert pause_mode in ('T1','A','B') and sl_pct in (None,3) and div1m_off in (True,False)
  super().__init__(*a,**kw);s.version='0.9.170'
  assert s.p169['pause_tf']=='4h' and not (s.p169['stale_days'] or s.p169['opp_bank'] or s.p169['loss_cap_pct'] or s.p169['net_tf'])
  s.p170=dict(div1m_off=div1m_off,sl_pct=sl_pct,pause_mode=pause_mode)
  s.div_refused170={'pat1_div':{'L':0,'S':0},'rsi1':{'L':0,'S':0}};s.sl170=[];s.c170=dict(neutral_minutes=0,sl_held_removed=0,sl_session_ends=0)
 def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
  if s.p170['div1m_off']:
   k='pat1_div' if (strat=='pat1' and '다이버전스' in (info or '')) else ('rsi1' if strat=='rsi1' else None)
   if k:s.div_refused170[k]['L' if buy else 'S']+=1;s.log(t,'OFF170 %s %s refused'%(k,'L' if buy else 'S'));return None
  return super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
 def regime169(s,tf,tend,c):
  m=s.p170['pause_mode'] if hasattr(s,'p170') else 'T1'
  if m=='T1':return super().regime169(tf,tend,c)
  ts,sm=s.sma169[tf];i=bisect.bisect_right(ts,tend)-1
  if i<0 or sm[i] is None:return None
  if m=='A':return 'UP' if c>sm[i]*1.02 else ('DOWN' if c<sm[i]*0.98 else 'NEUTRAL')
  if i<6 or sm[i-6] is None or ts[i]-ts[i-6]!=6*H4:return None
  if c>sm[i] and sm[i]>sm[i-6]:return 'UP'
  if c<=sm[i] and sm[i]<sm[i-6]:return 'DOWN'
  return 'NEUTRAL'
 def step(s,b):
  r=super().step(b)
  if not s._w() and s.end_state169.get('4h')=='NEUTRAL':s.c170['neutral_minutes']+=1
  return r
 def rescue_tick(s,t,o,h,l,c):
  super().rescue_tick(t,o,h,l,c)
  if not s.p170['sl_pct'] or s._w() or s.liq:return
  k=s.p170['sl_pct']/100
  for p in sorted([p for p in s.pos if p['strat']!='cyc' and p['n']>0 and p['t']<t],key=lambda p:(p['t'],p['id'])):
   buy=p['buy'];trig=p['entry']*(1-k) if buy else p['entry']*(1+k)
   if not (l<=trig if buy else h>=trig):continue
   base=min(o,trig) if buy else max(o,trig);px=float(D(base)*(D('0.9995') if buy else D('1.0005')))
   n=p['n'];before=len(s.trades);old=getattr(s,'_fr',None);s._fr=TAKER
   try:s.close(t,p,n,px,'sl3_170',limit=True)
   finally:s._fr=old
   trs=s.trades[before:];r=s.cr[buy];sd='L' if buy else 'S';was_held=r['phase']=='active' and p['id'] in (r.get('held') or [])
   for tr in trs:tr['sl170']=True
   row=dict(t=t,id=p['id'],side=sd,strat=p['strat'],info=p['info'],entry=p['entry'],entry_t=p['t'],trigger=trig,base=base,price=px,contracts=n,minute_o=o,minute_h=h,minute_l=l,
     pnl=round(sum(tr['pnl'] for tr in trs),6),pnl_rebate=round(sum(tr['pnl_rebate'] for tr in trs),6),gross=str(sum((D(tr.get('gross_exact152','0')) for tr in trs),D(0))),
     trade_index=before,held=was_held,session=r.get('started') if was_held else None,session_end=False)
   if was_held:
    r['held'].remove(p['id']);(r.get('held_g0_152') or {}).pop(p['id'],None);s.c170['sl_held_removed']+=1
    rs=s._session_record152(buy,r)
    if rs is not None:rs.setdefault('sl_removed_ids170',[]).append(p['id'])
    if not r['held']:s._finish152(buy,r,t,'sl3_all_held_stopped_170');row['session_end']=True;s.c170['sl_session_ends']+=1
   s.sl170.append(row);s.log(t,'SL170 '+str(row))
 def summary170(s,px,end):
  rows=s.sl170;g=s.summary169(px,end)
  g['rules170']=dict(params=s.p170,div1m_refused=s.div_refused170,off_events166=len(s.off_events166),neutral_pause_hours=round(s.c170['neutral_minutes']/60,4),
   stop_loss=dict(count=len(rows),contracts=sum(x['contracts'] for x in rows),realized_pnl_raw=round(sum(x['pnl'] for x in rows),6),realized_pnl_rebate70=round(sum(x['pnl_rebate'] for x in rows),6),
     by_side={sd:sum(x['side']==sd for x in rows) for sd in 'LS'},held_removed=s.c170['sl_held_removed'],session_ends=s.c170['sl_session_ends'],gapped_fills=sum(x['base']!=x['trigger'] for x in rows)))
  return g
