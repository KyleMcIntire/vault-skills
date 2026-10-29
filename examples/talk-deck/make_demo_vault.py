#!/usr/bin/env python3
"""Build a lived-in, entirely fictional Obsidian demo vault for screen recordings.

Usage:
    python3 examples/talk-deck/make_demo_vault.py <out-dir> [--today 2026-10-29] [--force]

It copies vault-template/ (found relative to this script) into <out-dir>, then adds about four
months of invented records: daily notes with habits and tasks, task notes with dated subtasks,
standups and project meetings, people, projects with changelogs, news digests, wiki notes,
preference profiles, automation tracking notes, and extra hubs (places, recipes, trips, vehicles,
events, documents, games, media). It also writes a minimal .obsidian/ config. It does not
install plugins or themes.

Everything is fictional: the company is Acme, people are invented, tickets are ABC-1xx and
links point at .invalid or example.com hosts. Output is deterministic for a given --today
(random.Random(2026), sorted writes), and each note's modified time is set to its own date so
the "edited per day" charts fill in.

Standard library only; no network.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
TEMPLATE = REPO / "vault-template"
BANNER_SRC = HERE / "media" / "banners"
SNIPPET = REPO / "docs" / "assets" / "snippets" / "home-dashboard.css"
PHILOSOPHY = REPO / "docs" / "philosophy.md"

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
HUB_BANNERS = ["places", "recipes", "trips", "vehicles", "game-hub", "media-hub", "scratch",
               "vault-automations", "meeting-recording-notes"]
DAY_BANNERS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

R = random.Random(2026)


# --------------------------------------------------------------------------- helpers

class Q(str):
    """A string that is always written quoted in YAML."""


def needs_quote(s: str) -> bool:
    return (
        not s
        or s[0] in "[]{}#&*!|>'\"%@`,?:-<=~"
        or ": " in s
        or " #" in s
        or s.endswith(":")
        or s.strip() != s
        or re.fullmatch(r"[\d.:+-]+", s) is not None
        or s.lower() in {"true", "false", "yes", "no", "null", "on", "off"}
    )


def yval(v) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dt.date):
        return v.isoformat()
    s = str(v)
    if isinstance(v, Q) or needs_quote(s):
        return json.dumps(s, ensure_ascii=False)
    return s


def frontmatter(pairs: list[tuple[str, object]]) -> str:
    out = ["---"]
    for key, value in pairs:
        if isinstance(value, (list, tuple)):
            if not value:
                out.append(f"{key}: []")
            else:
                out.append(f"{key}:")
                out.extend(f"  - {yval(item)}" for item in value)
        else:
            text = yval(value)
            out.append(f"{key}: {text}" if text else f"{key}:")
    out.append("---")
    return "\n".join(out) + "\n"


def iso(d: dt.date) -> str:
    return d.isoformat()


def dow(d: dt.date) -> str:
    return DAYS[d.weekday()]


def link(name: str) -> str:
    return f"[[{name}]]"


def qlink(name: str) -> Q:
    return Q(f"[[{name}]]")


def banner(path: str, height: int = 200) -> list[tuple[str, object]]:
    return [("banner", Q(path)), ("banner-height", height), ("banner-y", 50)]


class Vault:
    """Collects files, then writes them in sorted order with their modified times."""

    def __init__(self, root: Path, today: dt.date):
        self.root = root
        self.today = today
        self.files: dict[str, tuple[str, dt.date]] = {}

    # Obsidian's property editor rewrites `key: "plain value"` to `key: plain value` on first open, which would reset
    # every note's modified time (and the "edited per day" charts). Write those values unquoted to begin with.
    _QUOTED = re.compile(r'^((?:banner|date|title|meeting type): )"([A-Za-z0-9][A-Za-z0-9 ._/()&\'-]*)"$', re.M)

    def add(self, rel: str, text: str, when: dt.date) -> None:
        if rel.endswith(".md") and text.startswith("---\n"):
            end = text.find("\n---", 4)
            if end > 0:
                text = self._QUOTED.sub(r"\1\2", text[:end]) + text[end:]
        self.files[rel] = (text if text.endswith("\n") else text + "\n", when)

    def exists(self, rel: str) -> bool:
        return rel in self.files or (self.root / rel).exists()

    def write(self) -> None:
        for rel in sorted(self.files):
            text, when = self.files[rel]
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            stamp = dt.datetime.combine(min(when, self.today), dt.time(17, 30)).timestamp()
            os.utime(path, (stamp, stamp))


# --------------------------------------------------------------------------- people

ME = "Alex Example"
# name, group, relationship, role (team), location, title, timezone, pronouns, birthdate
PEOPLE = [
    ("Riley Rivera", "Work", "manager", "Platform Team", "Central US", "Engineering manager", "America/Chicago", "she/her", "1984-02-17"),
    ("Drew Patel", "Work", "coworker", "Platform Team", "Central US", "Site reliability engineer", "America/Chicago", "he/him", "1991-07-09"),
    ("Morgan Lee", "Work", "coworker", "Billing Team", "Eastern US", "Backend engineer", "America/New_York", "he/him", "1989-03-22"),
    ("Taylor Quinn", "Work", "coworker", "Billing Team", "Eastern US", "Product manager", "America/New_York", "she/her", "1987-12-01"),
    ("Casey Brooks", "Work", "coworker", "Mobile Team", "Western US", "Mobile engineer", "America/Los_Angeles", "they/them", "1993-05-30"),
    ("Quinn Murphy", "Work", "coworker", "Mobile Team", "Western Europe", "QA lead", "Europe/Dublin", "he/him", "1990-09-14"),
    ("Jamie Fox", "Work", "coworker", "Docs Team", "Central US", "Technical writer", "America/Chicago", "she/her", "1992-01-25"),
    ("Avery Kim", "Work", "coworker", "Design Team", "Western US", "Product designer", "America/Los_Angeles", "she/her", "1994-08-11"),
    ("Jo Placeholder", "Friends", "friend", "", "Springfield", "Climbing partner", "America/Chicago", "she/her", "1990-11-14"),
    ("Robin Hart", "Friends", "friend", "", "Shelbyville", "Board game night host", "America/Chicago", "he/him", "1988-06-02"),
    ("Charlie Demo", "Friends", "friend", "", "Springfield", "Neighbor and running buddy", "America/Chicago", "they/them", "1991-04-19"),
    ("Pat Sample", "Family", "family", "", "Capital City", "Sibling", "America/Denver", "he/him", "1986-10-08"),
]
WORK_PEOPLE = [p[0] for p in PEOPLE if p[1] == "Work"] + ["Sam Sample"]
TEAM_OF = {p[0]: p[3] for p in PEOPLE}
TEAM_OF["Sam Sample"] = "Design Team"

# --------------------------------------------------------------------------- projects and tickets

# name: (status, category, start offset, end offset, reviewed offset, summary, next step, people)
PROJECTS = {
    "Billing Revamp": ("🟢 Active", "Work", -143, 0, -3,
                       "Replace the hand-rolled invoice job with a tested billing service.",
                       "Finish proration and start the legacy API deprecation notice.",
                       ["Morgan Lee", "Taylor Quinn", "Drew Patel"]),
    "Mobile App Beta": ("🧪 Planning", "Work", -45, 0, -41,
                        "Ship a closed beta of the Acme mobile app to fifty friendly customers.",
                        "Agree the beta channel and recruit the first ten testers.",
                        ["Casey Brooks", "Quinn Murphy", "Avery Kim"]),
    "Docs Portal": ("⏸️ Paused", "Work", -178, -64, -63,
                    "One searchable home for product docs and the API reference.",
                    "Resume after the billing launch; pick up versioned docs first.",
                    ["Jamie Fox", "Sam Sample"]),
    "Onboarding Survey": ("✅ Done", "Work", -171, -97, -96,
                          "Ask new hires what their first month was like and act on it.",
                          "",
                          ["Riley Rivera", "Jamie Fox"]),
    "Home Office Upgrade": ("💡 Idea", "Home", -30, -30, -30,
                            "A quieter, brighter desk setup for long focus days.",
                            "Measure the desk and price a monitor arm.",
                            []),
}

TICKET_PLAN = {
    "Website Refresh": [
        ("Build the pricing page", "In Progress"), ("Set up preview deploys", "Done"),
        ("Write the 404 page", "To Do"), ("Migrate blog redirects", "To Do"),
        ("Add an accessibility audit", "In Progress"),
    ],
    "Billing Revamp": [
        ("Map the current invoice flow", "Done"), ("Design the new invoice schema", "Done"),
        ("Move tax rates into config", "Done"), ("Export invoices as CSV", "Done"),
        ("Retry failed card payments", "Done"), ("Write the billing runbook", "Done"),
        ("Backfill historic invoices", "Done"), ("Add a billing audit log", "Done"),
        ("Add proration for mid-cycle upgrades", "In Progress"),
        ("Alert on failed payment spikes", "In Progress"),
        ("Show upcoming charges in settings", "In Progress"),
        ("Deprecate the legacy billing API", "To Do"), ("Support annual plans", "To Do"),
        ("Load-test the invoice job", "Won't Do"), ("Handle currency rounding in the old job", "Won't Do"),
    ],
    "Mobile App Beta": [
        ("Pick a beta distribution channel", "Done"), ("Add crash reporting", "Done"),
        ("Write the beta test plan", "In Progress"), ("Design the onboarding screens", "In Progress"),
        ("Set up feature flags for beta", "To Do"), ("Recruit beta testers", "To Do"),
        ("Draft beta release notes", "To Do"), ("Add an in-app feedback form", "To Do"),
    ],
    "Docs Portal": [
        ("Choose a docs framework", "Done"), ("Import the API reference", "Done"),
        ("Set up docs search", "Done"), ("Write the getting-started guide", "Done"),
        ("Theme the docs to match the site", "Done"), ("Add versioned docs", "To Do"),
        ("Migrate the old FAQ", "Won't Do"), ("Add a docs feedback widget", "Won't Do"),
    ],
    "Onboarding Survey": [
        ("Draft survey questions", "Done"), ("Choose a survey tool", "Done"),
        ("Send the survey to new hires", "Done"), ("Analyze survey results", "Done"),
        ("Present findings to leadership", "Done"), ("Translate the survey", "Won't Do"),
    ],
}
PROJECT_WINDOWS = {"Website Refresh": (-9, 0)}

STEP_POOL = [
    "Write a short design note", "Open the pull request", "Address review comments", "Add unit tests",
    "Update the runbook", "Demo it at standup", "Check the staging deploy", "Ask {p} for a review",
    "Pair with {p} on the edge cases", "Write the release note", "Clean up the feature flag",
    "Confirm the numbers with {p}", "Add monitoring and an alert", "Record a short walkthrough",
    "Split the change into two PRs", "Update the project changelog",
]
REPOS = {"Website Refresh": "web", "Billing Revamp": "billing", "Mobile App Beta": "mobile",
         "Docs Portal": "docs", "Onboarding Survey": "people-ops"}


class Ticket:
    def __init__(self, title, project, status):
        self.title, self.project, self.status = title, project, status
        self.key = ""
        self.created = None
        self.resolved = None
        self.steps: list[dict] = []  # text, done (date|None), due (date|None), cancelled (date|None)
        self.points = 0
        self.reporter = ""
        self.helper = ""

    @property
    def name(self) -> str:
        return f"{self.key} {self.title}"

    @property
    def folder(self) -> str:
        return f"Tasks/{self.status}"

    def last_activity(self) -> dt.date:
        dates = [self.created] + [s["done"] for s in self.steps if s["done"]] + \
                [s["cancelled"] for s in self.steps if s["cancelled"]]
        if self.resolved:
            dates.append(self.resolved)
        return max(dates)

    def active_on(self, d: dt.date) -> bool:
        end = self.resolved or (TODAY if self.status == "In Progress" else None)
        return end is not None and self.status in ("Done", "In Progress") and self.created <= d <= end


def rand_date(a: dt.date, b: dt.date) -> dt.date:
    if b <= a:
        return a
    return a + dt.timedelta(days=R.randint(0, (b - a).days))


def workday(d: dt.date) -> dt.date:
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def build_tickets() -> list[Ticket]:
    tickets: list[Ticket] = []
    for project, plan in TICKET_PLAN.items():
        if project in PROJECT_WINDOWS:
            s_off, e_off = PROJECT_WINDOWS[project]
            people = ["Sam Sample", "Avery Kim"]
        else:
            _, _, s_off, e_off, _, _, _, people = PROJECTS[project]
        ps, pe = TODAY + dt.timedelta(days=s_off), TODAY + dt.timedelta(days=e_off)
        # Done tickets start in plan order, so the first planned step is also the first shipped.
        done_starts = sorted(workday(rand_date(ps, max(ps, pe - dt.timedelta(days=8))))
                             for _, st in plan if st == "Done")
        for title, status in plan:
            t = Ticket(title, project, status)
            t.points = R.choice([1, 2, 2, 3, 3, 5, 8])
            t.reporter = R.choice(people + [ME, "Riley Rivera"])
            t.helper = R.choice(people)
            n = R.randint(3, 5)
            texts = R.sample(STEP_POOL, n)
            texts = [x.format(p=link(t.helper)) for x in texts]
            if status == "Done":
                t.created = min(done_starts.pop(0), pe)
                t.resolved = min(pe, TODAY, t.created + dt.timedelta(days=R.randint(4, 21)))
                dates = sorted(rand_date(t.created, t.resolved) for _ in range(n - 1)) + [t.resolved]
                t.steps = [{"text": x, "done": d, "due": None, "cancelled": None} for x, d in zip(texts, dates)]
            elif status == "In Progress":
                t.created = workday(rand_date(max(ps, TODAY - dt.timedelta(days=40)), TODAY - dt.timedelta(days=4)))
                k = R.randint(1, n - 1)
                dates = sorted(rand_date(t.created, TODAY) for _ in range(k))
                t.steps = [{"text": x, "done": d, "due": None, "cancelled": None} for x, d in zip(texts[:k], dates)]
                for x in texts[k:]:
                    t.steps.append({"text": x, "done": None,
                                    "due": TODAY + dt.timedelta(days=R.choice([-2, 1, 2, 3, 5, 6, 8, 10, 13])),
                                    "cancelled": None})
            elif status == "To Do":
                hi = min(pe, TODAY - dt.timedelta(days=1))
                t.created = workday(rand_date(max(ps, hi - dt.timedelta(days=30)), hi))
                if t.created > TODAY:
                    t.created = TODAY
                t.steps = [{"text": x, "done": None, "due": None, "cancelled": None} for x in texts[:R.randint(2, 3)]]
                if pe >= TODAY and R.random() < 0.7:
                    t.steps[0]["due"] = TODAY + dt.timedelta(days=R.randint(3, 20))
            else:  # Won't Do
                t.created = workday(rand_date(ps, max(ps, pe - dt.timedelta(days=12))))
                t.resolved = min(TODAY, t.created + dt.timedelta(days=R.randint(5, 15)))
                first = rand_date(t.created, t.resolved)
                t.steps = [{"text": texts[0], "done": first, "due": None, "cancelled": None}]
                t.steps += [{"text": x, "done": None, "due": None, "cancelled": t.resolved} for x in texts[1:3]]
            tickets.append(t)
    tickets.sort(key=lambda t: (t.created, t.project, t.title))
    for i, t in enumerate(tickets):
        t.key = f"ABC-{103 + i}"
    return tickets


def step_line(s: dict, extra: str = "") -> str:
    if s["cancelled"]:
        return f"- [-] {s['text']}{extra} ❌ {iso(s['cancelled'])}"
    if s["done"]:
        return f"- [x] {s['text']}{extra} ✅ {iso(s['done'])}"
    return f"- [ ] {s['text']}{extra}" + (f" 📅 {iso(s['due'])}" if s["due"] else "")


def write_ticket(v: Vault, t: Ticket) -> None:
    open_steps = [s for s in t.steps if not s["done"] and not s["cancelled"]]
    next_step = "" if t.status in ("Done", "Won't Do") else (open_steps[0]["text"].replace("[[", "").replace("]]", "") + "." if open_steps else "")
    pr = f"https://git.acme.invalid/acme/{REPOS[t.project]}/pull/{R.randint(120, 980)}"
    fm = frontmatter([
        ("status", t.status), ("url", f"https://acme.invalid/browse/{t.key}"), ("reporter", t.reporter),
        ("type", "task"), ("task type", "issue"), ("tags", ["Task"]), ("project", t.project),
        ("story points", t.points), ("PRs", pr if t.status != "To Do" else ""), ("related issues", ""),
        ("links", ""), ("slack threads", ""), ("next step", next_step), ("created", t.created),
        ("resolved", t.resolved or ""), ("dateModified", t.last_activity()),
        *banner("Media/Banners/Note Types/task-note.gif"),
    ])
    desc = {
        "Done": f"{t.title} for {link(t.project)}. Shipped and verified; notes below.",
        "In Progress": f"{t.title} as part of {link(t.project)}. Working with {link(t.helper)}.",
        "To Do": f"{t.title} for {link(t.project)}. Not started yet.",
        "Won't Do": f"{t.title} for {link(t.project)}. Dropped: the work it supported changed direction.",
    }[t.status]
    # Work log: newest first, one section per date with the steps done that day.
    by_day: dict[dt.date, list[str]] = {}
    for s in t.steps:
        when = s["done"] or s["cancelled"]
        if when:
            by_day.setdefault(when, []).append(step_line(s))
    newest = max(by_day) if by_day else t.created
    if open_steps:
        by_day.setdefault(newest, [])
        by_day[newest] += [step_line(s) for s in open_steps]
    by_day.setdefault(t.created, []).insert(0, f"- Created by {link(t.reporter) if t.reporter != ME else 'me'}; {t.points} points.")
    notes = {
        "Done": "- Closed: everything below is shipped.",
        "Won't Do": f"- Closed as won't do after a chat with {link(t.helper)}.",
    }
    if t.resolved and t.status in notes:
        by_day.setdefault(t.resolved, []).insert(0, notes[t.status])
    log = []
    for d in sorted(by_day, reverse=True):
        log.append(f"### #{iso(d)}\n\n" + "\n".join(by_day[d]))
    body = f"""# {t.name}

