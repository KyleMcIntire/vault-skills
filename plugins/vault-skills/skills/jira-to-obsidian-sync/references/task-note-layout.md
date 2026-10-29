# Task note layout (used when the vault has no task template)

Prefer the vault's own template (`folders.templates` + `templates.task`). Otherwise create notes like this.
Example values are fictional.

```markdown
---
status: In Progress
url: https://acme.invalid/browse/ABC-1
reporter: "[[Sam Sample]]"
type: task
task type: jira
tags:
  - Task
  - Jira
project:
story points: 3
PRs:
related jiras:
links:
slack threads:
next step:
dateModified: 2026-01-02T09:00:00.000-06:00
parent: "[[Parent note name]]"   # sub-tasks only
---

# Example task

## Description

(Jira description as Markdown; its headings start at ###.)

---

## Open steps

```tasks
not done
path includes {{query.file.path}}
short mode
```

---

## Work-log

### 2026-01-02 - Friday

#### Started (Jira comment, 08:00)

(comment body)

---
```

Notes:

- `status` and the status folder both use the values from `task_statuses`.
- The "Open steps" block is a Tasks-plugin query; drop it if the vault does not use that plugin. A "Mentions"
  section embedding a Base is likewise optional and only copied when the vault's template has one.
- `PRs`, `related jiras`, `links`, `slack threads` are YAML lists of URLs, one per line.
