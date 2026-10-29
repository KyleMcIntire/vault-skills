#!/usr/bin/env python3
"""Collect the new things the owner wrote since the last run, as evidence for learned preferences.

Read-only toward Jira, GitHub, mail and Claude's logs. The only files it writes are its own state
under <vault>/<scratch>/learn-preferences/ (machine-local, not synced or committed). It prints one JSON document to stdout. A source that
fails holds an error and keeps its old watermark, so the next run retries it.

Usage:
  collect.py [--vault V] [--state-dir D] <command> ...
  collect.py status                         watermarks per source, as JSON
  collect.py collect [--days 30] [--sources sessions,github,jira,mail] [--extra slack.json]
                     [--cap 120] [--text-max 500] [--voice-only]
                     [--github-user U --github-org O] [--jira-site S --jira-names "A B,C D"]
                     [--jira-cli acli] [--mail-script PATH] [--claude-projects DIR]
  collect.py voice                          cumulative writing-style stats (emoji, formatting, length)
  collect.py commit                         accept the last collect: advance watermarks, remember ids
  collect.py reset [--source NAME]          forget a source's watermark (or everything)

Deltas: every source has a watermark (the start time of the last good run). A collect asks each
source only for what is newer (minus a one-hour overlap), drops ids already seen, and caps the
count per source oldest-first, so a large backlog drains over several runs. `commit` is a separate
step so a run that dies before the profile is updated loses nothing: nothing advances until then.

Slack is read through the Slack connector by the skill, not here. The skill passes what it found
with --extra, a JSON list of items; passing the file (even an empty list) advances the slack
watermark on commit.

Configuration arrives as flags or environment variables, never from a file and never baked in:
  --vault / VAULT_ROOT / PREFS_VAULT       vault root (default: search upward for .vault-skills.yaml or .obsidian)
  --state-dir / PREFS_STATE_DIR            state folder (default <vault>/<PREFS_SCRATCH or Local>/learn-preferences)
  --github-user / GITHUB_USER              the owner's GitHub login          (github source)
  --github-org  / GITHUB_ORG               org or user whose PRs are read    (github source)
  --jira-site   / JIRA_SITE                e.g. acme.invalid           (jira source)
  --jira-names  / JIRA_NAMES               comma-separated display names the owner appears under in Jira
  --jira-cli    / JIRA_CLI                 CLI binary, default acli
  --mail-script / PREFS_MAIL_SCRIPT        path to a helper that lists and reads sent mail (mail source;
                                           see references/mail-helper-contract.md)
  --claude-projects / PREFS_CLAUDE_PROJECTS  default ~/.claude/projects
A source whose settings are missing reports an error for that source only; the others still run.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path


def find_vault(cli_value=None):
    value = cli_value or os.environ.get("PREFS_VAULT") or os.environ.get("VAULT_ROOT")
    if value:
        return Path(value)
    here = Path.cwd().resolve()
    for marker in (".vault-skills.yaml", ".obsidian"):
        for parent in (here, *here.parents):
            if (parent / marker).exists():
                return parent
    return here


VAULT = find_vault()
STATE_DIR = Path(os.environ.get("PREFS_STATE_DIR") or VAULT / os.environ.get("PREFS_SCRATCH", "Local") / "learn-preferences")
STATE = STATE_DIR / "state.json"
PENDING = STATE_DIR / "pending.json"
MAIL_SCRIPT = os.environ.get("PREFS_MAIL_SCRIPT") or ""
CLAUDE_PROJECTS = Path(os.environ.get("PREFS_CLAUDE_PROJECTS") or Path.home() / ".claude" / "projects")

ME_GITHUB = os.environ.get("GITHUB_USER", "")
GITHUB_OWNER = os.environ.get("GITHUB_ORG", "")
JIRA_SITE = os.environ.get("JIRA_SITE", "")
ME_JIRA_NAMES = {n.strip() for n in os.environ.get("JIRA_NAMES", "").split(",") if n.strip()}
JIRA_CLI = os.environ.get("JIRA_CLI", "acli")
OVERLAP = timedelta(hours=1)
SEEN_KEEP_DAYS = 120
SOURCES = ("sessions", "github", "jira", "mail", "slack")
MIN_CHARS = 10

# Phrases that tend to carry a preference or a correction. A hit only marks the item `strong`;
# the skill still judges every item.
STRONG_RE = re.compile(
    r"\b(don'?t|do not|never|always|prefer|instead|rather|please|stop|shouldn'?t|should|must|"
    r"no[,.!]|nope|wrong|not what|too (long|verbose|much|many)|simpler|keep it|from now on|"
    r"going forward|i (like|want|need|hate|love|don'?t)|can we|why (did|are|is|not)|nit\b|"
    r"i'?d (rather|prefer|like)|make sure|remember)\b", re.I)
SECRET_RE = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|"
    r"ASIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._~+/=-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"(?i:(?:token|secret|password|passwd|api[_-]?key)\s*[:=]\s*\S{8,}))")
# Mail that is machine-made or too personal to learn from.
MAIL_SKIP_RE = re.compile(
    r"^(accepted|declined|tentative|automatic reply|canceled|\[(firing|resolved)\])|"
    r"\b(fmla|ada\b|accommodat|leave request|medical|benefit|payroll|salary|401k|hsa|doctor|"
    r"health|insurance)", re.I)


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s):
    """ISO 8601 with Z, an offset, or a Slack epoch like '1730000000.123' -> aware datetime."""
    if s is None:
        return None
    s = str(s).strip()
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return datetime.fromtimestamp(float(s), timezone.utc)
    s = s.replace("Z", "+00:00")
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def run(cmd, timeout=90):
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if out.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:4])}: {(out.stderr or out.stdout).strip()[:300]}")
    return out.stdout


def redact(text):
    return SECRET_RE.sub("[redacted]", text)


def clean(text, limit):
    text = redact((text or "").replace("\r", "")).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2B06\u2705\u274C\u2764\u203C\u2049\U0001F1E6-\U0001F1FF]\uFE0F?")
SHORTCODE_RE = re.compile(r"(?<![\w/:])(:[a-z0-9_+-]{2,40}:)(?![\w/])")
VOICE_SOURCES = ("slack", "github", "jira", "mail")
VOICE_KEYS = ("n", "chars", "words", "lines", "bullets", "numbered", "bold", "italic", "inline_code",
              "code_blocks", "links", "excl", "question", "lower_start", "period_end", "thanks",
              "please", "mentions", "multi_paragraph", "with_emoji", "headings")


def voice_features(text):
    """Counts that describe how a message is written, from the raw text."""
    t = (text or "").strip()
    body = re.sub(r"```.*?```", "", t, flags=re.S)
    emojis = [e.rstrip("\ufe0f") for e in EMOJI_RE.findall(body)] + SHORTCODE_RE.findall(body)
    lines = [l for l in t.splitlines() if l.strip()]
    f = {"n": 1, "chars": len(t), "words": len(t.split()), "lines": len(lines),
         "bullets": sum(bool(re.match(r"\s*[-*\u2022]\s", l)) for l in lines),
         "numbered": sum(bool(re.match(r"\s*\d+[.)]\s", l)) for l in lines),
         "bold": len(re.findall(r"(?<!\*)\*[^*\s][^*]*\*(?!\*)|\*\*[^*]+\*\*", body)),
         "italic": len(re.findall(r"(?<![\w_])_[^_\s][^_]*_(?![\w_])", body)),
         "inline_code": len(re.findall(r"`[^`\n]+`", body)),
         "code_blocks": t.count("```") // 2,
         "links": len(re.findall(r"https?://|<https?:", body)),
         "excl": body.count("!"), "question": int("?" in body),
         "lower_start": int(bool(re.match(r"[a-z]", t))),
         "period_end": int(t.endswith(".")),
         "thanks": int(bool(re.search(r"\bthank|\bthx\b|\bty\b", body, re.I))),
         "please": int(bool(re.search(r"\bplease\b|\bpls\b", body, re.I))),
         "mentions": len(re.findall(r"<@[A-Z0-9]+>|<!subteam|(?<!\w)@[\w.-]+", body)),
         "multi_paragraph": int("\n\n" in t),
         "with_emoji": int(bool(emojis)),
         "headings": sum(bool(re.match(r"\s*#{1,4}\s", l)) for l in lines)}
    return f, emojis


def merge_voice(total, source, f, emojis):
    d = total.setdefault(source, {k: 0 for k in VOICE_KEYS} | {"emoji": {}})
    for k in VOICE_KEYS:
        d[k] += f[k]
    for e in emojis:
        d["emoji"][e] = d["emoji"].get(e, 0) + 1


def make_id(*parts):
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def item(source, kind, at, where, link, text, id_parts, limit, extra=None):
    strong = bool(STRONG_RE.search(text or ""))
    raw = text or ""
    text = clean(text, limit if strong else min(limit, 300))
    if len(text) < MIN_CHARS:
        return None
    d = {"id": f"{source}:{make_id(*id_parts)}", "source": source, "kind": kind, "at": iso(at),
         "where": where, "link": link, "strong": strong, "text": text}
    if source in VOICE_SOURCES and kind != "pr-description":
        f, emojis = voice_features(redact(raw))
        d["_v"] = (f, emojis)
    if extra:
        d.update(extra)
    return d


# ---------------------------------------------------------------- state

def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"version": 1, "sources": {}, "seen": {}, "runs": []}


def save_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True))
    tmp.replace(STATE)


def since_for(state, source, days, now):
    wm = state["sources"].get(source, {}).get("watermark")
    if wm:
        return parse_ts(wm) - OVERLAP, True
    return now - timedelta(days=days), False


# ---------------------------------------------------------------- sources

def user_text(msg):
    """The text the owner typed, from a Claude Code user message; None for tool results and the like."""
    c = msg.get("content")
    if isinstance(c, list):
        c = "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(c, str) or not c.strip():
        return None
    m = re.search(r"<command-name>/?([^<]+)</command-name>.*?<command-args>(.*?)</command-args>", c, re.S)
    if m:
        c = f"/{m.group(1).strip()} {m.group(2).strip()}"
    if c.lstrip().startswith(("<system-reminder", "<local-command", "[Request interrupted",
                              "Caveat:", "<task-notification", "<bash-", "<command-stdout", "Base directory for this skill")):
        return None
    return c


def collect_sessions(since, text_max):
    out = []
    if not CLAUDE_PROJECTS.is_dir():
        raise RuntimeError(f"{CLAUDE_PROJECTS} not found")
    for proj in sorted(CLAUDE_PROJECTS.iterdir()):
        for f in proj.glob("*.jsonl"):
            if datetime.fromtimestamp(f.stat().st_mtime, timezone.utc) < since:
                continue
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for n, line in enumerate(lines):
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") != "user" or d.get("isMeta") or d.get("isSidechain"):
                    continue
                if (d.get("origin") or {}).get("kind", "human") != "human" or not d.get("timestamp"):
                    continue
                at = parse_ts(d["timestamp"])
                if at < since:
                    continue
                text = user_text(d.get("message") or {})
                if not text:
                    continue
                # Acknowledgements ("yes", "do it") and pasted logs say nothing about preferences,
                # unless they carry directive wording.
                if not STRONG_RE.search(text) and not 30 <= len(text) <= 1500:
                    continue
                home_prefix = str(Path.home()).replace("/", "-").replace("\\", "-").replace(":", "-")
                where = proj.name.replace(home_prefix, "~", 1)[-60:]
                it = item("sessions", "claude-message", at, where, f"claude --resume {f.stem}",
                          text, (f.stem, n), text_max, {"first_of_session": n < 3})
                if it:
                    out.append(it)
    return out


def gh_json(args):
    return json.loads(run(["gh", *args]) or "[]")


def collect_github(since, text_max):
    if not ME_GITHUB or not GITHUB_OWNER:
        raise RuntimeError("github source needs --github-user and --github-org (or GITHUB_USER, GITHUB_ORG)")
    if not shutil.which("gh"):
        raise RuntimeError("gh CLI not on PATH")
    day = since.strftime("%Y-%m-%d")
    prs = {}
    for flag in ("--author", "--commenter", "--reviewed-by"):
        try:
            found = gh_json(["search", "prs", flag, ME_GITHUB, "--owner", GITHUB_OWNER, "--updated", f">={day}",
                             "--limit", "60", "--json", "number,repository,title,url,body,createdAt,author"])
        except RuntimeError as e:
            raise RuntimeError(f"gh search prs {flag}: {e}")
        for p in found:
            prs[p["url"]] = p
    out = []
    ts = iso(since)

    def one(p):
        repo = p["repository"]["nameWithOwner"]
        n = p["number"]
        res = []
        where = f"{repo}#{n}"
        if (p.get("author") or {}).get("login") == ME_GITHUB and parse_ts(p["createdAt"]) >= since:
            it = item("github", "pr-description", parse_ts(p["createdAt"]), where, p["url"],
                      f"{p['title']}\n\n{p.get('body') or ''}", (p["url"], "body"), text_max)
            if it:
                res.append(it)
        for kind, path in (("review-comment", f"repos/{repo}/pulls/{n}/comments"),
                           ("pr-comment", f"repos/{repo}/issues/{n}/comments")):
            rows = json.loads(run(["gh", "api", "--paginate", f"{path}?since={ts}&per_page=100", "--jq",
                                   f'[.[] | select(.user.login == "{ME_GITHUB}") | '
                                   '{id, body, created_at, html_url, path}]']).replace("]\n[", ",").strip() or "[]")
            for r in rows:
                at = parse_ts(r["created_at"])
                if at < since:
                    continue
                it = item("github", kind, at, where + (f" {r['path']}" if r.get("path") else ""),
                          r["html_url"], r["body"], (kind, r["id"]), text_max)
                if it:
                    res.append(it)
        reviews = json.loads(run(["gh", "api", "--paginate", f"repos/{repo}/pulls/{n}/reviews?per_page=100",
                                  "--jq", f'[.[] | select(.user.login == "{ME_GITHUB}") | '
                                  '{id, body, state, submitted_at, html_url}]']).replace("]\n[", ",").strip() or "[]")
        for r in reviews:
            if not r.get("submitted_at") or parse_ts(r["submitted_at"]) < since:
                continue
            it = item("github", f"review-{r['state'].lower()}", parse_ts(r["submitted_at"]), where,
                      r["html_url"], r["body"] or "", ("review", r["id"]), text_max)
            if it:
                res.append(it)
        return res

    errors = []
    with ThreadPoolExecutor(6) as pool:
        for fut in [pool.submit(one, p) for p in prs.values()]:
            try:
                out.extend(fut.result())
            except Exception as e:  # one bad PR must not hide the rest
                errors.append(str(e)[:200])
    if errors and not out:
        raise RuntimeError(f"all {len(errors)} PR lookups failed, first: {errors[0]}")
    return out


def adf_to_md(node):
    """Minimal Atlassian Document Format to plain Markdown-ish text (enough for judging wording)."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_to_md(n) for n in node)
    t = node.get("type")
    kids = adf_to_md(node.get("content"))
    if t == "text":
        text = node.get("text", "")
        marks = {m.get("type") for m in node.get("marks", [])}
        return f"`{text}`" if "code" in marks else text
    if t == "hardBreak":
        return "\n"
    if t in ("paragraph", "heading"):
        return kids + "\n\n"
    if t == "listItem":
        return "- " + kids.strip() + "\n"
    if t == "codeBlock":
        return "```\n" + kids + "\n```\n\n"
    if t in ("mention", "emoji", "inlineCard"):
        a = node.get("attrs", {})
        return a.get("text") or a.get("shortName") or a.get("url") or ""
    return kids


