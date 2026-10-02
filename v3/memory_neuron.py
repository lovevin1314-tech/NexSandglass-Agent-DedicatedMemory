"""记忆神经元 — 落沙+涟漪。with open('a')追写。"""
from datetime import datetime
import os
from sandglass_paths import _NB
_SANDGLASS = os.path.join(_NB, "sandglass.txt")
from perception_neuron import sense as perc_sense
def put(text, sender):
    if sender != "user" and (text.startswith("<invoke") or '"function":' in text):
        return
    sender = sender.replace('|', ' ')
    sanitized = text.replace('\r\n',' ').replace('\n',' ').replace('\r',' ')
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {sender} | {sanitized}\n"
    with open(_SANDGLASS, "a", encoding="utf-8") as f:
        f.write(line)
    perc_sense()
