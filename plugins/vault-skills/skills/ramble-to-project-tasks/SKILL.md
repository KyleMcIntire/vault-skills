---
name: ramble-to-project-tasks
description: "Turn one of the user's brain dumps (typed, pasted or a voice memo, work or personal) into linked Obsidian records and real Tasks-plugin tasks. It files people, conversations, events, places, recipes, trips, vehicles, documents, ticket updates and project updates into existing notes, creates missing ones from the vault templates, and attaches each task to its project. It shows one capture plan for confirmation before writing and keeps the raw ramble in the daily note. Use whenever the user rambles, brain-dumps, dictates, says \"capture this\", \"file this\", \"log this\", \"get this out of my head\", \"turn this into tasks\", or pastes or records a stream of thoughts and wants it in the vault, even if they do not name this skill. It records only: it never executes the tasks, writes to the ticket system, or posts anything."
argument-hint: "[ramble text | path to a voice memo]"
---

# Ramble → notes and tasks

People talk in streams: a work update, a thing to buy, a call with a relative, an idea for a project, all in one breath. Your job is to split the stream into facts, file each fact where it already belongs in the vault, turn real commitments into tasks, and leave a trail back to what was actually said. It records and links. It never does the tasks, writes to Jira, or messages anyone.

## 0. Config

`SKILL_DIR` is this skill's base directory. Read `.vault-skills.yaml` at the vault root (see `docs/CONFIG.md`) and the vault's own rules file (`CLAUDE.md`); the rules file wins over anything here. This skill uses `owner.name`, `folders.daily`, `folders.tasks`, `folders.people`, `folders.projects`, `folders.meetings`, `folders.templates`, `templates.*`, `task_statuses.*`, `integrations.jira.*` and `integrations.calendar_mail`. Several record kinds (events, places, recipes, trips, vehicles, documents, communications, health) have no required folder: use the folder the vault already has for that kind (see `references/records.md`), and if the vault has none, file the item under the nearest person or project note or the task inbox instead of inventing a folder. If a needed value is missing, ask once and offer to write the answer into the config.

## 1. Get the ramble

- **Text:** use what the user typed or pasted, verbatim.
- **Voice memo** (`.m4a`, `.mp3`, `.wav`, ...): transcribe it with the `/vault-skills:meeting-recording-notes` environment. This needs an Apple Silicon Mac with ffmpeg; without it, ask the user to paste a transcript. There is one speaker, so skip the embedding and speaker steps:

  ```bash
  bash <meeting-recording-notes SKILL_DIR>/scripts/setup_env.sh
  RUN=~/.cache/meeting-notes/runs/<yyyy-mm-dd>-ramble-<hhmm>
  HF_HOME=~/.cache/meeting-notes/hf ~/.cache/meeting-notes/venv/bin/python \
    <meeting-recording-notes SKILL_DIR>/scripts/transcribe.py "<audio>" \
    --out-dir $RUN --prompt "<names and jargon likely in the ramble>"
  ~/.cache/meeting-notes/venv/bin/python -c "import json,sys; print(''.join(w['w'] for w in json.load(open(sys.argv[1]))).strip())" $RUN/words.json
  ```

  Run the transcription in the background. Apply the obvious fixes from that skill's `references/term-corrections.json` (and `.local.json`), then delete `$RUN/audio.wav`. Apple's Voice Memos folder is blocked without Full Disk Access; if `ls` fails there, ask the user to share the memo to a folder.
- **The date** is today (`date +%Y-%m-%d`) unless the user says the ramble is about another day. Resolve every relative date ("tomorrow", "Friday", "next week") against that date, and write only absolute dates. For a date tied to a work meeting ("before my 1:1", "at Thursday's office hours"), find the occurrence in the user's calendar if `integrations.calendar_mail` is configured (for example with `/vault-skills:mail-calendar`: `meetings --day <date> --days 14 --search "<title word>"`); otherwise ask. Report the resolved date as an inference.

## 2. Split it into items

Read the whole ramble before filing anything. Break it into items, and give each one a kind from `references/records.md`: person fact, conversation, event, place, recipe, trip, vehicle, document, ticket update, project update, new project, task, or health note. One sentence can produce several items ("Called Sam about the trip, need to book flights by Friday" is a conversation, a trip update and a task).

For each item, keep three things apart:

- **Recorded facts:** what the user said happened or is true.
- **Commitments:** what they said they will do, or must do. Only these become tasks.
- **Ideas and maybes:** "maybe I should", "it would be cool if". These go into notes as ideas (an ideas section of a project, or a bullet), never as tasks, unless the user asks.

Never invent an owner, a deadline, a status or a completion. If the user says someone else will do something, record it as a fact about that person, not a checkbox for the user.

## 3. Find where each item belongs

Reuse before you create. For every person, place, project, ticket and record named in an item, search first:

- If an Obsidian MCP server is connected, use its property/tag/link search for properties and links (for example `type: project`), and its simple search for names.
- Otherwise, if the Obsidian CLI works (`obsidian version`), use `obsidian search query='[type:project]' format=json` for property lookups.
- Otherwise use the filesystem: `find <folders.people> <folders.projects> <folders.meetings> -iname "*<word>*"` and `grep -rli` on the name. People are often filed by first name or role ("Mom", "Dad"), so search for both.
- **Ticket keys** (`ABC-123`, matching `integrations.jira.project_keys`) or ticket names: find the task note under `<folders.tasks>` by its `url:` property. If none exists, do not create one by hand; tell the user to run `/vault-skills:jira-to-obsidian-sync` (or `/vault-skills:work-on <KEY>`) and keep the item for later.
- **Projects:** match against `<folders.projects>/<Name>/<Name>.md` (`type: project`) and any sub-items nearby. A loose name ("the banner thing") still counts as a match if only one project fits; say which one you picked.

