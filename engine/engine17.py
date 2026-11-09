"""GateLadder 0.9.129 = engine15 (0.9.124+3pp, size switch at SWITCH, all user settings: rebate 0.7, maker 0.018%/taker 0.042%,
breakeven OFF, fib 0.722 kept, no SL, fixed 3x) + app 0.9.125..0.9.129 trading changes (Mix129):
- 0.9.125 keepEven: moved TPs (0.9.72 overlap shift, 0.9.101 held shift) never below own break-even entry +-0.02%;
  24h-open auto trade -> one alert (log only, never closed at a loss).
- 0.9.126 sloped lines (|slope|>=20 USDT/h; trend/learned/manual, not flat/triangle/channel): no against-slope breakout.
  New 'bounce': descending line above price -> short limit on the line, ascending line below -> long limit, follows line,
  max 3 uses per line (next only after previous trade closed), ends on 2 closes through the line or when the auto line
  is no longer recommended. TP = line breakout TP (1m +50, 15m +100, others +50), size = breakout size.
- 0.9.127 fib 0.886 level (same size as other levels), trades once; when it fills that Fibonacci is used up
  (unfilled other levels cancelled, filled ones keep their TPs).
- 0.9.128 per-line mode (breakout/bounce/auto) + reset buttons: the line backup has no mode -> auto (slope rule).
  Stricter line learning (3-nearest <=0.9 etc.) NOT modelled (learned-line suggestions keep the 0.9.124 rule).
- 0.9.129 rescue start ROI -1.5% (was -3%); while a side's rescue is active, no new auto entry on that side except rescue adds."""
import math
import engine5 as E5, engine6 as E6, engine7 as E7
from engine5 import tat, TICK, LEV, FR, W, LOOKBACK, PAT_FRAMES, beyond, atrw, lid
from engine15 import Mix124, Engine13
E7.ENTRY=(0.382,0.5,0.618,0.722,0.786,0.886)
SLOPE=20.0; EVEN=0.0002; START_ROI=-1.5; BUSES=3
E5.RNAME['bounce']='추세선 닿으면 반대'; E6.RNAME['bounce']='추세선 닿으면 반대'
def slope_h(ln): return (float(ln['q'])-float(ln['p']))/(ln['b']-ln['a'])*3600000.0
_LAST={}
_ll,_al=E5.learned_lines,E5.auto_lines
def _wl(*a,**k): r=_ll(*a,**k); _LAST.setdefault(a[1],[]).extend(r); return r
def _wa(*a,**k): r=_al(*a,**k); _LAST.setdefault(a[1],[]).extend(r); return r
E5.learned_lines=_wl; E5.auto_lines=_wa
_an6=E6.analyze6
def analyze129(w,f,block,buy,ed):
    out=[]
    for sg in _an6(w,f,block,buy,ed):
        if sg['rule'] in ('trend','learned','manual') and 'line' in sg and sg.get('info')!='tri':
            sl=slope_h(sg['line'])
            if (buy and sl<=-SLOPE) or ((not buy) and sl>=SLOPE): continue
        out.append(sg)
    return out
