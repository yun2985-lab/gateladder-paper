"""GateLadder 0.9.95 paper engine (source GateLadder-0.9.95 zip + user's line-edits backup json, 2026-11-02).
Paper only, Binance USDT-M public 1m klines. Builds on engine4 (RSI 15m/1h, 1m RSI sideways, 1m triangle, staged exits).
0.9.95 changes vs engine4 run: 1m/15m S/R + 15m/1h breakout REMOVED (replaced by PatternRun '선 돌파' 1m/15m/1h/4h);
old rescue RETIRED -> CycleRescue (side ROI<=-3% x3, 3m 3-tick limit adds 2% avail, +38 each, max 20, end ROI>=0);
overlap 0.9.72 (lead TPs shifted by auto avg - lead entry); breakeven switch default ON (source)."""
import math, json, numpy as np
import engine4 as E4
from engine4 import Engine4, pivots as _piv, atr as _atr, rsi_arr, LEV, CT, TICK
FR={1:60000,3:180000,15:900000,60:3600000,240:14400000}
PAT_FRAMES=(1,15,60,240)
LOOKBACK=240; RETEST=15; DIVB=5; MAJOR=10; MIN_SPAN=15
def jnum(x):
    s=repr(float(x))
    if 'e' in s: s=format(float(x),'f')
    if '.' in s: s=s.rstrip('0').rstrip('.')
    return s
def lid(a,b,p,q): return '%d:%d:%s:%s'%(a,b,jnum(p),jnum(q))
def tat(ln,t): p=float(ln['p']); q=float(ln['q']); return q+(q-p)*(t-ln['b'])/(ln['b']-ln['a'])
def at(a,p,b,q,k): return p+(q-p)*(k-a)/(b-a)
def clear(o,h,l,c,i,high,m):
    w=(h[i]-max(o[i],c[i])) if high else (min(o[i],c[i])-l[i]); return w>=abs(c[i]-o[i]) and w>=m
class W:  # window arrays
    def __init__(s,bars):
        a=np.array(bars,dtype=float); s.t=a[:,0].astype(np.int64); s.o=a[:,1]; s.h=a[:,2]; s.l=a[:,3]; s.c=a[:,4]; s.n=len(bars)
    def piv(s,high,r,atr):
        v=s.h if high else s.l; return [k for k in _piv(v,r,high) if clear(s.o,s.h,s.l,s.c,k,high,atr*.25)]
    def v(s,high,k): return s.h[k] if high else s.l[k]
def atrw(w): return _atr(w.h,w.l,w.c) if w.n>14 else 0.0
# ---------- LineStyle
def strength(w,k,high):
    v=w.v(high,k); L=R=0; i=k-1
    while i>=0 and L<60:
        x=w.v(high,i)
        if (x>v if high else x<v): break
        L+=1; i-=1
    i=k+1
    while i<w.n and R<60:
        x=w.v(high,i)
        if (x>v if high else x<v): break
        R+=1; i+=1
    return min(L,R)
def ls_touches(w,a,end,p,q,b,high,tol):
    t=0
    for k in range(max(1,a),min(end,w.n-2)+1):
        v=at(a,p,b,q,k); x=w.v(high,k); pr=w.v(high,k-1); nx=w.v(high,k+1)
        loc=(x>=pr and x>=nx) if high else (x<=pr and x<=nx)
        if loc and abs(x-v)<=tol: t+=1
    return t
def dist(c,s):
    d=abs(math.log(max(1,c['span'])/max(1,s.get('span',1))))
    d+=.5*min(2,abs(c['slope']-s.get('slope',0))/(.02+abs(s.get('slope',0))))
    if s.get('strength',-1)>=0: d+=.5*abs(math.log((c['strength']+1.0)/(s['strength']+1.0)))
    return d
def nearest(c,S,neg):
    b=float('inf')
    for s in S:
        if bool(s.get('neg'))!=neg: continue
        b=min(b,dist(c,s))
    return b
def pct(v,q): v=sorted(v); return v[int(min(len(v)-1,math.floor(q*(len(v)-1)+.5)))]
def srange(S):
    P=[s for s in S if not s.get('neg')]; st=[s['strength'] for s in P if s.get('strength',-1)>=0]; sp=[s['span'] for s in P]
    r=MAJOR if not st else int(max(3,min(30,round(pct(st,.25)))))
    lo=MIN_SPAN if not sp else int(max(5,math.floor(pct(sp,0)*.6)))
    hi=240 if not sp else int(max(lo+5,math.ceil(pct(sp,1)*1.6)))
    return r,lo,hi
