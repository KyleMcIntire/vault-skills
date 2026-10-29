---
name: pr-reactions
description: "Mark your own PR announcements in a Slack channel with a merged emoji once the pull request is merged. It checks your top-level posts in the announcement channel from the last few days, adds the missing reaction, and reports what it added and why. Optionally applies a second, user-defined reaction rule. Use when the user asks to \"mark merged PRs\", \"add the merged emoji\", update their PR announcements, or tidy up the PR announcement channel, even if they don't name this skill. Can also be called from an end-of-day wrap-up."
argument-hint: "[days to look back, default 3]"
---

# PR announcement reactions

Add a merged emoji to the user's own PR announcements in the Slack announcement channel, so the channel shows at a glance what has landed. Reactions are low-risk and easy to remove, so add them without asking, then report.

## Setup

Read `.vault-skills.yaml` at the vault root (see `docs/CONFIG.md`). Ask once, and offer to save the answer, for anything missing:

| Need | Config key | Notes |
| --- | --- | --- |
| Announcement channel | `integrations.slack.announce_channel` | resolve its ID with a channel search |
| GitHub org (optional) | `integrations.github.org` | only to recognise PR URLs |
| Slack user ID of the owner | `integrations.slack.user_id` (**not yet in CONFIG.md**) | look it up with a user search by `owner.name` if absent |
| Merged emoji name | `integrations.slack.merged_emoji` (**not yet in CONFIG.md**) | default `merged`; check it exists with an emoji search; names go to the API without colons |
| Optional second rule | `integrations.slack.second_reaction` (**not yet in CONFIG.md**) | see "Optional second rule" below; skipped when absent |

Tools: a Slack connector (search messages, get reactions, read thread, add reaction) and the `gh` CLI. Tools may be deferred; load them with one tool-search call. If there is no Slack connector, say so and stop.

- Look-back: the argument `$ARGUMENTS` as a number of days, default 3.

**Only ever add reactions to the owner's own top-level posts. Never remove a reaction, never react to anyone else's message, and never post or reply.**

## 1. Find the announcements

Search Slack with `in:<channel> from:<owner> after:<YYYY-MM-DD>` (the day before the look-back window starts), sorted by timestamp, without context. Keep only top-level posts: those with no `thread_ts`, or whose `thread_ts` equals their own `message_ts`. Thread replies are not announcements.

From each post, take every PR or merge-request URL:

- GitHub: `https://github.com/<org>/<repo>/pull/<n>`
- Other hosts (for example a self-hosted GitLab `.../-/merge_requests/<n>`): note them, but their state usually can't be read from here (see step 3).

Skip posts with no PR link. If a post links several PRs, a reaction applies only when it is true of all of them; otherwise report the mix and add nothing.

## 2. Check what's already there

Fetch the reactions on each post. A reaction the owner already added counts as done.

## 3. Decide the merged reaction

- **GitHub PR:** `gh pr view <n> --repo <org>/<repo> --json state,mergedAt,mergeCommit`. Add the merged emoji when `state` is `MERGED`. Closed without merging gets nothing.
- **Other hosts:** their state can't be read. Add the emoji only on firm evidence: the owner's own reaction, a teammate's message in the thread saying it merged, or a vault note recording the merge. Otherwise report it as unchecked.

## 4. Add the reactions

For each reaction still missing, call the add-reaction tool with the channel ID, the post's `message_ts`, and the emoji name without colons.

## 5. Report

A short table: post time, PR link, merged reaction (added, already there, or not merged) and the reason for each skip. List any PRs whose state couldn't be checked.

## Optional second rule (off unless configured)

Some teams want a second reaction meaning "this change has also reached some other environment" (a restricted network, a mirror, a second repository host). This is entirely user-defined; the skill ships no rule. If `integrations.slack.second_reaction` is configured, it has an emoji name and a table of repositories like this (fictional example):

| Repo | How it reaches the other environment | When to add the second emoji |
| --- | --- | --- |
| `acme/tools` | Mirror tracks `main` directly | When the PR is merged |
| `acme/service` | Needs a separate promotion step | Only once the user or a note confirms the promotion |
| Anything else | Unknown | Skip, and list the repo in the report |

Apply it only on the stated evidence. When unsure, leave the second emoji off and report it: a missing reaction costs less than one that claims something untrue. When the user corrects the table, update it in the config.
