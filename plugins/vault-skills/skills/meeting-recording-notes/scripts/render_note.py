"""Attach a speaker-labeled transcript to an Obsidian meeting note and resolve timestamp links.

Usage:
  # new note: HEAD is the note you wrote (frontmatter + summary) with {{ref:MM:SS}} or {{ref:H:MM:SS}} placeholders
  python render_note.py --lines DIR/lines.json --head head.md --out "Vault/…/2026-10-07 Title.md" \
      [--corrections term-corrections.json] [--corrections term-corrections.local.json] [--raw-out DIR/raw_transcript.txt] \
      [--me "Alex Example"] [--vault DIR] [--people-folder People]

  # existing note (e.g. after relabeling speakers): keep everything above "## :TwStudioMicrophone: Transcript" (or the older "## 🎙️ Transcript"),
  # re-point its [[#^tHHMMSS|…]] links at the new lines, and replace the transcript
  python render_note.py --lines DIR/lines.json --out "existing note.md" [--corrections …]

Each transcript line becomes a list item with a block ID so it can be linked:
  - `53:59` **Alex:** Yeah, since I've got the experience… ^t005359
A placeholder resolves to the latest line starting at or before that time: [[#^t005359|:TwStopwatch: 53:59]]
Speaker labels are linked to the attendees' people notes: **[[Sam Sample|Sam]]:** (scripts/speakers.py).
Inside Markdown table rows the pipe is escaped (\\|) so the table doesn't break.
"""
import argparse, bisect, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import speakers
from speakers import link_speakers

ap = argparse.ArgumentParser()
ap.add_argument("--lines", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--head")
ap.add_argument("--corrections", action="append", default=[], help="JSON list of [regex, replacement]; repeatable")
ap.add_argument("--raw-out")
ap.add_argument("--me", default="", help="owner.name; linked like any attendee (optional)")
ap.add_argument("--vault")
ap.add_argument("--people-folder")
ap.add_argument("--heading", default="## :TwStudioMicrophone: Transcript")
a = ap.parse_args()
speakers.configure(a.vault, a.people_folder, a.me)
ME = a.me

L = json.load(open(a.lines))
subs = []
for _cf in a.corrections:
    subs += [(re.compile(p), r) for p, r in json.load(open(_cf))]
def fix(t):
    for p, r in subs: t = p.sub(r, t)
    return t

def hms(s): s = int(s); return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"
def lab(s): s = int(s); return f"{s//3600}:{s%3600//60:02d}:{s%60:02d}" if s >= 3600 else f"{s//60:02d}:{s%60:02d}"
def tid(s): return "t" + hms(s).replace(":", "")
def tsec(x):
    s = 0
    for v in x.split(":"): s = s * 60 + int(v)
    return s

ids, seen = [], set()
for l in L:
    s = int(l["s"])
    while s in seen: s += 1  # block IDs must be unique
    seen.add(s); ids.append(s)
def at(sec):
    return ids[max(bisect.bisect_right(ids, sec) - 1, 0)]
def link(sec, table):
    s = at(sec); sep = "\\|" if table else "|"
    return f"[[#^{tid(s)}{sep}:TwStopwatch: {lab(s)}]]"

if a.head:
    head = open(a.head).read()
else:
    _txt = open(a.out).read()
    _legacy = "## 🎙️ Transcript"  # notes written before the Twemoji shortcode headings
    head = _txt.split(a.heading if a.heading in _txt else _legacy)[0]
    # re-point existing links at the new line IDs
    head = re.sub(r"\[\[#\^t(\d{2})(\d{2})(\d{2})(\\?\|)(?::TwStopwatch:|⏱️) [\d:]+\]\]",
                  lambda m: link(int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]), m[4] == "\\|"), head)

out = []
for line in head.rstrip().split("\n"):
    table = line.lstrip().startswith("|")
    out.append(re.sub(r"\{\{ref:([\d:]+)\}\}", lambda m: link(tsec(m[1]), table), line))
head = "\n".join(out)

# The owner has a person note: link them like everyone else (only when --me is given).
# Skips code, URLs, Markdown links, existing wiki-links and headings, so it is safe to rerun.
PROTECT = re.compile(r"(\[\[.*?\]\]|\[[^\]]*\]\([^)]*\)|`[^`]*`|https?://\S+)")
def link_me(text):
    first = ME.split()[0]
    def sub(part):
        part = re.sub(rf"\b{re.escape(ME)}\b", f"[[{ME}]]", part)
        return re.sub(rf"\b{re.escape(first)}\b(?! {re.escape(ME.split()[-1])})", f"[[{ME}|{first}]]", part)
    return "".join(p if i % 2 else sub(p) for i, p in enumerate(PROTECT.split(text)))
if ME:
    fm = re.match(r"---\n.*?\n---\n", head, re.S)
    fm_text, rest = (fm.group(0), head[fm.end():]) if fm else ("", head)
    fm_text = re.sub(rf"^(\s*-\s+){re.escape(ME)}\s*$", rf'\1"[[{ME}]]"', fm_text, flags=re.M)
    rest = "\n".join(l if l.lstrip().startswith("#") else link_me(l) for l in rest.split("\n"))
    head = fm_text + rest

note_name = os.path.splitext(os.path.basename(a.out))[0]
tx = "\n".join(f"- `{lab(s)}` **{l['sp']}:** {fix(l['t'])} ^{tid(s)}" for s, l in zip(ids, L))
body = (f"\n\n{a.heading}\n\nAuto-generated with timestamps and speaker labels. Each line has a block ID "
        f"(`^tHHMMSS`), so you can link to it from anywhere with `[[{note_name}#^{tid(ids[len(ids)//2])}]]`.\n\n{tx}\n")
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
# speaker labels become links to the attendees' people notes (see speakers.py)
full, linked, plain = link_speakers(head + body)
open(a.out, "w").write(full)
print("speaker links:", sorted(linked) or "none", "| left plain:", sorted(plain) or "none")

if a.raw_out:
    open(a.raw_out, "w").write("\n".join(f"[{hms(s)}] {l['sp']}: {l['t']}" for s, l in zip(ids, L)) + "\n")

missing = [r for r in re.findall(r"\[\[#\^(t\d{6})", head) if r not in {tid(s) for s in ids}]
left = re.findall(r"\{\{ref:[^}]*\}\}", head)
print("DONE", len(L), "lines;", "unresolved refs:", missing or "none", "| leftover placeholders:", left or "none")
