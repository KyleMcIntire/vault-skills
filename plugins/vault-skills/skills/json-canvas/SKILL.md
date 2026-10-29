---
name: json-canvas
description: Create and edit JSON Canvas (.canvas) files with valid nodes, edges, groups, colors, layout, IDs, and referential integrity. Use for Obsidian Canvas files, visual maps, flowcharts, project boards, or any request involving the JSON Canvas format.
license: MIT
---

# JSON Canvas

Follow JSON Canvas 1.0. A `.canvas` document contains top-level
`nodes` and `edges` arrays.

## Workflow

1. Parse the existing JSON before editing it.
2. Generate a unique lowercase 16-character hexadecimal ID for each new node
   or edge.
3. Position nodes without overlap and preserve intentional existing layout.
4. Point every edge at existing node IDs.
5. Serialize valid JSON and run the validation checklist below.

## Nodes

Every node requires `id`, `type`, `x`,
`y`, `width`, and `height`.

| Type | Required content | Purpose |
| --- | --- | --- |
| `text` | `text` | Markdown content |
| `file` | `file` | Vault file; optional `subpath` |
| `link` | `url` | External URL |
| `group` | none | Visual container; optional label/background |

Array order controls z-index: earlier nodes are behind later nodes. Coordinates
may be negative. Position is the top-left corner, x increases right, and y
increases down.

~~~json
{
  "id": "6f0ad84f44ce9c17",
  "type": "text",
  "x": 0,
  "y": 0,
  "width": 360,
  "height": 180,
  "text": "# Main idea\n\nDetails",
  "color": "5"
}
~~~

Use actual JSON newline escapes in text values. Do not double-escape them into
literal backslash-n text.

## Edges

Every edge requires `id`, `fromNode`, and
`toNode`. Optional sides are `top`, `right`,
`bottom`, or `left`. Optional ends are `none`
or `arrow`.

~~~json
{
  "id": "0123456789abcdef",
  "fromNode": "6f0ad84f44ce9c17",
  "fromSide": "right",
  "toNode": "a1b2c3d4e5f67890",
  "toSide": "left",
  "toEnd": "arrow",
  "label": "leads to"
}
~~~

## Colors and layout

A color is a hex string or preset `"1"` through
`"6"`. Presets deliberately do not define exact hex colors. Leave
50–100 px between nodes, 20–50 px padding inside groups, and align to a simple
grid when creating a new layout.

## Validation checklist

- JSON parses successfully.
- IDs are unique across nodes and edges.
- Every `fromNode` and `toNode` exists in
  `nodes`.
- Each node type has its required content field.
- Sides, ends, and colors use allowed values.
- Nodes do not unintentionally overlap and group children sit inside bounds.

Read [Examples](references/EXAMPLES.md) for complete connected and grouped
canvases.

## Attribution

Adapted from `kepano/obsidian-skills` at revision
`a1dc48e68138490d522c04cbf5822214c6eb1202`. See `LICENSE`.
