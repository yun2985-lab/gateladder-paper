"""GateLadder 0.9.100 paper engine = engine5 (0.9.95) + 0.9.96 fake-breakout reverse entry on my lines,
0.9.98 basis check (gone->dormant/cancel, alive->re-order max 3, divergence broken -> end; no void when price inside),
0.9.100 maker (post-only) entries for divergence & fake: price min(signal, last-1tick) long / max(signal, last+1tick) short, fee 0.02%.
0.9.97/0.9.99 are app-only (order record sync, drawing UI)."""
import math, engine5 as E5
from engine5 import Engine5, W, tat, beyond, spent, FR, PAT_FRAMES, LOOKBACK, TICK, LEV, RNAME
FAKE_BARS=5; REPLACE=3; MAKER_FEE=0.0002
RNAME=dict(RNAME,fake='가짜 돌파 반대 진입')
def analyze6(w,f,block,buy,ed):
    out=E5.analyze(w,f,block,buy,ed)
    fm=FR[f]; n=w.n
    if n<60 or w.t[-1]+fm!=block or n<4: return out
    atr=E5.atrw(w); tol=max(1e-8,atr*.25); last=n-1; up=not buy
    for m in ed['manual']:
        if not (m.get('both') or m['resistance']==(not buy)) or m['id'] in ed['excluded']: continue
        ln=dict(m['line']); ln['a']=int(ln['a']); ln['b']=int(ln['b']); ln['p']=float(ln['p']); ln['q']=float(ln['q'])
        if 'until' in ln: ln['until']=int(ln['until'])
        if ln['a']>=w.t[last-2]: continue
        if 'until' in ln and w.t[last]>ln['until']: continue
        if spent(w,ln,up,tol,last): continue
        v0,v1,v2=(tat(ln,w.t[k]) for k in (last-2,last-1,last)); c0,c1,c2=w.c[last-2],w.c[last-1],w.c[last]
        wick=(w.h[last]>v2+tol and c2<v2 and c1<=v1) if up else (w.l[last]<v2-tol and c2>v2 and c1>=v1)
        one=(c1>v1+tol and c2<v2 and c0<=v0) if up else (c1<v1-tol and c2>v2 and c0>=v0)
        if not wick and not one: continue
        out.append(dict(rule='fake',key='fake:%s:%d'%(m['id'],w.t[last]),price=float(c2),fakeLine=ln,tol=tol,frm=block,until=block+FAKE_BARS*fm,
            info=('꼬리만 돌파 후 복귀 ' if wick else '1봉 돌파 후 복귀 ')+m['id']))
    return out
def basis(sg,w,buy):
    c=w.c[-1]; tol=sg.get('tol',0); r=sg['rule']
    if r=='channel': return 'keep'
    if r in ('bull_div','bear_div'):
        tb=int(sg['key'].split(':')[2]); idx=[i for i in range(w.n) if w.t[i]==tb]
        if not idx: return 'keep'
        p=idx[0]; return ('broken' if w.l[-1]<w.l[p] else 'keep') if buy else ('broken' if w.h[-1]>w.h[p] else 'keep')
    ln=sg.get('fakeLine' if r=='fake' else 'line')
    if ln is None: return 'keep'
    v=tat(ln,w.t[-1])
    if r=='fake': return ('gone' if c<v-tol else 'alive' if c>v else 'keep') if buy else ('gone' if c>v+tol else 'alive' if c<v else 'keep')
    return ('gone' if c<v else 'alive' if c>v+tol else 'keep') if buy else ('gone' if c>v else 'alive' if c<v-tol else 'keep')
