"""Render thin banners and simulate how Pixel Banner crops them at 200px tall.

Usage, from this folder (needs Pillow and numpy):
    python render_thin.py <module> <outdir> [scene ...]
A module is any file in this folder with a SCENES dict mapping a name to
(function(frame, frames) -> (H, W, 3) uint8 array, frame_count). `example_scenes`
ships as a starting point; copy it and add your own. Render to a scratch outdir,
review <name>-frames.png (four moments of the loop) and crops.png (pane widths),
then copy the GIFs into your banners folder. The note-type banners come from
render_note_banners.py in this folder instead.
"""
import importlib
import os
import sys
import numpy as np
from PIL import Image, ImageDraw
from pix import save_gif

mod = importlib.import_module(sys.argv[1])
out = sys.argv[2]
only = sys.argv[3:] or list(mod.SCENES)
os.makedirs(out, exist_ok=True)
PANES = [800, 1100, 1500, 1900]
BH, CONTENT = 200, 101


def simulate(frame_rgb, pane):
    img = Image.fromarray(frame_rgb)
    iw, ih = img.size
    scale = max(pane / iw, BH / ih)               # object-fit: cover
    big = img.resize((round(iw * scale), round(ih * scale)), Image.NEAREST)
    x0 = (big.width - pane) // 2                  # banner-x / banner-y 50
    y0 = (big.height - BH) // 2
    crop = big.crop((x0, y0, x0 + pane, y0 + BH)).convert('RGB')
    d = ImageDraw.Draw(crop, 'RGBA')
    d.rectangle((0, CONTENT, pane, BH), fill=(30, 30, 30, 120))   # where note content starts
    return crop


rows = []
for name in only:
    fn, n = mod.SCENES[name]
    frames = [fn(f, n) for f in range(n)]
    path = os.path.join(out, name + '.gif')
    k = save_gif(frames, path, scale=5, duration=90)
    print(f"{name}: {n} frames, {k} colours, {os.path.getsize(path) / 1e6:.2f} MB")
    strip = np.concatenate([np.pad(frames[n * q // 4], ((0, 2), (0, 0), (0, 0)), constant_values=255)
                            for q in range(4)])
    Image.fromarray(np.repeat(np.repeat(strip, 3, 0), 3, 1)).save(os.path.join(out, name + '-frames.png'))
    mid =np.repeat(np.repeat(frames[n // 3], 5, 0), 5, 1)
    sims = [simulate(mid, p) for p in PANES]
    w = max(s.width for s in sims)
    row = Image.new('RGB', (w, sum(s.height + 6 for s in sims)), (255, 255, 255))
    y = 0
    for s in sims:
        row.paste(s, (0, y)); y += s.height + 6
    rows.append(row.resize((row.width // 2, row.height // 2), Image.NEAREST))
sheet_w = max(r.width for r in rows)
sheet = Image.new('RGB', (sheet_w, sum(r.height + 10 for r in rows)), (255, 255, 255))
y = 0
for r in rows:
    sheet.paste(r, (0, y)); y += r.height + 10
sheet.save(os.path.join(out, 'crops.png'))
