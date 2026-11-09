"""GateLadder 0.9.106 paper engine = engine6 (0.9.100)
+ 0.9.101 held auto entries: after 1h (1m/15m), 4h (1h), 24h (4h) since fill, if side avg is better than the entry's TP basis
  by >=5 USDT, shift remaining TPs by (avg-basis), only toward market; skipped if the side holds non-staged qty (rescue adds); cyc excluded.
+ 0.9.102-0.9.106 Fibonacci retracement: my fibs (by frame, from their drawn time) + auto 5-wave impulse fib (radius r,r+2,3r);
  levels 0.382/0.5/0.618/0.786, 1% of free seed x3 lev each, maker post-only 0.02%, +50 TP, level max 3 uses (busy until its TP),
  order rests only when price is on the favourable side; fib no longer active -> unfilled levels void.
  Learned fib recommendation needs >=5 positive samples per frame (backup has <=2 per frame -> inactive, still implemented check)."""
import math, engine6 as E6
from engine6 import Engine6, E5, W, FR, PAT_FRAMES, LOOKBACK, TICK, LEV, MAKER_FEE
# rebate 70% for the latest run (user 11/3); engine4 default 0.8 untouched for other runs
E5.E4.REBATE=0.7; E5.E4.F=E5.E4.FEE*(1-E5.E4.REBATE)
E6.RNAME['fib']='피보나치 되돌림'
ENTRY=(0.382,0.5,0.618,0.786); FIB_USES=3; HELD_MIN=5.0
def radius(f): return 3 if f==1 else 2
def pivot(w,x,high,r):
    if x-r<0 or x+r>=w.n: return False
    v=w.h[x] if high else w.l[x]
    for k in range(x-r,x+r+1):
        if k!=x and ((w.h[k]>v) if high else (w.l[k]<v)): return False
    return True
def zigzag(w,r):
    out=[]
    for x in range(r,w.n-r):
        h=pivot(w,x,True,r); l=pivot(w,x,False,r)
        for high in (True,False):
            if not (h if high else l): continue
            v=w.h[x] if high else w.l[x]
            if out and out[-1][2]==high:
                if (v>out[-1][1]) if high else (v<out[-1][1]): out[-1]=(x,v,high)
            else: out.append((x,v,high))
    return out
def impulse(w,r,buy):
    z=zigzag(w,r)
    if len(z)<6: return None
    e=len(z)-1
    if z[e][2]!=buy: e-=1
    if e<5: return None
    p=z[e-5:e+1]; sg=1 if buy else -1; v=[q[1]*sg for q in p]
    if not (v[1]>v[0] and v[2]>v[0] and v[3]>v[1] and v[4]>v[1] and v[5]>v[3] and v[2]<v[1] and v[4]<v[3]): return None
    w1,w3,w5=v[1]-v[0],v[3]-v[2],v[5]-v[4]
    if w3<min(w1,w5): return None
    i5=p[5][0]; sub=W([[w.t[k],w.o[k] if hasattr(w,'o') else w.c[k],w.h[k],w.l[k],w.c[k]] for k in range(max(0,i5-60),i5+1)])
    atr=max(1e-8,E5.atrw(sub))
    if v[5]-v[0]<3*atr: return None
    for x in range(i5+1,w.n):
        if (w.h[x]>p[5][1] or w.l[x]<p[0][1]) if buy else (w.l[x]<p[5][1] or w.h[x]>p[0][1]): return None
    return [q[0] for q in p] if p[0][0]<i5 else None
def mkfib(ta,pa,tb,pb):
    pa=round(pa,1); pb=round(pb,1)
    return dict(id='fib-%d-%d-%.1f-%.1f'%(ta,tb,pa,pb),a=dict(t=ta,p=pa),b=dict(t=tb,p=pb),buy=pb>pa)
def wave(w,f,buy,excl):
    if w.n<40: return None
    r=radius(f)
    for rr in (r,r+2,r*3):
        ix=impulse(w,rr,buy)
        if ix is None: continue
        a,b=ix[0],ix[5]
        fb=mkfib(w.t[a],w.l[a] if buy else w.h[a],w.t[b],w.h[b] if buy else w.l[b])
        if fb['id'] in excl: continue
        fb['wave']=True; return fb
    return None
def level(fb,r):
    pa,pb=float(fb['a']['p']),float(fb['b']['p']); h,l=max(pa,pb),min(pa,pb)
    return h-r*(h-l) if fb['buy'] else l+r*(h-l)
def tframe(strat):
    k=strat.split('@')[0]
    for f in (240,60,15,1):
        if k.endswith(str(f)): return f
    return 1