def side_of(s): return s['role'] if 'role' in s else ('res' if s.get('res') else 'sup')
def rdist(a,s):
    d=0
    if a.get('wick',-1)>=0 and s.get('wick',-1)>=0 and a['wick']!=s['wick']: d+=1
    if bool(a['above'])!=bool(s.get('above')): d+=1
    return d+.5*min(2,abs(a['raw']-s.get('raw',0))/(.02+abs(s.get('raw',0))))
def role3(f,S):
    pos=[s for s in S if not s.get('neg') and 'wick' in s]
    if len(pos)<5: return None
    pos.sort(key=lambda x:rdist(f,x)); k=pos[:5]; votes={}
    for x in k: votes[side_of(x)]=votes.get(side_of(x),0)+1
    best=side_of(pos[0]); top=votes[best]
    for kk,v in votes.items():
        if v>top: best=kk; top=v
    return best
# ---------- PatternRun analysis
def candidates(w,high,breakUp,atr,tol,upto,excl,radius=MAJOR,minSpan=MIN_SPAN,maxSpan=10**9):
    out=[]; piv=w.piv(high,radius,atr)
    for y in range(len(piv)-1,max(0,len(piv)-12)-1,-1):
        if y<=0: break
        b=piv[y]
        for x in range(y-1,-1,-1):
            a=piv[x]
            if b-a<minSpan: continue
            if b-a>maxSpan: break
            p=w.v(high,a); q=w.v(high,b); ok=True
            for k in range(a+1,b):
                v=at(a,p,b,q,k)
                if (w.h[k]>v+tol) if high else (w.l[k]<v-tol): ok=False;break
            if ok:
                for k in range(b+1,upto+1):
                    v=at(a,p,b,q,k)
                    if (w.c[k]>v+tol) if breakUp else (w.c[k]<v-tol): ok=False;break
            if ok and lid(w.t[a],w.t[b],p,q) not in excl: out.append((a,b))
    return out
def slope(w,l,high): return (w.v(high,l[1])-w.v(high,l[0]))/(l[1]-l[0])
def value(w,l,high,k): return at(l[0],w.v(high,l[0]),l[1],w.v(high,l[1]),k)
def triangle(w,res,sup,last):
    return res[0]<sup[1] and sup[0]<res[1] and value(w,res,True,last)>value(w,sup,False,last) and slope(w,res,True)<slope(w,sup,False)
def touches(w,piv,a,p,b,q,tol):
    return sum(1 for k in piv if k>=a and min(abs(w.h[k]-at(a,p,b,q,k)),abs(w.l[k]-at(a,p,b,q,k)))<=tol)
def auto_lines(w,buy,atr,tol,upto,excl):
    last=w.n-1; mine=candidates(w,buy,buy,atr,tol,upto,excl); opp=candidates(w,not buy,not buy,atr,tol,last,excl)
    piv=w.piv(buy,MAJOR,atr); sc=[]
    for c in mine:
        p=w.v(buy,c[0]); q=w.v(buy,c[1]); flat=abs(q-p)<=atr*.5
        tri=any((triangle(w,c,o,last) if buy else triangle(w,o,c,last)) for o in opp)
        if not flat and not tri and (q>p if buy else q<p): continue
        sc.append((( c[1]-c[0])+15*touches(w,piv,c[0],p,c[1],q,tol)+(60 if tri else 0)-(last-c[1])/4.0,c[0],c[1],flat,tri))
    sc.sort(key=lambda x:-x[0]); out=[]; ub=set()
    for d in sc:
        if len(out)>=2: break
        if d[2] in ub: continue
        ub.add(d[2]); out.append(dict(a=d[1],b=d[2],flat=d[3],tri=d[4],learned=False,hh=buy))
    return out