E6.analyze6=analyze129
class Mix129(Mix124):
    def _init129(s): s.bnc={}; s.fib_done=set(); s.stuck=set()
    def open(s,t,strat,buy,px,pct=None,info='',limit=False,notional=None,exitmode=None):
        if strat!='cyc' and not getattr(s,'warm',False) and s.cr[buy]['phase']=='active': return None
        return super().open(t,strat,buy,px,pct,info,limit,notional,exitmode)
    # ---- 0.9.125
    def overlap(s,t,c):
        before={p['id']:list(p['tps']) for p in s.pos}
        super().overlap(t,c)
        for p in s.pos:
            if p['strat']=='cyc' or before.get(p['id'])==p['tps']: continue
            b=p['buy']; fl=p['entry']*(1+EVEN) if b else p['entry']*(1-EVEN)
            fl=math.ceil(fl/TICK-1e-9)*TICK if b else math.floor(fl/TICK+1e-9)*TICK; kept=False; new=[]
            for i,(x,n) in enumerate(p['tps']):
                if i>=p['tpi'] and ((b and x<fl) or ((not b) and x>fl)): x=fl; kept=True
                new.append((x,n))
            if kept: p['tps']=new; s.log(t,'KEEPEVEN(0.9.125) #%d 본전 %.1f 아래로는 안 내림'%(p['id'],fl))
        if not getattr(s,'warm',False):
            for p in s.pos:
                if p['strat']!='cyc' and p['id'] not in s.stuck and t-p['t']>=86400000:
                    s.stuck.add(p['id']); s.log(t,'STUCK 24h #%d %s %s (알림만, 손절 안 함)'%(p['id'],p['strat'],'L' if p['buy'] else 'S'))
    # ---- 0.9.126 bounce + 0.9.127 fib done
    def pat_bar(s,f,t):
        _LAST.clear(); super().pat_bar(f,t)
        if getattr(s,'warm',False) or f not in PAT_FRAMES: return
        for buy in (True,False):
            for k,sg in s.fsig[f][buy].items():
                if sg['fib'] in s.fib_done and not sg.get('void') and not sg.get('filled'): sg['void']=True
        bars=s.pb[f][-LOOKBACK:]
        for i in range(len(bars)-1,0,-1):
            if bars[i][0]-bars[i-1][0]!=FR[f]: bars=bars[i:]; break
        if len(bars)<60: return
        w=W(bars); last=w.n-1; atr=atrw(w); tol=max(1e-8,atr*.25); c=w.c[last]; live={p['id'] for p in s.pos}
        cand={}
        for hb,Ls in _LAST.items():
            for L in Ls:
                if L.get('tri') or L.get('flat'): continue
                p=w.v(L['hh'],L['a']); q=w.v(L['hh'],L['b']); ln=dict(a=int(w.t[L['a']]),b=int(w.t[L['b']]),p=p,q=q)
                cand['auto:'+lid(ln['a'],ln['b'],p,q)]=(ln,'auto')
        ed=s.ed(f,t)
        for m in ed['manual']:
            if m['id'] in ed['excluded'] or m.get('channel') or m.get('triangle'): continue
            ln=dict(m['line']); ln['a']=int(ln['a']); ln['b']=int(ln['b']); ln['p']=float(ln['p']); ln['q']=float(ln['q'])
            if 'until' in ln: ln['until']=int(ln['until'])
            if ln['a']>=w.t[last-2] or ('until' in ln and w.t[last]>ln['until']): continue
            cand['manual:'+m['id']]=(ln,'manual')
        for key,(ln,src) in cand.items():
            K=(f,key)
            if K in s.bnc: continue
            sl=slope_h(ln); v=tat(ln,w.t[last])
            if sl<=-SLOPE and v>c+tol: bb=False
            elif sl>=SLOPE and v<c-tol: bb=True
            else: continue
            s.bnc[K]=dict(ln=ln,buy=bb,uses=0,busy=None,frm=t,src=src,brk=0,done=False)
            s.log(t,'BOUNCE %dm %s 기울어진 선(%+.0f/h) 닿으면 %s 지정가 대기 %.1f'%(f,src,sl,'롱' if bb else '숏',v))
        for K,b in s.bnc.items():
            if K[0]!=f or b['done']: continue
            v=tat(b['ln'],w.t[last])
            b['brk']=b['brk']+1 if (c<v-tol if b['buy'] else c>v+tol) else 0
            why=None
            if b['brk']>=2: why='종가 2개 돌파'
            elif b['src']=='auto' and K[1] not in cand: why='추천 끝'
            elif 'until' in b['ln'] and t>b['ln']['until']: why='선 기간 끝'
            elif b['uses']>=BUSES and (b['busy'] is None or b['busy'] not in live): why='3번 사용'
            if why: b['done']=True; s.log(t,'BOUNCE %dm %s 끝 (%s)'%(f,K[1][:40],why))
        for K in [K for K,b in s.bnc.items() if b['done'] and (b['busy'] is None or b['busy'] not in live)]: del s.bnc[K]
    def limits(s,t,o,h,l,c):
        super().limits(t,o,h,l,c)
        if getattr(s,'warm',False): return
        live={p['id'] for p in s.pos}
        for f in PAT_FRAMES:
            for buy in (True,False):
                D=s.fsig[f][buy]
                for k,sg in list(D.items()):
                    if sg['lv']==0.886 and sg['uses']>=1 and sg['fib'] not in s.fib_done:
                        s.fib_done.add(sg['fib']); sg['filled']=True
                        for k2,o2 in D.items():
                            if o2['fib']==sg['fib'] and not o2.get('filled') and not o2.get('void'): o2['void']=True
                        s.log(t,'FIB %dm %s 0.886 닿아 1번 매매 · 사용 완료 (%s)'%(f,'L' if buy else 'S',sg['fib']))
        for (f,key),b in s.bnc.items():
            if b['done'] or t<b['frm'] or b['uses']>=BUSES: continue
            if b['busy'] is not None:
                if b['busy'] in live: continue
                b['busy']=None
            blk=t//FR[f]*FR[f]; v=tat(b['ln'],blk); buy=b['buy']
            px=math.ceil(v/TICK)*TICK if buy else math.floor(v/TICK)*TICK
            if not (o>px if buy else o<px): continue
            if (l<=px if buy else h>=px):
                N=max(0,s.free(px))*0.04*LEV
                p=s.open(t,'pat%d'%f,buy,px,info='%s %dm 추세선 닿으면 반대 @%.1f (%d/3) %s'%('L' if buy else 'S',f,px,b['uses']+1,key[:30]),limit=True,notional=N,exitmode='pat')
                if p: b['uses']+=1; b['busy']=p['id']
    # ---- 0.9.129 rescue start -1.5%
    def rescue_tick(s,t,o,h,l,c):
        s.tri_tick(t,o,h,l,c)
        if getattr(s,'warm',False): return
        for buy in (True,False):
            r=s.cr[buy]; roi=s.side_roi(buy,c); sd='L' if buy else 'S'
            if r['phase']!='active':
                if roi is not None and roi<=START_ROI:
                    r.update(phase='active',started=t,adds=0,ticks=None,lastAdd=None,slot=None,ntr=len(s.trades))
                    held=[p for p in s.pos if p['buy']==buy and p['strat']!='cyc' and p['n']>0]
                    for p in held: p['tps_h']=p['tps']; p['tps']=p['tps'][:p['tpi']]; p['rhold']=True
                    r['held']=[p['id'] for p in held]
                    for (f,key),b in s.bnc.items():
                        pass
                    s.crlog.append(dict(t=t,side=sd,start_roi=round(roi,2),adds=0)); s.rescues.append(dict(t=t,side=sd,roi=round(roi,2),adds=0,held=len(held)))
                    s.log(t,'CYCLE RESCUE START %s ROI %.2f%% · 물린 거래 %d건 100%% 회복까지 보유 · 이 방향 신규 진입 멈춤'%(sd,roi,len(held)))
                continue
            ids=set(r.get('held') or [])
            hp=[p for p in s.pos if p['id'] in ids]
            if roi is None or (not ids and roi>=0) or (ids and not hp):
                r['phase']='watch'; r['slot']=None; r['held']=[]; s.rescues[-1]['done']=t
                s.log(t,'CYCLE RESCUE END %s %s adds %d · 이 방향 자동매매 다시 시작'%(sd,'flat' if roi is None else 'ROI %.2f%%'%roi,r['adds'])); continue
            if ids:
                rec=s._recovery(buy,r,c)
                if rec>=0:
                    at=math.floor(c/TICK)*TICK if buy else math.ceil(c/TICK)*TICK
                    for p in hp: s.close(t,p,p['n'],at,'rescue_hold_100%',limit=True)
                    r['phase']='watch'; r['slot']=None; r['held']=[]; s.rescues[-1]['done']=t
                    s.log(t,'CYCLE RESCUE END %s 손실 100%% 회복 (+%.2f) · 물린 거래 %d건 %.1f에 정리 · adds %d · 이 방향 자동매매 다시 시작'%(sd,rec,len(hp),at,r['adds']))
class Engine17(Mix129,Engine13):
    def __init__(s,*a,**k):
        super().__init__(*a,**k); s.version='0.9.129+3pp'; s._init124(); s._init129()
