"""pt163u round3/5 paper-only START/RSI/normal-cap parameter experiment."""
from engine161 import Engine161
class Engine162(Engine161):
 def __init__(s,*a,start_roi=-1.5,normal_cap_pct=20,**kw):
  if start_roi not in (-1,-1.5,-2) or normal_cap_pct not in (15,20,25):raise ValueError('Unreviewed .162 paper parameter')
  s.normal_cap_pct162=normal_cap_pct
  super().__init__(*a,start_roi=-1.5,**kw)
  s.start_roi159=start_roi;s.version='0.9.162'
 def capped(s,buy,px):
  # EXACT inherited side_share: current same-side ALL-position mark margin/raw
  # equity, rounded2. Pre-entry >= threshold; no prospective resize, cyc exempt
  # at inherited caller. Different from unrounded PRE-rescue margin40 guard.
  return s.side_share(buy,px)>=s.normal_cap_pct162
