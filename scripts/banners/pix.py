"""Tiny pixel-art canvas + looping GIF writer."""
import math
import random
import numpy as np
from PIL import Image

W, H = 320, 100

FONT = {
    'A': ["010", "101", "111", "101", "101"], 'B': ["110", "101", "110", "101", "110"],
    'C': ["011", "100", "100", "100", "011"], 'D': ["110", "101", "101", "101", "110"],
    'E': ["111", "100", "110", "100", "111"], 'F': ["111", "100", "110", "100", "100"],
    'G': ["011", "100", "101", "101", "011"], 'H': ["101", "101", "111", "101", "101"],
    'I': ["111", "010", "010", "010", "111"], 'J': ["001", "001", "001", "101", "010"],
    'K': ["101", "101", "110", "101", "101"], 'L': ["100", "100", "100", "100", "111"],
    'M': ["101", "111", "111", "101", "101"], 'N': ["110", "101", "101", "101", "101"],
    'O': ["010", "101", "101", "101", "010"], 'P': ["110", "101", "110", "100", "100"],
    'Q': ["010", "101", "101", "110", "011"], 'R': ["110", "101", "110", "101", "101"],
    'S': ["011", "100", "010", "001", "110"], 'T': ["111", "010", "010", "010", "010"],
    'U': ["101", "101", "101", "101", "111"], 'V': ["101", "101", "101", "101", "010"],
    'W': ["101", "101", "111", "111", "101"], 'X': ["101", "101", "010", "101", "101"],
    'Y': ["101", "101", "010", "010", "010"], 'Z': ["111", "001", "010", "100", "111"],
    '0': ["111", "101", "101", "101", "111"], '1': ["010", "110", "010", "010", "111"],
    '{': ["011", "010", "110", "010", "011"], '}': ["110", "010", "011", "010", "110"],
    '<': ["001", "010", "100", "010", "001"], '>': ["100", "010", "001", "010", "100"],
    '/': ["001", "001", "010", "100", "100"], ';': ["000", "010", "000", "010", "100"],
    '=': ["000", "111", "000", "111", "000"], '(': ["010", "100", "100", "100", "010"],
    ')': ["010", "001", "001", "001", "010"], '[': ["110", "100", "100", "100", "110"],
    ']': ["011", "001", "001", "001", "011"], '+': ["000", "010", "111", "010", "000"],
    '*': ["000", "101", "010", "101", "000"], '#': ["101", "111", "101", "111", "101"],
    '$': ["011", "110", "010", "011", "110"], '_': ["000", "000", "000", "000", "111"],
    ':': ["000", "010", "000", "010", "000"], '.': ["000", "000", "000", "000", "010"],
    ' ': ["000", "000", "000", "000", "000"],
}


def col(c):
    if isinstance(c, str):
        h = c.lstrip('#')
        return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.uint8)
    return np.array(c, np.uint8)


def mix(a, b, t, steps=4):
    """Blend two colours, quantised to a few steps to keep the palette small."""
    t = round(max(0.0, min(1.0, t)) * steps) / steps
    a, b = col(a).astype(float), col(b).astype(float)
    return tuple(int(round(v)) for v in a + (b - a) * t)


class Cv:
    def __init__(self, bg, w=None, h=None):
        self.w, self.h = w or W, h or H
        self.oy = 0  # vertical offset applied to every draw call
        self.a = np.zeros((self.h, self.w, 3), np.uint8)
        self.a[:] = col(bg)

    def px(self, x, y, c):
        x, y = int(round(x)), int(round(y + self.oy))
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x] = col(c)

    def rect(self, x, y, w, h, c):
        y = y + self.oy
        x0, y0 = max(0, int(round(x))), max(0, int(round(y)))
        x1, y1 = min(self.w, int(round(x + w))), min(self.h, int(round(y + h)))
        if x1 > x0 and y1 > y0:
            self.a[y0:y1, x0:x1] = col(c)

    def rrect(self, x, y, w, h, c):
        self.rect(x + 1, y, w - 2, h, c)
        self.rect(x, y + 1, w, h - 2, c)

    def outline(self, x, y, w, h, c):
        self.rect(x, y, w, 1, c); self.rect(x, y + h - 1, w, 1, c)
        self.rect(x, y, 1, h, c); self.rect(x + w - 1, y, 1, h, c)

    def disc(self, cx, cy, r, c):
        for y in range(int(cy - r - 1), int(cy + r + 2)):
            for x in range(int(cx - r - 1), int(cx + r + 2)):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + r * 0.6:
                    self.px(x, y, c)

    def ellipse(self, cx, cy, rx, ry, c, dither=False):
        for y in range(int(cy - ry - 1), int(cy + ry + 2)):
            for x in range(int(cx - rx - 1), int(cx + rx + 2)):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                    if not dither or (x + y) % 2 == 0:
                        self.px(x, y, c)

    def dither(self, x, y, w, h, c, phase=0):
        for yy in range(int(y), int(y + h)):
            for xx in range(int(x), int(x + w)):
                if (xx + yy + phase) % 2 == 0:
                    self.px(xx, yy, c)

    def line(self, x0, y0, x1, y1, c):
        x0, y0, x1, y1 = map(lambda v: int(round(v)), (x0, y0, x1, y1))
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            self.px(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy; x0 += sx
            if e2 <= dx:
                err += dx; y0 += sy

    def text(self, x, y, s, c):
        for i, ch in enumerate(s.upper()):
            g = FONT.get(ch, FONT[' '])
            for r, row in enumerate(g):
                for k, bit in enumerate(row):
                    if bit == '1':
                        self.px(x + i * 4 + k, y + r, c)

    def sparkle(self, x, y, size, c, core=None):
        if size <= 0:
            return
        self.px(x, y, core or c)
        for d in range(1, size + 1):
            for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d)):
                self.px(x + dx, y + dy, c)


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def save_gif(frames, path, scale=5, duration=90):
    """frames: list of (H,W,3) uint8 arrays. Uses one shared palette, no dithering."""
    stack = np.stack(frames)
    flat = stack.reshape(-1, 3)
    uniq = np.unique(flat, axis=0)
    if len(uniq) <= 256:
        pal = uniq
    else:  # fallback: median-cut over a mosaic of all frames
        mosaic = Image.fromarray(stack.reshape(-1, stack.shape[2], 3))
        q = mosaic.quantize(256, method=Image.Quantize.MEDIANCUT)
        pal = np.array(q.getpalette()[:768], np.uint8).reshape(-1, 3)
    pal_img = Image.new('P', (1, 1))
    flat_pal = list(pal.flatten()) + [0] * (768 - pal.size)
    pal_img.putpalette(flat_pal)
    out = []
    for fr in frames:
        big = np.repeat(np.repeat(fr, scale, axis=0), scale, axis=1)
        im = Image.fromarray(big).quantize(palette=pal_img, dither=Image.Dither.NONE)
        out.append(im)
    out[0].save(path, save_all=True, append_images=out[1:], loop=0,
                duration=duration, optimize=False, disposal=1)
    return len(uniq)
