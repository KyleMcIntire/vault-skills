---
name: finish-task
description: "Wrap up the current Claude session or task in the user's Obsidian vault: verify the work (vault check, tests), bring tracking notes, the vault's rules file and hubs up to date, save durable memories, file real open follow-ups in today's daily note, and commit only with the user's approval. Use when the user says \"wrap up\", \"finish up\", \"we're done\", \"close this out\", or asks to finish the task or session, even if they do not name this skill. Suggest it when a multi-step task has just been completed."
argument-hint: "[optional: what to focus the wrap-up on]"
---

# Finish task

Close out the work done in this conversation so nothing is left half-recorded: check it, document it, remember it, file what is left, and commit it with approval. Focus: "$ARGUMENTS" (if empty, the whole session).

Wrap up; do not keep working. Finish only small loose ends the task clearly implied, such as a reference the task's own rename left stale. Anything bigger becomes a follow-up. Do not widen the scope or redo finished work.

## 0. Orient

- **Config:** read `.vault-skills.yaml` at the vault root (see `docs/CONFIG.md`). This skill uses `folders.daily`, `folders.projects`, `folders.templates`, `templates.daily`, `owner.name` and `safety.never_commit`. If a needed value is missing, ask once and offer to write it into the file.
- **Vault root:** the nearest parent of the working directory holding `.vault-skills.yaml`, else `.obsidian/`. Read the vault's own rules file (`CLAUDE.md`, or whatever the user keeps their rules in) and any nested one on paths you touch. It overrides this skill.
- **What changed:** build the list from this conversation (files you created, edited, moved or deleted; notes; scripts; skills; settings outside the vault), plus `git status --short` for hidden folders. Note anything done outside the vault, such as scheduled tasks, MCP config or user-level settings.
- **Machine differences:** if the vault's rules file says some folders or tools are only available on one machine, respect that and file the other-machine work as a follow-up.

## 1. Verify

- Run the vault's checker if it has one (for example `make check`, or `python3 scripts/check_vault.py`; look in the rules file for the command). Compare with the session's baseline if one was recorded. Fix only findings this session introduced, and report the rest as already there.
- If scripts changed, run their tests with the command the repo documents (for example `python3 -m unittest discover -s scripts -p 'test_*.py'`).
- If a skill changed, confirm its `SKILL.md` frontmatter has `name` and `description`, and that any plugin or marketplace description that lists skills mentions it.
- Say plainly what you could not verify, such as visual rendering or something that only runs on another machine. Never describe a failed or skipped check as passing.

## 2. Update documentation

Update only what the session made stale:

- **Tracking notes** for the skill, automation or project touched (look in `<folders.projects>`; find one by searching for the skill name, its folder, or the script path). Update current-behavior, source and verification sections. Add a dated changelog entry in the note's existing style, newest first. Bump `reviewed` if the note has it, tick finished tasks with `✅ YYYY-MM-DD`, and update or clear `next step`. A new skill or automation gets a note from the matching template in `<folders.templates>`, with every placeholder resolved.
- **The rules file** when commands, paths, conventions or machine setup changed. Edit the existing section instead of adding a new one.
- **Hubs, bases and indexes** that name something the session moved, renamed, retired or added. Search for the old names and paths; Obsidian rewrites wiki-links on a rename but not plain-text paths in code spans.
- Keep history: do not rewrite earlier dated changelog entries. Prefer the Obsidian MCP for note edits when it is connected, and the filesystem for hidden folders. For a rename or move, use the MCP's move or the Obsidian CLI's `move`, so links are rewritten.

## 3. Save memories

Save what a future session would need and cannot get from the repo or the rules file: decisions and their reasons, the user's stated preferences or corrections, and constraints such as machine or account setup. Follow the memory instructions in the system prompt. Update an existing memory instead of adding a near-duplicate, and delete memories this session proved wrong. Skip anything that only mattered to this conversation.

## 4. File follow-ups

- Collect only real open items: work left unfinished, things blocked on the user or another machine, decisions they deferred, and verification they need to do. Never invent owners, deadlines or completion states.
- Add each as a task under the task-inbox heading of today's daily note (`<folders.daily>/YYYY-MM-DD.md`, or the path the Obsidian CLI's `daily:path` prints). If the note does not exist, create it from `templates.daily` in `<folders.templates>`. If the daily template has no inbox heading, match nearby daily notes rather than inventing one. Format: `- [ ] <action> #<tag>` with a wiki-link to the tracking note or source when there is one, and `📅 YYYY-MM-DD` only when a date was stated. Use the work or personal tag the vault already uses. Search the inbox and the tracking note first to avoid duplicates.
- Follow-ups about a skill or automation also go in that tracking note's follow-up section.

## 5. Commit, with approval

Never stage, commit or push unless the user asks; if `safety.never_commit` is true, only offer. Show the user the files and the commit message, then commit only after they say yes. Push only after a separate yes.

- Commit by explicit path, never `git add -A`, if the vault's rules file warns about files that exist on one machine only.
- If the vault has a backup command in its rules file (for example `make backup`), mention it as an option, and run it only when asked. Pull first if another machine has pushed.
- End the message with the attribution line the session's instructions give, if any.

## 6. Report

End with a short summary:

- **Done:** what changed, linking the main notes.
- **Verified:** the check and test results, with numbers, plus anything left unverified.
- **Recorded:** the docs and tracking notes updated, and the memories saved.
- **Committed:** the commit hash and push status, or what is waiting for approval.
- **Open:** the follow-ups and where they were filed.

Keep it to what the user needs to act on; do not replay the whole session.
