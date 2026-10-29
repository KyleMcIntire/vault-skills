"""Recolour an installed banner GIF with a hub theme, for banners whose scene script is gone.

Usage, from this folder (needs Pillow and numpy):
    python recolor_gif.py <theme> <in.gif> <out.gif>
Themes are in hub_themes.py. Render to a scratch path, review, then copy into Media/Banners.
"""
import sys
import numpy as np
from PIL import Image, ImageSequence
from hub_themes import retheme

theme, src, dst = sys.argv[1:4]
im = Image.open(src)
duration = im.info.get('duration', 90)
frames = [np.array(fr.convert('RGB')) for fr in ImageSequence.Iterator(im)]
out = [retheme(fr, theme) for fr in frames]
uniq = np.unique(np.concatenate([o.reshape(-1, 3) for o in out]), axis=0)
if len(uniq) > 256:
    sys.exit(f'{len(uniq)} colours after recolouring; GIF palettes hold 256')
pal = Image.new('P', (1, 1))
pal.putpalette(list(uniq.flatten()) + [0] * (768 - uniq.size))
imgs = [Image.fromarray(o).quantize(palette=pal, dither=Image.Dither.NONE) for o in out]
imgs[0].save(dst, save_all=True, append_images=imgs[1:], loop=0, duration=duration, optimize=False, disposal=1)
print(f'{dst}: {len(out)} frames, {len(uniq)} colours')
