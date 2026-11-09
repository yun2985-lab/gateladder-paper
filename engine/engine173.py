"""0.9.173 PAPER (pt219u): base = 0.9.172 W4 (Engine172 max_normal_side172=1 on exact 0.9.171 V4). All new switches OFF == Engine172 with same args.
 rescue_tp173 80/100 : rescue (cyc) take-profit +60 -> +80/+100 USDT/BTC price distance (same mechanism as Engine172 rescue_tp172 / engine159 rescue_tp159).
 Other switches are passed through unchanged to Engine172: max_normal_side172 (1/2), rescue_size_pct172 (5), params171 slope_bars (12)."""
from engine172 import Engine172
class Engine173(Engine172):
 def __init__(s,*a,rescue_tp173=None,**kw):
  assert rescue_tp173 in (None,80,100) and kw.get('rescue_tp172') is None
  super().__init__(*a,**kw);s.version='0.9.173'
  if rescue_tp173:s.rescue_tp159=rescue_tp173;s.p172['rescue_tp']=rescue_tp173
  s.p173=dict(s.p172)
 def summary171(s,px,end):
  g=super().summary171(px,end);g['rules173']=dict(params=s.p173);return g
