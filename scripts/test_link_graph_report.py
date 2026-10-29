import tempfile
import unittest
from pathlib import Path

import link_graph_report as report


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class LinkGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_counts_links_by_name_path_alias_and_embed(self):
        write(self.root, "Home.md", "[[Alpha]] and [[Wiki/Beta|the beta]] and ![[Gamma#Part]]\n")
        write(self.root, "Wiki/Alpha.md", "back to [[Home]]\n")
        write(self.root, "Wiki/Beta.md", "nothing\n")
        write(self.root, "Wiki/Gamma.md", "nothing\n")
        graph = report.link_graph(self.root)
        self.assertEqual(graph["outbound"]["Home.md"], {"Wiki/Alpha.md", "Wiki/Beta.md", "Wiki/Gamma.md"})
        self.assertEqual(graph["inbound"]["Home.md"], {"Wiki/Alpha.md"})

    def test_ignores_code_self_links_unresolved_and_non_notes(self):
        write(self.root, "A.md", "`[[B]]`\n```\n[[B]]\n```\n[[A]] [[Missing]] ![[pic.png]]\n")
        write(self.root, "B.md", "\n")
        write(self.root, "pic.png", "")
        graph = report.link_graph(self.root)
        self.assertEqual(graph["outbound"]["A.md"], set())
        self.assertEqual(graph["inbound"]["B.md"], set())

    def test_frontmatter_links_count(self):
        write(self.root, "Task.md", '---\nparent project: "[[Hub]]"\n---\n')
        write(self.root, "Hub.md", "\n")
        self.assertEqual(report.link_graph(self.root)["inbound"]["Hub.md"], {"Task.md"})

    def test_generated_and_hidden_notes_skipped_unless_asked(self):
        write(self.root, "Imports/Session.md", "[[Hub]]\n")
        write(self.root, ".hidden/Prompt.md", "[[Hub]]\n")
        write(self.root, "Hub.md", "\n")
        report.GENERATED_PREFIXES = ("Imports/",)
        self.addCleanup(setattr, report, "GENERATED_PREFIXES", ())
        self.assertEqual(report.link_graph(self.root)["inbound"]["Hub.md"], set())
        graph = report.link_graph(self.root, include_generated=True)
        self.assertEqual(graph["inbound"]["Hub.md"], {"Imports/Session.md"})

    def test_relative_link_resolves_from_source_folder(self):
        write(self.root, "Projects/X/Note.md", "[[Sub/Child]]\n")
        write(self.root, "Projects/X/Sub/Child.md", "\n")
        graph = report.link_graph(self.root)
        self.assertEqual(graph["outbound"]["Projects/X/Note.md"], {"Projects/X/Sub/Child.md"})

    def test_area_report_and_split_areas(self):
        report.SPLIT_AREAS.add("Archive")
        self.addCleanup(report.SPLIT_AREAS.discard, "Archive")
        write(self.root, "Archive/People/Ann.md", "[[Archive/People/Bob]]\n")
        write(self.root, "Archive/People/Bob.md", "\n")
        write(self.root, "Archive/Health/Lab.md", "\n")
        rows = {row["area"]: row for row in report.area_report(report.link_graph(self.root))}
        self.assertEqual(
            rows["Archive/People"],
            {"area": "Archive/People", "notes": 2, "no_inbound": 1, "no_outbound": 1, "isolated": 0, "links_out": 1},
        )
        self.assertEqual(rows["Archive/Health"]["isolated"], 1)
        self.assertEqual(report.area_of("Daily Notes/2026/10 October/2026-10-01.md"), "Daily Notes")
        self.assertEqual(report.area_of("Home.md"), "(root)")

    def test_local_scratch_notes_are_not_counted(self):
        write(self.root, "Local/Scratch.md", "[[Hub]]\n")
        write(self.root, "Hub.md", "\n")
        graph = report.link_graph(self.root)
        self.assertNotIn("Local/Scratch.md", graph["outbound"])
        self.assertEqual(graph["inbound"]["Hub.md"], set())


if __name__ == "__main__":
    unittest.main()
