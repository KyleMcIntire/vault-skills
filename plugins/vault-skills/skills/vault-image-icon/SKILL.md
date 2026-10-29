---
name: vault-image-icon
description: Turn a local image or a note's profile photo into a custom Obsidian Iconize file icon (an SVG that embeds the original image), assign it to a note, and avoid duplicate icon text from Pixel Banner or Pretty Properties. Use when the user wants an image-based icon, portrait icon, or photo icon on a vault note.
---

# Vault image icons

Embed the original raster image in a self-contained SVG, import it into an Iconize custom pack, and assign it to the requested note. This preserves the photograph; do not trace it into vector shapes, crop it, or rename the note unless requested.

## Config

Read `.vault-skills.yaml` at the vault root first (see `docs/CONFIG.md` in the vault-skills repo). This skill uses no required keys. Ask once for anything it cannot find on its own: the Iconize pack name, the frontmatter field that holds the icon, and the image to use. Offer to record answers in the file. The vault's own `CLAUDE.md` overrides this skill.

## Resolve and prepare

- Read the vault `CLAUDE.md` and the target note. Resolve the actual image from the user's reference or the note's `image` property. If several images are plausible, ask which to use. Keep private images local; never send them to external services.
- Inspect the installed Iconize version, its icon directory (`<vault>/.obsidian/icons/<pack>/`), the frontmatter field it reads (default `icon`), the note's existing icon assignment, and which decorative plugins are enabled. Read only the relevant configuration fields and never print credentials. Do not read plugin `data.json` files that could hold secrets; Iconize's own settings are the exception and only the fields you need.
- Inspect the image visually. The converter below supports PNG, JPEG, and GIF with the standard library only. For other formats use an available local conversion tool within the user's requested scope; report missing support instead of installing dependencies automatically.
- Pick a pack: reuse a portrait pack such as `people` for portraits, or choose a descriptive custom pack for other images. Check pack-prefix collisions before creating a pack: Iconize abbreviates a single-word pack to its first letter uppercase plus the second lowercase (`people` becomes `Pe`); a hyphenated pack uses the first letter of each component, with only the first uppercase. The icon filename must begin with an uppercase letter and use only letters and digits, for example `ContactPortrait.svg`. The ID is the pack prefix plus the filename stem, for example `PeContactPortrait`.

## Create the SVG

Run the bundled script from the vault root, using the skill's base directory that Claude Code shows when the skill loads. Use `python` on Windows and `python3` on macOS or Linux. The default is a dry run; add `--write` after inspecting the result:

```bash
python3 "<skill-directory>/scripts/image_to_svg.py" --image "<local-photo>" --pack people --output ".obsidian/icons/people/ContactPortrait.svg"
```

The script embeds the original bytes, uses the image dimensions as the SVG viewBox, supplies both `href` and `xlink:href`, and refuses to overwrite different existing content. The output reports the Iconize ID. Keep the pack prefix in the ID: it is required for lookup.

## Load and assign

- Prefer Obsidian's running app. Use `/vault-skills:obsidian-cli` when runtime access is available (or an Obsidian MCP server if one is connected). Load or import the custom pack before assigning its icon: creating a file on disk does not update Iconize's in-memory pack list.
- With runtime access, reload only Iconize when needed, then verify the pack and icon resolve through its API. Never restart Obsidian, and never reload the plugin hosting this session or the Local REST API plugin.
- Without runtime access, create the SVG and the persistent note property, then ask the user to toggle **Iconize** off and on or import the SVG with the custom pack's **+** button. State that rendering needs verification. A file existing on disk does not prove it renders.
- Set the Iconize frontmatter field to the complete ID. A note without that property can have its assignment cleared, after which Iconize's background cleanup may remove the unused SVG.
- Merge into existing properties and CSS classes, preserving all unrelated text. Use a frontmatter-aware patch when one is available, with a fresh document map and match check, and re-read the note afterwards. Some patch tools turn blank values into explicit `null`; restore only formatting changes the operation introduced.
- Notes written from the filesystem (bulk runs) do not get an assignment from the frontmatter property alone: Iconize keeps its own path-to-icon map, and when it loads it deletes pack SVGs that nothing is assigned to. So assign before reloading: through `obsidian eval`, set `plugin.data[<note path>] = <id>` for each note on `app.plugins.plugins['obsidian-icon-folder']` and `await plugin.saveIconFolderData()`, then write the SVGs, then reload only that plugin. Check each ID with `plugin.api.getIconByName(id)`, and check a minute later that the SVG files are still on disk. Reloading before assigning loses newly written SVGs.
- Do not edit a running plugin's `data.json` on disk as the primary assignment method: its in-memory state can overwrite the edit. If disk-only setup is necessary, preserve all settings, guard against concurrent changes, and explain that the plugin must load the new state.

## Prevent duplicate ID text

Several plugins can read the same `icon` property. Iconize renders the portrait, while Pixel Banner and Pretty Properties (if installed) may print the ID as text. Hiding only one of them does not fix the other.

For notes that should show only Iconize's portrait, merge a class such as `file-portrait-icon` into the note's `cssclasses`, and verify this rule exists in an **enabled** CSS snippet:

```css
.file-portrait-icon .banner-icon-overlay,
.file-portrait-icon .icon-wrapper,
.file-portrait-icon .title-icon-wrapper {
  display: none !important;
}
```

Reuse an existing rule rather than adding a duplicate; if none exists, offer to append this one to a snippet the user already enables, and ask which file. It hides Pixel Banner's overlays and Pretty Properties' wrappers without hiding Iconize's `iconize-title-icon`. Preserve existing CSS and note classes. If the user wants separate decorative banner icons, resolve the property conflict according to that preference instead of hiding them.

Do not rely on `icon-opacity: 0` alone: Pixel Banner has a code path that falls back to full opacity for zero. Do not change either plugin's global property mapping as a side effect.

## Verify and report

- Check that the generated SVG parses and its embedded image matches the source bytes. Verify that the persistent property, CSS class, enabled rule, pack ID, and assignment remain after a refresh.
- Inspect the filename icon and note header through runtime tools when available; otherwise ask the user to review the opened note. Separate configuration checks from visual confirmation.
- Run the vault's checker after structural note edits, if it has one, comparing against a baseline and reporting existing failures accurately. Open the target note for review.
- Do not stage, commit, move, or delete anything unless asked.
