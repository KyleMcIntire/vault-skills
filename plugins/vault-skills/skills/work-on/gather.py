#!/usr/bin/env python3
"""Collect everything the vault, Jira and GitHub know about one Jira issue or one project note.

Read-only. Prints one JSON document to stdout. A section that fails holds
{"error": ...} so the caller can report it and carry on. Slack is not read here;
the skill searches it through the Slack connector.

Usage: gather.py ABC-123 [--vault PATH] [--org ORG] [--repos DIR] [--jira-site SITE]
                         [--tasks-dir DIR] [--meetings-dir DIR] [--standup-name NAME]
       gather.py --project "Project Name" [--vault PATH] [--projects-dir DIR] [--repos DIR]

With --project the target is a project note's name, title, or alias, under --projects-dir (vault and
local git only) or under any --linked-projects-dir (also standup entries, task notes and open PRs).

All values arrive as flags; SKILL.md reads .vault-skills.yaml and passes them. Nothing is baked in.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "end-of-day"))
import adf  # noqa: E402  (shared ADF -> Markdown converter)

CFG = {"jira_site": "", "tasks_dir": "Tasks", "standup_dir": "Meetings/Recurring/Standup",
       "standup_name": "Standup", "hub_link": "", "entry_heading": "", "sessions_dir": ""}


def find_vault():
    """$VAULT_ROOT, else the nearest parent holding .vault-skills.yaml, else one holding .obsidian."""
    if os.environ.get("VAULT_ROOT"):
        return os.environ["VAULT_ROOT"]
    here = Path.cwd().resolve()
    for marker in (".vault-skills.yaml", ".obsidian"):
        for cur in (here, *here.parents):
            if (cur / marker).exists():
                return str(cur)
    return str(here)


KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
SKIP_DIRS = {".obsidian", ".trash", ".git", ".claude", "node_modules"}
VIEW_FIELDS = ("summary,status,description,comment,assignee,reporter,created,updated,"
               "issuetype,priority,labels,parent,subtasks,issuelinks")


def run(cmd, timeout=60):
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if out.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:4])}: {(out.stderr or out.stdout).strip()[:300]}")
    return out.stdout


def acli(*args):
    return json.loads(run(["acli", "jira", "workitem", *args, "--json"]) or "null")


def md(doc):
    return adf.to_md(doc) if doc else ""


def jira(key):
    f = acli("view", key, "--fields", VIEW_FIELDS)["fields"]
    name = lambda u: (u or {}).get("displayName")  # noqa: E731
    brief = lambda i: {  # noqa: E731
        "key": i["key"], "summary": i["fields"]["summary"],
        "status": i["fields"]["status"]["name"]}
    links = []
    for l in f.get("issuelinks", []):
        out = "outwardIssue" in l
        other = l["outwardIssue"] if out else l["inwardIssue"]
        links.append({"relation": l["type"]["outward" if out else "inward"], **brief(other)})
    try:
        children = [{"key": i["key"], "summary": i["fields"]["summary"], "status": i["fields"]["status"]["name"],
                     "assignee": name(i["fields"].get("assignee"))}
                    for i in acli("search", "--jql", f"parent = {key} ORDER BY created ASC",
                                  "--fields", "summary,status,assignee", "--paginate") or [] if i]
    except RuntimeError as e:
        children = {"error": str(e)}
    return {
        "key": key,
        "url": f"https://{CFG['jira_site']}/browse/{key}" if CFG["jira_site"] else None,
        "summary": f["summary"],
        "type": f["issuetype"]["name"],
        "status": f["status"]["name"],
        "status_category": f["status"]["statusCategory"]["name"],
        "priority": (f.get("priority") or {}).get("name"),
        "labels": f.get("labels", []),
        "assignee": name(f.get("assignee")),
        "reporter": name(f.get("reporter")),
        "created": f["created"],
        "updated": f["updated"],
        "parent": f.get("parent") and {"key": f["parent"]["key"], "summary": f["parent"]["fields"]["summary"]},
        "children": children,
        "links": links,
        "description": md(f.get("description")),
        "description_unsupported": adf.unsupported(f["description"]) if f.get("description") else [],
        "comments": [{"by": name(c.get("author")), "at": c["created"], "body": md(c.get("body"))}
                     for c in (f.get("comment") or {}).get("comments", [])],
    }


def vault_notes(vault, key):
    """Task note(s) whose url ends in the key, plus other notes that mention it."""
    tasks, mentions = [], []
    root = Path(vault)
    url_re = re.compile(rf"^url:\s*\S*/browse/{re.escape(key)}\s*$", re.M)
    key_re = re.compile(rf"(?<![A-Z0-9-]){re.escape(key)}(?!\d)")
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if not fn.endswith(".md"):
                continue
            p = Path(dirpath) / fn
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = str(p.relative_to(root))
            head = text.split("\n---", 2)[0] if text.startswith("---") else ""
            if rel.startswith(CFG["tasks_dir"].rstrip("/") + "/") and url_re.search(head):
                tasks.append(rel)
            elif key_re.search(text):
                mentions.append(rel)
    sessions = []
    # Optional: a folder of imported Claude session notes (--sessions-dir), newest first.
    sdir = root / CFG["sessions_dir"] if CFG["sessions_dir"] else None
    if sdir and sdir.is_dir():
        for p in sorted(sdir.glob("*.md"), reverse=True):
            try:
                if key in p.read_text(encoding="utf-8"):
                    sessions.append(str(p.relative_to(root)))
            except (OSError, UnicodeDecodeError):
                pass
            if len(sessions) >= 5:
                break
    return {"task_notes": tasks, "other_notes": sorted(mentions)[:25], "recent_claude_sessions": sessions}


REVIEW_RE = re.compile(r"review|claude", re.I)
FAILED = {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}
THREADS_QUERY = """query($o:String!,$r:String!,$n:Int!,$endCursor:String){repository(owner:$o,name:$r){
pullRequest(number:$n){reviewThreads(first:100,after:$endCursor){nodes{isResolved isOutdated path line
comments(first:30){nodes{author{login} body createdAt}}} pageInfo{hasNextPage endCursor}}}}}"""
THREADS_JQ = (".data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved|not) | "
              "{path, line, outdated: .isOutdated, comments: [.comments.nodes[] | {by: .author.login, at: .createdAt, body}]}")


def seconds(a, b):
    from datetime import datetime
    try:
        f = lambda t: datetime.fromisoformat(t.replace("Z", "+00:00"))  # noqa: E731
        return int((f(b) - f(a)).total_seconds())
    except (TypeError, ValueError):
        return None


def jsonl(text):
    return [json.loads(l) for l in text.splitlines() if l.strip()]


def unresolved_threads(repo, number, author):
    owner, name = repo.split("/", 1)
    out = run(["gh", "api", "graphql", "--paginate", "-F", f"o={owner}", "-F", f"r={name}", "-F", f"n={number}",
               "-f", f"query={THREADS_QUERY}", "--jq", THREADS_JQ])
    threads = []
    for t in jsonl(out):
        c = t["comments"]
        threads.append({"path": t["path"], "line": t["line"], "outdated": t["outdated"],
                        "first_by": c[0]["by"], "first": c[0]["body"][:400],
                        "last_by": c[-1]["by"], "last": c[-1]["body"][:300] if len(c) > 1 else None,
                        "replies": len(c) - 1,
                        "waiting_on_author": c[-1]["by"] != author})
    return threads


def failing_checks(repo, sha):
    """Failed check runs on a commit, with annotations (SonarQube's rule and line come through here)."""
    runs = jsonl(run(["gh", "api", f"repos/{repo}/commits/{sha}/check-runs", "--paginate", "--jq",
                      ".check_runs[] | {id, name, conclusion, url: .html_url, "
                      "count: .output.annotations_count, title: .output.title}"]))
    out = []
    for r in runs:
        if (r["conclusion"] or "").upper() not in FAILED:
            continue
        item = {"name": r["name"], "conclusion": r["conclusion"], "url": r["url"], "title": r["title"],
                "annotations": []}
        if r["count"]:
            try:
                item["annotations"] = jsonl(run([
                    "gh", "api", f"repos/{repo}/check-runs/{r['id']}/annotations", "--jq",
                    ".[] | {path, line: .start_line, level: .annotation_level, title, message: .message[0:300]}"]))[:10]
            except RuntimeError as e:
                item["annotations_error"] = str(e)
        out.append(item)
    return out


def review_coverage(d, author):
    """Which commits no reviewer has seen. A review is one by someone other than the PR author, or a
    'Claude finished' comment from the Actions bot; a clean re-review leaves only the comment."""
    events = []
    for r in d.get("reviews") or []:
        login = (r.get("author") or {}).get("login")
        if login and login != author and r.get("submittedAt"):
            events.append((r["submittedAt"], login, (r.get("commit") or {}).get("oid", "")))
    for c in d.get("comments") or []:
        login = (c.get("author") or {}).get("login", "")
        if login.startswith("github-actions") and "Claude finished" in (c.get("body") or ""):
            events.append((c["createdAt"], login, ""))
    commits = [{"sha": c["oid"][:7], "headline": c["messageHeadline"], "at": c["committedDate"]}
               for c in d.get("commits") or []]
    if not events:
        return {"reviewed": False, "last_review": None, "commits_after_last_review": commits}
    at, by, oid = max(events)
    return {"reviewed": True, "last_review": {"by": by, "at": at, "commit": oid[:7] or None},
            "commits_after_last_review": [c for c in commits if c["at"] > at],
            # Full sha of the reviewed commit, if the review names one. github() uses it and drops it.
            "reviewed_oid": oid or None}


def net_files(repo, base, head):
    """Files `head` changes relative to the point where it and `base` diverge, with line counts."""
    out = run(["gh", "api", f"repos/{repo}/compare/{base}...{head}", "--jq",
               "{status, ahead_by, behind_by, files: [.files[] | {f: .filename, a: .additions, d: .deletions}]}"])
    d = json.loads(out)
    return d, {x["f"]: (x["a"], x["d"]) for x in d["files"]}


def compare_commits(repo, old, new):
    """For a PR whose reviewed commit is gone: what the reviewed version changed versus what the head
    changes. The REST API has no two-dot compare, so this takes each side's net change from the commit
    they diverge at and compares the two. A rebase onto a newer base adds the base's own changes to both."""
    head_meta, head_files = net_files(repo, old, new)
    _, old_files = net_files(repo, new, old)
    dropped = sorted(set(old_files) - set(head_files))
    added = sorted(set(head_files) - set(old_files))
    changed = sorted(f for f in set(old_files) & set(head_files) if old_files[f] != head_files[f])
    return {"status": head_meta["status"], "ahead_by": head_meta["ahead_by"], "behind_by": head_meta["behind_by"],
            "reviewed_version_files": len(old_files), "head_files": len(head_files),
            "dropped_since_review": dropped[:20], "added_since_review": added[:20],
            "line_counts_changed": [{"file": f, "reviewed": old_files[f], "head": head_files[f]} for f in changed[:20]],
            "identical_net_change": not (dropped or added or changed)}


def github(key, org):
    if not org:
        raise RuntimeError("no --org given; pass --org <github-org> (or --org all to search every repo)")
    if org == "all":
        org = ""
    # gh search is fuzzy: an unquoted ABC-1 matches any PR with "ABC" and a "1", so search the quoted
    # phrase and then keep only PRs that name the exact key in the title, body, or branch.
    cmd = ["gh", "search", "prs", f'"{key}"', "--limit", "30", "--json",
           "number,title,body,state,repository,url,updatedAt,isDraft,author"]
    if org:
        cmd[4:4] = ["--owner", org]
    prs = json.loads(run(cmd))
    key_re = re.compile(rf"(?<![A-Z0-9-]){re.escape(key)}(?!\d)")
    out = []
    for pr in prs:
        item = {"repo": pr["repository"]["nameWithOwner"], "number": pr["number"], "title": pr["title"],
                "state": pr["state"], "draft": pr["isDraft"], "author": pr["author"]["login"],
                "updated": pr["updatedAt"], "url": pr["url"]}
        try:
            d = json.loads(run(["gh", "pr", "view", str(pr["number"]), "--repo", item["repo"], "--json",
                                "headRefName,headRefOid,baseRefName,reviewDecision,mergeStateStatus,"
                                "statusCheckRollup,reviewRequests,mergedAt,additions,deletions,changedFiles,"
                                "commits,reviews,comments"]))
            if not key_re.search(f'{pr["title"]} {pr.get("body") or ""} {d["headRefName"]}'):
                continue
            checks, review_checks = {}, []
            for c in d.get("statusCheckRollup") or []:
                state = c.get("conclusion") or c.get("state") or c.get("status") or "UNKNOWN"
                checks[state] = checks.get(state, 0) + 1
                name = c.get("name") or c.get("context") or ""
                if REVIEW_RE.search(name + " " + (c.get("workflowName") or "")):
                    review_checks.append({"name": name, "result": state,
                                          "seconds": seconds(c.get("startedAt"), c.get("completedAt"))})
            item.update(branch=d["headRefName"], head=d["headRefOid"][:7], base=d["baseRefName"],
                        review_decision=d["reviewDecision"], merge_state=d["mergeStateStatus"],
                        merged_at=d["mergedAt"], checks=checks, review_checks=review_checks,
                        pending_reviewers=[r.get("login") or r.get("name") for r in d.get("reviewRequests", [])],
                        size=f'+{d["additions"]}/-{d["deletions"]} in {d["changedFiles"]} files',
                        **review_coverage(d, item["author"]))
            # A reviewed commit that is no longer in the PR was amended, rebased, or force-pushed away, so
            # "commits after the last review" may hold a rewrite of reviewed code, not new work.
            oid = item.pop("reviewed_oid", None)
            in_history = {c["oid"] for c in d.get("commits") or []}
            item["reviewed_commit_rewritten"] = (oid not in in_history) if oid else None
            if item["reviewed_commit_rewritten"]:
                item["rewrite_diff"] = section(compare_commits, item["repo"], oid, d["headRefOid"])
            if pr["state"].lower() == "open":
                item["failing_checks"] = section(failing_checks, item["repo"], d["headRefOid"])
                item["unresolved_threads"] = section(unresolved_threads, item["repo"], pr["number"], item["author"])
        except (RuntimeError, ValueError, KeyError) as e:
            item["detail_error"] = str(e)
        out.append(item)
    return out


DATE_H = re.compile(r"^#{2,4}\s+.*?(\d{4}-\d{2}-\d{2})")
JIRA_C = re.compile(r"\(Jira comment,\s*(\d{1,2}:\d{2})\)")
BOX = re.compile(r"^(\s*)- \[(.)\]\s+(.*)")


def task_note(vault, rel, comments):
    """Work-log dates, open tasks, and which Jira comments the note does not yet hold."""
    text = (Path(vault) / rel).read_text(encoding="utf-8")
    dates, synced, date = [], set(), None
    in_log = False
    for line in text.splitlines():
        if re.match(r"^##\s+Work.?log", line, re.I):
            in_log = True
        m = DATE_H.match(line) if in_log else None
        if m:
            date = m.group(1)
            if date not in dates:
                dates.append(date)
        c = JIRA_C.search(line) if in_log else None
        if c and date:
            h, mi = c.group(1).split(":")
            synced.add((date, f"{int(h):02d}:{mi}"))
    fm = re.match(r"^---\n(.*?)\n---", text, re.S)
    meta = dict(l.split(":", 1) for l in (fm.group(1).splitlines() if fm else []) if re.match(r"^[\w ]+:", l))
    boxes = [m.groups() for m in map(BOX.match, text.splitlines()) if m]
    missing = []
    for c in comments if isinstance(comments, list) else []:
        d, t = c["at"][:10], c["at"][11:16]
        if (d, t) in synced:
            continue
        # The owner often writes the entry first and posts it to Jira later, so a same-day entry is only "maybe".
        missing.append({"at": c["at"], "by": c["by"], "work_log_has_entry_that_day": d in dates,
                        "start": c["body"][:200]})
    return {"path": rel, "status": meta.get("status", "").strip(), "dateModified": meta.get("dateModified", "").strip(),
            "work_log_dates": dates,
            "open_tasks": [{"mark": m, "text": t[:200]} for _, m, t in boxes if m in " /"][:25],
            "done_task_count": sum(1 for _, m, _ in boxes if m.lower() == "x"),
            "jira_comments_not_in_note": missing}


def standup_entry_range(lines):
    """Index range of the owner's entry: the --entry-heading section of a recorded note, else everything
    after the --hub-link line, else everything after the first H1."""
    heading, hub = CFG["entry_heading"], CFG["hub_link"]
    start = next((i for i, l in enumerate(lines) if heading and l.rstrip() == heading), None)
    if start is not None:
        return start, next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    start = next((i for i, l in enumerate(lines) if hub and hub in l), None)
    if start is None:
        start = next((i for i, l in enumerate(lines) if l.startswith("# ")), None)
    return (start, len(lines)) if start is not None else None


def standup_mentions(vault, key, limit=4, key_re=None):
    """Newest standup notes that name the key, as the top-level bullets that mention it."""
    folder = Path(vault) / CFG["standup_dir"]
    if not folder.exists():
        return []
    entries = []
    for path in sorted(folder.glob("*.md"), reverse=True):
        d = re.match(r"(\d{4}-\d{2}-\d{2}) ", path.name)
        if not d:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        rng = standup_entry_range(lines)
        if rng is None:
            continue
        start, end = rng
        cur, section_name = {"date": d.group(1), "blocks": []}, ""
        entries.append(cur)
        for line in lines[start + 1:end]:
            sec = re.match(r"^###\s+(.*)", line)
            if sec:
                section_name = re.sub(r"<[^>]+>", "", sec.group(1)).strip()
                continue
            if re.match(r"^[-*]\s", line):
                cur["blocks"].append({"section": section_name, "text": line})
            elif cur["blocks"] and line.strip():
                cur["blocks"][-1]["text"] += "\n" + line
    key_re = key_re or re.compile(rf"(?<![A-Z0-9-]){re.escape(key)}(?!\d)")
    out = []
    for e in entries:
        hits = [{"section": b["section"], "text": b["text"][:700]} for b in e["blocks"] if key_re.search(b["text"])]
        if hits:
            out.append({"date": e["date"], "mentions": hits[:6]})
        if len(out) >= limit:
            break
    return out


def local_branches(key, repos):
    """Branches named after the key in local clones, with their checkout state."""
    if not repos:
        raise RuntimeError("no --repos folder given, so local clones were not searched")
    found = []
    for repo in sorted(Path(repos).expanduser().iterdir()):
        if not (repo / ".git").exists():
            continue
        try:
            names = run(["git", "-C", str(repo), "branch", "-a", "--list", f"*{key}*",
                         "--format=%(refname:short)"]).split()
            if not names:
                continue
            found.append({
                "repo": str(repo),
                "current_branch": run(["git", "-C", str(repo), "branch", "--show-current"]).strip(),
                "branches": names,
                "uncommitted": len(run(["git", "-C", str(repo), "status", "--porcelain"]).splitlines()),
                "stashes": [s for s in run(["git", "-C", str(repo), "stash", "list"]).splitlines() if key in s],
            })
        except (RuntimeError, subprocess.TimeoutExpired):
            continue
    return found


# --- project mode -----------------------------------------------------------

PROJECT_ROOTS = {}  # vault-relative folder -> scope; filled from --projects-dir / --linked-projects-dir
H2 = re.compile(r"^##\s+(.*)$")


def parse_fm(text):
    """Frontmatter as a dict of strings and lists. Enough YAML for this vault: scalars, folded
    continuation lines, inline lists, and dash lists."""
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    out, key = {}, None
    for line in (m.group(1).splitlines() if m else []):
        top = re.match(r"^([A-Za-z_][\w \-]*):(.*)$", line)
        if top:
            key, v = top.group(1).strip(), top.group(2).strip()
            if v.startswith("[") and v.endswith("]") and not v.startswith("[["):
                out[key] = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
            else:
                out[key] = v.strip("\"'")
        elif key is not None and line.strip():
            st = line.strip()
            if st.startswith("- "):
                if not isinstance(out[key], list):
                    out[key] = [out[key]] if out[key] else []
                out[key].append(st[2:].strip().strip("\"'"))
            elif isinstance(out[key], str):
                out[key] = (out[key] + " " + st).strip()
    return out


def wiki_target(value):
    m = re.search(r"\[\[([^\]|#]+)", value or "")
    return m.group(1).strip() if m else None


def project_candidates(vault):
    root = Path(vault)
    found = []
    for base, scope in PROJECT_ROOTS.items():
        for p in sorted((root / base).rglob("*.md")) if (root / base).is_dir() else []:
            try:
                fm = parse_fm(p.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
            # Notes in the main projects folder carry type: project or doc. Linked folders may have no
            # consistent schema, so there any note can be the target.
            if scope == "vault" and str(fm.get("type", "")).lower() not in ("project", "doc"):
                continue
            aliases = fm.get("aliases") or []
            names = [p.stem, fm.get("title", "")] + (aliases if isinstance(aliases, list) else [aliases])
            found.append({"path": str(p.relative_to(root)), "type": fm.get("type") or "", "scope": scope,
                          "title": fm.get("title") or p.stem, "status": fm.get("status", ""),
                          "names": [n for n in names if n]})
    return found


def find_project(vault, name):
    import difflib
    want = name.strip().casefold()
    cands = project_candidates(vault)
    exact = [c for c in cands if want in (n.casefold() for n in c["names"])]
    if exact:
        return exact, []
    partial = [c for c in cands if any(want in n.casefold() or n.casefold() in want for n in c["names"])]
    if partial:
        return partial, []
    every = {n: c for c in cands for n in c["names"]}
    close = difflib.get_close_matches(name, list(every), n=5, cutoff=0.5)
    return [], sorted({every[n]["title"] for n in close})


def split_sections(text):
    body = re.sub(r"^---\n.*?\n---\n?", "", text, count=1, flags=re.S)
    secs, cur = {}, "_top"
    for line in body.splitlines():
        h = H2.match(line)
        if h:
            cur = h.group(1).strip()
            secs.setdefault(cur, [])
        else:
            secs.setdefault(cur, []).append(line)
    return secs


def sec(secs, *words):
    for name, lines in secs.items():
        if any(w.lower() in name.lower() for w in words):
            return name, lines
    return None, []


def project_note(vault, rel):
    text = (Path(vault) / rel).read_text(encoding="utf-8")
    fm = parse_fm(text)
    secs = split_sections(text)
    keep = ("type", "status", "category", "kind", "workstream", "summary", "next step", "repo", "started",
            "reviewed", "cadence", "parent project", "aliases", "title")
    tasks, section_name = [], None
    done = 0
    for name, lines in secs.items():
        for l in lines:
            m = BOX.match(l)
            if not m:
                continue
            if m.group(2) in " /":
                tasks.append({"section": name, "mark": m.group(2), "text": m.group(3)[:200]})
            elif m.group(2).lower() == "x":
                done += 1
    def bullets(*words, cap=12):
        _, lines = sec(secs, *words)
        return [l.strip()[:300] for l in lines if re.match(r"^\s*[-*]\s", l) and not BOX.match(l)][:cap]
    _, clog = sec(secs, "Changelog")
    entries, cur = [], None
    for l in clog:
        if re.match(r"^###\s", l):
            cur = {"heading": l.lstrip("# ").strip(), "lines": []}
            entries.append(cur)
        elif cur is not None and l.strip() and len(cur["lines"]) < 6:
            cur["lines"].append(l.strip()[:300])
    _, ver = sec(secs, "Verification")
    overview = " ".join(l.lstrip("> ").strip() for l in secs.get("_top", []) if l.startswith(">") and "[!" not in l)
    return {"path": rel, "frontmatter": {k: fm[k] for k in keep if k in fm}, "overview": overview[:700],
            "open_tasks": tasks[:30], "done_task_count": done,
            "improvement_ideas": bullets("Improvement ideas"), "changelog_newest": entries[:3],
            "verification_text": "\n".join(l for l in ver if l.strip())[:1200],
            "text": text}


def project_parent(vault, fm):
    target = wiki_target(fm.get("parent project", ""))
    if not target:
        return None
    for cand in (f"{target}.md", target):
        if (Path(vault) / cand).is_file():
            n = project_note(vault, cand)
            n.pop("text")
            return {k: n[k] for k in ("path", "frontmatter", "open_tasks", "changelog_newest")}
    return {"error": f"parent project note not found: {target}"}


def project_folder(vault, rel):
    folder = (Path(vault) / rel).parent
    items = []
    for p in sorted(folder.iterdir()):
        if p.name.startswith(".") or p == Path(vault) / rel:
            continue
        if p.suffix == ".md":
            fm = parse_fm(p.read_text(encoding="utf-8"))
            items.append({"name": p.stem, "type": fm.get("type"), "status": fm.get("status"),
                          "next step": fm.get("next step")})
        else:
            items.append({"name": p.name, "type": "file"})
    return items[:40]


def name_regex(names):
    return re.compile("|".join(rf"(?<!\w){re.escape(n)}(?!\w)" for n in names if len(n) > 3), re.I)


def vault_mentions(vault, rel, names):
    rx = name_regex(names)
    root, hits = Path(vault), []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if not fn.endswith(".md"):
                continue
            p = Path(dirpath) / fn
            r = str(p.relative_to(root))
            if r == rel:
                continue
            try:
                if rx.search(p.read_text(encoding="utf-8")):
                    hits.append(r)
            except (OSError, UnicodeDecodeError):
                pass
    return sorted(hits)


def norm_remote(url):
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?/?$", url or "")
    return m.group(1) if m else None


def git(repo, *args):
    return run(["git", "-C", str(repo), *args])


def project_repo(vault, rel, fm, parent_fm, repos, text, scope):

    """Local git state for the project's repo; for the vault itself, only the paths the project owns."""
    remote = norm_remote(fm.get("repo") or (parent_fm or {}).get("repo") or "")
    try:
        vault_remote = norm_remote(git(vault, "remote", "get-url", "origin").strip())
    except (RuntimeError, OSError):
        vault_remote = None
    path = None
    if remote and remote == vault_remote:
        path = Path(vault)
    elif remote and repos:
        for c in sorted(Path(repos).expanduser().iterdir()):
            if (c / ".git").exists():
                try:
                    if norm_remote(git(c, "remote", "get-url", "origin").strip()) == remote:
                        path = c
                        break
                except RuntimeError:
                    pass
    if path is None:
        return {"repo": remote, "local_clone": None}
    owned = None
    if path == Path(vault):
        parent = Path(rel).parent
        owned = [str(parent) if parent.name == Path(rel).stem else rel]
    scope_args = ["--", *owned] if owned else []
    out = {"repo": remote, "local_clone": str(path), "paths_checked": owned,
           "branch": git(path, "branch", "--show-current").strip()}
    try:
        behind, ahead = git(path, "rev-list", "--left-right", "--count", "@{upstream}...HEAD").split()
        out["behind_upstream"], out["ahead_of_upstream"] = int(behind), int(ahead)
    except (RuntimeError, ValueError):
        out["upstream"] = "none"
    status = git(path, "status", "--short", *scope_args).splitlines()
    out["changed_files"] = len(status)
    out["status_short"] = status[:12]
    out["recent_commits"] = git(path, "log", "--format=%h %ci %s", "-8", *scope_args).splitlines()
    out["untracked_owned_paths"] = [l[3:] for l in status if l.startswith("??")][:12]
    return out


def open_prs(remote):
    out = run(["gh", "pr", "list", "--repo", remote, "--author", "@me", "--state", "open", "--json",
               "number,title,url,isDraft,updatedAt,reviewDecision"])
    return json.loads(out)


def project_mode(args):
    vault, name = args.vault, args.target
    matches, closest = find_project(vault, name)
    base = {"mode": "project", "name": name}
    if not matches:
        return {**base, "matches": [], "closest_names": closest}
    if len(matches) > 1:
        return {**base, "ambiguous": True,
                "matches": [{k: m[k] for k in ("path", "type", "scope", "status", "title")} for m in matches]}
    m = matches[0]
    rel, scope = m["path"], m["scope"]
    note = project_note(vault, rel)
    text = note.pop("text")
    fm = note["frontmatter"]
    result = {**base, "scope": scope, "match": {k: m[k] for k in ("path", "type", "scope", "status", "title")},
              "note": note, "parent": section(project_parent, vault, fm),
              "folder": section(project_folder, vault, rel)}
    parent_fm = result["parent"].get("frontmatter") if isinstance(result["parent"], dict) else None
    names = sorted({n for n in m["names"] if len(n) > 3})
    hits = section(vault_mentions, vault, rel, names)
    result["mentions"] = hits[:25] if isinstance(hits, list) else hits
    result["mentions_total"] = len(hits) if isinstance(hits, list) else None
    result["repo"] = section(project_repo, vault, rel, fm, parent_fm, args.repos, text, scope)
    if scope == "linked":
        rx = name_regex(names)
        result["standup"] = section(standup_mentions, vault, "", 4, rx)
        result["task_notes"] = [r for r in hits if r.startswith(CFG["tasks_dir"].rstrip("/") + "/")][:15] if isinstance(hits, list) else []
        remote = result["repo"].get("repo") if isinstance(result["repo"], dict) else None
        result["github_prs"] = section(open_prs, remote) if remote and shutil.which("gh") else []
        result["skipped"] = ["slack: search it with the connector"]
    else:
        result["skipped"] = ["jira", "slack", "github", "task notes", "standup (vault-only project)"]
    return result



def section(fn, *a):
    try:
        return fn(*a)
    except Exception as e:  # noqa: BLE001 - report and carry on
        return {"error": str(e)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", help="a Jira key, or a project name with --project")
    ap.add_argument("--project", action="store_true",
                    help="treat the target as a project note's name or alias, under --projects-dir or --linked-projects-dir")
    ap.add_argument("--vault", default=None, help="vault root (default: $VAULT_ROOT, else search upward)")
    ap.add_argument("--org", default="", help="GitHub org to search (required for the PR section; 'all' searches every repo)")
    ap.add_argument("--repos", default="", help="folder holding local clones (required for branch lookup)")
    ap.add_argument("--jira-site", default="", help="e.g. acme.invalid, used to build issue links")
    ap.add_argument("--tasks-dir", default="Tasks", help="folders.tasks")
    ap.add_argument("--meetings-dir", default="Meetings", help="folders.meetings; standups live in <it>/Recurring/Standup")
    ap.add_argument("--standup-name", default="Standup", help="standup note title after the date")
    ap.add_argument("--hub-link", default="", help="text of the line after which the owner's standup entry starts")
    ap.add_argument("--entry-heading", default="", help="exact H2 line holding the entry in recorded notes")
    ap.add_argument("--projects-dir", default="Projects", help="folders.projects")
    ap.add_argument("--linked-projects-dir", action="append", default=[],
                    help="extra project folder whose notes also get standup, task-note and PR lookups (repeatable)")
    ap.add_argument("--sessions-dir", default="", help="optional folder of imported Claude session notes")
    args = ap.parse_args()
    args.vault = args.vault or find_vault()
    CFG.update(jira_site=args.jira_site, tasks_dir=args.tasks_dir, standup_name=args.standup_name,
               standup_dir=f"{args.meetings_dir}/Recurring/Standup", hub_link=args.hub_link,
               entry_heading=args.entry_heading, sessions_dir=args.sessions_dir)
    PROJECT_ROOTS[args.projects_dir] = "vault"
    for d in args.linked_projects_dir:
        PROJECT_ROOTS[d] = "linked"
    if args.project:
        json.dump(project_mode(args), sys.stdout, indent=1)
        return
    key = args.target.strip().upper()
    if not KEY_RE.match(key):
        sys.exit(f"not a Jira key: {args.target!r}")
    missing = [t for t in ("acli", "gh") if not shutil.which(t)]
    result = {
        "key": key,
        "vault": section(vault_notes, args.vault, key),
        "jira": section(jira, key) if "acli" not in missing else {"error": "acli is not installed"},
        "standup": section(standup_mentions, args.vault, key),
        "github_prs": section(github, key, args.org) if "gh" not in missing else {"error": "gh is not installed"},
        "local_branches": section(local_branches, key, args.repos),
    }
    notes = result["vault"].get("task_notes") if isinstance(result["vault"], dict) else None
    if notes:
        comments = result["jira"].get("comments") if isinstance(result["jira"], dict) else None
        result["task_note"] = section(task_note, args.vault, notes[0], comments)
    json.dump(result, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
