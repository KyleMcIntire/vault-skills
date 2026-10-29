---
name: draft-in-voice
description: Draft a Slack message (or a Jira or pull request comment) in the vault owner's own voice, using the style profile learned in the vault's Voice and Style note - their typical length, formatting, emoji and recurring phrasings. Saves Slack drafts with the draft tool and never posts. Use whenever the user asks to draft, write, word or announce something in Slack "like me", "in my voice", or just "draft a message to ..." for a channel, thread or person, even if they do not name this skill.
argument-hint: "[who or where] [what to say]"
---

# Draft in voice

Write the message the way the owner would. **Draft only**: never post, send, react or reply. The style comes from the vault, not from guessing.

## 0. Configuration

Read `.vault-skills.yaml` at the vault root (see `docs/CONFIG.md`) and the vault's `CLAUDE.md`. Used here: `folders.preferences`, `owner.name`, `integrations.slack` (announce channel, team handle), `integrations.jira.site` and `integrations.github.org` (to build links), and `safety.redact_identifiers`. Ask once if a value you need is missing.

## 1. Load the style

`Read` `<folders.preferences>/Voice and Style.md` (the **Patterns by message type** table, **Emoji I use**, **Voice, inferred**, **Exemplars**) and the communication rows of `<folders.preferences>/Learned Preferences.md`. They override any default below.

If either note is missing or empty, say so, offer to create the blank starters from this skill's `references/` folder, run `/vault-skills:learn-preferences` to fill them, and draft in a plain neutral style meanwhile, labelled as such.

## 2. Pick the message type

Choose the closest row from the **Patterns by message type** table (for example PR announcement, heads-up, ask to another team, review request, done, longer technical post). If the channel matters and a Slack connector is available, read the last few messages of the channel or thread so the draft fits it. For a person, search users to get the real @mention. Without a connector, leave a clearly marked placeholder for the mention.

## 3. Draft it

- Keep it as short as the type allows; one line when one line does it.
- Follow the profile for case, punctuation, markdown, inline code and emoji. At most one or two emoji, only from the **Emoji I use** table, at the end of the sentence they color.
- Facts and links first, then the ask or next step; add a light hedge or thanks only where the profile shows the owner doing so.
- Hyperlink every PR, MR, ticket and thread you mention, if the profile or vault rules say to. Build URLs from `integrations.jira.site` / `integrations.github.org` and the source notes, never leave a bare number when you can find the link, and say in the reply when you cannot.
- PR announcements follow the owner's pattern (usually the team handle plus the URL, posted to `integrations.slack.announce_channel`).
- Apply `safety.redact_identifiers`: replace matching identifiers with neutral labels in anything that leaves the vault. Include no secrets, customer content or meeting passcodes.

## 4. Show and save

Show the draft in a block with one line saying which pattern and emoji you used. When the user names a channel or thread and a Slack draft tool exists (for example `slack_send_message_draft`), save it as a draft; if the tool fails or is missing, fall back to a code block with bare URLs. Offer at most one tweak ("shorter", "less formal"). **Do not post.**

## 5. Corrections

If the user corrects the tone, apply it. The next `/vault-skills:learn-preferences` run records it; if they ask now, add it as a `low` row under the communication heading of Learned Preferences.
