#!/usr/bin/env python3
"""Build a Canvas map of the vault: one colored card per top-level folder.

Each card shows the folder's note count, its subfolders with counts, a few
notes (hub notes first), and a link to the folder's own area map if
`build_area_maps.py` has made one. If a banner GIF named after the folder
exists in the banners folder (`<folder>.gif` or `<folder>-hub.gif`), it is
embedded at the top. A "Projects" card lists every `type: project` note under
the projects folder, grouped by `status`.

Runs as a dry run by default. Pass --write to replace the canvas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from check_vault import EXCLUDED_DIRECTORIES, add_vault_arguments, apply_vault_arguments

DEFAULT_OUTPUT = "Vault Map.canvas"
BLUE, GREEN, ORANGE, PURPLE, YELLOW, PINK, TEAL, GREY = (
    "#5ab0ff", "#7bd88f", "#f6a85a", "#c49bff", "#ffd27a", "#f687b3", "#73daca", "#9aa3b5")
PALETTE = [BLUE, GREEN, ORANGE, PURPLE, YELLOW, PINK, TEAL]
CELL, GAP = 600, 120
STATUS_ORDER = ["Active", "Planning", "Paused", "Idea", "Done"]


class Canvas:
    """A JSON Canvas under construction. Node ids are stable hashes of a key, so rebuilds are diff-friendly."""

    def __init__(self) -> None:
        self.nodes: list[dict] = []
        self.edges: list[dict] = []
        self.ids: set[str] = set()

    def new_id(self, key: str) -> str:
        node_id = hashlib.sha1(key.encode()).hexdigest()[:16]
        if node_id in self.ids:
            raise ValueError(f"duplicate id for {key}")
        self.ids.add(node_id)
        return node_id

    def text(self, key, x, y, w, body, color=None, h=None) -> dict:
        node = {"id": self.new_id(key), "type": "text", "x": x, "y": y, "width": w,
                "height": h or text_height(body, w), "text": body}
        if color:
            node["color"] = color
        self.nodes.append(node)
        return node

    def edge(self, a, b, from_side, to_side, label=None, color=None) -> None:
        edge = {"id": self.new_id(f"edge:{a['id']}:{b['id']}:{label}"), "fromNode": a["id"],
                "fromSide": from_side, "toNode": b["id"], "toSide": to_side, "toEnd": "arrow"}
        if label:
            edge["label"] = label
        if color:
            edge["color"] = color
        self.edges.append(edge)


def visible(line: str) -> str:
    line = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", line)
    line = re.sub(r"\[\[([^\]]+)\]\]", lambda m: Path(m[1]).stem, line)
    line = re.sub(r":Tw\w+:", "XX", line)
    return line.replace("`", "").replace("**", "").replace("*", "")


def text_height(body: str, width: int) -> int:
    """Estimate a card's rendered height so text never needs a scrollbar."""
    per_line = (width - 40) / 7.5
    height = 76
    for line in body.split("\n"):
        if line.startswith("![["):
            height += round((width - 28) / 6) + 14
        elif line.startswith("# "):
            height += 44
        elif line.startswith("## "):
            height += 34
        elif not line.strip():
            height += 8
        else:
            chars = len(visible(line)) + 2 * line.count("[[")
            height += 24 * max(1, math.ceil(chars / per_line))
    return int(math.ceil(height / 10) * 10)


def close_row(cards: list[dict]) -> int:
    """Give a row's cards one height, so the grid reads as rows. Returns the row's bottom edge."""
    height = max(card["height"] for card in cards) + 32
    for card in cards:
        card["height"] = height
    return cards[0]["y"] + height


def areas(root: Path) -> list[Path]:
    """Top-level, non-hidden, non-excluded folders, sorted by name."""
    return sorted(p for p in root.iterdir()
                  if p.is_dir() and not p.name.startswith(".") and p.name not in EXCLUDED_DIRECTORIES)


def md_count(root: Path, relative: str) -> int:
    base = root / relative
    if not base.is_dir():
        return 0
    return sum(1 for p in base.rglob("*.md")
               if not any(part in EXCLUDED_DIRECTORIES for part in p.relative_to(root).parts))


def frontmatter(path: Path) -> dict[str, str]:
    """Read flat `key: value` pairs from a note's frontmatter (no nested YAML)."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return {}
    if not lines or lines[0] != "---":
        return {}
    values = {}
    for line in lines[1:]:
        if line == "---":
            break
        if ":" in line and not line.startswith((" ", "-")):
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


def link(root: Path, path: Path, label: str | None = None) -> str:
    rel = path.relative_to(root)
    target = rel.as_posix() if path.suffix in (".base", ".canvas") else rel.with_suffix("").as_posix()
    return f"[[{target}|{label or path.stem}]]"


def own_notes(root: Path, folder: Path, limit: int = 5) -> list[str]:
    """Bullet links to a folder's own notes (not its subfolders), hubs first, with a '+N more' tail."""
    files = sorted((p for p in folder.iterdir() if p.is_file() and p.suffix in (".md", ".canvas")),
                   key=lambda p: ("Hub" not in p.stem, p.stem.lower()))
    lines = [f"- {link(root, p)}" for p in files[:limit]]
    if len(files) > limit:
        lines.append(f"- +{len(files) - limit} more")
    return lines


