---
title: Meeting Hub
type: Hub
tags:
  - Hub
  - Meeting
aliases:
  - Meetings
banner: "Media/Banners/meeting-hub.gif"
banner-height: 200
banner-y: 50
---

# Meeting Hub

[[Home]]

> [!abstract] One note per meeting
> Start from [[Templates/Meeting Template|the meeting template]]. Recurring meetings go under `Meetings/Recurring/<Type>/`, one note per session, such as `Meetings/Recurring/Standup/2026-10-27 Team Standup`. Set `status: ⌛ Waiting on others` while you owe a follow-up from someone else.

## Dashboard

```dataviewjs
await dv.view("Templates/Views/hub-charts", { hub: "meetings" })
```

## Recent meetings

![[Meetings/Meetings.base#Recent meetings]]

## Waiting on others

![[Meetings/Meetings.base#Waiting on others]]

[[Meetings/Meetings.base|Open the full meeting Base]]
