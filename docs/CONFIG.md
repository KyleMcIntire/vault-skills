# Configuration: `.vault-skills.yaml`

Every skill in this plugin reads one optional file at the **vault root**: `.vault-skills.yaml`.
Copy `.vault-skills.example.yaml` from this repo's root and edit it. A skill that needs a value
that is missing must **ask the user once** (and offer to write the answer into the file), never guess.

## How a skill finds the config

1. Vault root = the nearest parent of the current directory that holds `.vault-skills.yaml`,
   else the nearest one that holds `.obsidian/`, else the current directory.
   In scripts, honor the `VAULT_ROOT` environment variable first, then do the search above.
2. Parse `.vault-skills.yaml` (YAML). Missing file or key: use the default shown below, or ask.
3. Read the vault's own `CLAUDE.md` (and nested ones) for house rules. They override the skill.

## Keys

```yaml
owner:
  name: "Your Name"            # how notes name you, and how speakers/authors are labelled
  note: "[[Your Name]]"        # wiki-link to your person note ("" if you have none)
  aliases: ["Your", "YN"]      # short forms to link to the note

folders:                       # vault-relative; defaults in parentheses
  daily: "Daily Notes"         # (Daily Notes)
  tasks: "Tasks"               # one note per issue/ticket (Tasks)
  meetings: "Meetings"         # (Meetings); recurring ones under <meetings>/Recurring/<Type>/
  people: "People"             # one note per person (People)
  projects: "Projects"         # (Projects)
  wiki: "Wiki"                 # durable reference notes (Wiki)
  news: "News"                 # digests written by get-news (News)
  preferences: "Preferences"   # learned preferences and voice profile (Preferences)
  templates: "Templates"       # (Templates)
  banners: "Media/Banners"     # (Media/Banners)
  scratch: "Local"             # machine-local, not synced or committed (Local)
  attachments: "Media/Attachments"  # downloaded photos and files (Media/Attachments)
  # optional record folders used by ramble-to-project-tasks; leave out the ones you don't keep
  comms: "People/Comms"        # calls and conversations
  events: "Events"
  places: "Places"
  recipes: "Recipes"
  trips: "Trips"
  vehicles: "Vehicles"
  documents: "Documents"
  health: "Health"             # sensitive; see your vault's CLAUDE.md
  repos: "~/Repos"             # where your local git clones live (outside the vault; used by work-on)

templates:                     # file names inside folders.templates; skip a key to use the built-in layout
  daily: "Daily Note Template.md"
  meeting: "Meeting Template.md"
  task: "Task Template.md"
  person: "Person Template.md"
  project: "Project Template.md"
  standup: "Standup Template.md"

task_statuses:                 # task-note status values and the sub-folder each lives in (all optional)
  todo: "To Do"
  in_progress: "In Progress"
  done: "Done"
  wont_do: "Won't Do"

integrations:                  # every block is optional; a skill that needs a missing one reports a gap
  jira:
    site: "<your-site>.atlassian.net"
    project_keys: ["ABC"]      # keys that identify tickets in text
    user_email: "you@example.com"
    cli: "acli"                # or "jira-cli"; how to reach Jira from the shell
    display_names: []          # your Jira display name(s), to find your own comments
  github:
    org: "your-org"
    user: "your-login"
  slack:
    workspace: "your-workspace"
    announce_channel: "#announce-prs"   # where you post PR announcements
    team_handle: "@your-team"           # mention used in PR announcements
    user_id: ""                         # your Slack member ID (U...), for searches of your own messages
    merged_emoji: "merged"              # reaction pr-reactions adds once a PR is merged
    second_reaction: []                 # optional extra rules for pr-reactions (see its SKILL.md)
  confluence:
    site: "<your-site>.atlassian.net"
  catalog:                     # service catalog / team directory (Backstage, Cortex, ...), optional
    kind: "backstage"
  calendar_mail:               # how to read mail and calendar; see the mail-calendar skill
    provider: "macos"          # macos | none
  mail:
    helper_script: ""          # optional script that prints sent mail as JSON (see learn-preferences references)
  weather_location: "City, Region"      # for the news digest
  news_feeds:                  # extra RSS/Atom URLs and Slack channels for get-news
    rss: []
    slack_channels: []

meetings:
  standup_title: "Team Standup"     # standup note name after the date: "<date> Team Standup.md"
  standup_entry_heading: ""         # optional heading inside the standup note for your own entry
  standup_hub_link: ""              # optional wiki-link added to the top of each standup note

tags:
  work: "#Work"                # added to work tasks and notes
  personal: "#Personal"

sections:
  task_inbox: "Task Inbox"     # heading in the daily note where new follow-ups go

people:
  groups: []                   # optional sub-folders of folders.people (e.g. Work, Friends); default: discover existing ones

safety:
  never_commit: true           # skills never stage, commit or push unless you ask
  redact_identifiers: []       # patterns (e.g. "CVE-\\d{4}-\\d+") to replace with labels in outbound drafts
```

