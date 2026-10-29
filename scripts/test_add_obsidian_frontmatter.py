import tempfile
import unittest
from pathlib import Path

import add_obsidian_frontmatter as fm


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


class FrontmatterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_plan_only_lists_notes_without_frontmatter(self):
        write(self.root, "Wiki/Plain.md", "Body\n")
        write(self.root, "Wiki/Done.md", "---\ntype: Wiki\n---\nBody\n")
        write(self.root, "Root.md", "Top\n")
        changes = {p.relative_to(self.root).as_posix(): t for p, t in fm.plan(self.root, fm.FOLDER_TYPES)}
        self.assertEqual(sorted(changes), ["Root.md", "Wiki/Plain.md"])
        self.assertIn("type: Wiki\ntags:\n  - Wiki\n---\nBody\n", changes["Wiki/Plain.md"])
        self.assertIn("type: Note\ntags: []", changes["Root.md"])
        self.assertIn('title: "Plain"', changes["Wiki/Plain.md"])

    def test_preserves_body_and_line_endings(self):
        write(self.root, "Wiki/Win.md", "Line one\r\nLine two\r\n")
        (_, text), = fm.plan(self.root, fm.FOLDER_TYPES)
        self.assertTrue(text.endswith("---\r\nLine one\r\nLine two\r\n"))
        self.assertNotIn("\n\n", text.replace("\r\n", "\r"))

    def test_custom_type_and_no_tags(self):
        write(self.root, "Notes/A.md", "x\n")
        (_, text), = fm.plan(self.root, {"Notes": "Reference"}, tags=False)
        self.assertIn("type: Reference\ntags: []", text)

    def test_unclosed_block_counts_as_no_frontmatter(self):
        self.assertFalse(fm.has_frontmatter("---\ntitle: x\nno close\n"))
        self.assertTrue(fm.has_frontmatter("---\ntitle: x\n---\n"))

    def test_hidden_and_excluded_folders_skipped(self):
        write(self.root, ".obsidian/templates.md", "x\n")
        write(self.root, ".hidden.md", "x\n")
        self.assertEqual(fm.plan(self.root, fm.FOLDER_TYPES), [])


if __name__ == "__main__":
    unittest.main()
