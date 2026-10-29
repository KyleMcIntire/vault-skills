---
name: add-person
description: Add a new person note to the vault's people folder with the right sub-folder, frontmatter, tags and body layout, copied from the vault's person template, and optionally pull their profile picture, title, email and timezone from Slack plus their team from a service catalog. Also updates an existing person note, for example to fill blanks or set a missing photo. Use whenever the user asks to add, create or make a note for a person (a coworker, friend, family member, doctor), says "add Sam to people", "new person: ...", "make a people note for ...", or asks to grab, pull or set someone's Slack photo or profile picture, even if they do not name this skill.
---

# Add a person

One note per person under `<folders.people>/<Group>/<Name>.md`. Get the folder, frontmatter and photo right with as few questions as possible.

`SKILL_DIR` is this skill's base directory, as given when the skill loads.

## 0. Configuration

Read `.vault-skills.yaml` at the vault root (see `docs/CONFIG.md`) and the vault's own `CLAUDE.md`. This skill uses `folders.people`, `folders.templates`, `templates.person`, `owner.name`, and optionally `integrations.slack` and `integrations.catalog`. If a needed value is missing, ask once and offer to write the answer into the file. The attachment folder for photos is `Media/Attachments` unless the vault says otherwise.

## 1. Work out who and where

Take the name, relationship and any facts from the user's message. People live in sub-folders by group. Inspect the existing sub-folders of `<folders.people>` and a few notes in each to learn the groups, their tags and their `relationship` values; reuse them. A typical set:

| Folder | Who | Tags |
| --- | --- | --- |
| `Work/` | Coworkers, anyone found in the work Slack | `person` plus a work tag |
| `Friends/` | Friends | `person`, `friend` |
| `Family/` | Relatives | `family`, `person` |
| `Doctors/` | Doctors and other care providers | `person` |
| `Other/` | Anyone else | `person` |

Ask one short question only when the group or relationship cannot be inferred. Never invent a new group or tag taxonomy; match what exists.

**Check for duplicates first.** Notes are sometimes named by first name or role ("Mom"), so search by first and last name:

```bash
cd "<vault>"
find "<folders.people>" -iname "*<first>*" -o -iname "*<last>*"
grep -rli "^name: .*<last>" "<folders.people>"
```

If a note exists, switch to **update mode**: fill empty fields and add the photo, never overwrite a filled value without asking.

## 2. Optional: look them up in Slack

Only when a Slack connector is available (for example a Slack MCP server) and the person is a coworker or the user asked for a photo. Skip it for friends, family and doctors unless asked, and say in the report if the connector is missing.

1. Search users with the name as separate words (`keywords: ["First", "Last"]`); quoted full names often fail. Retry with just the last name or the email. The search result, not the profile read, is where a profile-picture URL appears.
2. If several people match, take the exact name match. If still ambiguous, ask the user with the answer picker, offering each candidate's title and email.
3. Keep the user ID, title, email, timezone, pronouns, photo URL and permalink. Use the Slack spelling for the note name unless the user gave another.

If mail or calendar tools are available (see `/vault-skills:mail-calendar`), a person outside the Slack workspace can be looked up there, read-only, for the spelling of their name and their email. Skip otherwise.

### Optional: team from a service catalog

If `integrations.catalog` is configured and its tools are connected (Backstage or similar), look the person up by email, read the teams they belong to, keep real teams (not virtual or deactivated groups), and ask for only the fields you need. Never claim someone reports to a team's manager: a catalog rarely has reporting lines. If the catalog is not configured or not connected, skip this and say so.

## 3. Save the photo (optional)

```bash
python3 -I SKILL_DIR/scripts/fetch_avatar.py "<Note Name>" "<profile pic URL>" --vault "<vault>" --attachments "Media/Attachments"
```

It saves `<attachments>/<Note Name> (Slack).<ext>` scaled to 512px and prints `LINK: [[...]]`; use that link exactly.

- `ERROR: ... default avatar`: no real photo. Leave `image:` empty and say so.
- `ERROR: photo already exists`: reuse it unless the user asked to refresh, then rerun with `--force`.
- Other hosts: `--allow-host <host>` for one host, `--any-host` only for a URL the user explicitly gave.
- `--dry-run` shows the target without downloading. A failed download exits with a message, never a traceback.

If the user supplies their own photo it is already in the attachments folder; just link it.

## 4. Write the note

Read `<folders.templates>/<templates.person>` first and follow it: the same frontmatter keys in the same order, nothing new. If the vault has no person template, use the layout in this skill's fixture (`SKILL_DIR/fixtures/vault/People/Alex Example.md`) as a starting point and say so. Resolve template placeholders (`<% tp.file.title %>`, `{{date}}`) with the person's name and today's date, drop template comments, and leave unknown fields empty. Quote the `image` link in YAML.

- Body: copy the template body below the frontmatter. If it has a profile-card block, a Together section or a Meetings callout, keep them for work people and delete the Meetings callout for friends, family and doctors, as the template's comments say.
- Slack facts (role, handle link, timezone, pronouns) go under the Notes heading as bullets, using the labels the template or neighbouring notes use. Add a **Team** bullet when the catalog found one.
- `role`/`team` values: reuse a value neighbouring notes already have, say you inferred it, or leave it empty.
- Do not invent details. A temporary Slack status such as "On PTO" is left out.
- `location`: use what the user gives. For Slack lookups you may guess a broad region from the timezone (never a specific office) and must say it was guessed. Leave it empty otherwise.

**Writing:** if an Obsidian MCP server is connected, create the note through it and open it; otherwise use the file tools, then open it with the Obsidian CLI if available. Use the filesystem for the photo either way. Re-read the target right before editing.

**Update mode:** change only what is needed: set `image:` (single-line edit or frontmatter patch), add a missing profile card or photo embed, add a missing Team bullet. Do not touch the rest.

## 5. Check and report

Run the vault checker if there is one (`make check`, or `python3 scripts/check_vault.py`); it is read-only. Then report in a sentence or two: the note path and folder, whether a photo was saved (and offer `/vault-skills:vault-image-icon` to turn it into a file icon if that skill is installed), which fields came from Slack or the catalog, and anything you guessed.

Never stage or commit. Never message anyone.
