#!/usr/bin/env python3
"""Collect the past week's work for the weekly-review skill.

Read-only: this never writes to GitHub, Jira, or the vault. It reuses the
end-of-day gatherer's GitHub, Jira and Claude-session helpers over a multi-day
window, and adds the week's standup entries, daily-note summaries, dated
changelog entries, meeting notes, completed and upcoming vault tasks, and active
projects. Prints one JSON document to stdout.

Usage: gather.py [--end YYYY-MM-DD] [--days 7] [--scope work|all] [--vault PATH] [--org ORG]
                 [--jira-site SITE] [--project-keys ABC,DEF] [--daily-dir DIR]
                 [--meetings-dir DIR] [--tasks-dir DIR] [--projects-dir DIR]
                 [--standup-dir DIR] [--standup-name NAME] [--hub-link TEXT]
                 [--entry-heading TEXT] [--sensitive-dirs A,B] [--sensitive-tags #A,#B]
                 [--skip-dirs A/,B/] [--skip github,jira,sessions]

Every value comes from a flag (SKILL.md reads .vault-skills.yaml and passes them); nothing is
baked in. A missing optional value turns the dependent section into {"error": ...} or a null.
"""
import argparse
import datetime as dt
import glob
import importlib.util
import json
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(HERE)

# end-of-day's gather.py imports adf (its sibling), so load it under its own name from its folder.
sys.path.insert(0, os.path.join(SKILLS, "end-of-day"))
_spec = importlib.util.spec_from_file_location("eod_gather", os.path.join(SKILLS, "end-of-day", "gather.py"))
eod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eod)
adf = eod.adf
trunc = eod.trunc

DATED_HEADING = re.compile(r"^(#{2,4}) .*?#?(\d{4}-\d{2}-\d{2})\b.*$")
TASK_DONE = re.compile(r"^\s*- \[x\] (.*✅ (\d{4}-\d{2}-\d{2}).*)$")
TASK_OPEN = re.compile(r"^\s*- \[ \] (.*)$")
DUE = re.compile(r"📅 (\d{4}-\d{2}-\d{2})")

# Filled in by main() from the flags. Folders are vault-relative with forward slashes.
S = {
    "daily": "Daily Notes", "meetings": "Meetings", "tasks": "Tasks", "projects": "Projects",
    "standup_name": "Standup",
    # Never read: generated media, archives, templates, scratch.
    "skip_dirs": ("Media/", "Archive/", "Templates/", "Local/"),
    # Never interpreted or shared: the owner's own list of sensitive folders and tags.
    "sensitive_dirs": (), "sensitive_tags": (),
}


class Span(eod.Window):
    """A window of whole days, [first, last], usable wherever end-of-day expects a Window."""

    def __init__(self, first, last):
        self.day = last
        self.first = first
        self.start = dt.datetime.combine(first, dt.time.min).astimezone()
        self.end = dt.datetime.combine(last + dt.timedelta(days=1), dt.time.min).astimezone()

    def days(self):
        d = self.first
        while d <= self.day:
            yield d
            d += dt.timedelta(days=1)

    def has_date(self, iso):
        return self.first.isoformat() <= iso <= self.day.isoformat()


def slash(path):
    return path.strip().strip("/")


def is_sensitive_path(rel):
    return any(rel.startswith(d.rstrip("/") + "/") for d in S["sensitive_dirs"])


def vault_md(vault, scope):
    work_roots = tuple(slash(S[k]) + "/" for k in ("meetings", "tasks", "projects", "daily"))
    for p in glob.glob(os.path.join(vault, "**", "*.md"), recursive=True):
        rel = os.path.relpath(p, vault).replace(os.sep, "/")
        if rel.startswith(".") or "/." in rel or rel.startswith(S["skip_dirs"]):
            continue
        if scope == "work" and not rel.startswith(work_roots):
            continue
        yield p, rel


