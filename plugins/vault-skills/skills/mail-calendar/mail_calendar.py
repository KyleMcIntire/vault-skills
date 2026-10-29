#!/usr/bin/env python3
"""Read a work calendar and mail from the macOS Calendar and Mail stores (Mac only).

An Exchange (or similar) account added in macOS Internet Accounts is synced by
Calendar.app and Mail.app, which keep local copies. This reads their SQLite stores and message files
read-only and prints one JSON document. It never writes, sends, or marks mail
read.

  mail_calendar.py [global flags] meetings [--day today|tomorrow|YYYY-MM-DD] [--days N] [--search TEXT]
  mail_calendar.py [global flags] meeting EVENT_ID
  mail_calendar.py [global flags] mail [--search TEXT] [--sender TEXT] [--mailbox NAME] [--since DATE] [--limit N]
  mail_calendar.py [global flags] message MESSAGE_ID [--max-chars N]

Global flags (before the subcommand), each with an environment fallback:
  --account-store NAME   Calendar.app account (store) name, default "Exchange"   (MAILCAL_STORE)
  --calendar NAME        calendar inside that store, default "Calendar"           (MAILCAL_CALENDAR)
  --mail-url-prefix P    mailbox URL scheme of the account, default "ews://"      (MAILCAL_MAIL_PREFIX)
  --web-base URL         web mail base for outlook_link, e.g. https://outlook.office365.com/owa/
                         (MAILCAL_WEB_BASE); links are omitted when not given
  --join-hosts REGEX     extra host patterns that count as meeting join links    (MAILCAL_JOIN_HOSTS)
  --calendar-db PATH, --mail-root PATH   override the store locations (for tests)

The stores are Apple's private schemas, so a macOS update can change them.
"""

from __future__ import annotations

import argparse
import datetime as dt
import email
import email.policy
import html
import json
import os
import re
import sqlite3
import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

HOME = Path.home()
CALENDAR_DB = HOME / "Library/Group Containers/group.com.apple.calendar/Calendar.sqlitedb"
MAIL_ROOT = None  # resolved in configure(): newest ~/Library/Mail/V* folder
MAIL_DB = None

# Calendar dates are Core Data timestamps: seconds since 2001-01-01 UTC.
CORE_DATA_EPOCH = 978307200
CALENDAR_STORE = "Exchange"
CALENDAR_TITLE = "Calendar"
MAIL_PREFIX = "ews://"
WEB_BASE = ""
JOIN_HOSTS = r"zoom\.us/j/|teams\.microsoft\.com/|meet\.google\.com/|webex\.com/"

# Participant.status in Calendar's store. Inferred from the account owner's own
# rows: 1 for most meetings, 3 where Exchange also shows tentative free/busy,
# 7 for invitations still awaiting a reply.
RESPONSE = {
    0: "unknown",
    1: "accepted",
    2: "declined",
    3: "tentative",
    4: "delegated",
    5: "completed",
    6: "in process",
    7: "no response",
}
ORGANIZER_ENTITY = 8
# CalendarItem.status 3 is EKEventStatusCanceled.
CANCELED = 3
RECIPIENT_TYPES = {0: "to", 1: "cc", 2: "bcc"}
# Outlook on the web opens an item from its Exchange (EWS) item ID, which both
# stores keep: CalendarItem.external_id and messages.remote_id.


def configure(args: argparse.Namespace) -> None:
    global CALENDAR_DB, MAIL_ROOT, MAIL_DB, CALENDAR_STORE, CALENDAR_TITLE, MAIL_PREFIX, WEB_BASE, JOIN_HOSTS
    CALENDAR_STORE = args.account_store
    CALENDAR_TITLE = args.calendar
    MAIL_PREFIX = args.mail_url_prefix
    WEB_BASE = args.web_base or ""
    if args.join_hosts:
        JOIN_HOSTS = JOIN_HOSTS + "|" + args.join_hosts
    if args.calendar_db:
        CALENDAR_DB = Path(args.calendar_db)
    if args.mail_root:
        MAIL_ROOT = Path(args.mail_root)
    else:
        versions = sorted((HOME / "Library/Mail").glob("V*"), key=lambda p: p.name)
        MAIL_ROOT = versions[-1] if versions else HOME / "Library/Mail/V10"
    MAIL_DB = MAIL_ROOT / "MailData/Envelope Index"


