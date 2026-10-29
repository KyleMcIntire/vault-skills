#!/usr/bin/env python3
"""Read-only structural checks for an Obsidian vault.

Reports unclosed frontmatter and code fences, unresolved wiki-links, and
Iconize shortcodes that no installed icon pack provides. It never edits a file.

The vault root is --vault, else $VAULT_ROOT, else the nearest parent of the
current directory holding `.vault-skills.yaml` or `.obsidian/`, else the
current directory.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path


# Directory names skipped everywhere. Add more with --exclude (repeatable) or
# the comma-separated VAULT_EXCLUDE environment variable.
EXCLUDED_DIRECTORIES = {
    ".git",
    ".obsidian",
    ".smart-env",
    ".trash",
    "node_modules",
}
# Folders that exist on one machine only (scratch, render output), so links
# into them can't be expected to resolve elsewhere. Override with --machine-local.
MACHINE_LOCAL_PREFIXES = ("Local/",)
WIKI_LINK = re.compile(r"!?\[\[([^\]]+)\]\]")
FENCE = re.compile(r"^\s*([`~]{3,})")
# Fences can also open inside blockquotes and callouts ("> ```text").
QUOTED_FENCE = re.compile(r"^((?:[ \t]*>)*)[ \t]*([`~]{3,})")
QUOTE_PREFIX = re.compile(r"(?:[ \t]*>)*")
# Inline HTML <code> renders as code too, as in table cells showing link syntax.
CODE_SPAN = re.compile(r"(`+)(.+?)(?<!`)\1(?!`)|<code>.*?</code>")


# Iconize shortcodes (":TwCalendar:") and `icon:` properties. Only packs with an
# installed file list can be checked; Iconize's built-in packs (Fa, Ib, ...) can't.
ICON_SHORTCODE = re.compile(r"(?<![\w:]):([A-Z][A-Za-z0-9]{2,}):(?![\w])")
ICON_PROPERTY = re.compile(r"^icon:\s*[\"']?([A-Z][A-Za-z0-9]+)[\"']?\s*$", re.MULTILINE)
# Generated transcripts and worktree copies quote old names on purpose.
ICON_SKIP_PARTS = (".claude/worktrees/",)
# prefix -> (folder under .obsidian/icons, zip file name or None, loose matching).
# "Loose" ignores case and punctuation, for packs whose file names are kebab-case.
# Add your own packs with --icon-pack PREFIX=folder[,archive.zip[,loose]].
ICON_PACKS = {
    "Tw": ("twemoji", "twemoji.zip", False),
    "Li": ("lucide-icons", "lucide-icons.zip", True),
}


def icon_names(root: Path, packs: dict | None = None) -> dict[str, set[str]]:
    """Return installed icon names per prefix, from the pack folders and zips."""
    icons = root / ".obsidian" / "icons"
    found: dict[str, set[str]] = {}
    for prefix, (folder, archive, loose) in (packs or ICON_PACKS).items():
        names: set[str] = set()
        if (icons / folder).is_dir():
            names |= {p.stem for p in (icons / folder).glob("*.svg")}
        if archive and (icons / archive).is_file():
            with zipfile.ZipFile(icons / archive) as zf:
                names |= {Path(n).stem for n in zf.namelist() if n.endswith(".svg")}
        if names:
            found[prefix] = {re.sub(r"[^a-z0-9]", "", n.lower()) for n in names} if loose else names
    return found


def unknown_icons(root: Path, files: list[Path], packs: dict | None = None) -> list[str]:
    """Report icon names that no installed pack provides, so Iconize prints them as text."""
    packs = packs or ICON_PACKS
    installed = icon_names(root, packs)
    warnings: list[str] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        if any(part in relative for part in ICON_SKIP_PARTS):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        seen: set[str] = set()
        names = ICON_SHORTCODE.findall(without_code(content)) + ICON_PROPERTY.findall(content)
        for name in names:
            prefix, rest = name[:2], name[2:]
            pack = installed.get(prefix)
            if pack is None or name in seen:
                continue
            key = re.sub(r"[^a-z0-9]", "", rest.lower()) if packs[prefix][2] else rest
            if key not in pack:
                seen.add(name)
                warnings.append(f"{relative}: unknown icon :{name}:")
    return warnings


def find_vault_root(explicit: str | None = None) -> Path:
    """Resolve the vault root: explicit path, $VAULT_ROOT, nearest config/.obsidian parent, else cwd."""
    chosen = explicit or os.environ.get("VAULT_ROOT")
    if chosen:
        return Path(chosen).expanduser().resolve()
    here = Path.cwd().resolve()
    for marker in (".vault-skills.yaml", ".obsidian"):
        for parent in (here, *here.parents):
            if (parent / marker).exists():
                return parent
    return here


def add_vault_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the --vault and --exclude options every tool shares."""
    parser.add_argument("--vault", help="vault root (default: $VAULT_ROOT, else searched upward from the current directory)")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="DIR",
        help="extra directory name to skip everywhere (repeatable; also $VAULT_EXCLUDE, comma-separated)",
    )


