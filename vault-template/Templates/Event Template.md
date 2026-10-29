---
creation date: <% tp.file.creation_date() %>
date: <% tp.file.title.match(/^\d{4}-\d{2}-\d{2}/)?.[0] ?? "" %>
end date:
start:
end:
timezone:
title: <% JSON.stringify(tp.file.title) %>
type: event
status:
location:
address:
attendees: []
project:
summary:
reviewed: <% tp.date.now("YYYY-MM-DD") %>
tags:
  - event
---

<!-- Template: uses Templater (tp.* expressions run on insert; set Templates folder to Templates). Delete this comment in the finished note. -->
<!-- Prefer the file name "YYYY-MM-DD Event name". date/end date are event dates, not creation dates; leave unknown ones blank.
start/end: quoted HH:mm. status: 📅 Planned, ❔ Tentative, ✅ Happened or ❌ Cancelled; a past date alone does not prove attendance.
attendees: quoted person wiki-links. project: an optional quoted link to a project note. -->

# <% tp.file.title %>

[[Home]]

## When and where

## People

## Details

## Follow-up

## Sources
