---
name: obsidian-cli
description: Use the official Obsidian CLI when a task needs Obsidian's running app, index, configured features, command registry, or developer runtime. Use for currently open notes and tabs, workspace state, daily notes, typed properties, tasks, links/backlinks, Bases queries, template resolution, link-aware moves, plugin commands, and plugin/theme debugging; do not use it for ordinary filesystem operations.
license: MIT
---

# Obsidian CLI

Use the CLI only for behavior that depends on Obsidian's running application,
indexes, settings, command registry, or developer runtime. Use Claude Code's
Read, Edit, Glob, and Grep tools for ordinary file reads, writes, directory
listing, and text search.

When the Obsidian MCP server is connected, prefer its tools for note reads,
frontmatter and heading patches, property searches, and link-aware moves, as
the vault's `CLAUDE.md` may describe. Reach for the CLI when the MCP server is
unavailable or lacks the operation: open tabs and workspace state, configured
daily notes, backlinks and unresolved links, `base:query`, template resolution,
plugin commands, and developer tools.

## Config

Read `.vault-skills.yaml` at the vault root (see the repo's `docs/CONFIG.md`) if present. This skill needs no keys; use the vault folder name as `vault=` when targeting.

## Capability probe and fallback

Before relying on the CLI, probe it from the shell:

~~~bash
obsidian version
~~~

On Windows, `obsidian` resolves to `Obsidian.com` in the Obsidian install
directory, which the installer puts on `PATH`. In PowerShell, run it as
`& obsidian version` if a bare call is parsed as something else.

A command being present on PATH is not sufficient: the probe must exit
successfully. If the probe fails, continue with ordinary filesystem tools where
they can satisfy the request. Briefly tell the user only when the missing
runtime capability matters. Do not install Obsidian, change PATH, or register
the CLI on the user's behalf.

The CLI requires a compatible Obsidian installer and a running app. Commands
can differ by version, so inspect live help before using a command whose syntax
is not already established:

~~~bash
obsidian help <command>
~~~

When a request truly needs the runtime capability and the probe fails, tell the
user to open Obsidian and enable **Settings → General → Command line
interface** using a compatible installer. Leave registration and any platform
repair steps to the user.

## Target precisely

Put `vault=<name-or-id>` before the command whenever the vault is
known. Use `path=` for an exact vault-relative path. Use
`file=` only when Obsidian's wikilink-style name resolution is
desired. Do not rely on the active vault or active file when a precise target
is available.

~~~bash
obsidian vault="My Vault" backlinks path="Projects/Plan.md" format=json
~~~

Parameters use `name=value`; boolean flags have no value. Quote
values containing spaces or shell-special characters.

## High-value indexed and configured operations

Use live help for exact parameters, then prefer these families when they add
meaning beyond raw files:

- Configured daily notes: `daily`, `daily:path`,
  `daily:read`, `daily:append`,
  `daily:prepend`.
- Typed properties and parsed metadata: `properties`,
  `property:read`, `property:set`,
  `property:remove`, `tags`, `tag`, and
  `aliases`. Supply a `type=` to
  `property:set` when the property is not plain text.
- Tasks: `tasks` for indexed listing and `task` with a
  stable `ref=path:line` or exact file/line for status changes.
- Link graph: `backlinks`, `links`,
  `unresolved`, `orphans`, and `deadends`.
- Bases: `bases`, `base:views`, and
  `base:query`. Prefer `format=json` for structured agent
  consumption.
- Templates: `templates` and `template:read ... resolve`
  when configured template resolution is required.
- Live workspace state: `tabs ids` lists the currently open tabs and
  their IDs, while `workspace ids` shows the workspace tree and its
  item IDs.
- Link-aware refactors: `move` and `rename` when the vault
  setting to update internal links should be honored.

### Inspect open notes

When the user asks about notes currently open in Obsidian:

~~~bash
obsidian vault="My Vault" tabs ids
obsidian vault="My Vault" workspace ids
~~~

Use `tabs ids` as the source of truth for open tabs. Keep entries
verbatim and classify them only when the output provides enough evidence:

- a Markdown note has an explicit vault path ending in `.md`
  (case-insensitive)
- another file-backed tab has an explicit vault path with a different extension
- a non-file view, such as search, graph, settings, or a plugin view, has no
  vault path

Do not infer a path from a display title, view type, or tab ID, and do not
discard entries that cannot be classified. For a request about open notes,
extract the Markdown paths while retaining the other tabs as workspace context.
Use `workspace ids` when tab groups or workspace hierarchy matter. Do
not substitute `recents`, which includes files that are no longer open.

If the tab output does not expose paths or view types clearly, correlate its tab
IDs with this read-only, structured workspace query:

~~~bash
obsidian vault="My Vault" eval code='JSON.stringify((()=>{const tabs=[];const active=app.workspace.getMostRecentLeaf();app.workspace.iterateAllLeaves(leaf=>{const path=leaf.view.file?.path??null;tabs.push({id:leaf.id,title:leaf.getDisplayText(),viewType:leaf.view.getViewType(),path,kind:path===null?"view":path.toLowerCase().endsWith(".md")?"markdown":"file",active:leaf===active})});return tabs})())'
~~~

The workspace query also returns sidebar and floating leaves. Only call an entry
an open tab when its ID appears in `tabs ids`; retain query-only
entries separately as workspace context. Preserve tab entries that have no
matching workspace entry instead of guessing their identity.

If the user asks for the single currently focused note and the tab output does
not identify it, use a read-only app query:

~~~bash
obsidian vault="My Vault" eval code="app.workspace.getMostRecentLeaf()?.view.file?.path ?? ''"
~~~

Use normal filesystem tools only for explicit paths returned by Obsidian, and
choose a reader appropriate to the file type. Do not read every open note when
paths or titles alone answer the request.

## Obsidian and plugin commands

`commands` lists registered command IDs, including commands provided
by plugins. Filter by an ID prefix, then execute the selected command with
`command id=<command-id>`. Never guess a command ID when it can be
discovered. Do not execute a discovered command whose effect is prohibited by
the host-session rules below.

~~~bash
obsidian vault="My Vault" commands filter="my-plugin:"
obsidian vault="My Vault" command id="my-plugin:run-action"
~~~

## Plugin and theme development

Use the CLI as the first choice for runtime verification after the normal build
or test command has produced artifacts:

1. Reload the plugin under test with `plugin:reload id=<plugin-id>` when
   needed, but never one of the plugins listed under "Preserve the host
   session" below.
2. Inspect `dev:errors` and `dev:console level=error`.
3. Verify UI state with `dev:screenshot path=...`,
   `dev:dom selector=...`, and `dev:css selector=...`.
4. Use `dev:mobile on` only when mobile emulation is relevant, and
   turn it off afterward.

Read-only `eval` and `dev:cdp` queries are appropriate for
state that the documented inspection commands cannot expose. Keep expressions
small and return serializable values. Treat any expression or CDP call that
mutates application state as a risky operation requiring explicit user intent.

## Preserve the host session

Claude may be running inside Obsidian through a host plugin (for example
Claudian), and an Obsidian MCP server may run through the Local REST API
plugin (`obsidian-local-rest-api`). Never reload or restart the Obsidian app or
window from an agent session, and never reload, disable, or uninstall either of
those plugins if they are installed. In particular, do not use:

- any CLI command that reloads or restarts the app, window, or renderer
- any plugin reload, disable, or uninstall operation targeting the host plugin or
  Local REST API
- any restricted-mode change
- a command ID, JavaScript expression, or CDP call that performs an equivalent
  app, window, renderer, or plugin teardown

These actions can end a host-plugin session, drop the MCP connection
mid-edit, and discard the user's unsaved work. This is a hard prohibition, not
a confirmation-gated operation. If verification requires one, finish all
non-destructive checks and tell the user to perform the reload manually.

## Risky operations require explicit intent

Do not perform the following merely because they are available:

- permanent deletion
- local-history or Sync restoration
- publishing or unpublishing
- plugin or theme installation/uninstallation
- mutating JavaScript evaluation or CDP calls

Confirm that the user's request clearly authorizes the exact target and effect.
Prefer reversible variants, such as trash-backed deletion, when they satisfy
the request. Explicit intent does not override the host-session prohibition
above.

## Exclusions

Do not teach or use the TUI, clipboard output, undocumented flags, platform
registration repairs, or CLI equivalents of generic filesystem operations in
this skill.

## Attribution

Adapted from `kepano/obsidian-skills` at revision
`a1dc48e68138490d522c04cbf5822214c6eb1202`. See `LICENSE`.
