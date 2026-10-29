# Reference files

- `term-corrections.json` is a starter list of regex pairs (`[pattern, replacement]`) that fix common transcription errors in technical talk. It is applied to transcript lines only.
- `term-corrections.local.json` starts empty. Add your own team, product and colleague names here as `["(?i)\\bmisheard form\\b", "Correct Form"]`, so the starter list can be updated without losing your additions. Pass both files to `render_note.py` with one `--corrections` flag each (the flag can be repeated). Add a pair when the same error shows up twice; fix one-offs in the transcript by hand.
- `vault-conventions.md` describes the note layout the skill writes. Edit it to match your vault.
- `example-note-head.md` is a fictional finished note head at the expected level of detail.
