---
creation date: <% tp.file.creation_date() %>
date: <% tp.file.title.match(/^\d{4}-\d{2}-\d{2}/)?.[0] ?? tp.date.now("YYYY-MM-DD") %>
title: <% JSON.stringify(tp.file.title) %>
type: <% (await tp.system.suggester(["Call", "Message", "Email", "In-person conversation"], ["communication", "message", "email", "irl-chat"])) ?? "" %>
person:
status:
summary:
tags:
  - communication
banner: "Media/Banners/Note Types/communication-note.gif"
banner-height: 200
banner-y: 50
---

<!-- Template: uses Templater (tp.* expressions run on insert; set Templates folder to Templates). Delete this comment in the finished note. -->
<!-- Save in People/Conversations/ so the person profile card lists it. person: a quoted wiki-link to a person note,
or a plain name when no note exists. date is the communication date, not necessarily the sent date.
status: ⏩ ToDo (pending), ✅ Done, or blank. Keep summary to one short factual sentence. -->

# <% tp.file.title %>

[[People/People Hub|People Hub]]

## Communication

<!-- Paste the original message or record conversation notes. Keep wording and source dates. -->

## Follow-up

<!-- Only explicitly recorded actions or replies; keep Tasks metadata. -->

## Sources

<!-- Optional links to attachments, recordings or related notes. -->
