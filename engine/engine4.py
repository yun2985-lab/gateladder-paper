"""GateLadder 0.9.65 paper engine (spec 'GateLadder 0.9.65 매매 조건 명세', 2026-11-02).
Paper only. All prices = Binance USDT-M BTCUSDT public 1m klines (Gate prices not used). No funding.
User overrides: 1h breakout OFF (code kept), 15m breakout OFF; rescue trigger = ROI -2% at 3x (price ~-0.667%)."""
import math, numpy as np
FEE=0.0005; REBATE=0.8; F=FEE*(1-REBATE); LEV=3.0; MMR=0.005; SLIP=0.0001; CT=0.0001; TICK=0.1
RESCUE_ROI=-2.0; RESCUE_BUD=0.7; RESCUE_N=10
ENABLED={'brk60':False,'brk15':False,'rsi15':True,'rsi60':True,'rsi1':True,'tri1':True,'sr1':True,'sr15':True,'rescue':True}
FIXED={'brk60':(80,150,200),'sr15':(80,150,200),'brk15':(80,150,200)}
STRATS=['rsi15','rsi60','rsi1','tri1','sr1','sr15','brk60','rescue']
def atr(H,L,C,n=14):
    i=np.arange(len(C)-n,len(C)); return float(np.mean(np.maximum(H[i],C[i-1])-np.minimum(L[i],C[i-1])))
def pivots(v,r,high):
    out=[]; n=len(v)
    for i in range(r,n-r):
        x=v[i]; ok=True
        for j in range(i-r,i+r+1):
            if j==i: continue
            y=v[j]
            if high:
                if y>x or (j>i and y==x): ok=False;break   # right equal wins
            else:
                if y<x or (j>i and y==x): ok=False;break
        if ok: out.append(i)
    return out
def wick_ok(o,h,l,c,i,high,a):
    body=abs(c[i]-o[i]); wk=(h[i]-max(o[i],c[i])) if high else (min(o[i],c[i])-l[i])
    return wk>=body and wk>=a*0.25
def find_line(o,h,l,c,R,tol,a,res,allow_below=False,nb=3):
    """returns (ia,ib,pa,slope) nearest valid line of type res, or None"""
    n=len(c); v=h if res else l
    pv=[i for i in pivots(v,R,res) if wick_ok(o,h,l,c,i,res,a)]
    for bi in range(len(pv)-1,max(-1,len(pv)-1-nb),-1):
        b=pv[bi]
        for ai in range(bi-1,max(-1,bi-25),-1):
            A=pv[ai]
            if b-A<R+1: continue
            sl=(v[b]-v[A])/(b-A); idx=np.arange(A,b+1); line=v[A]+sl*(idx-A)
            if res and np.any(h[A:b+1]>line+tol): continue
            if not res and np.any(l[A:b+1]<line-tol): continue
            if b+1<n:
                idx2=np.arange(b+1,n); l2=v[A]+sl*(idx2-A)
                if res and np.any(c[b+1:]>l2+tol): continue
                if not res and np.any(c[b+1:]<l2-tol) and not (allow_below and sl<0): continue
            return (A,b,float(v[A]),float(sl))
    return None
def rsi_arr(c,n):
    d=np.diff(c); g=np.where(d>0,d,0.0); ls=np.where(d<0,-d,0.0); out=np.full(len(c),np.nan)
    if len(d)<n: return out
    ag=g[:n].mean(); al=ls[:n].mean(); out[n]=100-100/(1+ag/al) if al>0 else 100
    for i in range(n,len(d)):
        ag=(ag*(n-1)+g[i])/n; al=(al*(n-1)+ls[i])/n; out[i+1]=100-100/(1+ag/al) if al>0 else 100
    return out
def is_piv(v,i,r,high):
    if i-r<0 or i+r>=len(v): return False
    for j in range(i-r,i+r+1):
        if j==i: continue
        if high and (v[j]>v[i] or (j>i and v[j]==v[i])): return False
        if not high and (v[j]<v[i] or (j>i and v[j]==v[i])): return False
    return True
