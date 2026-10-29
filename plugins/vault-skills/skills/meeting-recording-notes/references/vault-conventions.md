# Meeting-note conventions

Paths are vault-relative. `<meetings>`, `<people>`, `<projects>` and `<templates>` are `folders.meetings`, `folders.people`, `folders.projects` and `folders.templates` from `.vault-skills.yaml` (defaults: `Meetings`, `People`, `Projects`, `Templates`). `<owner>` is `owner.name`. Read the vault's own `CLAUDE.md` first; it overrides anything here.

## Where the note goes

| Meeting | Path |
| --- | --- |
| Recurring meeting (standup, planning, refinement, 1-1, ...) | `<meetings>/Recurring/<Type>/YYYY-MM-DD <Title>.md` |
| Project meeting | `<meetings>/Projects/<Project>/YYYY-MM-DD <Title>.md` |
| Anything else | `<meetings>/Other/YYYY-MM-DD <Title>.md` |

Use an existing `<Type>` folder when one fits and create a new one only for a genuinely new meeting type. If the vault already lays meetings out differently, follow the vault.

Project log files (for example `<meetings>/Projects/<Project>/<Project>.md`) are **rolling logs**. Never put a full transcript in them. Create the single note, then add a short dated entry to the matching log, newest first, right under the H1, at the same heading level as the previous entry:

```markdown
### :TwCalendar: #2026-03-11 - Wednesday

Weekly sync with [[Sam Sample]] and [[Jo Placeholder]]. Full notes, action items, and transcript: [[2026-03-11 Platform Weekly]]

- One-line takeaway.
- One-line takeaway.

---
```

Recurring meetings that have one note per session (standups, 1-1s) are not logged. If a note for that day already exists and holds the owner's plan, do not overwrite it: copy its body into the new note as a section placed before the Transcript heading, then render over the old file.

## Frontmatter (single meeting)

Mirror the vault's meeting template (`templates.meeting` in `<templates>`) when one exists; the layout below is the fallback. A Meeting Hub or Base typically picks a note up when `type: meeting` and `date` are set.

```yaml
---
creation date: 2026-03-11 10:30        # when the note was written
date: 2026-03-11                        # meeting day
start: "09:02"                          # quoted; recording start (creation_time), else the invite's start
duration: 31                            # minutes, integer
title: Platform Weekly
type: meeting
meeting type: sprint                    # ad-hoc | standup | sprint | 1-1 | project | onboarding | other
project: platform                       # lowercase, matches the task notes' `project`
status: ✅ Closed                        # ⌛ Waiting on others while that table has an open row
attendees:
  - "[[Alex Example]]"                  # the owner has a person note, so always link them
  - "[[Sam Sample]]"                    # link when <people>/**/<Name>.md exists
summary: One sentence.
topics:
  - Staging deploy
jira: []                                # ticket keys mentioned, e.g. [ABC-123]
recording: <original filename>
transcript: auto (mlx-whisper large-v3-turbo + ECAPA speaker clustering)
tags:
  - Work
  - Meeting
---
```

If the vault uses banners, add the `banner` properties its template uses (look at a nearby meeting note); do not invent banner paths.

To get the start time, run `ffprobe -show_entries format_tags=creation_time`. It is UTC; convert to the local zone (`date +%Z`). The calendar invite (SKILL step 0), if available, gives the scheduled start and title; use it to cross-check, and as `start` when the recording has no `creation_time`. Its organizer and series help pick `meeting type`: a recurring team series is `standup` or `sprint`, and an invite with just the owner and one other person is usually `1-1`. Its notes can seed `topics` and `jira`.

People notes live in `<people>/`. Run `find <people> -name "*.md"` to match first names to full names, and match invite attendees by their `email` property. Write anyone without a note as plain text, because an unresolved link is a broken link.

