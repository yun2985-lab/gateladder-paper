""".153 on unchanged Engine29: old SAME-session adds>=24h after initial held gone.
Retain original held IDs/g0 while rescue stays active, so spent losses NEVER reset.
With no initial held remaining, only side ROI>=0 (or flat) ends the rescue.
User ABS unit-loss formula applies to ALL eligible old adds, including nonlosing;
source signed-loss/tick/single-order differences are explicitly documented.
"""
from decimal import ROUND_FLOOR
import math
from engine29 import Engine29,D,UNIT
from engine17 import START_ROI
from engine5 import TICK
DAY=24*3600000
class Engine30(Engine29):
    def __init__(s,*a,stale_enabled=True,**k):
        super().__init__(*a,**k);s.version='0.9.153 요청조건';s.stale_enabled153=stale_enabled
        s.repayment_by_target153={x:dict(events=0,contracts=0) for x in ('HELD','OLD_ADDS')}
    def held_open153(s,buy,r):
        ids=set(r.get('held',[]));return [p for p in s.pos if p['id'] in ids and p['n']>0]
    def stale_adds153(s,buy,r,asof):
        return [p for p in s.pos if p['strat']=='cyc' and p['buy']==buy and p['n']>0 and p.get('cycle_session152')==r.get('started') and asof-p['t']>=DAY]
    def end_if_roi153(s,buy,r,t,mark,reason):
        roi=s.side_roi(buy,mark)
        if roi is None or roi>=0:
            s._finish152(buy,r,t,reason);return True
        return False
    def repay153(s,buy,r,t,mark):
        if not s.repay_enabled152 or r['phase']!='active' or mark<=0:return
        asof=t+60000
        if r.get('last_repay_block153')==asof:return
        r['last_repay_block153']=asof
        held=s.held_open153(buy,r);kind='HELD' if held else 'OLD_ADDS'
        if held:
            if s._recovery(buy,r,mark)>=0:return
            targets=[p for p in held if (D(mark)-D(p['entry']))*(1 if buy else -1)<0]
        else:targets=s.stale_adds153(buy,r,asof) # young/other-session adds NEVER eligible
        px=D(mark)*(D('0.9995') if buy else D('1.0005'));choices=[]
        for p in targets:
            loss=abs(D(p['entry'])-px)*UNIT+px*UNIT*D('0.0005')
            if loss>0:choices.append((loss,p['id'],p))
        before=s.repayment_events152
        for loss,_,p in sorted(choices,key=lambda v:(v[0],v[1])):
            bank=s.bank152(buy,r);k=min(p['n'],int((bank/loss).to_integral_value(rounding=ROUND_FLOOR))) if bank>0 else 0
            if k<1:break
            pending=list(p['tps'][p['tpi']:]) or list(p.get('tps_h',[])[p['tpi']:]);left=k;plan=[]
            for target,q in pending:
                cut=min(q,left);left-=cut
                if q-cut>0:plan.append((target,q-cut))
            s.close(t,p,k,float(px),'rescue_repay152') # inherited exact fill/taker fee/gross ledgers
            s.trades[-1]['repayment_target153']=kind
            if p['n']>0:
                p['tps']=p['tps'][:p['tpi']]+plan;p['tps_h']=list(p['tps']);p['repay_tp_protected152']=True
                assert sum(q for _,q in p['tps'][p['tpi']:])==p['n'],'remaining TP contract mismatch'
            s.repayment_events152+=1;s.repayment_contracts152+=k
            s.repayment_by_target153[kind]['events']+=1;s.repayment_by_target153[kind]['contracts']+=k
            rs=s._session_record152(buy,r)
            if rs is not None:
                rs['repayment_events152']=rs.get('repayment_events152',0)+1;rs['repayment_contracts152']=rs.get('repayment_contracts152',0)+k
            ev=dict(t=t,side='L' if buy else 'S',session_start=r['started'],id=p['id'],target=kind,contracts=k,age_ms=asof-p['t'],price=str(px),estimated_loss_per_contract=str(loss),bank_before=str(bank),bank_after=str(s.bank152(buy,r)))
            s.repayment_log152.append(ev);s.log(t,'REPAY153 '+str(ev))
        if s.repayment_events152>before:s.repayment_batches152+=1
        if not s.held_open153(buy,r):s.end_if_roi153(buy,r,t,mark,'no_held_roi_recovered153')
    def rescue_tick(s,t,o,h,l,c):
        if not s.stale_enabled153:return super().rescue_tick(t,o,h,l,c) # exact .152 counterfactual
        s.tri_tick(t,o,h,l,c)
        if getattr(s,'warm',False):return
        for buy in (True,False):
            r=s.cr[buy];roi=s.side_roi(buy,c);sd='L' if buy else 'S'
            if r['phase']!='active':
                if roi is not None and roi<=START_ROI:
                    r.update(phase='active',started=t,adds=0,ticks=None,lastAdd=None,slot=None,ntr=len(s.trades))
                    held=[p for p in s.pos if p['buy']==buy and p['strat']!='cyc' and p['n']>0]
                    for p in held:p['tps_h']=p['tps'];p['tps']=p['tps'][:p['tpi']];p['rhold']=True
                    r['held']=[p['id'] for p in held];r['held_g0_152']={i:s.realized_gross152.get(i,D(0)) for i in r['held']}
                    r.pop('last_repay_block153',None)
                    s.crlog.append(dict(t=t,side=sd,start_roi=round(roi,2),adds=0));s.rescues.append(dict(t=t,side=sd,roi=round(roi,2),adds=0,held=len(held),initial_held_ids152=list(r['held']),repayment_events152=0,repayment_contracts152=0))
                    s.log(t,'CYCLE RESCUE START %s ROI %.2f%% · initial held%d · same-side new entries blocked'%(sd,roi,len(held)))
                continue
            hp=s.held_open153(buy,r)
            if roi is None:
                s._finish152(buy,r,t,'flat153');continue
            if not hp:
                if s.end_if_roi153(buy,r,t,c,'no_held_roi_recovered153'):continue
            else:
                rec=s._recovery(buy,r,c)
                if rec>=0:
                    at=math.floor(c/TICK)*TICK if buy else math.ceil(c/TICK)*TICK
                    for p in hp:s.close(t,p,p['n'],at,'rescue_hold_100%',limit=True)
                    # Explicit .153 override: legacy100% still closes held, but
                    # does NOT end while remaining side position ROI<0.
                    if s.end_if_roi153(buy,r,t,c,'legacy100_and_roi_recovered153'):continue
            if (t+60000)%180000==0:s.repay153(buy,r,t,c)
