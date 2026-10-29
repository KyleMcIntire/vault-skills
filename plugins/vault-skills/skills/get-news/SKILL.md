---
name: get-news
description: "Gather the news, release notes and security announcements that matter to your work into a digest note and a short chat summary. Reads a configurable list of RSS/Atom feeds (cloud provider announcements, project release feeds, security news), optional Slack announcement and incident channels, ranks security incidents first, optionally compares releases with the versions you pin, and adds a weather summary for your location. Read-only toward everything outside the vault. Use whenever the user asks \"what's new\", \"any news I should know about\", \"catch me up on <topic> news\", for a news or release digest, or what changed upstream this week, even if they don't name this skill."
argument-hint: "[days to look back, default 7]"
---

# Get news

Tell the user what changed upstream that bears on their work. The script collects and filters feed items; you judge relevance and write the digest. Read-only toward everything outside the vault: post nothing to Slack, Jira or GitHub.

## Setup

Read `.vault-skills.yaml` at the vault root (see `docs/CONFIG.md`) and the vault's `CLAUDE.md`. Values used:

| Need | Config key | If missing |
| --- | --- | --- |
| Digest folder | `folders.news` (default `News`) | use the default |
| Extra feed URLs | `integrations.news_feeds.rss` | none |
| Slack channels to scan | `integrations.news_feeds.slack_channels` | skip the Slack step and list it under Gaps |
| Weather location | `integrations.weather_location` ("City, Region") | ask once; if declined, skip weather |
| Scratch dir | `$CLAUDE_JOB_DIR/tmp/`, else `<folders.scratch>/` | |
| Digest template | `folders.templates` + `News Digest Template.md` if present | use [references/digest-layout.md](references/digest-layout.md) |
| Pinned versions (optional) | none in the config: a JSON file the user maintains, see below | skip the pin comparison |

The feed list is a JSON file the user owns. The skill ships an **example, clearly editable** list of public tech and security feeds in [references/example-feeds.json](references/example-feeds.json). On first use, copy it into the vault (for example `<folders.news>/feeds.json`), tell the user it is theirs to edit, and use the copy afterwards. Kinds: `filter` (keyword matches only), `release` (stable versions of software you run; add `"product"` to enable the pin comparison), `security` (incident-like titles only), `cisa`, `all`, `local`. `keywords` in that file drive the `filter` kind.

**Formatting:** write every version in inline code, for example `v3.5.6` or `1.14.1`, in the digest and in chat.

## 1. Collect

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/get-news/fetch_news.py" <days> \
  --feeds <feeds.json> --seen "<vault>/<folders.news>" \
  [--rss <url> ...] [--pins <pins.json>] [--location "<weather_location>"] [--local-area "<regex>"] \
  > "$CLAUDE_JOB_DIR/tmp/get-news.json"
