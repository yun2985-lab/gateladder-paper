"""0.9.147 version2-only adapter on engine25 (.144, no Bollinger).
.145/.146 are display-only. New MA touch of20/60/120 on15m/1h/4h:
SMA rises/falls twice, first wick touch from above/below, close holds MA.
3% available, maker5bars, TP100/100/50. Prior overrides unchanged.
"""
import math
from engine25 import Engine25
from engine5 import FR,LOOKBACK,LEV,TICK,tat

def ma_touch(bars,p):
    n=len(bars)
    if n<p+3:return 0
    cl=[x[4] for x in bars];m0=sum(cl[-p-2:-2])/p;m1=sum(cl[-p-1:-1])/p;m2=sum(cl[-p:])/p
    b,pb=bars[-1],bars[-2]
    if m0<m1<m2 and b[3]<=m2 and b[4]>=m2 and pb[3]>m1:return 1
    if m0>m1>m2 and b[2]>=m2 and b[4]<=m2 and pb[2]<m1:return -1
    return 0

class Engine26(Engine25):
    def __init__(s,*a,**k):super().__init__(*a,**k);s.version='0.9.147 현재 비율';s.mt_slots=[]
    def set_exits(s,p,mode):
        if mode=='mt':
            off=50 if p['strat']=='mt240' else 100;x=p['entry']+(off if p['buy'] else -off)
            x=(math.ceil(x/TICK-1e-9) if p['buy'] else math.floor(x/TICK+1e-9))*TICK
            p['tps']=[(x,p['n'])];p['be']=False
        else:super().set_exits(p,mode)
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        if strat.startswith(('pat','ma')):
            f=strat[3:] if strat.startswith('pat') else strat[2:]
            if any(p['buy']==buy and p['strat']=='mt'+f and abs(p['entry']-px)<100 for p in s.pos):return None
        return super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
    def pat_bar(s,f,t):
        super().pat_bar(f,t)
        if getattr(s,'warm',False) or f not in (15,60,240):return
        bars=s.pb[f][-LOOKBACK:]
        for i in range(len(bars)-1,0,-1):
            if bars[i][0]-bars[i-1][0]!=FR[f]:bars=bars[i:];break
        if len(bars)<60:return
        for p in (20,60,120):
            turn=ma_touch(bars,p)
            if turn:
                s.mt_slots.append(dict(f=f,buy=turn>0,period=p,price=bars[-1][4],frm=t,until=t+5*FR[f]))
                s.log(t,'MA TOUCH SIGNAL %dm SMA%d %s first touch'%(f,p,'L' if turn>0 else 'S'))
    def limits(s,t,o,h,l,c):
        hide={}
        for f in s.sigs:
            for buy in (True,False):
                near=[p for p in s.pos if p['buy']==buy and p['strat']=='mt%d'%f]
                if not near:continue
                keep=[];out=[];blk=t//FR[f]*FR[f]
                for sg in s.sigs[f][buy]:
                    px=tat(sg['line'],blk) if 'line' in sg else sg['price']
                    (out if any(abs(p['entry']-px)<100 for p in near) else keep).append(sg)
                if out:hide[(f,buy)]=out;s.sigs[f][buy]=keep
        try:super().limits(t,o,h,l,c)
        finally:
            for (f,buy),out in hide.items():s.sigs[f][buy]+=out
        if getattr(s,'warm',False):return
        for sg in s.mt_slots:
            if sg.get('filled') or not sg['frm']<=t<sg['until']:continue
            buy=sg['buy'];f=sg['f']
            if s.capped(buy,o) or s.rescue_blocks(buy):continue
            px=math.floor(sg['price']/TICK)*TICK if buy else math.ceil(sg['price']/TICK)*TICK
            px=min(px,round(o-TICK,1)) if buy else max(px,round(o+TICK,1))
            if any(p['buy']==buy and p['strat'] in ('pat%d'%f,'ma%d'%f,'mt%d'%f) and abs(p['entry']-px)<100 for p in s.pos):continue
            if l<=px if buy else h>=px:
                p=s.open(t,'mt%d'%f,buy,px,info='SMA%d touch %dm'%(sg['period'],f),limit=True,notional=max(0,s.free(px))*.03*LEV,exitmode='mt')
                if p:sg['filled']=True
        s.mt_slots=[x for x in s.mt_slots if not x.get('filled') and x['until']>t]