def rsi_div(h,l,c,P,PIV,lo,hi,buy):
    n=len(c); r=rsi_arr(c,P); i2=n-1-PIV; v=l if buy else h
    if not is_piv(v,i2,PIV,not buy): return None
    for i1 in range(i2-5,max(-1,i2-61),-1):
        if is_piv(v,i1,PIV,not buy):
            if np.isnan(r[i1]) or np.isnan(r[i2]): return None
            if buy and v[i2]<v[i1] and r[i2]>r[i1] and r[i1]<=lo and r[i2]<=lo: return (i1,i2,r[i1],r[i2])
            if not buy and v[i2]>v[i1] and r[i2]<r[i1] and r[i1]>=hi and r[i2]>=hi: return (i1,i2,r[i1],r[i2])
            return None
    return None
def adx(h,l,c,n=14):
    up=h[1:]-h[:-1]; dn=l[:-1]-l[1:]; pdm=np.where((up>dn)&(up>0),up,0); mdm=np.where((dn>up)&(dn>0),dn,0)
    tr=np.maximum(h[1:],c[:-1])-np.minimum(l[1:],c[:-1])
    def w(x):
        o=[x[:n].sum()]
        for v in x[n:]: o.append(o[-1]-o[-1]/n+v)
        return np.array(o)
    t=w(tr); pd=100*w(pdm)/t; md=100*w(mdm)/t; dx=100*np.abs(pd-md)/np.maximum(pd+md,1e-9)
    a=dx[:n].mean()
    for v in dx[n:]: a=(a*(n-1)+v)/n
    return a
