# Aesthetics

A vault you enjoy opening is one you keep using, so looks are part of the design, not an afterthought. This page covers the theme, the icon system (Iconize with the Twemoji pack), animated pixel-art banners, CSS snippets, Pretty Properties, `cssclasses`, and a short list of do and don't rules that keep the whole thing consistent. Decoration is always optional: nothing here may change the meaning of a note, and anything a Base or query reads keeps its exact format.

## Theme

The starter uses one community theme (the author's choice was **Primary**) with the system light/dark setting and no translucency. Pick a theme once, with a built-in way to test it: keep a *Theme Preview* note in `Wiki/` that shows every heading level, text style, link type, code block (several languages), callout, list, task, table, quote and embed on one page. When you try a new theme, open that note and scan for anything that looks broken.

Keep the number of installed themes small. Every extra theme is another set of CSS variables your snippets might not match.

## Icons: Iconize and Twemoji

Iconize puts icons on files, folders and, through shortcodes, inside note text. The starter standardizes on the **Twemoji** pack for decoration, so the vault looks the same on every machine and in every theme.

### Shortcodes

An icon in text is written as a shortcode: the pack prefix plus the icon name.

```markdown
## :TwCalendar: This week
## :TwBooks: Reading list
- :TwPushpin: Pinned idea
```

| Prefix | Pack | Notes |
| --- | --- | --- |
| `Tw` | Twemoji | The default for headings and notes. Names are the Unicode name in CamelCase: `:TwCheckMarkButton:`, `:TwMagnifyingGlassTiltedLeft:` |
| `Li` | Lucide | Line icons, handy for folders and rules. Names are matched ignoring case and hyphens |
| `Fa…`, `Ib…` | Font Awesome, IconBrew | Built into Iconize; cannot be verified by `check_vault.py` |

### Prefix rules

- The prefix is **case-sensitive** and **two letters**; the icon name follows with no separator.
- A name that is not in an installed pack prints as raw text (`:TwNope:`). `scripts/check_vault.py` warns about every unknown `Tw` and `Li` shortcode, so run it after a batch of edits.
- Icon packs live in `.obsidian/icons/` (for example `twemoji.zip`). Obsidian Sync does not carry that folder, so a pack installed on one machine must be copied to the others (or restored from git) before its shortcodes render there.
- To set a note's own icon from frontmatter, use `icon: TwBooks` (no colons). Some themes and plugins also need a `cssclasses` entry to avoid showing the icon twice.

### Why shortcodes for decoration, exact values for function

This is the rule that matters most. **Decoration uses shortcodes. Function keeps its exact format.**

| Kind | Example | Rule |
| --- | --- | --- |
| Decorative icon in a heading or list | `## :TwRocket: Launch` | Use a shortcode |
| Task metadata | `📅 2026-10-20` `✅ 2026-10-21` `🔁 every week` | Never replace; the Tasks plugin parses these emoji |
| Property value a Base filters on | `status: 🟢 Active` | Never replace; the Base matches the exact text |
| Heading that other notes link to | `[[Note#Done]]` | Do not rename for looks; anchors are text |

Typed emoji are fragile in decoration (they render differently per operating system) and fragile in function (a one-character difference breaks a filter). Shortcodes solve the first problem; leaving functional markers alone avoids the second. Do not swap existing icons wholesale; change them when you touch the note, or in a deliberate, previewed pass.

## Animated pixel-art banners

Banners are 1800x300 looping GIFs at the top of hub notes, daily notes and note types, shown by the **Pixel Banner** plugin. They are small pixel-art rooms with a lit window, a plant and a mug, and a label that says what the note is. They give each area a recognisable face and make a long vault feel like a place.

### Where they live

```
Media/Banners/
  <hub>.gif                 one per hub
  Note Types/<type>-note.gif
  Daily/<weekday>.gif
```

A note opts in through frontmatter:

```yaml
banner: Media/Banners/Note Types/reference-note.gif
banner-height: 200
banner-y: 50
content-start: 101
```

`banner-y` and `banner-x` choose the focal point when a wide pane crops the image; `content-start` is the pixel where text begins.

### How the engine works

`scripts/banners/` draws each frame in code, with no image assets:

1. **A tiny canvas** (`pix.py`) offers rectangles, discs, lines and a 3x5 pixel font on a small logical grid (360x60 for thin banners).
2. **A scene function** takes a frame number and returns one array. Scenes are pure functions of time, built so the last frame leads into the first: anything that moves is a sine or cosine of the loop position.
3. **The GIF writer** scales each frame five times with nearest-neighbour (so pixels stay crisp), builds one shared palette for the whole loop (so colours never flicker) and writes with no dithering.
4. **A preview step** renders a strip of frames and a sheet showing how Pixel Banner will crop the image at several pane widths, with the content-start line drawn in. The note-type renderer also asserts that the loop is periodic and that the label is never cropped.
5. **Layouts** (`note_banner_layouts.json`) hold the per-type focal point and label shift.
6. **Themes** (`hub_themes.py`) recolour the wall and wood families of a room into named palettes, so many hubs share one scene but read as different rooms.

Always render to a scratch folder, review the previews, and only then copy GIFs into `Media/Banners/`. The `/vault-skills:pixel-banners` skill wraps this workflow. Pillow and numpy are required for rendering only.

## CSS snippets

Snippets are small CSS files in `.obsidian/snippets/`, switched on under Settings, Appearance. The starter ships one, [`home-dashboard.css`](assets/snippets/home-dashboard.css), which:

- widens a page to the full pane when its frontmatter has `cssclasses: [home-dashboard]`;
- lays callouts of the made-up `multi-column` type side by side, wrapping on narrow panes;
- styles the stat tiles a dashboard script renders;
- hides duplicate decorations on notes that use an image icon, and the doubled icon Iconize can produce in a link.

Keep snippets few, commented at the top with what they do and which `cssclasses` or callout they hook, and built on the theme's CSS variables (`--background-secondary`, `--interactive-accent`) so they follow the theme.

## Pretty Properties and `cssclasses`

**Pretty Properties** restyles the properties panel: colours for values, hiding rarely used keys, and optional cover, banner and icon decorations. It changes only how properties *look*, never what they hold.

**`cssclasses`** is a frontmatter list that attaches CSS classes to one note, which is how a snippet targets a single page:

```yaml
cssclasses:
  - home-dashboard
```

Use a class instead of editing a theme, so a theme change does not lose your layout.

## Do and don't

| Do | Don't |
| --- | --- |
| Decorate headings with `:Tw…:` shortcodes | Paste typed emoji into new headings |
| Keep Tasks markers and status values byte-for-byte | "Tidy" `📅` or `🟢 Active` into a shortcode |
| Run `check_vault.py` after bulk icon edits | Assume every pack is installed on every machine |
| Use one banner style per note type | Give each note a different banner |
| Render banners to a scratch folder first | Overwrite a banner in place without a preview |
| Hook snippets on `cssclasses` | Restyle global elements with `!important` |
| Keep the theme preview note up to date | Install a theme without opening it |

[Back to the index](README.md)
