#!/bin/sh
# Syntax-check JS. Dataview views (vault-template/**/view.js and hub files) run inside an async
# function, so they are wrapped the same way before `node --check`.
set -e
command -v node >/dev/null || { echo "node not found, skipped JS"; exit 0; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
find plugins -name '*.mjs' -print | while IFS= read -r f; do node --check "$f"; done
find vault-template -name '*.js' -print | while IFS= read -r f; do
  { printf '(async (dv, input) => {\n'; cat "$f"; printf '\n});\n'; } > "$tmp/x.js"
  node --check "$tmp/x.js" || { echo "in $f"; exit 1; }
done
echo "JS ok"
