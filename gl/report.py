"""report.json builder. Ported verbatim from report_v2_0173_y2025.py (_build151/152/153 + build_report)
with only these changes: KST via fixed UTC+9 (OS-timezone independent), no engine-type whitelist,
round-specific bookkeeping labels removed, and the slow research-only cohort appendices
(m1_market_cohort, tf_signal_cohorts) omitted. All headline metrics are computed by the same code."""
import bisect
from .kst import fmt as _fmt

def kst(t):return _fmt(t,'%Y-%m-%d %H:%M:%S KST')
def kst_month(t):return _fmt(t,'%Y-%m')
def round6(x):return round(x,6)

def legacy_rebate_mdd(e):
    ts=sorted(t['t'] for t in e.trades);n=max(len(ts),1);pk=e.start;dd=0.
    for i,(t,v,_) in enumerate(e.eq):
        v+=e.rebate*(bisect.bisect_right(ts,t)/n if i<len(e.eq)-1 else 1)
        pk=max(pk,v);dd=max(dd,(pk-v)/pk)
    return dd*100

def _py171(o):
    import numpy as np
    if isinstance(o,dict):return {k:_py171(v) for k,v in o.items()}
    if isinstance(o,(list,tuple)):return [_py171(v) for v in o]
    if isinstance(o,np.integer):return int(o)
    if isinstance(o,np.floating):return float(o)
    if isinstance(o,np.bool_):return bool(o)
    return o

def _build151(e,cfg):
    assert e.last+60000==cfg['replay_end_ms']
    px=e.last_mark151[1];raw=e.equity(px);total=raw+e.rebate
    cyc=[t for t in e.trades if t['strat']=='cyc'];opened=[p for p in e.pos if p['strat']=='cyc' and p['n']>0]
    def open_result(ps):
        gross=sum((px-p['entry'])*p['qty']*(1 if p['buy'] else -1) for p in ps)
        fee=sum(p['fee']*p['n']/p['n0']*.3 for p in ps)
        return dict(count=len(ps),contracts=sum(p['n'] for p in ps),qty=sum(p['qty'] for p in ps),unrealized_gross=round6(gross),unrealized_after_entry_fee_rebate70=round6(gross-fee),net_if_closed_at_mark_maker_rebate70_estimate=round6(gross-fee-sum(px*p['qty']*.00018*.3 for p in ps)))
    monthly=[]
    for key,v in e.monthly151.items():
        tr=[t for t in e.trades if kst_month(t['t'])==key]
        monthly.append(dict(month=key,start=round6(v['start']),end=round6(v['end']),pnl_rebate_mtm=round6(v['end']-v['start']),return_rebate_pct=round6((v['end']/v['start']-1)*100) if v['start'] else None,realized_pnl_rebate=round6(sum(t['pnl_rebate'] for t in tr)),cyc_realized_pnl_rebate=round6(sum(t['pnl_rebate'] for t in tr if t['strat']=='cyc')),trades=len(tr),first_bar_open=kst(v['first_bar']),last_bar_open=kst(v['last_bar'])))
    ids={t['id'] for t in cyc}|{p['id'] for p in opened};openids={p['id'] for p in opened}
    return dict(version=cfg['version'],engine=cfg['module'],source_sha256=cfg['source_sha256'],initial=e.start,start=kst(cfg['start']),end=kst(cfg['replay_end_ms']),last_bar_open=kst(e.last),status='REPLAY_COMPLETE_FROZEN',comparison_baselines=cfg.get('comparison_baselines',{}),price=px,equity_raw=round6(raw),equity_rebate70=round6(total),return_raw_pct=round6((raw/e.start-1)*100),return_rebate70_pct=round6((total/e.start-1)*100),mdd_raw_minute_pct=round6(e.mdd*100),mdd_rebate70_exact_minute_pct=round6(e.rebate_mdd151*100),mdd_rebate70_legacy_15m_approx_pct=round6(legacy_rebate_mdd(e)),max_margin_usage_pct=round6(e.max_mu*100),fees=round6(e.fees),rebate70=round6(e.rebate),liquidated=e.liq,monthly=monthly,cyc=dict(sessions_count=len(e.rescues),filled_add_count=len(ids),fully_closed_add_count=len(ids-openids),closed_trade_records=len(cyc),realized_pnl_raw=round6(sum(t['pnl'] for t in cyc)),realized_pnl_rebate70=round6(sum(t['pnl_rebate'] for t in cyc)),open_at_end=dict(total=open_result(opened),L=open_result([p for p in opened if p['buy']]),S=open_result([p for p in opened if not p['buy']]))),margin50_skips=e.margin50_skips,margin50_skips_by_side=e.margin50_skips_by_side,definitions=dict(mdd_raw='Same engine minute-close raw wallet+unrealized equity, fees deducted, rebate excluded',mdd_rebate_exact='Every minute close raw equity + ACTUAL cumulative70% rebates at that instant',mdd_legacy='Only for old dashboard baseline comparability:15m raw curve + final total rebate apportioned by closed trade count, approximate',monthly='Month-end minus prior month-end equity INCLUDING actual cumulative rebate70%; mark-to-market, includes open PnL; partial first/last months',max_margin='Same existing minute-close engine metric margin/equity RAW; no guarantee<=30/35/40%, guard is pre-order only',cyc_realized='Closed cyc trade pnl and pnl_rebate fields, both entry/exit fees allocated, rebate70 included in pnl_rebate',open='Every STILL OPEN cyc add across all sessions, not just active-session additions; gross mark-to-market and remaining-entry-fee/rebate-aware PnL; prospective exit estimate separately labeled',skip='Otherwise eligible new rescue-add third-tick signals blocked by pre-placement unrounded margin>=actual variant threshold; not candle count, not rechecks; no fill-time or prospective cap'))


