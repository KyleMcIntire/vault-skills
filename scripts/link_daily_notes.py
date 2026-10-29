#!/usr/bin/env python3
"""Chain daily notes and link each one to the notes from its day.

For every `YYYY-MM-DD.md` under the daily folder (default `Daily Notes/`), sets the `prev` and `next`
frontmatter properties to the nearest existing daily notes, and keeps a
generated **Related** section listing the notes from that day: notes whose
filename starts with the date, or whose `creation date` is the date. A day
with more than --bulk-limit `creation date` matches is treated as a bulk
import and only its filename matches count. Templates, archives, scratch
folders, and any --skip folders are never listed.

Previews unless given --write. Safe to run repeatedly: notes already up to
date are left alone, and only the properties and the text between the
related-notes markers are rewritten.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from check_vault import add_vault_arguments, apply_vault_arguments, file_index, normalized, vault_files


DAILY_FOLDER = "Daily Notes/"
DAILY_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
DATED_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})(?!\d)")
CREATION_DATE = re.compile(r"""^creation date:\s*["']?(\d{4}-\d{2}-\d{2})""", re.MULTILINE)
# Never listed as related: templates, archives, and machine-local scratch.
# The daily folder itself is always skipped. Add more with --skip.
SKIPPED_PREFIXES = ("Archive/", "Templates/", "Local/")
BULK_LIMIT = 20
START = "<!-- related-notes -->"
END = "<!-- /related-notes -->"
HEADING = "## :TwLink: Related"
DONE_HEADING = re.compile(r"^## .*Done\s*$")


def daily_notes(root: Path, files: list[Path], daily_folder: str = DAILY_FOLDER) -> dict[str, str]:
    """Map each date to its daily note's vault-relative path."""
    notes: dict[str, str] = {}
    for path in files:
        relative = path.relative_to(root).as_posix()
        match = DAILY_NAME.match(path.name)
        if match and relative.startswith(daily_folder):
            notes[match.group(1)] = relative
    return notes


def frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[:end] if end != -1 else ""