## Rules every skill follows

- **No identity baked in.** Never hardcode a person's name, username, home path, company, ticket prefix,
  workspace, org, repo or team. Use `owner.*`, `integrations.*` and `folders.*`, or ask.
- **No absolute paths** in prose or scripts. Use `<vault>` in prose and `$VAULT_ROOT` (resolved as above) in scripts.
- **Cross-skill references** are written `/vault-skills:<name>` (the plugin is `vault-skills`).
- **Read-only toward outside systems** (Jira, Slack, GitHub, mail, calendar, catalog) unless the skill's purpose
  is to write and the user approves each write. Keep that wording from the original skills.
- **Scratch files** go in `$CLAUDE_JOB_DIR/tmp/` when set, else `<vault>/<folders.scratch>/`.
- Keep the vault-safety rules the originals state (preview before write, re-read before editing,
  anchored edits, no staging/committing/moving/deleting unless asked).
- Example names in docs and sample notes must be obviously fictional ("Alex Example", "Acme", "ABC-123").

## Scripts

Python in this repo uses only the standard library (plus whatever a skill's own `SKILL.md` lists, e.g. Pillow for banners).
There is no YAML parser in the standard library, so **scripts never parse `.vault-skills.yaml`**. Instead:

- A script takes `--vault <path>` (default: `$VAULT_ROOT`, else search upward as above).
- Any other value from the config arrives as an explicit flag or environment variable
  (for example `--jira-site`, `--github-org`, `GITHUB_ORG`). `SKILL.md` tells Claude to read the YAML and pass them.
- A script with a missing required value exits with a clear message naming the flag; it never falls back to someone's real value.

## Repo layout (binding for all contributors)

```
.claude-plugin/marketplace.json
plugins/vault-skills/{.claude-plugin/plugin.json, skills/<name>/...}
vault-template/            starter vault: copy it, open it in Obsidian (folders, templates, hubs, views, CLAUDE.md)
docs/                      philosophy, tagging, aesthetics, workflows, config
scripts/                   vault-level tooling (checker, link tools, banner engine) with tests
.vault-skills.example.yaml
```

`vault-template/` folder names must match the defaults above (Daily Notes, Tasks, Meetings, People, Projects,
Wiki, News, Preferences, Templates, Media/Banners, Local).

## Environment variables

| Variable | Used by | Meaning |
| --- | --- | --- |
| `VAULT_ROOT` | all scripts | Vault root; overrides the upward search. |
| `VAULT_SKILLS_BANNERS` | pixel-banners | Path to the banner engine. Default: `scripts/banners/` in this repo checkout. |
| `PIXEL_BANNERS_VENV` | pixel-banners | Optional virtualenv with Pillow and numpy for the engine. |
| `CLAUDE_JOB_DIR` | all skills | When set, scratch files go in `$CLAUDE_JOB_DIR/tmp/`. |

> **Examples never use a real domain.** Sample configs and test fixtures use `acme.invalid` (the `.invalid` TLD can never resolve),
> so running a script against an unedited example fails at DNS and never sends your `JIRA_TOKEN` anywhere.
