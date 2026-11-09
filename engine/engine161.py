"""pt153u round2/5 paper combinations; no Android source/live changes."""
from engine160 import Engine160
class Engine161(Engine160):
 def __init__(s,*a,rescue_max_open=20,rescue_tp=60,rescue_margin_pct=40,**kw):
  if rescue_max_open not in (20,30) or rescue_tp not in (60,80,100,120) or rescue_margin_pct!=40:raise ValueError('Unreviewed .161 paper parameter')
  super().__init__(*a,rescue_max_open=20,rescue_tp=60,rescue_margin_pct=40,**kw)
  s.rescue_settings158['max_open']=rescue_max_open;s.rescue_tp159=rescue_tp;s.version='0.9.161'
