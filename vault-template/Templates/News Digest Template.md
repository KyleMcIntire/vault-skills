---
creation date: <% tp.file.creation_date() %>
title: <% tp.file.title %>
type: news-digest
date: <% tp.date.now("YYYY-MM-DD") %>
window: 7
incidents: 0
needs a look: 0
summary:
conditions:
high:
low:
rain chance:
tags:
  - News
---

<!-- Template: uses Templater (tp.* expressions run on insert; set Templates folder to Templates). Delete this comment in the finished note. -->
<!-- Normally written by the get-news skill (/vault-skills:get-news) into News/. Use this to write one by hand.
The weather block is optional; set integrations.weather_location in .vault-skills.yaml to fill it. -->

# <% tp.file.title %>

[[News/News Hub|News Hub]] · last 7 days (YYYY-MM-DD to YYYY-MM-DD)

> [!abstract] At a glance
> **N security incidents** and **N items to look at.** One or two sentences: what matters most and what touches your work.
>
> Facts are what a post or release note says; "likely" marks inference.

## Weather

> [!info] City · conditions, high / low
> - **Today:**
> - **Next two days:**
> - **Alerts:**

## Security incidents

> [!danger] Incident title
> - **Status:**
> - **What happened:**
> - **Fixed versions:**
> - **Our work:**
> - **Sources:**

## Needs a look

| Item | Version | Our pin | Why it matters |
| --- | --- | --- | --- |

## Worth knowing

## Quiet

## Skipped

> [!note]- Judged irrelevant, listed so later runs skip them

## Gaps

> [!question]- What this digest did not check