def apply_vault_arguments(args: argparse.Namespace) -> Path:
    """Resolve the root and merge extra excluded directory names into the shared set."""
    extra = [name for name in os.environ.get("VAULT_EXCLUDE", "").split(",") if name]
    EXCLUDED_DIRECTORIES.update(extra + list(args.exclude))
    return find_vault_root(args.vault)


def vault_files(root: Path) -> list[Path]:
    """Return vault files while skipping tooling and generated areas."""
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRECTORIES for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return sorted(files)


def frontmatter_error(path: Path) -> str | None:
    """Check only whether opening YAML frontmatter has a closing delimiter."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return "is not valid UTF-8"

    if not lines or lines[0] != "---":
        return None
    if any(line in {"---", "..."} for line in lines[1:]):
        return None
    return "has opening YAML frontmatter without a closing delimiter"


def unclosed_fence(path: Path) -> str | None:
    """Detect an unmatched fenced code block without interpreting its contents."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return None

    open_fence: tuple[str, int, int] | None = None
    for number, line in enumerate(lines, start=1):
        match = FENCE.match(line)
        if not match:
            continue
        marker = match.group(1)
        if open_fence is None:
            open_fence = (marker[0], len(marker), number)
        elif marker[0] == open_fence[0] and len(marker) >= open_fence[1]:
            open_fence = None
    if open_fence is None:
        return None
    marker = open_fence[0] * open_fence[1]
    return f"has an unclosed {marker} fence opened on line {open_fence[2]}"


def without_code(content: str) -> str:
    """Blank fenced and inline code, including in callouts, where Obsidian makes no links."""
    kept: list[str] = []
    open_fence: tuple[str, int, int] | None = None
    for line in content.splitlines():
        match = QUOTED_FENCE.match(line)
        depth = QUOTE_PREFIX.match(line).group().count(">")
        if open_fence is None:
            if match:
                marker = match.group(2)
                open_fence = (marker[0], len(marker), depth)
                kept.append("")
            else:
                kept.append(CODE_SPAN.sub("", line))
            continue
        kept.append("")
        if match and depth == open_fence[2]:
            marker = match.group(2)
            if marker[0] == open_fence[0] and len(marker) >= open_fence[1] and not line[match.end():].strip():
                open_fence = None
        elif depth < open_fence[2]:
            # Leaving the quote ends a fence that opened inside it.
            open_fence = None
            kept[-1] = CODE_SPAN.sub("", line)
    return "\n".join(kept)


def normalized(value: str) -> str:
    return value.replace("\\", "/").casefold()