def learned_lines(w,buy,atr,tol,upto,excl,S,mine_ids):
    r,lo,hi=srange(S); last=w.n-1
    opp=candidates(w,not buy,not buy,atr,tol,last,excl,r,lo,hi); sc=[]
    for wick in (buy,not buy):
        for c in candidates(w,wick,buy,atr,tol,upto,excl,r,lo,hi):
            p=w.v(wick,c[0]); q=w.v(wick,c[1])
            if lid(w.t[c[0]],w.t[c[1]],p,q) in mine_ids: continue
            pb=(q-p)/(c[1]-c[0]); rf=dict(wick=1 if wick else 0,raw=pb/atr,above=w.c[last]>at(c[0],p,c[1],q,last))
            side=role3(rf,S); fits=(wick==buy) if side is None else (side=='both' or (side=='res')==buy)
            if not fits: continue
            st=min(strength(w,c[0],wick),strength(w,c[1],wick))
            f=dict(span=max(1,c[1]-c[0]),slope=(pb if buy else -pb)/atr,strength=st,touches=ls_touches(w,c[0],c[1],p,q,c[1],wick,atr*.3))
            d=nearest(f,S,False)
            if d>1.2 or nearest(f,S,True)<=d: continue
            tri=False
            if wick==buy: tri=any((triangle(w,c,o,last) if buy else triangle(w,o,c,last)) for o in opp)
            sc.append((d-(.3 if tri else 0)+(last-c[1])/2000.0,c[0],c[1],abs(q-p)<=atr*.5,tri,wick,d))
    sc.sort(key=lambda x:x[0]); out=[]; ub=set()
    for d in sc:
        if len(out)>=2: break
        if d[2] in ub: continue
        ub.add(d[2]); out.append(dict(a=d[1],b=d[2],flat=d[3],tri=d[4],learned=True,hh=d[5],like=int(max(0,min(100,round(100*(1-d[6]/1.8)))))))
    return out
def beyond(c,v,tol,buy): return c>v+tol if buy else c<v-tol
def spent(w,ln,buy,tol,upto):
    a=ln['a']; until=ln.get('until',10**15); run=0; inside=False
    for k in range(0,min(upto,w.n-1)+1):
        t=w.t[k]
        if t<=a or t>until: run=0; continue
        if beyond(w.c[k],tat(ln,t),tol,buy):
            if inside:
                run+=1
                if run>=2: return True
        else: run=0; inside=True
    return False
