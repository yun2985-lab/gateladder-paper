"""0.9.151 requested paper ONLY: Engine27 + rescue3%, pre-order margin50, normal cap20.
No prospective margin cap and no check at fill: existing orders/TPs stay intact.
A skipped qualifying third tick is consumed; retry only at a new third-tick signal.
Exact minute-close rebate accounting is observational only, not sizing capital.
"""
import math,time
from engine27 import Engine27,near148
from engine5 import cr_step,TICK

class Engine28(Engine27):
    def __init__(s,*a,**k):
        super().__init__(*a,**k);s.version='0.9.151 요청조건'
        s.margin50_skips=0;s.margin50_skips_by_side={'L':0,'S':0};s.margin50_last_block={True:None,False:None}
        s.rebate_peak151=s.start;s.rebate_mdd151=0.;s.monthly151={};s.acct151_rows=[];s.last_mark151=None
    def capped(s,buy,px):return s.side_share(buy,px)>=20
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        if strat=='cyc' and notional is not None:notional*=.5 # inherited current-size multiplier3: raw2% -> user3%, not old6%
        return super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
    def margin_use151(s,px):
        eq=s.equity(px)
        return (eq-s.free(px))/eq*100 if eq>0 else None
    def cr_bar(s,t):
        if getattr(s,'warm',False):return
        bars=s.pb[3]
        for buy in (True,False):
            r=s.cr[buy]
            if r['slot'] and t-r['slot']['blk']>=2*180000:r['slot']=None
            if r['phase']!='active' or len(bars)<40:continue
            signal=(r.get('started'),t)
            if s.margin50_last_block[buy]==signal:continue # no recheck/retry of a consumed blocked signal
            k=len(bars)-1
            if r['ticks'] is None:r['ticks']={};cr_step(r['ticks'],bars,k,buy);continue
            hit=cr_step(r['ticks'],bars,k,buy)
            if not hit or r['slot']:continue
            adds=s.open_adds(buy)
            if len(adds)>=20:continue
            px=bars[k][4];px=math.floor(px/TICK)*TICK if buy else math.ceil(px/TICK)*TICK
            near=near148([p['entry'] for p in adds],px)
            if near is not None:
                s.log(t,'CYCLE add skipped %.1f within 0.3%% of open add %.1f'%(px,near));continue
            # Explicit user formula, unrounded, at new limit placement only.
            # Evaluate only otherwise qualifying signals, after concurrent/gap guards.
            mark=bars[k][4];mu=s.margin_use151(mark)
            if mu is not None and mu>=50:
                side='L' if buy else 'S';s.margin50_skips+=1;s.margin50_skips_by_side[side]+=1;s.margin50_last_block[buy]=signal
                s.log(t,'MARGIN50_SKIP %s count%d usage%.10f equity%.8f available%.8f next3tick-only'%(side,s.margin50_skips,mu,s.equity(mark),s.free(mark)))
                continue
            r['slot']=dict(px=px,blk=t)
            s.log(t,'CYCLE add limit %s %.1f (3m 3-tick; open %d/20, gap0.3%%)'%('L' if buy else 'S',px,len(adds)))
    def mark(s,t,c,h=None,l=None):
        super().mark(t,c,h,l);s.last_mark151=(t,c)
        if getattr(s,'warm',False):return
        raw=s.equity(c);reb=raw+s.rebate;s.rebate_peak151=max(s.rebate_peak151,reb)
        if s.rebate_peak151>0:s.rebate_mdd151=max(s.rebate_mdd151,(s.rebate_peak151-reb)/s.rebate_peak151)
        month=time.strftime('%Y-%m',time.localtime(t/1000))
        if month not in s.monthly151:
            prev=next(reversed(s.monthly151.values()))['end'] if s.monthly151 else s.start
            s.monthly151[month]=dict(month=month,start=prev,end=reb,first_bar=t,last_bar=t)
        s.monthly151[month].update(end=reb,last_bar=t)
        s.acct151_rows.append((t,raw,s.rebate,s.margin(),c,s.margin50_skips))
