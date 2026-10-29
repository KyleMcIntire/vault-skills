#!/usr/bin/env python3
"""Collect one workday's GitHub, Jira, and vault activity for the end-of-day skill.

Read-only: this never writes to GitHub, Jira, or the vault. Jira is read through
acli, GitHub through gh. Prints one JSON document to stdout.

Usage: gather.py [--date YYYY-MM-DD] [--since YYYY-MM-DD] [--vault PATH] [--org ORG]
                 [--jira-site SITE] [--project-keys ABC,DEF] [--meetings-dir DIR]
                 [--tasks-dir DIR] [--standup-name NAME] [--standup-template FILE]
                 [--hub-link TEXT] [--entry-heading TEXT] [--no-sessions]

Every value comes from a flag (SKILL.md reads .vault-skills.yaml and passes them); nothing is
baked in. A missing optional value turns the dependent section into {"error": ...} or a null.
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python -I drops the script dir
import adf  # noqa: E402

CFG = {"jira_site": "", "standup_dir": "Meetings/Recurring/Standup", "tasks_dir": "Tasks",
       "standup_name": "Standup", "standup_template": "", "hub_link": "", "entry_heading": ""}
KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")


def find_vault():
    """$VAULT_ROOT, else the nearest parent holding .vault-skills.yaml, else one holding .obsidian."""
    if os.environ.get("VAULT_ROOT"):
        return os.environ["VAULT_ROOT"]
    here = os.path.abspath(os.getcwd())
    for marker in (".vault-skills.yaml", ".obsidian"):
        cur = here
        while True:
            if os.path.exists(os.path.join(cur, marker)):
                return cur
            if os.path.dirname(cur) == cur:
                break
            cur = os.path.dirname(cur)
    return here


def issue_url(key):
    return f"https://{CFG['jira_site']}/browse/{key}" if CFG["jira_site"] else None


BODY_LIMIT = 6000
TEXT_LIMIT = 600

PR_FIELDS = """
  number title url state isDraft merged mergedAt createdAt lastEditedAt updatedAt
  body headRefName baseRefName additions deletions changedFiles reviewDecision
  repository { nameWithOwner }
  author { login }
  commits(last: 40) { nodes { commit { abbreviatedOid committedDate messageHeadline
    statusCheckRollup { state } } } }
  reviewThreads(first: 50) { nodes { isResolved isOutdated path line
    comments(first: 20) { nodes { databaseId author { login } createdAt bodyText url } } } }
  reviews(last: 30) { nodes { author { login } state submittedAt bodyText url } }
  comments(last: 30) { nodes { author { login } createdAt bodyText url } }
  reviewRequests(first: 10) { nodes { requestedReviewer {
    ... on User { login } ... on Team { slug } } } }
"""

# Search returns only identifiers; asking for the full fields of 50 PRs in one query times out (HTTP 502).
SEARCH_QUERY = """
query($q: String!) {
  search(query: $q, type: ISSUE, first: 50) {
    nodes { ... on PullRequest { number repository { owner { login } name } } }
  }
}
"""

PR_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) { pullRequest(number: $number) { %s } }
}
""" % PR_FIELDS


def trunc(text, limit=TEXT_LIMIT):
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + " …[truncated]"


def parse_ts(value):
    if not value:
        return None
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


class Window:
    def __init__(self, day):
        self.day = day
        self.start = dt.datetime.combine(day, dt.time.min).astimezone()
        self.end = self.start + dt.timedelta(days=1)

    def __contains__(self, value):
        ts = parse_ts(value) if isinstance(value, str) else value
        return ts is not None and self.start <= ts < self.end


def next_workday(day):
    # Friday, Saturday and Sunday all roll to Monday.
    return day + dt.timedelta(days={4: 3, 5: 2}.get(day.weekday(), 1))


# --- GitHub -----------------------------------------------------------------

