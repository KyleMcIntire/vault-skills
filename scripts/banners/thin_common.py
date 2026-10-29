"""Shared helpers for the thin (6:1) banner set: 360x60 logical pixels, shown at 1800x300.

Crop-safe band: Pixel Banner shows these at 200px tall with the note content starting at
101px, across panes ~800-1900px wide. Keep labels and focal motion in x 60-300, y 8-34.
"""
import math
import random
from pix import Cv, mix, ease, FONT, col

TW, TH = 360, 60
TAU = math.tau


def canvas(bg, shift=0):
    c = Cv(bg, TW, TH)
    c.oy = shift  # push the scene down so its top survives wide-pane crops
    return c


def bands(c, y0, y1, colours, x0=0, x1=None):
    x1 = c.w if x1 is None else x1
    step = (y1 - y0) / len(colours)
    for i, cc in enumerate(colours):
        c.rect(x0, y0 + round(i * step), x1 - x0, round((i + 1) * step) - round(i * step), cc)


WIDE = {'M': ["10001", "11011", "10101", "10001", "10001"],
        'W': ["10001", "10001", "10101", "11011", "10001"]}


def glyphs(s):
    return [WIDE.get(ch) or FONT.get(ch, FONT[' ']) for ch in s.upper()]


def text_width(s, scale=2):
    return sum(len(g[0]) + 1 for g in glyphs(s)) * scale - scale


def big_text(c, x, y, s, colour, shadow, scale=2):
    for cc, off in ((shadow, 1), (colour, 0)):
        cx = x
        for g in glyphs(s):
            for r, row in enumerate(g):
                for k, bit in enumerate(row):
                    if bit == '1':
                        c.rect(cx + k * scale + off, y + r * scale + off, scale, scale, cc)
            cx += (len(g[0]) + 1) * scale


def label(c, day, fg, shadow, plate, edge, x=62, y=13):
    w = text_width(day) + 9
    c.rrect(x, y, w, 16, plate)
    c.rect(x + 1, y + 15, w - 2, 1, edge)
    big_text(c, x + 4, y + 3, day, fg, shadow)


def cloud(c, x, y, s, top, under):
    parts = [(0, 0, 3), (4, -2, 4), (9, 0, 3), (13, 1, 2)]
    for dx, dy, r in parts:
        c.disc(x + dx * s, y + dy * s + 1, r * s, under)
    for dx, dy, r in parts:
        c.disc(x + dx * s, y + dy * s, r * s, top)


def drift(x0, t, span, speed=1, margin=30):
    """x position that wraps across [−margin, span) in an integer number of loops."""
    return (x0 + t * speed * (span + margin)) % (span + margin) - margin


def twinkle(c, seed, count, x0, y0, w, h, t, levels):
    rnd = random.Random(seed)
    for _ in range(count):
        x, y = x0 + rnd.randrange(w), y0 + rnd.randrange(h)
        k, ph = rnd.choice([1, 2, 3]), rnd.random()
        v = (math.sin(TAU * (t * k + ph)) + 1) / 2
        c.px(x, y, levels[min(len(levels) - 1, int(v * len(levels)))])


def bird(c, x, y, up, cc):
    for dx, dy in [(0, 0), (-1, -1 if up else 0), (1, -1 if up else 0), (-2, -1 if up else 1), (2, -1 if up else 1)]:
        c.px(x + dx, y + dy, cc)


def ridge(c, base, amp, freq, phase, colour):
    for x in range(c.w):
        h = amp * (0.6 * math.sin(x / freq + phase) + 0.4 * math.sin(x / (freq * 0.43) + phase * 2))
        top = int(base - amp - h)
        c.rect(x, top, 1, c.h - top, colour)


def steam(c, x, y, t, n=5, rise=8, light='#c3cad6', dark=None, speed=3):
    for i in range(n):
        u = (t * speed + i / n) % 1
        if u < 0.8:
            c.px(x + round(math.sin(TAU * u)), y - u * rise, light if (dark is None or u < 0.5) else dark)


# ---------------------------------------------------------------- room set pieces
# Shared by personal_hubs and new scene modules: wall stripes, desk, windows, shelves.
def wall(c, stripe, step=24):
    for x in range(0, TW, step):
        c.rect(x, -7, 1, 49, stripe)


def desk(c, top='#7a5236', body='#5a3e2b', grain='#4f3624'):
    c.rect(0, 42, TW, 2, top); c.rect(0, 44, TW, 16, body)
    for x0, y0, w in [(10, 48, 50), (120, 51, 70), (250, 49, 60)]:
        c.rect(x0, y0, w, 1, grain)