def read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def frontmatter(text):
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    out = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z][\w ]*):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def wikilink(rel):
    return f"[[{rel[:-3]}|{os.path.basename(rel)[:-3]}]]"


# --- GitHub -----------------------------------------------------------------

def github_week(span, org):
    data = eod.github(span, org)
    authored = []
    for pr in data["authored_prs"]:
        authored.append({
            k: pr[k] for k in ("repo", "number", "title", "url", "state", "draft", "created_at",
                               "merged_at", "jira_keys", "checks", "review_decision",
                               "pending_reviewers", "size")
        } | {
            "merged_in_window": pr["merged_today"],
            "created_in_window": pr["created_today"],
            "commits_in_window": len(pr["commits_today"]),
            "unresolved_threads": len(pr["unresolved_threads"]),
            "approvals": sorted({r["by"] for r in pr["reviews"] if r["state"] == "APPROVED"}),
            "summary": trunc(pr["body"].split("\n## ", 2)[0], 500),
        })
    involved = []
    for pr in data["involved_prs"]:
        if pr.get("batch"):
            involved.append(pr)
            continue
        involved.append({
            k: pr[k] for k in ("repo", "number", "title", "url", "author", "state", "jira_keys",
                               "review_requested_from_me")
        } | {
            "merged_in_window": pr["merged_today"],
            "my_reviews": [r["state"] for r in pr["my_reviews_today"]],
            "my_comments": pr["my_comments_today"],
        })
    pushes = {}
    for p in data["pushes_today"]:
        if "error" in p:
            pushes = p
            break
        pushes.setdefault(f"{p['repo']}:{p['ref']}", 0)
        pushes[f"{p['repo']}:{p['ref']}"] += len(p["commits"]) or 1
    return {"login": data["login"], "authored_prs": authored, "involved_prs": involved,
            "pushes_by_branch": pushes}


# --- Jira (acli) ------------------------------------------------------------

def jira_week(span):
    if not shutil.which("acli"):
        raise RuntimeError("acli is not installed (brew install atlassian/acli/acli)")
    me = eod.acli("search", "--jql", "assignee = currentUser() ORDER BY updated DESC",
                  "--fields", "assignee", "--limit", "1")
    if not me:
        raise RuntimeError("no issue assigned to the current user to read the account ID from")
    aid = me[0]["fields"]["assignee"]["accountId"]
    frm, to = span.first.strftime("%Y/%m/%d"), (span.day + dt.timedelta(days=1)).strftime("%Y/%m/%d")
    touched = eod.jql(f'issuekey in updatedBy("{aid}", "{frm}", "{to}") ORDER BY updated DESC')
    transitioned = {i["key"] for i in eod.jql(f'status CHANGED BY "{aid}" DURING ("{frm}", "{to}")')}
    resolved = {i["key"] for i in eod.jql(
        f'assignee = currentUser() AND resolved >= "{frm}" AND resolved < "{to}"')}
    created = {i["key"] for i in eod.jql(
        f'reporter = currentUser() AND created >= "{frm}" AND created < "{to}"')}

    def detail(key):
        f = eod.acli("view", key, "--fields", "summary,status,issuetype,parent,assignee,comment")["fields"]
        comments = (f.get("comment") or {}).get("comments", [])
        return {
            "key": key,
            "url": eod.issue_url(key),
            "summary": f["summary"],
            "type": f["issuetype"]["name"],
            "status": f["status"]["name"],
            "status_category": f["status"]["statusCategory"]["name"],
            "assignee": (f.get("assignee") or {}).get("displayName"),
            "parent": (f.get("parent") or {}).get("key"),
            "transitioned_by_me": key in transitioned,
            "resolved_in_window": key in resolved,
            "created_by_me_in_window": key in created,
            "my_comments": [
                trunc(adf.to_md(c.get("body")), 400) for c in comments
                if (c.get("author") or {}).get("accountId") == aid and c["created"] in span],
        }

    keys = list(dict.fromkeys([i["key"] for i in touched] + sorted(resolved | created)))
    with ThreadPoolExecutor(max_workers=6) as pool:
        details = list(pool.map(detail, keys))
    open_assigned = eod.jql("assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC")
    return {
        "touched": details,
        "open_assigned": [
            {"key": i["key"], "summary": i["fields"]["summary"], "status": i["fields"]["status"]["name"]}
            for i in open_assigned],
    }