def related_notes(
    root: Path, files: list[Path], bulk_limit: int, skipped: tuple[str, ...] = SKIPPED_PREFIXES
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Return date -> related note paths, and the bulk-import dates skipped."""
    by_name: dict[str, set[str]] = defaultdict(set)
    by_created: dict[str, set[str]] = defaultdict(set)
    for path in files:
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() != ".md" or relative.startswith(".") or relative.startswith(skipped):
            continue
        if match := DATED_NAME.match(path.name):
            by_name[match.group(1)].add(relative)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if match := CREATION_DATE.search(frontmatter(text)):
            by_created[match.group(1)].add(relative)

    bulk = {day: len(notes) for day, notes in by_created.items() if len(notes) > bulk_limit}
    related: dict[str, list[str]] = {}
    for day in by_name.keys() | by_created.keys():
        notes = set(by_name.get(day, ()))
        if day not in bulk:
            notes |= by_created.get(day, set())
        related[day] = sorted(notes)
    return related, bulk


def wikilink(relative: str, names: dict[str, list[str]]) -> str:
    stem = Path(relative).stem
    if len(names.get(normalized(stem), [])) == 1:
        return f"[[{stem}]]"
    return f"[[{relative[:-3]}|{stem}]]"


def set_property(lines: list[str], key: str, value: str) -> list[str]:
    """Set a scalar frontmatter property, adding it after `date:` if missing."""
    try:
        end = lines.index("---", 1)
    except ValueError:
        return lines
    line = f"{key}: {value}" if value else f"{key}:"
    pattern = re.compile(rf"^{re.escape(key)}:(\s|$)")
    for index in range(1, end):
        if pattern.match(lines[index]):
            return lines[:index] + [line] + lines[index + 1 :]
    # prev goes after date, next after prev, so the pair stays together.
    after = ("prev:", "date:") if key == "next" else ("date:",)
    position = end
    for prefix in after:
        found = next((index for index in range(1, end) if lines[index].startswith(prefix)), None)
        if found is not None:
            position = found + 1
            break
    return lines[:position] + [line] + lines[position:]


def set_related(lines: list[str], links: list[str]) -> list[str]:
    """Rewrite the generated block, adding the section only when there is something to list."""
    body = [f"- {link}" for link in links]
    if START in lines and END in lines:
        start, end = lines.index(START), lines.index(END)
        return lines[: start + 1] + body + lines[end:]
    if not links:
        return lines
    section = [HEADING, "", START, *body, END, ""]
    done = next((index for index, line in enumerate(lines) if DONE_HEADING.match(line)), None)
    if done is None:
        tail = lines[:]
        while tail and not tail[-1].strip():
            tail.pop()
        return tail + [""] + section[:-1]
    if done >= 2 and lines[done - 1] == "" and lines[done - 2] == "---":
        done -= 2
    return lines[:done] + section + lines[done:]


def updated_note(text: str, prev: str, next_: str, links: list[str]) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    trailing = text.endswith(("\n", "\r\n"))
    lines = text.splitlines()
    lines = set_property(lines, "prev", prev)
    lines = set_property(lines, "next", next_)
    lines = set_related(lines, links)
    return newline.join(lines) + (newline if trailing or not text else "")


def plan(
    root: Path,
    bulk_limit: int = BULK_LIMIT,
    daily_folder: str = DAILY_FOLDER,
    skip: tuple[str, ...] = (),
) -> tuple[dict[str, tuple[str, str]], dict[str, int]]:
    """Return path -> (old text, new text) for every daily note that would change."""
    daily_folder = daily_folder.rstrip("/") + "/"
    files = vault_files(root)
    _, names = file_index(root, files)
    notes = daily_notes(root, files, daily_folder)
    related, bulk = related_notes(root, files, bulk_limit, (daily_folder, *SKIPPED_PREFIXES, *skip))
    days = sorted(notes)
    changes: dict[str, tuple[str, str]] = {}
    for index, day in enumerate(days):
        relative = notes[day]
        text = (root / relative).read_bytes().decode("utf-8")
        prev = f'"[[{days[index - 1]}]]"' if index else ""
        next_ = f'"[[{days[index + 1]}]]"' if index + 1 < len(days) else ""
        links = [wikilink(note, names) for note in related.get(day, [])]
        new = updated_note(text, prev, next_, links)
        if new != text:
            changes[relative] = (text, new)
    return changes, bulk


def write_atomic(path: Path, text: str) -> None:
    # Replace in one step so Obsidian never reads a half-written note.
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(text.encode("utf-8"))
    os.replace(temporary, path)


def sync(root: Path, write: bool, bulk_limit: int = BULK_LIMIT, daily_folder: str = DAILY_FOLDER) -> int:
    """Apply (or with write=False, count) the changes; handy for calling from another script."""
    changes, _ = plan(root, bulk_limit, daily_folder)
    if write:
        for relative, (_, new) in changes.items():
            write_atomic(root / relative, new)
    return len(changes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_vault_arguments(parser)
    parser.add_argument("--daily-folder", default=DAILY_FOLDER, help=f"vault-relative daily notes folder (default: {DAILY_FOLDER})")
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        metavar="PREFIX",
        help="vault-relative folder prefix never listed as related, e.g. Work/ (repeatable)",
    )
    parser.add_argument("--write", action="store_true", help="write the changes (default: preview)")
    parser.add_argument(
        "--bulk-limit",
        type=int,
        default=BULK_LIMIT,
        help=f"ignore `creation date` on days with more notes than this (default: {BULK_LIMIT})",
    )
    parser.add_argument("--show", type=int, default=3, help="notes to print in full in a preview (default: 3)")
    args = parser.parse_args()

    root = apply_vault_arguments(args)
    changes, bulk = plan(root, args.bulk_limit, args.daily_folder, tuple(args.skip))
    for day, count in sorted(bulk.items()):
        print(f"Skipped `creation date` on {day}: {count} notes, likely a bulk import.")
    if args.write:
        for relative, (_, new) in changes.items():
            write_atomic(root / relative, new)
        print(f"Updated {len(changes)} daily note(s).")
        return 0

    for relative in list(changes)[-args.show :]:
        print(f"\n=== {relative}")
        print(changes[relative][1])
    with_related = sum(START in new and START not in old for old, new in changes.values())
    print(f"\nWould update {len(changes)} daily note(s); {with_related} gain a Related section. Run with --write to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