## Description

{desc}

---

## Open steps

```tasks
not done
path includes {{{{query.file.path}}}}
short mode
hide tags
```

## Mentions

![[Task Mentions.base]]

---

## Work log

{chr(10).join(chr(10).join([x, '']) for x in log).rstrip()}

---
"""
    v.add(f"{t.folder}/{t.name}.md", fm + "\n" + body, t.last_activity())


# --------------------------------------------------------------------------- daily notes

MOODS = ["✅ Good", "👍 Normal", "🥱 Tired", "😬 Anxious", "😞 Rough"]
HABITS = [("Walk 30 minutes", 0.72, 0.85), ("Read 20 pages", 0.55, 0.7), ("Stretch for ten minutes", 0.5, 0.45),
          ("No screens after 22:00", 0.4, 0.5), ("Drink two litres of water", 0.8, 0.75)]
WORK_ITEMS = [
    "Review {p}'s pull request for {t}", "Reply to {p} about {t}", "Update the status of {t}",
    "Prepare notes for the {proj} sync", "Answer {p}'s question in the team channel",
    "Book a room for the {proj} demo", "Read {p}'s design note for {t}", "Follow up with {p} on {t}",
]
HOME_ITEMS = [
    "Pay the water bill", "Book a haircut", "Order a birthday gift for [[Jo Placeholder]]", "Call [[Pat Sample]]",
    "Pick up groceries", "Return the library books", "Water the plants", "Plan meals for the week",
    "Renew the parking permit", "Clean out the fridge", "Take the recycling out", "Text [[Charlie Demo]] about the long run",
    "Fix the squeaky door hinge", "Back up the laptop", "Sort the receipts folder",
]
JOURNAL = {
    "✅ Good": ["Good focus day; got through the hard part before lunch.", "Long walk at sunset, felt properly rested.",
                "Small win: the thing I was dreading took twenty minutes.", "Laughed a lot at lunch with the team."],
    "👍 Normal": ["Steady day, nothing dramatic.", "Mostly reviews and small fixes.", "Ordinary day; cooked something new.",
                  "Meetings in the morning, heads-down after."],
    "🥱 Tired": ["Slept badly; kept the afternoon light.", "Too many context switches today.",
                 "Coffee did not help. Early night."],
    "😬 Anxious": ["Deadline feels close; wrote down the next three steps to calm it down.",
                   "Worried about the release; asked for help early, which helped."],
    "😞 Rough": ["Rough one. Rescheduled what could wait and went for a walk."],
}
WEEKEND_JOURNAL = ["Climbing with [[Jo Placeholder]] in the morning.", "Board games at [[Robin Hart]]'s place.",
                   "Lazy Sunday: book, tea, rain.", "Long run with [[Charlie Demo]] by the river.",
                   "Tidied the garage and found the old bike.", "Video call with [[Pat Sample]]."]
SUMMARIES = ["Reviews and small fixes.", "Focused day on {proj}.", "Mostly meetings.", "Quiet day, good progress.",
             "Errands and admin.", "Planning and catching up."]


def daily_template() -> str:
    text = (TEMPLATE / "Templates" / "Daily Note Template.md").read_text(encoding="utf-8")
    body = text.split("\n---\n", 1)[1]
    body = re.sub(r"<!--.*?-->\n*", "", body, count=1, flags=re.S)
    return body.lstrip("\n")


def build_daily(v: Vault, tickets: list[Ticket], standup_days: set[dt.date], start: dt.date) -> list[str]:
    tmpl = daily_template()
    days = [start + dt.timedelta(days=i) for i in range((TODAY - start).days + 1)]
    names = []
    for d in days:
        weekend = d.weekday() >= 5
        mood = R.choices(MOODS, [55, 30, 10, 3, 2] if weekend else [30, 35, 20, 10, 5])[0]
        items = []
        active = [t for t in tickets if t.active_on(d)]
        recent = d >= TODAY - dt.timedelta(days=6)
        n_work = 0 if weekend else R.randint(1, 3)
        n_home = R.randint(1, 2) if weekend else R.choice([0, 0, 1])
        picks = [("work", x) for x in R.sample(WORK_ITEMS, n_work)] + [("home", x) for x in R.sample(HOME_ITEMS, n_home)]
        for kind, text in picks:
            if kind == "work":
                tk = R.choice(active) if active else None
                text = text.format(p=link(R.choice(WORK_PEOPLE)), t=link(tk.name) if tk else "the release",
                                   proj=tk.project if tk else "team")
            tag = " #work" if kind == "work" else ""
            if recent and R.random() < 0.4:
                due = d + dt.timedelta(days=R.randint(1, 8))
                items.append(f"- [ ] {text} 📅 {iso(due)}{tag}")
            else:
                done = min(TODAY, d + dt.timedelta(days=R.choice([0, 0, 0, 0, 0, 1, 2, 3])))
                due = f" 📅 {iso(d + dt.timedelta(days=R.randint(0, 2)))}" if R.random() < 0.5 else ""
                items.append(f"- [x] {text}{due} ✅ {iso(done)}{tag}")
        shipped = [t for t in tickets if t.resolved == d and t.status == "Done"]
        for t in shipped:
            items.append(f"- [x] Close {link(t.name)} ✅ {iso(d)} #work")
        habits = []
        for name, wd, we in HABITS:
            rate = we if weekend else wd
            rate += {"✅ Good": 0.1, "😞 Rough": -0.25, "🥱 Tired": -0.1}.get(mood, 0)
            prefix = f"{name} 🔁 every day 📅 {iso(d)}"
            if d == TODAY:
                habits.append(f"- [x] {prefix} ✅ {iso(d)} #habit" if R.random() < 0.35 else f"- [ ] {prefix} #habit")
            elif R.random() < rate:
                habits.append(f"- [x] {prefix} ✅ {iso(d)} #habit")
            else:
                habits.append(f"- [-] {prefix} ❌ {iso(d)} #habit")
        journal = []
        if R.random() < 0.75:
            journal.append(R.choice(WEEKEND_JOURNAL if weekend and R.random() < 0.6 else JOURNAL[mood]))
        if d in standup_days:
            journal.append(f"Standup: {link(iso(d) + ' Team Standup')}.")
        for t in shipped:
            journal.append(f"Shipped {link(t.name)} for {link(t.project)}.")
        if shipped:
            summary = f"Shipped {shipped[0].title.lower()}."
        elif weekend:
            summary = R.choice(["Rest day.", "Errands and a long walk.", "Time with friends.", "Slow morning, tidy afternoon."])
        else:
            summary = R.choice(SUMMARIES).format(proj=(active[0].project if active else "the team"))
        prev = d - dt.timedelta(days=1)
        nxt = d + dt.timedelta(days=1)
        day_banner = f"Media/Banners/Days/{dow(d)}.gif" if not weekend else "Media/Banners/daily-notes-hub.gif"
        fm = frontmatter([
            ("date", Q(iso(d))), ("prev", qlink(iso(prev)) if prev >= start else ""),
            ("next", qlink(iso(nxt)) if nxt <= TODAY else ""), ("type", "Daily Note"), ("mood", mood),
            ("summary", summary), ("tags", ["Journal"]), *banner(day_banner),
        ])
        body = tmpl.replace("{{date:dddd}}", dow(d)).replace("{{date}}", iso(d))
        body = body.replace("\n\n## Task Inbox\n", "\n\n[[Daily Notes/Daily Notes Hub|Daily Notes Hub]]\n\n## Task Inbox\n\n"
                            + "\n".join(items) + "\n", 1)
        journal_md = "\n".join(f"- {j}" for j in journal) if journal else "-"
        body = body.replace("\n## Related\n", "\n" + "\n".join(habits) + "\n\n## Journal\n\n" + journal_md + "\n\n## Related\n", 1)
        v.add(f"Daily Notes/{iso(d)}.md", fm + "\n" + body, d)
        names.append(iso(d))
    return names


# --------------------------------------------------------------------------- meetings

def meeting_note(v: Vault, *, folder, title, d, start, duration, attendees, kind, project, status, summary,
                 topics, tldr, actions, waiting, decisions, notes, file_title=None, tags_extra=()):
    file_title = file_title or title
    fm = frontmatter([
        ("creation date", d), ("date", d), ("start", Q(start)), ("duration", duration), ("title", title),
        ("attendees", [qlink(a) for a in attendees]), ("type", "meeting"), ("meeting type", kind),
        ("project", project), ("status", status), ("summary", summary), ("topics", topics),
        ("tags", ["Meeting", *tags_extra]),
        *banner("Media/Banners/standup.gif" if kind == "standup" else "Media/Banners/Note Types/meeting-note.gif"),
    ])
    rows = "\n".join(f"| {link(o)} | {w} | {iso(due)} |" for o, w, due in waiting) or "|  |  |  |"
    body = f"""# {title}