def _build152(e,cfg):
    r=_build151(e,cfg);px=e.last_mark151[1];end=cfg['replay_end_ms'];ids=set()
    for buy in (True,False):
        if e.cr[buy]['phase']=='active':ids.update(e.cr[buy].get('held',[]))
    def held(ps):
        gross=sum((px-p['entry'])*p['qty']*(1 if p['buy'] else -1) for p in ps)
        fee=sum(p['fee']*p['n']/p['n0']*.3 for p in ps)
        return dict(count=len(ps),contracts=sum(p['n'] for p in ps),qty=sum(p['qty'] for p in ps),unrealized_gross=round6(gross),unrealized_after_entry_fee_rebate70=round6(gross-fee))
    trapped=[p for p in e.pos if p['id'] in ids and p['n']>0]
    rs=e.rescues;completed=[x for x in rs if x.get('done') is not None]
    def duration(x):
        stop=x.get('done') if x.get('done') is not None else end
        return dict(side=x['side'],start=kst(x['t']),end=kst(stop),hours=round6((stop-x['t'])/3600000),ongoing=x.get('done') is None,end_reason=x.get('end_reason152'))
    longest=max(rs,key=lambda x:(x.get('done') if x.get('done') is not None else end)-x['t']) if rs else None
    longest_done=max(completed,key=lambda x:x['done']-x['t']) if completed else None
    chip=[x for x in e.trades if x['why']=='rescue_repay152']
    r['repayment']=dict(events=e.repayment_events152,contracts=e.repayment_contracts152,three_minute_batches=e.repayment_batches152,realized_pnl_raw=round6(sum(x['pnl'] for x in chip)),realized_pnl_rebate70=round6(sum(x['pnl_rebate'] for x in chip)),budget_definition='THIS session add realised PRICE profit + initial held realised PRICE pnl since start (source OfficeFeed.gross); fees/rebates excluded from bank, included in account/results. Gross losses debited once; no old-session add profit or pre-session held PnL.',estimated_fee_rate=.0005,actual_exit_taker_fee_rate=.00042,rebate_rate=.7)
    r['rescue_sessions']=dict(total=len(rs),completed=len(completed),ongoing=len(rs)-len(completed),longest_including_ongoing=duration(longest) if longest else None,longest_completed=duration(longest_done) if longest_done else None)
    r['initial_held_open_at_end']=dict(total=held(trapped),L=held([p for p in trapped if p['buy']]),S=held([p for p in trapped if not p['buy']]))
    r['definitions']['repayment']='Requested3m sorted losing-held contract batches; exact mark +/-0.05%, no extra slippage; estimated fee .05% sizes k, actual taker.042%/rebate70% booked with proportional remaining entry fees. Residual original TP prices preserved; legacy full100% recovery first.'
    return r


