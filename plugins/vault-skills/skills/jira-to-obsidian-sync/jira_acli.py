#!/usr/bin/env python3
"""Read Jira through acli for the sync when no Atlassian connector is connected.

Read-only: it only runs `acli jira workitem search` and `view`, plus GET requests
to the Jira REST API for web links and pull requests. Prints one JSON document to
stdout. An issue that fails holds {"key": ..., "error": ...} so the sync can count
it as failed and keep the watermark behind it.

Usage: jira_acli.py --site acme.invalid search "<JQL>"                      rows, at most 100
       jira_acli.py --site acme.invalid issue KEY [KEY ...] [--no-description]   detail

Settings (flags, never read from the vault config by this script):
  --site         Jira site host, e.g. acme.invalid (or env JIRA_SITE). Required.
  --email        account email for REST calls (or env JIRA_EMAIL, else `git config user.email`).
  JIRA_TOKEN     API token for REST calls (env only). Without it, web links and PRs
                 come back as {"error": ...} and the rest still works.
  --acli         name or path of the acli binary (default: acli).
  --points-field story-points custom field id (default customfield_10028);
  --points-fallback  second id to try (default customfield_10016).

acli search only returns key, summary, and status, so `search` views each match
for `updated`, `parent`, and `resolutiondate`. Descriptions and comments come
back as Markdown via adf.py (next to this file), with the ADF node types it
cannot render listed under `unsupported`.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adf  # noqa: E402  (ADF -> Markdown converter)

LIMIT = 100
ROW_FIELDS = "summary,status,updated,parent,resolutiondate"
GITHUB_APP = "oAuth-com.github.integration.production"  # dev-status applicationType for GitHub PRs

CFG = {"site": None, "email": None, "acli": "acli", "points": "customfield_10028", "fallback": "customfield_10016"}


def rest(path):
    """GET a Jira REST path with JIRA_TOKEN. Raises on failure."""
    email = CFG["email"] or subprocess.run(["git", "config", "user.email"], capture_output=True, text=True).stdout.strip()
    token = os.environ.get("JIRA_TOKEN")
    if not (email and token):
        raise RuntimeError("JIRA_TOKEN or account email not set (use --email / JIRA_EMAIL)")
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    req = urllib.request.Request(f"https://{CFG['site']}{path}", headers={"Authorization": "Basic " + auth})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def extras(key, f):
    """Story points, linked Jiras, web links and PR URLs. A source that fails holds {"error": ...}."""
    points = f.get(CFG["points"])
    out = {"story_points": points if points is not None else f.get(CFG["fallback"])}
    out["related_jiras"] = [{"key": (l.get("outwardIssue") or l.get("inwardIssue"))["key"], "type": l["type"]["name"],
                            "direction": "outward" if l.get("outwardIssue") else "inward"}
                           for l in f.get("issuelinks") or []]
    try:
        out["web_links"] = [{"title": r["object"].get("title"), "url": r["object"]["url"]}
                            for r in rest(f"/rest/api/3/issue/{key}/remotelink")]
    except Exception as e:  # noqa: BLE001
        out["web_links"] = {"error": str(e)}
    try:
        issue_id = rest(f"/rest/api/3/issue/{key}?fields=id")["id"]
        d = rest(f"/rest/dev-status/latest/issue/detail?issueId={issue_id}&applicationType={GITHUB_APP}&dataType=pullrequest")
        out["prs"] = [{"url": p["url"], "status": p["status"]} for x in d.get("detail", []) for p in x.get("pullRequests", [])]
    except Exception as e:  # noqa: BLE001
        out["prs"] = {"error": str(e)}
    return out


def acli(*args):
    try:
        out = subprocess.run([CFG["acli"], "jira", "workitem", *args, "--json"], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise RuntimeError(f"{CFG['acli']} not found; install acli or use the Atlassian connector")
    if out.returncode != 0:
        raise RuntimeError(f"acli {' '.join(args[:2])}: {(out.stderr or out.stdout).strip()[:300]}")
    return json.loads(out.stdout or "null")


def row(key, fields=ROW_FIELDS):
    f = acli("view", key, "--fields", fields)["fields"]
    parent = f.get("parent")
    return f, {
        "key": key,
        "summary": f["summary"],
        "status": f["status"]["name"],
        "status_category": f["status"]["statusCategory"]["name"],
        "updated": f["updated"],
        "resolutiondate": f.get("resolutiondate"),
        "parent": parent and {"key": parent["key"], "summary": parent["fields"]["summary"]},
    }


def md(doc):
    return {"markdown": adf.to_md(doc), "unsupported": adf.unsupported(doc) if isinstance(doc, dict) else []}


def detail(key, description=True):
    fields = f"{ROW_FIELDS},reporter,comment,issuelinks,{CFG['points']},{CFG['fallback']}" + (",description" if description else "")
    f, out = row(key, fields)
    out["reporter"] = (f.get("reporter") or {}).get("displayName")
    out.update(extras(key, f))
    if description:
        out["description"] = md(f.get("description"))
    comment = f.get("comment") or {}
    out["comments"] = [{"author": (c.get("author") or {}).get("displayName"), "created": c["created"], **md(c.get("body"))}
                       for c in comment.get("comments", [])]
    if comment.get("total", 0) > len(out["comments"]):
        out["comments_truncated"] = f"acli returned {len(out['comments'])} of {comment['total']} comments"
    return out


def safe(fn, key):
    try:
        return fn(key)
    except Exception as e:  # noqa: BLE001  (report per issue, don't abort the batch)
        return {"key": key, "error": str(e)}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--site", default=os.environ.get("JIRA_SITE"))
    p.add_argument("--email", default=os.environ.get("JIRA_EMAIL"))
    p.add_argument("--acli", default="acli")
    p.add_argument("--points-field", default="customfield_10028")
    p.add_argument("--points-fallback", default="customfield_10016")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("jql")
    i = sub.add_parser("issue")
    i.add_argument("keys", nargs="+")
    i.add_argument("--no-description", action="store_true")
    a = p.parse_args()
    if not a.site:
        sys.exit("missing --site (or JIRA_SITE): the Jira host, from integrations.jira.site in .vault-skills.yaml")
    CFG.update(site=a.site.removeprefix("https://").rstrip("/"), email=a.email, acli=a.acli,
               points=a.points_field, fallback=a.points_fallback)

    with ThreadPoolExecutor(max_workers=6) as pool:
        if a.cmd == "search":
            try:
                found = acli("search", "--jql", a.jql, "--fields", "key,summary,status", "--limit", str(LIMIT)) or []
            except RuntimeError as e:
                print(json.dumps({"error": str(e)}))
                sys.exit(1)
            keys = [x["key"] for x in found if x]
            issues = list(pool.map(lambda k: safe(lambda k: row(k)[1], k), keys))
            result = {"issues": issues, "hit_limit": len(keys) >= LIMIT}
        else:
            result = {"issues": list(pool.map(lambda k: safe(lambda k: detail(k, not a.no_description), k),
                                              [k.upper() for k in a.keys]))}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