def collect_jira(since, text_max):
    if not JIRA_SITE or not ME_JIRA_NAMES:
        raise RuntimeError("jira source needs --jira-site and --jira-names (or JIRA_SITE, JIRA_NAMES)")
    if not shutil.which(JIRA_CLI):
        raise RuntimeError(f"{JIRA_CLI} not on PATH")
    adf = type("adf", (), {"to_md": staticmethod(adf_to_md)})
    stamp = since.astimezone().strftime("%Y-%m-%d %H:%M")
    out = []

    def acli(*args):
        return json.loads(run([JIRA_CLI, "jira", "workitem", *args, "--json"]) or "[]")

    keys = {}
    # JQL has no "commented by me"; Jira auto-watches an issue once you comment, so watcher covers it.
    for jql in (f'updated >= "{stamp}" AND (watcher = currentUser() OR assignee = currentUser())',
                f'reporter = currentUser() AND created >= "{stamp}"'):
        for i in acli("search", "--jql", jql, "--fields", "key,summary", "--limit", "60"):
            keys[i["key"]] = i["fields"]["summary"]

    def one(key):
        f = acli("view", key, "--fields", "summary,description,comment,reporter,created")["fields"]
        res = []
        url = f"https://{JIRA_SITE}/browse/{key}"
        for c in (f.get("comment") or {}).get("comments", []):
            who = (c.get("author") or {}).get("displayName")
            at = parse_ts(c["created"])
            if who in ME_JIRA_NAMES and at >= since:
                it = item("jira", "comment", at, key, f"{url}?focusedCommentId={c.get('id')}",
                          adf.to_md(c.get("body")), (key, c.get("id")), text_max)
                if it:
                    res.append(it)
        if (f.get("reporter") or {}).get("displayName") in ME_JIRA_NAMES and parse_ts(f["created"]) >= since:
            it = item("jira", "issue-description", parse_ts(f["created"]), key, url,
                      f"{f['summary']}\n\n{adf.to_md(f.get('description')) if f.get('description') else ''}",
                      (key, "desc"), text_max)
            if it:
                res.append(it)
        return res

    errors = []
    with ThreadPoolExecutor(4) as pool:
        for fut in [pool.submit(one, k) for k in keys]:
            try:
                out.extend(fut.result())
            except Exception as e:
                errors.append(str(e)[:200])
    if errors and not out:
        raise RuntimeError(f"all {len(errors)} issue lookups failed, first: {errors[0]}")
    return out


