---
creation date: <% tp.file.creation_date() %>
date: <% tp.date.now("YYYY-MM-DD") %>
start: "<% tp.date.now('HH:mm') %>"
duration:
title: <% tp.file.title %>
attendees: []
type: meeting
meeting type: ad-hoc
project:
status: ✅ Closed
summary:
topics: []
tags:
  - Meeting
banner: "Media/Banners/Note Types/meeting-note.gif"
banner-height: 200
banner-y: 50
---

<!-- Template: uses Templater (tp.* expressions run on insert; set Templates folder to Templates). Delete this comment in the finished note. -->
<!-- attendees: quoted person wiki-links, for example "[[Sam Sample]]".
meeting type: standup, planning, review, 1-1 or ad-hoc (the Meeting Hub chart groups by it).
status: ✅ Closed, or ⌛ Waiting on others while a row below is open. duration is in minutes. -->

# <% tp.file.title %>

[[Meetings/Meeting Hub|Meeting Hub]]

> [!abstract] TL;DR
> -

## My action items

<!-- - [ ] Description 📅 YYYY-MM-DD -->

## Waiting on others

Only what someone owes you or what blocks your work. Set `status: ⌛ Waiting on others` while a row is open.

| Owner | What you're waiting on | Due |
| --- | --- | --- |
|  |  |  |

## Decisions

-

## Notes

-
