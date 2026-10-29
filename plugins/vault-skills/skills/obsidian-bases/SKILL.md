---
name: obsidian-bases
description: Create and edit Obsidian Bases (.base files) with valid YAML schemas, filters, formulas, properties, summaries, and views. Use for database-like Obsidian views or when the user mentions Bases, .base files, table/card/list views, filters, formulas, or summaries.
license: MIT
---

# Obsidian Bases

## Workflow

1. Read the existing `.base` file before editing it, plus a few notes it
   matches. Filters compare exact property values (including emoji, such as a
   status of `🟢 Active`), so copy names and values from real notes.
2. Define global scope with `filters`.
3. Add computed values under `formulas` only when needed.
4. Configure property display names and one or more views.
5. Validate YAML, formula references, quoting, and date/duration operations.
6. Check the result with `base:query ... format=json` through the
   `obsidian-cli` skill when Obsidian is running.

## Schema

~~~yaml
filters:
  and:
    - 'file.ext == "md"'
    - 'status != "archived"'

formulas:
  days_until_due: 'if(due, (date(due) - today()).days, "")'

properties:
  status:
    displayName: Status
  formula.days_until_due:
    displayName: "Days Until Due"

summaries:
  mean_rounded: 'values.mean().round(2)'

views:
  - type: table
    name: Active
    limit: 50
    filters:
      and:
        - 'status != "done"'
    order:
      - file.name
      - status
      - formula.days_until_due
    groupBy:
      property: status
      direction: ASC
    summaries:
      formula.days_until_due: Average
~~~

Views may be `table`, `cards`, or `list`.
A `map` view depends on compatible map support.

## Filters and properties

Filters may be a single expression or recursively nested `and`,
`or`, and `not` objects. Property namespaces are:

- note properties: `status` or `note.status`
- file metadata: `file.name`, `file.path`,
  `file.folder`, `file.ctime`, `file.mtime`,
  `file.tags`, `file.links`, and
  `file.backlinks`
- formulas: `formula.days_until_due`

Use `file.hasTag()`, `file.hasLink()`,
`file.hasProperty()`, and `file.inFolder()` for indexed
file relationships. The `this` value refers to the Base itself, the
embedding note, or the active file depending on where the Base is rendered.

## Formula rules

- Guard optional properties with `if()`.
- Date subtraction returns a Duration, not a number. Access
  `.days`, `.hours`, or another numeric field before
  calling number methods such as `.round()`.
- Every `formula.X` used by a view or property configuration must
  have a matching `X` entry under `formulas`.
- Wrap formulas containing double quotes in YAML single quotes.
- Quote YAML strings containing special characters, especially colons and
  leading punctuation.

Read [Functions reference](references/FUNCTIONS_REFERENCE.md) for function and
type-specific operations, and [Examples](references/EXAMPLES.md) for complete
task-tracker and daily-notes Bases.

## Validation checklist

- The document parses as YAML and has a `views` list.
- View `order`, `groupBy`, and summaries reference defined
  note, file, or formula properties.
- Formula quoting is balanced and duration math accesses a numeric field.
- Embedded view names match exactly: `![[My Base.base#View Name]]`.

## Attribution

Adapted from `kepano/obsidian-skills` at revision
`a1dc48e68138490d522c04cbf5822214c6eb1202`. See `LICENSE`.
