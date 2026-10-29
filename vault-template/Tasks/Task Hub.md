---
title: Task Hub
type: Hub
tags:
  - Hub
  - Task
aliases:
  - Tasks
banner: "Media/Banners/task-hub.gif"
banner-height: 200
banner-y: 50
---

# Task Hub

[[Home]]

> [!abstract] One note per issue
> Each task note (`type: task`) is named for its issue, such as `ABC-101 Draft homepage copy`, and lives in the sub-folder for its status: `To Do`, `In Progress`, `Done` or `Won't Do`. Start one from [[Templates/Task Template|the task template]]. Checkboxes inside a task note are its sub-steps and feed the charts.

## Dashboard

```dataviewjs
await dv.view("Templates/Views/hub-charts", { hub: "tasks" })
```

## In flight

> [!multi-column]
>
> > [!todo]+ Active work
> > ![[Tasks/Task Hub.base#Active]]
>
> > [!todo]+ Next up
> > ![[Tasks/Task Hub.base#Next Up]]

## Triage and done

> [!multi-column]
>
> > [!question]+ Needs triage
> > ![[Tasks/Task Hub.base#Needs Triage]]
>
> > [!check]+ Recently completed
> > ![[Tasks/Task Hub.base#Recently Done]]

## All task records

[[Tasks/Task Hub.base|Open the full task Base]]