def connect(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(f"not found: {path}")
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def local_time(seconds: float) -> dt.datetime:
    # astimezone() picks the offset in force at that moment, so times across a DST
    # change keep their wall-clock hour; today's fixed offset would shift them.
    return dt.datetime.fromtimestamp(seconds).astimezone()


def from_core_data(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    return local_time(seconds + CORE_DATA_EPOCH).isoformat(timespec="minutes")


def to_core_data(moment: dt.datetime) -> float:
    return moment.timestamp() - CORE_DATA_EPOCH


def from_unix(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    return local_time(seconds).isoformat(timespec="minutes")


def parse_day(text: str) -> dt.date:
    today = dt.date.today()
    named = {"today": today, "tomorrow": today + dt.timedelta(days=1), "yesterday": today - dt.timedelta(days=1)}
    if text.lower() in named:
        return named[text.lower()]
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise SystemExit(f"not a date: {text!r} (use today, tomorrow, yesterday, or YYYY-MM-DD)")


def start_of(day: dt.date) -> dt.datetime:
    return dt.datetime.combine(day, dt.time.min).astimezone()


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# --- Calendar ---------------------------------------------------------------


def work_calendar_ids(con: sqlite3.Connection, all_calendars: bool) -> list[int]:
    rows = con.execute(
        "select c.ROWID, c.title from Calendar c join Store s on s.ROWID = c.store_id where s.name = ?",
        (CALENDAR_STORE,),
    ).fetchall()
    ids = [r["ROWID"] for r in rows if all_calendars or r["title"] == CALENDAR_TITLE]
    if not ids:
        raise SystemExit(f"no '{CALENDAR_TITLE}' calendar in the '{CALENDAR_STORE}' store; check the account name (--account-store) and that it is still in Internet Accounts")
    return ids


def identity_name(con: sqlite3.Connection, identity_id: int | None) -> str | None:
    if not identity_id:
        return None
    row = con.execute("select display_name from Identity where ROWID = ?", (identity_id,)).fetchone()
    return row["display_name"] if row and row["display_name"] else None


def participants(con: sqlite3.Connection, item: sqlite3.Row) -> tuple[dict | None, list[dict], str | None]:
    organizer, attendees, mine = None, [], None
    for p in con.execute("select * from Participant where owner_id = ? order by ROWID", (item["ROWID"],)):
        person = {
            "name": identity_name(con, p["identity_id"]),
            "email": (p["email"] or "").removeprefix("mailto:") or None,
        }
        if p["entity_type"] == ORGANIZER_ENTITY:
            organizer = person
            continue
        person["response"] = RESPONSE.get(p["status"], f"code {p['status']}")
        attendees.append(person)
        if p["ROWID"] == item["self_attendee_id"]:
            mine = person["response"]
    return organizer, attendees, mine


def location(con: sqlite3.Connection, location_id: int | None) -> str | None:
    if not location_id:
        return None
    row = con.execute("select title from Location where ROWID = ?", (location_id,)).fetchone()
    return row["title"] if row else None


def join_link(item: sqlite3.Row, where: str | None) -> str | None:
    if item["conference_url"]:
        return item["conference_url"]
    for text in (where or "", item["description"] or ""):
        match = re.search(r"https://[\w.-]*(" + JOIN_HOSTS + r")\S+", text)
        if match:
            return match.group(0).rstrip(">)")
    return None


def outlook_link(item_id: str | None, kind: str) -> str | None:
    if not item_id or not WEB_BASE:
        return None
    view = "path=/calendar/item" if kind == "calendar" else "viewmodel=ReadMessageItem"
    return f"{WEB_BASE}?itemid={urllib.parse.quote(item_id, safe='')}&exvsurl=1&{view}"


def is_canceled(item: sqlite3.Row) -> bool:
    return item["status"] == CANCELED or (item["summary"] or "").startswith("Canceled:")


def cmd_meetings(args: argparse.Namespace) -> dict:
    con = connect(CALENDAR_DB)
    ids = work_calendar_ids(con, args.all_calendars)
    first = parse_day(args.day)
    lo, hi = start_of(first), start_of(first + dt.timedelta(days=args.days))
    marks = ",".join("?" * len(ids))
    sql = f"""
        select o.occurrence_date, i.*
        from OccurrenceCache o join CalendarItem i on i.ROWID = o.event_id
        where o.calendar_id in ({marks}) and o.occurrence_date >= ? and o.occurrence_date < ?
        order by o.occurrence_date, i.summary"""
    meetings = []
    for item in con.execute(sql, (*ids, to_core_data(lo), to_core_data(hi))):
        if args.search and args.search.lower() not in (item["summary"] or "").lower():
            continue
        if not args.include_canceled and is_canceled(item):
            continue
        organizer, attendees, mine = participants(con, item)
        if not args.include_declined and mine == "declined":
            continue
        start = item["occurrence_date"]
        where = location(con, item["location_id"])
        meetings.append({
            "event_id": item["ROWID"],
            "title": item["summary"],
            "start": from_core_data(start),
            "end": from_core_data(start + (item["end_date"] - item["start_date"])),
            "all_day": bool(item["all_day"]),
            "location": where,
            "join_link": join_link(item, where),
            "outlook_link": outlook_link(item["external_id"], "calendar"),
            "organizer": organizer,
            "my_response": mine,
            "attendee_count": len(attendees),
            "recurring": bool(item["has_recurrences"] or item["orig_item_id"]),
            "canceled": is_canceled(item),
        })
    return {"from": lo.date().isoformat(), "to": (hi.date() - dt.timedelta(days=1)).isoformat(), "count": len(meetings), "meetings": meetings}


def cmd_meeting(args: argparse.Namespace) -> dict:
    con = connect(CALENDAR_DB)
    item = con.execute("select * from CalendarItem where ROWID = ?", (args.event_id,)).fetchone()
    if not item:
        raise SystemExit(f"no calendar item {args.event_id}")
    organizer, attendees, mine = participants(con, item)
    where = location(con, item["location_id"])
    upcoming = [
        from_core_data(r["occurrence_date"])
        for r in con.execute(
            "select occurrence_date from OccurrenceCache where event_id = ? and occurrence_date >= ? order by occurrence_date limit 5",
            (item["ROWID"], to_core_data(start_of(dt.date.today()))),
        )
    ]
    return {
        "event_id": item["ROWID"],
        "title": item["summary"],
        "start": from_core_data(item["start_date"]),
        "end": from_core_data(item["end_date"]),
        "all_day": bool(item["all_day"]),
        "location": where,
        "join_link": join_link(item, where),
        "outlook_link": outlook_link(item["external_id"], "calendar"),
        "organizer": organizer,
        "my_response": mine,
        "recurring": bool(item["has_recurrences"]),
        "series_event_id": item["orig_item_id"] or None,
        "upcoming_occurrences": upcoming,
        "canceled": is_canceled(item),
        "attendees": attendees,
        "notes": clean_text(item["description"]),
    }


# --- Mail -------------------------------------------------------------------


def mailbox_name(url: str) -> str:
    return urllib.parse.unquote(url.split("/", 3)[3]) if url.count("/") >= 3 else url


def cmd_mail(args: argparse.Namespace) -> dict:
    con = connect(MAIL_DB)
    where = ["m.deleted = 0", "mb.url like ?"]
    params: list = [MAIL_PREFIX + "%"]
    if args.search:
        where.append("s.subject like ?")
        params.append(f"%{args.search}%")
    if args.sender:
        where.append("(a.address like ? or a.comment like ?)")
        params += [f"%{args.sender}%"] * 2
    if args.mailbox:
        where.append("mb.url like ?")
        params.append(f"%/{urllib.parse.quote(args.mailbox)}")
    if args.since:
        where.append("m.date_received >= ?")
        params.append(int(start_of(parse_day(args.since)).timestamp()))
    if args.until:
        where.append("m.date_received < ?")
        params.append(int(start_of(parse_day(args.until) + dt.timedelta(days=1)).timestamp()))
    if args.unread:
        where.append("m.read = 0")
    sql = f"""
        select m.ROWID, m.remote_id, m.date_received, m.read, m.flagged, a.address, a.comment,
               coalesce(m.subject_prefix, '') || s.subject as subject, mb.url, sm.summary
        from messages m
        join subjects s on s.ROWID = m.subject
        join mailboxes mb on mb.ROWID = m.mailbox
        left join addresses a on a.ROWID = m.sender
        left join summaries sm on sm.ROWID = m.summary
        where {' and '.join(where)}
        order by m.date_received desc limit ?"""
    messages = [
        {
            "message_id": r["ROWID"],
            "received": from_unix(r["date_received"]),
            "from": f"{r['comment']} <{r['address']}>" if r["comment"] else r["address"],
            "subject": r["subject"],
            "mailbox": mailbox_name(r["url"]),
            "read": bool(r["read"]),
            "flagged": bool(r["flagged"]),
            "snippet": clean_text(r["summary"])[:200] or None,
            "outlook_link": outlook_link(r["remote_id"], "mail"),
        }
        for r in con.execute(sql, (*params, args.limit))
    ]
    return {"count": len(messages), "messages": messages}


def emlx_path(url: str, rowid: int) -> Path | None:
    """Find a message's .emlx file from its mailbox URL and ROWID.

    Mail files message 119868 under <account>/<mailbox>.mbox/<uuid>/Data/9/1/1/Messages/:
    the digits of ROWID // 1000, reversed, one directory each.
    """
    account, _, folder = url.removeprefix(MAIL_PREFIX).partition("/")
    mbox = MAIL_ROOT / account / "/".join(f"{part}.mbox" for part in urllib.parse.unquote(folder).split("/"))
    shard = "/".join(reversed(str(rowid // 1000))) if rowid >= 1000 else ""
    for store in mbox.glob("*/Data"):
        for name in (f"{rowid}.emlx", f"{rowid}.partial.emlx"):
            candidate = store / shard / "Messages" / name
            if candidate.exists():
                return candidate
    return None


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "head"):
            self.skip += 1
        elif tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script", "head") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(markup: str) -> str:
    parser = _TextExtractor()
    parser.feed(markup)
    text = html.unescape("".join(parser.parts))
    return re.sub(r"[ \t\xa0]+\n", "\n", re.sub(r"[ \t\xa0]{2,}", " ", text))


def read_emlx(path: Path) -> email.message.EmailMessage:
    raw = path.read_bytes()
    length, _, rest = raw.partition(b"\n")
    return email.message_from_bytes(rest[: int(length.strip())], policy=email.policy.default)


def cmd_message(args: argparse.Namespace) -> dict:
    con = connect(MAIL_DB)
    row = con.execute(
        """select m.ROWID, m.remote_id, m.date_received, mb.url, coalesce(m.subject_prefix, '') || s.subject as subject
           from messages m join mailboxes mb on mb.ROWID = m.mailbox join subjects s on s.ROWID = m.subject
           where m.ROWID = ?""",
        (args.message_id,),
    ).fetchone()
    if not row:
        raise SystemExit(f"no message {args.message_id}")
    if not row["url"].startswith(MAIL_PREFIX):
        raise SystemExit(f"message {args.message_id} is not in the configured mail account (--mail-url-prefix {MAIL_PREFIX})")
    recipients: dict[str, list[str]] = {}
    for r in con.execute(
        "select r.type, a.address, a.comment from recipients r join addresses a on a.ROWID = r.address where r.message = ? order by r.type, r.position",
        (row["ROWID"],),
    ):
        label = RECIPIENT_TYPES.get(r["type"], f"type {r['type']}")
        recipients.setdefault(label, []).append(f"{r['comment']} <{r['address']}>" if r["comment"] else r["address"])
    result = {
        "message_id": row["ROWID"],
        "received": from_unix(row["date_received"]),
        "subject": row["subject"],
        "mailbox": mailbox_name(row["url"]),
        "outlook_link": outlook_link(row["remote_id"], "mail"),
        **recipients,
    }
    path = emlx_path(row["url"], row["ROWID"])
    if not path:
        result["body_error"] = "message file not downloaded; open the message in Mail.app once, then retry"
        return result
    msg = read_emlx(path)
    result["from"] = str(msg["From"] or "")
    result["date"] = str(msg["Date"] or "")
    part = msg.get_body(preferencelist=("plain", "html"))
    body = ""
    if part is not None:
        body = part.get_content()
        if part.get_content_type() == "text/html":
            body = html_to_text(body)
    body = clean_text(body)
    result["attachments"] = [a.get_filename() for a in msg.iter_attachments() if a.get_filename()]
    result["partial"] = path.name.endswith(".partial.emlx")
    result["truncated"] = len(body) > args.max_chars
    result["body"] = body[: args.max_chars]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read a work calendar and mail from macOS stores (read-only, Mac only).")
    env = os.environ.get
    parser.add_argument("--account-store", default=env("MAILCAL_STORE", "Exchange"), help="Calendar.app account (store) name")
    parser.add_argument("--calendar", default=env("MAILCAL_CALENDAR", "Calendar"), help="calendar name inside the store")
    parser.add_argument("--mail-url-prefix", default=env("MAILCAL_MAIL_PREFIX", "ews://"), help="mailbox URL scheme of the account")
    parser.add_argument("--web-base", default=env("MAILCAL_WEB_BASE"), help="web mail base URL for outlook_link (omitted if unset)")
    parser.add_argument("--join-hosts", default=env("MAILCAL_JOIN_HOSTS"), help="extra regex of meeting-link hosts")
    parser.add_argument("--calendar-db", help="path to Calendar.sqlitedb (override)")
    parser.add_argument("--mail-root", help="path to the Mail V* folder (override)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("meetings", help="list meetings in a date range")
    p.add_argument("--day", default="today", help="first day: today, tomorrow, yesterday, or YYYY-MM-DD")
    p.add_argument("--days", type=int, default=1, help="number of days from --day (default 1)")
    p.add_argument("--search", help="only titles containing this text")
    p.add_argument("--include-declined", action="store_true")
    p.add_argument("--include-canceled", action="store_true")
    p.add_argument("--all-calendars", action="store_true", help="include the Exchange store's other calendars (holidays, birthdays)")
    p.set_defaults(func=cmd_meetings)

    p = sub.add_parser("meeting", help="one meeting's attendees, notes, and join link")
    p.add_argument("event_id", type=int)
    p.set_defaults(func=cmd_meeting)

    p = sub.add_parser("mail", help="search message headers")
    p.add_argument("--search", help="subject contains")
    p.add_argument("--sender", help="sender address or name contains")
    p.add_argument("--mailbox", help="exact folder name, such as Inbox, DevOps, or 'Sent Items'")
    p.add_argument("--since", help="received on or after: today, yesterday, or YYYY-MM-DD")
    p.add_argument("--until", help="received on or before: YYYY-MM-DD")
    p.add_argument("--unread", action="store_true")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_mail)

    p = sub.add_parser("message", help="one message's headers and body")
    p.add_argument("message_id", type=int)
    p.add_argument("--max-chars", type=int, default=20000)
    p.set_defaults(func=cmd_message)

    args = parser.parse_args(argv)
    configure(args)
    json.dump(args.func(args), sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
