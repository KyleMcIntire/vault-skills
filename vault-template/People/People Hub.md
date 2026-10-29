---
title: People Hub
type: Hub
tags:
  - Hub
aliases:
  - People
banner: "Media/Banners/people-hub.gif"
banner-height: 200
banner-y: 50
---

# People Hub

[[Home]]

> [!abstract] One note per person
> Start from [[Templates/Person Template|the person template]]. Your own note has `relationship: me`. Other relationships: coworker, manager, family, friend, other. Each note draws a profile card from its properties and the notes that link to it.

## Dashboard

```dataviewjs
await dv.view("Templates/Views/hub-charts", { hub: "people" })
```

## Everyone

![[People/People.base#List]]
