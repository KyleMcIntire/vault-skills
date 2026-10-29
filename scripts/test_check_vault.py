import tempfile
import unittest
import zipfile
from pathlib import Path

import check_vault


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class UnknownIconTests(unittest.TestCase):
    def make_vault(self, note: str, relative: str = "Note.md") -> tuple[Path, list[Path]]:
        root = Path(self._tmp.name)
        icons = root / ".obsidian" / "icons"
        (icons / "twemoji").mkdir(parents=True, exist_ok=True)
        (icons / "twemoji" / "Calendar.svg").write_text("<svg/>")
        with zipfile.ZipFile(icons / "twemoji.zip", "w") as zf:
            zf.writestr("twemoji/TearOffCalendar.svg", "<svg/>")
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(note, encoding="utf-8")
        return root, [path]

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_flags_unknown_and_accepts_folder_and_zip_icons(self):
        root, files = self.make_vault(
            "## :TwCalendar: ok\n## :TwTearOffCalendar: ok\n## :TwCalendarDots: bad\n"
        )
        self.assertEqual(
            check_vault.unknown_icons(root, files),
            ["Note.md: unknown icon :TwCalendarDots:"],
        )

    def test_ignores_code_and_unchecked_prefixes_and_worktrees(self):
        root, files = self.make_vault("`:TwNope:` and :FasWhatever: here\n")
        self.assertEqual(check_vault.unknown_icons(root, files), [])
        root, files = self.make_vault(":TwNope:\n", ".claude/worktrees/x.md")
        self.assertEqual(check_vault.unknown_icons(root, files), [])

    def test_checks_icon_property(self):
        root, files = self.make_vault("---\nicon: TwNope\n---\n")
        self.assertEqual(check_vault.unknown_icons(root, files), ["Note.md: unknown icon :TwNope:"])

    def test_no_packs_installed_means_no_warnings(self):
        root = Path(self._tmp.name)
        note = root / "Note.md"
        note.write_text(":TwNope:\n", encoding="utf-8")
        self.assertEqual(check_vault.unknown_icons(root, [note]), [])

    def test_custom_pack_is_checked(self):
        root, files = self.make_vault(":XxStar: :XxMoon:\n")
        pack = root / ".obsidian" / "icons" / "extras"
        pack.mkdir()
        (pack / "Star.svg").write_text("<svg/>")
        packs = {"Xx": ("extras", None, False)}
        self.assertEqual(check_vault.unknown_icons(root, files, packs), ["Note.md: unknown icon :XxMoon:"])


class StructureTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_frontmatter_and_fence_problems(self):
        open_fm = write(self.root, "A.md", "---\ntitle: x\n\nBody\n")
        fence = write(self.root, "B.md", "text\n```python\nprint(1)\n")
        fine = write(self.root, "C.md", "---\ntitle: x\n---\n```\ncode\n```\n")
        self.assertIn("without a closing", check_vault.frontmatter_error(open_fm))
        self.assertIn("unclosed ``` fence opened on line 2", check_vault.unclosed_fence(fence))
        self.assertIsNone(check_vault.frontmatter_error(fine))
        self.assertIsNone(check_vault.unclosed_fence(fine))

    def test_invalid_utf8_is_reported(self):
        path = self.root / "Bad.md"
        path.write_bytes(b"\xff\xfe\x00bad")
        self.assertEqual(check_vault.frontmatter_error(path), "is not valid UTF-8")

    def test_link_resolution_forms(self):
        write(self.root, "Wiki/Topic.md", "\n")
        write(self.root, "Projects/Plan.base", "\n")
        note = write(
            self.root,
            "Home.md",
            "[[Topic]] [[Wiki/Topic#Heading]] [[Topic|alias]] [[Topic\\|table alias]] ![[Plan.base#View]] "
            "[[Nowhere]] `[[InCode]]`\n```\n[[InFence]]\n```\n",
        )
        files = check_vault.vault_files(self.root)
        paths, names = check_vault.file_index(self.root, files)
        warnings = check_vault.unresolved_links(self.root, [note], paths, names)
        self.assertEqual(warnings, ["Home.md: unresolved wiki-link [[Nowhere]]"])

    def test_machine_local_links_are_ignored(self):
        note = write(self.root, "Home.md", "[[Local/Scratch]]\n")
        files = check_vault.vault_files(self.root)
        paths, names = check_vault.file_index(self.root, files)
        self.assertEqual(check_vault.unresolved_links(self.root, [note], paths, names), [])

    def test_excluded_directories_and_extra_excludes(self):
        write(self.root, ".obsidian/x.md", "\n")
        write(self.root, "node_modules/y.md", "\n")
        write(self.root, "Keep.md", "\n")
        write(self.root, "Build/z.md", "\n")
        names = lambda: [p.name for p in check_vault.vault_files(self.root)]
        self.assertEqual(sorted(names()), ["Keep.md", "z.md"])
        check_vault.EXCLUDED_DIRECTORIES.add("Build")
        self.addCleanup(check_vault.EXCLUDED_DIRECTORIES.discard, "Build")
        self.assertEqual(names(), ["Keep.md"])


class RootDiscoveryTests(unittest.TestCase):
    def test_explicit_path_wins_then_env_then_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / ".obsidian").mkdir()
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            self.assertEqual(check_vault.find_vault_root(str(root)), root)
            import os
            old, cwd = os.environ.pop("VAULT_ROOT", None), os.getcwd()
            try:
                os.chdir(nested)
                self.assertEqual(check_vault.find_vault_root(), root)
                os.environ["VAULT_ROOT"] = str(nested)
                self.assertEqual(check_vault.find_vault_root(), nested)
            finally:
                os.chdir(cwd)
                os.environ.pop("VAULT_ROOT", None)
                if old is not None:
                    os.environ["VAULT_ROOT"] = old


if __name__ == "__main__":
    unittest.main()
