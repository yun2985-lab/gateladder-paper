"""GateLadder 0.9.115 = engine11 (0.9.114 + all user settings) + 5-wave ranking: wave 5 within 10% of wave 1 (price)
-> '★1파=5파', +30 to the selection score. Sizes/TP/uses unchanged; other 0.9.115 changes are reports/display only."""
import engine11 as E11
from engine11 import Engine11
_el=E11.elliott
def elliott(p,buy):
    ok,sc=_el(p,buy); sg=1 if buy else -1; v=[x*sg for x in p]; w1=v[1]-v[0]
    if w1>0 and abs((v[5]-v[4])/w1-1)<=0.10: sc+=30
    return ok,sc
E11.elliott=elliott
class Engine12(Engine11):
    def __init__(s,*a,**k):
        super().__init__(*a,**k); s.version='0.9.115'