def gh(*args, attempts=3):
    for attempt in range(attempts):
        out = subprocess.run(["gh", *args], capture_output=True, text=True)
        if out.returncode == 0:
            return out.stdout
        if "HTTP 5" not in out.stderr or attempt == attempts - 1:
            raise RuntimeError(f"gh {' '.join(args[:2])}: {out.stderr.strip()}")
        time.sleep(2 * (attempt + 1))


def gh_search(query, cache):
    """Return full PR nodes for a search, fetching each PR once across searches."""
    data = json.loads(gh("api", "graphql", "-f", f"query={SEARCH_QUERY}", "-f", f"q={query}"))
    idents = [(n["repository"]["owner"]["login"], n["repository"]["name"], n["number"])
              for n in data["data"]["search"]["nodes"] if n]

    def fetch(ident):
        owner, name, number = ident
        return json.loads(gh(
            "api", "graphql", "-f", f"query={PR_QUERY}", "-f", f"owner={owner}",
            "-f", f"name={name}", "-F", f"number={number}"))["data"]["repository"]["pullRequest"]

    missing = [i for i in idents if i not in cache]
    with ThreadPoolExecutor(max_workers=8) as pool:
        cache.update(zip(missing, pool.map(fetch, missing)))
    return [cache[i] for i in idents]


def last_check_state(pr):
    nodes = pr["commits"]["nodes"]
    rollup = nodes[-1]["commit"].get("statusCheckRollup") if nodes else None
    return rollup["state"] if rollup else None


def login_of(node):
    return (node.get("author") or {}).get("login")


def summarize_authored(pr, me, window):
    body_edited = pr["lastEditedAt"] or pr["createdAt"]
    commits = [n["commit"] for n in pr["commits"]["nodes"]]
    threads = []
    for t in pr["reviewThreads"]["nodes"]:
        comments = t["comments"]["nodes"]
        if t["isResolved"] or not comments:
            continue
        last = comments[-1]
        threads.append({
            "path": t["path"],
            "line": t["line"],
            "outdated": t["isOutdated"],
            "reply_to_id": comments[0]["databaseId"],
            "awaiting_me": login_of(last) != me,
            "opened_by": login_of(comments[0]),
            "first_comment": trunc(comments[0]["bodyText"]),
            "last_author": login_of(last),
            "last_at": last["createdAt"],
            "last_comment": trunc(last["bodyText"]),
            "url": last["url"],
        })
    my_last_comment = max(
        (c["createdAt"] for c in pr["comments"]["nodes"] if login_of(c) == me), default=None)
    return {
        "repo": pr["repository"]["nameWithOwner"],
        "number": pr["number"],
        "title": pr["title"],
        "url": pr["url"],
        "state": pr["state"],
        "draft": pr["isDraft"],
        "branch": pr["headRefName"],
        "base": pr["baseRefName"],
        "created_at": pr["createdAt"],
        "merged_at": pr["mergedAt"],
        "merged_today": pr["mergedAt"] in window,
        "created_today": pr["createdAt"] in window,
        "updated_today": pr["updatedAt"] in window,
        "size": f"+{pr['additions']}/-{pr['deletions']} across {pr['changedFiles']} files",
        "jira_keys": sorted(set(KEY_RE.findall(f"{pr['title']} {pr['headRefName']} {pr['body']}"))),
        "title_has_jira_key": bool(KEY_RE.search(pr["title"])),
        "checks": last_check_state(pr),
        "review_decision": pr["reviewDecision"],
        "pending_reviewers": [
            r["requestedReviewer"].get("login") or r["requestedReviewer"].get("slug")
            for r in pr["reviewRequests"]["nodes"] if r["requestedReviewer"]],
        "reviews": [
            {"by": login_of(r), "state": r["state"], "at": r["submittedAt"],
             "body": trunc(r["bodyText"]), "url": r["url"]}
            for r in pr["reviews"]["nodes"] if login_of(r) != me],
        "body_last_edited": body_edited,
        "body": trunc(pr["body"], BODY_LIMIT),
        "commits_today": [
            f"{c['abbreviatedOid']} {c['messageHeadline']}"
            for c in commits if c["committedDate"] in window],
        "commits_after_body_edit": [
            f"{c['abbreviatedOid']} {c['committedDate']} {c['messageHeadline']}"
            for c in commits if parse_ts(c["committedDate"]) > parse_ts(body_edited)],
        "unresolved_threads": threads,
        "others_comments_since_my_last": [
            {"by": login_of(c), "at": c["createdAt"], "body": trunc(c["bodyText"]), "url": c["url"]}
            for c in pr["comments"]["nodes"]
            if login_of(c) != me and (my_last_comment is None or c["createdAt"] > my_last_comment)],
    }