def strip_quoted(body):
    """Cut a reply at the start of the quoted thread."""
    parts = re.split(r"(?m)^(?:From:|-{3,}\s*Original Message|On .{5,120} wrote:|_{5,})", body, maxsplit=1)
    return parts[0]


def collect_mail(since, text_max):
    if not MAIL_SCRIPT or not Path(MAIL_SCRIPT).exists():
        raise RuntimeError("mail source needs --mail-script (or PREFS_MAIL_SCRIPT); see references/mail-helper-contract.md")
    cmd = [sys.executable, "-I", str(MAIL_SCRIPT)]
    listing = json.loads(run(cmd + ["mail", "--mailbox", "Sent Items", "--since",
                                    since.astimezone().strftime("%Y-%m-%d"), "--limit", "60"]))
    out = []
    for m in listing.get("messages", []):
        at = parse_ts(m["received"])
        if at < since or MAIL_SKIP_RE.search(m["subject"] or ""):
            continue
        body = json.loads(run(cmd + ["message", str(m["message_id"]), "--max-chars", "4000"]))
        text = strip_quoted(body.get("body") or body.get("text") or "")
        # Do not record who it went to or what it was about; the subject is enough context.
        it = item("mail", "sent-mail", at, m["subject"][:80], m.get("outlook_link"), text,
                  (m["message_id"],), text_max)
        if it:
            out.append(it)
    return out


