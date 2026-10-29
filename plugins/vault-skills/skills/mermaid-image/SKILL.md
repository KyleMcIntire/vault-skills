---
name: mermaid-image
description: Render a Mermaid diagram to a clean themed SVG and PNG locally with pele and headless Chrome, so it can be attached to Slack, a ticket comment, a PR or a note, none of which render Mermaid code themselves. Use whenever a diagram, flowchart, sequence diagram, architecture or rollout-order picture would explain something better than text, when the user asks for a diagram or "mermaid" image, or to turn an existing mermaid code block into a picture, even if they do not name this skill. Never uploads or posts anything.
argument-hint: "[what to draw, or a path to a .mmd file] [light|dark|warm-light|warm-dark]"
---

# Mermaid image

Turn Mermaid text into an image the user can attach. Slack does not render Mermaid and GitHub, Obsidian and Confluence differ, so a PNG is the portable form. **Local only**: render and show, never upload, post or send.

## Setup and constants

Read `.vault-skills.yaml` at the vault root (see `docs/CONFIG.md`) for `folders.scratch`; nothing else in it is needed. Ask once if you must write into the vault and `folders.*` is missing.

- **Renderer:** `render.mjs` in this skill's folder (`SKILL_DIR`), run with `node`. If the environment variable `MERMAID_RENDERER` is set, run that script instead (a custom build with the same flags). It uses [pele](https://pele.run) (an npm library, MIT, no dependencies; it renders Mermaid text to themeable SVG) and a Chrome or Chromium in headless mode for the PNG. Chrome runs with a throwaway profile, so it never touches the user's open browser.
- **pele location:** `~/.local/share/pele` by default; set `PELE_DIR` to put it elsewhere. If it is missing, the script prints the install command: `mkdir -p ~/.local/share/pele && cd ~/.local/share/pele && npm init -y && npm install pele --ignore-scripts`. Run it once if asked; `--ignore-scripts` keeps install scripts off.
- **Browser:** the script looks for Chrome or Chromium at the usual macOS, Linux and Windows paths. Set `CHROME` to a browser binary to override, or pass `--no-png` for SVG only.
- **Output:** `$CLAUDE_JOB_DIR/tmp/mermaid/`, or `<vault>/<folders.scratch>/mermaid/` if unset. Copy into the vault (for example under the media folder) only when the user asks, with a descriptive filename.

## 1. Write the diagram

Draft Mermaid text for what the user described, or take their `.mmd` file or code block (a surrounding ```` ```mermaid ```` fence is stripped). Save it to `<output>/<name>.mmd`.

- Pele targets Mermaid 12.1 syntax and supports every built-in diagram type: `flowchart`, `sequenceDiagram`, `stateDiagram-v2`, `classDiagram`, `erDiagram`, `gantt`, `timeline` and the rest.
- Keep it readable at Slack width: left-to-right for short flows (`flowchart LR`), top-down only for tall ones; short node labels, quoted when they hold punctuation (`A["service #466"]`); no more than about 12 nodes before it should be split into two images.
- Use the real names, environments and order from the vault or the task, not guesses. Label an inference as one in the reply, not in the picture.
- Anything that will leave the vault follows the usual rules: no secrets, no customer content, and apply `safety.redact_identifiers` from the config (replace matching identifiers with neutral labels).

## 2. Render

```bash
node SKILL_DIR/render.mjs "<output>/<name>.mmd" --out "<output>" --name <name>
```

Options: `--theme warm-dark|warm-light|light|dark` (default `warm-dark`: warm greys with an orange accent; `warm-light` is the same for light mode; `light` and `dark` are neutral presets), `--theme-file theme.json` (a JSON object of pele variables such as `bg`, `fg`, `muted`, `line`, `surface`, `surface-alt`, `border`, `accent`, `series-1` to `series-8`; it overrides the chosen preset so a vault can match its own colours), `--scale 2` (pixel density, 2 is crisp for Slack), `--padding 24`, `--no-png` (SVG only). It prints one JSON line with the `svg` and `png` paths and the diagram size. A parse error from pele comes back on stderr: fix the Mermaid and re-run, and do not retry the same text.

**Give meaning with colour.** The themes only colour the neutral parts, so add meaning with `classDef` in the Mermaid text, using dark text on the fills: green `#a9b665` for done and healthy, yellow `#d8a657` for in progress or a decision, orange `#e78a4e` for production or a caution, red `#ea6962` for blocked or failing, blue `#7daea3` for outputs, purple `#d3869b` for people and asks. Example: `classDef bad fill:#ea6962,stroke:#ea6962,color:#2e261f` then `class S bad`. Colour sparingly and keep the meaning consistent within one diagram. If the vault has its own palette (check its `CLAUDE.md`), use that instead.

## 3. Check it

`Read` the PNG to look at it. Fix overlapping or cut-off labels, crossing arrows, and unreadably small text by shortening labels, changing direction, or splitting the diagram, then re-render. Say what the image shows in one line.

## 4. Hand it over

Give the PNG path (and the SVG path) and offer one next step: open it, copy it into the vault, or paste the Mermaid source into a GitHub PR or an Obsidian note, which render it natively. Drafted Slack messages cannot carry the image: say that the user attaches the PNG by hand, and refer to it in the draft text.

## Notes

- Pele has its own layout and look, so output differs a little from Mermaid.js. Features outside Mermaid 12.1 are not supported.
- The SVG has the theme baked in as CSS variables and also themes by variables (`--pele-bg`, `--pele-accent` and so on, see pele.run/theming), so a different palette is a theme file, or a change to `THEMES` in `render.mjs`.
- `fixtures/example.mmd` is a tiny fictional diagram for a smoke test: `node SKILL_DIR/render.mjs fixtures/example.mmd --out /tmp/mermaid-test --no-png`.