def summarize_involved(pr, me, window):
    mine = [r for r in pr["reviews"]["nodes"] if login_of(r) == me]
    my_last_review = max((r["submittedAt"] for r in mine), default=None)
    commits = [n["commit"] for n in pr["commits"]["nodes"]]
    my_thread_comments_today = sum(
        1 for t in pr["reviewThreads"]["nodes"] for c in t["comments"]["nodes"]
        if login_of(c) == me and c["createdAt"] in window)
    my_comments_today = sum(
        1 for c in pr["comments"]["nodes"] if login_of(c) == me and c["createdAt"] in window)
    requested = any(
        (r["requestedReviewer"] or {}).get("login") == me for r in pr["reviewRequests"]["nodes"])
    return {
        "repo": pr["repository"]["nameWithOwner"],
        "number": pr["number"],
        "title": pr["title"],
        "url": pr["url"],
        "author": login_of(pr),
        "state": pr["state"],
        "updated_at": pr["updatedAt"],
        "merged_today": pr["mergedAt"] in window,
        "jira_keys": sorted(set(KEY_RE.findall(f"{pr['title']} {pr['headRefName']}"))),
        "my_reviews_today": [
            {"state": r["state"], "at": r["submittedAt"], "body": trunc(r["bodyText"])}
            for r in mine if r["submittedAt"] in window],
        "my_comments_today": my_comments_today + my_thread_comments_today,
        "review_requested_from_me": requested,
        "my_last_review": my_last_review,
        "commits_since_my_last_review": [
            f"{c['abbreviatedOid']} {c['messageHeadline']}" for c in commits
            if my_last_review and c["committedDate"] > my_last_review],
    }


def group_batches(prs):
    """Collapse one author's same-titled PRs across many repos (a bulk rollout) into one entry."""
    groups = {}
    for pr in prs:
        groups.setdefault((pr["author"], pr["title"]), []).append(pr)
    out = []
    for (author, title), members in groups.items():
        if len(members) < 3:
            out += members
            continue
        out.append({
            "batch": True, "author": author, "title": title, "count": len(members),
            "states": sorted({m["state"] for m in members}),
            "my_reviews_today": sum(len(m["my_reviews_today"]) for m in members),
            "prs": [f"{m['repo']}#{m['number']}" for m in members],
        })
    return out


def github(window, org, since_day=None):
    me = json.loads(gh("api", "user"))["login"]
    # --since widens only the search, so a PR merged last evening is listed; the
    # per-PR "today" facts still use the workday's window.
    since = (Window(since_day).start if since_day else window.start).isoformat(timespec="seconds")
    scope = f"org:{org}" if org else ""
    cache, authored = {}, {}
    for q in (f"is:pr {scope} author:{me} updated:>={since}", f"is:pr {scope} is:open author:{me}"):
        for pr in gh_search(q, cache):
            authored[pr["url"]] = summarize_authored(pr, me, window)
    involved = {}
    # user-review-requested excludes requests made only to one of my teams.
    for q in (f"is:pr {scope} involves:{me} -author:{me} updated:>={since}",
              f"is:pr {scope} is:open user-review-requested:{me}"):
        for pr in gh_search(q, cache):
            s = summarize_involved(pr, me, window)
            waiting_on_me = s["state"] == "OPEN" and s["review_requested_from_me"]
            if s["my_reviews_today"] or s["my_comments_today"] or waiting_on_me:
                involved[pr["url"]] = s
    pushes = []
    try:
        events = json.loads(gh("api", f"users/{me}/events?per_page=100"))
    except RuntimeError as err:
        events, pushes = [], [{"error": str(err)}]
    for e in events:
        if e["type"] == "PushEvent" and e["created_at"] in window:
            p = e.get("payload", {})
            pushes.append({
                "repo": e["repo"]["name"],
                "ref": p.get("ref", "").removeprefix("refs/heads/"),
                "at": e["created_at"],
                "commits": [c["message"].splitlines()[0] for c in p.get("commits", [])],
            })
    return {
        "login": me,
        "authored_prs": list(authored.values()),
        "involved_prs": group_batches(list(involved.values())),
        "pushes_today": pushes,
    }