class Engine7(Engine6):
    def __init__(s,*a,**k):
        super().__init__(*a,**k); s.version='0.9.106'; s.no_be=True; s.fsig={f:{True:{},False:{}} for f in PAT_FRAMES}
    def fibs_mine(s,f,t,buy):
        e=s.edits.get(f,{}); ex=set(e.get('fibExcluded',[]))
        return [x for x in e.get('fib',[]) if bool(x.get('buy'))==buy and x['id'] not in ex and (not s.gate or x.get('at',0)<=t)]
    def pat_bar(s,f,t):
        super().pat_bar(f,t)
        if getattr(s,'warm',False): return
        bars=s.pb[f][-LOOKBACK:]
        for i in range(len(bars)-1,0,-1):
            if bars[i][0]-bars[i-1][0]!=FR[f]: bars=bars[i:]; break
        bars=[b for b in bars if b[0]+FR[f]<=t]
        if len(bars)<30: return
        w=W(bars); ex=set(s.edits.get(f,{}).get('fibExcluded',[]))
        for buy in (True,False):
            act=list(s.fibs_mine(f,t,buy))
            try: wv=wave(w,f,buy,ex)
            except Exception as er: s.log(t,'FIB ERR %r'%er); wv=None
            if wv and wv['id'] not in {x['id'] for x in act}: act.append(wv)
            # (learned suggestion needs >=5 samples on this frame)
            ids={x['id'] for x in act}; D=s.fsig[f][buy]
            for k,sg in D.items():
                if not sg.get('void') and not sg.get('filled') and sg['fib'] not in ids:
                    sg['void']=True; s.log(t,'FIB %dm %s %s 취소 (%s)'%(f,'L' if buy else 'S',k,'5파동 구조 바뀜' if sg['wave'] else '피보나치 지움'))
            for fb in act:
                for r in ENTRY:
                    k='fib:%s:%s'%(fb['id'],r)
                    if k in D: continue
                    D[k]=dict(fib=fb['id'],lv=r,price=round(level(fb,r),1),uses=0,busy=None,wave=bool(fb.get('wave')),frm=t)
                    s.log(t,'FIB %dm %s %s %s 지정가 대기 %.1f'%(f,'L' if buy else 'S','5파동' if fb.get('wave') else '내 피보나치',r,D[k]['price']))
    def limits(s,t,o,h,l,c):
        super().limits(t,o,h,l,c)
        if getattr(s,'warm',False): return
        live={p['id'] for p in s.pos}
        for f in PAT_FRAMES:
            for buy in (True,False):
                for k,sg in s.fsig[f][buy].items():
                    if sg.get('void') or sg.get('filled') or t<sg['frm']: continue
                    if sg['busy'] is not None:
                        if sg['busy'] in live: continue
                        sg['busy']=None
                    px=math.floor(sg['price']/TICK)*TICK if buy else math.ceil(sg['price']/TICK)*TICK
                    if not (o>px if buy else o<px): continue   # order rests only on the favourable side
                    if (l<=px if buy else h>=px):
                        N=max(0,s.free(px))*0.01*LEV; s._fr=MAKER_FEE
                        try: p=s.open(t,'fib%d'%f,buy,px,info='%s %dm %s %s @%.1f maker (%d/3)'%('L' if buy else 'S',f,'5파동 피보나치' if sg['wave'] else '내 피보나치',sg['lv'],px,sg['uses']+1),limit=True,notional=N,exitmode='pat')
                        finally: s._fr=None
                        if p:
                            sg['uses']+=1; sg['busy']=p['id']
                            if sg['uses']>=FIB_USES: sg['filled']=True
    def overlap(s,t,c):
        pre={p['id']:(p['tps'][0][0] if p['tps'] else None) for p in s.pos if p['id'] not in s.avg_done}
        super().overlap(t,c)
        for p in s.pos:
            if p['id'] in pre and p['id'] in s.avg_done and pre[p['id']] is not None and p['tps']: p['ash']=p['tps'][0][0]-pre[p['id']]
        if getattr(s,'warm',False): return
        for buy in (True,False):
            side=[p for p in s.pos if p['buy']==buy]
            if not side or any(p['strat']=='cyc' or p.get('rescue') or p.get('ov') for p in side): continue
            n=sum(p['n'] for p in side); avg=sum(p['entry']*p['n'] for p in side)/n
            for p in side:
                if p['tpi']>=len(p['tps']): continue
                f=tframe(p['strat']); wait=24*3600000 if f>=240 else 4*3600000 if f>=60 else 3600000
                if t-p['t']<wait: continue
                ref=p.get('href',p['entry']+p.get('ash',0.0)); sh=avg-ref
                if (sh*(-1 if buy else 1))<HELD_MIN: continue
                rnd=(lambda x:math.ceil(x/TICK-1e-9)*TICK) if buy else (lambda x:math.floor(x/TICK+1e-9)*TICK)
                p['tps']=p['tps'][:p['tpi']]+[(rnd(px+sh),q) for (px,q) in p['tps'][p['tpi']:]]; p['href']=avg
                s.log(t,'HELD(0.9.101) #%d %s %s TP shift %+.1f to avg %.1f'%(p['id'],p['strat'],'L' if buy else 'S',sh,avg))
