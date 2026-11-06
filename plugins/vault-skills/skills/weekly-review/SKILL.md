---
name: weekly-review
description: Summarize the past 7 days of the owner's work as a weekly review and roundup. Gathers the week's PRs, Jira issues, standup entries, daily-note summaries, meeting notes, project and task-note changelogs, completed and upcoming vault tasks, calendar and Claude sessions, then writes a source-linked note in a Weekly Reviews folder beside the daily notes with a TL;DR, a shareable Shipped / In progress / Blockers roundup, wins, what's still open, patterns, and next week's priorities, and can save the roundup as a Slack draft. Use whenever the owner asks for a weekly review, weekly roundup, weekly recap, week in review, weekly status update, "what did I do this week", "summarize my week", or "the past 7 days", even if they don't name this skill.
argument-hint: "[work|all] [YYYY-MM-DD last day, default today] [Nd window, default 7d]"
allowed-tools: Bash(python3 -I *weekly-review/gather.py*), Bash(jq *), Bash(acli jira workitem view*), Bash(gh pr view*)
---

# Weekly review

Turn the past week into one review note the owner can read in two minutes, plus a short roundup they can share with the team. The skill reads from everywhere and posts nowhere: the only writes are the review note, the tasks the owner picks for next week, and an optional hub link.

## Configuration

Read `.vault-skills.yaml` from the vault root first (see the repo's `docs/CONFIG.md`), and the vault's own `CLAUDE.md`, which overrides this skill. If a needed value is missing, ask once and offer to save it into the file; never guess. Keys used here: `owner.name`, `folders.daily`, `folders.meetings`, `folders.tasks`, `folders.projects`, `folders.scratch`, `meetings.standup_title`, `meetings.standup_entry_heading`, `meetings.standup_hub_link`, `integrations.jira.site`, `.project_keys`, `.cli`, `integrations.github.org`, `.user`, `integrations.calendar_mail.provider`, `tags.work`, `tags.personal`, `safety.sensitive_dirs`, `safety.sensitive_tags`, `safety.never_commit`.

- Review notes: `<folders.daily>/<ISO year>/Weekly Reviews/<ISO year>-W<ISO week> Weekly Review.md`, named by the ISO week of the window's last day (the gatherer's `review_note`). If earlier reviews exist, match their format over the one below.
- Calendar: `/vault-skills:mail-calendar` when `integrations.calendar_mail.provider` is not `none`. If it fails, say so and carry on.
- Jira: the CLI in `integrations.jira.cli`. The gatherer assumes `acli`; with another CLI its `jira` section reports an error, so read the issues through that CLI instead.
- Scratch: `$CLAUDE_JOB_DIR/tmp/`, or `<vault>/<folders.scratch>/` when `$CLAUDE_JOB_DIR` is unset. On Windows, run `python` instead of `python3`.

Never stage, commit, push, move or delete vault files. Sensitive material (`safety.sensitive_dirs`, `safety.sensitive_tags`) is never interpreted, summarized beyond what a task says, or shared.

## 1. Pick the window and scope

Arguments: "$ARGUMENTS".

- **Scope.** `work` (default) covers meetings, tasks, projects and daily notes. `all` adds the rest of the vault (personal projects, home, finance, health tasks). Use `all` when the owner says "my week", "life", "personal", or asks for the full review.
- **Window.** The last day defaults to today, the length to 7 days (`7d`), so the window ends today and starts six days earlier. "Last week" or "the work week" on a weekend or Monday means the Monday to Friday just finished: pass `--end <that Friday> --days 5`. Say which range you picked in the heading.

## 2. Gather

```bash
python3 -I <skill-directory>/gather.py --scope <scope> --end <YYYY-MM-DD> --days <N> \
  --vault <vault> --org <integrations.github.org> --jira-site <integrations.jira.site> \
  --project-keys <ABC,DEF> --daily-dir <folders.daily> --meetings-dir <folders.meetings> \
  --tasks-dir <folders.tasks> --projects-dir <folders.projects> --standup-name "<standup title>" \
  --sensitive-dirs <safety.sensitive_dirs> --sensitive-tags <safety.sensitive_tags> \
  > "$CLAUDE_JOB_DIR/tmp/weekly-review.json"
```

