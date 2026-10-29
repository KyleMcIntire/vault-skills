import json
import sys
import tempfile
import unittest
from pathlib import Path

BANNERS = Path(__file__).resolve().parent / "banners"

try:
    import numpy  # noqa: F401
    import PIL  # noqa: F401
except ImportError:  # the banner engine is the one optional-dependency corner of this repo
    PIL = None

LAYOUTS = json.loads((BANNERS / "note_banner_layouts.json").read_text(encoding="utf-8"))


class LayoutFileTests(unittest.TestCase):
    """These need no imaging libraries, so they always run."""

    def test_layouts_have_required_keys_and_no_private_sources(self):
        required = {"source", "banner-height", "banner-y", "content-start", "scene-shift"}
        for name, layout in LAYOUTS.items():
            self.assertTrue(required <= set(layout), name)
            self.assertTrue(layout["source"].endswith(".md"), name)
            self.assertTrue(0 <= layout["banner-y"] <= 100, name)


@unittest.skipIf(PIL is None, "Pillow and numpy are not installed; skipping banner rendering tests (pip install pillow numpy)")
class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(BANNERS))
        import hub_themes
        import pix
        import render_note_banners
        cls.hub_themes, cls.pix, cls.render = hub_themes, pix, render_note_banners

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(BANNERS))

    def test_every_scene_has_a_layout_and_loops(self):
        self.assertEqual(set(self.render.SCENES), set(LAYOUTS))
        for name, fn in self.render.SCENES.items():
            self.assertEqual(fn(0).tobytes(), fn(1).tobytes(), f"{name} does not loop")
            self.assertEqual(fn(0).size, (self.render.W, self.render.H))

    def test_canvas_primitives_and_gif_writer(self):
        import numpy as np
        from PIL import Image
        cv = self.pix.Cv("#000000", 20, 10)
        cv.rect(2, 2, 4, 4, "#ff0000")
        cv.text(8, 1, "A1", "#00ff00")
        self.assertEqual(tuple(cv.a[3, 3]), (255, 0, 0))
        frames = [cv.a.copy(), np.flip(cv.a, 1).copy()]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.gif"
            colours = self.pix.save_gif(frames, str(path), scale=2)
            self.assertGreaterEqual(colours, 3)
            with Image.open(path) as gif:
                self.assertEqual(gif.size, (40, 20))
                self.assertEqual(gif.n_frames, 2)

    def test_retheme_changes_wall_colours_only(self):
        import numpy as np
        wall = np.array([[[29, 36, 52]]], np.uint8)
        skin = np.array([[[232, 180, 119]]], np.uint8)
        self.assertEqual(self.hub_themes.retheme(wall, "navy").tolist(), wall.tolist())
        self.assertNotEqual(self.hub_themes.retheme(wall, "emerald").tolist(), wall.tolist())
        self.assertEqual(self.hub_themes.retheme(skin, "emerald").tolist(), skin.tolist())

    def test_example_scene_loops(self):
        import example_scenes
        fn, n = example_scenes.SCENES["skyline"]
        self.assertEqual(fn(0, n).tobytes(), fn(n, n).tobytes())


if __name__ == "__main__":
    unittest.main()
