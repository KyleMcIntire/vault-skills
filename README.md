<p align="center">
  <img src="vault-template/Media/Banners/home.gif" alt="Animated pixel-art banner: a cozy desk at night with bookshelves, a glowing crystal and a cat in the window" width="100%">
</p>

<h1 align="center">vault-skills</h1>

<p align="center">
  <b>An Obsidian vault that runs itself with Claude Code.</b><br>
  A starter vault, 20 Claude Code skills, the tooling that keeps it honest, and the thinking behind all of it.
</p>

---

Most note systems fail the same way: filing is a chore, so notes rot, and restarting a piece of work means touring six tools
to remember where you were. This repo is one answer that has held up in daily use. **Notes are records. Hubs and dashboards
are views over them. Templates are the schema. Claude does the filing and the briefing, and asks before it writes anything
that matters.**

It is three things you can take separately:

| | What | Start here |
| --- | --- | --- |
| 🗂️ | **A starter vault**: folders, 19 templates, hubs with live chart dashboards, Bases, animated pixel banners, a `CLAUDE.md` rules file, and fictional example notes so everything renders on first open | [`vault-template/`](vault-template/README.md) |
| 🧰 | **A Claude Code plugin** with 20 skills, configured per vault by one `.vault-skills.yaml` file | [Skills](#the-skills) · [Config](docs/CONFIG.md) |
| 📚 | **The design docs**: philosophy, tagging, aesthetics, workflows, architecture | [`docs/`](docs/README.md) |

## Quick start

1. **Get the vault.** Copy `vault-template/` somewhere and open it in Obsidian as a vault. Install the community plugins its
   [README](vault-template/README.md) lists (Dataview and Tasks are the must-haves; Pixel Banner shows the banners).
2. **Tell the skills about you.** Edit `.vault-skills.yaml` at the vault root: your name, folder names if you changed them,
   and whichever integrations you use (Jira, GitHub, Slack, mail). Every block is optional; the [config reference](docs/CONFIG.md)
   explains each key.
3. **Install the plugin.** In Claude Code, from anywhere:

   ```text
   /plugin marketplace add <path-or-git-url-of-this-repo>
   /plugin install vault-skills@vault-skills
   ```

   Skills then run as `/vault-skills:<name>`, and most also trigger on their own when you ask for what they do.
4. **Try one.** Open a terminal in the vault, run `claude`, and paste a messy paragraph about your day after
   `/vault-skills:ramble-to-project-tasks`. It shows a capture plan first and writes nothing until you approve.

## The skills

**Capture and records**

| Skill | What it does |
| --- | --- |
| `ramble-to-project-tasks` | Turns a brain dump (typed or a voice memo) into linked notes and real Tasks-plugin tasks, after showing you the plan |
| `meeting-recording-notes` | Recording in, speaker-labelled transcript and a finished meeting note out: TL;DR, decisions, your action items, what you're waiting on |
| `add-person` | Creates or fills in a person note, optionally with their photo and title from Slack |
| `jira-to-obsidian-sync` | One-way, incremental sync of your Jira issues into task notes, with comments as work-log entries. Never writes to Jira |

**Briefings and the daily loop**

| Skill | What it does |
| --- | --- |
| `work-on` | One command to (re)start a ticket or project: task note, Jira, PRs (with review coverage and failing checks), local branches, Slack and mail, then "do next" |
| `start-of-day` | Checks last night's plan against what actually happened overnight and briefs you on the day |
| `end-of-day` | Finds PRs and issues that need a comment, shows every draft with its reason, posts only what you pick, writes tomorrow's standup |
| `finish-task` | Verifies the work, updates the docs it made stale, files real follow-ups, and commits only on a yes |
| `get-news` | A daily digest of releases and security news ranked by what touches the versions you pin, plus weather |
| `mail-calendar` | Reads your Mac's local Calendar and Mail copies, read-only, for meetings, attendees and messages |

**Writing like you**

| Skill | What it does |
| --- | --- |
| `learn-preferences` | Reads what you've written since last time and keeps a profile of how you like work done, with evidence and confidence |
| `draft-in-voice` | Drafts Slack, Jira or PR text in your own voice from that profile, and saves drafts instead of posting |
| `pr-reactions` | Marks your PR announcements in Slack with a merged emoji once they merge |

**Look and feel, and Obsidian formats**

| Skill | What it does |
| --- | --- |
| `pixel-banners` | Renders animated pixel-art banners in the house style with the engine in `scripts/banners/` |
| `vault-image-icon` | Turns an image or profile photo into an Iconize file icon |
| `mermaid-image` | Renders Mermaid diagrams to themed PNG and SVG for places that can't render Mermaid |
| `obsidian-markdown`, `obsidian-bases`, `json-canvas`, `obsidian-cli` | References that keep Claude's Obsidian syntax correct (adapted from [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills), MIT) |

## Guardrails are the design

Letting an agent into your notes is only pleasant if you're never surprised by what it changed. Every skill here follows the
same rules, spelled out in the vault's `CLAUDE.md` and [`docs/philosophy.md`](docs/philosophy.md):

- **Read-only toward the outside world** (Jira, Slack, GitHub, mail) unless writing is the skill's job, and then only what you approve.
- **Preview before write.** Bulk tools need an explicit `--write`; skills show a plan or a diff first.
- **Facts, inferences and proposals stay apart** in anything generated, and a failed source is reported as a gap, never as "nothing found".
- **No commits, pushes, moves or deletes** unless you ask.
- **Honest checks.** `make check` reports what it can't verify instead of passing it.

## What's in the box

```text
.claude-plugin/marketplace.json   the marketplace this repo publishes
plugins/vault-skills/skills/      20 skills, each a SKILL.md plus helper scripts and a fictional test fixture
vault-template/                   the starter vault (open it in Obsidian)
docs/                             philosophy, tagging, aesthetics, workflows, architecture, setup, config
scripts/                          vault checker, link tools, area and vault maps, the pixel-banner engine, with tests
.vault-skills.example.yaml        the config file, filled in with fictional values
Makefile                          make all = lint, tests, strict link check on the template, privacy grep
```

## Development

```sh
make all            # lint + tests + strict link check on vault-template + privacy grep
make check VAULT=~/path/to/your/vault   # run the read-only checker on any vault
```

The scripts use only the Python standard library, except the banner engine (Pillow and numpy; its tests skip without them).
All examples use fictional people and the `acme.invalid` domain, which can never resolve, so an unedited example config can't
send credentials anywhere.

## Credits and license

MIT, see [LICENSE](LICENSE). The four Obsidian format skills are adapted from Steph Ango's
[obsidian-skills](https://github.com/kepano/obsidian-skills) (MIT; each keeps its own `LICENSE`). Icons in the docs refer to
[Twemoji](https://github.com/jdecked/twemoji) (CC BY 4.0) through the Iconize plugin. The pixel-art banners were made with the
engine in `scripts/banners/` and are released with the repo.