def analyze(w,f,block,buy,ed):
    """ed: dict(manual=[...], excluded=set, samples=[...]) already time-gated."""
    fm=FR[f]; n=w.n; r=3 if f==1 else 2; out=[]
    if n<60 or w.t[-1]+fm!=block: return out
    atr=atrw(w); tol=max(1e-8,atr*.25); excl=ed['excluded']; last=n-1
    highs=w.piv(True,r,atr); lows=w.piv(False,r,atr)
    S=ed['samples']; ready=sum(1 for s in S if not s.get('neg'))>=5
    mine_ids={m['id'] for m in ed['manual']}
    autos=learned_lines(w,buy,atr,tol,last-2,excl,S,mine_ids) if ready else (auto_lines(w,buy,atr,tol,last-2,excl) if f==1 else [])
    for L in autos:
        a,b=L['a'],L['b']
        if b>last-2: continue
        hh=L['hh']; p=w.v(hh,a); q=w.v(hh,b)
        v1=at(a,p,b,q,last-1); v2=at(a,p,b,q,last); c1=w.c[last-1]; c2=w.c[last]
        ok=(c1>v1+tol and c2>v2+tol and c2-v2>c1-v1) if buy else (c1<v1-tol and c2<v2-tol and v2-c2>v1-c1)
        if not ok: continue
        rule='learned' if L['learned'] else ('flat' if L['flat'] else 'trend')
        ln=dict(a=int(w.t[a]),b=int(w.t[b]),p=p,q=q)
        out.append(dict(rule=rule,key=rule+':'+lid(ln['a'],ln['b'],p,q),line=ln,tol=tol,frm=block,until=block+RETEST*fm,info='tri' if L['tri'] else ''))
    for m in ed['manual']:
        if not (m.get('both') or m['resistance']==buy) or m['id'] in excl: continue
        ln=dict(m['line']); ln['a']=int(ln['a']); ln['b']=int(ln['b']); ln['p']=float(ln['p']); ln['q']=float(ln['q'])
        if 'until' in ln: ln['until']=int(ln['until'])
        if n<3 or ln['a']>=w.t[last-2]: continue
        if 'until' in ln and w.t[last]>ln['until']: continue
        if spent(w,ln,buy,tol,last-1): continue
        v0,v1,v2=(tat(ln,w.t[k]) for k in (last-2,last-1,last)); c0,c1,c2=w.c[last-2],w.c[last-1],w.c[last]
        ok=(not beyond(c0,v0,tol,buy)) and ((c1>v1+tol and c2>v2+tol and c2-v2>c1-v1) if buy else (c1<v1-tol and c2<v2-tol and v2-c2>v1-c1))
        if not ok: continue
        out.append(dict(rule='manual',key='manual:%s:%d'%(m['id'],w.t[last-1]),line=ln,tol=tol,frm=block,
            until=min(block+RETEST*fm,ln['until']+fm if 'until' in ln else 10**15),info=m['id']))
    rs=rsi_arr(w.c,14); dp=lows if buy else highs
    if len(dp)>=2:
        b=dp[-1]
        if b+r==last:
            for x in range(len(dp)-2,-1,-1):
                a=dp[x]
                if b-a<5: continue
                if b-a>60: break
                ra,rb=rs[a],rs[b]
                if np.isnan(ra) or np.isnan(rb): continue
                div=(w.l[b]<=w.l[a] and ra<=30 and rb>30 and rb>ra) if buy else (w.h[b]>w.h[a] and ra>=70 and rb<70 and rb<ra)
                if not div: continue
                out.append(dict(rule='bull_div' if buy else 'bear_div',key='%s:%d:%d'%('bull' if buy else 'bear',w.t[a],w.t[b]),price=float(w.c[last]),frm=block,until=block+DIVB*fm,info='RSI14 %.1f->%.1f'%(ra,rb)))
                break
    if f==1:
        base=w.piv(buy,MAJOR,atr); other=w.piv(not buy,MAJOR,atr)
        if len(base)>=2:
            i3=base[-1]
            for x in range(len(base)-2,-1,-1):
                i1=base[x]
                if i3-i1<MIN_SPAN: continue
                p=w.v(buy,i1); q=w.v(buy,i3)
                if (not q<p) if buy else (not q>p): continue
                i2=-1; ext=0
                for k in other:
                    if i1<k<i3:
                        vv=w.l[k] if buy else w.h[k]; d=abs(vv-at(i1,p,i3,q,k))
                        if i2<0 or d>ext: i2=k; ext=d
                if i2<0: break
                off=(w.l[i2] if buy else w.h[i2])-at(i1,p,i3,q,i2)
                if (off>=0) if buy else (off<=0): break
                ok=True
                for k in range(i1,last+1):
                    e=at(i1,p,i3,q,k); op=e+off; top=max(e,op); bot=min(e,op)
                    if w.c[k]>top+tol or w.c[k]<bot-tol: ok=False;break
                if ok:
                    b1=dict(a=int(w.t[i1]),b=int(w.t[i3]),p=p,q=q); en=dict(a=b1['a'],b=b1['b'],p=p+off,q=q+off)
                    out.append(dict(rule='channel',key='channel:'+lid(b1['a'],b1['b'],p,q),line=en,base=b1,tol=tol,frm=block,until=10**15,info=''))
                break
    return out
# ---------- cycle rescue tick step (CycleRescue.step)
def cr_step(st,bars,k,buy):
    sg=1 if buy else -1; c=sg*bars[k][4]; o=sg*bars[k][1]
    if 'ref' not in st: st.update(ref=c,count=0,pending=True); return False
    sub=bars[max(0,k-40):k+1]; tr=[max(sub[i][2],sub[i-1][4])-min(sub[i][3],sub[i-1][4]) for i in range(max(1,len(sub)-14),len(sub))]
    thr=max(1e-8,(sum(tr)/len(tr) if tr else 0)*0.3); ref=st['ref']
    if c>ref+thr: st.update(ref=c,count=0,pending=True); return False
    if c<=ref-thr and c<o:
        js=range(max(0,k-10),k); avg=sum(abs(bars[j][4]-bars[j][1]) for j in js)/len(js) if len(js) else 0
        if st.get('pending') and o-c<2.0*avg: st.update(pending=False,ref=c); return False
        cnt=st.get('count',0)+1; st.update(pending=False,ref=c)
        if cnt>=3: st['count']=0; return True
        st['count']=cnt
    return False
