# Vault scripts

Small, boring tools for keeping a vault healthy. They use only the Python standard library, except the banner engine, which needs Pillow and numpy. Every tool takes the same two options, and every tool that can change a file previews first.

```
--vault PATH     vault root; default $VAULT_ROOT, else the nearest parent of the
                 current directory holding .vault-skills.yaml or .obsidian/, else the cwd
--exclude DIR    extra directory name to skip everywhere (repeatable; or $VAULT_EXCLUDE=a,b)
```

Always skipped: `.git`, `.obsidian`, `.smart-env`, `.trash`, `node_modules`. Run the tools from this folder or put it on `PYTHONPATH`, because they import each other by bare module name.

## The tools

| Tool | What it does | Writes? |
| --- | --- | --- |
| `check_vault.py` | Reports unclosed frontmatter, unclosed code fences, invalid UTF-8, unresolved wiki-links, and Iconize shortcodes no installed pack provides. | Never |
| `link_graph_report.py` | Per-area table of notes with no inbound link, no outbound link, or neither, as a baseline for linking work. | Never |
| `link_daily_notes.py` | Chains daily notes with `prev`/`next` properties and keeps a generated **Related** block listing notes from that day. | Only with `--write` |
| `add_obsidian_frontmatter.py` | Prepends starter frontmatter to notes that have none. | Only with `--write` |
| `build_area_maps.py` | One Canvas map per top-level folder, saved inside it (`Wiki/Wiki Map.canvas`). | Only with `--write` |
| `build_vault_map.py` | One Canvas map of the whole vault, one card per top-level folder, linking each area map. | Only with `--write` |
| `banners/` | Renders animated pixel-art GIF banners (Pillow and numpy). | Writes only to the output folder you name |

### check_vault.py

```
python check_vault.py --vault ~/Vault [--strict-links] [--limit 40]
                      [--machine-local Local/] [--icon-pack Xx=folder[,pack.zip[,loose]]]
```

- Exit code 1 on errors, or on unresolved links with `--strict-links`; otherwise 0.
- Link resolution follows Obsidian: exact path, then note name, then path relative to the source folder, then a unique path suffix. Links inside code spans and fences are ignored.
- `--machine-local` names folders (default `Local/`) whose links are not expected to resolve on other machines.
- Icon checks cover the `Tw` (Twemoji) and `Li` (Lucide) packs when they are installed in `.obsidian/icons/`. With no pack installed, no icon warnings appear. Built-in Iconize packs cannot be checked.

### link_graph_report.py

```
python link_graph_report.py --vault ~/Vault [--json] [--list AREA] [--limit 40]
                            [--split FOLDER] [--generated PREFIX] [--include-generated]
```

`--split Meetings` breaks a top-level folder down one level in the table. `--generated Imports/` leaves a folder of generated notes out of the counts unless `--include-generated` is given. `--list Wiki` prints that area's notes with no inbound link.

### link_daily_notes.py

```
python link_daily_notes.py --vault ~/Vault [--daily-folder "Daily Notes"] [--skip Work/]
                           [--bulk-limit 20] [--show 3] [--write]
```

Previews unless `--write`. It touches only the `prev`/`next` properties and the text between `<!-- related-notes -->` and `<!-- /related-notes -->`. Safe to rerun; notes already current are left alone. A day with more than `--bulk-limit` notes created on it is treated as a bulk import and matched by file name only.

### add_obsidian_frontmatter.py

```
python add_obsidian_frontmatter.py --vault ~/Vault [--type Wiki=Reference] [--no-tags] [--write]
```

Previews unless `--write`. (The private original wrote by default; this version flips that on purpose.) Notes that already have a frontmatter block are skipped, the body is preserved byte for byte, and line endings are kept. No backup files are made, because the change only prepends.

### build_area_maps.py and build_vault_map.py

```
python build_area_maps.py --vault ~/Vault [--only Wiki] [--banners Media/Banners] [--columns 3] [--write]
python build_vault_map.py --vault ~/Vault [--output "Vault Map.canvas"] [--projects Projects]
                          [--status-order Active,Planning,Paused,Idea,Done] [--write]
```

Build the area maps first, then the master map, so it can link them. Both dry-run by default, refuse to write a canvas with broken links or overlapping cards, and use stable node ids so a rebuild produces a small git diff. If a GIF named after a folder (`wiki.gif` or `wiki-hub.gif`) exists in the banners folder, its card embeds it. The master map lists every `type: project` note under the projects folder, grouped by `status`.

## Banner engine

Needs `pip install pillow numpy`. Run from `scripts/banners/`.

| File | Role |
| --- | --- |
| `pix.py` | Tiny pixel canvas (`Cv`), a 3x5 pixel font, and `save_gif`, which writes a looping GIF with one shared palette and no dithering. |
| `thin_common.py` | Helpers for the thin 360x60 banners: bands, big pixel text, plates, clouds. |
| `render_thin.py` | Renders scenes from any module with a `SCENES` dict, then writes a frame strip and a crop sheet showing how Pixel Banner would crop it at several pane widths. |
| `example_scenes.py` | One looping night-skyline scene to copy from. |
| `render_note_banners.py` | Renders one banner per note type (person, task, meeting, project, reference, communication, workout), asserts each loops cleanly, and writes a gallery and crop previews. |
| `note_banner_layouts.json` | Per note type placement, described below. |
| `hub_themes.py`, `recolor_gif.py` | Recolour the wall and wood families of a room-style banner into named themes, for scenes or for existing GIFs. |

```
python render_thin.py example_scenes /tmp/banners-out            # all scenes in the module
python render_note_banners.py /tmp/banners-out person-note       # one note-type banner
python recolor_gif.py teal in.gif /tmp/banners-out/out.gif
```

Render into a scratch folder, look at `*-frames.png` and `crops.png`, and only then copy GIFs into your banners folder.

### note_banner_layouts.json

One entry per note-type scene, keyed by scene name:

| Key | Meaning |
| --- | --- |
| `source` | A hub note whose banner settings the entry was copied from. Documentation only; nothing reads the file. |
| `banner-height` | Banner height in pixels in Pixel Banner. |
| `banner-y`, `banner-x` | Focal point as a percentage; `banner-x` defaults to 50. |
| `content-start` | Pixel where the note's text starts, so the preview can shade it. |
| `scene-shift` | Logical pixels to push the scene down so its label survives wide-pane cropping. The renderer asserts the label is never cropped. |

Paste the same `banner-height`, `banner-y`, `banner-x` and `content-start` values into the notes' frontmatter.

## Tests

From the repository root:

```
python3 -m unittest discover -s scripts -p 'test_*.py'
```

Without Pillow and numpy the rendering tests in `test_banners.py` skip with a message; the rest still run. A single test, from `scripts/`: `python3 -m unittest test_check_vault.UnknownIconTests`.

## Make targets for the repository Makefile

```make
VAULT ?= vault-template
PY ?= python3

check:        ## structural checks, read-only
	$(PY) scripts/check_vault.py --vault $(VAULT)

check-links:  ## same, but unresolved links fail the run
	$(PY) scripts/check_vault.py --vault $(VAULT) --strict-links

test:         ## unit tests (banner tests skip without Pillow and numpy)
	$(PY) -m unittest discover -s scripts -p 'test_*.py'
```

`check_vault.py` reads no config file; scripts never parse `.vault-skills.yaml`. A skill reads the YAML and passes the folder names as flags.
