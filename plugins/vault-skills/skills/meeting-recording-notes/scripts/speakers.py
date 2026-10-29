"""Link transcript speaker labels to people notes.

Used by render_note.py when it writes a transcript, and runnable on its own to fix existing notes:

  python speakers.py "note.md" [more notes…] [--dry-run] [--vault DIR] [--people-folder People] [--me "Alex Example"]

--vault defaults to $VAULT_ROOT, else the current directory. --people-folder is the vault-relative folder
holding one note per person (folders.people in .vault-skills.yaml). --me is owner.name; omit it to link
only the attendees.

A label like `**Sam:**` becomes `**[[Sam Sample|Sam]]:**`. People come from the note's `attendees` (or `person`)
frontmatter (wiki-links), plus the vault owner (`--me`), who is always linked. A label matches an attendee by full
name, first name or an `aliases` entry on the person note, with accents ignored. A label that matches two
attendees, or none (Unidentified, Guest 1, Person 2…), stays plain. Already-linked labels are skipped,
so reruns change nothing.
"""
import glob, os, re, sys, unicodedata

VAULT = os.environ.get("VAULT_ROOT") or os.getcwd()
PEOPLE = "People"
ME = ""

def configure(vault=None, people=None, me=None):
    global VAULT, PEOPLE, ME
    if vault: VAULT = vault
    if people: PEOPLE = people
    if me is not None: ME = me

def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)).casefold().strip()

def _aliases(name):
    hits = glob.glob(f"{VAULT}/{PEOPLE}/**/{glob.escape(name)}.md", recursive=True)
    if not hits: return []
    fm = re.match(r"---\n(.*?)\n---", open(hits[0], encoding="utf-8").read(), re.S)
    if not fm: return []
    m = re.search(r"^aliases:\s*\n((?:\s+-.*\n?)+)", fm.group(1) + "\n", re.M)
    return [a.strip().strip("\"'") for a in re.findall(r"^\s+-\s*(.+)$", m.group(1), re.M)] if m else []

def speaker_map(text):
    """label (normalized) -> wiki-link target, for the attendees of a note's frontmatter."""
    fm = re.match(r"---\n(.*?)\n---", text, re.S)
    targets = [ME] if ME else []
    if fm:
        block = re.search(r"^attendees:\s*\n((?:[ \t]+-.*\n?)+)", fm.group(1) + "\n", re.M)
        person = re.search(r"^person:.*$", fm.group(1), re.M)  # 1:1 and call notes use `person:` instead
        for t in re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", (block.group(1) if block else "") + (person.group(0) if person else "")):
            t = t.strip().split("/")[-1]
            if t not in targets: targets.append(t)
    keys = {}
    for t in targets:
        for k in {norm(t), norm(t.split()[0]), *(norm(a) for a in _aliases(t))}:
            keys.setdefault(k, set()).add(t)
    return {k: next(iter(v)) for k, v in keys.items() if len(v) == 1}

LINE = re.compile(r"^(- `[\d:]+` \*\*)([^\[\]*]+?):(\*\* )", re.M)

def link_speakers(text):
    m = speaker_map(text)
    head, sep, tx = text.partition("\n## :TwStudioMicrophone: Transcript")
    for alt in ("\n## 🎙️ Transcript", "\n## Transcript"):
        if not sep: head, sep, tx = text.partition(alt)
    if not sep: return text, set(), set()
    done, left = set(), set()
    def sub(x):
        label = x[2]; t = m.get(norm(label))
        if not t: left.add(label); return x[0]
        done.add(label)
        link = f"[[{t}]]" if t == label else f"[[{t}|{label}]]"
        return f"{x[1]}{link}:{x[3]}"
    return head + sep + LINE.sub(sub, tx), done, left

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("notes", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--vault")
    ap.add_argument("--people-folder")
    ap.add_argument("--me")
    a = ap.parse_args()
    configure(a.vault, a.people_folder, a.me)
    for p in a.notes:
        s = open(p, encoding="utf-8").read()
        new, done, left = link_speakers(s)
        print(f"{'would change' if new != s else 'ok'}: {os.path.basename(p)} | linked {sorted(done)} | plain {sorted(left)}")
        if new != s and not a.dry_run: open(p, "w", encoding="utf-8").write(new)
