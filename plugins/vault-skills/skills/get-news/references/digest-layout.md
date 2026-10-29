# Digest note layout (used when the vault has no news template)

Prefer the vault's template at `<folders.templates>/News Digest Template.md` if one exists; resolve its
placeholders and keep its frontmatter. Otherwise write `<folders.news>/YYYY-MM-DD News.md` like this. Omit an
empty section except **Gaps**. Example values are fictional.

```markdown
---
type: news-digest
date: 2026-01-02
window: 7
incidents: 0
needs a look: 1
summary: One sentence on what matters most.
conditions: partly cloudy
high: 71
low: 55
rain chance: 20
cloud cover: 40
aqi: 42
---

# News 2026-01-02

Last 7 days (2025-12-26 to 2026-01-02)

> [!abstract] At a glance
> **0 security incidents** and **1 item to look at.** One or two sentences on what matters most.
>
> Facts are what a post or pin file says; "likely" marks inference.

## Weather

> [!info] Springfield, IL · partly cloudy, 71° / 55°
> - **Today:** conditions, high, low, rain chance, cloud cover, wind, sunrise to sunset
> - **Air quality:** AQI now and peak, with category (a model value, not a station reading)
> - **Next two days:**
> - **Alerts:** none from the National Weather Service

## Security incidents

> [!warning] Incident title
> - **Status:**
> - **What happened:**
> - **Fixed versions:**
> - **Open needs:**
> - **Sources:**

## Needs a look

| Item | Version | Our pin | Why it matters |
| --- | --- | --- | --- |
| [Acme Cluster](https://example.com/rel/1.2.9) | `v1.2.9` | `1.2.3` (acme-infra, per the local clone) | newer patch of a pinned version |

## Worth knowing

## Local

## Quiet

## Skipped

> [!note]- Judged irrelevant, listed so later runs skip them

## Gaps

> [!question]- What this digest did not check
```
