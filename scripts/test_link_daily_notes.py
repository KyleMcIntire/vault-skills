import tempfile
import unittest
from pathlib import Path

import link_daily_notes as daily

TEMPLATE_STYLE = """---
date: 2026-10-02
type: Daily Note
tags:
  - Journal
---

# Day

### Habits

- [ ] Dishes

---

## :TwCheckMarkButton: Done

```tasks
done today
```
"""


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


class DailyLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def apply(self):
        changes, bulk = daily.plan(self.root, bulk_limit=2)
        for relative, (_, new) in changes.items():
            (self.root / relative).write_bytes(new.encode("utf-8"))
        return changes, bulk

    def read(self, relative):
        return (self.root / relative).read_bytes().decode("utf-8")

    def test_chains_neighbours_across_folders_and_gaps(self):
        write(self.root, "Daily Notes/Past/2024/2024-12-01.md", "---\ndate: 2024-12-01\n---\n")
        write(self.root, "Daily Notes/2026/10 October/2026-10-02.md", TEMPLATE_STYLE)
        write(self.root, "Daily Notes/2026-10-05.md", "---\ndate: 2026-10-05\nprev:\nnext:\n---\n")
        write(self.root, "Daily Notes/2026-10-05 1.md", "---\n---\n")
        self.apply()
        middle = self.read("Daily Notes/2026/10 October/2026-10-02.md")
        self.assertIn('date: 2026-10-02\nprev: "[[2024-12-01]]"\nnext: "[[2026-10-05]]"\ntype: Daily Note', middle)
        self.assertIn('prev: "[[2026-10-02]]"\nnext:\n', self.read("Daily Notes/2026-10-05.md"))
        self.assertEqual(self.read("Daily Notes/2026-10-05 1.md"), "---\n---\n")

    def test_related_by_filename_and_creation_date_before_done(self):
        write(self.root, "Daily Notes/2026-10-02.md", TEMPLATE_STYLE)
        write(self.root, "People/2026-10-02 Call with Sam.md", "x\n")
        write(self.root, "Wiki/Topic.md", '---\ncreation date: "2026-10-02T10:00"\n---\n')
        write(self.root, "Templates/2026-10-02 Template.md", "x\n")
        write(self.root, "Local/2026-10-02 Scratch.md", "x\n")
        self.apply()
        text = self.read("Daily Notes/2026-10-02.md")
        self.assertIn(
            "- [ ] Dishes\n\n## :TwLink: Related\n\n<!-- related-notes -->\n"
            "- [[2026-10-02 Call with Sam]]\n- [[Topic]]\n<!-- /related-notes -->\n\n---\n\n## :TwCheckMarkButton: Done",
            text,
        )
        self.assertNotIn("Template", text)
        self.assertNotIn("Scratch", text)

    def test_bulk_creation_dates_skipped_but_filenames_kept(self):
        write(self.root, "Daily Notes/2026-10-17.md", "---\ndate: 2026-10-17\n---\n")
        for name in ("A", "B", "C"):
            write(self.root, f"Wiki/Games/{name}.md", "---\ncreation date: 2026-10-17\n---\n")
        write(self.root, "Wiki/2026-10-17 Notes.md", "x\n")
        _, bulk = self.apply()
        self.assertEqual(bulk, {"2026-10-17": 3})
        text = self.read("Daily Notes/2026-10-17.md")
        self.assertIn("- [[2026-10-17 Notes]]\n", text)
        self.assertNotIn("[[A]]", text)

    def test_ambiguous_names_use_paths_and_rerun_is_a_no_op(self):
        write(self.root, "Daily Notes/2026-10-02.md", "---\r\ndate: 2026-10-02\r\n---\r\n\r\nBody\r\n")
        write(self.root, "Wiki/2026-10-02 Plan.md", "x\n")
        write(self.root, "Projects/2026-10-02 Plan.md", "x\n")
        self.apply()
        text = self.read("Daily Notes/2026-10-02.md")
        self.assertIn("- [[Projects/2026-10-02 Plan|2026-10-02 Plan]]\r\n", text)
        self.assertNotIn("\n\n", text.replace("\r\n", "\r"))  # no stray LF-only lines
        self.assertTrue(text.endswith("<!-- /related-notes -->\r\n"))
        changes, _ = daily.plan(self.root, bulk_limit=2)
        self.assertEqual(changes, {})

    def test_custom_daily_folder_and_skip(self):
        write(self.root, "Journal/2026-10-02.md", "---\ndate: 2026-10-02\n---\n")
        write(self.root, "Wiki/2026-10-02 Keep.md", "x\n")
        write(self.root, "Work/2026-10-02 Private.md", "x\n")
        changes, _ = daily.plan(self.root, daily_folder="Journal", skip=("Work/",))
        text = changes["Journal/2026-10-02.md"][1]
        self.assertIn("[[2026-10-02 Keep]]", text)
        self.assertNotIn("Private", text)

    def test_sync_previews_then_writes(self):
        write(self.root, "Daily Notes/2026-10-01.md", "---\ndate: 2026-10-01\n---\n")
        write(self.root, "Daily Notes/2026-10-02.md", "---\ndate: 2026-10-02\n---\n")
        self.assertEqual(daily.sync(self.root, write=False), 2)
        self.assertNotIn("prev", self.read("Daily Notes/2026-10-02.md"))
        self.assertEqual(daily.sync(self.root, write=True), 2)
        self.assertIn('prev: "[[2026-10-01]]"', self.read("Daily Notes/2026-10-02.md"))
        self.assertEqual(daily.sync(self.root, write=True), 0)
        self.assertEqual(sorted(p.name for p in (self.root / "Daily Notes").iterdir()), ["2026-10-01.md", "2026-10-02.md"])

    def test_existing_block_is_replaced_and_user_text_kept(self):
        write(
            self.root,
            "Daily Notes/2026-10-02.md",
            "---\ndate: 2026-10-02\n---\n\n## :TwLink: Related\n\nMy note\n<!-- related-notes -->\n- [[Old]]\n<!-- /related-notes -->\n",
        )
        write(self.root, "Wiki/2026-10-02 New.md", "x\n")
        self.apply()
        text = self.read("Daily Notes/2026-10-02.md")
        self.assertIn("My note\n<!-- related-notes -->\n- [[2026-10-02 New]]\n<!-- /related-notes -->", text)
        self.assertNotIn("[[Old]]", text)


if __name__ == "__main__":
    unittest.main()
