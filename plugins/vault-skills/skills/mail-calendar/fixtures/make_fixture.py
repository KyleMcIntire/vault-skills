#!/usr/bin/env python3
"""Build a tiny fictional Calendar.sqlitedb and Mail store for offline tests.

Usage: make_fixture.py OUT_DIR
Then:  mail_calendar.py --calendar-db OUT_DIR/Calendar.sqlitedb --mail-root OUT_DIR/Mail meetings --day today
"""
import datetime as dt
import sqlite3
import sys
from pathlib import Path

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
EPOCH = 978307200
now = dt.datetime.now().astimezone()
start = dt.datetime.combine(now.date(), dt.time(10, 0)).astimezone()
core = start.timestamp() - EPOCH

db = out / "Calendar.sqlitedb"
db.unlink(missing_ok=True)
c = sqlite3.connect(db)
c.executescript("""
create table Store(ROWID integer primary key, name text);
create table Calendar(ROWID integer primary key, title text, store_id integer);
create table Location(ROWID integer primary key, title text);
create table Identity(ROWID integer primary key, display_name text);
create table CalendarItem(ROWID integer primary key, summary text, start_date real, end_date real, all_day int,
  location_id int, conference_url text, description text, external_id text, status int, has_recurrences int,
  orig_item_id int, self_attendee_id int);
create table OccurrenceCache(event_id int, calendar_id int, occurrence_date real);
create table Participant(ROWID integer primary key, owner_id int, identity_id int, email text, entity_type int, status int);
""")
c.execute("insert into Store values (1,'Exchange')")
c.execute("insert into Calendar values (1,'Calendar',1)")
c.execute("insert into Location values (1,'Room 1')")
c.executemany("insert into Identity values (?,?)", [(1, "Alex Example"), (2, "Sam Sample")])
c.execute("insert into CalendarItem values (1,'Team sync',?,?,0,1,NULL,'Agenda: demo. Join https://example.zoom.us/j/123',?,0,0,0,2)",
           (core, core + 1800, "AAMk-fixture-id"))
c.execute("insert into OccurrenceCache values (1,1,?)", (core,))
c.execute("insert into Participant values (1,1,2,'mailto:sam@example.com',8,0)")  # organizer
c.execute("insert into Participant values (2,1,1,'mailto:alex@example.com',7,1)")  # attendee (me)
c.commit()

mail = out / "Mail"
(mail / "MailData").mkdir(parents=True, exist_ok=True)
mdb = mail / "MailData" / "Envelope Index"
mdb.unlink(missing_ok=True)
m = sqlite3.connect(mdb)
m.executescript("""
create table subjects(ROWID integer primary key, subject text);
create table mailboxes(ROWID integer primary key, url text);
create table addresses(ROWID integer primary key, address text, comment text);
create table summaries(ROWID integer primary key, summary text);
create table recipients(message int, type int, address int, position int);
create table messages(ROWID integer primary key, remote_id text, date_received int, read int, flagged int,
  sender int, subject int, subject_prefix text, mailbox int, summary int, deleted int);
""")
m.execute("insert into subjects values (1,'Weekly report')")
m.execute("insert into mailboxes values (1,'ews://ACCT-1/Inbox')")
m.execute("insert into addresses values (1,'sam@example.com','Sam Sample')")
m.execute("insert into summaries values (1,'Numbers attached')")
m.execute("insert into recipients values (1,0,1,0)")
m.execute("insert into messages values (1,'AAMk-msg',?,0,0,1,1,'',1,1,0)", (int(now.timestamp()),))
m.commit()
emlx_dir = mail / "ACCT-1" / "Inbox.mbox" / "UUID" / "Data" / "Messages"
emlx_dir.mkdir(parents=True, exist_ok=True)
body = b"From: Sam Sample <sam@example.com>\nSubject: Weekly report\nDate: Mon, 01 Jan 2026 09:00:00 +0000\nContent-Type: text/plain\n\nHello Alex, numbers are attached.\n"
(emlx_dir / "1.emlx").write_bytes(str(len(body)).encode() + b"\n" + body)
print("fixture written to", out)
