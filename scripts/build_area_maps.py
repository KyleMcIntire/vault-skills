#!/usr/bin/env python3
"""Build one map canvas per top-level folder, saved inside that folder.

For a folder `Wiki/`, writes `Wiki/Wiki Map.canvas`: a header card with the
folder's note count and own notes, then a grid of cards, one per subfolder,
linked by arrows from the header. `build_vault_map.py` links each area's map
from the master map when one exists, so build these first.

Runs as a dry run by default. Pass --write to replace the canvases, and --only
<folder> (repeatable) to build only some.
"""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

from build_vault_map import (BLUE, EXCLUDED_DIRECTORIES, GAP, PALETTE, Canvas, areas, banner_for, check,
                             close_row, md_count, own_notes, write_canvas)
from check_vault import add_vault_arguments, apply_vault_arguments

ROW_GAP, CELL = 150, 560


def bases(root: Path, folder: Path) -> str:
    found = sorted(folder.glob("*.base"))
    return " · ".join(f"[[{p.relative_to(root).as_posix()}|{p.stem}]]" for p in found)


def subfolders(folder: Path) -> list[Path]:
    return sorted(d for d in folder.iterdir()
                  if d.is_dir() and not d.name.startswith(".") and d.name not in EXCLUDED_DIRECTORIES)


def build_area(root: Path, folder: Path, banners: str, cols: int = 3) -> Canvas:
    name = folder.name
    c = Canvas()
    head = [f"## {name}", f"**{md_count(root, name)} notes**", ""]
    if banner := banner_for(root, banners, name):
        head = [f"![[{banner}]]", ""] + head
    head += own_notes(root, folder, 6)
    if listing := bases(root, folder):
        head += ["", "Views: " + listing]
    width = cols * CELL + (cols - 1) * GAP
    header = c.text(f"{name}:header", (width - CELL) // 2, 0, CELL, "\n".join(head), BLUE)
    y = header["height"] + ROW_GAP
    first_row, row = [], []
    for index, sub in enumerate(subfolders(folder)):
        rel = f"{name}/{sub.name}"
        body = [f"## {sub.name}", f"**{md_count(root, rel)} notes**", "", *own_notes(root, sub, 6)]
        col = index % cols
        row.append(c.text(f"{name}:{sub.name}", col * (CELL + GAP), y, CELL, "\n".join(body),
                          PALETTE[(index + 1) % len(PALETTE)]))
        if col == cols - 1:
            y = close_row(row) + ROW_GAP
            first_row = first_row or row
            row = []
    if row:
        close_row(row)
        first_row = first_row or row
    for target in first_row:
        c.edge(header, target, "bottom", "top", color=BLUE)
    return c


def icon_problems(root: Path, canvas: Canvas) -> list[str]:
    """Flag `:TwName:` shortcodes the installed Twemoji pack lacks. No pack installed means no check."""
    archive = root / ".obsidian/icons/twemoji.zip"
    if not archive.exists():
        return []
    with zipfile.ZipFile(archive) as zf:
        known = {Path(n).stem for n in zf.namelist()}
    used = {m for n in canvas.nodes for m in re.findall(r":Tw(\w+):", n.get("text", ""))}
    return [f"unknown icon Tw{m}" for m in sorted(used - known)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_vault_arguments(parser)
    parser.add_argument("--write", action="store_true", help="write the canvases (default: dry run)")
    parser.add_argument("--only", action="append", default=[], metavar="FOLDER", help="build only this folder (repeatable)")
    parser.add_argument("--banners", default="Media/Banners", help="banner folder (default: Media/Banners)")
    parser.add_argument("--columns", type=int, default=3, help="cards per row (default: 3)")
    args = parser.parse_args()

    root = apply_vault_arguments(args)
    failed = False
    for folder in areas(root):
        if args.only and folder.name not in args.only:
            continue
        if not subfolders(folder):
            print(f"{folder.name}: no subfolders, skipped")
            continue
        canvas = build_area(root, folder, args.banners, args.columns)
        problems = check(root, canvas) + icon_problems(root, canvas)
        target = f"{folder.name}/{folder.name} Map.canvas"
        width = max(n["x"] + n["width"] for n in canvas.nodes)
        height = max(n["y"] + n["height"] for n in canvas.nodes)
        print(f"{folder.name}: {len(canvas.nodes)} nodes, {len(canvas.edges)} edges, {width}x{height} -> {target}")
        for problem in problems:
            print("  problem:", problem)
        failed |= bool(problems)
        if args.write and not problems:
            write_canvas(root / target, canvas)
    if not args.write:
        print("Dry run only. Rerun with --write to replace the canvases.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
