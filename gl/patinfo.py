"""Dashboard info for PatternRun: active user lines, recommended lines, pending signals per frame."""
import time, engine5 as E5
from engine5 import W, tat, spent, FR, PAT_FRAMES, LOOKBACK
def patinfo(e):
    out={}; now=e.last+60000
    for f in PAT_FRAMES:
        bars=e.pb[f][-LOOKBACK:]
        if len(bars)<60: continue
        w=W(bars); atr=E5.atrw(w); tol=max(1e-8,atr*.25); ed=e.ed(f,now); last=w.n-1
        man=[]
        for m in ed['manual']:
            if m['id'] in ed['excluded']: continue
            ln=dict(m['line']); ln={k:(float(v) if k in ('p','q') else int(v)) for k,v in ln.items()}
            if 'until' in ln and now>ln['until']: continue
            sides=[True,False] if m.get('both') else [m['resistance']]
            act=[b for b in sides if not spent(w,ln,b,tol,last)]
            if not act: continue
            man.append(dict(id=m['id'],kind='both' if m.get('both') else ('R' if m['resistance'] else 'S'),level=round(tat(ln,now),1),
                a=ln['a']//1000,pa=round(tat(ln,ln['a']),1),t1=now//1000,p1=round(tat(ln,now),1)))
        rec=[]
        S=ed['samples']
        if sum(1 for s in S if not s.get('neg'))>=5:
            mine={m['id'] for m in ed['manual']}
            for buy in (True,False):
                try:
                    for L in E5.learned_lines(w,buy,atr,tol,last,ed['excluded'],S,mine):
                        a,b,hh=L['a'],L['b'],L['hh']; p=w.v(hh,a); q=w.v(hh,b)
                        rec.append(dict(side='L' if buy else 'S',level=round(E5.at(a,p,b,q,last),1),like=L.get('like'),tri=L['tri']))
                except Exception: pass
        sig=[]
        for buy in (True,False):
            for s in e.sigs[f][buy]:
                if s.get('void') or s.get('filled') or s['until']<=now: continue
                px=tat(s['line'],now//FR[f]*FR[f]) if 'line' in s else s['price']
                sig.append(dict(side='L' if buy else 'S',rule=E5.RNAME.get(s['rule'],s['rule']) if s['rule']!='fake' else '가짜 돌파 반대 진입',price=round(px,1),dormant=bool(s.get('dormant')),until=time.strftime('%m-%d %H:%M',time.localtime(s['until']/1000))))
        out[str(f)]=dict(manual=man,recommended=rec,pending=sig)
    return out
