"""0.9.172 PAPER (pt218u): base = 0.9.171 V4 (Engine171 rescue_size_pct171=4 on exact 0.9.170 U4). All new switches OFF == Engine171 V4.
 max_normal_side172 1/2/3 : same definition as 0.9.171 V2 (Engine171 max_normal_side; NEW normal entry refused when >=k normal (strat!='cyc', n>0)
                            positions of that side are open; s.open + capped() hooks; rescue excluded). k=2 delegates to Engine171 exactly.
 slope_bars 12 (params171) : 0.9.171 V3 (Pause-B slope vs SMA120[i-12]).
 rescue_size_pct172 5      : rescue add size 5% of available (rescue_settings158 override, same mechanism as V4's 4%).
 rescue_tp172 80           : rescue (cyc) take-profit +60 -> +80 USDT/BTC price distance (engine159 rescue_tp159, same as engine161 TP override)."""
from engine171 import Engine171
class Engine172(Engine171):
 def __init__(s,*a,max_normal_side172=None,rescue_size_pct172=None,rescue_tp172=None,**kw):
  assert max_normal_side172 in (None,1,2,3) and rescue_size_pct172 in (None,5) and rescue_tp172 in (None,80)
  assert kw.get('rescue_size_pct171')==4 and kw.get('max_normal_side') is None,'0.9.172 base must be exact 0.9.171 V4'
  super().__init__(*a,**kw);s.version='0.9.172'
  assert s.rescue_tp159==60 and s.rescue_settings158['size_available_pct']==4
  if max_normal_side172:s.p171['max_normal_side']=max_normal_side172
  if rescue_size_pct172:s.rescue_settings158['size_available_pct']=rescue_size_pct172;s.p171['rescue_size_pct']=rescue_size_pct172
  if rescue_tp172:s.rescue_tp159=rescue_tp172
  s.p172=dict(max_normal_side=s.p171['max_normal_side'],slope_bars=s.p171['slope_bars'],rescue_size_pct=s.rescue_settings158['size_available_pct'],rescue_tp=s.rescue_tp159,rescue_margin_pct=s.rescue_settings158['margin_threshold_pct'])
 def summary171(s,px,end):
  g=super().summary171(px,end);g['rules172']=dict(params=s.p172);return g
