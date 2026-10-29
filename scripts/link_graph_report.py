#!/usr/bin/env python3
"""Read-only report of wiki-link density per vault area.

Counts, for each area, the notes with no inbound link, no outbound link, or
neither, as a repeatable baseline for linking work. A link is any wiki-link or
embed to another Markdown note, anywhere in the note (frontmatter included),
outside code. Self-links don't count, and neither do Bases, Dataview, or
Canvas views. Link parsing and resolution reuse check_vault.py, so this agrees
with `make check` about what resolves.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import check_vault
from check_vault import (
    WIKI_LINK,
    add_vault_arguments,
    apply_vault_arguments,
    file_index,
    link_target,
    normalized,
    vault_files,
    without_code,
)


# Generated notes (imports, exports) would swamp inbound counts. Pass --generated
# PREFIX to leave a folder out unless --include-generated is given.
GENERATED_PREFIXES: tuple[str, ...] = ()
# Top-level folders broken down one level further (Meetings/Recurring). Set with --split.
SPLIT_AREAS: set[str] = {"Meetings", "Media"}


def area_of(relative: str) -> str:
    parts = relative.split("/")
    if len(parts) == 1:
        return "(root)"
    if parts[0] in SPLIT_AREAS and len(parts) > 2:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


def counted(relative: str, include_generated: bool) -> bool:
    if relative.startswith(".") or relative.startswith(check_vault.MACHINE_LOCAL_PREFIXES):
        return False
    return include_generated or not GENERATED_PREFIXES or not relative.startswith(GENERATED_PREFIXES)


def resolve(
    source: str, target: str, paths: dict[str, list[str]], names: dict[str, list[str]]
) -> str | None:
    """Return the file a link points at, in check_vault.resolves order."""
    key = normalized(target)
    hits = paths.get(key) or names.get(key)
    if not hits:
        parent = Path(source).parent
        for folder in (parent, *parent.parents):
            if str(folder) == ".":
                continue
            if hits := paths.get(normalized((folder / target).as_posix())):
                break
    if not hits and "/" in target:
        suffix = "/" + key
        found = {value for path_key, values in paths.items() if path_key.endswith(suffix) for value in values}
        hits = sorted(found) if len(found) == 1 else None
    if not hits:
        return None
    # Obsidian prefers the shortest path when a bare name is ambiguous.
    return min(hits, key=lambda value: (value.count("/"), value))


def link_graph(root: Path, include_generated: bool = False) -> dict[str, dict[str, set[str]]]:
    """Map each counted note to the notes it links to and the notes linking in."""
    all_files = vault_files(root)
    paths, names = file_index(root, all_files)
    notes = {
        relative
        for path in all_files
        if path.suffix.lower() == ".md"
        and counted(relative := path.relative_to(root).as_posix(), include_generated)
    }
    outbound: dict[str, set[str]] = {note: set() for note in notes}
    inbound: dict[str, set[str]] = {note: set() for note in notes}
    for note in notes:
        try:
            content = (root / note).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in WIKI_LINK.finditer(without_code(content)):
            target = link_target(match.group(1))
            if not target or target.startswith(":"):
                continue
            linked = resolve(note, target, paths, names)
            if linked in notes and linked != note:
                outbound[note].add(linked)
                inbound[linked].add(note)
    return {"outbound": outbound, "inbound": inbound}


def area_report(graph: dict[str, dict[str, set[str]]]) -> list[dict]:
    rows: dict[str, dict] = defaultdict(
        lambda: {"notes": 0, "no_inbound": 0, "no_outbound": 0, "isolated": 0, "links_out": 0}
    )
    for note, targets in graph["outbound"].items():
        row = rows[area_of(note)]
        has_in = bool(graph["inbound"][note])
        row["notes"] += 1
        row["links_out"] += len(targets)
        row["no_inbound"] += not has_in
        row["no_outbound"] += not targets
        row["isolated"] += not has_in and not targets
    return [
        {"area": area, **row}
        for area, row in sorted(rows.items(), key=lambda item: (-item[1]["notes"], item[0]))
    ]


def print_table(rows: list[dict]) -> None:
    total = {key: sum(row[key] for row in rows) for key in ("notes", "no_inbound", "no_outbound", "isolated", "links_out")}
    width = max(len(row["area"]) for row in rows + [{"area": "Total"}])
    print(f"{'Area':<{width}}  {'Notes':>5}  {'No in':>5}  {'No out':>6}  {'Isolated':>8}  {'Links/note':>10}")
    for row in rows + [{"area": "Total", **total}]:
        density = row["links_out"] / row["notes"] if row["notes"] else 0
        print(
            f"{row['area']:<{width}}  {row['notes']:>5}  {row['no_inbound']:>5}  "
            f"{row['no_outbound']:>6}  {row['isolated']:>8}  {density:>10.1f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_vault_arguments(parser)
    parser.add_argument("--json", action="store_true", help="print the area rows as JSON")
    parser.add_argument(
        "--include-generated",
        action="store_true",
        help="also count notes under the --generated folders",
    )
    parser.add_argument(
        "--generated",
        action="append",
        default=[],
        metavar="PREFIX",
        help="vault-relative folder of generated notes to leave out of the counts (repeatable)",
    )
    parser.add_argument(
        "--split",
        action="append",
        default=[],
        metavar="FOLDER",
        help="top-level folder to break down one level further in the table (repeatable)",
    )
    parser.add_argument(
        "--list",
        metavar="AREA",
        help="list the notes in AREA (as shown in the table) with no inbound link",
    )
    parser.add_argument("--limit", type=int, default=40, help="maximum notes to list (default: 40)")
    args = parser.parse_args()

    global GENERATED_PREFIXES
    root = apply_vault_arguments(args)
    GENERATED_PREFIXES = tuple(args.generated)
    SPLIT_AREAS.update(args.split)
    graph = link_graph(root, args.include_generated)
    if args.list:
        orphans = sorted(note for note, sources in graph["inbound"].items() if not sources and area_of(note) == args.list)
        for note in orphans[: args.limit]:
            print(note)
        if len(orphans) > args.limit:
            print(f"... {len(orphans) - args.limit} more not shown")
        print(f"{len(orphans)} note(s) in {args.list} with no inbound link.")
        return 0

    rows = area_report(graph)
    if args.json:
        json.dump(rows, sys.stdout, indent=1)
        print()
    else:
        print_table(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
