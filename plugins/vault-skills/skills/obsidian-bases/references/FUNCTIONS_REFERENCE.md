# Bases functions reference

## Global functions

| Function | Purpose |
| --- | --- |
| `date(value)` | Parse a date string |
| `duration(value)` | Parse a duration string |
| `now()` / `today()` | Current date-time / date |
| `if(condition, yes, no?)` | Conditional value |
| `number(value)` | Convert to number |
| `link(path, display?)` | Create a link |
| `file(path)` | Resolve a file object |
| `list(value)` | Normalize a value to a list |
| `image(path)` / `icon(name)` | Create renderable values |

## Common methods

- String: `contains`, `startsWith`, `endsWith`,
  `lower`, `trim`, `replace`,
  `split`, `isEmpty`.
- Number: `abs`, `ceil`, `floor`,
  `round`, `toFixed`.
- List: `contains`, `containsAll`,
  `containsAny`, `filter`, `map`,
  `reduce`, `flat`, `join`,
  `sort`, `unique`.
- File: `asLink`, `hasLink`, `hasTag`,
  `hasProperty`, `inFolder`.
- Link: `asFile`, `linksTo`.
- Object: `keys`, `values`, `isEmpty`.
- Regular expression: `matches`.

Date fields include `year`, `month`, `day`,
`hour`, `minute`, and `second`. Date methods
include `date()`, `format()`, `time()`, and
`relative()`.

Duration fields are `days`, `hours`,
`minutes`, `seconds`, and `milliseconds`.
Duration does not directly support number rounding methods.