# --- Vault ------------------------------------------------------------------

def standups(vault, span):
    """Each standup entry in the window plus the next one, whose Yesterday covers the last day."""
    out = []
    days = list(span.days()) + [eod.next_workday(span.day)]
    for d in dict.fromkeys(days):
        path, exists = eod.standup_path(vault, d)
        if exists:
            entry = eod.standup_entry(path)
            out.append({"date": d.isoformat(), "path": os.path.relpath(path, vault),
                        "text": trunc(entry["text"], 4000) if entry else None})
    return out


def daily_notes(vault, span):
    out = []
    for d in span.days():
        hits = glob.glob(os.path.join(vault, S["daily"], "**", f"{d.isoformat()}.md"), recursive=True)
        hits = [h for h in hits if "Weekly Reviews" not in h]
        if not hits:
            out.append({"date": d.isoformat(), "path": None})
            continue
        rel = os.path.relpath(hits[0], vault)
        text = read(hits[0])
        fm = frontmatter(text)
        inbox = [m.group(1) for m in map(TASK_OPEN.match, text.splitlines()) if m]
        out.append({"date": d.isoformat(), "path": rel, "summary": fm.get("summary") or None,
                    "mood": fm.get("mood") or None, "open_inbox_items": len(inbox)})
    return out


def changelog_entries(vault, span, scope):
    """Sections under dated headings (`### #YYYY-MM-DD - …`) inside the window."""
    out = []
    daily = slash(S["daily"]) + "/"
    for path, rel in vault_md(vault, scope):
        if is_sensitive_path(rel) or rel.startswith(daily):
            continue
        lines = read(path).splitlines()
        for i, line in enumerate(lines):
            m = DATED_HEADING.match(line)
            if not m or not span.has_date(m.group(2)):
                continue
            level = len(m.group(1))
            end = next((j for j in range(i + 1, len(lines))
                        if re.match(r"^#{1,%d} " % level, lines[j])), len(lines))
            body = "\n".join(lines[i + 1:end]).strip()
            if body:
                out.append({"path": rel, "date": m.group(2), "heading": line.strip("# ").strip(),
                            "text": trunc(body, 500)})
    out.sort(key=lambda e: (e["date"], e["path"]))
    return out


def meeting_notes(vault, span):
    out = []
    for p in glob.glob(os.path.join(vault, S["meetings"], "**", "*.md"), recursive=True):
        name = os.path.basename(p)
        m = re.match(r"(\d{4}-\d{2}-\d{2}) ", name)
        if not m or not span.has_date(m.group(1)) or S["standup_name"] in name:
            continue
        rel = os.path.relpath(p, vault).replace(os.sep, "/")
        text = read(p)
        tldr = re.search(r"^#{2,3} [^\n]*TL;?DR[^\n]*\n(.*?)(?=^#{2,3} |\Z)", text, re.M | re.S | re.I)
        decisions = re.search(r"^#{2,3} [^\n]*Decisions[^\n]*\n(.*?)(?=^#{2,3} |\Z)", text, re.M | re.S)
        out.append({"date": m.group(1), "path": rel, "wikilink": wikilink(rel),
                    "tldr": trunc(tldr.group(1), 800) if tldr else None,
                    "decisions": trunc(decisions.group(1), 800) if decisions else None})
    return sorted(out, key=lambda e: e["date"])


