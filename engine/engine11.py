"""GateLadder 0.9.114 paper engine = engine10 (0.9.110 + all user settings: rebate 0.7, real fees, breakeven OFF, fib 0.722,
+1pp sizes fixed 3x) + app 0.9.111/0.9.114 automatic 5-wave:
- wave 1 starts at the most extreme low/high before wave 5 (window = last 240 bars of the frame), wave 5 = latest swing extreme
  of radius rr not exceeded since; swings between simplified (smallest pull-back pair removed first) to exactly 6 points.
- radii max(1,r-1), r, r+2, 3r; only Elliott-valid readings (wave 2 <100%, wave 3 not shortest, no wave 4 overlap, wave 5 past 3,
  alternating, >=3 ATR); among them the highest guideline score (no corrected-wave samples in the backup).
- 0.9.110 'sweep' (break-and-bounce) reading is no longer drawn.
0.9.112/0.9.113 are display only; 0.9.111 manual 5-wave drawing/learning has no samples in the line backup -> inactive."""
import engine7 as E7, engine5 as E5
from engine10 import Engine10
from engine7 import W, mkfib, zigzag, pivot, radius
def anchored(w,r,buy):
    n=w.n; i5=-1
    for x in range(n-1-r,r-1,-1):
        if pivot(w,x,buy,r): i5=x; break
    if i5<1: return None
    end=w.h[i5] if buy else w.l[i5]
    for x in range(i5+1,n):
        if (w.h[x]>end) if buy else (w.l[x]<end): return None
    i0=-1; start=0
    for x in range(i5):
        v=w.l[x] if buy else w.h[x]
        if i0<0 or ((v<start) if buy else (v>start)): start=v; i0=x
    for x in range(i5+1,n):
        if (w.l[x]<start) if buy else (w.h[x]>start): return None
    pts=[[i0,start,not buy]]
    for (x,v,high) in zigzag(w,r):
        if x<=i0 or x>=i5: continue
        last=pts[-1]
        if high==last[2]:
            if len(pts)>1 and ((v>last[1]) if high else (v<last[1])): pts[-1]=[x,v,high]
        else: pts.append([x,v,high])
    while len(pts)>1 and pts[-1][2]==buy: pts.pop()
    pts.append([i5,end,buy])
    while len(pts)>6:
        k=-1; d=1e18
        for j in range(1,len(pts)-2):
            dd=abs(pts[j+1][1]-pts[j][1])
            if dd<d: d=dd; k=j
        if k<0: break
        del pts[k:k+2]
    return [int(q[0]) for q in pts] if len(pts)==6 else None
def point(w,ix,k,buy): return w.l[ix[k]] if ((k%2==0)==buy) else w.h[ix[k]]
def elliott(p,buy):
    sg=1 if buy else -1; v=[x*sg for x in p]; ok=True
    if not (v[1]>v[0] and v[2]<v[1] and v[3]>v[2] and v[4]<v[3] and v[5]>v[4]): ok=False
    w1,w3,w5=v[1]-v[0],v[3]-v[2],v[5]-v[4]
    if v[2]<=v[0] or w3<min(w1,w5) or v[4]<=v[1] or v[5]<=v[3]: ok=False
    r2=(v[1]-v[2])/w1 if w1>0 else 0; x3=w3/w1 if w1>0 else 0; r4=(v[3]-v[4])/w3 if w3>0 else 0; x5=w5/w1 if w1>0 else 0
    sc=(25 if .382<=r2<=.786 else 0)+(25 if x3>=1.618 else 15 if x3>=1 else 0)+(25 if .236<=r4<=.5 else 0)+(25 if .618<=x5<=1.618 else 0)
    return ok,sc
def wave(w,f,buy,excl):
    if w.n<40: return None
    r=radius(f); best=None; bs=-1; seen=set()
    for rr in (max(1,r-1),r,r+2,r*3):
        ix=anchored(w,rr,buy)
        if ix is None or any(ix[k]>=ix[k+1] for k in range(5)): continue
        sub=W([[w.t[k],w.o[k],w.h[k],w.l[k],w.c[k]] for k in range(max(0,ix[5]-60),ix[5]+1)])
        p=[point(w,ix,k,buy) for k in range(6)]
        if (p[5]-p[0])*(1 if buy else -1)<3*max(1e-8,E5.atrw(sub)): continue
        ok,sc=elliott(p,buy)
        if not ok: continue
        fb=mkfib(w.t[ix[0]],p[0],w.t[ix[5]],p[5])
        if fb['id'] in excl or tuple(ix) in seen: continue
        seen.add(tuple(ix))
        if sc>bs: fb['wave']=True; fb['score']=sc; best=fb; bs=sc
    return best
E7.wave=wave
class Engine11(Engine10):
    def __init__(s,*a,**k):
        super().__init__(*a,**k); s.version='0.9.114'