[[Meetings/Meeting Hub|Meeting Hub]]

> [!abstract] TL;DR
> {tldr}

## My action items

{chr(10).join(actions) if actions else '-'}

## Waiting on others

Only what someone owes you or what blocks your work. Set `status: ⌛ Waiting on others` while a row is open.

| Owner | What you're waiting on | Due |
| --- | --- | --- |
{rows}

## Decisions

{chr(10).join('- ' + x for x in decisions)}

## Notes

{chr(10).join('- ' + x for x in notes)}
"""
    v.add(f"{folder}/{file_title}.md", fm + "\n" + body, d)
    return file_title


def action(text, d, done_after=None, due_after=None):
    if done_after is not None and d + dt.timedelta(days=done_after) <= TODAY:
        return f"- [x] {text} ✅ {iso(d + dt.timedelta(days=done_after))}"
    due = d + dt.timedelta(days=due_after if due_after is not None else 5)
    return f"- [ ] {text} 📅 {iso(due)}"


def build_meetings(v: Vault, tickets: list[Ticket]) -> tuple[set[dt.date], list[tuple[str, dt.date, str, list[str]]]]:
    log: list[tuple[str, dt.date, str, list[str]]] = []  # (note, date, project, attendees)
    standups: set[dt.date] = set()
    for off in range(-27, 1):
        d = TODAY + dt.timedelta(days=off)
        if d.weekday() >= 4:
            continue
        rel = f"Meetings/Recurring/Standup/{iso(d)} Team Standup.md"
        standups.add(d)
        if v.exists(rel):
            continue
        prev = d - dt.timedelta(days=3 if d.weekday() == 0 else 1)
        done = [(t, s) for t in tickets for s in t.steps if s["done"] and prev <= s["done"] < d]
        active = [t for t in tickets if t.active_on(d)]
        yesterday = [f"{s['text']} ({link(t.name)})" for t, s in done[:2]] or ["Reviews and support questions."]
        today = [f"Continue {link(t.name)}." for t in active[:2]] or ["Pick up the next ticket from the board."]
        blockers = ["None."]
        if R.random() < 0.25:
            blockers = [f"Waiting on {link(R.choice(['Taylor Quinn', 'Morgan Lee', 'Avery Kim']))} for sign-off."]
        attendees = [ME, "Riley Rivera", "Drew Patel"] + R.sample(["Morgan Lee", "Sam Sample", "Casey Brooks", "Avery Kim"], 2)
        project = active[0].project if active else "Billing Revamp"
        did = re.sub(r"\[\[|\]\]", "", done[0][1]["text"]) if done else "Reviews and support"
        summary = f"{did}; next up: {active[0].title.lower() if active else 'the board'}."
        fm = frontmatter([
            ("creation date", d), ("date", d), ("start", Q("09:30")), ("duration", R.choice([15, 15, 15, 20, 25])),
            ("title", "Team Standup"), ("type", "meeting"), ("meeting type", "standup"), ("project", project),
            ("status", "✅ Closed"), ("summary", summary),
            ("attendees", [qlink(a) for a in attendees]), ("tags", ["Meeting"]), *banner("Media/Banners/standup.gif"),
        ])
        body = "# Team Standup\n\n[[Meetings/Meeting Hub|Meeting Hub]]\n\n### Yesterday\n\n" + \
               "\n".join(f"- {x}" for x in yesterday) + "\n\n### Today\n\n" + "\n".join(f"- {x}" for x in today) + \
               "\n\n### Blockers\n\n" + "\n".join(f"- {x}" for x in blockers) + "\n"
        v.add(rel, fm + "\n" + body, d)
        log.append((f"{iso(d)} Team Standup", d, project, attendees))

    def day(off):
        return workday(TODAY + dt.timedelta(days=off)) if TODAY + dt.timedelta(days=off) < TODAY else TODAY + dt.timedelta(days=off)

    specs = [
        dict(off=-104, name="Billing Revamp Kickoff", kind="planning", project="Billing Revamp", dur=60, start="14:00",
             att=[ME, "Morgan Lee", "Taylor Quinn", "Riley Rivera"], status="✅ Closed",
             summary="Agreed the scope and order of work for the billing rewrite.",
             tldr="Rewrite the invoice job as a service, behind a flag. [[Taylor Quinn]] owns scope, [[Morgan Lee]] the schema.",
             actions=[("Write up the current invoice flow", 3, None), ("Share the plan with [[Riley Rivera]]", 1, None)],
             waiting=[], decisions=["Ship behind a flag; no big-bang cutover.", "Tax rates move into config first."],
             notes=["Project note: [[Billing Revamp]].", "Biggest risk is historic invoices with odd rounding."]),
        dict(off=-97, name="Onboarding Survey Retro", kind="review", project="Onboarding Survey", dur=45, start="11:00",
             att=[ME, "Riley Rivera", "Jamie Fox"], status="✅ Closed",
             summary="Closed the survey project and picked three follow-ups.",
             tldr="Response rate was good; the top ask is a clearer first-week checklist.",
             actions=[("Send the summary to the team", 1, None)], waiting=[],
             decisions=["Close [[Onboarding Survey]] as done.", "Repeat the survey in six months."],
             notes=["[[Jamie Fox]] will fold the checklist into the docs."]),
        dict(off=-76, name="Alex and Riley 1-1", kind="1-1", project="", dur=30, start="15:00", folder="Meetings/Recurring/1-1",
             att=[ME, "Riley Rivera"], status="✅ Closed", summary="Career goals and the billing timeline.",
             tldr="Talked about leading the billing launch and taking a conference talk.",
             actions=[("Draft a talk abstract", 9, None)], waiting=[], decisions=["Aim to lead the billing launch."],
             notes=["Next 1-1 in four weeks."]),
        dict(off=-64, name="Docs Portal Pause Review", kind="review", project="Docs Portal", dur=30, start="10:00",
             att=[ME, "Jamie Fox", "Sam Sample", "Riley Rivera"], status="✅ Closed",
             summary="Paused the docs portal until billing ships.",
             tldr="Search and the guide shipped; versioned docs wait until after the billing launch.",
             actions=[("Move open docs tickets to the backlog", 1, None)], waiting=[],
             decisions=["Pause [[Docs Portal]]; resume after billing.", "Drop the FAQ migration."],
             notes=["Versioned docs stay in To Do."]),
        dict(off=-48, name="Alex and Riley 1-1", kind="1-1", project="", dur=30, start="15:00", folder="Meetings/Recurring/1-1",
             att=[ME, "Riley Rivera"], status="✅ Closed", summary="Workload check and the mobile beta.",
             tldr="Mobile beta planning starts next month; keep billing as the priority.",
             actions=[("Block focus time on Tuesdays", 2, None)], waiting=[], decisions=["Billing first, beta second."],
             notes=["Talk abstract accepted for the internal meetup."]),
        dict(off=-41, name="Mobile App Beta Scoping", kind="planning", project="Mobile App Beta", dur=50, start="13:00",
             att=[ME, "Casey Brooks", "Quinn Murphy", "Avery Kim"], status="⌛ Waiting on others",
             summary="Scoped the closed beta; waiting on a tester list.",
             tldr="Fifty testers, two-week cycles, crash reporting before anything else.",
             actions=[("Write the beta test plan", None, 50)],
             waiting=[("Quinn Murphy", "List of candidate beta testers", 7), ("Avery Kim", "Onboarding screen sketches", 14)],
             decisions=["Closed beta only; no public store listing yet."],
             notes=["Project note: [[Mobile App Beta]]."]),
        dict(off=-33, name="Billing Sprint Review", kind="review", project="Billing Revamp", dur=45, start="14:00",
             att=[ME, "Morgan Lee", "Taylor Quinn", "Drew Patel"], status="✅ Closed",
             summary="Demoed CSV export and card retries.",
             tldr="Retries cut failed payments in staging; CSV export is ready for finance.",
             actions=[("Write the billing runbook", 6, None), ("Ask finance to try the export", 2, None)], waiting=[],
             decisions=["Load-testing the old job is not worth it; drop it."], notes=["Demo recording in the team drive."]),
        dict(off=-20, name="Alex and Riley 1-1", kind="1-1", project="", dur=30, start="15:00", folder="Meetings/Recurring/1-1",
             att=[ME, "Riley Rivera"], status="✅ Closed", summary="Feedback on the runbook and launch date.",
             tldr="Runbook landed well; launch target is mid-November.",
             actions=[("Share the launch checklist", 4, None)], waiting=[], decisions=["Launch window: mid-November."],
             notes=["Ask about the offsite budget next time."]),
        dict(off=-12, name="Payment Alert Review", kind="ad-hoc", project="Billing Revamp", dur=25, start="16:00",
             att=[ME, "Drew Patel", "Morgan Lee"], status="⌛ Waiting on others",
             summary="Reviewed a noisy payment alert; waiting on a threshold change.",
             tldr="The failed-payment alert fired on a test card burst. Thresholds need a floor.",
             actions=[("Add a minimum-volume floor to the alert", None, 16)],
             waiting=[("Drew Patel", "Updated alert thresholds in staging", 5)],
             decisions=["Page only above twenty failures in ten minutes."], notes=["No customer impact."]),
        dict(off=-6, name="Beta Test Plan Review", kind="review", project="Mobile App Beta", dur=40, start="11:30",
             att=[ME, "Casey Brooks", "Quinn Murphy"], status="⌛ Waiting on others",
             summary="First pass at the beta test plan.",
             tldr="Plan covers install, sign-in and payments; offline mode is out of scope.",
             actions=[("Fold review comments into the plan", 2, None), ("Send the plan to [[Riley Rivera]]", None, 9)],
             waiting=[("Casey Brooks", "Crash-report dashboard link", 3)],
             decisions=["Offline mode is out of scope for the beta."], notes=["Next review in two weeks."]),
        dict(off=-2, name="Billing Launch Planning", kind="planning", project="Billing Revamp", dur=55, start="13:30",
             att=[ME, "Taylor Quinn", "Morgan Lee", "Riley Rivera", "Drew Patel"], status="✅ Closed",
             summary="Agreed the launch checklist and the deprecation notice.",
             tldr="Proration finishes first; the legacy API gets a ninety-day notice.",
             actions=[("Draft the deprecation notice", 1, None), ("Book the launch review", None, 6)], waiting=[],
             decisions=["Ninety-day notice for the legacy API.", "Launch behind the flag for 10% first."],
             notes=["Project note: [[Billing Revamp]]."]),
    ]
    for s in specs:
        d = day(s["off"])
        if d > TODAY:
            d = TODAY
        actions = [action(t, d, done_after=a, due_after=b) for t, a, b in s["actions"]]
        waiting = [(o, w, d + dt.timedelta(days=x)) for o, w, x in s["waiting"]]
        title = f"{iso(d)} {s['name']}"
        name = meeting_note(
            v, folder=s.get("folder", "Meetings"), title=title, d=d, start=s["start"], duration=s["dur"],
            attendees=s["att"], kind=s["kind"], project=s["project"], status=s["status"], summary=s["summary"],
            topics=[s["kind"], (s["project"] or "career").lower()], tldr=s["tldr"], actions=actions, waiting=waiting,
            decisions=s["decisions"], notes=s["notes"])
        log.append((name, d, s["project"], s["att"]))
    return standups, log


# --------------------------------------------------------------------------- people

def build_people(v: Vault, meetings_log) -> list[str]:
    names = []
    for name, group, rel, role, loc, title, tz, pronouns, birth in PEOPLE:
        slug = name.lower().replace(" ", ".")
        mine = sorted([(d, m) for m, d, _, att in meetings_log if name in att], reverse=True)[:3]
        log = [f"### #{iso(d)} - {dow(d)}\n\n- Met in {link(m)}." for d, m in mine]
        added = TODAY - dt.timedelta(days=150 if group == "Work" else 200)
        log.append(f"### #{iso(added)} - {dow(added)}\n\n- Added the note.")
        fm = frontmatter([
            ("creation date", added), ("name", name), ("relationship", rel), ("role", role), ("location", loc),
            ("birthdate", dt.date.fromisoformat(birth)), ("address", ""), ("phone", ""), ("email", f"{slug}@example.com"),
            ("tags", ["person"]), ("image", ""), *banner("Media/Banners/Note Types/person-note.gif"),
        ])
        team = f"[{role}](https://acme.invalid/teams/{role.split()[0].lower()})" if role else ""
        slack = f"[@{slug}](https://acme.invalid/slack/{slug})" if group == "Work" else ""
        overview = {
            "Work": f"{title} on the {role}. Good first call for anything about {(role or 'x').split()[0].lower()}.",
            "Friends": f"{title}. Lives in {loc}.",
            "Family": f"{title}. Lives in {loc}; call at least every couple of weeks.",
        }[group]
        body = f"""# {name}