RNAME={'trend':'추세선 돌파 리테스트','flat':'수평선 돌파 리테스트','bear_div':'하락 다이버전스','bull_div':'상승 다이버전스','channel':'평행채널 4번째 포인트','manual':'내 선 돌파 리테스트','learned':'추천선 돌파 리테스트'}
class Engine5(Engine4):
    def __init__(s,cash=1000.0,edits=None,gate_edits_by_time=True):
        super().__init__(cash); s.no_be=False; s.pb={f:[] for f in FR}; s.pagg={}
        s.edits=edits or {}; s.gate=gate_edits_by_time; s.sigs={f:{True:[],False:[]} for f in PAT_FRAMES}; s.known=set()
        s.cr={b:dict(phase='watch',adds=0,slot=None,last=None,ticks=None,lastAdd=None) for b in (True,False)}; s.crlog=[]
        s.avg_done=set(); s.version='0.9.95'
    def ed(s,f,t):
        e=s.edits.get(f,{}); g=(lambda x:x.get('at',0)<=t) if s.gate else (lambda x:True)
        return dict(manual=[m for m in e.get('manual',[]) if g(m)],excluded=set(e.get('excluded',[])),samples=[x for x in e.get('style',{}).get('samples',[]) if g(x)])
    # disable engine4 SR/breakout/old rescue
    def mk_line(s,*a,**k): pass
    def breakouts(s,*a): pass
    def set_exits(s,p,mode):
        d=1 if p['buy'] else -1
        if mode in ('pat','cyc'):
            off=50 if mode=='pat' else 38; x=p['entry']+d*off
            x=math.ceil(x/TICK-1e-9)*TICK if p['buy'] else math.floor(x/TICK+1e-9)*TICK
            p['tps']=[(x,p['n'])]; p['be']=False
        else: super().set_exits(p,mode)
    def step(s,b):
        super().step(b)
        for f in FR:
            fm=FR[f]; st=b[0]//fm*fm; a=s.pagg.get(f)
            if a is None or a[0]!=st: a=[st,b[1],b[2],b[3],b[4]]
            else: a[2]=max(a[2],b[2]); a[3]=min(a[3],b[3]); a[4]=b[4]
            s.pagg[f]=a
            if b[0]+60000==st+fm:
                w=s.pb[f]
                if not w or w[-1][0]<st: w.append(list(a)); del w[:-300]
                t=st+fm
                if f==3: s.cr_bar(t)
                if f in PAT_FRAMES: s.pat_bar(f,t)
    def pat_bar(s,f,t):
        bars=s.pb[f][-LOOKBACK:]
        for i in range(len(bars)-1,0,-1):
            if bars[i][0]-bars[i-1][0]!=FR[f]: bars=bars[i:]; break
        if len(bars)<60: return
        w=W(bars)
        for buy in (True,False):
            L=s.sigs[f][buy]
            # channel void check / expiry
            for sg in L:
                if sg['rule']=='channel' and not sg.get('void') and not sg.get('filled'):
                    cl=w.c[-1]; e1=tat(sg['base'],w.t[-1]); e2=tat(sg['line'],w.t[-1])
                    if cl>max(e1,e2)+sg['tol'] or cl<min(e1,e2)-sg['tol']: sg['void']=True
            if getattr(s,'warm',False): continue
            try: new=analyze(w,f,t,buy,s.ed(f,t))
            except Exception as ex: s.log(t,'PAT ERR %r'%ex); new=[]
            for sg in new:
                k=(f,buy,sg['key'])
                if k in s.known: continue
                s.known.add(k); L.append(sg)
                s.log(t,'PAT SIGNAL %dm %s %s %s'%(f,'L' if buy else 'S',RNAME[sg['rule']],sg.get('info','')))
            s.sigs[f][buy]=[x for x in L if not x.get('void') and not x.get('filled') and x['until']>t]
    def limits(s,t,o,h,l,c):
        super().limits(t,o,h,l,c)
        if getattr(s,'warm',False): return
        for f in PAT_FRAMES:
            blk=t//FR[f]*FR[f]
            for buy in (True,False):
                for sg in s.sigs[f][buy]:
                    if sg.get('void') or sg.get('filled') or t<sg['frm'] or t>=sg['until']: continue
                    if 'line' in sg:
                        v=tat(sg['line'],blk); px=math.floor(v/TICK)*TICK if buy else math.ceil(v/TICK)*TICK
                        if not (o>px if buy else o<px):
                            if sg['rule']!='channel': sg['void']=True
                            continue
                    else:
                        px=math.floor(sg['price']/TICK)*TICK if buy else math.ceil(sg['price']/TICK)*TICK
                    if (l<=px if buy else h>=px):
                        N=max(0,s.free(px))*0.04*LEV
                        p=s.open(t,'pat%d'%f,buy,px,info='%s %dm %s @%.1f %s'%('L' if buy else 'S',f,RNAME[sg['rule']],px,sg.get('info','')),limit=True,notional=N,exitmode='pat')
                        sg['filled']=True
        s.cr_fill(t,o,h,l,c)
    # 0.9.72 overlap: shift lead's remaining TPs by (auto avg - lead entry), once, 30m after 2nd entry
    def overlap(s,t,c):
        for buy in (True,False):
            ps=sorted([p for p in s.pos if p['buy']==buy and p['strat']!='cyc'],key=lambda p:(p['t'],p['id']))
            if len(ps)<2: continue
            lead=ps[0]
            if lead['id'] in s.avg_done or t<ps[1]['t']+30*60000: continue
            q=sum(p['n'] for p in ps); avg=sum(p['entry']*p['n'] for p in ps)/q; sh=avg-lead['entry']
            rnd=(lambda x:math.ceil(x/TICK-1e-9)*TICK) if buy else (lambda x:math.floor(x/TICK+1e-9)*TICK)
            lead['tps']=[(rnd(px+sh),n) for (px,n) in lead['tps']]; s.avg_done.add(lead['id'])
            s.log(t,'OVERLAP(0.9.72) #%d %s shift TPs %+.1f to auto avg %.1f'%(lead['id'],'L' if buy else 'S',sh,avg))
    # ---------- CycleRescue
    def side_roi(s,buy,px):
        ps=[p for p in s.pos if p['buy']==buy]
        if not ps: return None
        n=sum(p['n'] for p in ps); avg=sum(p['entry']*p['n'] for p in ps)/n
        return (px/avg-1)*100*LEV*(1 if buy else -1)
    def rescue_tick(s,t,o,h,l,c):
        s.tri_tick(t,o,h,l,c)
        if getattr(s,'warm',False): return
        for buy in (True,False):
            r=s.cr[buy]; roi=s.side_roi(buy,c); sd='L' if buy else 'S'
            if r['phase']!='active':
                if roi is not None and roi<=-3:
                    r.update(phase='active',started=t,adds=0,ticks=None,lastAdd=None,slot=None)
                    s.crlog.append(dict(t=t,side=sd,start_roi=round(roi,2),adds=0)); s.rescues.append(dict(t=t,side=sd,roi=round(roi,2),adds=0))
                    s.log(t,'CYCLE RESCUE START %s ROI %.2f%%'%(sd,roi))
            elif roi is None or roi>=0:
                r['phase']='watch'; r['slot']=None; s.rescues[-1]['done']=t
                s.log(t,'CYCLE RESCUE END %s %s adds %d'%(sd,'flat' if roi is None else 'ROI %.2f%%'%roi,r['adds']))
    def cr_bar(s,t):
        if getattr(s,'warm',False): return
        bars=s.pb[3]
        for buy in (True,False):
            r=s.cr[buy]
            if r['slot'] and t-r['slot']['blk']>=2*180000: r['slot']=None   # cancel after 2 bars
            if r['phase']!='active' or len(bars)<40: continue
            k=len(bars)-1
            if r['ticks'] is None: r['ticks']={}; cr_step(r['ticks'],bars,k,buy); continue
            hit=cr_step(r['ticks'],bars,k,buy)
            if not hit or r['slot'] or r['adds']>=20: continue
            px=bars[k][4]; px=math.floor(px/TICK)*TICK if buy else math.ceil(px/TICK)*TICK
            if r['lastAdd'] is not None and (px>=r['lastAdd'] if buy else px<=r['lastAdd']):
                s.log(t,'CYCLE add skipped %.1f not beyond last add %.1f'%(px,r['lastAdd'])); continue
            r['slot']=dict(px=px,blk=t); s.log(t,'CYCLE add limit %s %.1f (3m 3-tick)'%('L' if buy else 'S',px))
    def cr_fill(s,t,o,h,l,c):
        for buy in (True,False):
            r=s.cr[buy]; sl=r['slot']
            if not sl or t<sl['blk']: continue
            if (l<=sl['px'] if buy else h>=sl['px']):
                N=max(0,s.free(sl['px']))*0.02*LEV
                p=s.open(t,'cyc',buy,sl['px'],info='cycle rescue add %d/20 @%.1f'%(r['adds']+1,sl['px']),limit=True,notional=N,exitmode='cyc')
                r['slot']=None
                if p: r['adds']+=1; r['lastAdd']=sl['px']; s.rescues[-1]['adds']=r['adds']
def load_edits(path):
    d=json.load(open(path))['data']; out={}
    for k,v in d.items(): out[int(k.split('/')[1])//60000]=v
    return out
