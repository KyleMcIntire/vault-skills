"""Offline tests for weekly-review's gather.py, run against the fictional fixtures/vault."""
import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.join(HERE, "fixtures", "vault")
spec = importlib.util.spec_from_file_location("weekly_gather", os.path.join(HERE, "gather.py"))
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

END = dt.date(2026, 10, 30)
SPAN = g.Span(END - dt.timedelta(days=6), END)


class Gather(unittest.TestCase):
    def setUp(self):
        g.S.update(daily="Daily Notes", meetings="Meetings", tasks="Tasks", projects="Projects",
                   standup_name="Team Standup", sensitive_dirs=("Tasks/Health",), sensitive_tags=("#Health",))
        g.eod.CFG.update(standup_dir="Meetings/Recurring/Standup", standup_name="Team Standup",
                         tasks_dir="Tasks", hub_link="", entry_heading="", jira_site="acme.invalid")

    def test_span(self):
        self.assertEqual(SPAN.first, dt.date(2026, 10, 24))
        self.assertEqual([d.day for d in SPAN.days()], list(range(24, 31)))
        self.assertTrue(SPAN.has_date("2026-10-28"))
        self.assertFalse(SPAN.has_date("2026-10-23"))

    def test_standups_and_meetings(self):
        s = g.standups(VAULT, SPAN)
        self.assertEqual([e["date"] for e in s], ["2026-10-28"])
        self.assertIn("Opened the PR", s[0]["text"])
        m = g.meeting_notes(VAULT, SPAN)
        self.assertEqual(len(m), 1)  # the standup is excluded
        self.assertIn("widget cache first", m[0]["tldr"])
        self.assertIn("Cache before", m[0]["decisions"])

    def test_daily_notes(self):
        d = {e["date"]: e for e in g.daily_notes(VAULT, SPAN)}
        self.assertEqual(d["2026-10-28"]["summary"], "Work: opened the widget cache PR.")
        self.assertEqual(d["2026-10-28"]["open_inbox_items"], 1)
        self.assertIsNone(d["2026-10-27"]["path"])

    def test_changelog_entries(self):
        e = g.changelog_entries(VAULT, SPAN, "all")
        self.assertEqual([x["date"] for x in e], ["2026-10-28", "2026-10-29"])
        self.assertTrue(all(x["date"] >= "2026-10-24" for x in e))

    def test_tasks(self):
        t = g.tasks(VAULT, SPAN, "all")
        self.assertEqual(t["completed_total"], 3)  # the 10-26 and 10-28 ticks plus the health task
        notes = {n["path"]: n for n in t["completed_by_note"]}
        self.assertTrue(notes["Tasks/Health/Checkup.md"]["sensitive"])
        self.assertFalse(notes["Tasks/In Progress/Add widget cache.md"]["sensitive"])
        due = {x["task"].split(" 📅")[0]: x for x in t["due_soon"]}
        self.assertTrue(due["Old chore"]["overdue"])
        self.assertIn("Update docs", due)
        self.assertNotIn("Stretch daily", due)  # daily habits are left out
        self.assertTrue(due["Follow-up call"]["sensitive"])

    def test_projects_and_previous_review(self):
        p = g.projects(VAULT, SPAN, "work")
        self.assertEqual([x["path"].split("/")[-1] for x in p], ["Demo Project.md"])
        self.assertTrue(p[0]["reviewed_in_window"])
        prev = g.previous_review(VAULT, SPAN)
        self.assertIn("Open the widget cache PR", prev["priorities"])
        self.assertEqual(g.review_note_rel(SPAN), "Daily Notes/2026/Weekly Reviews/2026-W44 Weekly Review.md")

    def test_cli_offline(self):
        out = subprocess.run(
            [sys.executable, "-I", os.path.join(HERE, "gather.py"), "--vault", VAULT, "--end", "2026-10-30",
             "--skip", "github,jira,sessions", "--standup-name", "Team Standup", "--jira-site", "acme.invalid",
             "--project-keys", "ABC", "--sensitive-dirs", "Tasks/Health"],
            capture_output=True, text=True, check=True)
        data = json.loads(out.stdout)
        self.assertEqual(data["window"]["first"], "2026-10-24")
        self.assertFalse(data["review_note_exists"])
        self.assertIn("skipped", data["github"]["error"])
        self.assertEqual(data["claude_sessions"], [])
        self.assertIn("ABC-123", json.dumps(data["standups"]))
        self.assertEqual(list(data["task_notes_by_key"]), ["ABC-123"])
        self.assertTrue(any(n["sensitive"] for n in data["tasks"]["completed_by_note"]))


if __name__ == "__main__":
    unittest.main()
