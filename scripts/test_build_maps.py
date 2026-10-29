import json
import tempfile
import unittest
from pathlib import Path

import build_area_maps as areas
import build_vault_map as vault_map


def write(root: Path, relative: str, text: str = "\n") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class MapTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        write(self.root, "Wiki/Wiki Hub.md")
        write(self.root, "Wiki/Cooking/Bread.md")
        write(self.root, "Wiki/Cooking/Soup.md")
        write(self.root, "Wiki/Wiki.base")
        write(self.root, "Projects/Garden/Garden.md", "---\ntype: project\nstatus: 🟢 Active\ntitle: Garden\n---\n")
        write(self.root, "Projects/Shed/Shed.md", "---\ntype: project\nstatus: 💡 Idea\n---\n")
        write(self.root, "Media/Banners/wiki-hub.gif", "gif")
        write(self.root, ".obsidian/ignored.md")

    def test_master_map_has_one_card_per_visible_folder(self):
        canvas = vault_map.build(self.root)
        titles = sorted(n["text"].split("\n")[0].replace("![[Media/Banners/wiki-hub.gif]]", "wiki") for n in canvas.nodes)
        self.assertEqual(len(canvas.nodes), 3)  # Media, Projects, Wiki
        self.assertEqual(vault_map.check(self.root, canvas), [])
        wiki = next(n for n in canvas.nodes if "## Wiki" in n["text"])
        self.assertIn("![[Media/Banners/wiki-hub.gif]]", wiki["text"])
        self.assertIn("`Cooking/` · 2", wiki["text"])
        self.assertNotIn("obsidian", " ".join(titles).lower())

    def test_projects_grouped_by_status_in_order(self):
        lines = vault_map.projects_by_status(self.root, "Projects", vault_map.STATUS_ORDER)
        self.assertEqual(len(lines), 2)
        self.assertIn("Active", lines[0])
        self.assertIn("[[Projects/Garden/Garden|Garden]]", lines[0])
        self.assertIn("Idea", lines[1])

    def test_build_is_deterministic_and_non_overlapping(self):
        a = json.dumps(vault_map.build(self.root).nodes)
        b = json.dumps(vault_map.build(self.root).nodes)
        self.assertEqual(a, b)

    def test_broken_link_is_reported(self):
        canvas = vault_map.Canvas()
        canvas.text("x", 0, 0, 300, "[[Missing Note]]")
        self.assertEqual(vault_map.check(self.root, canvas), ["unresolved link [[Missing Note]]"])

    def test_area_map_has_header_cards_and_edges(self):
        canvas = areas.build_area(self.root, self.root / "Wiki", "Media/Banners")
        self.assertEqual(len(canvas.nodes), 2)  # header + Cooking
        self.assertEqual(len(canvas.edges), 1)
        self.assertEqual(areas.check(self.root, canvas), [])
        self.assertIn("Views: [[Wiki/Wiki.base|Wiki]]", canvas.nodes[0]["text"])

    def test_write_creates_canvas_and_master_links_to_it(self):
        canvas = areas.build_area(self.root, self.root / "Wiki", "Media/Banners")
        vault_map.write_canvas(self.root / "Wiki/Wiki Map.canvas", canvas)
        data = json.loads((self.root / "Wiki/Wiki Map.canvas").read_text(encoding="utf-8"))
        self.assertEqual(len(data["nodes"]), 2)
        master = vault_map.build(self.root)
        wiki = next(n for n in master.nodes if "## Wiki" in n["text"])
        self.assertIn("[[Wiki/Wiki Map.canvas|Area map]]", wiki["text"])
        self.assertEqual(vault_map.check(self.root, master), [])


if __name__ == "__main__":
    unittest.main()
