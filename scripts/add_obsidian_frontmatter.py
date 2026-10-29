#!/usr/bin/env python3
"""Add starter YAML frontmatter to Markdown notes that have none.

Previews by default: nothing is written unless you pass --write. Notes that
already open with a frontmatter block are never touched, and a write only
prepends a block, so the body of a note is preserved byte for byte.

The block holds `creation date` (the file's creation date), `title` (the file
name), `type` (from the top-level folder, or --type FOLDER=Type), and `tags`
(the top-level folder name unless --no-tags). Fill in a better `type` and tags
afterwards; the point is that every note is a record with a type.

Examples:
    python add_obsidian_frontmatter.py --vault ~/Vault
    python add_obsidian_frontmatter.py --vault ~/Vault --type Wiki=Reference --write
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from check_vault import add_vault_arguments, apply_vault_arguments, vault_files

# Folder name -> default `type`. Unlisted folders use their own name; root notes use "Note".
FOLDER_TYPES = {
    "Daily Notes": "Daily Note",
    "Templates": "Template",
    "Wiki": "Wiki",
    "Projects": "project",
    "Meetings": "meeting",
    "Tasks": "task",
    "People": "person",
}


def has_frontmatter(text: str) -> bool:
    """True when the note opens with `---` and a closing `---` or `...` follows."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    return any(line.strip() in {"---", "..."} for line in lines[1:])


def creation_date(path: Path) -> str:
    stat = path.stat()
    stamp = getattr(stat, "st_birthtime", None) or stat.st_ctime
    return datetime.fromtimestamp(stamp).strftime("%Y-%m-%d")


def note_type(relative: Path, types: dict[str, str]) -> str:
    if len(relative.parts) == 1:
        return "Note"
    return types.get(relative.parts[0], relative.parts[0])


def build_frontmatter(title: str, date: str, type_: str, tags: list[str], newline: str = "\n") -> str:
    safe = title.replace('"', "'")
    lines = ["---", f"creation date: {date}", f'title: "{safe}"', f"type: {type_}"]
    if tags:
        lines.append("tags:")
        lines.extend(f"  - {tag}" for tag in tags)
    else:
        lines.append("tags: []")
    lines += ["---", ""]
    return newline.join(lines)


def plan(root: Path, types: dict[str, str], tags: bool = True) -> list[tuple[Path, str]]:
    """Return (path, new text) for every Markdown note that lacks frontmatter."""
    changes: list[tuple[Path, str]] = []
    for path in vault_files(root):
        if path.suffix.lower() != ".md" or path.name.startswith("."):
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        if has_frontmatter(text):
            continue
        relative = path.relative_to(root)
        newline = "\r\n" if "\r\n" in text else "\n"
        folder_tags = [relative.parts[0]] if tags and len(relative.parts) > 1 else []
        block = build_frontmatter(path.stem, creation_date(path), note_type(relative, types), folder_tags, newline)
        changes.append((path, block + text))
    return changes


def write_atomic(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(text.encode("utf-8"))
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_vault_arguments(parser)
    parser.add_argument("--write", action="store_true", help="write the frontmatter (default: preview only)")
    parser.add_argument(
        "--type",
        action="append",
        default=[],
        metavar="FOLDER=Type",
        help="map a top-level folder to a `type` value (repeatable)",
    )
    parser.add_argument("--no-tags", action="store_true", help="leave `tags` empty instead of using the folder name")
    parser.add_argument("--show", type=int, default=10, help="notes to list in a preview (default: 10)")
    args = parser.parse_args()

    root = apply_vault_arguments(args)
    types = dict(FOLDER_TYPES)
    for spec in args.type:
        folder, sep, value = spec.partition("=")
        if not sep or not value:
            parser.error(f"--type expects FOLDER=Type, got {spec!r}")
        types[folder] = value

    changes = plan(root, types, tags=not args.no_tags)
    if args.write:
        for path, text in changes:
            write_atomic(path, text)
        print(f"Added frontmatter to {len(changes)} note(s).")
        return 0
    for path, text in changes[: args.show]:
        print(f"would add to {path.relative_to(root).as_posix()}:")
        print("  " + text.split("\n---\n", 1)[0].replace("\n", "\n  "))
    if len(changes) > args.show:
        print(f"... {len(changes) - args.show} more not shown")
    print(f"Would add frontmatter to {len(changes)} note(s). Run with --write to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
