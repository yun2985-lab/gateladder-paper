"""Version 2: engine14 (current sizes whole period, fib slot pruning) + 0.9.124 (Mix124) + 0.9.125..0.9.129 (engine17.Mix129)."""
from engine14 import Engine14
from engine17 import Mix129
class Engine18(Mix129,Engine14):
    def __init__(s,*a,**k):
        super().__init__(*a,**k); s.version='0.9.129 현재 비율'; s._init124(); s._init129()
