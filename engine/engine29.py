""".152 ONLY earned-profit contract repayment, based on unchanged Engine28/.151.
Bank matches source OfficeFeed.gross: price-only realised adds of THIS session
plus held realised price PnL SINCE start, NOT net fees/rebates; no reset/reuse.
User text takes precedence: every closed3m, losing held only, exact mark +/-0.05%,
absolute unit loss + estimated0.05% exit fee, sorted batches until unaffordable.
Actual immediate fills charge existing TAKER .042%,70% rebate, no extra slippage.
"""
from decimal import Decimal,ROUND_FLOOR
from engine28 import Engine28
from engine4 import Engine4,SLIP
from engine8 import TAKER
D=lambda x:Decimal(str(x))
UNIT=Decimal('0.0001')

class Engine29(Engine28):
    def __init__(s,*a,repay_enabled=True,**k):
        super().__init__(*a,**k);s.version='0.9.152 요청조건';s.repay_enabled152=repay_enabled
        s.realized_gross152={};s.cyc_gross152={};s.repayment_events152=0;s.repayment_contracts152=0;s.repayment_batches152=0;s.repayment_log152=[]
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        p=super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
        if p is not None and strat=='cyc':p['cycle_session152']=s.cr[buy].get('started')
        return p
    def close(s,t,p,n,price,why,limit=False):
        before=len(s.trades);oldn=p['n'];chip=why=='rescue_repay152'
        actual=price if limit or chip else price*(1-SLIP if p['buy'] else 1+SLIP)
        if chip:
            old=getattr(s,'_fr',None);s._fr=TAKER
            try:Engine4.close(s,t,p,n,price,why,limit=True)
            finally:s._fr=old
        else:super().close(t,p,n,price,why,limit)
        k=oldn-p['n']
        if k<=0:return
        gross=(D(actual)-D(p['entry']))*UNIT*k*(1 if p['buy'] else -1)
        s.realized_gross152[p['id']]=s.realized_gross152.get(p['id'],D(0))+gross
        if p['strat']=='cyc' and p.get('cycle_session152') is not None:
            key=(p['buy'],p['cycle_session152']);s.cyc_gross152[key]=s.cyc_gross152.get(key,D(0))+gross
        for tr in s.trades[before:]:tr.update(actual_exit152=actual,cycle_session152=p.get('cycle_session152'),gross_exact152=str(gross))
    def bank152(s,buy,r):
        g0=r.get('held_g0_152',{})
        return s.cyc_gross152.get((buy,r.get('started')),D(0))+sum((s.realized_gross152.get(i,D(0))-g0.get(i,D(0)) for i in r.get('held',[])),D(0))
    def _recovery(s,buy,r,px):
        if not s.repay_enabled152:return super()._recovery(buy,r,px)
        # Preserve .151's existing full-recovery calculation. The ONLY extra
        # term is held realised PnL since start: new repayments must not vanish
        # from its recovery accounting after the contracts have been closed.
        g0=r.get('held_g0_152',{})
        paid=sum((s.realized_gross152.get(i,D(0))-g0.get(i,D(0)) for i in r.get('held',[])),D(0))
        return super()._recovery(buy,r,px)+float(paid)
    def _session_record152(s,buy,r):
        return next((x for x in reversed(s.rescues) if x['side']==('L' if buy else 'S') and x['t']==r.get('started')),None)
    def _finish152(s,buy,r,t,reason):
        r.update(phase='watch',slot=None,held=[])
        rs=s._session_record152(buy,r)
        if rs is not None:rs.update(done=t,end_reason152=reason)
        s.log(t,'CYCLE RESCUE END %s %s · same-side normal entries resume'%('L' if buy else 'S',reason))
    def repay152(s,buy,r,t,mark):
        if not s.repay_enabled152 or r['phase']!='active' or not r.get('held') or mark<=0:return
        block=t+60000
        if r.get('last_repay_block152')==block:return
        r['last_repay_block152']=block
        if s._recovery(buy,r,mark)>=0:return # legacy full100% recovery has priority
        px=D(mark)*(D('0.9995') if buy else D('1.0005'));ids=set(r['held']);choices=[]
        for p in s.pos:
            if p['id'] not in ids or p['n']<=0 or (D(mark)-D(p['entry']))*(1 if buy else -1)>=0:continue
            unit=abs(D(p['entry'])-px)*UNIT+px*UNIT*D('0.0005')
            if unit>0:choices.append((unit,p['id'],p))
        count_before=s.repayment_events152
        for loss,_,p in sorted(choices,key=lambda v:(v[0],v[1])):
            bank=s.bank152(buy,r);k=min(p['n'],int((bank/loss).to_integral_value(rounding=ROUND_FLOOR))) if bank>0 else 0
            if k<1:break
            # Keep original remaining TP prices; reduce their quantities from
            # the current stage first, never changing original n0/entry fee.
            pending=list(p['tps'][p['tpi']:]) or list(p.get('tps_h',[])[p['tpi']:]);left=k;plan=[]
            for target,q in pending:
                cut=min(q,left);left-=cut
                if q-cut>0:plan.append((target,q-cut))
            s.close(t,p,k,float(px),'rescue_repay152')
            if p['n']>0:
                p['tps']=p['tps'][:p['tpi']]+plan;p['tps_h']=list(p['tps']);p['repay_tp_protected152']=True
                assert sum(q for _,q in p['tps'][p['tpi']:])==p['n'],'remaining TP contract mismatch'
            s.repayment_events152+=1;s.repayment_contracts152+=k
            rs=s._session_record152(buy,r)
            if rs is not None:rs['repayment_events152']=rs.get('repayment_events152',0)+1;rs['repayment_contracts152']=rs.get('repayment_contracts152',0)+k
            event=dict(t=t,side='L' if buy else 'S',session_start=r['started'],id=p['id'],contracts=k,price=str(px),estimated_loss_per_contract=str(loss),bank_before=str(bank),bank_after=str(s.bank152(buy,r)))
            s.repayment_log152.append(event);s.log(t,'REPAY152 '+str(event))
        if s.repayment_events152>count_before:s.repayment_batches152+=1
        if not any(p['id'] in ids and p['n']>0 for p in s.pos):s._finish152(buy,r,t,'all_initial_held_repaid')
    def rescue_tick(s,t,o,h,l,c):
        before={buy:(s.cr[buy]['phase'],s.cr[buy].get('started')) for buy in (True,False)}
        old_done=[x.get('done') for x in s.rescues]
        super().rescue_tick(t,o,h,l,c)
        if getattr(s,'warm',False):return
        # Metadata correction only: inherited older engines wrote done to the
        # latest OTHER-side session. Attribute completion to its real side/start.
        for x,done in zip(s.rescues,old_done):
            if done is None:x.pop('done',None)
            else:x['done']=done
        for buy in (True,False):
            r=s.cr[buy];was,started=before[buy]
            if r['phase']=='active' and (was!='active' or r.get('started')!=started):
                r['held_g0_152']={i:s.realized_gross152.get(i,D(0)) for i in r.get('held',[])}
                rs=s._session_record152(buy,r)
                if rs is not None:rs.update(initial_held_ids152=list(r.get('held',[])),repayment_events152=0,repayment_contracts152=0)
            if r['phase']=='active':
                active_rs=s._session_record152(buy,r)
                if active_rs is not None:active_rs.pop('done',None)
            if was=='active' and r['phase']!='active':
                rs=s._session_record152(buy,r)
                if rs is not None:rs.update(done=t,end_reason152='legacy_recovery_or_held_finished')
            if (t+60000)%180000==0:s.repay152(buy,r,t,c)
    def overlap(s,t,c):
        protected={p['id']:list(p['tps']) for p in s.pos if p.get('repay_tp_protected152') and p.get('rhold')}
        super().overlap(t,c)
        for p in s.pos:
            if p['id'] in protected:p['tps']=protected[p['id']]
