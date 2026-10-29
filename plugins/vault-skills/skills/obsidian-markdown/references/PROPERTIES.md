# Properties reference

Properties are YAML frontmatter at the very start of a note.

| Property type | Example |
| --- | --- |
| Text | `title: My title` |
| Number | `rating: 4.5` |
| Checkbox | `completed: true` |
| Date | `date: 2026-07-21` |
| Date and time | `due: 2026-07-21T14:30:00` |
| List | `tags: [one, two]` or a YAML list |
| Link | `related: "[[Other Note]]"` |

Obsidian reserves `tags`, `aliases`, and
`cssclasses` for their built-in behaviors. Tags may contain letters,
numbers (not as the first character), underscores, hyphens, and forward slashes.
Prefer YAML lists when a property naturally has multiple values.
