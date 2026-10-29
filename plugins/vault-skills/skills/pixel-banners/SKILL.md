---
name: pixel-banners
description: Create, replace, or tweak animated pixel-art GIF banners for Obsidian notes (hubs, daily notes, templates, projects) using the vault-skills banner engine, so new banners match one house style (1800x300, flat palette, seamless loop). Use when the user asks for a new banner, a banner for a hub or template, to convert an image or video banner to the pixel GIF style, to change a scene in an existing banner, or to clean up unused banner assets.
---

# Pixel banners

Banners are flat pixel-art GIF loops generated in code, so they share one palette, layout, and motion language. Each banner is a Python scene function. **Never** substitute AI-generated images, video, or photos unless the user explicitly asks.

## Config

Read `.vault-skills.yaml` at the vault root first (see `docs/CONFIG.md`). Keys used: `folders.banners` (where finished GIFs live, default `Media/Banners`), `folders.templates`, `folders.scratch`. Ask once if a needed value is missing. The vault's `CLAUDE.md` overrides this skill.

## The engine

The engine lives in the vault-skills checkout at `scripts/banners/`. Locate it with the `VAULT_SKILLS_BANNERS` environment variable; the default is the `scripts/banners` folder of the checkout this skill was installed from. If neither exists, ask the user where the checkout is and set `VAULT_SKILLS_BANNERS` for the render command. Do not copy the engine into the vault.

| Path (inside the engine folder) | Role |
| --- | --- |
| `pix.py`, `thin_common.py` | Canvas, font, GIF writer, shared set pieces |
| `render_thin.py` | Renders a module's `SCENES` and writes `<name>.gif`, `<name>-frames.png`, and `crops.png` |
| `thin_*.py`, `*_hubs.py`, other scene modules | Scene modules; list them with `ls` to see which exist. Each defines a `SCENES` dict |
| `render_note_banners.py`, `note_banner_layouts.json` | A separate engine for note-type banners (module name `note_types`) |
| `<skill-directory>/scripts/render.sh` | Wrapper: bootstraps a cached Pillow + numpy venv and renders outside the vault |
| `<skill-directory>/references/style-guide.md` | Canvas, crop-safe zones, palette, composition, animation rules, and API |
| `<skill-directory>/references/note-types.md` | Template for positioning banners by note type |

## Workflow

1. **Scope.** Read the vault `CLAUDE.md`. Find every note and template that will use the banner: search `banner:` frontmatter (properties search, or grep `*.md`, `*.base`, `*.canvas`, and CSS). For a replacement, list each file that references the old asset and confirm the set with the user before editing.
2. **Concept.** Read `references/style-guide.md`. Look at two or three existing banners: extract a frame with `ffmpeg -i <gif> -frames:v 1 x.png` and view it. If an old image or video is being replaced, keep its theme. Choose one centrepiece that says what the note collection is, one hero motion, a few ambient motions, and an UPPERCASE label word. If the concept is unclear, ask; otherwise pick sensibly and say what you chose.
3. **Write the scene.** Add a scene function to a fitting module, or create a new module from the skeleton in the style guide. Register it in `SCENES` as `'<output-name>': (fn, 72)`. The output name becomes the filename, so use lowercase kebab-case such as `garden-hub`. Reuse the `thin_common` helpers instead of copying them. Edit existing scene functions only as requested.
4. **Render to scratch.** From the vault root run `sh "<skill-directory>/scripts/render.sh" <module> "$CLAUDE_JOB_DIR/tmp/pixel-banners/<task>" [scene ...]`, or `/tmp/pixel-banners/<task>` when `$CLAUDE_JOB_DIR` is unset. The script refuses output paths inside the vault, so the scratch folder under the vault is not an option. If venv creation fails because the network is blocked, report it and ask the user to run the command or allow network access. Do not install packages any other way.
5. **Review visually and iterate.** View `<name>-frames.png` (four points in the loop) and `crops.png` (800/1100/1500/1900 px panes; the darkened area is behind note content). Check for:
   - the label fully visible at 1900 px, with the hero motion in the clear band
   - no overlaps or floating props
   - glows drawn behind their sources
   - seamless looping
   - a size of about 1.2 MB or less
   Fix any problem and render again. Do not show the user a banner you have not looked at.
6. **Install.** Copy the GIF into the right folder under `folders.banners` with `cp -n`, so an existing file is never silently replaced. Overwriting a GIF that the same task created is fine. Replacing any other existing GIF needs the user's go-ahead.
7. **Point notes at it.** Change only the `banner:` value in the files confirmed in step 1, including the matching template under `folders.templates` so future notes inherit it. Match nearby notes for the other keys (for example `banner-height`, `banner-y`, `banner-x`, `content-start`). Preserve every other line. On macOS, iterate over files with `while IFS= read -r f`; BSD `grep -Z` does not NUL-separate its output.
8. **Clean up only when asked.** An old asset is unused only if no note, Base, canvas, CSS, script, or template references it. Generated transcripts and workspace state files do not count as references. Prefer a trash-backed delete over permanent deletion, and update any note that describes the removed path as current. Leave historical records as they are.
9. **Validate and report.** Run the vault's checker if it has one (compare against a baseline), and open one updated note for review. Report the new files and their sizes, the notes and templates changed, check results (including pre-existing warnings), and anything skipped or left for the user.

Do not stage or commit.
