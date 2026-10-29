---
creation date: <% tp.file.creation_date() %>
title: <% tp.file.title %>
type: doc
parent project:
kind: 🔧 Improvement
workstream: 🧰 Vault improvements
status: 🧪 Planning
summary:
next step:
started: <% tp.date.now("YYYY-MM-DD") %>
reviewed: <% tp.date.now("YYYY-MM-DD") %>
cadence:
tags:
  - type/doc
aliases: []
banner: "Media/Banners/Note Types/project-note.gif"
banner-height: 200
banner-y: 50
---

<!-- Template: uses Templater (tp.* expressions run on insert; set Templates folder to Templates). Delete this comment in the finished note. -->
<!-- A tracking note for one skill, script or automation. Save it inside its project's folder under Projects/ and set
parent project to a quoted wiki-link to that project's main note. type: doc makes it a sub-item on the Project Hub chart. -->

# <% tp.file.title %>

> [!abstract] Overview
> What this improvement or automation does, and why it matters.

## Outcome

<!-- Describe the desired behavior. Separate recorded facts from proposals. -->

## How it works

<!-- Inputs, outputs, triggers and any approval boundaries. -->

## Source files

<!-- Link source notes and list the relevant script, skill or plugin paths. -->

## Verification

<!-- Record checks actually run and any remaining uncertainty. -->

## Follow-ups

## Changelog

Newest first.

### #<% tp.date.now("YYYY-MM-DD") %> - <% tp.date.now("dddd") %>

- Started tracking this item.

## Sources
