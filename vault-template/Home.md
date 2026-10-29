---
title: Home
type: Hub
banner: "Media/Banners/home.gif"
banner-height: 200
banner-y: 50
tags:
  - Hub
aliases:
  - Start here
---

<!-- The animated banner above needs the Pixel Banner plugin. Swap `banner` for any image in Media/Banners, or delete the three banner properties. -->

# Home

> [!abstract] Your vault at a glance
> Start here. Each hub below owns one folder and draws its own live charts.

## Hubs

| Hub | What lives there |
| --- | --- |
| [[Daily Notes/Daily Notes Hub\|Daily Notes]] | One note per day: tasks due, habits, mood |
| [[Tasks/Task Hub\|Tasks]] | One note per issue or ticket, filed by status |
| [[Meetings/Meeting Hub\|Meetings]] | One note per meeting, standups under Recurring |
| [[People/People Hub\|People]] | One note per person |
| [[Projects/Project Hub\|Projects]] | Multi-step efforts with a status |
| [[Wiki/Wiki Hub\|Wiki]] | Durable reference notes |
| [[News/News Hub\|News]] | Digests written by the get-news skill |
| [[Preferences/Preferences Hub\|Preferences]] | Learned preferences and voice profile |

## Due today and overdue

```tasks
not done
due before tomorrow
sort by priority
short mode
```

## Stats

Counts every note by top-level folder, plus edits and tasks done over time. Needs Dataview with JavaScript queries enabled.

```dataviewjs
await dv.view("Templates/Views/hub-charts", { hub: "home" })
```

## Recently edited

```base
filters:
  and:
    - file.ext == "md"
    - '!file.inFolder("Templates")'
    - '!file.inFolder("Local")'
views:
  - type: table
    name: Recently edited
    order:
      - file.name
      - type
      - summary
      - file.mtime
    sort:
      - property: file.mtime
        direction: DESC
    limit: 10
```