# --- Jira (acli) ------------------------------------------------------------

VIEW_FIELDS = "summary,status,description,comment,assignee,reporter,created,updated,issuetype,parent,issuelinks"


def acli(*args):
    out = subprocess.run(["acli", "jira", "workitem", *args, "--json"], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"acli {' '.join(args[:2])}: {(out.stderr or out.stdout).strip()[:300]}")
    return json.loads(out.stdout or "null")


def jql(query):
    """Keys and summaries only: acli search rejects most other fields, so details come from view."""
    return [i for i in acli("search", "--jql", query, "--fields", "summary,status", "--paginate") or [] if i]


def issue_detail(key, account_id, window, transitioned):
    f = acli("view", key, "--fields", VIEW_FIELDS)["fields"]
    comments = (f.get("comment") or {}).get("comments", [])
    mine = [c for c in comments if (c.get("author") or {}).get("accountId") == account_id]
    description = f.get("description")
    return {
        "key": key,
        "url": issue_url(key),
        "summary": f["summary"],
        "type": f["issuetype"]["name"],
        "status": f["status"]["name"],
        "status_category": f["status"]["statusCategory"]["name"],
        "transitioned_by_me_today": key in transitioned,
        "assignee": (f.get("assignee") or {}).get("displayName"),
        "reporter": (f.get("reporter") or {}).get("displayName"),
        "created_today": f["created"] in window,
        "updated": f["updated"],
        "parent": (f.get("parent") or {}).get("key"),
        "links": [
            f"{l['type']['outward'] if 'outwardIssue' in l else l['type']['inward']} "
            f"{(l.get('outwardIssue') or l.get('inwardIssue'))['key']}"
            for l in f.get("issuelinks", [])],
        # Markdown rendering of the ADF. Editing a description whose ADF has nodes listed in
        # description_unsupported needs the raw ADF (acli view <key> --fields description --json).
        "description": trunc(adf.to_md(description), BODY_LIMIT),
        "description_unsupported": adf.unsupported(description) if description else [],
        "my_last_comment_at": max((c["created"] for c in mine), default=None),
        "comments_today": [
            {"by": (c.get("author") or {}).get("displayName"), "at": c["created"],
             "body": trunc(adf.to_md(c.get("body")), 1500)}
            for c in comments if c["created"] in window],
    }


def jira_activity(window):
    if not shutil.which("acli"):
        raise RuntimeError("acli is not installed (brew install atlassian/acli/acli)")
    # acli has no "myself" command; updatedBy() needs an account ID, not currentUser().
    me = acli("search", "--jql", "assignee = currentUser() ORDER BY updated DESC",
              "--fields", "assignee", "--limit", "1")
    if not me:
        raise RuntimeError("no issue assigned to the current user to read the account ID from")
    aid = me[0]["fields"]["assignee"]["accountId"]
    frm, to = window.day.strftime("%Y/%m/%d"), (window.day + dt.timedelta(days=1)).strftime("%Y/%m/%d")
    touched = jql(f'issuekey in updatedBy("{aid}", "{frm}", "{to}") ORDER BY updated DESC')
    # acli returns no changelog, so transitions come from JQL instead.
    transitioned = {i["key"] for i in jql(f'status CHANGED BY "{aid}" DURING ("{frm}", "{to}")')}
    open_assigned = jql("assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC")
    with ThreadPoolExecutor(max_workers=6) as pool:
        details = list(pool.map(lambda i: issue_detail(i["key"], aid, window, transitioned), touched))
    return {
        "touched_today": details,
        "open_assigned": [
            {"key": i["key"], "summary": i["fields"]["summary"], "status": i["fields"]["status"]["name"]}
            for i in open_assigned],
    }


