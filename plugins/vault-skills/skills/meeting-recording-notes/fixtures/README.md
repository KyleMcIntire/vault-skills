Tiny fictional fixture. Smoke test:

    python3 ../scripts/render_note.py --lines lines.json --head ../references/example-note-head.md \
      --out /tmp/test-note.md --corrections ../references/term-corrections.json \
      --vault vault --people-folder People --me "Alex Example"

Expect `speaker links: ['Alex', 'Sam']` and `unresolved refs: none`.
