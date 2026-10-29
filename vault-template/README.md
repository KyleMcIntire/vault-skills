# Starter vault

A ready-to-open Obsidian vault: folders, note templates, hubs with live charts, Bases, a `CLAUDE.md`
rules file and a few fictional example notes. Copy this folder, open it in Obsidian, and replace the examples.

## Open it

1. Copy `vault-template/` somewhere and rename it (for example `~/Notes`).
2. In Obsidian choose **Open folder as vault** and pick the copy.
3. Turn off Restricted mode (**Settings, Community plugins**) and install the plugins below.
4. Edit `.vault-skills.yaml` (your name, folder names, integrations), then `CLAUDE.md`.
5. Delete the notes tagged `example` (search `tag:#example`) once you have your own.

Nothing under `.obsidian/` is shipped, so your settings stay yours.

## Core plugins to enable

Daily notes (folder `Daily Notes`, template `Templates/Daily Note Template`), Templates is optional (see
below), Bases, Properties, Backlinks, Outgoing links, Graph view, Tags, Search, Quick switcher, Page preview.

## Community plugins

| Plugin | Needed for |
| --- | --- |
| **Dataview** (turn on *Enable JavaScript Queries*) | the dashboards in `Templates/Views/` and every hub |
| **Tasks** | the task queries in the daily note, Home and person notes; the `📅 ✅ ⏳ 🔁` markers |
| **Templater** | the `<% tp... %>` expressions in most templates (set template folder to `Templates`) |
| **Iconize** | optional icons. Add the Twemoji pack (**Settings, Iconize, Icon packs, add predefined pack: Twemoji**) to use `:TwName:` shortcodes as in `docs/aesthetics.md`; headings here use none, so nothing breaks without it |
| **Obsidian Git** | optional backup |
| **Linter** | optional formatting |
| **Pixel Banner** | shows the animated pixel-art banners on Home, every hub and the note templates (`banner` property); without it the property is ignored |

## How templates work

- `Daily Note Template.md` uses the core placeholders `{{date}}` and `{{date:dddd}}`, so the core Daily notes
  plugin fills it in. Templater leaves those alone, so either works.
- Every other template uses Templater expressions. Insert one with the Templater command, or
  set a folder template. Each template starts with a comment saying so; delete the comment in the finished note.
- Only the five templates named in `.vault-skills.yaml` (`daily`, `meeting`, `task`, `person`, `project`) are
  looked up by skills; the rest are for you.
- `Templates/Optional - Health/` is structure only (property names and headings, no content). Delete it if unused.

## Folders

`Daily Notes`, `Tasks` (one sub-folder per status), `Meetings` (recurring ones in `Recurring/<Type>`),
`People`, `Projects`, `Wiki`, `News`, `Preferences`, `Templates`, `Media/Banners`, `Local`. Each has a hub note
(`Home.md` links them all). `Local/` is git-ignored scratch.

## Vocabulary the charts rely on

| Property | Values |
| --- | --- |
| Project `status` | `💡 Idea`, `🧪 Planning`, `🟢 Active`, `⏸️ Paused`, `✅ Done` |
| Task `status` | `To Do`, `In Progress`, `Done`, `Won't Do` |
| Meeting `meeting type` | `standup`, `planning`, `review`, `1-1`, `ad-hoc` |
| Meeting `status` | `✅ Closed`, `⌛ Waiting on others` |
| Person `relationship` | `me`, `coworker`, `manager`, `family`, `friend`, `other` |
| Daily `mood` | `✅ Good`, `👍 Normal`, `🥱 Tired`, `😬 Anxious`, `😞 Rough` |

The charts and Bases match these strings exactly. To change one, edit it in the template, the hub's `.base`
file and `Templates/Views/hub-charts/<hub>.js` (each file lists the properties it reads in its header).

## Use with Claude Code

Open the folder in a terminal, run `claude`, and install the plugin from this repository's marketplace so the
`/vault-skills:<name>` commands are available. `CLAUDE.md` holds the vault's house rules.