def _build153(e,cfg):
    r=_build152(e,cfg);px=e.last_mark151[1];end=cfg['replay_end_ms'];DAY=86400000
    def summary(ps):
        gross=sum((px-p['entry'])*p['qty']*(1 if p['buy'] else -1) for p in ps)
        fee=sum(p['fee']*p['n']/p['n0']*.3 for p in ps)
        return dict(count=len(ps),contracts=sum(p['n'] for p in ps),qty=sum(p['qty'] for p in ps),unrealized_gross=round6(gross),unrealized_after_entry_fee_rebate70=round6(gross-fee))
    def sides(ps):return dict(total=summary(ps),L=summary([p for p in ps if p['buy']]),S=summary([p for p in ps if not p['buy']]))
    adds=[p for p in e.pos if p['strat']=='cyc' and p['n']>0]
    old=[p for p in adds if end-p['t']>=DAY];young=[p for p in adds if end-p['t']<DAY]
    eligible=[p for p in old if e.flags154['UNTIL_ZERO'] and e.cr[p['buy']]['phase']=='active' and p.get('cycle_session152')==e.cr[p['buy']].get('started') and not e.held_open153(p['buy'],e.cr[p['buy']])]
    heldids={i for buy in (True,False) if e.cr[buy]['phase']=='active' for i in e.cr[buy].get('held',[])}
    r['trapped_total_at_end']=sides([p for p in e.pos if p['n']>0 and (p['strat']=='cyc' or p['id'] in heldids)])
    r['definitions']['repayment']='3m sorted losing initial held first; only when none left SAME-session >=24h adds next. User ABS unit formula; exact mark +/-0.05%, no extra SLIP; estimate fee.05%, actualtaker.042%/rebate70%, proportional entry fees and residual original TP. Legacy100% closes held first but ROI<0 residual side keeps rescue.'
    r['rescue_adds_age_at_end']=dict(under24h=sides(young),at_least24h=sides(old),eligible_current_session_old=sides(eligible),other_or_held_blocked_old=sides([p for p in old if p not in eligible]))
    details={}
    for target in ('HELD','OLD_ADDS'):
        events=[x for x in e.repayment_log152 if x.get('target','HELD')==target]
        trades=[x for x in e.trades if x.get('repayment_target153','HELD' if x.get('why')=='rescue_repay152' else None)==target]
        details[target]=dict(events=len(events),contracts=sum(x['contracts'] for x in events),realized_pnl_raw=round6(sum(x['pnl'] for x in trades)),realized_pnl_rebate70=round6(sum(x['pnl_rebate'] for x in trades)))
    r['repayment']['by_target']=details
    r['repayment']['budget_definition']='THIS session ALL add realised PRICE PnL, INCLUDING old-add repayment losses, plus original held realised PRICE PnL since start. Original held IDs/g0 remain while session active after all held gone; no reset/double spend. Prefee gross source bank; actual account/results include fees/rebate70.'
    r['definitions']['repayment']='Exact .152 held-only repayment. No OLD_ADDS/24h repayment. Price-only bank since held g0; actual fees/rebates in account.'
    r['definitions']['old_add_targets']='Only zero remaining original held permits SAME-session filled adds age>=24h at3m close. Young and prior-session adds untouched. User ABS loss+estimatedfee formula applies to ALL eligible old adds including flat/profitable; differs from source signed-loss filter. ROI>=0/flat ends only when held absent; legacy100% still closes held but then uses this ROI gate.'
    return r