def file_index(
    root: Path, files: list[Path]
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Index vault-relative paths and filenames using Obsidian-like matching."""
    paths: dict[str, list[str]] = defaultdict(list)
    names: dict[str, list[str]] = defaultdict(list)
    for path in files:
        relative = path.relative_to(root)
        rendered = relative.as_posix()
        paths[normalized(rendered)].append(rendered)
        if path.suffix:
            paths[normalized(relative.with_suffix("").as_posix())].append(rendered)
        names[normalized(path.name)].append(rendered)
        names[normalized(path.stem)].append(rendered)
    return paths, names


def link_target(link: str) -> str:
    """Strip Obsidian display, heading, block, and extension syntax."""
    # Inside tables, Obsidian aliases use an escaped pipe: [[target\|alias]].
    target = re.split(r"\\?\|", link, maxsplit=1)[0].strip()
    target = target.split("#", maxsplit=1)[0].strip()
    if target.lower().endswith(".md"):
        target = target[:-3]
    return target.strip("/")


def resolves(
    root: Path, source: Path, target: str, paths: dict[str, list[str]], names: dict[str, list[str]]
) -> bool:
    """Resolve a target by exact, relative, basename, then unique suffix match."""
    if target.startswith(":"):
        return True

    target_key = normalized(target)
    if target_key in paths or target_key in names:
        return True

    source_parent = source.relative_to(root).parent
    for parent in (source_parent, *source_parent.parents):
        if str(parent) == ".":
            continue
        candidate = normalized((parent / target).as_posix())
        if candidate in paths:
            return True

    if "/" not in target:
        return False
    suffix = "/" + target_key
    matches = {
        rendered
        for key, values in paths.items()
        if key.endswith(suffix)
        for rendered in values
    }
    return len(matches) == 1


def unresolved_links(
    root: Path,
    files: list[Path],
    paths: dict[str, list[str]],
    names: dict[str, list[str]],
) -> list[str]:
    """Report references that cannot resolve to a known note path or title."""
    warnings: list[str] = []
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in WIKI_LINK.finditer(without_code(content)):
            target = link_target(match.group(1))
            if not target or target.startswith(MACHINE_LOCAL_PREFIXES) or resolves(root, path, target, paths, names):
                continue
            relative = path.relative_to(root).as_posix()
            warnings.append(f"{relative}: unresolved wiki-link [[{match.group(1)}]]")
    return warnings


def display(items: list[str], label: str, limit: int) -> None:
    for item in items[:limit]:
        print(f"{label}: {item}")
    if len(items) > limit:
        print(f"{label}: ... {len(items) - limit} more not shown")


def main() -> int:
    global MACHINE_LOCAL_PREFIXES
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_vault_arguments(parser)
    parser.add_argument(
        "--machine-local",
        action="append",
        metavar="PREFIX",
        help="vault-relative folder prefix whose links are not checked, e.g. Local/ (repeatable; default: Local/)",
    )
    parser.add_argument(
        "--icon-pack",
        action="append",
        default=[],
        metavar="PREFIX=FOLDER[,ZIP[,loose]]",
        help="also check icons from this Iconize pack (repeatable)",
    )
    parser.add_argument(
        "--strict-links",
        action="store_true",
        help="fail when wiki-links cannot be resolved",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=40,
        help="maximum findings to print per category (default: 40)",
    )
    args = parser.parse_args()

    root = apply_vault_arguments(args)
    if not root.is_dir():
        print(f"error: vault folder not found: {root}", file=sys.stderr)
        return 2
    if args.machine_local:
        MACHINE_LOCAL_PREFIXES = tuple(args.machine_local)
    packs = dict(ICON_PACKS)
    for spec in args.icon_pack:
        prefix, _, rest = spec.partition("=")
        parts = rest.split(",")
        packs[prefix] = (parts[0], parts[1] if len(parts) > 1 and parts[1] else None, "loose" in parts[2:])
    all_files = vault_files(root)
    files = [path for path in all_files if path.suffix.lower() == ".md"]
    paths, names = file_index(root, all_files)

    errors: list[str] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        if problem := frontmatter_error(path):
            errors.append(f"{relative}: {problem}")
        if problem := unclosed_fence(path):
            errors.append(f"{relative}: {problem}")

    warnings = unresolved_links(root, files, paths, names)
    icon_warnings = unknown_icons(root, files, packs)
    display(errors, "ERROR", args.limit)
    display(warnings, "WARN", args.limit)
    display(icon_warnings, "WARN", args.limit)
    print(
        f"Checked {len(files)} Markdown files: {len(errors)} error(s), "
        f"{len(warnings)} unresolved wiki-link(s), {len(icon_warnings)} unknown icon(s)."
    )
    if errors or (args.strict_links and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
