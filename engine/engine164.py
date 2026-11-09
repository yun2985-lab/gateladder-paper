"""pt181u PAPER new-series round1/5. X1 establishes B4 TP90; no app/source-ZIP claim."""
from engine162m import Engine162M
class Engine164(Engine162M):
 def __init__(s,*a,start_roi=-2,rescue_gap=.003,rescue_margin_pct=40,rescue_tp=60,m1_market=True,m1_break_tp=90,**kw):
  if start_roi not in (-2,-2.5) or rescue_gap not in (.003,.004) or rescue_margin_pct not in (35,40) or rescue_tp not in (60,80) or not m1_market or m1_break_tp!=90:raise ValueError('Unreviewed pt181u .164 paper parameters')
  # Bootstrap only pre-existing accepted constructor values. No orders/warmup
  # occur here; install authorized new values before any signal/order.
  super().__init__(*a,start_roi=-2,rescue_gap=.003,rescue_margin_pct=40,rescue_tp=60,m1_market=True,m1_break_tp=80,**kw)
  s.start_roi159=start_roi;s.rescue_settings158.update(gap_ratio=rescue_gap,margin_threshold_pct=rescue_margin_pct);s.rescue_tp159=rescue_tp;s.m1_tp162m=90;s.version='0.9.164'
