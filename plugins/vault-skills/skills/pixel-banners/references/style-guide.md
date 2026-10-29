# Pixel banner style guide

These rules describe the hub and daily-note GIFs that the engine in `scripts/banners/` produces. Match them so a new banner reads as part of the same set.

## Format

- Canvas: 360x60 logical pixels, scaled 5x with nearest-neighbour to **1800x300**.
- Loop: **72 frames at 90 ms** (6.48 s) by default. Existing scenes also use 48, 64, and 96 frames. Every frame uses one shared palette with no dithering at encode time. Keep the palette well under 256 colours (scenes land at 50–80) and the file around 0.4–1.2 MB.
- Flat colour pixel art: hard edges, 1-px details, and no gradients beyond a few `bands()` or a `mix()` stepped in quarters. Avoid anti-aliasing, painterly texture, or photo sources.

## Crop safety

Pixel Banner shows these at `banner-height: 200` with `content-start: 101`, using object-fit cover across panes 800–1900 px wide (the vault default is `banner-x: 50`, `banner-y: 50`).

- **Horizontal:** at an 800 px pane only logical **x 60–300** is visible. Keep the label and the main motion inside that band. The outer 60 px on each side are decoration.
- **Vertical:** wider panes crop more of the top: 0 rows at 800–1100 px, 6 at 1500 px, and **11 at 1900 px**. At every width, note content starts at about final row **30** and covers the rows below. The clear band for the label and hero motion is therefore final rows **11–30**.
- `canvas(bg, shift=7)` pushes every draw call down 7 rows, so drawing y = final row − 7, and the canvas spans drawing y −7..52. The clear band is drawing **y 4–23**: a label plate at `y=4` sits at final rows 11–27. The desk or floor starts at drawing y 42 and sits behind the note title, which is fine for props.
- Always review `crops.png`. It simulates 800, 1100, 1500, and 1900 px panes and darkens the area where note content starts.

## Composition

Most scenes are a cosy night-time room, seen straight-on:

| Zone | Drawing y | Typical content |
| --- | --- | --- |
| Wall | −7..41 | `wall(c, stripe)` vertical stripes, or tiles or blocks; navy `#1b1f33` / stripes `#20253d` |
| Left decor | x 0–60 | Shelf, bookcase, garage door: anything that can be cropped |
| Label | x 60–150, y 4–20 | `label(c, 'TEXT', fg, shadow, plate, edge, x, y)`, a 2x pixel-font plate |
| Centrepiece | x 90–270 | The thing that says what the hub is: a map board, stove, car, calendar |
| Window | x 284–342, y 2–30 | `window_box` + night sky `twinkle` + `moon` + `city` or `mountains` + `frame_window` |
| Desk or counter | y 42+ | `desk(c)` (`#7a5236` top, `#5a3e2b` body, grain lines) plus small props |

Recurring props tie the set together: a steaming mug (`steam()`), a plant on the sill, a lantern or desk lamp with a dithered light pool, books, and a moon with a twinkling sky.

### Palette

| Role | Colours |
| --- | --- |
| Wall | `#1b1f33` bg, `#20253d` stripes, `#2e3450` frames |
| Night sky | `#141a33` glass, stars `#26305a` / `#6a74a8` / `#eef0ff`, moon `#f4f0d8`, buildings `#262b45`, lit windows `#e0af68` |
| Dusk | bands `#1e1d3d` `#2d2650` `#45305e` `#6a3d63`, ridges `#4b4a85` / `#2c3060` |
| Wood | `#7a5236` light, `#6b4a33` shelf, `#5a3e2b` body, `#4f3624` grain, `#3a2a22` dark |
| Paper and metal | `#e6e9ef` `#f2e6b8` `#faf2db`, steel `#9aa3b5` `#5c6380` `#3b4261` |
| Accents | `#7aa2f7` blue, `#bb9af7` violet, `#9ece6a` green, `#f7768e` pink, `#e0af68` amber, `#73daca` teal, `#e05561` red |

Labels take an accent-tinted plate with a dark foreground, e.g. `label(c, 'RECIPES', '#6b2f3a', '#e8b8b0', '#f9e6dc', '#d49a8e')`.

## Animation

- Each scene is a function `scene(f, n)` that returns `c.a`. Derive all motion from `t = f / n`, using whole-number frequencies (`sin(TAU * t * k)`, `drift(...)`, `(f // k) % m`) so frame `n` equals frame 0 and the loop is seamless.
- Aim for one clear hero motion, plus two to four small ambient ones. Hero examples: pins dropping in sequence, a stamp pressing, a calendar's "today" box walking, a plane crossing. Ambient examples: twinkling stars, steam, a flickering flame, a swaying lamp, blinking lights.
- Sequences that build up must reset before the loop ends, e.g. visible while `t < 0.94`. Stagger step starts with `land = [0.06 + i * 0.15 ...]` and use `ease()` for drops and slides.
- Keep motion readable at 5x: about 1–8 px of travel per cycle, blinks on 3–6 frame periods, and nothing strobing.

## Engine API (`pix.py` + `thin_common.py`)

`Cv` methods: `px`, `rect`, `rrect` (rounded), `outline`, `disc`, `ellipse(..., dither=False)`, `dither`, `line`, `text` (3x5 font), and `sparkle`.

`thin_common` helpers:

| Helper | What it draws |
| --- | --- |
| `canvas(bg, shift=7)` | New canvas |
| `bands(c, y0, y1, colours, x0, x1)` | Stepped gradient |
| `label(...)`, `big_text(...)`, `text_width(s)` | 2x label plate and text |
| `twinkle`, `drift`, `steam`, `bird`, `cloud`, `ridge` | Ambient motion |
| `wall`, `desk`, `window_box`, `frame_window`, `moon`, `city`, `mountains` | Room shell and windows |
| `books(c, x, y, [(w, h, colour), ...])`, `pin`, `lantern` | Props |

The font covers A–Z, `0`, `1`, and some punctuation. Wide `M` and `W` come from `thin_common.WIDE`. Add glyphs to `pix.FONT` before using other digits or symbols, and check the result.

## Scene skeleton

```python
# scripts/banners/<module>.py
"""Thin (360x60) banners for <group>."""
import math
import random
from thin_common import *


# ---------------------------------------------------------------- <Name>: <one-line concept>
def name(f, n):
    t = f / n
    c = canvas('#1b1f33', shift=7)
    wall(c, '#20253d')
    # left decor (croppable), x 0-60
    label(c, 'NAME', '#2b3150', '#9aa3b5', '#e6e9ef', '#8b93a7', x=66, y=4)
    # centrepiece + hero motion, x 90-270
    wx, wy, ww, wh = 288, 2, 54, 28
    window_box(c, wx, wy, ww, wh)
    twinkle(c, 14, 14, wx, wy, ww, 14, t, ['#26305a', '#6a74a8', '#eef0ff'])
    moon(c, wx + 40, wy + 8)
    city(c, t, wx, wy, ww, wh, 41, 6, 14)
    frame_window(c, wx, wy, ww, wh)
    desk(c)
    # desk props + ambient motion
    return c.a


SCENES = {
    'name': (name, 72),
}
```

Draw back to front, because later calls overwrite earlier ones: put glows before the flame they surround, and the desk before props that sit on it.
