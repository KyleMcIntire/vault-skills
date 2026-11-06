"""Tests for scripts/image_to_svg.py, using the 1x1 tests/pixel.png fixture."""
import base64
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "image_to_svg.py")
PIXEL = os.path.join(HERE, "pixel.png")
spec = importlib.util.spec_from_file_location("image_to_svg", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ImageToSvg(unittest.TestCase):
    def test_png_info_and_svg_roundtrip(self):
        with open(PIXEL, "rb") as fh:
            data = fh.read()
        self.assertEqual(m.image_info(data), ("image/png", 1, 1))
        svg, width, height = m.create_svg(data)
        image = ET.fromstring(svg)[0]
        self.assertEqual((width, height), (1, 1))
        self.assertEqual(base64.b64decode(image.attrib["href"].split(",", 1)[1]), data)

    def test_rejects_unknown_formats(self):
        with self.assertRaises(ValueError):
            m.image_info(b"not an image at all")

    def test_pack_prefix(self):
        self.assertEqual(m.pack_prefix("twemoji"), "Tw")
        self.assertEqual(m.pack_prefix("my-photos"), "Mp")

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", SCRIPT, *args], capture_output=True, text=True)

    def test_cli_dry_run_then_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "my-photos", "Sample.svg")
            dry = self.run_cli("--image", PIXEL, "--pack", "my-photos", "--output", out)
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertEqual(json.loads(dry.stdout)["mode"], "dry-run")
            self.assertFalse(os.path.exists(out))
            wrote = self.run_cli("--image", PIXEL, "--pack", "my-photos", "--output", out, "--write")
            info = json.loads(wrote.stdout)
            self.assertEqual((info["icon_id"], info["mode"]), ("MpSample", "write"))
            self.assertTrue(os.path.exists(out))
            again = json.loads(self.run_cli("--image", PIXEL, "--pack", "my-photos", "--output", out, "--write").stdout)
            self.assertTrue(again["already_identical"])

    def test_cli_rejects_bad_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = self.run_cli("--image", PIXEL, "--pack", "My Pack", "--output", os.path.join(tmp, "x", "Sample.svg"))
            self.assertEqual(bad.returncode, 1)
            wrong_dir = self.run_cli("--image", PIXEL, "--pack", "photos", "--output", os.path.join(tmp, "other", "Sample.svg"))
            self.assertEqual(wrong_dir.returncode, 1)


if __name__ == "__main__":
    unittest.main()