def build_report(e,cfg):
    r=_build153(e,cfg);r['normal_direction_cap_pct']=e.normal_cap_pct162;r['params162']=cfg['params162'];r['variant_id']=cfg['variant'];r['flags']=e.flags154;r['normal_entry_counts']=e.normal_counts154;r['filter_counts']=e.filter_counts154;r['filter_totals']=e.filter_totals154
    r['held_block159']=e.held_block159;r['start_roi159']=e.start_roi159;r['rescue_tp159']=e.rescue_tp159;r['held_adoption_events']=len(e.adoption_log159);r['held_adoption_batches']=e.adoption_batches159;r['held_adoption_contracts']=e.adoption_contracts159;r['held_open_at_end']=r['initial_held_open_at_end']
    r['definitions']['HELD_BLOCK']='ALL .167 conditions HELD_BLOCK OFF; no adoption. Inherited optional semantics: SIDE_BLOCK only while actual open normal held quantities remain. Source159 adoption at individual mark/basis ROI rounded12 HALF_EVEN x3 <= configurable START (H3=-3 for BOTH start+adoption). Every adoption stores current realised gross g0, unchanged bank; late-held final statistics/CSV included. Original initial-held IDs remain separate. UNTIL_ZERO OFF ends after all once-held positions gone; never-held leftover-add session persists until side ROI>=0 as baseline.'
    r['rescue_sessions']['longest_ongoing_hours']=max([(cfg['replay_end_ms']-x['t'])/3600000 for x in e.rescues if x.get('done') is None] or [0]);r['repayment']['budget_definition']='Exact .152: THIS rescue session add realised PRICE PnL plus original held realised PRICE PnL SINCE session start and adopted held realised PRICE PnL SINCE incorporation g0; held-only repayment; account PnL includes actual fees/rebate70 but bank excludes fees/rebates. UNTIL_ZERO OFF, no old-add age repayment.'
    r['definitions']['skip']='Otherwise eligible NEW rescue third-tick order blocked at variant unrounded margin>=30/35/40; consumed signal retried only at next3ticks. Counter aliases margin50_* retain old schema, see margin_guard_threshold_pct.'
    r['rescue_settings158']=e.rescue_settings158;r['margin_guard_threshold_pct']=e.rescue_settings158['margin_threshold_pct'];r['margin_guard_skips']=e.margin50_skips;r['margin_guard_skips_by_side']=e.margin50_skips_by_side
    r['definitions']['margin_guard']='Unrounded (equity-available)/equity*100 checked only before otherwise eligible NEW rescue limit; >= variant threshold30/35/40 consumes signal until next3ticks. No prospective/fill-time total margin cap. Historical margin50_* field/CSV column aliases store this variant threshold counter, not necessarily50.'
    r['definitions']['rescue_parameters']='Source158 OPEN_LIMIT ON: max concurrent SAME-session filled remaining adds; TP frees slots. Gap vs EVERY open add uses abs(new-old)/old rounded8 decimals HALF_UP, equality allowed. Size at fill from instantaneous available *variant2/3% *fixed3, contractfloor unchanged. Old source158 margin helper rounds2decimals; paper deliberately retains baseline unrounded guard and baseline gap-before-margin counter ordering.'
    r['need_held']=e.need_held156;r['rescue_start_without_normal_count']=sum(x['normal_auto_count156']==0 for x in e.rescues);r['rescue_start_without_normal_by_side']={sd:sum(x['normal_auto_count156']==0 and x['side']==sd for x in e.rescues) for sd in ('L','S')};r['normal_entry_rescue_blocked_minutes']=e.blocked_minutes156;r['normal_entry_rescue_blocked_hours']={sd:round(n/60,9) for sd,n in e.blocked_minutes156.items()};r['need_held_start_skipped_side_minutes']=e.need_held_skips156
    r['definitions']['NEED_HELD']='Source .156 CycleRescue.openTrades predicate mapped to open same-side non-cyc automatic runtime positions; gate ONLY before new rescue starts. Inherited initial held and bank unchanged. No stale-add repayment. Runtime contains no imported manual/rescueOwned positions; explicit flags excluded by predicate if present.'
    r['definitions']['rescue_blocked_time']='When HELD_BLOCK ON, requires actual remaining held quantities; adoption/full close changes next-minute block state. Actual pre-step minute-open SIDE_BLOCK phase used by normal-entry processing; one minute per side, overlaps never double-counted. Rescue transitions occur after entry limits, so a session starting at minute t first blocks minute t+1; ending at t still blocks that minute. Post-step state also audited. L/S hours=minute counts/60.'
    r['settings155']=e.settings155;r['blocked_unique_side_minutes']=e.blocked_unique_side_minutes155
    r['definitions']['POS30']='Previous30 COMPLETED UTC daily high maximum / low minimum; strict >90 blocks L, <10 blocks S, equality allowed; missing or nonpositive range HARD ERROR. Current UTC day excluded.'
    r['definitions']['filter_counts']='Normal logical pending-entry plans / market attempts. Each new plan attempted once; rejected placement vs later pending cancellation separated. Per-rule counts overlap when multiple conditions match; totals are unique events, not sum-of-rules. Includes plans held by other baseline controls, NOT counterfactual successful fills exclusively prevented by filter. blocked_side_minutes counts each enabled rule once per side at minute-open; denominator side_minutes=2*replayed1m candles. No per-minute repeated cancellation counts.'
    r['definitions']['filter_timing']='Minute OPEN currentprice, completed HTF close<=minuteopen; cancel normal pending BEFORE samebar fills. After on_1m, update completedUTC HTF with thisminute then close-bar placement uses minuteclose and newlycompletedHTF. Market triggers also checked at modeled triggerprice; minute OHLC cannot prove intrabar gate crossings. No queue/volume model; inherited fillmechanics unchanged.'
    r['definitions']['missing_history']='ZIP fail-open for unknown; paper explicitly fetches70prewarmupdays publicUTC1h/4h/daily and HARDERROR if any enabled indicator unavailable. No silent disable. Inherited strategy13daywarmup untouched; filters have separate earlier lookback. WilderRSI14 seeded meanfirst14changes, flat=50.'
    r['definitions']['repayment']='Exact .152 held-only repayment. No OLD_ADDS/24h repayment. Price-only bank since held g0; actual fees/rebates in account.'
    r['definitions']['old_add_targets']='Disabled: exact .152 held-only repayment/end when held gone' if not e.flags154['UNTIL_ZERO'] else r['definitions']['old_add_targets']
    r['definitions']['normal_direction_cap']='Inherited round2 side_share ALL same-side mark margin/raw equity; pre-entry >= cap blocks NORMAL only; no prospective cap/resize, cyc exempt. Margin40 rescue guard separately unrounded.'
    r['definitions']['switches']='UNTIL_ZERO false exactEngine29 .152; true exactEngine30 .153 heldpriority,24h same-session adds,persistentgrossbank,ROI>=0 end. SIDE_BLOCK only normal entry guard; with HELD_BLOCK ON, eligible new same-side AUTO normal positions are adopted at configurable START with incorporation g0; OFF never appends. SideROI includes all current same-side positions, as baseline.'
    px=e.last_mark151[1]
    def side(ps):
        def one(pp):return dict(count=len(pp),contracts=sum(p['n'] for p in pp),unrealized_gross=sum((px-p['entry'])*p['qty']*(1 if p['buy'] else -1) for p in pp),unrealized_after_entry_fee_rebate70=sum((px-p['entry'])*p['qty']*(1 if p['buy'] else -1)-p['fee']*p['n']/p['n0']*.3 for p in pp))
        return dict(total=one(ps),L=one([p for p in ps if p['buy']]),S=one([p for p in ps if not p['buy']]))
    heldids={i for b in (True,False) if e.cr[b]['phase']=='active' for i in e.cr[b].get('held',[])}
    r['normal_nonheld_open_at_end']=side([p for p in e.pos if p['strat']!='cyc' and p['id'] not in heldids]);r['all_positions_at_end']=side(e.pos)
    r['pattern_switches167']=cfg['params167'];r['m1_market']=e.m1_market162m;r['m1_break_tp_usdt']=e.m1_tp162m
    from collections import Counter
    r['m1_market_signal_outcomes']=dict(Counter(ev['outcome'] for ev in e.m1_decisions162m))
    r['definitions']['m1_market']='pt202u next1m OPEN exact, taker. Internal exact-price route limit=True with forcedTAKER not maker. FullTP maker, one-shot, inside/equal invalid. Triangle/otherTF unchanged. Read cohort definitions for boundary-safe MFE/MAE lower bounds.'
    if hasattr(e,'summary171'):r['rules169']=_py171(e.summary171(e.last_mark151[1],cfg['replay_end_ms']))  # numpy scalars -> python (int64 JSON fix)
    elif hasattr(e,'summary170'):r['rules169']=e.summary170(e.last_mark151[1],cfg['replay_end_ms']);sl=r['rules169']['rules170']['stop_loss'];sl['gapped_fills']=int(sl['gapped_fills'])
    elif hasattr(e,'summary169'):r['rules169']=e.summary169(e.last_mark151[1],cfg['replay_end_ms'])
    return r


