#!/usr/bin/env python3
"""Download a profile picture into the vault's attachment folder.

Prints the wiki-link to use in a person note's `image:` property, e.g.
`[[Alex Example (Slack).jpg]]`. Standard library only, plus macOS `sips` to
shrink the photo when it is available.

    fetch_avatar.py "Alex Example" "https://avatars.slack-edge.com/.../alex_original.jpg" \
        --vault /path/to/vault --attachments "Media/Attachments"

The vault comes from --vault, else $VAULT_ROOT, else the nearest parent of the
current directory holding .vault-skills.yaml or .obsidian/. Nothing is baked in.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_ATTACHMENTS = "Media/Attachments"
DEFAULT_HOSTS = ("slack-edge.com", "slack.com", "slack-files.com")
EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}
MAX_BYTES = 15 * 1024 * 1024


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def find_vault(cli_value):
    if cli_value:
        return Path(cli_value)
    if os.environ.get("VAULT_ROOT"):
        return Path(os.environ["VAULT_ROOT"])
    here = Path.cwd().resolve()
    for marker in (".vault-skills.yaml", ".obsidian"):
        for parent in (here, *here.parents):
            if (parent / marker).exists():
                return parent
    return here


def check_url(url, hosts, any_host):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        fail(f"only https URLs are allowed: {url}")
    if "gravatar.com" in host or "/avatars/ava_" in url:
        fail("this is a default avatar, not a real photo; leave `image:` empty")
    if not any_host and not any(host == h or host.endswith("." + h) for h in hosts):
        fail(f"{host} is not an allowed image host; pass --allow-host {host} or --any-host")


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "vault-skills-add-person/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content_type = response.headers.get_content_type()
            data = response.read(MAX_BYTES + 1)
    except OSError as exc:  # URLError and timeouts: report a gap, never a traceback
        fail(f"could not download the image: {exc}")
    if content_type not in EXTENSIONS:
        fail(f"expected an image, got {content_type}")
    if len(data) > MAX_BYTES:
        fail("image is larger than 15 MB")
    return data, EXTENSIONS[content_type]


def shrink(path, size):
    # Original profile photos can be 1500px+; a person card does not need that.
    if size and shutil.which("sips") and path.suffix in (".jpg", ".png"):
        subprocess.run(["sips", "-Z", str(size), str(path)], check=False, capture_output=True)


def glob_escape(text):
    return re.sub(r"([*?\[])", r"[\1]", text)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="the person's note name, e.g. 'Alex Example'")
    parser.add_argument("url", help="the profile picture URL (https)")
    parser.add_argument("--vault", help="vault root (default: $VAULT_ROOT, else search upward)")
    parser.add_argument("--attachments", default=DEFAULT_ATTACHMENTS,
                        help=f"vault-relative attachment folder (default: {DEFAULT_ATTACHMENTS})")
    parser.add_argument("--label", default="Slack",
                        help="source label in the file name, 'Name (Label).ext' (default: Slack)")
    parser.add_argument("--allow-host", action="append", default=[],
                        help="extra allowed image host (repeatable); defaults are Slack's image hosts")
    parser.add_argument("--size", type=int, default=512, help="longest side in px; 0 keeps the original")
    parser.add_argument("--force", action="store_true", help="replace an existing photo with the same name")
    parser.add_argument("--any-host", action="store_true", help="allow any https image host")
    parser.add_argument("--dry-run", action="store_true", help="show the target path without downloading")
    args = parser.parse_args()

    vault = find_vault(args.vault)
    check_url(args.url, tuple(DEFAULT_HOSTS) + tuple(args.allow_host), args.any_host)
    safe_name = re.sub(r'[\\/:*?"<>|#^\[\]]', "", args.name).strip()
    if not safe_name:
        fail("name is empty after removing characters Obsidian can't link to")
    folder = vault / args.attachments
    if not folder.is_dir():
        fail(f"attachment folder not found: {folder} (pass --attachments or create it)")

    stem = f"{safe_name} ({args.label})"
    existing = sorted(folder.glob(f"{glob_escape(stem)}.*"))
    if existing and not args.force:
        fail(f"photo already exists: {existing[0].relative_to(vault)} (pass --force to replace it)")
    if args.dry_run:
        print(f"DRY RUN: would save {args.attachments}/{stem}.<ext>")
        return

    data, ext = download(args.url)
    target = folder / f"{stem}{ext}"
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / target.name
        staged.write_bytes(data)
        shrink(staged, args.size)
        for old in existing:
            old.unlink()
        shutil.move(str(staged), target)

    print(f"SAVED: {target.relative_to(vault)}")
    print(f"LINK: [[{target.name}]]")


if __name__ == "__main__":
    main()