Pick a destination for each item using `references/records.md`. When two destinations fit equally, choose the more specific one (a trip over a place, an existing project over the task inbox).

## 4. Show the capture plan and confirm once

Before writing anything, show the user a compact plan:

```markdown
| # | Item (their words, trimmed) | → Destination | Change |
| --- | --- | --- | --- |
| 1 | "called Sam about Thanksgiving" | [[2026-03-11 Call with Sam]] *(new, communication)* | create |
| 2 | "book flights by Friday" | [[Thanksgiving 2026]] → actions section | task 📅 2026-03-13 |
| 3 | "PR 408 got approved" | [[Fix queue worker - ABC-140]] → Work-log | append |
```

Then ask one `AskUserQuestion` with **Write it (Recommended)**, **Change something** (they type what in Other), and **Only the tasks**. Ask follow-up questions only for things you truly cannot infer, such as an unknown person's relationship or which of two projects they mean, and put them in the same call (at most four questions).

Skip the confirmation only when every change is a small append to an existing note (no new notes, no new projects, at most three tasks), and say what you did afterwards.

## 5. Write

Follow the vault's rules file: re-read each target immediately before editing, use anchored edits, and preserve everything else in the note. If an Obsidian MCP is connected, prefer its heading-anchored patch for appends under known headings (reject if the content already exists, so a rerun does not duplicate) and its write for new notes. Otherwise use `Edit` and `Write`.

1. **Keep the raw ramble.** Append it to today's daily note, `<folders.daily>/<YYYY-MM-DD>.md` (older notes may be filed into year/month sub-folders, so check both; the Obsidian CLI's `daily:path` gives today's path when available), under a `## Rambles` heading at the end. Create the heading if it is missing (match the icon style of nearby headings). Use a collapsed callout with a block ID, so records can link back to it:

   ```markdown
   > [!quote]- Ramble · 14:32
   > <verbatim text, or the transcript>
   ^ramble-1432
   ```

   If today's daily note does not exist, do not create one from this skill. Put the raw text in your reply instead and tell the user. If they create it later in the session, append the block then and add the link-backs. Skip this step for health content (see below).
2. **Update existing notes** first, then **create new ones** from the template named in `references/records.md` (inside `<folders.templates>`). Read the template and nearby notes first, keep the frontmatter keys in order, and resolve every Templater expression (`<% ... %>`, `{{date}}`). Leave fields the user did not give blank; do not guess them.
3. **Link back.** Every appended entry and new note gets a source link: `([[<YYYY-MM-DD>#^ramble-1432|ramble]])`.
4. **Tasks** use the Tasks plugin format: checkbox, one fitting emoji, the description, a link to the record when the task sits elsewhere, the tag, then the dates.

   ```markdown
   - [ ] :TwAirplane: Book Thanksgiving flights [[Thanksgiving 2026]] #Personal 📅 2026-03-13
   ```

   - Use the work and personal tags the vault already uses (look at existing tasks; `#Work` and `#Personal` are the fallback) so the right dashboard query picks them up.
   - Add `📅` only when the user gave or implied a date. Do not add `⏳`, `🔁` or priorities unless they said so.
   - Put a task in the record it is about (a trip's actions section, a project's next-up list, a ticket note's newest work-log day). A task that belongs to nothing goes in today's daily note under its task-inbox heading.
   - Before adding a task, check that the same open task is not already there.
5. **New projects** come only from something multi-step or ongoing that the user frames as a project ("I want to start...", "new project:"), and only after they confirm it in the plan. Create `<folders.projects>/<Name>/<Name>.md` from `templates.project`, with the status values and `category` values the vault already uses (look at the existing project notes or Base), a one-sentence `summary`, and `started`/`reviewed` set to today. Put the first steps in the next-up section and ideas in the ideas section. A single errand is a task, not a project.

**Health:** anything about symptoms, medication, appointments or providers goes into the vault's health area (if any), in an existing note when one fits, with the user's wording, dates and measurements preserved. Do not copy it into the daily ramble block, do not add advice, and do not send it anywhere. Appointments can still become tasks.

**Never** write to Jira, Slack or email, rewrite another skill's sections (for example the standup entry that `/vault-skills:end-of-day` maintains), mark anything done that the user did not say was done, move or rename notes, or touch `.obsidian/`, attachments or the trash.

## 6. Check and report

- Run the vault's checker if it has one (look in the rules file; for example `python3 scripts/check_vault.py`). Only new unresolved links or errors are yours.
- Open the most important new or changed note (the Obsidian MCP's `open_file`, or `obsidian open path="<note>" newtab`).
- Reply briefly:
  - what was filed where, as a list of wiki-links with *(new)* or *(updated)*
  - the tasks added, with due dates
  - anything left unfiled and why (no task note yet, ambiguous project, the user declined)
  - anything you inferred, such as a matched project or a resolved date

Do not stage or commit.