[[People/People Hub|People Hub]]

```dataviewjs
await dv.view("Templates/Views/person-profile")
```

> [!abstract] Overview
> {overview}

## Together

> [!multi-column]
>
> > [!note]+ Meetings
> > ![[Meetings/Meetings.base#Linked to this note]]
>
> > [!todo]+ Open tasks
> >
> > ```tasks
> > not done
> > description includes [[{name}]]
> > sort by due
> > short mode
> > ```

## Log

Newest first. Dated moments worth remembering: what they said, plans, gifts, follow-ups.

{chr(10).join(chr(10).join([x, '']) for x in log).rstrip()}

## Notes

- **Role:** {title}{' at Acme' if group == 'Work' else ''}
- **Team:** {team}
- **Slack:** {slack}
- **Timezone:** {tz}
- **Pronouns:** {pronouns}

## Mentioned in

```base
filters:
  and:
    - file.hasLink(this.file)
    - '!file.inFolder("Meetings")'
    - '!file.inFolder("Daily Notes")'
    - '!file.inFolder("Templates")'
views:
  - type: table
    name: Mentioned in
    order:
      - file.name
      - type
      - summary
    sort:
      - property: file.mtime
        direction: DESC
    limit: 10
```
"""
        v.add(f"People/{group}/{name}.md", fm + "\n" + body, mine[0][0] if mine else added)
        names.append(name)
    convos = [
        (-9, "Call with Pat Sample", "Pat Sample", "communication", "Planned the winter visit dates."),
        (-16, "Message from Jo Placeholder", "Jo Placeholder", "message", "Climbing gym moved its late session to Thursdays."),
        (-25, "Coffee with Robin Hart", "Robin Hart", "irl-chat", "Robin is hosting a game night next month."),
    ]
    for off, title, person, kind, summary in convos:
        d = TODAY + dt.timedelta(days=off)
        full = f"{iso(d)} {title}"
        fm = frontmatter([("creation date", d), ("date", d), ("title", full), ("type", kind), ("person", qlink(person)),
                          ("status", "✅ Done"), ("summary", summary), ("tags", ["communication"]),
                          *banner("Media/Banners/Note Types/communication-note.gif")])
        body = f"# {full}\n\n[[People/People Hub|People Hub]]\n\n## Communication\n\n- {summary}\n\n## Follow-up\n\n" \
               f"- [x] Add it to the calendar ✅ {iso(d)}\n\n## Sources\n\n-\n"
        v.add(f"People/Conversations/{full}.md", fm + "\n" + body, d)
    return names


# --------------------------------------------------------------------------- projects

def build_projects(v: Vault, tickets: list[Ticket], meetings_log) -> None:
    for name, (status, category, s_off, e_off, r_off, summary, next_step, people) in PROJECTS.items():
        start = TODAY + dt.timedelta(days=s_off)
        end = TODAY + dt.timedelta(days=e_off)
        mine = [t for t in tickets if t.project == name]
        tasks = []
        for t in sorted(mine, key=lambda t: t.created):
            if t.status == "Done":
                tasks.append(f"- [x] Ship {link(t.name)} ✅ {iso(t.resolved)}")
            elif t.status == "In Progress":
                tasks.append(f"- [ ] Finish {link(t.name)} 📅 {iso(TODAY + dt.timedelta(days=R.randint(-3, 12)))}")
            elif t.status == "To Do" and status == "🟢 Active":
                tasks.append(f"- [ ] Start {link(t.name)}")
        if status != "💡 Idea":
            d = start + dt.timedelta(days=13)
            while d <= min(end, TODAY):
                tasks.append(f"- [x] Post the fortnightly status update to [[Riley Rivera]] ✅ {iso(d)}")
                d += dt.timedelta(days=14)
        else:
            tasks += ["- [ ] Measure the desk", "- [ ] Price a monitor arm and a desk lamp"]
        changes: dict[dt.date, list[str]] = {start: ["Started the project."]}
        for t in mine:
            if t.status == "Done":
                changes.setdefault(t.resolved, []).append(f"Shipped {link(t.name)}.")
            if t.status == "Won't Do":
                changes.setdefault(t.resolved, []).append(f"Dropped {link(t.name)}.")
        for m, d, p, _ in meetings_log:
            if p == name and "Standup" not in m:
                changes.setdefault(d, []).append(f"Met: {link(m)}.")
        if status == "⏸️ Paused":
            changes.setdefault(end, []).append("Paused until the billing launch.")
        if status == "✅ Done":
            changes.setdefault(end, []).append("Marked done.")
        changelog = "\n\n".join(f"### #{iso(d)} - {dow(d)}\n\n" + "\n".join(f"- {x}" for x in changes[d])
                                for d in sorted(changes, reverse=True))
        team = ", ".join(link(p) for p in people) or "just me"
        fm = frontmatter([
            ("creation date", start), ("title", name), ("type", "project"), ("status", status), ("category", category),
            ("summary", summary), ("next step", next_step), ("started", start),
            ("reviewed", TODAY + dt.timedelta(days=r_off)), ("repo", f"https://git.acme.invalid/acme/{REPOS[name]}" if name in REPOS else ""),
            ("tags", ["type/project"]), ("aliases", []), *banner("Media/Banners/Note Types/project-note.gif"),
        ])
        body = f"""# {name}

[[Projects/Project Hub|Project Hub]]

> [!abstract] Overview
> {summary} Working with {team}.

## Goals

- {summary.split(' and ')[0].rstrip('.')}
- Keep the changelog current so anyone can catch up in two minutes

## How it works

- Tickets live in `Tasks/` with `project: {name}`; meetings set the same `project`.

## Next up

{chr(10).join(tasks)}

## Ideas

- Write a short retro when this wraps up

## Changelog

Newest first.

{changelog}

## Project files

![[Projects/Projects.base#Project files]]
"""
        last = max(d for d in changes if d <= TODAY)
        v.add(f"Projects/{name}/{name}.md", fm + "\n" + body, last)


AUTOMATIONS = [
    ("Daily News Digest", "get-news", "⚙️ Automation", "📰 Briefings", "🟢 Active", -150, -2, "Daily at 06:00",
     "A morning digest of releases and security news, ranked by what touches the versions the team pins, plus Springfield weather.",
     "Runs from a scheduler, reads the feeds in `.vault-skills.yaml`, compares releases with local pin files and writes `News/YYYY-MM-DD News.md`.",
     ["skills/get-news/SKILL.md", "skills/get-news/fetch_news.py", "skills/get-news/references/digest-layout.md"],
     "Fixture run against saved feeds; the last ten digests opened cleanly in Obsidian.",
     [("Add the local news section", 20), ("Cap the Skipped list at fifteen items", None)]),
    ("Work-on Briefings", "work-on", "🧰 Skill", "📰 Briefings", "🟢 Active", -120, -9, "On demand",
     "One command to pick up a ticket or project: task note, PRs, branches, chat and mail, then a short do-next list.",
     "Takes an ABC key or a project name, gathers context read-only and ends with a briefing; never writes outside the vault.",
     ["skills/work-on/SKILL.md", "skills/work-on/gather.py"],
     "Ran it on [[Billing Revamp]] and three tickets; briefings matched the task notes.",
     [("Show failing checks first in the PR section", 30), ("Mention stale branches older than 30 days", None)]),
    ("Meeting Recording Notes", "meeting-recording-notes", "🧰 Skill", "🎙️ Capture", "🟢 Active", -90, -12, "On demand",
     "A recording goes in; a speaker-labelled transcript and a finished meeting note come out.",
     "Transcribes locally, labels speakers from the invite, writes TL;DR, decisions, my action items and the waiting table.",
     ["skills/meeting-recording-notes/SKILL.md", "skills/meeting-recording-notes/scripts/transcribe.py",
      "skills/meeting-recording-notes/scripts/render_note.py"],
     "Checked against the fixture lines and two real-length recordings of team demos.",
     [("Split back-to-back meetings automatically", 25), ("Handle a second language in one recording", None)]),
    ("Animated Vault Banners", "pixel-banners", "🎨 Look and feel", "🎨 Look and feel", "✅ Done", -170, -58, "",
     "Animated pixel-art banners for every hub and note type, in one 1800x300 house style.",
     "Scenes are drawn by the banner engine in `scripts/banners/`, rendered to a scratch folder, reviewed, then copied to `Media/Banners/`.",
     ["skills/pixel-banners/SKILL.md", "skills/pixel-banners/references/style-guide.md", "scripts/banners/pix.py"],
     "Every banner in [[Pixel Banners]] loops cleanly and stays under 1.3 MB.",
     [("Add weekday banners for daily notes", 60), ("Render the hub set for places, recipes and trips", 64)]),
    ("Preference Learning", "learn-preferences", "🧠 Learning", "🧠 Learning", "🧪 Planning", -40, -38, "Evenings at 18:45",
     "Learn how I like work done from what I write, with evidence and a confidence for each preference.",
     "Reads only what is new since the last run, merges rows into [[Learned Preferences]] and measures voice for [[Voice and Style]].",
     ["skills/learn-preferences/SKILL.md", "skills/learn-preferences/collect.py",
      "skills/learn-preferences/references/Learned Preferences.md"],
     "Dry run on the fixtures only; the scheduled run is not set up yet.",
     [("Decide which sources to include", None), ("Set up the evening schedule", None)]),
]


def build_automations(v: Vault) -> None:
    folder = "Projects/Vault Automations"
    start = TODAY - dt.timedelta(days=172)
    items = []
    for title, skill, kind, stream, status, s_off, r_off, cadence, overview, how, files, verify, follow in AUTOMATIONS:
        started = TODAY + dt.timedelta(days=s_off)
        reviewed = TODAY + dt.timedelta(days=r_off)
        fol = []
        for text, after in follow:
            if after is not None and started + dt.timedelta(days=after) <= TODAY:
                fol.append(f"- [x] {text} ✅ {iso(started + dt.timedelta(days=after))}")
            else:
                fol.append(f"- [ ] {text}")
        changes = [(reviewed, "Reviewed: behavior and verification still accurate."),
                   (started + (reviewed - started) // 2, "Tightened the instructions after a real run."),
                   (started, "Started tracking this item.")]
        changelog = "\n\n".join(f"### #{iso(d)} - {dow(d)}\n\n- {x}" for d, x in changes)
        ban = "Media/Banners/Hubs/meeting-recording-notes.gif" if skill == "meeting-recording-notes" else "Media/Banners/Note Types/project-note.gif"
        fm = frontmatter([
            ("creation date", started), ("title", title), ("type", "doc"), ("parent project", qlink("Vault Automations")),
            ("kind", kind), ("workstream", stream), ("status", status), ("summary", overview.split(",")[0].rstrip(".") + "."),
            ("next step", next((t for t, a in follow if a is None), "")), ("started", started), ("reviewed", reviewed),
            ("cadence", cadence), ("tags", ["type/doc"]), ("aliases", [f"/vault-skills:{skill}"]), *banner(ban),
        ])
        body = f"""# {title}

> [!abstract] Overview
> {overview}

Skill: `/vault-skills:{skill}` · Parent: [[Vault Automations]]

## Outcome

- **Recorded:** {overview}
- **Proposal:** keep the output short enough to read in two minutes.

## How it works

- {how}
- Read-only toward everything outside the vault; asks before any write that matters.

## Source files

{chr(10).join(f'- `plugins/vault-skills/{f}`' if f.startswith('skills/') else f'- `{f}`' for f in files)}

## Verification

- {verify}

## Follow-ups

{chr(10).join(fol)}

## Changelog

Newest first.

{changelog}

## Sources

- [[Vault Automations]]
"""
        v.add(f"{folder}/{title}.md", fm + "\n" + body, reviewed)
        items.append(title)
    fm = frontmatter([
        ("creation date", start), ("title", "Vault Automations"), ("type", "project"), ("status", "🟢 Active"),
        ("category", "Tooling"), ("summary", "The skills and scheduled jobs that keep this vault filed and briefed."),
        ("next step", "Set up the evening preference run."), ("started", start), ("reviewed", TODAY - dt.timedelta(days=2)),
        ("repo", ""), ("tags", ["type/project"]), ("aliases", []), *banner("Media/Banners/Hubs/vault-automations.gif"),
    ])
    chores = []
    d = start + dt.timedelta(days=10)
    while d <= TODAY:
        chores.append(f"- [x] Weekly vault check: links, frontmatter, fences ✅ {iso(d)}")
        d += dt.timedelta(days=R.choice([6, 7, 7, 8]))
    body = f"""# Vault Automations

[[Projects/Project Hub|Project Hub]]

> [!abstract] Overview
> One tracking note per skill or scheduled job: what it does, its source files, how it was verified and what changed. Each note sets `parent project` to this note and `type: doc`, so it shows as an item on the Project Hub.

## Items

```dataview
TABLE status, workstream, cadence, reviewed
FROM "Projects/Vault Automations"
WHERE type = "doc"
SORT reviewed DESC
```

## Next up

- [ ] Set up the evening schedule for [[Preference Learning]] 📅 {iso(TODAY + dt.timedelta(days=4))}
{chr(10).join(chores[-12:])}

## Changelog

Newest first.

### #{iso(TODAY - dt.timedelta(days=2))} - {dow(TODAY - dt.timedelta(days=2))}

- Reviewed every item; [[Preference Learning]] is next.

### #{iso(start)} - {dow(start)}

- Started the project.

## Project files

![[Projects/Projects.base#Project files]]
"""
    v.add(f"{folder}/Vault Automations.md", fm + "\n" + body, TODAY - dt.timedelta(days=2))


# --------------------------------------------------------------------------- news

PINS = {  # project: (pinned, latest sequence over time)
    "Kubernetes": ("v1.33.4", ["v1.33.5", "v1.33.6", "v1.34.2", "v1.34.3"]),
    "Flux": ("v2.6.1", ["v2.6.2", "v2.6.3", "v2.7.0"]),
    "Argo CD": ("v3.0.8", ["v3.0.9", "v3.0.11", "v3.1.2"]),
    "Karpenter": ("v1.5.0", ["v1.5.2", "v1.6.0", "v1.6.1"]),
    "cert-manager": ("v1.17.2", ["v1.17.3", "v1.18.0"]),
    "Helm": ("v3.18.1", ["v3.18.3", "v3.18.4"]),
}
INCIDENTS = [
    ("Path traversal in the `tarwell` archive library", "`tarwell` `v2.4.1`", "Patched", "Crafted archives could write outside the target folder.",
     "Nothing in our services imports it; one build image does. Rebuild it."),
    ("Token leak in the `quickrelay` webhook proxy", "`quickrelay` `v0.9.7`", "Patched", "Debug logging printed bearer tokens.",
     "Not used by the team."),
    ("Denial of service in the `yamlite` parser", "`yamlite` `v5.2.3`", "Fix released", "Deeply nested documents exhausted memory.",
     "Our config loader uses it indirectly; likely low risk because inputs are trusted."),
    ("Signed-package bypass in `pkgseal`", "`pkgseal` `v1.1.0`", "Investigating", "A malformed signature could pass verification.",
     "Our CI uses `pkgseal` to check base images. Pin to the fixed version when it lands."),
]
WEATHER = ["partly cloudy", "sunny", "light rain", "overcast", "windy and clear", "showers", "fog, then sun", "cool and clear"]


def build_news(v: Vault) -> None:
    for i in range(10):
        d = TODAY - dt.timedelta(days=3 * (9 - i))
        stage = i * 1.0 / 9
        hi = 58 + int(20 * (1 - stage)) + R.randint(-4, 4)
        lo = hi - R.randint(10, 18)
        rain = R.choice([5, 10, 20, 30, 40, 60, 70])
        cond = R.choice(WEATHER)
        incidents = R.sample(INCIDENTS, R.choice([0, 1, 1, 2]))
        rows = []
        for proj, (pin, seq) in PINS.items():
            latest = seq[min(len(seq) - 1, int(stage * len(seq)))]
            if latest != pin and R.random() < 0.55:
                kind = "minor" if latest.split(".")[1] != pin.split(".")[1] else "patch"
                why = ("new minor; read the upgrade notes before planning" if kind == "minor"
                       else "patch on our pinned line; bug fixes only per its notes")
                rows.append(f"| [{proj} `{latest}`](https://example.com/releases/{proj.lower().replace(' ', '-')}/{latest}) | `{latest}` | `{pin}` | {why} |")
        rows = rows[:4]
        need = len(rows)
        top = incidents[0][0].replace("`", "") if incidents else (rows[0].split("]")[0].strip("| [").replace("`", "") if rows else "nothing urgent")
        summary = f"{len(incidents)} security item(s) and {need} release(s) to look at; top: {top}."
        fm = frontmatter([
            ("creation date", d), ("title", f"{iso(d)} News"), ("type", "news-digest"), ("date", d), ("window", 7),
            ("incidents", len(incidents)), ("needs a look", need), ("summary", summary), ("conditions", cond),
            ("high", hi), ("low", lo), ("rain chance", rain), ("tags", ["News"]), *banner("Media/Banners/news-hub.gif"),
        ])
        inc_md = "\n\n".join(
            f"> [!danger] {t}\n> - **Status:** {st}\n> - **What happened:** {what}\n> - **Fixed versions:** {fix}\n"
            f"> - **Our work:** {ours}\n> - **Sources:** [advisory](https://example.com/advisories/{i}-{n})"
            for n, (t, fix, st, what, ours) in enumerate(incidents)) or "Nothing this window."
        worth = R.sample([
            "- **Kubernetes:** the next minor's release candidate is out; likely a quiet upgrade for us.",
            "- **Argo CD:** a docs post on progressive sync waves; useful for the billing rollout.",
            "- **Flux:** maintainers posted a roadmap update; nothing breaking announced.",
            "- **Karpenter:** a guide on consolidation budgets; worth reading before the next node change.",
            "- **Helm:** plugin signing is now documented end to end.",
            "- **cert-manager:** a reminder that an old API version goes away in two releases.",
        ], 3)
        body = f"""# {iso(d)} News

[[News/News Hub|News Hub]] · last 7 days ({iso(d - dt.timedelta(days=7))} to {iso(d)})

> [!abstract] At a glance
> **{len(incidents)} security incidents** and **{need} items to look at.** {('Start with ' + top + '.') if incidents else 'No incidents; the releases below are routine.'}
>
> Facts are what a post or release note says; "likely" marks inference.

## Weather

> [!info] Springfield · {cond}, {hi}° / {lo}°
> - **Today:** {cond}, high {hi}°, low {lo}°, rain chance {rain}%
> - **Next two days:** {R.choice(WEATHER)}, then {R.choice(WEATHER)}
> - **Alerts:** none

## Security incidents

{inc_md}

## Needs a look

| Item | Version | Our pin | Why it matters |
| --- | --- | --- | --- |
{chr(10).join(rows) if rows else '| Nothing new against our pins |  |  |  |'}

## Worth knowing

{chr(10).join(worth)}

## Quiet

- Container runtime, ingress controller and DNS add-ons: no new releases.

## Skipped

> [!note]- Judged irrelevant, listed so later runs skip them
> - Vendor webinar announcements
> - Release candidates for projects we do not run

## Gaps

> [!question]- What this digest did not check
> - Demo vault: the projects are public open-source names, but every version, advisory and note here is invented.
> - Slack incident channels were not read.
"""
        v.add(f"News/{iso(d)} News.md", fm + "\n" + body, d)


# --------------------------------------------------------------------------- wiki

def build_wiki(v: Vault) -> None:
    def wiki(rel, title, summary, tags, body, off, ban="Media/Banners/Note Types/reference-note.gif"):
        d = TODAY + dt.timedelta(days=off)
        fm = frontmatter([("creation date", d), ("title", Q(title)), ("summary", summary), ("type", "Wiki"),
                          ("tags", tags), ("aliases", []), *banner(ban)])
        v.add(rel, fm + "\n" + body, d)

    text = PHILOSOPHY.read_text(encoding="utf-8")
    text = re.sub(r"\[([^\]]+)\]\((?!https?:)[^)]+\.md\)", r"\1", text)
    text = text.replace("# Philosophy\n", "# Vault Design Philosophy\n\n**Related:** [[Wiki/Wiki Hub|Wiki Hub]]\n", 1)
    wiki("Wiki/Vault Design Philosophy.md", "Vault Design Philosophy",
         "Why the vault is records with views on top, and how that shapes the rules.", ["Obsidian"], text, -60)

    gifs = [("Places", "places"), ("Recipes", "recipes"), ("Trips", "trips"), ("Vehicles", "vehicles"),
            ("Games", "game-hub"), ("Media", "media-hub"), ("Documents", "scratch"), ("Vault Automations", "vault-automations")]
    gallery = "\n\n".join(f"### {label}\n\n![[Media/Banners/Hubs/{g}.gif]]" for label, g in gifs)
    wiki("Wiki/Pixel Banners.md", "Pixel Banners", "How the animated hub banners work and where they live.", ["Obsidian"],
         f"""# Pixel Banners

> [!abstract] At a glance
> Every hub and note type has an animated 1800x300 pixel-art banner, shown by the Pixel Banner plugin from three properties.

**Related:** [[Wiki/Wiki Hub|Wiki Hub]] · [[Animated Vault Banners]]

## Notes

- Set `banner` to a quoted vault path, such as `"Media/Banners/Hubs/places.gif"`.
- `banner-height: 200` and `banner-y: 50` keep every banner the same height and centred.
- Hub banners live in `Media/Banners/Hubs/`, weekday banners for daily notes in `Media/Banners/Days/`.
- Render new ones with `/vault-skills:pixel-banners`; review the frames before copying them in.

## Gallery

{gallery}

### Weekdays

![[Media/Banners/Days/Monday.gif]]

![[Media/Banners/Days/Friday.gif]]

## Sources

- [[Animated Vault Banners]]
""", -50)

    rows = []
    windows = [(-56, "staging", "Node image patching", "✅ Done"), (-49, "production", "Node image patching", "✅ Done"),
               (-35, "staging", "Kubernetes minor upgrade `v1.32` to `v1.33`", "✅ Done"),
               (-28, "production", "Kubernetes minor upgrade `v1.32` to `v1.33`", "✅ Done"),
               (-14, "staging", "Add-on refresh (ingress, DNS, cert-manager)", "✅ Done"),
               (-7, "production", "Add-on refresh (ingress, DNS, cert-manager)", "✅ Done"),
               (6, "staging", "Node image patching", "📅 Planned"), (13, "production", "Node image patching", "📅 Planned"),
               (27, "staging", "Kubernetes minor upgrade `v1.33` to `v1.34`", "❔ Tentative"),
               (41, "production", "Kubernetes minor upgrade `v1.33` to `v1.34`", "❔ Tentative")]
    for off, cluster, what, st in windows:
        d = workday(TODAY + dt.timedelta(days=off))
        rows.append(f"| {iso(d)} | {dow(d)} | 14:00-16:00 UTC | `{cluster}` | {what} | {st} |")
    wiki("Wiki/Upgrade Calendar.md", "Upgrade Calendar", "Maintenance windows for the staging and production clusters.",
         ["Operations"], f"""# Upgrade Calendar

> [!abstract] At a glance
> Fictional maintenance windows for the `staging` and `production` clusters. Staging always goes first, a week ahead.

**Related:** [[Wiki/Wiki Hub|Wiki Hub]] · [[Release Checklist]] · [[On-call Handbook]]

## Windows

| Date | Day | Window | Cluster | Change | Status |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(rows)}

## Notes

- Post in the team channel one day ahead and again at the start of the window.
- A production window moves if its staging window found anything.

## Sources

- The platform team's maintenance calendar (fictional).
""", -3)

    simple = [
        ("Wiki/Engineering/Release Checklist.md", "Release Checklist", "The steps every release goes through, in order.",
         ["Engineering"], ["Merge to main with green checks.", "Cut the tag from the merge commit.",
                           "Deploy to staging and watch the dashboards for an hour.",
                           "Post the release note, then deploy to production.", "Update the project changelog."], -80),
        ("Wiki/Engineering/On-call Handbook.md", "On-call Handbook", "What to do in the first fifteen minutes of a page.",
         ["Engineering"], ["Acknowledge within five minutes.", "Open an incident note and paste the alert.",
                           "Check the [[Upgrade Calendar]] for a change in flight.",
                           "Ask for help early; it is never a bother.", "Write the timeline while it is fresh."], -70),
        ("Wiki/Engineering/Writing a Good Ticket.md", "Writing a Good Ticket", "A ticket someone else can pick up cold.",
         ["Engineering"], ["Title says the outcome, not the activity.", "One paragraph of why.",
                           "Acceptance criteria as a short list.", "Link the project and any meeting it came from."], -90),
        ("Wiki/Engineering/Git Branch Naming.md", "Git Branch Naming", "Branch names that link back to their ticket.",
         ["Engineering"], ["Start with the ticket key: `ABC-123-short-title`.", "Lowercase, hyphens, no slashes beyond one prefix.",
                           "Delete the branch after merge."], -100),
        ("Wiki/Home/Home Network Setup.md", "Home Network Setup", "Where the router, mesh points and backups are.",
         ["Home"], ["Router in the hall closet; mesh points in the office and the garage.",
                    "Guest network is separate and has no access to the printer.",
                    "Laptop backups run nightly to the external drive."], -110),
    ]
    for rel, title, summary, tags, bullets, off in simple:
        body = f"""# {title}

> [!abstract] At a glance
> {summary}

**Related:** [[Wiki/Wiki Hub|Wiki Hub]]

## Notes

{chr(10).join('- ' + b for b in bullets)}

## Sources

- Team practice (fictional).
"""
        wiki(rel, title, summary, tags, body, off)


# --------------------------------------------------------------------------- preferences

def build_preferences(v: Vault, tickets, meetings_log, daily) -> None:
    standups = [m for m, _, _, _ in meetings_log if "Standup" in m]
    others = [m for m, _, _, _ in meetings_log if "Standup" not in m]
    done = [t.name for t in tickets if t.status == "Done"]

    def ev(n, *notes):
        return f"{n} · " + ", ".join(link(x) for x in notes)

    first = TODAY - dt.timedelta(days=38)
    rows = {
        "Working with people and communication": [
            ("Lead with the answer, then the detail.", "high", -38, -1, ev(9, standups[-1], others[-1], daily[-3])),
            ("Link every ticket and person mention to its note.", "high", -36, -2, ev(7, done[-1], done[-2], standups[-2])),
            ("Keep status updates to three bullets.", "medium", -30, -6, ev(4, others[-3], daily[-10])),
        ],
        "Code, review and pull requests": [
            ("Split a change over 400 lines into separate PRs.", "medium", -34, -9, ev(3, done[-3], done[-4])),
            ("Reply to every review comment, even with a thumbs-up.", "high", -38, -3, ev(8, done[-5], done[-6], done[-7])),
        ],
        "Process, tooling and releases": [
            ("Deploy to staging and wait an hour before production.", "high", -37, -7, ev(6, "Release Checklist", "Upgrade Calendar")),
            ("Write the runbook before the launch, not after.", "medium", -33, -12, ev(3, others[-4], done[-8])),
        ],
        "Working with Claude": [
            ("Show a plan before writing more than one note.", "high", -38, -1, ev(11, daily[-1], daily[-2])),
            ("Put version numbers in inline code.", "medium", -20, -4, ev(4, "Upgrade Calendar")),
            ("Ask with options rather than open questions.", "low", -9, -9, ev(1, daily[-9])),
        ],
    }
    n_pref = sum(len(x) for x in rows.values())
    sections = []
    for head, items in rows.items():
        lines = [f"## {head}", "", "| Preference | Confidence | First seen | Last seen | Evidence |", "| --- | --- | --- | --- | --- |"]
        for p, c, f, l, e in items:
            lines.append(f"| {p} | {c} | {iso(TODAY + dt.timedelta(days=f))} | {iso(TODAY + dt.timedelta(days=l))} | {e} |")
        sections.append("\n".join(lines))
    runs = "\n".join(f"- {iso(TODAY - dt.timedelta(days=k))}: {R.randint(4, 30)} new items, {R.randint(0, 2)} rows changed."
                     for k in range(1, 9))
    fm = frontmatter([("type", "reference"), ("last run", TODAY - dt.timedelta(days=1)), ("runs", 24),
                      ("evidence items", 312), ("preferences", n_pref), ("tags", ["Preferences"]),
                      *banner("Media/Banners/Note Types/reference-note.gif")])
    body = f"""# Learned Preferences

[[Preferences/Preferences Hub|Preferences Hub]]

How the owner likes work done, distilled from their own writing by `/vault-skills:learn-preferences`. Each row: one imperative sentence, a confidence (`low`, `medium`, `high`), `First seen`, `Last seen`, and an `Evidence` cell with a count and up to three links. All evidence in this demo vault is fictional.

{chr(10).join(s + chr(10) for s in sections).rstrip()}

## Promotion candidates

High-confidence rows that Claude's memory or the vault's `CLAUDE.md` does not yet hold. Promote only with the owner's approval.

- Show a plan before writing more than one note.
- Reply to every review comment, even with a thumbs-up.

## Conflicts and open questions

Rows that disagree with newer evidence. The owner decides; neither side is replaced automatically.

- "Keep status updates to three bullets" vs. the longer launch update in {link(others[-1])}.

## Rejected

Preferences the owner turned down. The learner skips anything that matches.

| Preference |
| --- |
| Always use emoji in commit messages. |

## Faded

Rows not seen for more than 90 days.

| Preference | Last seen |
| --- | --- |
| Post standup notes in the channel as well. | {iso(first - dt.timedelta(days=60))} |

## Run log

Newest first, trimmed to 15 lines.

{runs}
"""
    v.add("Preferences/Learned Preferences.md", fm + "\n" + body, TODAY - dt.timedelta(days=1))

    fm = frontmatter([("type", "reference"), ("last run", TODAY - dt.timedelta(days=1)), ("messages measured", 486),
                      ("tags", ["Preferences"]), *banner("Media/Banners/Note Types/reference-note.gif")])
    body = f"""# Voice and Style

[[Preferences/Preferences Hub|Preferences Hub]]

How the owner writes, learned by `/vault-skills:learn-preferences` and read by `/vault-skills:draft-in-voice`. Demo values: every number and message here is invented.

## Measured

Numbers computed by the collector (`collect.py voice`). Do not hand-edit the numbers.

| Source | Messages | Avg words | Avg lines | With emoji | Lowercase start | Ends with period |
| --- | --- | --- | --- | --- | --- | --- |
| Chat | 312 | 14.2 | 1.3 | 22% | 41% | 18% |
| Ticket comments | 96 | 38.5 | 3.1 | 4% | 6% | 77% |
| PR descriptions | 48 | 92.0 | 9.4 | 10% | 0% | 64% |
| Mail | 30 | 71.3 | 6.2 | 0% | 0% | 90% |

## Patterns by message type

| Message type | Length | Shape | Typical opening | Typical closing |
| --- | --- | --- | --- | --- |
| Status update | 2-4 lines | bullets | "Quick update:" | a link to the ticket |
| Review reply | 1 line | sentence | "Good catch," | none |
| PR announcement | 1 line | mention + link | the team mention | none |
| Question to a teammate | 1-2 lines | sentence | "Hey, quick one:" | "no rush" |

## Emoji I use

| Emoji | Count | Where it goes |
| --- | --- | --- |
| 👍 | 64 | alone, as a reply |
| 🙏 | 21 | end of a thank-you |
| 🎉 | 12 | release posts |
| 👀 | 9 | "looking now" |

## Voice, inferred

Judgment calls, kept apart from the measured numbers. Add a trait only after seeing it at least twice.

- Friendly and brief in chat; full sentences in tickets.
- Names the next step and the owner in almost every update.
- Avoids exclamation marks outside release posts.

## Exemplars

The owner's own short messages, verbatim (under about 300 characters each, at most 12). Never add other people's words, direct messages, secrets or private matters.

- "Quick update: proration is in review, retries are live in staging. Next: the deprecation notice."
- "Good catch, fixed in the last push."
- "Hey, quick one: is the tester list still on for Friday? no rush"
- "Runbook is up, would love a second pair of eyes before launch 🙏"
"""
    v.add("Preferences/Voice and Style.md", fm + "\n" + body, TODAY - dt.timedelta(days=1))


# --------------------------------------------------------------------------- extra hubs

def hub(v: Vault, folder: str, title: str, gif: str, blurb: str, type_value: str, columns: list[str], extra_view=""):
    order = "\n".join(f"      - {c}" for c in ["file.name", *columns])
    fm = frontmatter([("title", title), ("type", "Hub"), ("tags", ["Hub"]), ("aliases", [folder]),
                      *banner(gif if "/" in gif else f"Media/Banners/Hubs/{gif}.gif")])
    body = f"""# {title}

[[Home]]

> [!abstract] {folder}
> {blurb}

## All {folder.lower()}

```base
filters:
  and:
    - file.inFolder("{folder}")
    - type == "{type_value}"
views:
  - type: table
    name: All
    order:
{order}
    sort:
      - property: file.name
        direction: ASC
  - type: cards
    name: Cards
    order:
      - file.name
      - summary
      - status{extra_view}
```
"""
    rel = f"{folder}/{title}.md"
    v.add(rel, fm + "\n" + body, TODAY - dt.timedelta(days=5))
    return rel


def record(v: Vault, rel: str, pairs, body: str, when: dt.date):
    v.add(rel, frontmatter(pairs) + "\n" + body, when)


def build_extra_hubs(v: Vault) -> list[tuple[str, str, str]]:
    hubs = []
    T = TODAY

    def off(n):
        return T + dt.timedelta(days=n)

    # Places
    hubs.append(("Places", hub(v, "Places", "Places Hub", "places", "Places worth remembering: shops, trails, venues.",
                               "place", ["place type", "city", "status", "summary"]), "Places worth going back to"))
    for name, ptype, summary, st in [
        ("Elm Street Bakehouse", "Café", "Best cardamom buns in town; quiet before 9.", "⭐ Favourite"),
        ("Riverside Trailhead", "Trail", "Flat 8 km loop along the river; muddy after rain.", "⭐ Favourite"),
        ("Maple Hollow Library", "Library", "Good study rooms; book them a week ahead.", "✅ Visited"),
        ("Lakeview Climbing Gym", "Gym", "Where Jo and I climb on Thursdays.", "⭐ Favourite"),
        ("Springfield Farmers Market", "Market", "Saturdays 8-12, May to October.", "✅ Visited"),
    ]:
        record(v, f"Places/{name}.md", [
            ("creation date", off(-120)), ("title", Q(name)), ("type", "place"), ("summary", summary), ("place type", ptype),
            ("city", "Springfield"), ("region", ""), ("country", ""), ("address", ""), ("location", ""), ("website", ""),
            ("status", st), ("image", ""), ("reviewed", off(-R.randint(5, 60))), ("tags", ["place"]), ("aliases", [])],
            f"# {name}\n\n[[Home]] · [[Places/Places Hub|Places Hub]]\n\n## Location\n\n- Springfield\n\n## Notes\n\n- {summary}\n\n## Related records\n\n-\n",
            off(-R.randint(5, 60)))

    # Recipes
    hubs.append(("Recipes", hub(v, "Recipes", "Recipes Hub", "recipes", "Recipes that worked, with the tweaks.",
                                "Recipe", ["category", "servings", "prep time", "cook time", "status"]), "Recipes that worked"))
    for name, cat, serv, prep, cook, ingr in [
        ("Weeknight Chili", "Dinner", 4, "15 min", "40 min", ["500 g beans", "1 onion", "2 tins tomatoes", "chili powder"]),
        ("Lemon Herb Chicken", "Dinner", 4, "10 min", "35 min", ["4 chicken thighs", "1 lemon", "thyme", "garlic"]),
        ("Overnight Oats", "Breakfast", 2, "5 min", "0 min", ["1 cup oats", "1 cup milk", "chia seeds", "berries"]),
        ("Sheet-pan Gnocchi", "Dinner", 3, "10 min", "25 min", ["500 g gnocchi", "cherry tomatoes", "feta", "olive oil"]),
        ("Banana Bread", "Baking", 8, "15 min", "60 min", ["3 ripe bananas", "250 g flour", "2 eggs", "brown sugar"]),
    ]:
        when = off(-R.randint(10, 110))
        record(v, f"Recipes/{name}.md", [
            ("creation date", when), ("title", Q(name)), ("type", "Recipe"), ("summary", f"{cat} for {serv}; reliable."),
            ("date", when), ("category", cat), ("servings", serv), ("prep time", prep), ("cook time", cook),
            ("status", R.choice(["⭐ Favourite", "✅ Tried", "🔁 Regular"])), ("source", ""), ("project", ""), ("image", ""),
            ("reviewed", when), ("tags", ["Recipe"]), ("aliases", [])],
            f"# {name}\n\n[[Home]] · [[Recipes/Recipes Hub|Recipes Hub]]\n\n## Ingredients\n\n" +
            "\n".join(f"- {x}" for x in ingr) + "\n\n## Instructions\n\n1. Prep everything first.\n2. Cook, taste, adjust.\n\n"
            "## Notes and variations\n\n- Doubles well.\n\n## Source\n\n- Family recipe (fictional).\n", when)

    # Trips
    hubs.append(("Trips", hub(v, "Trips", "Trips Hub", "trips", "Trips taken and planned, with what to pack next time.",
                              "trip", ["start date", "end date", "destination", "status"]), "Trips taken and planned"))
    for s_off, days, name, dest, comp, st in [
        (-110, 3, "Mountain Hike Weekend", "Pine Ridge", ["Jo Placeholder"], "✅ Done"),
        (-75, 4, "Lake Cabin Weekend", "Clearwater Lake", ["Robin Hart", "Charlie Demo"], "✅ Done"),
        (-20, 2, "Conference in Capital City", "Capital City", [], "✅ Done"),
        (40, 5, "Winter Visit to Pat", "Capital City", ["Pat Sample"], "📅 Planned"),
        (140, 7, "Coastal Road Trip", "The coast road", ["Jo Placeholder"], "❔ Idea"),
    ]:
        s, e = off(s_off), off(s_off + days)
        full = f"{s.strftime('%Y-%m')} {name}"
        tasks = "- [x] Book the stay ✅ " + iso(s - dt.timedelta(days=21)) if s_off < 0 else "- [ ] Book the stay"
        record(v, f"Trips/{full}.md", [
            ("creation date", s - dt.timedelta(days=30)), ("title", Q(full)), ("type", "trip"), ("summary", f"{days} days at {dest}."),
            ("start date", s), ("end date", e), ("destination", dest), ("companions", [qlink(c) for c in comp]),
            ("status", st), ("project", ""), ("image", ""), ("reviewed", min(T, e)), ("tags", ["trip"]), ("aliases", [])],
            f"# {full}\n\n[[Home]] · [[Trips/Trips Hub|Trips Hub]]\n\n## Plan and itinerary\n\n- {iso(s)} to {iso(e)}, {dest}\n\n"
            f"## Packing and actions\n\n{tasks}\n\n## Trip journal\n\n-\n\n## Sources and bookings\n\n-\n", min(T, s))

    # Vehicles
    hubs.append(("Vehicles", hub(v, "Vehicles", "Vehicles Hub", "vehicles", "Cars, bikes and anything with a service history.",
                                 "vehicle", ["make", "model", "year", "status", "odometer"]), "Service history"))
    for name, make, model, year, st, odo in [
        ("Blue Hatchback", "Roadstar", "Compact 5", 2019, "🟢 In use", 61250),
        ("Commuter Bike", "Pedalworks", "City 7", 2022, "🟢 In use", ""),
        ("Old Pickup", "Roadstar", "Hauler", 2008, "💸 Sold", 188400),
        ("Utility Trailer", "Haulit", "4x6", 2015, "🟢 In use", ""),
    ]:
        when = off(-R.randint(10, 90))
        maint = f"- [x] Oil change and tyre rotation ✅ {iso(when)}" if odo else f"- [x] Tune-up ✅ {iso(when)}"
        record(v, f"Vehicles/{name}.md", [
            ("creation date", off(-200)), ("title", Q(name)), ("type", "vehicle"), ("summary", f"{year} {make} {model}."),
            ("make", make), ("model", model), ("year", year), ("status", st), ("purchase date", ""),
            ("sold date", off(-150) if st == "💸 Sold" else ""), ("people", []), ("plate", ""), ("odometer", odo),
            ("odometer date", when if odo else ""), ("project", ""), ("image", ""), ("reviewed", when),
            ("tags", ["vehicle"]), ("aliases", [])],
            f"# {name}\n\n[[Home]] · [[Vehicles/Vehicles Hub|Vehicles Hub]]\n\n## Vehicle details\n\n- {year} {make} {model}\n\n"
            f"## Maintenance log\n\n{maint}\n\n## Registration and insurance\n\n-\n\n## History and notes\n\n-\n\n## Follow-up\n\n-\n", when)

    # Events
    hubs.append(("Events", hub(v, "Events", "Events Hub", "Media/Banners/journal.gif", "Birthdays, races, parties and game nights.",
                               "event", ["date", "status", "location", "attendees"]), "Birthdays, races and parties"))
    for e_off, name, st, loc, att in [
        (-100, "Neighborhood Picnic", "✅ Happened", "Riverside Park", ["Charlie Demo"]),
        (-39, "Springfield Half Marathon", "✅ Happened", "Downtown Springfield", ["Charlie Demo"]),
        (-26, "Board Game Night", "✅ Happened", "Robin's place", ["Robin Hart", "Jo Placeholder"]),
        (16, "Jo's Birthday Dinner", "📅 Planned", "Elm Street Bakehouse", ["Jo Placeholder", "Robin Hart"]),
        (37, "Acme Holiday Party", "❔ Tentative", "Acme office", ["Riley Rivera", "Morgan Lee", "Sam Sample"]),
    ]:
        d = off(e_off)
        full = f"{iso(d)} {name}"
        record(v, f"Events/{full}.md", [
            ("creation date", d - dt.timedelta(days=20)), ("date", d), ("end date", ""), ("start", Q("18:00")), ("end", Q("21:00")),
            ("timezone", "America/Chicago"), ("title", Q(full)), ("type", "event"), ("status", st), ("location", loc),
            ("address", ""), ("attendees", [qlink(a) for a in att]), ("project", ""), ("summary", f"{name} at {loc}."),
            ("reviewed", min(T, d)), ("tags", ["event"])],
            f"# {full}\n\n[[Home]] · [[Events/Events Hub|Events Hub]]\n\n## When and where\n\n- {iso(d)}, 18:00, {loc}\n\n"
            f"## People\n\n" + "\n".join(f"- {link(a)}" for a in att) + "\n\n## Details\n\n-\n\n## Follow-up\n\n-\n\n## Sources\n\n-\n",
            min(T, d - dt.timedelta(days=20)) if d > T else d)

    # Documents
    hubs.append(("Documents", hub(v, "Documents", "Documents Hub", "scratch", "Where important papers are and when they expire. No numbers here.",
                                  "document", ["document kind", "issued", "expires", "status"]), "Papers and expiry dates"))
    for name, kind, iss, exp, issuer in [
        ("Passport", "Identity", -900, 2750, "Passport office"),
        ("Home Insurance Policy", "Insurance", -300, 65, "Fictional Mutual"),
        ("Car Registration", "Registration", -200, 165, "Springfield DMV"),
        ("Apartment Lease", "Contract", -400, 330, "Maple Court Rentals"),
        ("Dishwasher Warranty", "Warranty", -500, 230, "Appliance shop"),
    ]:
        record(v, f"Documents/{name}.md", [
            ("creation date", off(iss)), ("title", Q(name)), ("type", "document"), ("summary", f"{kind}; original in the file box."),
            ("document kind", kind), ("date", off(iss)), ("issued", off(iss)), ("expires", off(exp)), ("issuer", issuer),
            ("status", "⚠️ Renew soon" if exp < 90 else "✅ Current"), ("person", qlink(ME)), ("project", ""), ("files", []),
            ("source", ""), ("image", ""), ("reviewed", off(-R.randint(3, 40))), ("tags", ["document"]), ("aliases", [])],
            f"# {name}\n\n[[Home]] · [[Documents/Documents Hub|Documents Hub]]\n\n## Record\n\n- {kind}, issued by {issuer}.\n\n"
            "## Files and sources\n\n- Original in the file box.\n\n## Related records\n\n-\n\n## Follow-up\n\n" +
            (f"- [ ] Renew before {iso(off(exp))} 📅 {iso(off(exp - 30))}\n" if exp < 200 else "-\n"), off(-R.randint(3, 40)))

    # Games
    hubs.append(("Games", hub(v, "Games", "Games Hub", "game-hub", "What I'm playing, finished and saving for later.",
                              "Game", ["status", "platforms", "genre", "rating", "hours"]), "Playing, finished, backlog"))
    for name, st, plat, genre, rating, hours, s_off in [
        ("Starfall Tactics", "🎮 Playing", ["PC"], ["Strategy"], "", 14, -12),
        ("Pixel Farm Stories", "✅ Finished", ["Switch"], ["Cozy", "Sim"], 9, 62, -150),
        ("Dungeon Cartographer", "✅ Finished", ["PC"], ["Roguelike"], 8, 31, -90),
        ("Orbit Golf", "📋 Backlog", ["Phone"], ["Puzzle"], "", "", None),
        ("Cozy Lighthouse", "⏸️ Paused", ["Switch"], ["Adventure"], "", 6, -60),
    ]:
        started = off(s_off) if s_off is not None else ""
        finished = off(s_off + 40) if st == "✅ Finished" else ""
        record(v, f"Games/{name}.md", [
            ("creation date", off(-160)), ("title", Q(name)), ("type", "Game"), ("summary", f"{genre[0]} game on {plat[0]}."),
            ("status", st), ("kind", "Video game"), ("platforms", plat), ("genre", genre), ("developer", "Fictional Studio"),
            ("publisher", ""), ("release_date", ""), ("date", started), ("rating", rating), ("hours", hours),
            ("started", started), ("finished", finished), ("reviewed", off(-R.randint(1, 30))), ("tags", ["Game"]), ("aliases", [])],
            f"# {name}\n\n[[Games/Games Hub|Games Hub]]\n\n## Notes\n\n- {st} on {plat[0]}.\n\n## Todo\n\n- [ ] Try the hard mode\n",
            off(-R.randint(1, 30)))

    # Media (lives next to the banners and attachments)
    hubs.append(("Media", hub(v, "Media", "Media Hub", "media-hub", "Books, shows, films and podcasts: what I thought of them.",
                              "media", ["kind", "status", "rating", "finished"]), "Books, shows and podcasts"))
    for name, kind, st, rating, s_off in [
        ("The Quiet Algorithm", "📚 Book", "✅ Finished", 8, -70),
        ("Harbor Lights", "📺 Show", "▶️ Watching", "", -14),
        ("The Long Commit", "🎬 Film", "✅ Finished", 7, -33),
        ("Signals From Nowhere", "🎧 Podcast", "▶️ Listening", "", -100),
        ("Gardens of Glass", "📚 Book", "📋 Queued", "", None),
    ]:
        started = off(s_off) if s_off is not None else ""
        record(v, f"Media/Library/{name}.md", [
            ("creation date", off(-120)), ("title", Q(name)), ("type", "media"), ("summary", f"{kind.split(' ', 1)[1]}; {st.split(' ', 1)[1].lower()}."),
            ("kind", kind), ("status", st), ("rating", rating), ("started", started),
            ("finished", off(s_off + 20) if st == "✅ Finished" else ""), ("reviewed", off(-R.randint(1, 40))),
            ("tags", ["media"]), ("aliases", [])],
            f"# {name}\n\n[[Media/Media Hub|Media Hub]]\n\n## Notes\n\n- {kind}, {st.lower()}.\n", off(-R.randint(1, 40)))
    return hubs


def update_home(v: Vault, hubs) -> None:
    path = v.root / "Home.md"
    text = path.read_text(encoding="utf-8")
    rows = "".join(f"| [[{rel[:-3]}\\|{label}]] | {what} |\n" for label, rel, what in hubs)
    rows += "| [[Projects/Vault Automations/Vault Automations\\|Automations]] | Skills and scheduled jobs that run the vault |\n"
    anchor = "| [[Preferences/Preferences Hub\\|Preferences]] | Learned preferences and voice profile |\n"
    if anchor not in text:
        sys.exit("Home.md changed: hub-table anchor not found")
    text = text.replace(anchor, anchor + rows, 1)
    text = text.replace("aliases:\n  - Start here\n---", "aliases:\n  - Start here\ncssclasses:\n  - home-dashboard\n---", 1)
    v.add("Home.md", text, TODAY)


# --------------------------------------------------------------------------- .obsidian

def write_obsidian(root: Path) -> None:
    ob = root / ".obsidian"
    (ob / "snippets").mkdir(parents=True, exist_ok=True)
    core = {k: True for k in [
        "file-explorer", "global-search", "switcher", "graph", "backlink", "outgoing-link", "tag-pane", "properties",
        "page-preview", "daily-notes", "templates", "note-composer", "command-palette", "editor-status", "bookmarks",
        "outline", "word-count", "file-recovery", "bases", "canvas"]}
    core.update({"slash-command": False, "markdown-importer": False, "zk-prefixer": False, "random-note": False,
                 "slides": False, "audio-recorder": False, "workspaces": False, "publish": False, "sync": False})
    files = {
        "core-plugins.json": core,
        "community-plugins.json": ["dataview", "obsidian-tasks-plugin", "pexels-banner", "pretty-properties"],
        "appearance.json": {"cssTheme": "Primary", "theme": "obsidian", "enabledCssSnippets": ["home-dashboard"]},
        "daily-notes.json": {"folder": "Daily Notes", "template": "Templates/Daily Note Template", "format": "YYYY-MM-DD"},
        "templates.json": {"folder": "Templates"},
        # Settings only (no plugin code): the hub charts need Dataview's JavaScript queries on.
        "plugins/dataview/data.json": {"enableDataviewJs": True, "enableInlineDataviewJs": True},
    }
    for rel, data in files.items():
        p = ob / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    shutil.copyfile(SNIPPET, ob / "snippets" / "home-dashboard.css")


# --------------------------------------------------------------------------- main

TODAY = dt.date.today()


def main() -> int:
    global TODAY
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", help="output folder for the demo vault")
    ap.add_argument("--today", default=None, help="date the vault should look like it is (YYYY-MM-DD; default: today)")
    ap.add_argument("--force", action="store_true", help="replace an existing demo vault at <out>")
    args = ap.parse_args()
    if args.today:
        TODAY = dt.date.fromisoformat(args.today)
    out = Path(args.out).expanduser().resolve()
    if out.exists() and any(out.iterdir()):
        if not args.force:
            sys.exit(f"{out} exists and is not empty; pass --force to replace it")
        if not (out / ".vault-skills.yaml").exists():
            sys.exit(f"{out} does not look like a demo vault (no .vault-skills.yaml); refusing to delete it")
        shutil.rmtree(out)
    if out == TEMPLATE or TEMPLATE in out.parents:
        sys.exit("refusing to write inside vault-template/")

    shutil.copytree(TEMPLATE, out, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".DS_Store", "__pycache__", ".obsidian", ".trash"))
    for name in HUB_BANNERS:
        (out / "Media/Banners/Hubs").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BANNER_SRC / f"{name}.gif", out / "Media/Banners/Hubs" / f"{name}.gif")
    for name in DAY_BANNERS:
        (out / "Media/Banners/Days").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BANNER_SRC / f"{name}.gif", out / "Media/Banners/Days" / f"{name}.gif")

    v = Vault(out, TODAY)
    tickets = build_tickets()
    for t in tickets:
        write_ticket(v, t)
    standups, meetings_log = build_meetings(v, tickets)
    daily = build_daily(v, tickets, standups, TODAY - dt.timedelta(days=120))
    build_people(v, meetings_log)
    build_projects(v, tickets, meetings_log)
    build_automations(v)
    build_news(v)
    build_wiki(v)
    build_preferences(v, tickets, meetings_log, daily)
    hubs = build_extra_hubs(v)
    update_home(v, hubs)
    v.write()
    write_obsidian(out)

    counts: dict[str, int] = {}
    for rel in v.files:
        counts[rel.split("/")[0]] = counts.get(rel.split("/")[0], 0) + 1
    print(f"Demo vault for {TODAY} written to {out}")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]} generated notes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
