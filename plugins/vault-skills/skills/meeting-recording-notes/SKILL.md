---
name: "meeting-recording-notes"
description: "Turn a meeting recording (.m4a, .mp3, .wav, .mp4, Zoom or Teams audio) into a speaker-labeled transcript and a finished Obsidian meeting note, with a TL;DR, decisions, Tasks-plugin action items for the vault owner, a table of what they are waiting on from others, timestamp links into the transcript, and an optional project log entry. Detects recordings that cover several back-to-back meetings (e.g. standup + planning + refinement) and, after the user confirms the split, writes one note per meeting. Use whenever the user shares or points at a recording and asks for notes, a summary, minutes, a transcript, action items, \"who said what\", or wants a meeting \"in Obsidian\", even if they do not name this skill. Also use to relabel speakers or regenerate the transcript of a note this skill already made."
---

# Meeting recording → Obsidian note

**Config first.** Read `.vault-skills.yaml` at the vault root (see the repo's `docs/CONFIG.md`) and the vault's own `CLAUDE.md`. This skill uses `owner.name`, `owner.note`, `owner.aliases`, `folders.meetings`, `folders.people`, `folders.projects`, `folders.templates`, `templates.meeting` and, optionally, `integrations.calendar_mail` and `integrations.catalog`. If a needed value is missing, ask once and offer to write the answer into the file. Below, `<owner>` is `owner.name`, and `<meetings>`, `<people>`, `<projects>` are the configured folders.

The pipeline has five stages. Transcribe with word timestamps, check whether the recording holds more than one meeting, embed the voices, put names on the voices with the owner's confirmation, then write the note (or one note per meeting) and let a script attach the transcript. The scripts do the mechanical work, so your effort goes into splitting correctly, naming speakers correctly and writing a sharp summary. Throughout, the **owner** is the person whose vault this is; "you" in a note means them.

**Requirements.** The heavy steps run locally on an Apple Silicon Mac (mlx-whisper uses the Apple GPU). This needs ffmpeg (`brew install ffmpeg`) and python3. On other platforms, say so and stop rather than improvising another speech-to-text route; the scripts have not been tested there.

- **Claude Code** (CLI or the desktop app's Code tab): run every command directly with the Bash tool. Use `run_in_background` for the long jobs; you're notified when they exit, so don't poll.
- **A sandboxed agent mode** (a Linux sandbox that cannot download models or reach the Mac): run commands through a tool that executes on the Mac host, such as Desktop Commander, if you have one.

`SKILL_DIR` below means this skill's base directory, as given when the skill loads. `<vault>` is the vault root. Use host paths in commands.

Scripts never read the YAML config. Pass what they need as flags: `--vault <vault>`, `--people-folder <folders.people>` and `--me "<owner.name>"` (to `render_note.py` and `speakers.py`).

## 0. Gather context (in parallel with setup)

- **Audio path on the Mac.** The user gives a path or drags the file into the prompt. In a sandboxed mode, use the host path, not the sandbox path, since the scripts run on the Mac. Apple Voice Memos live in `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/`, but macOS blocks the terminal there without Full Disk Access. If `ls` says "Operation not permitted", ask the user to share the memo to a folder (Voice Memos → Share → Save to Files) and give that path.
- **Meeting facts.** Collect the title, the date (the recording's `creation_time` via `ffprobe`, converted from UTC), the duration, the attendees and the project. The user usually names the attendees in their message.
- **The calendar invite (optional).** If `integrations.calendar_mail` is configured, look the meeting up with your calendar skill or tool (for example `/vault-skills:mail-calendar`: `meetings --day <recording date>`, pick the occurrence whose start is closest to `creation_time`, then `meeting <event_id>`). The invite gives:
  - the meeting's real title, scheduled start and end, organizer, and the invite notes (agenda, topics, ticket keys);
  - the attendee list with names, emails and responses. Accepted and tentative attendees are the likely speakers; the list says who was invited, not who came or spoke.
  If the user named attendees, their list wins. If no calendar is available or nothing matches (a personal call, an ad hoc huddle), carry on without it and say so.
- **People notes.** Map attendees to people notes, the owner's included, with `find <vault>/<people> -name "*.md"`. Match invite attendees by the `email` property first (`grep -rl "^email: <address>" <people>`), then by name.
- **Multi-meeting hints.** Note anything suggesting the recording spans several meetings: a filename with `+`, "and" or several meeting names (for example "Standup + innovation planning + backlog refinement"), a duration well over an hour, or back-to-back events in that window on the owner's calendar. The calendar lookup above shows them, with their titles and scheduled times.
- **Vault rules.** Read `references/vault-conventions.md` now. It covers where the note goes, the frontmatter, the task format and the structure. Recurring team meetings go in a **folder per meeting type** under `<meetings>/Recurring/`. Use an existing folder when one fits, and create a new one only for a new meeting type. Project meetings go in `<meetings>/Projects/<Project>/`. Leave rolling logs where they are. If the vault's own `CLAUDE.md` or meeting template lays things out differently, follow the vault.

## 1. Set up and transcribe (Mac, background)

Run the `transcribe.py` and `embed.py` commands below without `nohup … &` and with `run_in_background`, keeping the log redirect. In a sandboxed mode whose calls time out after about a minute, start long jobs with `nohup … &`, then poll with short loops like `for i in $(seq 1 10); do grep -q DONE log && break; sleep 5; done; tail -3 log`, keeping each poll under 55 s.

```bash
bash SKILL_DIR/scripts/setup_env.sh          # idempotent; prints PYTHON= and HF_HOME=
RUN=~/.cache/meeting-notes/runs/<yyyy-mm-dd-slug>
export HF_HOME=~/.cache/meeting-notes/hf
nohup ~/.cache/meeting-notes/venv/bin/python SKILL_DIR/scripts/transcribe.py "<audio>" --out-dir $RUN \
  --prompt "<attendee names from the invite or the user, project names, product and team jargon>" > $RUN.transcribe.log 2>&1 &
```

The first run downloads about 1.5 GB of models. After that, it takes roughly 3 to 5 minutes per hour of audio. The log shows nothing between the model fetch and `DONE`, so keep polling. Put real names and jargon in `--prompt`, because it noticeably improves spelling.

Then compute the voice embeddings. This takes about a minute on Apple's GPU:

```bash
nohup ~/.cache/meeting-notes/venv/bin/python SKILL_DIR/scripts/embed.py --out-dir $RUN > $RUN.embed.log 2>&1 &
```

## 2. Detect multiple meetings

Run this as soon as `words.json` exists. It's safe to run while the embeddings compute. It prints quiet stretches (breaks, or the dead air before and after the meeting, which Whisper often fills with "Thank you.") and hand-off phrases with their timestamps:

```bash
~/.cache/meeting-notes/venv/bin/python - "$RUN/words.json" <<'EOF'
import json, re, sys, bisect
W = json.load(open(sys.argv[1]))
h = lambda s: f"{int(s)//3600}:{int(s)%3600//60:02d}:{int(s)%60:02d}"
filler = re.compile(r"^(thank|you|thanks|bye|okay|so|uh|um|oh|wow)\W*$", re.I)
end = W[-1]["e"]; bins = [0] * (int(end // 30) + 1)
for w in W:
    if not filler.match(w["w"].strip()): bins[int(w["s"] // 30)] += 1
runs, i = [], 0
while i < len(bins):
    if bins[i] < 8:
        j = i
        while j + 1 < len(bins) and bins[j + 1] < 8: j += 1
        if (j - i + 1) * 30 >= 120: runs.append((i * 30, (j + 1) * 30))
        i = j + 1
    else: i += 1
print("QUIET (>= 2 min):", ", ".join(f"{h(a)}-{h(b)}" for a, b in runs) or "none")
text, idx = "", []
for w in W: idx.append(len(text)); text += w["w"]
pat = re.compile(r"(move on to|moving on to|let'?s (start|begin|go to|switch to|jump to|do) (the )?\w+|next (topic|agenda|item|meeting)|"
                 r"that'?s it for (the )?(standup|stand-up|today)|take a (short )?break|see you in \w+ minutes|meet (again )?in \w+ minutes|"
                 r"welcome( back)?|(i'?d|i would|let'?s) (like (us )?to )?(talk|move) (about|on)|(start|kick off) (the )?(refinement|retro|planning|review|demo))", re.I)
seen = -999
for m in pat.finditer(text):
    t = W[bisect.bisect_right(idx, m.start()) - 1]["s"]
    if t - seen < 45: continue
    seen = t
    print(f"CUE {h(t)}  …{text[max(0, m.start()-50):m.end()+50].strip()}…")
print("DURATION", h(end))
EOF
```

Cues are candidates, not answers. Read the transcript around each one and decide where each meeting really starts and ends. Signs of a real boundary:

- The agenda changes. Standup round-robin turns into "let's move on to the refinement", or planning turns into "now I'd like to talk about the Rancher epic".
- A different person starts facilitating, or someone shares their screen again.
- The calendar or the filename names that meeting. A calendar meeting's scheduled start, as an offset from `creation_time`, is where to look for its boundary.

A break inside one meeting ("let's meet in 7 minutes") is **not** a boundary. Mark it as a range to drop instead.

**If you find more than one meeting, confirm the split with the user using AskUserQuestion.** Put it in the same call as the speaker confirmation in step 3, so they answer once:

- Propose each meeting with a name, a start–end range in recording time, a one-line summary and the folder it goes in, for example: "① Standup 0:36–12:33 → `Standup/` · ② Sprint planning 12:33–51:51 → `Planning/` · ③ Backlog refinement 51:51–2:05:50, dropping the break 53:10–1:00:55 → `Backlog Refinement/`".
- Options: **Split as proposed (Recommended)**, **Keep as one note**, and one alternative merge if a boundary is debatable (for example "Merge ② and ③"). They can type different boundaries in Other.
- If there's only one meeting, skip the question. Still drop the dead air at the start and end, and any mid-meeting break.

## 3. Name the speakers (discover → infer → confirm → anchor)

Speakers are named once for the whole recording, even when it's split. Voices carry across meetings.

Raw clustering alone splits a meeting badly. It tends to make one huge cluster and a few tiny ones. Seeding each speaker from stretches you're confident about, then refining, works much better. Here's the process:

1. **Discover.** Run `~/.cache/meeting-notes/venv/bin/python SKILL_DIR/scripts/assign.py --out-dir $RUN --speakers <N attendees>` (always with the venv's Python, as here: the system `python` has no numpy), counting the user's list or the invite's accepted and tentative attendees. Read `$RUN/transcript.txt` and `$RUN/samples.txt`. In a sandboxed mode, copy them into the outputs folder first.
2. **Infer names** from the content rather than the cluster numbers:
   - Direct address: in "Thanks, Alex" or "Sam, do you have…", the speaker is someone else, and the named person usually answers next. A standup host calling "And Jo?" is the strongest cue.
   - Self-reference and ownership: "my PR", "I created the ticket", "my workflow".
   - Who demos or explains which system: long monologues are the most reliable stretches.
   - What the user said about the attendees, then the invite's attendee list from step 0.
   - For a team meeting with no attendee list from the user or the invite, a team roster can give candidate names and spellings. If `integrations.catalog` is configured and its MCP server is connected (for example Backstage), query the team's group members; otherwise skip this. The roster lists who could be there, not who attended, so it is never evidence that someone spoke.
3. **Pick anchors.** For each person, choose one to three stretches of 30 seconds or more where only they talk, such as a demo or an explanation, with no back-and-forth.
4. **Confirm with the user** using AskUserQuestion, together with the split question from step 2. For each voice, show your proposed name with one or two short quotes and timestamps, and let them correct any of them. If they reject a name without giving the right one, ask a short follow-up. Ten seconds of confirming beats wrong names in their notes.
5. **Assign.** Run `~/.cache/meeting-notes/venv/bin/python SKILL_DIR/scripts/assign.py --out-dir $RUN --anchor "Alex=15:50-17:10,51:44-54:00" --anchor "Jo=1:00:27-1:03:00" …`, with one `--anchor` per person. Read `anchor_check.txt`. Under about 60% matched means a weak anchor, so pick a cleaner stretch and rerun; it only takes seconds.
   - **Silence anchor.** If the recording has dead air or a break, add `--anchor "Silence=<quiet ranges>"` so hallucinated "Thank you" lines don't pull a real person's voice. Drop those lines when splitting (step 4).
   - **Late joiners.** Someone who joins partway through can absorb other people's backchannel before they arrive. Run `assign.py` without their anchor for the part before they joined and with it afterward, and keep each run's `lines.json` for its own time range.
6. **Spot-check.** Read through `transcript.txt`. Check direct-address lines ("Thank you, Sam" shouldn't be Sam). Fix clear slips with `--override "19:33=Sam"`. Label short lines you can't attribute as `Unidentified`. Don't chase every one-word "yeah"; the warning callout in the note covers that.

If someone spoke for under a minute or so, they may never form their own voice. Label their lines by content and say so in the note, rather than forcing a cluster.

## 4. Split the transcript (only for multiple meetings)

After `lines.json` is final, cut it into one file per confirmed meeting and remove the drop ranges. Ranges are in recording time, end-exclusive:

```bash
~/.cache/meeting-notes/venv/bin/python - "$RUN" standup=0:36-12:33 innovation=12:33-51:51 refinement=51:51-2:05:50 drop=53:10-1:00:55 <<'EOF'
import json, sys
D, specs = sys.argv[1], sys.argv[2:]
t = lambda x: sum(int(v) * 60 ** i for i, v in enumerate(reversed(x.split(":"))))
L = json.load(open(f"{D}/lines.json"))
drops = [tuple(map(t, s.split("=", 1)[1].split("-"))) for s in specs if s.startswith("drop=")]
L = [l for l in L if not any(a <= l["s"] < b for a, b in drops) and l["sp"] != "Silence"]
for s in specs:
    if s.startswith("drop="): continue
    slug, rng = s.split("=", 1); a, b = map(t, rng.split("-"))
    part = [l for l in L if a <= l["s"] < b]
    json.dump(part, open(f"{D}/lines_{slug}.json", "w"))
    print(f"{slug}: {len(part)} lines, speakers {sorted({l['sp'] for l in part})}")
EOF
```

For a single meeting, run it with one slug (for example `main=0:36-58:10`) to trim the dead air. Then use `lines_main.json`.

## 5. Write each note head, then render

Read the full transcript (or the segment) before writing. Then write the note **head**: frontmatter, TL;DR, action items, waiting on others, decisions, discussion, open questions and glossary. Follow `references/vault-conventions.md`, and see `references/example-note-head.md` for a finished example at the expected level of detail. Save it to `$RUN/head.md`, or `$RUN/head_<slug>.md` per meeting.

- Wherever a point comes from a moment in the meeting, write `{{ref:MM:SS}}` or `{{ref:H:MM:SS}}` using times from `transcript.txt`. The script turns these into links to the transcript line.
- Link the owner like every other attendee: `"<owner.note>"` in `attendees` and `[[<owner.name>|First]]` wherever the body names them (if they have no person note, write plain text). Never leave a person who has a note as plain text.
- Every attendee who has a people note goes in `attendees` as a `[[Full Name]]` link, since `render_note.py` links the transcript speaker labels from that list. Check `render_note.py`'s `left plain` output and fix any real person it lists.
- Owners come from the confirmed speaker labels. Mark anything still uncertain with *(confirm)*.
- Use absolute dates. Resolve "tomorrow" or "Friday" against the meeting date. For "at the next working group" or "in Thursday's office hours", find the real occurrence with `meetings --day <meeting date> --days 14 --search <title word>`.
- Write plainly: short bullets, specific facts (tags, versions, cluster counts, ticket keys), no filler.

**When split, each note stands alone:**

- **Frontmatter.** Give each note its own `title`, `meeting type` (`standup` for standups, `sprint` for planning, refinement, retro and review), `start` (recording start plus the segment offset) and `duration` (segment length, breaks included).
- **Attendees.** List only the people who spoke or were present in that segment. For example, someone who joined during refinement isn't a standup attendee.
- **Links.** Add a "Same call:" link to the other notes on the links line under the H1.
- **How-this-was-made callout.** Say which part of the recording the note covers, that timestamps are positions in the full recording, and which ranges were dropped.
- **Content.** Put action items, waiting-on rows and decisions only in the note where they came up. Don't repeat them across notes.

Render each note:

```bash
~/.cache/meeting-notes/venv/bin/python SKILL_DIR/scripts/render_note.py --lines $RUN/lines_<slug>.json --head $RUN/head_<slug>.md \
  --out "<vault>/<meetings>/<Recurring/<Type> or Projects/<Project>>/<YYYY-MM-DD Title>.md" \
  --corrections SKILL_DIR/references/term-corrections.json --corrections SKILL_DIR/references/term-corrections.local.json \
  --vault <vault> --people-folder <people> --me "<owner.name>"
```

The script prints any unresolved refs or leftover placeholders, and both should be "none". `term-corrections.json` is a starter list of regex fixes for transcription errors that come up again and again ("cube config" becomes kubeconfig, "carpenter" becomes Karpenter, "dependable" becomes Dependabot). Put the user's own team, product and colleague names in `term-corrections.local.json`, which starts empty (see `references/README.md`); add a pair after the user agrees when an error repeats. Fix one-offs in the transcript by hand. If the skill folder is read-only, merge extra pairs into a scratch corrections file in `<folders.scratch>` and tell the user which pairs to add.

## 6. Finish up

- Project meetings get a dated entry in the project's rolling log if one exists, as described in vault-conventions: add it with `Edit`, anchored on the newest existing entry heading, at that heading's level. Recurring meetings with one note per session are not logged. If a note for that session already exists and holds the owner's plan, do not overwrite it: copy its body into the new note as a section placed before the Transcript heading, then render over the old file. Planning, refinement and retro notes have no log of their own: link them from that day's standup or daily note if the vault keeps one.
- If an editing session cannot write to the main checkout (for example a background session that requires a worktree), patch the log through the Obsidian MCP instead, or enter a worktree before the log edit. `render_note.py` writes the note itself straight to its `--out` path.
- Run the vault's checker if it has one and expect no new findings. Do not stage, commit or push.
- Delete `$RUN/audio.wav`, which is about 150 MB. Keep `words.json`, `E.npy`, `C.npy` and the `lines*.json` files so a relabel later takes seconds.
- If the Obsidian MCP is connected, open every note you created with `open_file` and `newLeaf: true`, so each gets its own tab, in recording order. Without the MCP, use the Obsidian CLI (`obsidian open path="<note>" newtab`) when it is available. Do the same when a later fix creates or re-splits notes. The owner will want to review each one.
- In your reply, give the outcome in 2 to 3 sentences (for a split, list each note and its folder), the owner's own action items and due dates, and anything flagged *(confirm)*. Only offer to create tickets if the user has not said someone else handles them.

## Extras (only when asked)

- **Link speakers in an existing note.** `python3 SKILL_DIR/scripts/speakers.py "<note>.md" --vault <vault> --people-folder <people> --me "<owner.name>" [--dry-run]` links the `**Name:**` labels in a note's transcript from its `attendees`. It is idempotent.

- **Plain transcript file.** Add `--raw-out <path>` to `render_note.py` to also write `[HH:MM:SS] Name: text`.
- **Shareable web page.** If your environment has an artifact or page-publishing tool, build a page from the note's content with a searchable transcript and a speaker column. It stays private until the user shares it.
- **Relabel an existing note.** Rerun `assign.py` with corrected anchors (and re-split if it was split), then run `render_note.py --lines … --out <existing note>` without `--head`. It keeps everything above `## :TwStudioMicrophone: Transcript`, re-points the existing :TwStopwatch: links and replaces the transcript.
- **Split an existing combined note.** Rerun steps 2 and 4 from the saved run folder, write one head per meeting from the combined note's content, render them, update the log entries to link the new notes, then delete the combined note.

## If something fails

- **`ffmpeg missing`:** ask the user to run `brew install ffmpeg`.
- **Model download blocked or very slow:** the Hugging Face hub is needed on first run. Retry, or ask whether they are on a VPN or proxy.
- **In a sandbox with no host access, or not on an Apple Silicon Mac:** the models can't run, so say so and stop rather than improvising another speech-to-text route.
- **Embedding on CPU is slow (10+ min):** that's expected when `mps` isn't available. Let it run and keep polling.