# --- Vault ------------------------------------------------------------------

# Each standup is its own note: `<standup_dir>/YYYY-MM-DD <standup_name>.md`. The owner's entry is the
# section named by --entry-heading when the note came from a recording, else everything after the
# line containing --hub-link, else everything after the first H1.


def standup_path(vault, day):
    """The day's note if it exists, else the path a new note takes."""
    path = os.path.join(vault, CFG["standup_dir"], f"{day.isoformat()} {CFG['standup_name']}.md")
    return path, os.path.exists(path)


def standup_entry(path):
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    heading = CFG["entry_heading"]
    start = next((i for i, l in enumerate(lines) if heading and l.rstrip() == heading), None)
    if start is not None:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        first = start + 1
    else:
        hub = CFG["hub_link"]
        anchor = next((i for i, l in enumerate(lines) if hub and hub in l), None)
        if anchor is None:
            anchor = next((i for i, l in enumerate(lines) if l.startswith("# ")), None)
        if anchor is None:
            return None
        first, end = anchor + 1, len(lines)
    # The morning brief is reference-only; keep the editable sections.
    brief = next((i for i in range(first, end) if lines[i].strip() == "### Morning brief"), end)
    return {"line": first + 1, "text": "\n".join(lines[first:brief]).strip(),
            "in_recorded_note": start is not None}


def standup(vault, day, nxt):
    out = {"template": CFG["standup_template"] or None}
    for label, d in (("today", day), ("next", nxt)):
        path, exists = standup_path(vault, d)
        out[f"{label}_path"] = os.path.relpath(path, vault)
        out[f"{label}_file_exists"] = exists
        out[f"{label}_entry"] = standup_entry(path) if exists else None
    return out


def task_notes(vault, window):
    """Map Jira keys to their task notes and list the notes touched today."""
    all_md = glob.glob(os.path.join(vault, "**", "*.md"), recursive=True)
    names = {}
    for p in all_md:
        names.setdefault(os.path.basename(p)[:-3], []).append(p)
    by_key, touched = {}, []
    for p in glob.glob(os.path.join(vault, CFG["tasks_dir"], "**", "*.md"), recursive=True):
        rel = os.path.relpath(p, vault)
        name = os.path.basename(p)[:-3]
        link = name if len(names[name]) == 1 else rel[:-3]
        with open(p, encoding="utf-8") as fh:
            head = fh.read(2000)
        m = re.search(r"^url:\s*\S*/browse/([A-Z][A-Z0-9]+-\d+)\s*$", head, re.M)
        status = re.search(r"^status:\s*(.+)$", head, re.M)
        entry = {"path": rel, "wikilink": f"[[{link}]]", "status": status.group(1).strip() if status else None}
        if m:
            by_key.setdefault(m.group(1), []).append(entry)
        if dt.datetime.fromtimestamp(os.path.getmtime(p)).astimezone() in window:
            touched.append({**entry, "jira_key": m.group(1) if m else None})
    return by_key, touched


def completed_tasks(vault, day):
    marker = f"✅ {day.isoformat()}"
    done = []
    for p in glob.glob(os.path.join(vault, "**", "*.md"), recursive=True):
        if any(part.startswith(".") for part in os.path.relpath(p, vault).split(os.sep)):
            continue
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                if marker in line and re.match(r"\s*- \[x\]", line):
                    done.append({"path": os.path.relpath(p, vault), "task": line.strip()})
    return done


