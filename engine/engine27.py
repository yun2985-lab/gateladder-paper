"""0.9.148 version2-only adapter on Engine26 (.147).
Source changes: max20 currently OPEN rescue adds (slots reusable after TP),
0.3% distance from EVERY open add; no last-add monotonic condition.
No normal same-side entries until rescue ends: remove spent20 1/3 + SMA120 restart.
All paper fee/size/no-SL/no-BE/MA/line approximations remain unchanged.
"""
import math
from decimal import Decimal, ROUND_HALF_UP
from engine26 import Engine26
from engine5 import cr_step, LEV, TICK

def near148(prices,price):
    q=Decimal(str(price))
    for x in prices:
        o=Decimal(str(x))
        if o>0 and ((q-o).copy_abs()/o).quantize(Decimal('0.00000001'),rounding=ROUND_HALF_UP)<Decimal('0.003'):return x
    return None

class Engine27(Engine26):
    def __init__(s,*a,**k):super().__init__(*a,**k);s.version='0.9.148 현재 비율'
    def rescue_small(s,buy):return False
    def rescue_blocks(s,buy):return s.cr[buy]['phase']=='active'
    def open_adds(s,buy):
        r=s.cr[buy]
        return [p for p in s.pos if p['strat']=='cyc' and p['buy']==buy and p['n']>0 and p['t']>=r.get('started',float('inf'))]
    def cr_bar(s,t):
        if getattr(s,'warm',False):return
        bars=s.pb[3]
        for buy in (True,False):
            r=s.cr[buy]
            if r['slot'] and t-r['slot']['blk']>=2*180000:r['slot']=None
            if r['phase']!='active' or len(bars)<40:continue
            k=len(bars)-1
            if r['ticks'] is None:r['ticks']={};cr_step(r['ticks'],bars,k,buy);continue
            hit=cr_step(r['ticks'],bars,k,buy)
            if not hit or r['slot']:continue
            adds=s.open_adds(buy)
            if len(adds)>=20:continue
            px=bars[k][4];px=math.floor(px/TICK)*TICK if buy else math.ceil(px/TICK)*TICK
            near=near148([p['entry'] for p in adds],px)
            if near is not None:
                s.log(t,'CYCLE add skipped %.1f within 0.3%% of open add %.1f'%(px,near));continue
            r['slot']=dict(px=px,blk=t)
            s.log(t,'CYCLE add limit %s %.1f (3m 3-tick; open %d/20, gap0.3%%)'%('L' if buy else 'S',px,len(adds)))
    def cr_fill(s,t,o,h,l,c):
        for buy in (True,False):
            r=s.cr[buy];sl=r['slot']
            if not sl or t<sl['blk']:continue
            if l<=sl['px'] if buy else h>=sl['px']:
                # Same raw2% notional as established engine5, transformed by
                # inherited version2 current-size override to USER6% x fixed3.
                N=max(0,s.free(sl['px']))*.02*LEV
                p=s.open(t,'cyc',buy,sl['px'],info='cycle rescue add %d total; open %d/20 @%.1f'%(r['adds']+1,len(s.open_adds(buy))+1,sl['px']),limit=True,notional=N,exitmode='cyc')
                r['slot']=None
                if p:
                    r['adds']+=1;r['lastAdd']=sl['px']
                    for rs in reversed(s.rescues):
                        if rs['t']==r.get('started') and rs['side']==('L' if buy else 'S'):rs['adds']=r['adds'];break
                    s.log(t,'CYCLE ADD OPEN %s total%d open%d/20'%('L' if buy else 'S',r['adds'],len(s.open_adds(buy))))
