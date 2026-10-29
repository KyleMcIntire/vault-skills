"""A minimal scene module for render_thin.py: one looping night-skyline banner.

Copy this file, rename it, and add scenes to SCENES. Every scene is a function
f(frame, frames) -> (H, W, 3) uint8 array that must loop: the last frame should
lead smoothly back into the first. Keep labels and focal motion in the
crop-safe band described in thin_common.py.
"""
import math
import random

from pix import mix
from thin_common import TAU, TH, TW, bands, canvas, label

SKY = ['#10182b', '#16213b', '#1d2b4d', '#26386a']


def skyline(f, n):
    t = f / n
    c = canvas(SKY[0])
    bands(c, 0, 40, SKY)
    rnd = random.Random(3)
    for _ in range(40):  # stars twinkle on a loop
        x, y = rnd.randrange(TW), rnd.randrange(30)
        if math.sin(TAU * (t + rnd.random())) > 0.4:
            c.px(x, y, '#f4efe0')
    c.disc(300, 14 + 2 * math.sin(TAU * t), 5, '#f4efe0')  # moon bobbing gently
    for i in range(14):  # buildings with lit windows
        bx, bh = i * 26, 14 + (i * 11) % 20
        c.rect(bx, TH - bh, 24, bh, '#0d1322')
        for wy in range(TH - bh + 3, TH - 2, 4):
            for wx in range(bx + 3, bx + 22, 5):
                lit = math.sin(TAU * (t * 2 + wx * 0.37 + wy * 0.11)) > 0.2
                c.px(wx, wy, mix('#2a3350', '#f2c46d', 1.0 if lit else 0.0))
    label(c, 'NOTES', '#f4efe0', '#10182b', '#26386a', '#6bb8f5')
    return c.a


SCENES = {'skyline': (skyline, 48)}
