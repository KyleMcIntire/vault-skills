# Obsidian setup

This is the set of Obsidian plugins the starter vault is designed around, how to keep two machines in step, and how an assistant can reach a running vault. Everything here is optional except Obsidian itself: the notes are plain Markdown and open anywhere. Turn on the core plugins first, add the few community plugins that carry the design (Tasks, Dataview, Iconize, Pixel Banner), and add the rest only when you feel the need.

## Core plugins

Enable these under Settings, Core plugins.

| Plugin | Purpose |
| --- | --- |
| Properties | Edit frontmatter as typed fields; the base of the records-with-views design |
| Bases | `.base` files: live tables and cards over notes filtered by folder and property |
| Daily notes | Creates the day's note from your template in the daily folder |
| Templates | Inserts a template; use alongside a community templating plugin for dynamic fields |
| Backlinks, Outgoing links | See what links to and from a note |
| Graph view | Visual map of links; useful for spotting orphans |
| Canvas | Spatial maps; the map builders write Canvas files |
| Tag pane | Browse and audit tags; the first stop for a [tag cleanup](tagging.md) |
| Page preview | Hover a link to read the note |
| Bookmarks, Workspaces | Pin the notes and layouts you return to |
| Command palette, Quick switcher, Slash commands | Keyboard-first navigation |
| Outline, Word count | Navigate long notes |
| File recovery | Local snapshots; a cheap safety net |
| Sync | Optional first-party sync (see below) |

## Community plugins

Install from Settings, Community plugins. Descriptions are the authors' own.

| Plugin | Purpose | Priority |
| --- | --- | --- |
| **Tasks** | Track tasks across the vault with due dates, recurrence, done dates and filtering queries | Core to the design |
| **Dataview** | Query notes like a database; powers dashboards and chart scripts | Core to the design |
| **Iconize** | Add icons to files, folders and text via `:Tw…:` shortcodes | Core to the design |
| **Pixel Banner** | Banner images at the top of notes, including animated GIFs | Core to the design |
| **Style Settings** | Adjust theme, plugin and snippet CSS variables from a UI | Recommended |
| **Pretty Properties** | Restyle the properties panel: colours, hidden keys, cover and icon decorations | Recommended |
| **Homepage** | Open a chosen note, Base or workspace on startup, such as `Home` | Recommended |
| **Linter** | Format YAML, headings, spacing and lists consistently on save | Recommended |
| **Omnisearch** | Fast full-text search with ranking, including PDFs and images | Recommended |
| **Git** | Version control with scheduled backup | Recommended for a backup |
| **Local REST API with MCP** | A secure REST API and Model Context Protocol server for the vault | Optional, for assistant access |
| **Buttons** | Buttons in notes that run commands, open links or insert templates | Optional |
| **Templater** | Dynamic template fields such as dates and prompts, if your templates use `<% %>` | Optional |
| **Checkbox Chime** | Sounds when tasks are completed or cancelled | Optional, fun |
| **Recent Files** | List files by most recently opened | Optional |
| **Various Complements** | IDE-style word completion | Optional |
| **PDF++**, **Media Extended**, **Image in Editor** | Annotate PDFs, play media, and show images and embeds inline | Optional, by need |
| **Terminal** | Shells inside Obsidian | Optional |

Two caveats worth knowing:

- Plugin settings files can contain tokens (the REST API key, for one). Never share, paste or commit them, and keep `.obsidian/plugins/*/data.json` out of public repositories.
- Some sync setups do not carry the *list of enabled* community plugins between machines, though they do carry installs and settings. Enable plugins on each machine.

## Theme and snippets

Pick a theme under Appearance and enable `home-dashboard` from [the snippet](assets/snippets/home-dashboard.css) if you use the Home dashboard. See [aesthetics](aesthetics.md).

## Sync and git: who carries what

Use sync for convenience and git for history, and never let them race.

| Data | Carried by |
| --- | --- |
| Notes, attachments, Obsidian settings | Obsidian Sync (or your file sync) |
| Icon packs in `.obsidian/icons/` | Not carried by Obsidian Sync; copy them or restore from git |
| Hidden folders (`.claude/`, plugin folders) and history | Git |
| Machine-local files | Nothing; keep them in `Local/` |

Practical rules:

- Pick **one committer** machine. It runs the backup (the Git plugin or a `make backup` target) and pushes.
- Other machines pull before they work, and commit **by explicit path** only, never with a blanket `git add -A`, so a machine that lacks some tracked files cannot record their deletion.
- Pull on the committer before its next backup if another machine pushed.
- Disable the Git plugin on machines that are not the committer, so a git pull does not race the file sync.
- `.gitignore` the `Local/` folder, workspace state you do not want in history, and any plugin `data.json` that holds secrets.
- Skills never stage, commit or push unless you ask (`safety.never_commit` in the config).

## Assistant access: MCP and CLI

An assistant can work on the vault straight from the filesystem, but a running Obsidian offers better tools. Prefer them for note-level work, and fall back to files when they are unavailable.

### MCP (Local REST API with MCP)

- Enable the plugin and add its MCP endpoint to your assistant's configuration. Use the plain-HTTP localhost URL the plugin shows if the HTTPS one fails on its self-signed certificate.
- It works only while Obsidian is running, and cannot see hidden folders such as `.obsidian/` or `.claude/`.
- Use it for searches that need Obsidian's index (properties, tags, links), for moves and renames that must rewrite links, for patching a frontmatter value or a heading section, and for opening a note for review.
- Do not mix MCP and filesystem writes for one edit. Use files for bulk or scripted edits, hidden folders, git and `scripts/`.

### Obsidian CLI

The `obsidian` command talks to the running app. Probe it with `obsidian version`. It can print today's daily note path, move a note with links updated, list backlinks and unresolved links, search by property, show what a Base returns, and open a note in a new tab. The `/vault-skills:obsidian-cli` skill documents syntax and the few commands never to run (anything that reloads the app or disables the API plugin).

### Safety

- Treat the vault as private and plugin settings as secrets.
- Do not edit `.obsidian/`, `.trash/` or `Local/` unless asked.
- Let a human approve moves, renames and deletes. Deleting through the API should be a deliberate act, and scratch files should be removed permanently so nothing lingers in the trash.

[Back to the index](README.md)
