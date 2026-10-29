---
name: jira-to-obsidian-sync
description: "One-way incremental sync of your Jira issues into an Obsidian vault's tasks folder. Creates missing task notes, fixes statuses and status folders, and copies new Jira comments into notes as work-log entries, tracked by a watermark state note. Use whenever the user asks to sync, refresh, pull or update their Jira tasks or task notes in Obsidian, or to catch the vault up with Jira, even if they don't say \"sync\". Never writes to Jira."
argument-hint: "[optional: issue keys to force-reconcile]"
---

Make reasonable choices without asking, and put every judgment call in the final report.

Sync Jira issues assigned to the vault owner into the vault. This is a **one-way sync: Jira to Obsidian.** Never write to Jira: no comments, no transitions, no edits. The only writes are to the vault.

This is an **incremental** sync. Most runs should touch almost nothing. If you find yourself fetching comments for an issue that hasn't changed, or reading a note you have no reason to edit, you've skipped a short-circuit.

## Setup: read the config first

Read `.vault-skills.yaml` at the vault root (see the plugin's `docs/CONFIG.md`) and the vault's own `CLAUDE.md`. Values used here:

| Need | Config key | If missing |
| --- | --- | --- |
| Jira site host | `integrations.jira.site` | ask once, offer to save it |
| Project keys (for linking keys in text) | `integrations.jira.project_keys` | ask, or link any `[A-Z][A-Z0-9]+-\d+` |
| Shell access to Jira | `integrations.jira.cli` (`acli`) and `integrations.jira.user_email` | only needed on the fallback path |
| Task root | `folders.tasks` (default `Tasks`) | use the default |
| People notes (reporter links) | `folders.people` (default `People`) | use the default |
| Task template | `folders.templates` + `templates.task` | use [references/task-note-layout.md](references/task-note-layout.md) |
| Status values and folders | `task_statuses` (`todo`, `in_progress`, `done`, `wont_do`) | defaults `To Do`, `In Progress`, `Done`, `Won't Do` |

Derived paths (all vault-relative):

- Task root: `<folders.tasks>/`
- State note: `<folders.tasks>/.sync-state.md` unless the vault says otherwise. Layout: [references/state-note.md](references/state-note.md).
- Status folders: `<folders.tasks>/<status value>/`

Rules that apply the whole run:

- Do **not** stage, commit, push, or delete anything in the vault's git repo. Never touch hidden folders (`.obsidian/`, `.trash/`) or attachment folders.
- Re-read a note immediately before editing it. Use anchored edits; never rewrite existing work-log text.
- Paths contain spaces and apostrophes (such as `Won't Do`); always quote them.

## Vault access

Prefer an Obsidian MCP server or the Obsidian CLI for note-level work when one is connected, because their move operations rewrite links across the vault. Otherwise use the filesystem. Check once at the start, use one method per edit, and say which you used in the report.

- Moves and renames: use the link-aware move if available; otherwise `mkdir -p` then `mv -n` (never overwrite). Verify with `ls`.
- Frontmatter edits: a frontmatter-patch tool if available, otherwise an anchored `Edit` on the one line.
- Everything else (creating notes, work-log entries) is plain file writes.

## Jira access

**Check once, at the start, and use one method for the whole run.** Say in the report which one it was.

1. **An Atlassian/Jira connector** (preferred), if the session has one signed in to the configured site. Its tools may be deferred; load the issue-search and issue-get tools together with one tool-search call.
2. **`acli` fallback**, only when no connector is found and `acli jira auth status` succeeds. Query through the read-only helper `jira_acli.py` next to this file, which only runs `acli jira workitem search` and `view` plus REST GETs. Run it with `python3 -I`:

   ```bash
   H="${CLAUDE_PLUGIN_ROOT}/skills/jira-to-obsidian-sync/jira_acli.py"
   python3 -I "$H" --site <integrations.jira.site> --email <integrations.jira.user_email> search '<JQL>'
   python3 -I "$H" --site <site> --email <email> issue <KEY> [<KEY> ...] [--no-description]
   ```

   Never run an `acli` command that writes (`create`, `edit`, `transition`, `comment create`, `assign`). `JIRA_TOKEN` (environment only) enables web links and pull requests; without it those come back as an error object, which you report and leave the matching properties untouched.
   - `search` returns `issues` (`key`, `summary`, `status`, `status_category`, `updated`, `resolutiondate`, `parent`) in the JQL's order, plus `hit_limit` (true at the 100-result cap).
   - `issue` adds `reporter`, `story_points`, `related_jiras`, `web_links`, `prs`, `description` and `comments` (`author`, `created`, `markdown`, `unsupported`). `unsupported` lists ADF node types that were flattened (tables, media); when it is not empty, read that item raw with `acli jira workitem view <KEY> --fields comment --json` and rebuild what was lost. `comments_truncated` means treat the issue as failed. An issue that failed comes back as `{"key", "error"}`.

If neither works, report that and stop without touching the state note. If `acli` is installed but not logged in, tell the user to run `! acli jira auth login --web`.

## Step 0: Read the state note

Read the state note. It holds `watermark` (newest Jira `updated` already processed), `forceKeys` (keys to reconcile regardless; add any keys the user passed as arguments), a **Fingerprints** table (`key | jira status | updated | comments | note`, the change-detection cache and the authoritative key-to-note map), **Known noise projects**, **Ambiguous key to note mappings**, and **Open follow-ups**. Carry follow-ups forward verbatim unless resolved; report them, never act on them.

**If the note is missing or `watermark` is blank, this is a bootstrap run**: use the fallback queries in Step 1b and create the note from [references/state-note.md](references/state-note.md).

## Step 1a: Delta query (the normal path)

One JQL search, at most 100 results:

```
assignee = currentUser() AND project NOT IN (<noise projects>) AND updated > "<watermark minus 2 hours, formatted yyyy/MM/dd HH:mm>" ORDER BY updated ASC
```

Example: watermark `2026-10-02T09:27:10.635-0500` gives `updated > "2026/10/02 07:27"`. JQL reads the time in the user's Jira timezone, which matches the watermark's offset, so do not convert to UTC and always use the watermark's own offset. Omit the `project NOT IN` clause when there are no noise projects.

The 2-hour buffer absorbs clock skew and mid-run edits; re-seeing a synced issue is free because its fingerprint matches. Request only `summary`, `status`, `updated`, `parent`; **not** `description` or `comment` here.

Zero issues and empty `forceKeys` is an **empty-delta no-op**: go to Step 5's no-op branch and report one line. If the response is too large for the tool, hand the temp file to a read-only subagent and ask for a compact table (`key | summary | status | statusCategory | updated | resolutiondate`) rather than reading it yourself.

## Step 1b: Fallback queries (bootstrap only)

1. Open work: `assignee = currentUser() AND project NOT IN (<noise>) AND statusCategory != Done ORDER BY updated DESC`
2. Recent changes: `assignee = currentUser() AND project NOT IN (<noise>) AND updated >= -30d ORDER BY updated DESC`

If a query hits the cap, check what is filling it. Bulk-edit noise (many issues sharing one `updated` timestamp, with old `resolutiondate`) belongs in the noise table rather than being paginated. Report any project key you add.

## Step 2: Triage before doing any work

Working set = every issue from Step 1, plus every key in `forceKeys`.

**Short-circuit** when the key is not in `forceKeys`, a fingerprint row exists, and its `jira status` and `updated` both equal what the query returned: do nothing, count it.

**Otherwise** fetch that issue's detail: summary, status, updated, description, comments, parent, reporter, story points, issue links; web links and pull requests come from the remote-links and dev-status endpoints (the helper script does these on the `acli` path). Include `updated` so a `forceKeys` issue still gets a fingerprint. Fetch each yourself, in parallel batches of three or four. Do not delegate comment fetches to a subagent: it has to retype every body and long comments get cut off. Read comment bodies in full.

If everything short-circuited, this is an **all-short-circuit no-op**: Step 5's no-op branch, one-line report, skip Steps 3, 4 and 6.

## Step 3: Inventory the vault (only if Step 2 found work)

One shell call listing every task note's `url` and `status` frontmatter line (first match only, so note bodies are not read):

```bash
cd "<vault>/<folders.tasks>" && grep -rH -m1 --include='*.md' -E '^url: *https?://' . ; echo ===; grep -rH -m1 --include='*.md' -E '^status:' .
```

Match Jira keys to notes by the `url` property, never by filename. Reconcile with the fingerprint table's `note` paths; if a recorded path is gone, the note was moved by hand, so re-resolve it by `url`. If one `url` maps to several notes, resolve by (1) the canonical path in the ambiguous-mappings table, (2) the fingerprint row's path, (3) the note whose filename matches the summary; record or correct a row in the ambiguous table and report it.

## Step 4: Reconcile

For each issue that needs reconciling:

- **Note is missing**: create it (see Conventions). Closed issues get notes too if the work happened.
- **Status differs**: update the `status:` line (and `dateModified`). Move the file only if the note has **no `parent` property** and does **not own a container subfolder** of sub-tasks. If it owns one, use the parent-folder rule below. Sub-tasks never move on their own.
- **A parent's status changed**: move the parent's whole folder, sub-tasks included, under the folder for the new status, then update the `note` path of every fingerprint row pointing into it, including sub-tasks that short-circuited.
- **Reporter missing or different**: set `reporter:` (see Conventions), directly after `url:` if absent. Backfill only notes you are already editing.
- **Open steps / Mentions sections missing**: insert them (see Body structure) above the `---` preceding the work-log heading, only on notes you are already editing; never move existing text to make room.
- **Story points, PRs, related Jiras, links, Slack threads**: refresh from the detail data. `story points` is overwritten from Jira. The four lists are merged additively: add missing URLs, never remove or reorder existing entries (the user adds some by hand). Write `related jiras` as `https://<site>/browse/<KEY>` URLs. Web links on a `slack.com` host go in `slack threads`, all others in `links`. If a source holds `{"error": ...}`, leave that property untouched and report it. Bump `dateModified` only when a value changed.
- **Description changed materially**: rewrite only the description portion (under the Description heading, down to the `---` above Open steps). Shift the description's own headings down one level outside fenced code. Preserve everything under the work-log heading; that is the user's own writing. If the change is substantive (approach reversed, scope added), add a dated work-log entry saying what changed.
- **New Jira comments**: add each as a work-log entry dated to the comment's created date, with the full substance (code blocks, command output, findings, links, reasoning). A one-line summary loses the point. Skip a comment only if the existing work log already covers it: same date and same substance, even under a different heading; do not rely on the fingerprint's `comments` count, which does not survive deleted comments. Give each synced comment an H4 `#### <short title> (Jira comment, HH:MM)` inside its date entry, newest first when several share a date. A comment that says it supersedes earlier ones still becomes its own entry; the work log is history, and the description rewrite is where current state goes.
- **Parent status changed**: also add a one-line `Jira sync:` note to that day's entry saying what moved (old to new status, folder move). Same for any sub-task whose status changed.
- **Filename is stale**: rename only when the summary text itself changed. Do not rename over differences from the sanitization rules, an omitted issue key, a leading bracketed tag, or a sub-task ordinal prefix.

Never delete a note, and never remove existing work-log content.

## Conventions

**Frontmatter**: copy the vault's task template (`folders.templates` + `templates.task`) exactly. If there is none, use [references/task-note-layout.md](references/task-note-layout.md). Required for every note: `type: task`, `status`, `url: https://<site>/browse/<KEY>`. Match sibling notes for tags and `project`. `next step` is the user's own pointer: leave it blank on creation and never overwrite it. Bump `dateModified` only on notes you actually changed (ISO 8601 with the local offset in force today).

**Reporter**: the Jira reporter's `displayName`, linked to their person note under `<folders.people>/`. Match the note's filename first, then its `aliases`; link with the note's filename, not Jira's spelling (diacritics and short names differ). Resolve each distinct name once per run. If no person note matches, write the plain name unlinked, never a dangling link, and add a follow-up suggesting `/vault-skills:add-person` for them.

**Status vocabulary** (values from `task_statuses`; the frontmatter `status` and the sub-folder name are both the value):

| Jira status | `status` and folder |
| --- | --- |
| Done | `task_statuses.done` |
| In Progress, Testing, any other in-progress category | `task_statuses.in_progress` |
| Backlog, To Do | `task_statuses.todo` |
| Not Going To Do, Won't Do | `task_statuses.wont_do` |

When a Jira status has no exact vault equivalent (such as `Testing`), map it by status **category** and record the real Jira status in a work-log line so the nuance is not lost.

**Folder invariant** (the second rule overrides the first):

1. A note **without** a `parent` property lives **under** its status folder, either directly in it or inside a container subfolder named after the note or after its issue key. Both are fine and are not drift.
2. A note **with** a `parent` property lives in its parent's folder, whatever its own status. A to-do sub-task under an in-progress parent's folder is correct; do not "fix" it or report it.

**Body structure**: see [references/task-note-layout.md](references/task-note-layout.md). Key points:

- H1 is the Jira summary; omit the issue key from the H1 and the filename.
- **Description** holds only the Jira description, headings starting at H3 so the section folds as one.
- **Open steps** and **Mentions** are views, not content: copy them exactly from the template and never write into them. If the vault has no such views, omit those two sections.
- Work-log entries run **newest first**. A newer entry goes directly under the work-log heading (after its `---` line if it has one); an older one goes at the correct date position. Anchor each edit on a unique existing line. Match whatever heading the note already has (`## Work-log` or `## Work Log`); if there is none, add the scaffold.
- Strip inline backticks from identifiers in prose but keep fenced code blocks intact. Convert Jira smartlink wrappers (`<custom data-type="smartlink" ...>`) to plain Markdown links.
- Sub-tasks live in a folder named after the parent note, next to it, with an ordinal prefix reflecting execution order (`1. <summary>.md`). If a parent is a flat file and sub-tasks must be added, create the sub-tasks first, then move the parent into the new folder.
- **Filenames** cannot contain `:` or `/`: replace `:` with ` - ` and `/` with `-` or ` & `, and keep the original text in the H1.
- People referenced by name get wiki-links, matching how existing notes do it.
- **Jira keys are always hyperlinked** in the report, the state note and note bodies: `[ABC-123](https://<site>/browse/ABC-123)`. Exceptions: filenames, H1 headings, frontmatter values, and text inside code. Do not double-wrap.

## Step 5: Update the state note

**No-op branch** (empty delta or all short-circuited): do not rewrite the note. Edit only the frontmatter lines: `lastRun` and `dateModified` to now; on an all-short-circuit no-op also set `watermark` to the newest `updated` seen (so the query window does not creep wider); on an empty-delta no-op leave `watermark` alone. Then report one line.

**Normal branch**: re-emit the entire note (it is rewritten wholesale): frontmatter, prose, fingerprints, noise projects, ambiguous mappings, and open follow-ups. Drop a follow-up only when resolved.

- Add or update a fingerprint row for every issue you reconciled. Leave short-circuited rows alone except for path corrections forced by a parent folder move. Do not add or update a row for an issue that failed.
- `forceKeys` becomes `[]` minus any key that failed.
- Watermark: let `S` = newest `updated` among issues processed or short-circuited and `F` = earliest `updated` among failed ones. No failures: `watermark = S`. Otherwise `watermark = min(S, F minus one second)`. Never let it pass unfinished work.
- Write the watermark exactly as Jira returns it, milliseconds and offset included.
- Set `lastRun`, `dateModified`, and `issuesTracked` (row count).

If the run aborts before Step 4, leave the note untouched. If it aborts partway through Step 4, still write it with the normal branch; the per-issue rules make a partial run safe to resume.

## Step 6: Verify, then report

Skip verification on a no-op run. Otherwise re-run the full Step 3 inventory (both halves) and confirm the folder invariant for every note you wrote and that every `note` path in the fingerprint table exists.

Report, grouped: issues in the delta and how many short-circuited; notes created; statuses corrected (old to new); comments synced (key and count); reporters set or left unlinked; files moved or renamed; issues with no note and why; noise or ambiguous-mapping changes and follow-ups carried forward; new follow-ups (keys that synced comments mention as new work but that are not assigned to the user). State the Jira access method and vault access method used. Be explicit about every judgment call (filename sanitization, ambiguous status mapping, inferred ordering). A no-op report is a couple of lines.

## Out of scope

- Notes for issues in the noise projects table, or other clone/boilerplate tickets.
- `.base` files.
- Reorganizing notes that have no `url` property, even if status and folder disagree; list them under follow-ups.
- Writing to Jira, under any circumstances.