COLLECTORS = {"sessions": collect_sessions, "github": collect_github, "jira": collect_jira, "mail": collect_mail}


# ---------------------------------------------------------------- commands

def cmd_status(args):
    state = load_state()
    print(json.dumps({"now": iso(now_utc()), "sources": state["sources"], "seen": len(state["seen"]),
                      "last_runs": state["runs"][-3:]}, indent=1))


def cmd_collect(args):
    state = load_state()
    now = now_utc()
    if args.sources is None:  # default: sessions, plus every source that has its settings
        configured = {"sessions": True, "github": bool(ME_GITHUB and GITHUB_OWNER),
                      "jira": bool(JIRA_SITE and ME_JIRA_NAMES), "mail": bool(MAIL_SCRIPT)}
        args.sources = ",".join(s for s, ok in configured.items() if ok)
    wanted = [s for s in args.sources.split(",") if s]
    if args.voice_only:
        wanted = [s for s in wanted if s in VOICE_SOURCES]
    result = {"run_id": make_id(iso(now)), "started": iso(now), "sources": {}, "items": []}
    pending = {"run_id": result["run_id"], "started": iso(now), "sources": {}, "ids": []}
    extra = None
    if args.extra:
        extra = json.loads(Path(args.extra).read_text())
        wanted = [s for s in wanted if s != "slack"] + ["slack"]
    for src in wanted:
        since, has_wm = since_for(state, src, args.days, now)
        if args.voice_only:
            since, has_wm = now - timedelta(days=args.days), False
        info = {"since": iso(since), "first_run": not has_wm}
        try:
            if src == "slack":
                items = []
                for e in extra or []:
                    at = parse_ts(e.get("at") or now)
                    it = item("slack", e.get("kind", "message"), at, e.get("where", ""), e.get("link"),
                              e.get("text", ""), (e.get("link") or e.get("text", "")[:80],), args.text_max)
                    if it and at >= since:
                        items.append(it)
            else:
                items = COLLECTORS[src](since, args.text_max)
            items.sort(key=lambda i: i["at"])
            fresh = [i for i in items if args.voice_only or i["id"] not in state["seen"]]
            info.update(found=len(items), new=len(fresh))
            wm = iso(now)
            if len(fresh) > args.cap:
                info["capped"] = len(fresh) - args.cap
                fresh = fresh[:args.cap]
                wm = fresh[-1]["at"]  # resume just after the last one kept
            if not args.voice_only:
                pending["sources"][src] = wm
            result["items"].extend(fresh)
        except Exception as e:
            info["error"] = str(e)[:400]
        result["sources"][src] = info
    voice = {}
    for i in result["items"]:
        fe = i.pop("_v", None)
        if fe:
            merge_voice(voice, i["source"], *fe)
    pending["voice"] = voice
    result["voice_delta"] = {k: {"messages": v["n"], "top_emoji": sorted(v["emoji"].items(), key=lambda x: -x[1])[:8]}
                             for k, v in voice.items()}
    pending["ids"] = [] if args.voice_only else [i["id"] for i in result["items"]]
    if args.voice_only:
        result["items"] = []  # style numbers only; nothing for the preference judge to re-read
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PENDING.write_text(json.dumps(pending))
    result["counts"] = {"total": len(result["items"]),
                        "strong": sum(i["strong"] for i in result["items"])}
    print(json.dumps(result, indent=1, ensure_ascii=False))


