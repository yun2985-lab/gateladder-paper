"""0.9.143 BTC paper adapter on engine21.
.142 BB20 population-sd x2 return, 1m2%/15m3% available, maker5bars,
TP50/100; no signals if completed15m bandwidth grows above1.5x prior20 mean.
.143 rescue20 small entries require last completed4h close above/below SMA120.
Unknown/equal trend blocks. All prior paper overrides retained.
"""
import math,collections
from engine21 import Engine21
from engine13 import SWITCH
from engine5 import FR,LOOKBACK,TICK,LEV,tat

def bb(bars,end=None):
    end=len(bars)-1 if end is None else end
    if end<19 or end>=len(bars):return None
    vals=[x[4] for x in bars[end-19:end+1]];m=sum(vals)/20;sd=math.sqrt(sum((x-m)**2 for x in vals)/20)
    return m,m+2*sd,m-2*sd

def widening(bars):
    last=len(bars)-1
    if last<40:return None
    def width(i):
        b=bb(bars,i);return (b[1]-b[2])/b[0] if b and b[0]>0 else float('nan')
    now=width(last);prev=width(last-1);avg=sum(width(i) for i in range(last-20,last))/20
    return now>prev and now>1.5*avg

def quarters(input,block):
    groups={}
    for x in input:
        if x[0]+60000>block:break
        groups.setdefault(x[0]//900000*900000,[]).append(x)
    out=[]
    for q,rows in groups.items():
        if len(rows)!=15 or rows[0][0]!=q or rows[-1][0]!=q+840000 or any(rows[i][0]-rows[i-1][0]!=60000 for i in range(1,15)):continue
        if q+900000<=block:out.append([q,rows[0][1],max(x[2] for x in rows),min(x[3] for x in rows),rows[-1][4]])
    for i in range(len(out)-1,0,-1):
        if out[i][0]-out[i-1][0]!=900000:return out[i:]
    return out

def bb_back(bars,buy):
    a=bb(bars,len(bars)-2);b=bb(bars)
    if a is None or b is None:return False
    pc,c=bars[-2][4],bars[-1][4]
    return (pc<a[2] and c>=b[2] and c<b[0]) if buy else (pc>a[1] and c<=b[1] and c>b[0])

def trend143(bars,now=None):
    w=[x for x in bars if now is None or x[0]+14400000<=now]
    if len(w)<120:return 0
    w=w[-120:]
    if any(w[i][0]-w[i-1][0]!=14400000 for i in range(1,120)):return 0
    avg=sum(x[4] for x in w)/120;last=w[-1][4]
    return 1 if last>avg else -1 if last<avg else 0

class Mix143:
    def __init__(s,*a,**k):
        super().__init__(*a,**k);s.bb_minutes=collections.deque(maxlen=720);s.bb_slots=[]
    def flow143(s):
        w=s.pb[240];key=(id(w),len(w),w[0][0],w[-1][0],w[-1][4]) if w else None
        if not hasattr(s,'_flow143_key') or s._flow143_key!=key:
            s._flow143_key=key;s._flow143_value=trend143(w)
        return s._flow143_value
    def rescue_small(s,buy):
        return s.cr[buy]['phase']=='active' and s.cr[buy]['adds']>=20 and s.flow143()==(1 if buy else -1)
    def rescue_blocks(s,buy):return s.cr[buy]['phase']=='active' and not s.rescue_small(buy)
    def step(s,b):s.bb_minutes.append(list(b));return super().step(b)
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        if strat=='bb1' and buy and getattr(s,'_drop',False):return None
        if strat.startswith(('pat','ma')):
            frame=strat.lstrip('patm')
            if any(p['buy']==buy and p['strat']=='bb'+frame and abs(p['entry']-px)<100 for p in s.pos):return None
        return super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
    def set_exits(s,p,mode):
        if mode=='bb':
            off=100 if p['strat']=='bb15' else 50;x=p['entry']+(off if p['buy'] else -off)
            x=(math.ceil(x/TICK-1e-9) if p['buy'] else math.floor(x/TICK+1e-9))*TICK
            p['tps']=[(x,p['n'])];p['be']=False
        else:super().set_exits(p,mode)
    def pat_bar(s,f,t):
        super().pat_bar(f,t)
        if getattr(s,'warm',False) or f not in (1,15):return
        bars=s.pb[f][-LOOKBACK:]
        for i in range(len(bars)-1,0,-1):
            if bars[i][0]-bars[i-1][0]!=FR[f]:bars=bars[i:];break
        if len(bars)<60:return
        candidates=[buy for buy in (True,False) if bb_back(bars,buy)]
        if not candidates:return
        q=bars if f==15 else quarters(s.bb_minutes,t)
        if widening(q) is not False:return
        for buy in candidates:
            s.bb_slots.append(dict(f=f,buy=buy,price=bars[-1][4],frm=t,until=t+5*FR[f]))
            s.log(t,'BB SIGNAL %dm %s band outside -> inside'%(f,'L' if buy else 'S'))
    def limits(s,t,o,h,l,c):
        hide={}
        # Existing pat signals wait while a new BB trade of that frame is within $100.
        for f in s.sigs:
            for buy in (True,False):
                near=[p for p in s.pos if p['buy']==buy and p['strat']=='bb%d'%f]
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
        for sg in s.bb_slots:
            if sg.get('filled') or not sg['frm']<=t<sg['until']:continue
            buy=sg['buy'];f=sg['f']
            if s.capped(buy,o) or s.rescue_blocks(buy) or (f==1 and buy and getattr(s,'_drop',False)):continue
            px=math.floor(sg['price']/TICK)*TICK if buy else math.ceil(sg['price']/TICK)*TICK
            px=min(px,round(o-TICK,1)) if buy else max(px,round(o+TICK,1))
            if any(p['buy']==buy and p['strat'] in ('pat%d'%f,'ma%d'%f,'bb%d'%f) and abs(p['entry']-px)<100 for p in s.pos):continue
            if l<=px if buy else h>=px:
                p=s.open(t,'bb%d'%f,buy,px,info='BB20x2 return %dm'%f,limit=True,notional=max(0,s.free(px))*(.02 if f==1 else .03)*LEV,exitmode='bb')
                if p:sg['filled']=True
        s.bb_slots=[x for x in s.bb_slots if not x.get('filled') and x['until']>t]

class Engine23(Mix143,Engine21):
    def __init__(s,*a,**k):super().__init__(*a,**k);s.version='0.9.143+3pp'
