#!/bin/sh
# Render pixel banners from the banner engine into a scratch folder outside the vault.
# Usage, from the vault root: render.sh <module> <outdir> [scene ...]
# Engine location: $VAULT_SKILLS_BANNERS, else <vault-skills checkout>/scripts/banners
# (derived from this script's location). Uses a cached Pillow + numpy venv outside the
# vault (override with PIXEL_BANNERS_VENV).
set -eu
[ $# -ge 2 ] || { echo "usage: render.sh <module> <outdir> [scene ...]" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
VAULT="${VAULT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
ENGINE="${VAULT_SKILLS_BANNERS:-$HERE/../../../../../scripts/banners}"
[ -f "$ENGINE/render_thin.py" ] || { echo "no banner engine at $ENGINE; set VAULT_SKILLS_BANNERS to the scripts/banners folder of your vault-skills checkout" >&2; exit 1; }
ENGINE="$(cd "$ENGINE" && pwd)"
VENV="${PIXEL_BANNERS_VENV:-$HOME/.cache/pixel-banners/venv}"
if ! "$VENV/bin/python" -c "import PIL, numpy" 2>/dev/null; then
    echo "creating $VENV (Pillow + numpy)" >&2
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q Pillow numpy
fi
module=$1; out=$2; shift 2
case "$out" in /*) ;; *) out="$PWD/$out" ;; esac
case "$out" in "$VAULT"|"$VAULT"/*) echo "render outside the vault, e.g. /tmp/pixel-banners" >&2; exit 2 ;; esac
cd "$ENGINE"
# note_types is the separate note-type engine; the rest are thin modules.
if [ "$module" = note_types ]; then
    PYTHONDONTWRITEBYTECODE=1 "$VENV/bin/python" render_note_banners.py "$out" "$@"
else
    PYTHONDONTWRITEBYTECODE=1 "$VENV/bin/python" render_thin.py "$module" "$out" "$@"
fi