def city(c, t, wx, wy, ww, wh, seed, lo=10, hi=24):
    brnd = random.Random(seed)
    x = wx
    while x < wx + ww:
        bw, bh = min(brnd.randint(6, 11), wx + ww - x), brnd.randint(lo, hi)
        c.rect(x, wy + wh - bh, bw, bh, '#262b45')
        for yy in range(wy + wh - bh + 2, wy + wh - 1, 3):
            for xx in range(x + 1, x + bw - 1, 2):
                ph = brnd.random()
                if ph < 0.3 or (ph < 0.45 and math.sin(TAU * (t * 2 + ph * 7)) > 0.3):
                    c.px(xx, yy, '#e0af68')
        x += bw + 1


def mountains(c, t, wx, wy, ww, wh, seed):
    """Dusk sky, two ridges, a lake with a shimmering moon path and a lit shoreline town."""
    bands(c, wy, wy + wh * 2 // 3, ['#1e1d3d', '#2d2650', '#45305e', '#6a3d63'], wx, wx + ww)
    twinkle(c, seed, ww // 4, wx, wy, ww, wh // 3, t, ['#2d2650', '#6a74a8', '#eef0ff'])
    horizon = wy + wh * 2 // 3
    for x in range(wx, wx + ww):
        u = x - wx
        far = 4 + 9 * (1 - abs(((u + 9) % 26) - 13) / 13) + math.sin(u / 3)
        near = 2 + 4 * (1 - abs(((u + 3) % 18) - 9) / 9)
        c.rect(x, horizon - far, 1, far, '#4b4a85')
        if far > 10:
            c.rect(x, horizon - far, 1, 2, '#d8d4f0')
        c.rect(x, horizon - near, 1, near, '#2c3060')
    c.rect(wx, horizon, ww, wy + wh - horizon, '#1a2142')
    rnd = random.Random(seed + 1)
    for k in range(wy + wh - horizon):
        y = horizon + k
        for _ in range(3):
            x = wx + rnd.randrange(ww)
            if math.sin(TAU * (t * 3 + rnd.random())) > 0.2:
                c.rect(x, y, 2, 1, '#3a4378')
    for i in range(6):
        x = wx + 4 + i * 4 + (i % 2)
        if math.sin(TAU * (t * 2 + i * 0.37)) > -0.4:
            c.px(x, horizon - 1, '#f2c66b')


def frame_window(c, wx, wy, ww, wh, frame='#2e3450', sill='#6b4a33'):
    c.rect(wx + ww // 2 - 1, wy, 2, wh, frame)
    c.rect(wx - 4, wy + wh + 2, ww + 8, 2, sill)


def window_box(c, wx, wy, ww, wh, frame='#2e3450', glass='#141a33'):
    c.rect(wx - 2, wy - 2, ww + 4, wh + 4, frame); c.rect(wx, wy, ww, wh, glass)


def moon(c, x, y, sky='#141a33'):
    c.disc(x, y, 4, '#f4f0d8'); c.disc(x + 2, y - 2, 4, sky)


def books(c, x, y, specs):
    for bw, bh, bc in specs:
        c.rect(x, y - bh, bw, bh, bc); c.rect(x, y - bh + 2, bw, 1, mix(bc, '#ffffff', 0.25))
        x += bw + 1
    return x


def pin(c, x, y, cc):
    c.px(x, y, '#3b2a20'); c.px(x, y - 1, '#3b2a20')
    c.disc(x, y - 4, 2, cc); c.px(x - 1, y - 5, mix(cc, '#ffffff', 0.5))


def lantern(c, x, y, t, f):
    glow = ['#f2c66b', '#e0af68', '#ffd98a'][(f // 2 + (f // 5)) % 3]
    c.ellipse(x + 4, y + 5, 10, 9, '#3a3040', dither=True)
    c.rect(x + 2, y - 3, 4, 1, '#3a3a4a'); c.rect(x + 1, y - 2, 6, 1, '#4a4a5a')
    c.rect(x, y, 8, 10, '#4a4a5a'); c.rect(x + 1, y + 1, 6, 8, glow)
    c.rect(x + 3, y + 3, 2, 4, '#fff1c4'); c.rect(x, y + 4, 8, 1, '#4a4a5a')
    c.rect(x - 1, y + 10, 10, 2, '#3a3a4a')