def banner_for(root: Path, banners: str, name: str) -> str | None:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    for candidate in (f"{slug}.gif", f"{slug}-hub.gif"):
        if (root / banners / candidate).is_file():
            return f"{banners}/{candidate}"
    return None


def projects_by_status(root: Path, projects: str, order: list[str]) -> list[str]:
    """One line per status, listing every `type: project` note under the projects folder."""
    buckets: dict[str, list[str]] = {}
    base = root / projects
    for path in sorted(base.rglob("*.md")) if base.is_dir() else []:
        meta = frontmatter(path)
        if meta.get("type") != "project":
            continue
        title = meta.get("title") or (path.parent.name if path.stem == "README" else path.stem)
        rel = path.relative_to(root).with_suffix("").as_posix()
        buckets.setdefault(meta.get("status", ""), []).append(f"[[{rel}|{title}]]")
    rank = lambda s: next((i for i, word in enumerate(order) if word.lower() in s.lower()), len(order))
    return [f"- **{status or 'No status'}** · " + " · ".join(links)
            for status, links in sorted(buckets.items(), key=lambda kv: (rank(kv[0]), kv[0]))]


def area_card(root: Path, folder: Path, banners: str, projects: str, order: list[str]) -> str:
    rel = folder.name
    parts = []
    if banner := banner_for(root, banners, rel):
        parts += [f"![[{banner}]]", ""]
    parts += [f"## {rel}", f"**{md_count(root, rel)} notes**", ""]
    subfolders = sorted(d for d in folder.iterdir()
                        if d.is_dir() and not d.name.startswith(".") and d.name not in EXCLUDED_DIRECTORIES)
    parts += [f"- `{d.name}/` · {md_count(root, f'{rel}/{d.name}')}" for d in subfolders[:8]]
    if len(subfolders) > 8:
        parts.append(f"- +{len(subfolders) - 8} more folders")
    parts += own_notes(root, folder, 4)
    if rel == projects:
        parts += ["", *projects_by_status(root, projects, order)]
    area_map = folder / f"{rel} Map.canvas"
    if area_map.is_file():
        parts += ["", f"[[{area_map.relative_to(root).as_posix()}|Area map]]"]
    return "\n".join(parts)


def build(root: Path, banners: str = "Media/Banners", projects: str = "Projects",
          order: list[str] | None = None, cols: int = 3) -> Canvas:
    c = Canvas()
    order = order or STATUS_ORDER
    y, row = 0, []
    for index, folder in enumerate(areas(root)):
        col = index % cols
        body = area_card(root, folder, banners, projects, order)
        row.append(c.text(f"area:{folder.name}", col * (CELL + GAP), y, CELL, body, PALETTE[index % len(PALETTE)]))
        if col == cols - 1:
            y = close_row(row) + GAP
            row = []
    if row:
        close_row(row)
    return c


def check(root: Path, c: Canvas) -> list[str]:
    """Return problems: edges to missing nodes, unresolved links, overlapping cards."""
    problems = []
    ids = {n["id"] for n in c.nodes}
    for e in c.edges:
        if e["fromNode"] not in ids or e["toNode"] not in ids:
            problems.append(f"edge {e['id']} points at a missing node")
    names = set()
    for p in root.rglob("*"):
        if any(part in EXCLUDED_DIRECTORIES for part in p.relative_to(root).parts):
            continue
        names.add(p.stem.lower() if p.suffix == ".md" else p.name.lower())
    for n in c.nodes:
        for target in re.findall(r"!?\[\[([^\]|#]+)", n.get("text", "")):
            if not ((root / target).exists() or (root / f"{target}.md").exists() or Path(target).name.lower() in names):
                problems.append(f"unresolved link [[{target}]]")
    boxes = [n for n in c.nodes if n["type"] != "group"]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if (a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"]
                    and a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"]):
                problems.append(f"overlap {a['id']} {b['id']}")
    return problems


def write_canvas(path: Path, c: Canvas) -> None:
    data = json.dumps({"nodes": c.nodes, "edges": c.edges}, indent="\t", ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_vault_arguments(parser)
    parser.add_argument("--write", action="store_true", help="write the canvas (default: dry run)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"vault-relative canvas path (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--banners", default="Media/Banners", help="banner folder (default: Media/Banners)")
    parser.add_argument("--projects", default="Projects", help="projects folder (default: Projects)")
    parser.add_argument("--status-order", default=",".join(STATUS_ORDER),
                        help="comma-separated status words, in display order")
    parser.add_argument("--columns", type=int, default=3, help="cards per row (default: 3)")
    args = parser.parse_args()

    root = apply_vault_arguments(args)
    canvas = build(root, args.banners, args.projects, args.status_order.split(","), args.columns)
    if not canvas.nodes:
        print("No top-level folders found; nothing to map.")
        return 1
    problems = check(root, canvas)
    width = max(n["x"] + n["width"] for n in canvas.nodes)
    height = max(n["y"] + n["height"] for n in canvas.nodes)
    print(f"{len(canvas.nodes)} nodes, {len(canvas.edges)} edges, {width}x{height}")
    for problem in problems:
        print("problem:", problem)
    if problems:
        return 1
    if not args.write:
        print(f"Dry run only. Rerun with --write to replace {args.output}.")
        return 0
    write_canvas(root / args.output, canvas)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
