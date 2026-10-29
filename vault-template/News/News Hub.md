---
title: News Hub
type: Hub
tags:
  - Hub
  - News
aliases:
  - News
banner: "Media/Banners/news-hub.gif"
banner-height: 200
banner-y: 50
---

# News Hub

[[Home]]

> [!abstract] Digests
> The `get-news` skill (`/vault-skills:get-news`) writes one digest note per run into this folder, named `YYYY-MM-DD News`. You can also write one by hand from [[Templates/News Digest Template|the digest template]]. Configure feeds and your weather location in `.vault-skills.yaml` under `integrations`.

```base
filters:
  and:
    - file.inFolder("News")
    - type == "news-digest"
views:
  - type: table
    name: Digests
    order:
      - file.name
      - date
      - incidents
      - needs a look
      - summary
    sort:
      - property: date
        direction: DESC
    limit: 20
```
