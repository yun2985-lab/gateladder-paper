"""0.9.138 version 2: engine18 ancestry, current sizes for whole replay."""
from engine19 import Mix138
from engine18 import Engine18
class Engine20(Mix138,Engine18):
    def __init__(s,*a,**k):super().__init__(*a,**k);s.version='0.9.138 현재 비율'
