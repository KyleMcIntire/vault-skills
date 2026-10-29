---
date: "{{date}}"
prev:
next:
type: Daily Note
mood:
summary:
tags:
  - Journal
banner: "Media/Banners/daily-notes-hub.gif"
banner-height: 200
banner-y: 50
---

<!-- Template: uses core placeholders ({{date}}, {{date:dddd}}), so it works with the core Daily notes
plugin AND with Templater (which leaves them alone). Point Daily notes at folder "Daily Notes" and
this file as the template. `mood` feeds the Daily Notes Hub chart: use one of ✅ Good, 👍 Normal,
🥱 Tired, 😬 Anxious, 😞 Rough. `prev`/`next` are filled by the vault-skills daily-note linker.
Delete this comment in the finished note. -->

# {{date}} - {{date:dddd}}

## Task Inbox

## Overdue

> [!warning] Overdue
>
> ```tasks
> not done
> due before today
> sort by priority
> ```

## ToDo

> [!check] ToDo
>
> ```tasks
> not done
> due before tomorrow
> tag does not include #habit
> sort by priority
> ```

## Upcoming

> [!check] Upcoming
>
> ```tasks
> not done
> due after today
> sort by due date
> ```

---

## Habits

> [!check] Habits
>
> ```tasks
> not done
> tag includes #habit
> due today
> hide backlink
> hide edit button
> ```

## Related

<!-- related-notes -->
<!-- /related-notes -->

---

## Done

```tasks
done today
```
