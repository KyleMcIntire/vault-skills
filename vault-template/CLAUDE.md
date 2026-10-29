# Vault rules for Claude

This is a private Obsidian vault of notes. These rules guide Claude Code (and any other agent) working in
it. Make focused, minimal changes and preserve the existing structure. A nested `CLAUDE.md` in a folder
adds to these rules and wins where the two differ, so read the ones along the path of the folder you are
about to change. Edit this file freely: it is yours.

## Layout

| Folder | Holds |
| --- | --- |
| `Daily Notes/` | One note per day, named `YYYY-MM-DD` |
| `Tasks/` | One note per issue or ticket, filed in a sub-folder per status |
| `Meetings/` | One note per meeting; recurring ones in `Meetings/Recurring/<Type>/` |
| `People/` | One note per person |
| `Projects/` | One folder per project, with a main note that has `type: project` |
| `Wiki/` | Durable reference notes |
| `News/` | Digests written by the get-news skill |
| `Preferences/` | Learned preferences and voice profile |
| `Templates/` | Note templates and the chart views in `Templates/Views/` |
| `Media/Banners/` | Banner images |
| `Local/` | Machine-local scratch; git ignores it |

Folder names are configured in `.vault-skills.yaml` at the vault root. If you rename a folder, change it
there, in the hubs and Bases that name it, and in `Templates/Views/hub-charts/*.js`.

## Preserve vault behavior

- Keep YAML frontmatter keys, indentation, wiki-links, embeds and heading anchors intact unless the request
  explicitly changes them.
- Preserve fenced `tasks`, `dataview`, `dataviewjs` and `base` blocks, and Templater expressions. Task
  metadata uses emoji markers such as `📅` (due), `✅` (done), `⏳` (scheduled) and `🔁` (repeat).
- Preserve property names, types and exact values that Bases and charts match. Project statuses are
  `💡 Idea`, `🧪 Planning`, `🟢 Active`, `⏸️ Paused`, `✅ Done` (see `Projects/Project Hub.md`); task statuses
  are `To Do`, `In Progress`, `Done`, `Won't Do`.
- Before creating a note, read the matching template in `Templates/` and a nearby note. Follow their
  style and frontmatter. If no template applies, match nearby notes instead of inventing a new schema.
- When you create a finished note directly, resolve placeholders such as `<% ... %>` and `{{date}}` using the
  real title and date. Do not guess missing source information. Keep the expressions when editing a template itself.
- Re-read the target immediately before editing. Use anchored edits and keep unrelated changes made by the
  user, Obsidian or scripts. If the file changed under you, re-read and adapt the patch.
- Read and write Markdown as UTF-8 and keep existing line endings.
- Do not reformat unrelated text or make broad link changes as a side effect of a small edit.

## Safety and privacy

- Treat the vault as private. Redact secrets (tokens, passwords, keys) instead of repeating them.
- Do not change `.obsidian/`, `.trash/` or any generated plugin data unless explicitly asked.
- For bulk updates, list or dry-run the files you intend to touch first.
- Do not stage, commit, push, rename, move or delete files unless explicitly asked. Move notes with
  Obsidian (or a link-aware tool) so links keep working.
- Treat credentials, API tokens and `.env` files as secrets. Never write them into notes.
- When delegating, give read-only work to other agents and keep all edits in one agent, so edits do not collide.

## Sensitive areas

Add one line per private area, and a nested `CLAUDE.md` inside the folder with the detailed rules. Examples
to adapt (the folders do not exist until you create them):

- `Health/`: preserve source dates, measurements and wording; do not give medical advice or send contents to
  external services without explicit permission. See `Templates/Optional - Health/`.
- `Work/` or your employer's folder: keep ticket identifiers and historical records exact; do not share
  content outside the vault without explicit permission.
- `Finance/`, `Documents/`: never copy account numbers or identifiers into other notes.

## Daily and standup conventions

- Create a daily note in `Daily Notes/` named `YYYY-MM-DD`, starting from `Templates/Daily Note Template.md`.
  After a month ends you may file notes into `Daily Notes/<year>/<month>/`; leave that move to the user.
- Each standup is its own meeting note, `Meetings/Recurring/Standup/YYYY-MM-DD Team Standup.md`, with
  Yesterday, Today and Blockers. Link a section as `[[2026-10-28 Team Standup#Today]]`. Other recurring
  meetings (1-1s, retros) follow the same one-note-per-session pattern under their own `Recurring/<Type>/`.
- Daily-note properties: `date`, `mood` (✅ Good, 👍 Normal, 🥱 Tired, 😬 Anxious, 😞 Rough), `summary`.
  Habits are recurring tasks tagged `#habit`, not a per-day checklist.
- Keep recorded facts, inferences and proposals separate in anything you generate. Link summaries to their
  source notes. Never invent decisions, task owners, deadlines or completion states.

## Working style

- Ask when a decision is the user's; otherwise pick the sensible default and say what you chose.
- Keep the active project's note current as you work: add dated changelog entries (newest first) for what
  changed, was decided or is still open, and bump `reviewed`.
- Link every person, project, issue and pull request mention to its note or page. Put a version number in
  inline code, such as `v1.2.3`.
- Long sessions get expensive. Suggest `/clear` or `/compact` at natural breaks, after the project note is
  up to date.

## Validation

- After structural edits, check that wiki-links resolve, frontmatter is closed (`---` pair), code fences are
  balanced, and no file has invalid UTF-8. The repository's `scripts/` folder has a vault checker; run its
  `--help` for flags.
- Separate problems that were already there from problems you introduced, and fix only your own. Report
  the checks you ran and any that failed or were unavailable; never call a failed check a pass.

## Skills

The vault-skills plugin adds these commands (run `/help` to see the installed set):

- `/vault-skills:start-of-day` and `/vault-skills:end-of-day` for daily planning and wrap-up
- `/vault-skills:work-on <issue or project>` to gather context and start work
- `/vault-skills:finish-task` to wrap up a session: verify, update notes, save follow-ups
- `/vault-skills:add-person`, `/vault-skills:ramble-to-project-tasks`, `/vault-skills:meeting-recording-notes`
- `/vault-skills:get-news`, `/vault-skills:learn-preferences`, `/vault-skills:draft-in-voice`
- `/vault-skills:obsidian-markdown`, `/vault-skills:obsidian-bases`, `/vault-skills:obsidian-cli`

Skills read `.vault-skills.yaml` for folder names, your name and integrations, then these rules. When a skill
and this file disagree, this file wins.
