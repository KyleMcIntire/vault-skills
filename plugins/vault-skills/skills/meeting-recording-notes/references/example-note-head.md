---
creation date: 2026-03-11 10:30
date: 2026-03-11
start: "09:02"
duration: 31
title: Platform Weekly
type: meeting
meeting type: sprint
project: platform
status: ⌛ Waiting on others
attendees:
  - "[[Alex Example]]"
  - "[[Sam Sample]]"
  - "[[Jo Placeholder]]"
summary: Staging deploy slipped to Thursday; alert noise on the queue worker to be cut; Jo owns the runbook refresh.
topics:
  - Staging deploy
  - Alert noise
  - Runbooks
jira: [ABC-123, ABC-140]
recording: Platform Weekly.m4a
transcript: auto (mlx-whisper large-v3-turbo + ECAPA speaker clustering)
tags:
  - Work
  - Meeting
---

# :TwCalendar: Platform Weekly

[[Meetings/Meeting Hub|Meeting Hub]] · [[Projects/Platform/Platform|Platform project]]

> [!abstract] TL;DR
> - :TwRocket: **Staging deploy moves to Thursday.** The migration job needs one more dry run. {{ref:03:12}}
> - :TwBell: **Queue worker alerts are too noisy.** Raise the threshold and page only on sustained backlog. {{ref:14:40}}
> - :TwBook: **Runbooks get a refresh.** [[Jo Placeholder|Jo]] takes the on-call section. {{ref:24:05}}

> [!important] Deadline
> Staging deploy must land by **2026-03-12** to keep the release train on schedule.

> [!warning]- How this note was made
> I auto-transcribed the recording, which has no speaker labels. Speakers were identified by grouping the three voices in the audio and matching each voice to a name from known stretches of the conversation. Short interjections can still be mislabeled, so check owners before anything goes into Jira.

## :TwCheckMarkButton: My action items

- [ ] :TwTestTube: Run the staging migration dry run and post the result in the team channel {{ref:03:40}} #Work 📅 2026-03-12
- [ ] :TwBell: Draft the new queue worker alert threshold for review {{ref:15:10}} #Work 📅 2026-03-13

## :TwHourglassNotDone: Waiting on others

Only what someone owes [[Alex Example|Alex]] or what blocks the work.

| Owner | What you're waiting on | Due | Ref |
| --- | --- | --- | --- |
| [[Sam Sample]] | :TwTicket: Confirm the staging database snapshot is fresh (ABC-123) | 2026-03-12 | {{ref:05:02}} |

## :TwCompass: Decisions

> [!success] Agreed
> - Deploy to staging on Thursday, not Wednesday. {{ref:03:12}}
> - Page only when queue backlog stays high for 10 minutes. {{ref:16:20}}

## :TwMemo: Discussion

### 1. Staging deploy

- The migration job failed once in the last dry run; cause was a missing index. {{ref:02:30}}
- A second dry run is needed before Thursday. {{ref:03:40}}

### 2. Alert noise

- Roughly 30 pages last week came from short backlog spikes. {{ref:13:55}}
- Raise the threshold and add a duration condition. {{ref:16:20}}

## :TwRedQuestionMark: Open questions

> [!question]
> - Should the runbooks live in the wiki or next to the code? {{ref:26:30}}

> [!tip]- Glossary
> - **Dry run**: a deploy rehearsal against a copy of production data.