**The owner is a person too.** Link them everywhere they are named, as `[[<owner>]]` in `attendees` and as `[[<owner>|First]]` in the body (TL;DR, discussion, the Waiting on others table, the how-this-was-made callout). Transcript speaker labels are linked too (`**[[Sam Sample|Sam]]:**`). `render_note.py` does that from the `attendees` frontmatter using `scripts/speakers.py`, so every speaker with a note must be an `attendees` link, or the label stays plain; `Unidentified` and generic labels always do. Pass `--me "<owner.name>"` so it also links any bare first name it finds in the head as a safety net, but write the links yourself.

## Tasks

Only the owner's own action items are checkboxes. A hub or dashboard usually runs a Tasks query over unchecked tasks, so other people's items would clutter it.

```markdown
- [ ] :TwBell: Description, with a timestamp link {{ref:53:48}} #Work 📅 2026-03-13
```

Format: checkbox, one fitting emoji, description, the vault's work tag (`#Work` here; match the vault), `📅 YYYY-MM-DD`. Give absolute dates only. Resolve "tomorrow" or "Friday" against the meeting date. When the meeting set no date, use a reasonable one (end of week) and say so in the reply. Completed tasks get `✅ YYYY-MM-DD` and dropped ones become `- [-] ... ❌ YYYY-MM-DD`; that is the owner's job, not yours.

Do not track other people's action items. Put one in the **Waiting on others** table only when it directly affects the owner: someone owes them something (an answer, a review, a ticket, access), or their own work is blocked until it is done. Team-wide reminders are not waiting on anyone. When nothing qualifies, write one line saying so and set `status: ✅ Closed`; otherwise set `status: ⌛ Waiting on others`.

Escape `|` inside wiki-links in the table; `render_note.py` does it for `{{ref}}` placeholders automatically.

```markdown
| Owner | What you're waiting on | Due | Ref |
| --- | --- | --- | --- |
| [[Sam Sample]] | :TwTicket: Add acceptance criteria to ABC-123 and tag [[Alex Example\|Alex]] | 2026-03-12 | {{ref:19:09}} |
```

## Note body (in order)

1. H1 with an emoji, then a links line: `[[<meetings>/Meeting Hub|Meeting Hub]] · [[...project log...]]` (omit links to hubs that do not exist)
2. `> [!abstract] TL;DR`: 3 to 6 bullets, each opening with an emoji and a **bold lead**
3. `> [!important] Deadline`: only if a real deadline came up
4. `> [!warning]- How this note was made` (collapsed): auto-transcribed, how speakers were identified, that short interjections may be mislabeled, and which terms were corrected
5. `## :TwCheckMarkButton: My action items`: tasks as above
6. `## :TwHourglassNotDone: Waiting on others`: the table, introduced with one line, or one line saying nothing is waiting
7. `## :TwCompass: Decisions` in a `> [!success] Agreed` callout, each with a `{{ref}}`
8. `## :TwMemo: Discussion`: `### 1. Topic` sections with short bullets and a `{{ref}}` on each
9. `## :TwRedQuestionMark: Open questions` in a `> [!question]` callout
10. `> [!tip]- Glossary` (collapsed): only for terms a reader might not know
11. `## :TwStudioMicrophone: Transcript`, appended by `render_note.py`. Do not write it yourself.

The `:Tw...:` shortcodes are Iconize icons; if the vault does not use Iconize, use plain emoji instead (and pass `--heading "## Transcript"` to `render_note.py`; `speakers.py` recognises that heading too). Callouts used: abstract, important, warning, success, question, tip, info, note. A trailing `-` collapses one.

## After writing

- Confirm the owner is linked: `grep -nw <FirstName> <note>` should show only wiki-link forms, and the render output's `left plain` list should hold only `Unidentified` or generic labels.
- Run the vault's checker if it has one (for example `python3 scripts/check_vault.py`); only new findings are yours.
- Do not stage, commit or push. Do not touch `.obsidian/` or other notes beyond the one log entry.
