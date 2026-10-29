---
title: Project Hub
type: Hub
tags:
  - Hub
  - Projects
aliases:
  - Projects
banner: "Media/Banners/project-hub.gif"
banner-height: 200
banner-y: 50
---

# Project Hub

[[Home]]

> [!abstract] Project command center
> Every project has one main note with `type: project`, an emoji `status` and a `category`, in its own folder under `Projects/`. Start one from [[Templates/Project Template|the project template]]. Each keeps a changelog, newest first. Bump `reviewed` when you check in; anything open and unreviewed for 30 days shows **Review due**.

## Status vocabulary

The Bases and charts match these values exactly, including the emoji.

| Status | Meaning |
| --- | --- |
| 💡 Idea | Not started |
| 🧪 Planning | Designing or scoping, not building yet |
| 🟢 Active | Being worked on now |
| ⏸️ Paused | Started, then set aside |
| ✅ Done | Finished; kept for reference |

Categories are free text. The example uses `Work`; common ones are Career, Life Admin, Hobbies and Tooling.

## Dashboard

```dataviewjs
await dv.view("Templates/Views/hub-charts", { hub: "projects" })
```

## In progress

![[Projects/Projects.base#In progress]]

## Ideas

![[Projects/Projects.base#Ideas]]

[[Projects/Projects.base|Open the full project Base]]