def cmd_commit(args):
    if not PENDING.exists():
        sys.exit("nothing pending: run collect first")
    pending = json.loads(PENDING.read_text())
    state = load_state()
    today = now_utc().strftime("%Y-%m-%d")
    for src, wm in pending["sources"].items():
        state["sources"][src] = {"watermark": wm, "last_run": pending["started"]}
    for i in pending["ids"]:
        state["seen"][i] = today
    for src, v in pending.get("voice", {}).items():
        merge_voice(state.setdefault("voice", {}), src, {k: v[k] for k in VOICE_KEYS}, [])
        for e, n in v["emoji"].items():
            state["voice"][src]["emoji"][e] = state["voice"][src]["emoji"].get(e, 0) + n
    cutoff = (now_utc() - timedelta(days=SEEN_KEEP_DAYS)).strftime("%Y-%m-%d")
    state["seen"] = {k: v for k, v in state["seen"].items() if v >= cutoff}
    state["runs"] = (state["runs"] + [{"run_id": pending["run_id"], "at": pending["started"],
                                       "items": len(pending["ids"]),
                                       "sources": sorted(pending["sources"])}])[-30:]
    save_state(state)
    PENDING.unlink()
    print(json.dumps({"committed": pending["run_id"], "items": len(pending["ids"]),
                      "sources": pending["sources"]}))