def claude_sessions(window):
    """First prompt of each Claude Code session active today, as hints for work not visible elsewhere."""
    sessions = []
    for p in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
        if dt.datetime.fromtimestamp(os.path.getmtime(p)).astimezone() not in window:
            continue
        prompt = None
        with open(p, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                try:
                    rec = json.loads(raw)
                except ValueError:
                    continue
                if rec.get("type") != "user" or rec.get("isMeta"):
                    continue
                content = rec.get("message", {}).get("content")
                if isinstance(content, list):
                    content = " ".join(c.get("text", "") for c in content if c.get("type") == "text")
                if content and not content.lstrip().startswith("<"):
                    prompt = content
                    break
        if prompt:
            sessions.append({
                "project": os.path.basename(os.path.dirname(p)),
                "cwd_hint": os.path.basename(os.path.dirname(p)).replace("-", "/"),
                "first_prompt": trunc(prompt, 300),
            })
    return sessions


def section(fn, *args):
    try:
        return fn(*args)
    except Exception as err:  # Report the failure and keep the other sources.
        return {"error": f"{type(err).__name__}: {err}"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", type=dt.date.fromisoformat, default=dt.date.today(),
                    help="workday to summarize (default: today)")
    ap.add_argument("--vault", default=None, help="vault root (default: $VAULT_ROOT, else search upward)")
    ap.add_argument("--org", default="", help="GitHub org to search; empty for all repos")
    ap.add_argument("--jira-site", default="", help="e.g. acme.invalid, used to build issue links")
    ap.add_argument("--project-keys", default="", help="comma-separated Jira project keys, e.g. ABC,DEF")
    ap.add_argument("--meetings-dir", default="Meetings", help="folders.meetings; standups live in <it>/Recurring/Standup")
    ap.add_argument("--standup-dir", default="", help="override the standup folder (vault-relative)")
    ap.add_argument("--tasks-dir", default="Tasks", help="folders.tasks")
    ap.add_argument("--standup-name", default="Standup", help="note title after the date, e.g. 'Team Standup'")
    ap.add_argument("--standup-template", default="", help="vault-relative template path, echoed back")
    ap.add_argument("--hub-link", default="", help="text of the line after which the owner's entry starts")
    ap.add_argument("--entry-heading", default="", help="exact H2 line holding the entry in recorded notes")
    ap.add_argument("--no-sessions", action="store_true", help="skip reading local Claude Code session prompts")
    ap.add_argument("--since", type=dt.date.fromisoformat, default=None,
                    help="also list PRs updated since the start of this day (start-of-day passes the previous workday)")
    args = ap.parse_args()
    args.vault = args.vault or find_vault()
    global KEY_RE
    if args.project_keys:
        keys = "|".join(re.escape(k.strip()) for k in args.project_keys.split(",") if k.strip())
        KEY_RE = re.compile(rf"\b(?:{keys})-\d+\b")
    CFG.update(jira_site=args.jira_site, tasks_dir=args.tasks_dir, standup_name=args.standup_name,
               standup_dir=args.standup_dir or f"{args.meetings_dir}/Recurring/Standup",
               standup_template=args.standup_template, hub_link=args.hub_link,
               entry_heading=args.entry_heading)

    window = Window(args.date)
    nxt = next_workday(args.date)
    notes = section(task_notes, args.vault, window)
    by_key, touched_notes = notes if isinstance(notes, tuple) else ({}, notes)

    result = {
        "workday": f"{args.date.isoformat()} ({args.date.strftime('%A')})",
        "next_standup": f"{nxt.isoformat()} ({nxt.strftime('%A')})",
        "window": [window.start.isoformat(), window.end.isoformat()],
        "github": section(github, window, args.org, args.since),
        "jira": section(jira_activity, window),
        "standup": section(standup, args.vault, args.date, nxt),
        "task_notes_by_key": None,
        "task_notes_touched_today": touched_notes,
        "vault_tasks_completed_today": section(completed_tasks, args.vault, args.date),
        "claude_sessions_today": [] if args.no_sessions else section(claude_sessions, window),
    }
    # Only map the keys that appear in today's GitHub or Jira data.
    seen = set(KEY_RE.findall(json.dumps([result["github"], result["jira"], result["standup"]])))
    result["task_notes_by_key"] = {k: v for k, v in by_key.items() if k in seen}
    json.dump(result, sys.stdout, indent=1, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
