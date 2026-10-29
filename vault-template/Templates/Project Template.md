---
creation date: <% tp.file.creation_date() %>
title: <% tp.file.title %>
type: project
status: 🧪 Planning
category:
summary:
next step:
started: <% tp.date.now("YYYY-MM-DD") %>
reviewed: <% tp.date.now("YYYY-MM-DD") %>
repo:
tags:
  - type/project
aliases: []
banner: "Media/Banners/Note Types/project-note.gif"
banner-height: 200
banner-y: 50
---

<!-- Template: uses Templater (tp.* expressions run on insert; set Templates folder to Templates). Delete this comment in the finished note. -->
<!-- Save as Projects/<Project name>/<Project name>.md; other notes for the project live in the same folder.
status (exact text, the Bases and charts match it): 💡 Idea, 🧪 Planning, 🟢 Active, ⏸️ Paused, ✅ Done.
Bump `reviewed` whenever you check in; anything open and unreviewed for 30 days shows as Review due. -->

# <% tp.file.title %>

[[Projects/Project Hub|Project Hub]]

> [!abstract] Overview
> What this is, and why it matters.

## Goals

-

## How it works

-

## Next up

<!-- - [ ] Task 📅 YYYY-MM-DD -->

## Ideas

-

## Changelog

Newest first.

### #<% tp.date.now("YYYY-MM-DD") %> - <% tp.date.now("dddd") %>

- Started the project.

## Project files

![[Projects/Projects.base#Project files]]
