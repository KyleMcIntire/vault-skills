# Note-type banners

TODO template: record here which banner each note type in your vault uses, so new notes and templates stay consistent. Keep one row per type and update it when you roll a banner out.

The `note_types` module of the banner engine (`render_note_banners.py` with `note_banner_layouts.json`) renders one generic banner per note type: 1800 x 300, crisp 5x pixels, dark rooms, warm desks, subtle loops of about 6.5 seconds. Illustrations are generic, never portraits of real people or records of real events. Render with:

```sh
sh "<skill-directory>/scripts/render.sh" note_types "$CLAUDE_JOB_DIR/tmp/pixel-banners/<task>" [scene ...]
```

Name scenes (for example `person-note`) to render only those. For each banner it writes `<name>.gif`, `<name>-frames.png` (four moments of the loop) and `<name>-crops.png` (800 / 1100 / 1500 / 1900 px panes), plus a `gallery.png` contact sheet, and asserts the GIF size, loop timing, seamless wraparound and label visibility. Crop previews simulate the Pixel Banner plugin's cover crop and fade; they are not screenshots from Obsidian. Review, then install with `cp -n` into a `Note Types` folder under `folders.banners`.

## Mapping (fill in)

| Note type | Banner file | Template that uses it | banner-y | banner-x | content-start |
| --- | --- | --- | --- | --- | --- |
| Person | `person-note.gif` | TODO | 30 | 50 | 121 |
| Task | `task-note.gif` | TODO | TODO | TODO | 101 |
| Meeting | `meeting-note.gif` | TODO | TODO | TODO | TODO |
| Project | `project-note.gif` | TODO | TODO | TODO | 101 |
| Reference | `reference-note.gif` | TODO | 50 | 50 | 101 |

Positions come from the corresponding hub notes: each banner is 200 px high (`banner-height: 200`), and label shifts in the layouts JSON keep the label visible under the hub's vertical crop. Add banners to existing notes only after listing the target set and confirming it; preserve note bodies, unrelated frontmatter, and line endings, and do not touch notes that already have a custom banner.

Example frontmatter for a person note:

```yaml
banner: Media/Banners/Note Types/person-note.gif
banner-height: 200
banner-y: 30
banner-x: 50
content-start: 121
```