class Engine4:
    def __init__(s,cash=1000.0):
        s.start=cash; s.cash=cash; s.rebate=0.0; s.fees=0.0; s.pos=[]; s.trades=[]; s.eq=[]; s.rescues=[]; s.rescue={True:None,False:None}
        s.liq=False; s.bars={1:[],5:[],15:[],60:[]}; s.agg={}; s.nid=0; s.peak=cash; s.mdd=0; s.max_mu=0; s.events=[]; s.alerts=[]
        s.lines={}; s.uses={}; s.used=set(); s.sr1=None; s.sr15=None; s.overlap_done=set(); s.snap={}; s.daily={}
    def log(s,t,m): s.events.append((t,m))
    def equity(s,px): return s.cash+sum((px-p['entry'])*p['qty']*(1 if p['buy'] else -1) for p in s.pos)
    def margin(s): return sum(p['entry']*p['qty']/LEV for p in s.pos)
    def free(s,px): return s.equity(px)-s.margin()
    def fee(s,notional):
        f=notional*FEE; s.cash-=f; s.fees+=f; s.rebate+=f*REBATE; return f
    # ---------- orders
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        if s.liq or getattr(s,'warm',False): return None
        if strat!='rescue' and s.rescue[buy]: return None
        fp=px if limit else px*(1+SLIP if buy else 1-SLIP)
        N=notional if notional is not None else s.start*pct*LEV           # fixed seed (non-compounding)
        n=math.floor(N/(fp*CT)+1e-9)
        if n<1: s.log(t,'SKIP %s <1 contract'%strat); return None
        q=n*CT
        if fp*q/LEV>s.free(fp): s.log(t,'SKIP %s insufficient margin'%strat); return None
        f=s.fee(fp*q); s.nid+=1; d=1 if buy else -1
        p=dict(id=s.nid,t=t,strat=strat,buy=buy,entry=fp,n=n,qty=q,n0=n,info=info,fee=f,tps=[],tpi=0,be_at=None,rescue=strat=='rescue',add=strat=='rescue',ov=False)
        if exitmode: s.set_exits(p,exitmode)
        s.pos.append(p); s.log(t,'OPEN %s %s %.1f %dct | %s'%(strat,'L' if buy else 'S',fp,n,info)); return p
    def split(s,n):
        c1=math.floor(n*0.4); c2=math.floor((n-c1)/2); c3=n-c1-c2
        return [n] if min(c1,c2,c3)<1 else [c1,c2,c3]
    def set_exits(s,p,mode):
        d=1 if p['buy'] else -1; e=p['entry']; parts=s.split(p['n'])
        rnd=(lambda x:math.ceil(x/TICK-1e-9)*TICK) if p['buy'] else (lambda x:math.floor(x/TICK+1e-9)*TICK)
        if mode in ('cost5','cost5full'):
            q=p['n']*CT; q1=(parts[0] if len(parts)==3 else math.floor(p['n']*0.4) or p['n'])*CT
            cost=p['fee']*(1-REBATE)+e*q*F; move=cost/(q1*(1-F*d))*5; tp1=rnd(e+d*move)
            if mode=='cost5full' or len(parts)==1: p['tps']=[(tp1,p['n'])]
            else: p['tps']=[(tp1,parts[0]),(tp1+d*30,parts[1]),(tp1+d*60,parts[2])]
            p['be']=(mode=='cost5')
        elif mode=='sr1': p['tps']=[(rnd(e+d*55),p['n'])]; p['be']=False
        else:
            a,b,c=FIXED[mode]; lv=[rnd(e+d*a),rnd(e+d*b),rnd(e+d*c)]
            p['tps']=[(lv[0],p['n'])] if len(parts)==1 else list(zip(lv,parts)); p['be']=True
    def close(s,t,p,n,price,why,limit=False):
        n=min(n,p['n']);
        if n<=0: return
        px=price if limit else price*(1-SLIP if p['buy'] else 1+SLIP); q=n*CT
        pnl=(px-p['entry'])*q*(1 if p['buy'] else -1); ef=p['fee']*n/p['n0']; f=s.fee(px*q); s.cash+=pnl; p['n']-=n; p['qty']=p['n']*CT
        net=pnl-f-ef
        s.trades.append(dict(t_in=p['t'],t=t,id=p['id'],strat=p['strat'] if not p['rescue'] or p['add'] else p['strat']+'@rescue',side='L' if p['buy'] else 'S',entry=round(p['entry'],2),exit=round(px,2),qty=round(q,4),
            pnl=round(net,4),pnl_rebate=round(net+(f+ef)*REBATE,4),pnl_pct_margin=round(net/(p['entry']*q/LEV)*100,3),pnl_pct_equity=round(net/s.start*100,4),
            result='WIN' if net>0 else 'LOSS',why=why,info=p['info']))
        if p['n']<=0: s.pos.remove(p)
    # ---------- driver
    def step(s,b):
        s.on_1m(b)
        for f in (5,15,60):
            st=b[0]//(f*60000)*(f*60000); a=s.agg.get(f)
            if a is None or a[0]!=st: a=[st,b[1],b[2],b[3],b[4]]
            else: a[2]=max(a[2],b[2]); a[3]=min(a[3],b[3]); a[4]=b[4]
            s.agg[f]=a
        s.close_bar(1,b)
        for f in (5,15,60):
            a=s.agg[f]
            if b[0]+60000==a[0]+f*60000: s.close_bar(f,list(a))
    def close_bar(s,f,b):
        w=s.bars[f]; w.append(b); del w[:-300]
        t=b[0]+f*60000
        if f==1:
            s.sig_rsi(t,1,9,5,30,70); s.sig_triangle(t); s.mk_line('sr1',1,240,3,0.25)
        elif f==5: s.rescue_signal(b)
        elif f==15:
            s.sig_rsi(t,15,7,2,25,75); s.mk_line('sr15',15,96,2,0.25)
        elif f==60:
            s.sig_rsi(t,60,9,5,40,60); s.mk_line('brk60',60,120,5,0.5,allow_below=True)
    def arr(s,f,N):
        w=s.bars[f][-N:]
        if len(w)<N: return None
        for i in range(1,len(w)):
            if w[i][0]-w[i-1][0]!=f*60000: return None      # missing bar -> skip analysis
        a=np.array(w,dtype=float); return a[:,1],a[:,2],a[:,3],a[:,4],a[:,0]
    def mk_line(s,strat,f,N,R,K,allow_below=False):
        A=s.arr(f,N)
        if A is None: return
        o,h,l,c,ts=A; a=atr(h,l,c); tol=a*K; out=[]
        for res in (True,False):
            ln=find_line(o,h,l,c,R,tol,a,res,allow_below and not res)
            if ln:
                ia,ib,pa,sl=ln; key=(strat,res,int(ts[ia]),int(ts[ib]))
                old=s.lines.get((strat,res)); armed=old['armed'] if old and old['key']==key else False
                out.append(dict(strat=strat,res=res,key=key,t0=ts[ia],pa=pa,sl=sl,f=f,tol=tol,armed=armed,below=allow_below and not res and sl<0))
            s.lines[(strat,res)]=out[-1] if ln else None
        s.snap['lines_'+strat]=[dict(type='R' if x['res'] else 'S',level=round(s.lv(x,t:=ts[-1]+f*60000),1),tol=round(x['tol'],1)) for x in out]
    def lv(s,L,t): return L['pa']+L['sl']*(t-L['t0'])/(L['f']*60000)
    # ---------- per-1m price processing (exits, breakouts, rescue, liq)
    def on_1m(s,b):
        t,o,h,l,c=b[:5]
        if s.liq: s.mark(t,c); return
        if s.pos:
            for side in (True,False):
                worst=s.equity(l if side else h)
                if worst<=sum(p['entry']*p['qty']*MMR for p in s.pos):
                    for p in list(s.pos): s.close(t,p,p['n'],l if side else h,'LIQUIDATION (total loss)')
                    s.cash=min(s.cash,0); s.liq=True; s.log(t,'LIQUIDATED'); s.mark(t,c); return
        s.exits(t,o,h,l,c)
        s.limits(t,o,h,l,c)
        s.breakouts(t,o,h,l,c)
        s.overlap(t,c)
        s.rescue_tick(t,o,h,l,c)
        s.mark(t,c,h,l)
    def exits(s,t,o,h,l,c):
        for p in list(s.pos):
            if p['rescue'] or p['ov']: continue
            d=p['buy']
            # breakeven first (adverse-first in same bar)
            if not getattr(s,'no_be',False) and p['be_at'] is not None and t>=p['be_at'] and (l<=p['entry'] if d else h>=p['entry']):
                s.close(t,p,p['n'],p['entry'],'breakeven'); continue
            while p in s.pos and p['tpi']<len(p['tps']):
                px,n=p['tps'][p['tpi']]
                if not (h>=px if d else l<=px): break
                p['tpi']+=1; s.close(t,p,n,px,'tp%d'%p['tpi'],limit=True)
                if p['tpi']==1 and p.get('be') and not getattr(s,'no_be',False) and p in s.pos: p['be_at']=t+15*60000
    def limits(s,t,o,h,l,c):
        cy=s.sr1
        if cy and cy.get('retest'):
            r=cy['retest']
            if t>r['exp']: cy['retest']=None; s.log(t,'SR1 retest limit expired')
            elif (l<=r['px'] if r['buy'] else h>=r['px']):
                cy['retest']=None; p=s.open(t,'sr1',r['buy'],r['px'],0.01,'1m S/R retest limit 1%% @%.1f'%r['px'],limit=True,exitmode='sr1')
                if p: cy['ids'].append(p['id'])
        for p in list(s.pos):
            if not p['ov']: continue
            for od in list(p['ovo']):
                px,n=od
                if (h>=px if p['buy'] else l<=px) and p in s.pos: p['ovo'].remove(od); s.close(t,p,n,px,'overlap_clean',limit=True)
        if s.sr1 and not s.sr1.get('retest') and not any(p['id'] in s.sr1['ids'] for p in s.pos): s.sr1=None
        if s.sr15 and not any(p['id'] in s.sr15['ids'] for p in s.pos): s.sr15=None
    def breakouts(s,t,o,h,l,c):
        for k,L in list(s.lines.items()):
            if not L or not ENABLED[L['strat']]: continue
            st=L['strat']; lvl=s.lv(L,t); tol=L['tol']; res=L['res']
            buy=res or L['below']        # descending support re-break -> long (brk60 only)
            inside=(o<=lvl) if buy else (o>=lvl)
            if inside: L['armed']=True
            if not L['armed']: 
                L['armed']=(l<=lvl) if buy else (h>=lvl); continue
            trig=lvl+tol if buy else lvl-tol
            if not (h>trig if buy else l<trig): continue
            # breakout detected in this bar
            L['armed']=False; ku=L['key']
            if s.uses.get(ku,0)>=3: continue
            fill=max(o,trig) if buy else min(o,trig)
            desc='%s %s line %.1f (tol %.1f) %s at %.1f'%(st,'R' if res else ('S-desc' if L['below'] else 'S'),lvl,tol,'up-break' if buy else 'down-break',fill)
            p=None
            if st=='brk60': p=s.open(t,st,buy,fill,0.06,desc+' use %d/3'%(s.uses.get(ku,0)+1),exitmode='brk60')
            elif st=='sr1':
                if s.sr1 or s.rescue[buy]: continue
                p=s.open(t,st,buy,fill,0.01,desc+' market 1%',exitmode='sr1')
                if p:
                    rp=math.floor(lvl/TICK)*TICK if buy else math.ceil(lvl/TICK)*TICK
                    s.sr1=dict(ids=[p['id']],retest=dict(buy=buy,px=rp,exp=t+15*60000))
            elif st=='sr15':
                if s.sr15 or s.rescue[buy]: continue
                p=s.open(t,st,buy,fill,0.01,desc+' market 1%',exitmode='sr15')
                if p: s.sr15=dict(ids=[p['id']],added=False,buy=buy)
            if p: s.uses[ku]=s.uses.get(ku,0)+1
    def open_auto(s,buy=None,strats=None):
        return [p for p in s.pos if not p['rescue'] and (buy is None or p['buy']==buy) and (strats is None or p['strat'] in strats)]
    # ---------- signals
    def sig_rsi(s,t,f,P,PIV,lo,hi):
        st='rsi%d'%f
        if not ENABLED[st]: return
        A=s.arr(f,200)
        if A is None: return
        o,h,l,c,ts=A
        for buy in (True,False):
            sg=rsi_div(h,l,c,P,PIV,lo,hi,buy)
            if not sg: continue
            key=(st,buy,int(ts[sg[1]]))
            if key in s.used: continue
            s.used.add(key)
            grp=('rsi15','rsi60') if f!=1 else ('rsi1',)
            if len(s.open_auto(None,grp))>=10: s.log(t,'SKIP %s max 10 open'%st); continue
            info='RSI%d %dm %s div p1 RSI %.1f p2 RSI %.1f (%d/%d, pivot %d)'%(P,f,'bull' if buy else 'bear',sg[2],sg[3],lo,hi,PIV)
            if f==1:
                ok,why=s.sideways()
                if not ok: s.log(t,'SKIP rsi1 15m filter '+why); continue
                info+=' | '+why
            s.open(t,st,buy,c[-1],0.05,info,exitmode='cost5' if f!=1 else 'cost5full')
    def sideways(s):
        A=s.arr(15,60)
        if A is None: return False,'no 15m'
        o,h,l,c,ts=A; ad=adx(h,l,c); m=c[-20:].mean(); sd=c[-20:].std(); up=m+2*sd; dn=m-2*sd; wd=(up-dn)/m*100
        ok=ad<20 and wd<=1 and dn<=c[-1]<=up
        return ok,'15m ADX %.1f BBw %.2f%%'%(ad,wd)
    def sig_triangle(s,t):
        if not ENABLED['tri1']: return
        A=s.arr(1,120)
        if A is None: return
        o,h,l,c,ts=A; a=atr(h,l,c); tol=a*0.25; n=len(c)
        R=find_line(o,h,l,c,3,tol,a,True); S=find_line(o,h,l,c,3,tol,a,False)
        s.snap['triangle']=None
        if not R or not S: return
        st=max(R[0],S[0]); 
        if n-1-st<6: return
        rl=lambda i:R[2]+R[3]*(i-R[0]); sl=lambda i:S[2]+S[3]*(i-S[0])
        dR=rl(n-1)-rl(st); dS=sl(n-1)-sl(st)
        kind='asc' if abs(dR)<=tol and dS>tol else 'desc' if dR<-tol and abs(dS)<=tol else 'sym' if dR<-tol and dS>tol else None
        if not kind: return
        w0=rl(st)-sl(st); w1=rl(n-1)-sl(n-1)
        if not (w1>=2*tol and w1<=w0*0.9 and w0-w1>=tol and sl(n-1)<c[-1]<rl(n-1)): return
        touches=[]
        for side,fn in ((1,rl),(0,sl)):
            last=-99
            for i in range(st,n):
                ln=fn(i); body=abs(c[i]-o[i])
                if side: ok=abs(h[i]-ln)<=tol and h[i]-max(o[i],c[i])>=max(body,tol) and c[i]<=ln
                else: ok=abs(l[i]-ln)<=tol and min(o[i],c[i])-l[i]>=max(body,tol) and c[i]>=ln
                if ok:
                    if i-last>=3: touches.append((i,side))
                    last=i
        touches.sort(); up=sum(1 for x in touches if x[1]); dnn=len(touches)-up
        alt=sum(1 for i in range(1,len(touches)) if touches[i][1]!=touches[i-1][1])
        if up<2 or dnn<2 or alt<1: return
        key=('tri1',int(ts[R[0]]),int(ts[S[0]]),int(ts[R[1]]),int(ts[S[1]]))
        s.snap['triangle']=dict(kind=kind,upper=round(rl(n),1),lower=round(sl(n),1),tol=round(tol,1))
        if key in s.used: return
        s.tri=dict(key=key,R=R,S=S,t0=ts[0],tol=tol,kind=kind)
    def tri_tick(s,t,o,h,l,c):
        T=getattr(s,'tri',None)
        if not T or T['key'] in s.used: return
        i=(t-T['t0'])/60000; up=T['R'][2]+T['R'][3]*(i-T['R'][0]); dn=T['S'][2]+T['S'][3]*(i-T['S'][0]); tol=T['tol']
        for buy,trig in ((True,up+tol),(False,dn-tol)):
            if (h>trig if buy else l<trig):
                s.used.add(T['key']); s.tri=None
                if len(s.open_auto(None,('tri1',)))>=10: return
                s.open(t,'tri1',buy,max(o,trig) if buy else min(o,trig),0.02,'1m %s triangle break %s (upper %.1f lower %.1f tol %.1f)'%(T['kind'],'up' if buy else 'down',up,dn,tol),exitmode='cost5full'); return
    def sig5(s,buy,need_atr=True):
        A=s.arr(5,20)
        if A is None: return False
        o,h,l,c,ts=A; a=atr(h,l,c)
        for i in (-1,-2,-3):
            adverse=(c[i]<o[i]) if buy else (c[i]>o[i]); mv=(c[i]-c[i-1])/c[i-1]
            if not adverse or abs(mv)<0.001 or (mv>0)==buy or abs(c[i]-o[i])<a*0.25: return False
        fav=(c[-4]>o[-4]) if buy else (c[-4]<o[-4])
        if fav and abs(c[-4]-o[-4])>=2*a: return False
        return True
    def rescue_signal(s,b):
        s.pending5={buy:(b[0]+300000,b[4]) for buy in (True,False) if s.sig5(buy)}
    def mark(s,t,c,h=None,l=None):
        e=s.equity(c); s.peak=max(s.peak,e); s.mdd=max(s.mdd,(s.peak-e)/s.peak)
        if e>0: s.max_mu=max(s.max_mu,s.margin()/e)
        if not s.eq or t-s.eq[-1][0]>=900000: s.eq.append((t,round(e,4),round(c,2)))
    # ---------- overlap cleanup + sr15 add + triangle tick, hooked into rescue_tick order
    def overlap(s,t,c):
        s.tri_tick_last=None
        for buy in (True,False):
            ps=sorted(s.open_auto(buy),key=lambda p:(p['t'],p['id']))
            if len(ps)<2: continue
            tgt=next((p for p in ps if p['id'] not in s.overlap_done),None)
            if tgt is None or tgt is not ps[0]: continue
            if t<ps[1]['t']+30*60000: continue
            q=sum(p['n'] for p in ps); avg=sum(p['entry']*p['n'] for p in ps)/q
            h1=math.floor(tgt['n']*0.5); d=1 if buy else -1
            tgt['ov']=True; tgt['tps']=[]; tgt['be_at']=None; tgt['ovo']=[(round(avg,1),h1),(round(avg+d*50,1),tgt['n']-h1)] if h1>=1 else [(round(avg+d*50,1),tgt['n'])]
            s.overlap_done.add(tgt['id']); s.log(t,'OVERLAP clean #%d %s: avg %.1f, 50%% @avg, 50%% @avg%+d'%(tgt['id'],'L' if buy else 'S',avg,d*50))
    def rescue_tick(s,t,o,h,l,c):
        s.tri_tick(t,o,h,l,c)
        # sr15 1% add on fresh 5m signal (within 60s of close)
        pd=getattr(s,'pending5',{})
        cy=s.sr15
        if cy and not cy['added'] and cy['buy'] in pd and pd[cy['buy']][0]==t and not s.rescue[cy['buy']]:
            ps=[p for p in s.pos if p['id'] in cy['ids']]
            if ps:
                q=sum(p['n'] for p in ps); avg=sum(p['entry']*p['n'] for p in ps)/q
                if (o<avg if cy['buy'] else o>avg):
                    cy['added']=True; p=s.open(t,'sr15',cy['buy'],o,0.01,'15m S/R add 1% (5m 3-bar adverse signal)',exitmode='sr15')
                    if p: cy['ids'].append(p['id'])
        if not ENABLED['rescue']: return
        for buy in (True,False):
            r=s.rescue[buy]; d=1 if buy else -1
            if r is None:
                if s.rescue[not buy]: continue          # one direction at a time
                mine=s.open_auto(buy)
                if getattr(s,'rescue_price',False):
                    if not mine: continue
                    _n=sum(p['n'] for p in mine); _avg=sum(p['entry']*p['n'] for p in mine)/_n
                    if (c-_avg)/_avg*100*d>-2.0: continue
                else:
                    hit=[p for p in mine if (c-p['entry'])/p['entry']*100*d*LEV<=RESCUE_ROI]
                    if not hit: continue
                for p in mine: p['rescue']=True; p['tps']=[]; p['be_at']=None; p['ov']=False
                if s.sr1 and s.sr1.get('retest') and s.sr1['retest']['buy']==buy: s.sr1['retest']=None
                av=max(0,s.free(c)); part=av*LEV*RESCUE_BUD/RESCUE_N
                n=sum(p['n'] for p in mine); avg=sum(p['entry']*p['n'] for p in mine)/n
                s.rescue[buy]=dict(t0=t,part=part,adds=0,half=False,alerted=False,n0=n)
                s.rescues.append(dict(t=t,side='L' if buy else 'S',avg=round(avg,1),px=round(c,1),avail=round(av,2),part_notional=round(part,2),entries=len(mine),adds=0))
                s.log(t,'RESCUE START %s (%s) avg %.1f px %.1f avail %.2f add notional %.2f'%('L' if buy else 'S','PRICE<=-2% vs avg' if getattr(s,'rescue_price',False) else 'ROI<=-2% x3',avg,c,av,part))
                continue
            if not r['alerted'] and t-r['t0']>72*3600000: r['alerted']=True; s.alerts.append(dict(t=t,msg='rescue %s > 72h'%('L' if buy else 'S'))); s.log(t,'ALERT rescue >72h')
            adds=[p for p in s.pos if p['buy']==buy and p['add']]; base=[p for p in s.pos if p['buy']==buy and p['rescue'] and not p['add']]
            if adds:
                q=sum(p['n'] for p in adds); aavg=sum(p['entry']*p['n'] for p in adds)/q; tp=aavg*(1+0.002*d)
                if (h>=tp if buy else l<=tp):
                    for p in adds: s.close(t,p,p['n'],tp,'rescue_add_tp+0.2%',limit=True)
            elif base:
                q=sum(p['n'] for p in base); avg=sum(p['entry']*p['n'] for p in base)/q
                if not r['half']:
                    tp=avg*(1+0.002*d)
                    if (h>=tp if buy else l<=tp):
                        for p in list(base): s.close(t,p,max(1,math.floor(p['n']*0.5)) if p['n']>1 else 1,tp,'rescue_base_50%@+0.2%',limit=True)
                        r['half']=True
                else:
                    tp=avg*(1+0.003*d)
                    if (h>=tp if buy else l<=tp):
                        for p in list(base): s.close(t,p,p['n'],tp,'rescue_base_rest@+0.3%',limit=True)
            if r['adds']<RESCUE_N and buy in pd and pd[buy][0]==t and abs(o-pd[buy][1])/pd[buy][1]<=0.001 and not [p for p in s.pos if p['buy']==buy and p['add']]==None:
                p=s.open(t,'rescue',buy,o,info='rescue add %d/10 (5m 3 adverse bars)'%(r['adds']+1),notional=r['part'])
                if p: r['adds']+=1; s.rescues[-1]['adds']=r['adds']
            if not [p for p in s.pos if p['buy']==buy and p['rescue']]:
                s.rescues[-1]['done']=t; s.log(t,'RESCUE DONE %s adds %d, %.1fh'%('L' if buy else 'S',r['adds'],(t-r['t0'])/3600000)); s.rescue[buy]=None
