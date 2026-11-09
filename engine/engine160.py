"""pt145u paper-only single-parameter experiments; exact .159T1 behavior, no Android ZIP claim."""
from engine159 import Engine159
class Engine160(Engine159):
 def __init__(s,*a,rescue_max_open=20,rescue_gap=.003,rescue_tp=60,**kw):
  if rescue_max_open not in (12,20) or rescue_gap not in (.003,.005) or rescue_tp not in (60,80,100):raise ValueError('Unreviewed .160 paper parameter')
  # Parent guards predate these explicit user parameter values. Bootstrap at exact
  # valid B1, then install requested values before warmup/orders; no policy override.
  kw.setdefault('rsi_upper',70);kw.setdefault('rsi_lower',30);kw.setdefault('pos30',False);kw.setdefault('need_held',False);kw.setdefault('held_block',False);kw.setdefault('start_roi',-1.5)
  kw.setdefault('flags',dict(TREND=True,RSI=True,STRETCH=False,UNTIL_ZERO=False,SIDE_BLOCK=True))
  super().__init__(*a,rescue_max_open=20,rescue_gap=.003,rescue_tp=60,**kw)
  s.rescue_settings158.update(max_open=rescue_max_open,gap_ratio=rescue_gap)
  s.rescue_tp159=rescue_tp;s.version='0.9.160'