Leave out flags whose value is unknown. Optional: `--hub-link`, `--entry-heading` (as in end-of-day, to find the owner's entry in each standup note), `--skip-dirs <A/,B/>` for folders to ignore, and `--skip github,jira,sessions` to leave a source out (for example when offline). It takes under a minute and prints one JSON document (around 200 KB for a busy week). Read it a section at a time, for example `jq '.github' "$CLAUDE_JOB_DIR/tmp/weekly-review.json"`, rather than the whole file at once. A section that failed holds `{"error": ...}`: report it under the sources line and carry on, and never fill the gap by guessing.

| Key | What it holds |
|---|---|
| `window`, `review_note`, `review_note_exists` | the range, scope, and target note |
| `previous_review` | the last review before this window and its **Next Week's Priorities** block, to check what got done |
| `github.authored_prs` | the owner's PRs active in the window: state, `merged_in_window`, `created_in_window`, `commits_in_window`, approvals, pending reviewers, checks, unresolved thread count, `jira_keys`, and the start of the body |
| `github.involved_prs` | others' PRs they reviewed or commented on (`my_reviews`, `my_comments`); `batch: true` groups one author's rollout across repos |
| `github.pushes_by_branch` | commit counts per branch, for work with no PR yet |
| `jira.touched` | issues the owner changed: status, `transitioned_by_me`, `resolved_in_window`, `created_by_me_in_window`, and their comments from the window (Markdown) |
| `jira.open_assigned` | everything still open and assigned to them |
| `standups` | each standup entry in the window plus the next one. The **Yesterday** sections are end-of-day's own daily summaries, so they are the best single source |
| `daily_notes` | each day's `summary` property, `mood`, and open inbox count; `path: null` means no note that day |
| `meeting_notes` | non-standup meetings with their TL;DR and decisions |
| `changelog_entries` | dated sections (`### #YYYY-MM-DD …`) from task notes, project notes and tracking notes (excerpted to 500 characters) |
| `tasks` | `completed_by_note` (ticked in the window, grouped), `due_soon` (open, overdue or due within 7 days of the last day). `sensitive: true` marks tasks in `safety.sensitive_dirs` or carrying `safety.sensitive_tags`; daily habits are left out of `due_soon` |
| `projects` | active, planning, blocked or paused projects with `next step`, and any reviewed in the window |
| `task_notes_touched`, `task_notes_by_key` | Jira key → task note and its `wikilink` |
| `claude_sessions` | first prompt of each Claude Code session, as leads only |

Then read the calendar for the window and for the week ahead through `/vault-skills:mail-calendar`: `meetings --day <first day> --days <N>`, then `meetings --day <day after last> --days 7`.

Use the past week for themes and load (a heavy meeting week, an upgrade weekend), not as accomplishments. Use the coming week for priorities the owner has to prepare for. If the script fails, list the calendar as unavailable.

Only when the data leaves a workstream unexplained, check the source directly with `gh pr view` or the Jira CLI. Slack is optional: if a blocker or decision is mentioned but not recorded in the vault, search the owner's own Slack messages for it with the Slack tools (load them with `ToolSearch`), and treat what you find as a lead to confirm.

## 3. Build the week's picture

Group everything into **workstreams**, normally one per Jira epic or parent issue, project, or recurring theme (a migration rollout, dependency updates, vault automation). A PR, its Jira issue, its task note's changelog, and the standup lines about it belong together. For each workstream, settle:

- **outcome this week**: merged, released, rolled out, closed, decided, unblocked. Use concrete numbers (clusters upgraded, tests passing, repos covered).
- **state now**: who or what it is waiting on, and the next step (the task note's next unchecked step, or the project's `next step`).

Then compare with `previous_review.priorities`: which of last week's priorities got done (`[x]`), dropped (`[-]`), or are still open. Mention the carry-overs in **Still Open**.

Rules, the same ones end-of-day uses:

- Every claim needs a source in the data. Don't credit work a Claude session merely mentions, or that only a meeting discussed.
- Work the owner reviewed and approved is still theirs; don't credit automation or other people for it.
- Reviews of others' PRs collapse into one line per batch or notable review. Routine meetings, admin and surveys stay out of the wins.
- A thin week gets a short review. Don't pad it.
- Separate facts from inference: patterns and friction are inference, so phrase them as such and tie each to the evidence.

In `all` scope, sensitive items (`sensitive: true`) appear only as what the task says was done or is due, never interpreted or turned into advice, and never in the shareable roundup.

## 4. Draft the note

Frontmatter, matching earlier reviews if there are any:

```yaml
---
date: <last day of the window>
type: Weekly Review
tags:
  - <tags.work>
---
```

In `all` scope add `<tags.personal>` as well.

Body (keep the headings; if the vault uses Iconize, add the icon shortcodes earlier reviews use, and no others):

```markdown
# Weekly Review — <Month D–D, YYYY>

> [!abstract] TL;DR
> - <the two or three outcomes that mattered most, and the one thing most at risk>

## Roundup

**Shipped**
- <one line per outcome, with PR and Jira links>

**In progress**
- <one line per active workstream and where it stands>

**Blockers**
- <only work waiting on someone else; leave out the label and list if none>

## Wins

- <wins with context: why it mattered, what it unblocked, and its sources> [[source note]] · [[source note]]

## Still Open

- <open threads, carry-overs from last week's priorities, overdue tasks from `due_soon`>

## Friction and Patterns

- <inferred patterns, each tied to evidence>

## Next Week's Priorities

- <filled in step 5>

## Questions for <owner.name>

- <only real open decisions; leave out the section if none>

---
Sources: <checked sources>; unavailable: <failed or skipped sources>.
```

Section rules:

- **Roundup** is the shareable status update, written for the team: five to ten one-line bullets in total, no sub-bullets, outcomes rather than activity ("Upgraded the four production clusters to `v1.36`", not "worked on the upgrade"). First person without the "I". It holds only work items.
- **Wins** is for the owner: it may hold vault and personal-project work in `all` scope, and may say why something mattered.
- **Links.** Link every PR as `[repo PR #123](url)` and every Jira key to its task note as `[[<note>|<KEY>]]` when `task_notes_by_key` has one, else to `https://<integrations.jira.site>/browse/<KEY>`. Link vault sources with the exact `wikilink` or path from the gather output; never invent note names. Daily notes link as `[[YYYY-MM-DD]]`.
- **Versions** go in inline code (`` `v1.36` ``).
- Leave out an empty section except the sources line.

## 5. Next week's priorities

Draft three to five candidates from the open work: open authored PRs needing approval or merge, blocked workstreams, `due_soon` tasks, projects' `next step`, last week's unfinished priorities, and meetings next week the owner must prepare for. Show them as a numbered list with the reason for each, then ask with `AskUserQuestion` (`multiSelect: true`, up to 4 options per question) which to add as tasks.

- Picked items become Tasks-plugin tasks under **Next Week's Priorities**, in the shape earlier reviews use, else `- [ ] <verb-first action> <links> <tags.work>` (or `<tags.personal>`), with a priority (`⏫`, `🔼`, `🔽`) if the owner gives one.
- Add a `📅` date only when the source has one (a Jira due date, a dated task, a scheduled meeting) or the owner names it. Never invent deadlines.
- When an item already exists as an open task elsewhere, link to it as plain text instead of creating a duplicate (`Already tracked in [[<source note>]]`).
- If the owner picks none, write the candidates as plain bullets under a `Candidates (not tracked):` line.

## 6. Write and link the note

- If `review_note_exists` is true, read the existing note, show what would change, and ask whether to replace it or merge into it. Never drop lines the owner wrote.
- Re-read the target right before writing. With the Obsidian MCP connected, create the note with it; otherwise use `Write`. Create the `Weekly Reviews` folder for a new year only if needed.
- If the vault has a hub that lists weekly reviews, add the new review to that list with an anchored edit and leave other notes alone. Obsidian Bases draw no graph edges, so a link in a note body is what connects the review to the hub.
- Run the vault's structural check if it has one (this repo's `scripts/check_vault.py --vault <vault>`, or the command the vault's `CLAUDE.md` names). Fix only what this note broke.
- Open the note for review (`/vault-skills:obsidian-cli`, or the Obsidian MCP) if a way exists.

## 7. Offer to share the roundup

Ask with `AskUserQuestion`: save the **Roundup** as a Slack draft (Recommended only if the owner has asked for a status update to share), copy it in chat only, or skip. For a draft, load `/vault-skills:draft-in-voice` with the `Skill` tool and follow its rules, with the destination channel or person the owner names; it saves a draft and never posts. Strip any icon shortcodes and Obsidian wiki-links from the shared text, turning task-note links into Jira URLs.

## 8. Report

End with:

- the review note path and its TL;DR
- the Roundup text, so the owner can check it without opening the note
- the tasks added for next week
- sources checked, and any that failed or were skipped, with the reason
- whether the hub list and the structural check were updated and passed

Leave `$CLAUDE_JOB_DIR/tmp/weekly-review.json` in place for follow-up questions.
