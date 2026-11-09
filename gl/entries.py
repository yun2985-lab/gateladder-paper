"""entries.csv exporter. Ported from export_entries_0173.py: identical row/column logic, but it reads the
in-memory finished engine plus this run's events.log / equity_minutes.csv / minute arrays instead of a
frozen replay_complete directory and pickle. Encoding is always UTF-8."""
import argparse, collections, csv, hashlib, json, math, pickle, re
from pathlib import Path
from decimal import Decimal as Dec
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
def kst(t): return datetime.fromtimestamp(float(t)/1000,timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
def num(x):
    if x is None or not np.isfinite(float(x)): return ''
    return format(float(x),'.12g')
def dumpcsv(path, rows, fields):
    with open(path,'w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def recorded_entry_fee154(audit, entry, contracts):
    """Use actual recorded fee; rate is validated, never guessed from strategy name."""
    assert audit and audit['n']==contracts and contracts>0
    assert abs(float(audit['entry'])-entry)<1e-8
    fee=float(audit['fee']);notional=entry*(contracts*.0001)
    matches=[rate for rate in (.00018,.00042) if abs(fee-notional*rate)<1e-10]
    assert len(matches)==1, ('Unknown recorded entry fee',fee,notional)
    return fee,matches[0]
def exit_fee_rate154(reason):
    if reason in ('tp1','tp2','tp3','rescue_hold_100%'):return .00018
    if reason in ('rescue_repay152','stale30d_169','losscap10_169','opprepay_169','sl3_170') or reason.startswith('LIQUIDATION'):return .00042
    raise ValueError('Unreviewed exit reason: '+reason)
def export(e,cfg,report,events_path,acct_path,T,V,O,version,entries_name='entries.csv'):
    """cfg needs start, replay_end_ms. Writes O/entries_name, O/validation_entries.json, O/cash_checks.csv."""
    O=Path(O)
    assert type(e).__name__ in ('Engine167','Engine169','Engine170','Engine171','Engine172','Engine173'), 'entries exporter reviewed only for Engine167..Engine173'
    start=cfg['start'];end=cfg['replay_end_ms'];seed=report['initial'];mark=report['price'];v152=True
    g={}
    for tr in e.trades:
        x=g.setdefault(tr['id'],dict(id=tr['id'],strat=tr['strat'],side=tr['side'],t=tr['t_in'],entry_reported=tr['entry'],info=tr['info'],tr=[]));x['tr'].append(tr)
    for pos in e.pos:
        x=g.setdefault(pos['id'],dict(id=pos['id'],strat=pos['strat'],side='L' if pos['buy'] else 'S',t=pos['t'],entry_reported=pos['entry'],info=pos['info'],tr=[]));x['open']=pos
    xs=sorted(g.values(),key=lambda x:x['id']);assert [x['id'] for x in xs]==list(range(1,e.nid+1))
    held={i for r in e.rescues for i in r.get('initial_held_ids152',[])+r.get('adopted_held_ids159',[])}
    # All OPEN records, including cyc; chronological ordinal is the engine's nid.
    logs=[];active={'L':False,'S':False}
    for line in Path(events_path).read_text(encoding='utf-8').splitlines():
        m=re.match(r'(\d{4}-\d\d-\d\d \d\d:\d\d) KST (.*)',line)
        if not m:continue
        text=m[2]
        r=re.match(r'CYCLE RESCUE (START|END) ([LS]) ',text)
        if r:active[r[2]]=r[1]=='START'
        r=re.match(r'OPEN (\S+) ([LS]) ([\d.]+) (\d+)ct \| (.*)',text)
        if r:logs.append(dict(time=m[1],strat=r[1],side=r[2],entry=float(r[3]),n=int(r[4]),info=r[5],rescue=int(active[r[2]])))
    assert len(logs)==len(xs)
    cash_events=[];fees_total=0.;qty_errors=[];rounding_errors=[];gross_discrep=[]
    # Reconstruct historical cash/position deltas from existing fills, never signals.
    for x,lg in zip(xs,logs):
        tr=x['tr'];pos=x.get('open');d=1 if x['side']=='L' else -1
        x['n']=sum(round(t['qty']*10000) for t in tr)+(pos['n'] if pos else 0);x['qty']=x['n']*.0001
        assert lg['time']==kst(x['t']) and lg['strat']==x['strat'] and lg['side']==x['side'] and lg['n']==x['n'] and lg['info']==x['info']
        if pos:entry=pos['entry']
        elif tr and 'gross_exact152' in tr[0]:
            z=tr[0];entry=float(Dec(str(z['actual_exit152']))-Dec(z['gross_exact152'])/(Dec(str(z['qty']))*d))
        else:entry=None
        x['entry']=entry if entry is not None else x['entry_reported'];x['entry_exact']=entry is not None
        assert abs(lg['entry']-x['entry'])<=.051
        assert start<=x['t']<end
        x['entry_fee'],x['entry_rate']=recorded_entry_fee154(e.entry_audit154.get(x['id']),x['entry'],x['n'])
        if pos and v152:assert abs(x['entry_fee']-pos['fee'])<1e-8
        x['rescue_active']=lg['rescue'];x['exit_t']=max([z['t'] for z in tr],default=0) if not pos else None
        if pos:assert pos['n0']==x['n']
        assert all(t['t']>=x['t'] for t in tr)
        x['realized']=sum(z['pnl_rebate'] for z in tr)
        x['unrealized']=((mark-x['entry'])*pos['qty']*d-pos['fee']*pos['n']/pos['n0']*.3) if pos else 0.
        x['total']=x['realized']+x['unrealized'];x['exact_realized']=0.
        if not v152: continue
        q=x['qty'];en=x['entry'];fee=x['entry_fee'];fees_total+=fee
        # columns: time,cash_delta,fee_delta,signed_qty,signed_basis,margin,Lqty,Sqty
        cash_events.append((x['t'],-fee,fee,d*q,d*q*en,q*en/3,q if d==1 else 0,q if d==-1 else 0))
        for z in tr:
            q=z['qty'];out=z['actual_exit152'];gross=float(z['gross_exact152']);rate=exit_fee_rate154(z['why']);ef=x['entry_fee']*round(q*10000)/x['n'];xf=out*q*rate
            assert abs(gross-(out-en)*q*d)<1e-8
            exact=gross-(ef+xf)*.3;x['exact_realized']+=exact
            rounding_errors.append(abs(exact-z['pnl_rebate']));fees_total+=xf
            cash_events.append((z['t'],gross-xf,xf,-d*q,-d*q*en,-q*en/3,-q if d==1 else 0,-q if d==-1 else 0))
    # Immutable local OHLC snapshot in memory. Strictly truncate at frozen end.
    B=np.column_stack([np.asarray(T,dtype=float),np.asarray(V,dtype=float)])
    B=B[B[:,0]<end];assert np.all(np.diff(B[:,0])==60000);ts=B[:,0]
    assert ts[0]<=start and ts[-1]==end-60000
    bars_hash=hashlib.sha256(B.astype('<f8').tobytes()).hexdigest()
    # Minute-close accounting validation, including reconstructed cash at every saved minute.
    acct=pd.read_csv(acct_path).sort_values('t')
    assert acct.t.is_unique
    account_adjustment=0.
    if e.liq:
        account_adjustment=e.cash-(seed+sum(z[1] for z in cash_events))
        if abs(account_adjustment)>1e-7:
            lt=min(z['t'] for z in e.trades if z['why'].startswith('LIQUIDATION'));assert account_adjustment<=0
            cash_events.append((lt,account_adjustment,0,0,0,0,0,0))
    ce=np.asarray(sorted(cash_events,key=lambda r:r[0]),dtype=float).reshape((-1,8)) if v152 else None
    validation={}
    if v152:
        sums=np.vstack([np.zeros(7),np.cumsum(ce[:,1:],axis=0)])
        ix=np.searchsorted(ce[:,0],acct.t.to_numpy(),side='right');s=sums[ix];prices=acct.price.to_numpy();cash=seed+s[:,0];eq=cash+prices*s[:,2]-s[:,3]
        archived_cash=acct.equity_raw.to_numpy()-(prices*s[:,2]-s[:,3])
        errors=np.abs(eq-acct.equity_raw.to_numpy());reb_err=np.abs(s[:,1]*.7-acct.rebate_total.to_numpy());mar_err=np.abs(s[:,4]-acct.margin.to_numpy())
        validation.update(accounting_rows=len(acct),accounting_first=kst(acct.t.iloc[0]),accounting_last=kst(acct.t.iloc[-1]),minute_equity_max_abs_error=float(errors.max()),cash_series_max_abs_error=float(np.max(np.abs(cash-archived_cash))),minute_rebate_max_abs_error=float(reb_err.max()),minute_margin_max_abs_error=float(mar_err.max()),final_cash_reconstructed=seed+float(sums[-1,0]),final_cash_archive=float(e.cash),fees_reconstructed=fees_total,fees_archive=float(e.fees),max_fill_rounding_error=max(rounding_errors,default=0))
        assert errors.max()<1e-7 and reb_err.max()<1e-7 and mar_err.max()<1e-7
        assert abs(seed+sums[-1,0]-e.cash)<1e-7
        assert abs(fees_total-e.fees)<1e-7
        cashcheck=pd.DataFrame({'t_kst':[kst(t) for t in acct.t],'cash_reconstructed':cash,'cash_derived_from_frozen_equity':archived_cash,'equity_error':eq-acct.equity_raw.to_numpy()})
        # Compact audit only: maximum-error and periodic checkpoints, not publishing full data_y1.
        picks=sorted(set([0,len(acct)-1,int(np.argmax(errors))]+list(np.flatnonzero(np.r_[np.diff(acct.t.to_numpy()//(30*86400000))!=0,False]))))
        cashcheck.iloc[picks].to_csv(O/'cash_checks.csv',index=False)
    # Prior completed exchange-UTC daily / 4h / 1h OHLC. Only full buckets.
    def resample(minutes):
        span=minutes*60000;df=pd.DataFrame(B,columns=['t','o','h','l','c']);df['bucket']=(df.t//span).astype('int64')*span
        z=df.groupby('bucket',sort=True).agg(o=('o','first'),h=('h','max'),l=('l','min'),c=('c','last'),count=('c','size'));return z[z['count']==minutes]
    day=resample(1440);h4=resample(240);h1=resample(60)
    for n in (20,50,120):day['d_ma'+str(n)]=day.c.rolling(n,min_periods=n).mean()
    day['d_hi30']=day.h.rolling(30,min_periods=30).max();day['d_lo30']=day.l.rolling(30,min_periods=30).min()
    h4['h4_sma120']=h4.c.rolling(120,min_periods=120).mean()
    cc=h1.c.to_numpy();rr=np.full(len(cc),np.nan);delta=np.diff(cc)
    if len(delta)>=14:
        gain=np.maximum(delta,0);loss=np.maximum(-delta,0);ag=np.mean(gain[:14]);al=np.mean(loss[:14]);rr[14]=100-100/(1+ag/al) if al>0 else 100
        for i in range(14,len(delta)):
            ag=(ag*13+gain[i])/14;al=(al*13+loss[i])/14;rr[i+1]=100-100/(1+ag/al) if al>0 else 100
    h1['h1_rsi14']=rr
    fields='id,strat,rule,frame,side,entry_time,entry_price,qty_btc,pct,tp_price,exit_time,exit_price,exit_reason,pnl_usdt,hold_hours,mae_pct,mae_time,mfe_pct,held_by_rescue,rescue_side_active,exposure_side_pct,margin_use_pct'.split(',')
    extras=['realized_pnl_rebate70','unrealized_pnl_rebate70','total_pnl_rebate70','realized_pnl_exact_rebate70','total_pnl_exact_rebate70','remaining_qty_btc','entry_margin_usdt','entry_margin_seed_pct','pct_basis','entry_snapshot_status','exit_history_raw','mae_mfe_basis','d_ma20','d_ma50','d_ma120','d_hi30','d_lo30','h4_sma120','h1_rsi14','daily_asof_kst','h4_asof_kst','h1_asof_kst']
    close_times={z['t'] for z in e.trades};same_t=collections.defaultdict(list);rows=[];pnl_exact_total=0.;excursion_bars=0
    for x in xs:
        en=x['entry'];d=1 if x['side']=='L' else -1;q=x['qty'];pos=x.get('open');tr=x['tr'];t=x['t'];last=end if pos else x['exit_t']
        r=dict.fromkeys(fields+extras,'');r.update(id=x['id'],strat=x['strat'],rule=x['info'],side=x['side'],entry_time=kst(t),entry_price=num(en),qty_btc=num(q),exit_time='' if pos else kst(last),exit_price='' if pos else num(sum(z['actual_exit152']*z['qty'] for z in tr)/q),exit_reason='열림' if pos else '|'.join(dict.fromkeys('갚기(.152)' if z['why']=='rescue_repay152' else '구출회복정리' if z['why']=='rescue_hold_100%' else z['why'] for z in tr)),pnl_usdt=num(x['unrealized'] if pos else x['realized']),hold_hours=num((last-t)/3600000),held_by_rescue=int(x['id'] in held),rescue_side_active=x['rescue_active'],realized_pnl_rebate70=num(x['realized']),unrealized_pnl_rebate70=num(x['unrealized']),total_pnl_rebate70=num(x['total']),remaining_qty_btc=num(pos['qty'] if pos else 0),entry_margin_usdt=num(q*en/3),entry_margin_seed_pct=num(q*en/3/seed*100),pct_basis='actual_margin/pre_fill_available_at_fill_price',exit_history_raw='|'.join(dict.fromkeys(z['why'] for z in tr)),mae_mfe_basis='observed_boundary_safe_lower_bound_no_intrabar_order')
        frame='3m' if x['strat']=='cyc' else re.search(r'(\d+)$',x['strat']).group(1)+'m'
        r['frame']={'60m':'1h','240m':'4h'}.get(frame,frame)
        # TP is original target, never final/shifted target. Pure formula from frozen source.
        if v152:
            off=38 if x['strat']=='cyc' else (40 if x['strat'] in ('fib1','fib15') else (100 if x['strat'] in ('fib60','pat15') or (x['strat'].startswith(('ma','mt')) and frame!='240m') else 50))
            if x['strat'] in ('tri1','rsi1'):
                n=x['n'];parts=[math.floor(n*.4),math.floor((n-math.floor(n*.4))/2)];parts.append(n-sum(parts));q1=(parts[0] if min(parts)>=1 else math.floor(n*.4) or n)*.0001
                F=.00042*.3;off=(x['entry_fee']*.3+en*q*F)/(q1*(1-F*d))*5
            target=en+d*off;r['tp_price']=num((math.ceil(target/.1-1e-9) if d==1 else math.floor(target/.1+1e-9))*.1)
            r['realized_pnl_exact_rebate70']=num(x['exact_realized']);r['total_pnl_exact_rebate70']=num(x['exact_realized']+x['unrealized']);pnl_exact_total+=x['exact_realized']+x['unrealized']
        # No same-minute closes => pre-fill state is unambiguous; earlier OPENs same minute by id.
        if v152 and t not in close_times and x['strat'] not in ('tri1','rsi1'):
            si=sums[np.searchsorted(ce[:,0],t,side='left')].copy()
            for prev in same_t[t]:
                pd_=1 if prev['side']=='L' else -1;pq=prev['qty'];pe=prev['entry'];si+=np.array([-prev['entry_fee'],prev['entry_fee'],pd_*pq,pd_*pq*pe,pq*pe/3,pq if pd_==1 else 0,pq if pd_==-1 else 0])
            eq0=seed+si[0]+en*si[2]-si[3];free=eq0-si[4]
            if eq0>0 and free>0:
                r['exposure_side_pct']=num(round(si[5 if d==1 else 6]*en/3/eq0*100,2));r['margin_use_pct']=num(si[4]/eq0*100);r['pct']=num(q*en/3/free*100);r['entry_snapshot_status']='reconstructed_pre_fill_exact_order'
        if not r['entry_snapshot_status']:r['entry_snapshot_status']='missing_intraminute_close_order_or_market_reference'
        same_t[t].append(x)
        entry_open=x['id'] in getattr(e,'m1_entries162m',{}) or x['id'] in getattr(e,'ma_market_entries167',{})
        stop=end if pos else last+(60000 if tr[-1]['why'] in ('rescue_repay152','rescue_hold_100%') else 0)
        a0=np.searchsorted(ts,t+(0 if entry_open else 60000),side='left');a1=np.searchsorted(ts,stop,side='left');window=B[a0:a1]
        known=[en]+[z['actual_exit152'] for z in tr];low=min(known+([float(window[:,3].min())] if len(window) else []));high=max(known+([float(window[:,2].max())] if len(window) else []));adv=(en-low)/en*100 if d==1 else (high-en)/en*100;fav=(high-en)/en*100 if d==1 else (en-low)/en*100
        r.update(mae_pct=num(max(0,adv)),mae_time='',mfe_pct=num(max(0,fav)));excursion_bars+=len(window)
        assert float(r['mae_pct'])>=0 and float(r['mfe_pct'])>=0
        for table,span,names,timekey in [(day,86400000,['d_ma20','d_ma50','d_ma120','d_hi30','d_lo30'],'daily_asof_kst'),(h4,14400000,['h4_sma120'],'h4_asof_kst'),(h1,3600000,['h1_rsi14'],'h1_asof_kst')]:
            j=np.searchsorted(table.index.to_numpy()+span,t,side='right')-1
            if j>=0:
                for key in names:r[key]=num(table.iloc[j][key])
                r[timekey]=kst(int(table.index[j])+span);assert table.index[j]+span<=t
        audit=e.entry_audit154.get(x['id'])
        assert audit and abs(audit['entry']-en)<1e-8 and audit['n']==x['n']
        r['tp_price']=num(audit['first_tp']);r['pct']=num(q*en/3/audit['free']*100) if audit['free']>0 else ''
        r['exposure_side_pct']=num(audit['side_exposure_pct']);r['margin_use_pct']=num(audit['margin_usage_pct']);r['rescue_side_active']=int(audit['rescue_active']);r['entry_snapshot_status']='recorded_pre_fill154';r['h4_sma120']=num(audit['gate_values']['TREND']);r['h1_rsi14']=num(audit['gate_values']['RSI']);r['d_ma50']=num(audit['gate_values']['STRETCH'])
        for f,key in ((1440,'daily_asof_kst'),(240,'h4_asof_kst'),(60,'h1_asof_kst')):r[key]=kst(audit['gate_asof'][f]);assert audit['gate_asof'][f]<=x['t']
        rows.append(r)
    assert len({r['id'] for r in rows})==len(rows)
    normal=sum(x['strat']!='cyc' for x in xs);partial=sum(len(x['tr'])>1 for x in xs);openpartial=sum(bool(x.get('open')) and bool(x['tr']) for x in xs)
    pnl_logged_total=sum(x['total'] for x in xs)
    validation.update(version=version,source='in-memory run',start_kst=kst(start),end_kst=kst(end),rows=len(xs),normal_entries=normal,cyc_entries=len(xs)-normal,unique_ids=len(g),id_min=xs[0]['id'] if xs else None,id_max=xs[-1]['id'] if xs else None,closed_entries=sum(not bool(x.get('open')) for x in xs),open_entries=len(e.pos),exit_fill_records=len(e.trades),multiple_exit_records_ids=partial,partially_realized_open_ids=openpartial,initial_contracts=sum(x['n'] for x in xs),closed_contracts=sum(round(t['qty']*10000) for t in e.trades),remaining_contracts=sum(p['n'] for p in e.pos),sum_total_pnl_logged=pnl_logged_total,sum_pnl_column=sum(float(r['pnl_usdt']) for r in rows),open_entry_realized_sum=sum(x['realized'] for x in xs if x.get('open')),sum_total_pnl_exact=pnl_exact_total,report_profit=report['equity_rebate70']-seed,logged_total_minus_report=pnl_logged_total-(report['equity_rebate70']-seed),liquidation_nontrade_cash_adjustment=account_adjustment,exact_total_minus_report=pnl_exact_total+account_adjustment-(report['equity_rebate70']-seed),held_by_rescue=sum(r['held_by_rescue'] for r in rows),excursion_bar_observations=excursion_bars,local_bars_frozen_slice_sha256=bars_hash,missing={f:sum(r[f]=='' for r in rows) for f in fields+extras})
    assert validation['initial_contracts']==validation['closed_contracts']+validation['remaining_contracts']
    if v152:assert abs(validation['exact_total_minus_report'])<1e-6
    dumpcsv(O/entries_name,rows,fields+extras)
    (O/'validation_entries.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2,default=float),encoding='utf-8')
    return validation