def tasks(vault, span, scope):
    """Tasks completed in the window, and open tasks overdue or due in the next 7 days."""
    horizon = (span.day + dt.timedelta(days=7)).isoformat()
    done, due = [], []
    for path, rel in vault_md(vault, scope):
        in_sensitive = is_sensitive_path(rel)
        for line in read(path).splitlines():
            sensitive = in_sensitive or any(t in line for t in S["sensitive_tags"])
            m = TASK_DONE.match(line)
            if m and span.has_date(m.group(2)):
                done.append({"path": rel, "task": trunc(m.group(1), 300), "done": m.group(2),
                             "sensitive": sensitive})
                continue
            m = TASK_OPEN.match(line)
            if m:
                d = DUE.search(m.group(1))
                # Daily habits recur every day and would crowd out real deadlines.
                if d and d.group(1) <= horizon and "🔁 every day" not in m.group(1):
                    due.append({"path": rel, "task": trunc(m.group(1), 300), "due": d.group(1),
                                "overdue": d.group(1) < span.day.isoformat(), "sensitive": sensitive})
    # Grouped per note: task notes from the Jira sync can tick dozens of checklist items in a week.
    grouped = {}
    for t in done:
        g = grouped.setdefault(t["path"], {"path": t["path"], "sensitive": t["sensitive"], "count": 0, "tasks": []})
        g["count"] += 1
        if len(g["tasks"]) < 6:
            g["tasks"].append(f'{t["done"]} {trunc(t["task"], 160)}')
    return {"completed_total": len(done),
            "completed_by_note": sorted(grouped.values(), key=lambda g: -g["count"]),
            "due_soon": sorted(due, key=lambda t: t["due"])}


def projects(vault, span, scope):
    out = []
    root = slash(S["projects"]) + "/"
    for path, rel in vault_md(vault, scope):
        if not rel.startswith(root):
            continue
        fm = frontmatter(read(path))
        if fm.get("type") != "project":
            continue
        status = fm.get("status", "")
        if not any(s in status for s in ("Active", "Planning", "Blocked", "Paused")) and \
                not span.has_date(fm.get("reviewed", "")):
            continue
        out.append({"path": rel, "wikilink": wikilink(rel), "status": status,
                    "category": fm.get("category"), "next step": fm.get("next step") or None,
                    "reviewed": fm.get("reviewed"), "reviewed_in_window": span.has_date(fm.get("reviewed", ""))})
    return out


def review_note_rel(span):
    iso_year, iso_week, _ = span.day.isocalendar()
    return f"{slash(S['daily'])}/{iso_year}/Weekly Reviews/{iso_year}-W{iso_week:02d} Weekly Review.md"


def previous_review(vault, span):
    notes = sorted(glob.glob(os.path.join(vault, S["daily"], "*", "Weekly Reviews", "*Weekly Review.md")))
    notes = [n for n in notes if frontmatter(read(n)).get("date", "") < span.first.isoformat()]
    if not notes:
        return None
    text = read(notes[-1])
    prio = re.search(r"^## [^\n]*Next Week's Priorities[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return {"path": os.path.relpath(notes[-1], vault),
            "priorities": prio.group(1).strip() if prio else None}