def cmd_voice(args):
    """Cumulative style numbers per source, as per-message rates, for the Voice and Style note."""
    out = {}
    for src, v in load_state().get("voice", {}).items():
        n = max(v["n"], 1)
        out[src] = {"messages": v["n"], "avg_words": round(v["words"] / n, 1),
                    "avg_lines": round(v["lines"] / n, 1),
                    "pct": {k: round(100 * v[k] / n) for k in (
                        "with_emoji", "multi_paragraph", "lower_start", "period_end", "question", "thanks",
                        "please")},
                    "per_message": {k: round(v[k] / n, 2) for k in (
                        "bullets", "bold", "italic", "inline_code", "code_blocks", "links", "excl", "mentions",
                        "headings", "numbered")},
                    "emoji": sorted(v["emoji"].items(), key=lambda x: -x[1])[:25]}
    print(json.dumps(out, indent=1, ensure_ascii=False))


def cmd_reset(args):
    state = load_state()
    if args.source:
        state["sources"].pop(args.source, None)
    else:
        state = {"version": 1, "sources": {}, "seen": {}, "runs": []}
    save_state(state)
    print("reset", args.source or "everything")


def apply_config(args):
    global VAULT, STATE_DIR, STATE, PENDING, ME_GITHUB, GITHUB_OWNER, JIRA_SITE, ME_JIRA_NAMES
    global JIRA_CLI, MAIL_SCRIPT, CLAUDE_PROJECTS
    if args.vault:
        VAULT = find_vault(args.vault)
        STATE_DIR = Path(os.environ.get("PREFS_STATE_DIR") or VAULT / os.environ.get("PREFS_SCRATCH", "Local")
                         / "learn-preferences")
    if args.state_dir:
        STATE_DIR = Path(args.state_dir)
    STATE, PENDING = STATE_DIR / "state.json", STATE_DIR / "pending.json"
    ME_GITHUB = getattr(args, "github_user", None) or ME_GITHUB
    GITHUB_OWNER = getattr(args, "github_org", None) or GITHUB_OWNER
    JIRA_SITE = getattr(args, "jira_site", None) or JIRA_SITE
    if getattr(args, "jira_names", None):
        ME_JIRA_NAMES = {n.strip() for n in args.jira_names.split(",") if n.strip()}
    JIRA_CLI = getattr(args, "jira_cli", None) or JIRA_CLI
    MAIL_SCRIPT = getattr(args, "mail_script", None) or MAIL_SCRIPT
    if getattr(args, "claude_projects", None):
        CLAUDE_PROJECTS = Path(args.claude_projects)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", help="vault root (default: $VAULT_ROOT, else search upward)")
    ap.add_argument("--state-dir", help="state folder (default <vault>/Local/learn-preferences)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    c = sub.add_parser("collect")
    c.add_argument("--days", type=int, default=30, help="look-back for a source with no watermark")
    c.add_argument("--sources", default=None,
                   help="comma list of sessions,github,jira,mail (default: sessions plus every configured source)")
    c.add_argument("--github-user")
    c.add_argument("--github-org")
    c.add_argument("--jira-site")
    c.add_argument("--jira-names", help="comma-separated display names the owner appears under in Jira")
    c.add_argument("--jira-cli")
    c.add_argument("--mail-script")
    c.add_argument("--claude-projects")
    c.add_argument("--extra", help="JSON list of Slack items found by the skill")
    c.add_argument("--cap", type=int, default=120, help="max new items per source per run")
    c.add_argument("--voice-only", action="store_true",
                   help="one-off backfill: ignore watermarks and seen ids, record writing-style stats only")
    c.add_argument("--text-max", type=int, default=500)
    c.set_defaults(fn=cmd_collect)
    sub.add_parser("commit").set_defaults(fn=cmd_commit)
    sub.add_parser("voice").set_defaults(fn=cmd_voice)
    r = sub.add_parser("reset")
    r.add_argument("--source", choices=SOURCES)
    r.set_defaults(fn=cmd_reset)
    args = ap.parse_args(argv)
    apply_config(args)
    args.fn(args)


if __name__ == "__main__":
    main()