```

`<days>` defaults to 7. Pass each `integrations.news_feeds.rss` URL with `--rss`. `--seen` drops items an earlier digest already links, so a repeat run lists only what is new (`already_in_digests` says how many). Then read the JSON file. It holds:

- `items`, newest first: `source`, `product`, `date`, `title`, `link`, `matched`, `in_title`, `excerpt`, `security` (true for security-feed items and incident-like titles) and, for release items with a pinned product, `pin_note`.
- `local`: recent stories from `local` feeds (at most 3 days), not in `items`.
- `weather` (when a location was given): `days` (today and the next two: `high`, `low` in F, `rain_chance`, `sky_percent`, `condition`, `wind_max_mph`, `sunrise`, `sunset`), `aqi`, `alerts` (US National Weather Service only; elsewhere an error is reported), and `errors` per part.
- `pins`, `counts` and `errors` per source.

Rules:

- A source in `errors` failed: list it under **Gaps** with its error text. Never present it as "nothing new".
- A source with count 0 is quiet in the window, not broken.
- Keyword-filtered feeds can miss an item whose wording avoids the keywords.

### Pins (optional)

To compare releases with what you run, keep a small JSON file (see [references/example-pins.json](references/example-pins.json)): product name to `[{"version", "where"}]`. Pass it with `--pins`. The user maintains it, or offers to have you read the version from their infra repos once; never guess a pin. When a pin decides the call, say where it came from and that it may lag the source of truth.

## 2. Slack (optional)

Skip this if the session has no Slack connector or `integrations.news_feeds.slack_channels` is empty, and list the skip under **Gaps**. Otherwise load the Slack read tools and read each configured channel with `oldest` set to the window start, a small `limit` and a concise response format. Keep posts that announce something about platforms, deploys, maintenance windows, security or the user's cloud services; ignore chatter and bot noise. Quote sparingly and link each message. If a channel can't be read, list it under **Gaps**. Never post, react or draft.

Then search Slack broadly for incident terms (`incident`, `outage`, `vulnerability`, `CVE`, `breach`, plus the distinctive title of any security story the feeds returned), since an incident can land in a channel that isn't listed. Carry an incident channel's status, actions and open needs into the digest.

## 3. Judge

For each item decide whether it matters to the user's work, and say why in a clause. Rank by effect, not date:

0. **Security incidents first**: a CA or signing-key compromise, a supply-chain attack on a package, image or tool the user runs, an exploited or emergency-patched flaw in a runtime, OS package, orchestrator or cloud service they use, and any incident their organization has declared. Security feeds are broad: keep an item only when it touches what the user runs, or when an internal channel is already discussing it. For each: what happened, severity, what to do (patched versions, rebuilds), and open needs. Check `<folders.tasks>/` for a task note already tracking it and link it. An incident that is in the news and in Slack but absent from the digest is the worst miss: when a story appears in several security sources, search Slack for it by name before dropping it.
1. **Acts on something the user runs or pins**: a release of a pinned product, a platform version or deprecation, an image advisory, a change to a service they use. Use `pin_note` to say whether it is a newer patch of a pinned version, a different line, or a newer minor. Read the `excerpt` for breaking changes and security fixes; when it is cut off and matters, fetch the item's link and quote only the relevant lines.
2. **Compliance or regional scope changes** relevant to the user.
3. **Slack announcements** touching the platform or deploys: rank by effect.
4. **Worth knowing**: industry incidents and vendor announcements, one line each. Group releases of tools with no pin lookup in one **Releases** bullet and say they were not compared with what the user runs.
5. **Local** (if `local` feeds are configured): the few stories most worth a glance for someone living there; drop statewide or national ones that merely mention the area and list them under **Skipped**.

Drop the rest. Separate recorded facts (what the post says, what the pin file says) from inference about why it matters, and mark inferences ("likely"). Never infer an affected version without a `pin_note` or a pin you read yourself.

## 4. Write the digest

Create `<folders.news>/YYYY-MM-DD News.md` (today's date) from the vault's template if there is one, otherwise from [references/digest-layout.md](references/digest-layout.md). Resolve template placeholders. If today's note already exists, re-read it and add only new items, keeping the user's edits. Fill the numeric and text properties: `window`, `incidents`, `needs a look`, `summary`, and the weather properties from `weather` for today (leave them empty and say so under **Gaps** if weather failed or was skipped).

- **Security incidents:** one callout per incident (`[!danger]` for one that touches the user's own systems, `[!warning]` otherwise) with bullets for Status, What happened, Fixed versions, Open needs, Sources; leave out a label with nothing to say.
- **Needs a look:** one table row per item (Item, Version, Our pin, Why it matters). Version in inline code with its release link; the pin with where it came from; `-` when there is no version.
- **Worth knowing:** short bullets under a bold lead word, every item with its link.
- **Skipped** and **Gaps:** collapsed callouts, links separated by ` · `. Every item you drop as irrelevant goes in **Skipped** as a bare link, because `--seen` only knows links a digest contains.
- Do not put the skill's own history in the digest.

If the vault keeps a news hub or index note, add the new digest to its list, newest first (skip if already listed). Open the new note in Obsidian in a new tab if a tool for that is available. Do not stage, commit or move anything.

## 5. Brief in chat

A short version of the digest: any **Security incidents** first, then the **Needs a look** items with links and why, one line for everything else, and the **Gaps**. Do not repeat the whole note.

## 6. Offer, don't do

Offer as a short list, and do one only when the user picks it: add a `- [ ]` task to today's daily note for an item needing follow-up; start a version bump through `/vault-skills:work-on`; read a linked post in full. Do not invent owners or deadlines. If asked to share an item in Slack, draft it (never post). In any draft that leaves the vault, apply `safety.redact_identifiers` from the config (for example, refer to CVEs by label instead of ID when the user's rules say so).

## Scheduling (optional)

To get a digest every morning, see [references/launchd-plist-template.md](references/launchd-plist-template.md) for a generic macOS LaunchAgent and wrapper script with placeholders.

## Known limits

- Security feeds are filtered by incident-like words in the title, so a story phrased without them can be missed; the Slack incident search is the backstop.
- X/Twitter and similar feeds have no key-free source. Say so under **Gaps** rather than implying they were checked.
- Weather alerts come from the US National Weather Service; other regions get forecast and air quality only.
- The AQI is a model value, not a station reading.

## Offline test

`fixtures/make_fixture.py <dir>` writes fictional local feed files, a feed list and a pins file; run `fetch_news.py 7 --feeds <dir>/feeds.json --pins <dir>/pins.json` against them (no network needed without `--location`).