def csv(value):
    return tuple(v.strip() for v in value.split(",") if v.strip())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--end", type=dt.date.fromisoformat, default=dt.date.today(),
                    help="last day of the review window (default: today)")
    ap.add_argument("--days", type=int, default=7, help="window length in days (default: 7)")
    ap.add_argument("--scope", choices=("work", "all"), default="work",
                    help="work: meetings, tasks, projects and daily notes; all: the whole vault")
    ap.add_argument("--vault", default=None, help="vault root (default: $VAULT_ROOT, else search upward)")
    ap.add_argument("--org", default="", help="GitHub org to search; empty for all repos")
    ap.add_argument("--jira-site", default="", help="e.g. acme.invalid, used to build issue links")
    ap.add_argument("--project-keys", default="", help="comma-separated Jira project keys, e.g. ABC,DEF")
    ap.add_argument("--daily-dir", default="Daily Notes", help="folders.daily")
    ap.add_argument("--meetings-dir", default="Meetings", help="folders.meetings; standups live in <it>/Recurring/Standup")
    ap.add_argument("--standup-dir", default="", help="override the standup folder (vault-relative)")
    ap.add_argument("--tasks-dir", default="Tasks", help="folders.tasks")
    ap.add_argument("--projects-dir", default="Projects", help="folders.projects")
    ap.add_argument("--standup-name", default="Standup", help="note title after the date, e.g. 'Team Standup'")
    ap.add_argument("--hub-link", default="", help="text of the line after which the owner's standup entry starts")
    ap.add_argument("--entry-heading", default="", help="exact H2 line holding the entry in recorded notes")
    ap.add_argument("--sensitive-dirs", default="", help="comma-separated vault folders never interpreted or shared")
    ap.add_argument("--sensitive-tags", default="", help="comma-separated tags (e.g. #Health) marking sensitive tasks")
    ap.add_argument("--skip-dirs", default="", help="extra comma-separated folders to ignore, e.g. 'Clippings/'")
    ap.add_argument("--skip", default="", help="comma-separated sources to skip: github, jira, sessions")
    args = ap.parse_args(argv)
    args.vault = args.vault or eod.find_vault()
    skip = set(csv(args.skip))

    if args.project_keys:
        keys = "|".join(re.escape(k) for k in csv(args.project_keys))
        eod.KEY_RE = re.compile(rf"\b(?:{keys})-\d+\b")
    eod.CFG.update(jira_site=args.jira_site, tasks_dir=slash(args.tasks_dir), standup_name=args.standup_name,
                   standup_dir=slash(args.standup_dir) or f"{slash(args.meetings_dir)}/Recurring/Standup",
                   hub_link=args.hub_link, entry_heading=args.entry_heading)
    S.update(daily=slash(args.daily_dir), meetings=slash(args.meetings_dir), tasks=slash(args.tasks_dir),
             projects=slash(args.projects_dir), standup_name=args.standup_name,
             sensitive_dirs=csv(args.sensitive_dirs), sensitive_tags=csv(args.sensitive_tags),
             skip_dirs=S["skip_dirs"] + tuple(d if d.endswith("/") else d + "/" for d in csv(args.skip_dirs)))

    span = Span(args.end - dt.timedelta(days=args.days - 1), args.end)
    section = eod.section
    notes = section(eod.task_notes, args.vault, span)
    by_key, touched_notes = notes if isinstance(notes, tuple) else ({}, notes)

    def skipped(name):
        return {"error": f"skipped (--skip {name})"}

    review_rel = review_note_rel(span)
    result = {
        "window": {"first": span.first.isoformat(), "last": span.day.isoformat(),
                   "days": args.days, "scope": args.scope},
        "review_note": review_rel,
        "review_note_exists": os.path.exists(os.path.join(args.vault, review_rel)),
        "previous_review": section(previous_review, args.vault, span),
        "github": skipped("github") if "github" in skip else section(github_week, span, args.org),
        "jira": skipped("jira") if "jira" in skip else section(jira_week, span),
        "standups": section(standups, args.vault, span),
        "daily_notes": section(daily_notes, args.vault, span),
        "meeting_notes": section(meeting_notes, args.vault, span),
        "changelog_entries": section(changelog_entries, args.vault, span, args.scope),
        "tasks": section(tasks, args.vault, span, args.scope),
        "projects": section(projects, args.vault, span, args.scope),
        "task_notes_touched": touched_notes,
        "task_notes_by_key": None,
        "claude_sessions": [] if "sessions" in skip else section(eod.claude_sessions, span),
    }
    seen = set(eod.KEY_RE.findall(json.dumps([result["github"], result["jira"], result["standups"]])))
    result["task_notes_by_key"] = {k: v for k, v in by_key.items() if k in seen}
    json.dump(result, sys.stdout, indent=1, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
