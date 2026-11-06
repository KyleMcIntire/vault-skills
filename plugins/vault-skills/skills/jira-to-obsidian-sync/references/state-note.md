# State note layout

Location: `<folders.tasks>/Jira Sync State.md` (or wherever the vault says). It is a visible note so Obsidian, its
CLI and its MCP can open, link and patch it; older vaults may still hold a hidden `<folders.tasks>/.sync-state.md`,
which the skill migrates on the next run. Create it on the first (bootstrap) run, then keep exactly this shape. Example values are fictional.

```markdown
---
type: meta
tags:
  - Meta
watermark: 2026-01-02T09:27:10.635-0600
lastRun: 2026-01-02T10:00:00-06:00
dateModified: 2026-01-02T10:00:00-06:00
issuesTracked: 1
forceKeys: []
---

# Jira Sync State

Written by `/vault-skills:jira-to-obsidian-sync`. Do not edit by hand except `forceKeys`.
`forceKeys` lists issue keys to reconcile on the next run regardless of the watermark.

## Fingerprints

| key | jira status | updated | comments | note |
| --- | --- | --- | --- | --- |
| [ABC-1](https://acme.invalid/browse/ABC-1) | In Progress | 2026-01-02T09:00:00.000-0600 | 1 | Tasks/In Progress/Example task.md |

## Known noise projects

| project key | reason |
| --- | --- |

## Ambiguous key to note mappings

| key | canonical note | other notes |
| --- | --- | --- |

## Open follow-ups

- (none)
```
