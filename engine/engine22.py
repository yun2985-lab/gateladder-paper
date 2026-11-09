"""0.9.141 version2 on engine20; current user sizes throughout historical replay."""
from engine21 import Mix141
from engine20 import Engine20
class Engine22(Mix141,Engine20):
    def __init__(s,*a,**k):super().__init__(*a,**k);s.version='0.9.141 현재 비율'
