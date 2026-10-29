---
name: end-of-day
description: End-of-workday wrap-up. Reviews the PRs and Jira issues the owner touched today, drafts the comments or description updates they need and posts only the ones approved, then writes the next standup day's entry (what was done today as Yesterday, tomorrow's focus as Today) in the standup folder. Invoke explicitly as /vault-skills:end-of-day.
argument-hint: "[YYYY-MM-DD workday to wrap up, default today]"
disable-model-invocation: true
allowed-tools: Bash(python3 -I *end-of-day/gather.py*), Bash(python3 *end-of-day/adf.py*), Bash(acli jira workitem view*), Bash(acli jira workitem search*), Bash(acli jira auth status*), Bash(gh pr view*), Bash(gh pr diff*), Bash(gh pr list*), Bash(make check*)
---

# End of day

Wrap up the owner's workday in three passes: check the day's PRs and Jira issues for missing comments or stale descriptions, post the approved fixes, then write the next standup entry.

## Configuration

Read `.vault-skills.yaml` from the vault root first (see the plugin's `docs/CONFIG.md`), and the vault's own `CLAUDE.md`, which overrides this skill. If a needed value is missing, ask once and offer to save it into the file; never guess. Keys used here: `owner.name`, `folders.meetings`, `folders.tasks`, `folders.daily`, `folders.templates`, `folders.scratch`, `templates.*`, `integrations.jira.site`, `.project_keys`, `.cli`, `integrations.github.org`, `.user`, `integrations.slack.*`, `integrations.calendar_mail.provider`, `safety.redact_identifiers`.

- Standup notes: one per day, `<folders.meetings>/Recurring/Standup/YYYY-MM-DD <standup title>.md`. Ask once for the title if unknown. Never edit an index note listing them.
- Jira: the CLI in `integrations.jira.cli`. The gatherer and the posting commands below assume `acli` (`acli jira workitem …`). If `acli jira auth status` fails, ask the owner to run `! acli jira auth login --web`; don't fall back to curl. With `jira-cli`, the gatherer's `jira` section will report an error: read and post through `jira issue view/comment add/edit` instead, with the same draft-and-approve flow.
- Jira bodies are Atlassian Document Format (ADF) JSON. `adf.py` next to this file converts between ADF and Markdown (`to-md`, `from-md`, `check`). Draft in Markdown, show the Markdown, and convert to ADF only to post.
- GitHub: `gh`, logged in as `integrations.github.user`.
- Calendar: `/vault-skills:mail-calendar` when `integrations.calendar_mail.provider` is not `none`. If it fails, say so in the report and carry on.

**Nothing is posted without approval.** Never stage, commit, push, move or delete vault files. Re-read any note immediately before editing it, and use anchored edits.

## 1. Gather

```bash
python3 -I <skill-directory>/gather.py --vault <vault> --org <integrations.github.org> \
  --jira-site <integrations.jira.site> --project-keys <ABC,DEF> --meetings-dir <folders.meetings> \
  --tasks-dir <folders.tasks> --standup-name "<standup title>" \
  --standup-template <folders.templates>/<standup template> > "$CLAUDE_JOB_DIR/tmp/end-of-day.json"
```

Arguments: "$ARGUMENTS". If that holds a date, add `--date YYYY-MM-DD` so a missed day can be wrapped up the next morning. Leave out flags whose value is unknown. Optional: `--hub-link <text>` (the line after which the owner's entry starts in a standup note, for example a link to a meeting hub) and `--entry-heading "<exact H2>"` (the section holding the owner's entry in notes made from a recording); without them the entry starts after the note's H1. `--no-sessions` skips reading local Claude Code session prompts, which are otherwise used as leads. Then `Read` the JSON file. If `$CLAUDE_JOB_DIR` is unset, use `<vault>/<folders.scratch>/` for it and for the scratch files in step 5. The script is read-only and takes about 30 seconds. Any section that failed holds `{"error": ...}`. Report it, carry on with the other sources, and never guess at missing data.

What's in it:

- `workday`, `next_standup`: the next standup rolls Friday to Monday. If the next workday is a holiday or day off, the owner can say so; then use that date instead.
- `github.authored_prs`: open PRs plus PRs updated today. Signals: `commits_after_body_edit`, `unresolved_threads` (`awaiting_me` is true when someone else spoke last), `others_comments_since_my_last`, `checks`, `review_decision`, `pending_reviewers`, `title_has_jira_key`, `jira_keys`.
- `github.involved_prs`: others' PRs the owner reviewed or commented on today, or that directly request their review. `batch: true` entries collapse a bulk rollout of one author across many repos.
- `github.pushes_today`: branches pushed, to catch work with no PR yet.
- `jira.touched_today`: issues the owner changed today. Each has `description` and `comments_today` rendered as Markdown, `description_unsupported` (ADF nodes the Markdown can't round-trip), `transitioned_by_me_today`, and `my_last_comment_at`. `acli` returns no changelog, so field edits other than status don't show. `jira.open_assigned`: all of the owner's open issues.
- `standup.today_entry`: today's entry, without the morning brief, including today's `### Today` plan. `standup.next_entry` is set if the next entry already exists.
- `task_notes_by_key`: Jira key to task note and a ready-made `wikilink`. Issues created today usually have no note yet, because the Jira sync only creates one when it has run.
- `vault_tasks_completed_today`, `task_notes_touched_today`, `claude_sessions_today`: hints for work that leaves no PR or Jira trace. Treat sessions as leads only; confirm from another source before claiming anything, and ignore personal or vault-maintenance sessions.

Then check the next standup day against the calendar (via `/vault-skills:mail-calendar`: meetings for that date, including declined):

- If that day has an all-day out-of-office or holiday event, or no meeting whose title contains "standup", tell the owner and propose the next day that has one (search the following seven days). Use their answer as the entry's date.
- Keep the meeting list for the **Today** section and the report: meetings the owner must prepare for, and invites with `my_response` `no response` or `tentative`.

## 2. Build the day's picture

Group the activity into **workstreams**, normally one per Jira issue or parent epic, so a PR, its Jira issue and its task note land together. Match PRs to issues through `jira_keys`. For each workstream, note:

- what happened today: PRs opened, pushed, merged or reviewed, review feedback addressed, transitions, tests run, new tickets filed
- where it stands now: status, who it waits on, and the next step

Compare the result with today's `### Today` plan. Planned items with no activity carry forward to tomorrow unless dropped (`[-]`) or completed.

When the data doesn't explain a change, check the source directly with `gh pr view`, `gh pr diff` or the Jira issue, rather than inferring. Do not describe work that isn't backed by a source.

## 3. Find what needs a comment or a description change

Check each **authored PR active today**: created, pushed, merged, reviewed or commented on. Open PRs untouched today get only the reviewer and CI checks, for tomorrow's plan.

- **Stale description.** If `commits_after_body_edit` is non-empty, read those commits (`gh pr diff`, `gh api repos/{repo}/commits/{sha}`) and check that the body still matches. Look for behaviour lists, dropped or added scope, test counts, file/line counts, and the SHA it says was tested. Propose a minimal edit that keeps the owner's sections and wording. Never rewrite a body that is still accurate.
- **Unanswered review threads** (`awaiting_me`). If a later commit addresses the comment, draft a short reply: `Fixed in <sha>: <what changed>.` If it is a question, draft an answer. If neither, make it a tomorrow item and don't draft a reply. Never resolve threads.
- **Unanswered PR comments** (`others_comments_since_my_last`). Draft a reply only where someone asked something or asked for something.
- **Title/Jira link.** If the title has no Jira key, or the body doesn't link the issue, propose a fix that follows the repo's own convention. Check two or three recent PRs in that repo, since prefixes differ (`ABC-123: …` or `[ABC-123] …`).
- **Failing checks / changes requested.** No comment; it becomes a tomorrow item.

For **involved PRs**, there's nothing to post. An open PR with `commits_since_my_last_review` needs a re-review tomorrow. Open direct review requests updated in the last 14 days are tomorrow candidates; mention the count of older ones only.

Check each **Jira issue** in `touched_today`, plus any key behind a PR active today:

- **Progress without a comment.** If the issue saw real progress today and `my_last_comment_at` is before today, draft a comment. Real progress means a PR opened, merged or updated with substance, review feedback addressed, or a test or rollout result. Sprint, story-point and link edits don't count.
- **Description drift.** If the work now differs from the description (scope dropped or added, a different fix, acceptance criteria met or changed), draft a minimal edit to the affected lines only. For issues created today, check for a problem statement, a fix and acceptance criteria, following the shape of the owner's other issues.
- **Status drift.** A merged PR on an issue that isn't in a testing or done status, or an open PR on a backlog or to-do issue: propose a transition. Leave Done issues alone unless they closed today with no closing note.

### Writing style

Before the first draft, load `/vault-skills:draft-in-voice` with the `Skill` tool if it is installed and follow its voice and linking rules. Its draft-only rule doesn't apply here: step 4 still asks, and step 5 posts only what is picked. Match the owner's existing comments and descriptions (read a recent one from the same issue when unsure). Use short, plain, past-tense sentences. Lead with what changed and where it stands, and give concrete numbers (test counts, environment names, SHAs). No filler, no headings for short comments, no "As discussed" or summaries of the obvious.

If `safety.redact_identifiers` lists patterns, replace matching identifiers in anything outward-facing with neutral labels (for example `ID-HIGH-1`) and keep the real identifiers only in the vault.

- **Jira (Markdown, converted to ADF):** use only what `adf.py` supports: paragraphs, `## headings`, `-` bullets (nest with two spaces), fenced code, `**bold**`, `*italic*`, `` `code` ``, and `[text](url)` links. Link PRs as `[PR #12](https://github.com/acme/widgets/pull/12)` and keys as `[ABC-123](https://acme.invalid/browse/ABC-123)`. For example:
  ```markdown
  Review addressed in [bd41fde](https://github.com/acme/widgets/pull/12/commits/bd41fde) on [PR #12](https://github.com/acme/widgets/pull/12):

  - `parse_flags` accepts only `true` or `false` in all three helpers.
  - The cache moves on to the next key after a failed read.

  New tests cover each change. 21/21 pass locally, and CI is green.
  ```
- **GitHub (markdown):** replies are one or two sentences. Description edits keep the existing markdown structure.

## 4. Ask before posting anything

Everything in step 3 is outward-facing. Post nothing until the owner picks it.

Print a numbered list grouped by target, PRs first, then Jira. Each item gets:

- the target as a link, with the kind of change (reply, comment, description edit, title or transition)
- the reason: the concrete signal, e.g. "3 commits since the body was written; it still says 17 tests and there are now 21"
- the full draft in a fenced block. For description edits, show only the changed lines as a `diff` block.

Then use `AskUserQuestion` with `multiSelect: true` to pick what to post. One question per group (PR updates, Jira comments, Jira descriptions/transitions), up to 4 options each, splitting larger groups across questions. "Other" takes edits to a draft; apply them before posting.

If nothing needs attention, say so in one line and go to step 6.

## 5. Post the approved changes

Write every body to a temp file and pass the file; never splice text into shell quotes. Before editing a PR body or Jira description, fetch it fresh. If it changed since the gather step, stop and show the difference instead of overwriting it.

Jira bodies:

1. Write the approved Markdown to `$CLAUDE_JOB_DIR/tmp/eod-<KEY>.md`, then run `python3 <skill-directory>/adf.py from-md < $CLAUDE_JOB_DIR/tmp/eod-<KEY>.md > $CLAUDE_JOB_DIR/tmp/eod-<KEY>.json`.
2. Check it: `adf.py to-md < $CLAUDE_JOB_DIR/tmp/eod-<KEY>.json` should read back the same as the draft.
3. Description edits: fetch the live ADF with `acli jira workitem view <KEY> --fields description --json` and run `adf.py check` on `.fields.description`.
   - Prints `ok`: edit the Markdown from `to-md` and convert it back.
   - Lists node types (for example `inlineCard`, `taskList`, `codeBlock.wrap`): edit the ADF JSON directly, changing only the affected nodes, so those nodes survive. Never round-trip it through Markdown.

| Change | Command |
|---|---|
| PR body | `gh pr edit <n> -R <repo> --body-file <file>` |
| PR title | `gh pr edit <n> -R <repo> --title '<title>'` |
| PR comment | `gh pr comment <n> -R <repo> --body-file <file>` |
| Review-thread reply | `gh api repos/<repo>/pulls/<n>/comments/<reply_to_id>/replies -F body=@<file>` |
| Jira comment | `acli jira workitem comment create --key <KEY> --body-file $CLAUDE_JOB_DIR/tmp/eod-<KEY>.json --json` |
| Jira description | `acli jira workitem edit --key <KEY> --description-file $CLAUDE_JOB_DIR/tmp/eod-<KEY>.json --yes --json` |
| Jira transition | `acli jira workitem transition --key <KEY> --status '<target status>' --yes --json` |

After each post, confirm it from the `--json` response, then re-read the item. For Jira, run `acli jira workitem view <KEY> --fields comment,description,status --json` and render the new body with `adf.py to-md`. It must show formatted text, not raw JSON. If `acli` stored the ADF file as plain text, post no more Jira bodies and tell the owner. Report any failure with its error text, and don't retry blindly.

### Then mark merged PR announcements (optional)

If `integrations.slack.announce_channel` is set and `/vault-skills:pr-reactions` is installed, run it with the `Skill` tool. Keep its report for step 7 and use what it found about merges when writing Yesterday. Skip this step otherwise.

## 6. Write the next standup entry

Write the entry into the next standup day's own note (`standup.next_path`) and leave every other day's note untouched, including today's.

**Where:** if `standup.next_file_exists` is false, create the note from the standup template (`standup.template`, else a nearby standup note) with placeholders resolved for that date, followed by the entry. If it exists and `standup.next_entry` is set (from an earlier run, or because a recording was filed), show its current Yesterday/Today next to the new draft and ask whether to replace those sections or merge into them. Never remove lines the owner wrote. A note made from a recording holds the owner's entry under its own H2; edit inside that section.

**Shape.** If step 1 moved the entry to another day, use `YYYY-MM-DD <standup title>.md` for that date and check whether it exists, because the gatherer looked up its own date. The entry has no date heading, because the note's title and `date` carry it. Match the heading style of the existing standup notes and template; the default is:

```markdown
### TLDR

- <the one or two things that matter most>

### Yesterday

- **<workstream> ([ABC-123](https://acme.invalid/browse/ABC-123))**
	- <what happened, one fact per bullet>

### Today

- <focus item>

### Blockers

- <only if something is waiting on someone else>
```

Next morning, `/vault-skills:start-of-day` adds new items to Today and Blockers and writes `### Morning brief` at the bottom of this entry. So don't add a Morning brief section, and don't add anything after Blockers. The TLDR goes above Yesterday.

**TLDR:** one to three plain bullets: the outcomes that matter most from Yesterday and what is stuck or needs attention today. Repeat nothing word for word from the sections below; link the key PR or Jira issue.

**Yesterday:** today's work, written for the team.

- One top-level bullet per workstream, with a **bold** title and its Jira link. Nest the details under it with a **tab** indent. Use one bullet if a workstream has a single fact.
- Link PRs as `[repo PR #N](url)`. Link every Jira key: to its task note as `[[<note>|<KEY>]]` when `task_notes_by_key` has one, else to `https://<jira site>/browse/<KEY>`.
- State outcomes and the current state: merged, tests passed (with counts), confirmed in a named environment, in review waiting on approvals, filed a ticket for a flake. Include the comments and description fixes posted in step 5 only when they matter to the team.
- Put reviews of others' PRs under one **Reviews** bullet, one line per PR or batch. Leave it out if the reviews were trivial.
- Leave out meetings, surveys, email and other admin, and anything not backed by a source.

**Today:** what the owner will focus on next, most important first.

- Use plain bullets, not checkboxes. The to-do query at the top of the standup note (if the template has one) already shows open `- [ ]` tasks, so copying a checkbox would duplicate it. A planned checkbox task that is still open needs no new line.
- Sources: open authored PRs that need reviews, merges or fixes, unresolved threads, failing checks, re-reviews owed, unfinished items from today's plan, and the next unchecked `- [ ]` step in each in-progress task note (read it via `task_notes_by_key`).
- Add a meeting from step 1's calendar check only when the owner has to bring, present or decide something there, tied to a workstream. Don't list the day's meetings; the morning brief does that.
- Start each bullet with a verb ("Get … approved and merged", "Address …'s review on …"). Link the PR and Jira issue the same way as in Yesterday. Use the exact note name from the gather output's `wikilink` and don't invent note names.

**Blockers:** only for work waiting on someone else, such as reviewer approvals, another team or access. If there are none, leave out the whole section, heading included.

**Writing:** with the Obsidian MCP connected, use its write tool for a new note and its heading patch (operation replace, `ifMatch` from the document map) for an existing entry; otherwise use `Write` and `Edit`. Open the note afterwards (MCP `open_file`, the Obsidian CLI, or give the path). Then run the vault's check command if it has one (`make check` or its documented equivalent) and fix only what this edit broke.

### Then fill today's daily note `summary` (optional)

If today's daily note (`<folders.daily>/YYYY-MM-DD.md`) has a `summary` property in its template, fill it with one short paragraph that says what got done that day, using only recorded facts (posted changes, merged PRs, work-log entries), no tasks still open. Re-read the note first, replace an existing summary only after showing it to the owner, and leave the rest of the note alone. Skip this if the daily note has no `summary` property.

## 7. Report

End with a short summary. Every PR mentioned links to its page, and every Jira key links to its task note from `task_notes_by_key` when one exists, else to `https://<jira site>/browse/<KEY>`. The same applies to the step 4 list and the standup's TLDR and Blockers.

- each change posted, with its link
- the proposals the owner skipped
- announcement reactions added, if that optional step ran
- the next standup day's invites still awaiting a reply, and overlapping meetings, from step 1's calendar check
- the standup entry as written, so it can be checked without opening the note
- any source that failed or was skipped

Leave the JSON file in place for follow-up questions.