class Engine6(Engine5):
    def __init__(s,*a,**k):
        super().__init__(*a,**k); s.version='0.9.100'; s._fr=None
    def fee(s,notional):
        r=s._fr if getattr(s,'_fr',None) is not None else E5.E4.FEE
        f=notional*r; s.cash-=f; s.fees+=f; s.rebate+=f*E5.E4.REBATE; return f
    def pat_bar(s,f,t):
        bars=s.pb[f][-LOOKBACK:]
        for i in range(len(bars)-1,0,-1):
            if bars[i][0]-bars[i-1][0]!=FR[f]: bars=bars[i:]; break
        if len(bars)<60: return
        w=W(bars)
        for buy in (True,False):
            L=s.sigs[f][buy]
            for sg in L:
                if sg.get('void') or sg.get('filled') or t>=sg['until'] or sg['frm']>=t: continue
                if sg['rule']=='channel':
                    cl=w.c[-1]; e1=tat(sg['base'],w.t[-1]); e2=tat(sg['line'],w.t[-1])
                    if cl>max(e1,e2)+sg['tol'] or cl<min(e1,e2)-sg['tol']: sg['void']=True
                    continue
                st=basis(sg,w,buy)
                if st=='broken': sg['void']=True; s.log(t,'PAT %dm %s %s 근거 깨짐 취소'%(f,'L' if buy else 'S',RNAME[sg['rule']]))
                elif st=='gone' and not sg.get('dormant'): sg['dormant']=True; s.log(t,'PAT %dm %s %s 근거 사라짐 (휴면)'%(f,'L' if buy else 'S',RNAME[sg['rule']]))
                elif st=='alive' and sg.get('dormant'):
                    if sg.get('replaced',0)>=REPLACE: sg['void']=True
                    else: sg['dormant']=False; sg['replaced']=sg.get('replaced',0)+1; s.log(t,'PAT %dm %s %s 근거 회복 재주문 %d/3'%(f,'L' if buy else 'S',RNAME[sg['rule']],sg['replaced']))
            if getattr(s,'warm',False): continue
            try: new=analyze6(w,f,t,buy,s.ed(f,t))
            except Exception as ex: s.log(t,'PAT ERR %r'%ex); new=[]
            for sg in new:
                k=(f,buy,sg['key'])
                if k in s.known: continue
                s.known.add(k); L.append(sg); s.log(t,'PAT SIGNAL %dm %s %s %s'%(f,'L' if buy else 'S',RNAME[sg['rule']],sg.get('info','')))
            s.sigs[f][buy]=[x for x in L if not x.get('void') and not x.get('filled') and x['until']>t]
    def limits(s,t,o,h,l,c):
        E5.Engine4.limits(s,t,o,h,l,c)
        if getattr(s,'warm',False): return
        for f in PAT_FRAMES:
            blk=t//FR[f]*FR[f]
            for buy in (True,False):
                for sg in s.sigs[f][buy]:
                    if sg.get('void') or sg.get('filled') or sg.get('dormant') or t<sg['frm'] or t>=sg['until']: continue
                    mk=sg['rule'] in ('bull_div','bear_div','fake')
                    if 'line' in sg:
                        v=tat(sg['line'],blk); px=math.floor(v/TICK)*TICK if buy else math.ceil(v/TICK)*TICK
                        if not (o>px if buy else o<px): continue      # 0.9.98: wait, no void
                    else:
                        px=math.floor(sg['price']/TICK)*TICK if buy else math.ceil(sg['price']/TICK)*TICK
                        if mk: px=min(px,round(o-TICK,1)) if buy else max(px,round(o+TICK,1))
                    if (l<=px if buy else h>=px):
                        N=max(0,s.free(px))*0.04*LEV
                        s._fr=MAKER_FEE if mk else None
                        try: s.open(t,'pat%d'%f,buy,px,info='%s %dm %s @%.1f%s %s'%('L' if buy else 'S',f,RNAME[sg['rule']],px,' maker' if mk else '',sg.get('info','')),limit=True,notional=N,exitmode='pat')
                        finally: s._fr=None
                        sg['filled']=True
        s.cr_fill(t,o,h,l,c)
