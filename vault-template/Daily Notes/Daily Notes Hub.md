---
title: Daily Notes Hub
type: Hub
tags:
  - Hub
aliases:
  - Daily Note Hub
banner: "Media/Banners/daily-notes-hub.gif"
banner-height: 200
banner-y: 50
---

# Daily Notes Hub

[[Home]]

> [!abstract] One note per day
> Create a note named `YYYY-MM-DD` from [[Templates/Daily Note Template|the daily template]] (core Daily notes plugin: folder `Daily Notes`, template `Templates/Daily Note Template`). After a month ends you can file notes into year and month sub-folders, such as `Daily Notes/2026/10 October/`; the charts search the whole folder.

## Dashboard

```dataviewjs
await dv.view("Templates/Views/hub-charts", { hub: "daily" })
```

## Recent days

![[Daily Notes/Daily Notes.base#Recent]]

## By mood

![[Daily Notes/Daily Notes.base#By mood]]