def summary_row(r):
    """Flat headline metrics, same columns as the .172/.173 comparison.csv (package_0172.row_of)."""
    ls=r['rescue_sessions']['longest_including_ongoing']
    z=dict(return_rebate70_pct=r['return_rebate70_pct'],return_raw_pct=r['return_raw_pct'],mdd_raw_pct=r['mdd_raw_minute_pct'],mdd_rebate_exact_pct=r['mdd_rebate70_exact_minute_pct'],max_margin_pct=r['max_margin_usage_pct'],liquidated=r['liquidated'],
      rescue_sessions=r['rescue_sessions']['total'],rescue_ongoing_at_end=r['rescue_sessions']['ongoing'],longest_session_hours=ls['hours'] if ls else 0,
      margin_pause_skips=r['margin_guard_skips'],held_repay_events=r['repayment']['events'])
    tr=r['trapped_total_at_end']['total'];hh=r['initial_held_open_at_end']['total'];nn=r['normal_nonheld_open_at_end']['total']
    z.update(stuck_total_open_end=tr['count'],stuck_total_open_end_unreal=round(tr['unrealized_gross'],6),held_normal_open_end=hh['count'],held_normal_open_end_unreal=round(hh['unrealized_gross'],6),
      normal_nonheld_open_end=nn['count'],normal_nonheld_open_end_unreal=round(nn['unrealized_gross'],6))
    g=r.get('rules169')
    if g:
        ra=g['rescue_adds_open_at_end']
        z.update(rescue_adds_open_end=ra['count'],rescue_adds_open_end_unreal=ra['unrealized_gross'],
          pause_hours_L=g['trend_pause_hours']['regime']['L'],pause_hours_S=g['trend_pause_hours']['regime']['S'],pause_hours_active_L=g['trend_pause_hours']['while_rescue_active']['L'],pause_hours_active_S=g['trend_pause_hours']['while_rescue_active']['S'],
          pause_suppressed=sum(g['pause_suppressed_placements'].values()),pause_cancels=sum(g['pause_slot_cancels'].values()))
        g7=g.get('rules170')
        if g7:
            s=g7['stop_loss'];z.update(sl_count=s['count'],sl_contracts=s['contracts'],sl_realized_raw=s['realized_pnl_raw'],sl_realized_rebate70=s['realized_pnl_rebate70'],sl_held_removed=s['held_removed'],sl_session_ends=s['session_ends'],
              div1m_refused=sum(sum(x.values()) for x in g7['div1m_refused'].values()),off_events166=g7['off_events166'],neutral_hours=g7['neutral_pause_hours'])
        g8=g.get('rules171')
        if g8:z.update(v2_blocked=sum(g8['max2_blocked']['open'].values()),v2_market_minute_checks_blocked=sum(g8['max2_blocked']['market'].values()),v2_blocked_open_L=g8['max2_blocked']['open']['L'],v2_blocked_open_S=g8['max2_blocked']['open']['S'],v2_blocked_market_L=g8['max2_blocked']['market']['L'],v2_blocked_market_S=g8['max2_blocked']['market']['S'],bounce_short_refused=g8['bounce_short_refused'],slope_bars=g8['params']['slope_bars'],rescue_size_pct=g8['params']['rescue_size_pct'],rescue_margin_pct=g8['params']['rescue_margin_pct'],max_normal_side=g8['params']['max_normal_side'])
        g9=g.get('rules173') or g.get('rules172')
        z['rescue_tp']=g9['params']['rescue_tp'] if g9 else r['rescue_tp159']
        for k,vv in g['pnl_by_side_kind'].items():
            if k.endswith('_net'):continue
            z['pnl_rebate_'+k]=vv['realized_pnl_rebate70'];z['open_unreal_'+k]=vv['open_unrealized_gross'];z['open_count_'+k]=vv['open_count']
    else:
        z['rescue_tp']=r['rescue_tp159']
    return z
