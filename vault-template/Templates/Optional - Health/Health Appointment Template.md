---
creation date: <% tp.file.creation_date() %>
title: <% JSON.stringify(tp.file.title) %>
type: appointment
area: Appointments
date: <% tp.date.now("YYYY-MM-DD") %>
provider:
appointment kind:
summary:
status:
condition: []
reviewed:
tags:
  - Health
aliases: []
---

<!-- Template: uses Templater (tp.* expressions run on insert; set Templates folder to Templates). Delete this comment in the finished note. -->
<!-- Optional, structure only. Record only what the source says; keep dates, values and wording exact; leave unknown properties blank. This is a record, not medical advice. -->

# <% tp.file.title %>

## Record

## Follow-ups
