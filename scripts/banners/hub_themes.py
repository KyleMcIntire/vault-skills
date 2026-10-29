"""Per-hub colour themes for the room-style hub banners.

Most hub banners share one night room: navy wall, brown wood, a navy city outside. In the
Home hub's card view they read as one banner. A theme moves two colour families and leaves
everything else (labels, screens, accents, skin, glows) alone:

- the cool dark family (the wall, shelves' shadows, props, the night sky), and
- the warm brown family (desk, shelves, frames).

Each family keeps its shading: only hue, saturation and value are scaled, so the scene
reads as the same pixel art in a different room. Themes work on frames of any scale, so
they apply both to scene functions (`themed`) and to installed GIFs (`recolor_gif.py`).
"""
import colorsys
import numpy as np

# name: (wall_hue, wall_sat_mul, wall_val_mul, wood_hue, wood_sat_mul, wood_val_mul); hues in degrees
THEMES = {
    'navy':     (230, 1.00, 1.00, 24, 1.00, 1.00),   # the original room
    'emerald':  (152, 1.35, 1.10, 38, 0.80, 1.20),
    'amber':    (36, 1.50, 1.15, 28, 1.00, 0.95),
    'rose':     (345, 1.25, 1.10, 18, 0.90, 1.00),
    'plum':     (300, 1.30, 1.10, 24, 0.75, 1.05),
    'violet':   (268, 1.30, 1.15, 14, 0.90, 1.00),
    'brick':    (8, 1.45, 1.05, 30, 0.85, 1.15),
    'olive':    (96, 1.30, 1.10, 32, 0.85, 1.10),
    'teal':     (178, 1.45, 1.10, 30, 0.70, 1.10),
    'steel':    (205, 0.90, 1.55, 24, 0.55, 1.25),
    'slate':    (215, 0.35, 1.25, 20, 0.45, 1.15),
    'sand':     (48, 0.95, 1.65, 22, 0.70, 1.20),
    'indigo':   (252, 1.45, 1.30, 20, 0.80, 1.00),
    'coral':    (14, 1.10, 1.45, 26, 0.80, 1.20),
    'ocean':    (192, 1.20, 1.35, 30, 0.75, 1.10),
}

_COOL = (185, 280)    # hue range of the night-room family
_WARM = (8, 46)       # hue range of the wood family


def _shift(rgb, theme):
    wall_h, wall_s, wall_v, wood_h, wood_s, wood_v = THEMES[theme]
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    deg = h * 360
    if _COOL[0] <= deg <= _COOL[1] and s >= 0.12 and v <= 0.64:
        nh = (wall_h + (deg - 230) * 0.25) % 360
        s, v = min(1.0, s * wall_s), min(1.0, v * wall_v)
    elif _WARM[0] <= deg <= _WARM[1] and s >= 0.25 and 0.12 <= v <= 0.72:
        nh = (wood_h + (deg - 24) * 0.5) % 360
        s, v = min(1.0, s * wood_s), min(1.0, v * wood_v)
    else:
        return rgb
    return tuple(int(round(c * 255)) for c in colorsys.hsv_to_rgb(nh / 360, s, v))


def retheme(frame, theme):
    """Recolour one (H, W, 3) uint8 frame. Cheap: only the unique colours are converted."""
    if theme == 'navy':
        return frame
    flat = frame.reshape(-1, 3)
    uniq, inv = np.unique(flat, axis=0, return_inverse=True)
    mapped = np.array([_shift(tuple(int(x) for x in u), theme) for u in uniq], np.uint8)
    return mapped[inv.reshape(-1)].reshape(frame.shape)


def themed(fn, theme):
    """Wrap a scene function so every frame it returns is recoloured."""
    def scene(f, n):
        return retheme(fn(f, n), theme)
    return scene
