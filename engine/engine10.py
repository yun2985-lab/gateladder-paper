"""GateLadder 0.9.110 paper engine = engine9 (0.9.108+size == app 0.9.109: sizes +1pp, fixed 3x qty & rescue ROI,
real fees maker 0.018%/taker 0.042%, rebate 0.7, breakeven OFF, fib 0.722) + app 0.9.110:
- my Fibonacci follows the swing: closed bar (of its frame) wick past the end -> end moves there (levels re-placed, unfilled orders move);
  live price (1m bars here) moves it only when >= 1% of the swing past the end. Wick past the start -> used up (unfilled cancelled,
  filled positions keep +50 / rescue). Recommended/5-wave fibs are recomputed each bar as before.
- 5-wave 'sweep' (뚫고 반등) fallback after the strict impulse: each push past the previous extreme, pullbacks rising,
  >=3 ATR, a closed bar after wave 5 closes past the wave-5 candle (below its low for a rise), end not exceeded and start not broken."""
import engine7 as E7, engine5 as E5
from engine9 import Engine9
from engine7 import W, FR, PAT_FRAMES, mkfib, zigzag, impulse, radius
STEP=0.01
def sweep(w,r,buy):
    z=zigzag(w,r)
    if len(z)<6: return None
    e=len(z)-1
    if z[e][2]!=buy: e-=1
    if e<5: return None
    p=z[e-5:e+1]; sg=1 if buy else -1; v=[q[1]*sg for q in p]
    if not (v[1]>v[0] and v[2]>v[0] and v[2]<v[1] and v[3]>v[1] and v[4]>v[2] and v[4]<v[3] and v[5]>v[3]): return None
    i0,i5=p[0][0],p[5][0]
    if i0>=i5: return None
    sub=W([[w.t[k],w.o[k],w.h[k],w.l[k],w.c[k]] for k in range(max(0,i5-60),i5+1)])
    if v[5]-v[0]<3*max(1e-8,E5.atrw(sub)): return None
    bounced=False
    for x in range(i5+1,w.n):
        if (w.h[x]>p[5][1] or w.l[x]<p[0][1]) if buy else (w.l[x]<p[5][1] or w.h[x]>p[0][1]): return None
        if (w.c[x]<w.l[i5]) if buy else (w.c[x]>w.h[i5]): bounced=True
    return [q[0] for q in p] if bounced else None
def wave(w,f,buy,excl):
    if w.n<40: return None
    r=radius(f)
    for rr in (r,r+2,r*3):
        ix=impulse(w,rr,buy); loose=False
        if ix is None: ix=sweep(w,rr,buy); loose=ix is not None
        if ix is None: continue
        a,b=ix[0],ix[5]
        fb=mkfib(w.t[a],w.l[a] if buy else w.h[a],w.t[b],w.h[b] if buy else w.l[b])
        if fb['id'] in excl: continue
        fb['wave']=True; fb['sweep']=loose; return fb
    return None
E7.wave=wave
class Engine10(Engine9):
    def __init__(s,*a,**k):
        super().__init__(*a,**k); s.version='0.9.110'; s.ftrack={}
    def _st(s,f,x):
        k=(f,x['id']); st=s.ftrack.get(k)
        if st is None: st=s.ftrack[k]=dict(cur=dict(x),done=False)
        return st
    def _apply(s,f,st,hi,lo,tb,live,t):
        if st['done']: return
        c=st['cur']; buy=bool(c.get('buy')); a=float(c['a']['p']); b=float(c['b']['p'])
        if (lo<a) if buy else (hi>a):
            st['done']=True
            if not getattr(s,'warm',False): s.log(t,'FIB %dm %s 시작점 깨짐 · 사용 완료 (%s)'%(f,'L' if buy else 'S',c['id']))
            return
        ext=hi if buy else lo; over=(ext-b)*(1 if buy else -1); need=max(0.1,STEP*abs(b-a)) if live else 0.1
        if over<need-1e-9 or tb<=c['b']['t']: return
        n=mkfib(c['a']['t'],a,tb,ext); n['buy']=buy; n['at']=c.get('at',0); n['moved']=c.get('moved',0)+1
        st['cur']=n
        if not getattr(s,'warm',False): s.log(t,'FIB %dm %s %s 갱신 %.1f -> %.1f · 레벨 다시 계산'%(f,'L' if buy else 'S','고점' if buy else '저점',b,n['b']['p']))
    def fibs_mine(s,f,t,buy):
        out=[]
        for x in super().fibs_mine(f,t,buy):
            st=s._st(f,x)
            if not st['done']: out.append(st['cur'])
        return out
    def pat_bar(s,f,t):
        bar=s.pb[f][-1] if s.pb[f] else None
        if bar and bar[0]+FR[f]==t:
            for x in s.edits.get(f,{}).get('fib',[]):
                st=s._st(f,x)
                if bar[0]>st['cur']['b']['t']: s._apply(f,st,bar[2],bar[3],bar[0],False,t)
        super().pat_bar(f,t)
    def limits(s,t,o,h,l,c):
        if not getattr(s,'warm',False):
            for f in PAT_FRAMES:
                if f==1: continue
                for x in s.edits.get(f,{}).get('fib',[]):
                    if s.gate and x.get('at',0)>t: continue
                    st=s._st(f,x); blk=t//FR[f]*FR[f]
                    if blk>=st['cur']['b']['t']: s._apply(f,st,h,l,blk,True,t)
        super().limits(t,o,h,l,c)
