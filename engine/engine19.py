"""0.9.138 BTC paper adapter on engine17. Preserves historical settings.
New MA turns, side exposure cap, manual-line wick following. Optional multi-asset
DCA is not enabled. Existing learned-line approximation and all-auto modes retained.
"""
import math,copy
from decimal import Decimal,ROUND_HALF_UP
from engine17 import Engine17
from engine13 import SWITCH
from engine5 import FR,LOOKBACK,TICK,LEV,tat,atrw,W,lid

def ma_turn(bars,p):
    if len(bars)<p+2:return 0
    d1=bars[-2][4]-bars[-p-2][4];d2=bars[-1][4]-bars[-p-1][4]
    return 1 if d1<0<d2 else -1 if d1>0>d2 else 0

def follow_line(bars,ln,high,tol,now):
    n=len(bars)
    if n<12 or ('until' in ln and bars[-1][0]>int(ln['until'])):return None
    a,b=int(ln['a']),int(ln['b']);ia=next((i for i,x in enumerate(bars) if x[0]>=a),0)
    after=[i for i,x in enumerate(bars) if x[0]>b]
    if not after:return None
    col=2 if high else 3;k=(max if high else min)(after,key=lambda i:bars[i][col]);ext=bars[k][col];v=tat(ln,bars[k][0])
    if (ext<=v+tol if high else ext>=v-tol) or n-1-k<5:return None
    anchors=range(ia,k-4)
    if not anchors:return None
    j=(min if high else max)(anchors,key=lambda i:(ext-bars[i][col])/(bars[k][0]-bars[i][0]))
    rnd=lambda v:float(Decimal(str(v)).quantize(Decimal('.1'),rounding=ROUND_HALF_UP))
    out=dict(a=bars[j][0],b=bars[k][0],p=rnd(bars[j][col]),q=rnd(ext),at=max(now,bars[k][0]))
    if 'until' in ln:out['until']=max(int(ln['until']),bars[k][0])
    return out

class Mix138:
    def __init__(s,*a,**k):
        super().__init__(*a,**k);s.edits=copy.deepcopy(s.edits);s.ma_slots=[];s.cap_state={True:False,False:False}
    def side_share(s,buy,px):
        total=s.equity(px)
        if total<=0 or px<=0:return 0
        return round(sum(p['qty'] for p in s.pos if p['buy']==buy)*px/3/total*100,2)
    def capped(s,buy,px):return s.side_share(buy,px)>=15
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        if strat!='cyc' and not getattr(s,'warm',False) and s.capped(buy,px):return None
        return super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
    def set_exits(s,p,mode):
        if mode=='ma':
            off=50 if p['strat']=='ma240' else 100;x=p['entry']+(off if p['buy'] else -off)
            x=(math.ceil(x/TICK-1e-9) if p['buy'] else math.floor(x/TICK+1e-9))*TICK
            p['tps']=[(x,p['n'])];p['be']=False
        else:super().set_exits(p,mode)
    def track_lines(s,f,t):
        bars=s.pb[f][-LOOKBACK:]
        if len(bars)<20:return
        ed=s.edits.get(f,{});tol=max(1e-8,atrw(W(bars))*.25);excluded=ed.setdefault('excluded',[])
        for m in ed.get('manual',[]):
            if m.get('at',0)>t or m['id'] in excluded or any(k in m for k in ('channel','tri','triangle')):continue
            ln={k:(int(v) if k in ('a','b','until','at') else float(v)) for k,v in m['line'].items() if k in ('a','b','p','q','until','at')}
            if m.get('both'):
                near=[min(bars,key=lambda x:abs(x[0]-ln[z])) for z in ('a','b')]
                high=sum(abs(x[2]-ln[z]) for x,z in zip(near,('p','q')))<sum(abs(x[3]-ln[z]) for x,z in zip(near,('p','q')))
            else:high=bool(m.get('resistance'))
            moved=follow_line(bars,ln,high,tol,t)
            if not moved:continue
            old=m['id'];new=lid(moved['a'],moved['b'],moved['p'],moved['q'])
            if new==old:continue
            excluded.append(old);m.update(id=new,line=moved,at=t,origin=m.get('origin',old),moved=m.get('moved',0)+1)
            for buy in (True,False):
                for sg in s.sigs[f][buy]:
                    if old in sg['key'] and not sg.get('filled'):sg['void']=True
            for (ff,key),bn in s.bnc.items():
                if ff==f and key=='manual:'+old:bn['done']=True
            s.log(t,'LINEFOLLOW %dm %s -> %s (5 bars)'%(f,old,new))
    def pat_bar(s,f,t):
        s.track_lines(f,t);super().pat_bar(f,t)
        if getattr(s,'warm',False) or f not in (15,60,240):return
        bars=s.pb[f][-LOOKBACK:]
        for p in (20,60,120):
            turn=ma_turn(bars,p)
            if turn:
                s.ma_slots.append(dict(f=f,buy=turn>0,period=p,price=bars[-1][4],frm=t,until=t+5*FR[f]))
                s.log(t,'MA SIGNAL %dm SMA%d %s'%(f,p,'L' if turn>0 else 'S'))
    def limits(s,t,o,h,l,c):
        hide={}
        if not getattr(s,'warm',False):
            for buy in (True,False):
                blocked=s.capped(buy,o) or s.cr[buy]['phase']=='active'
                if blocked!=s.cap_state[buy]:
                    s.cap_state[buy]=blocked;s.log(t,'ENTRY HOLD %s %s (side %.2f%%)'%('L' if buy else 'S',blocked,s.side_share(buy,o)))
                if blocked:
                    # Cancel resting order, retain signal eligibility until original expiry.
                    for f in s.sigs:hide[(f,buy)]=s.sigs[f][buy];s.sigs[f][buy]=[]
        try:super().limits(t,o,h,l,c)
        finally:
            for (f,buy),signals in hide.items():s.sigs[f][buy]=signals
        if getattr(s,'warm',False):return
        for sg in s.ma_slots:
            if sg.get('filled') or not sg['frm']<=t<sg['until']:continue
            buy=sg['buy']
            if s.capped(buy,o) or s.cr[buy]['phase']=='active':continue
            px=math.floor(sg['price']/TICK)*TICK if buy else math.ceil(sg['price']/TICK)*TICK
            px=min(px,round(o-TICK,1)) if buy else max(px,round(o+TICK,1))
            if any(p['buy']==buy and p['strat'] in ('pat%d'%sg['f'],'ma%d'%sg['f']) and abs(p['entry']-px)<100 for p in s.pos):continue
            if l<=px if buy else h>=px:
                p=s.open(t,'ma%d'%sg['f'],buy,px,info='SMA%d turn %dm'%(sg['period'],sg['f']),limit=True,notional=max(0,s.free(px))*.03*LEV,exitmode='ma')
                if p:sg['filled']=True
        s.ma_slots=[x for x in s.ma_slots if not x.get('filled') and x['until']>t]

class Engine19(Mix138,Engine17):
    def __init__(s,*a,**k):super().__init__(*a,**k);s.version='0.9.138+3pp'
