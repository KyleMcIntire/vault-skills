import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["PREFS_STATE_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(HERE))
import collect  # noqa: E402


def call(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        collect.main(list(argv))
    return json.loads(buf.getvalue()) if buf.getvalue().strip().startswith("{") else buf.getvalue()


class Units(unittest.TestCase):
    def test_parse_ts_forms(self):
        self.assertEqual(collect.parse_ts("2026-10-28T23:04:04.538Z").hour, 23)
        self.assertEqual(collect.parse_ts("2026-10-06T17:01:35.538-0500").hour, 17)
        self.assertEqual(collect.parse_ts("1730000000.5").year, 2024)

    def test_user_text_skips_machine_messages(self):
        for c in ("<system-reminder>x", "[Request interrupted by user]", "<bash-stderr>boom", "Caveat: x"):
            self.assertIsNone(collect.user_text({"content": c}))
        self.assertIsNone(collect.user_text({"content": [{"type": "tool_result", "content": "x"}]}))
        self.assertEqual(collect.user_text({"content": [{"type": "text", "text": "hello there"}]}), "hello there")

    def test_slash_command_keeps_args(self):
        t = collect.user_text({"content": "<command-message>x</command-message><command-name>/vault-skills:foo</command-name>"
                                           "<command-args>do the thing</command-args>"})
        self.assertEqual(t, "/vault-skills:foo do the thing")

    def test_redaction_and_strong(self):
        self.assertNotIn("ghp_", collect.redact("use ghp_" + "a" * 30 + " now"))
        self.assertNotIn("hunter2hunter2", collect.redact("password: hunter2hunter2"))
        self.assertTrue(collect.STRONG_RE.search("No, don't do that"))
        self.assertFalse(collect.STRONG_RE.search("looks fine to me"))

    def test_short_text_dropped(self):
        now = datetime.now(timezone.utc)
        self.assertIsNone(collect.item("x", "k", now, "w", None, "lgtm", ("a",), 100))

    def test_strip_quoted(self):
        self.assertEqual(collect.strip_quoted("Sounds good.\nFrom: Bob\nold").strip(), "Sounds good.")


class Voice(unittest.TestCase):
    def test_features_and_emoji(self):
        f, e = collect.voice_features("Thanks! :rocket: Merged \U0001F44D\n\n- one\n- two `code` https://x.y")
        self.assertEqual((f["bullets"], f["inline_code"], f["links"], f["thanks"], f["multi_paragraph"]), (2, 1, 1, 1, 1))
        self.assertIn(":rocket:", e)
        self.assertIn("\U0001F44D", e)

    def test_code_block_emoji_ignored_and_time_not_shortcode(self):
        f, e = collect.voice_features("at 10:30:45 ok\n```\n:fake: \U0001F600\n```")
        self.assertEqual(e, [])
        self.assertEqual(f["code_blocks"], 1)


class Deltas(unittest.TestCase):
    def setUp(self):
        collect.STATE_DIR = Path(tempfile.mkdtemp())
        collect.STATE = collect.STATE_DIR / "state.json"
        collect.PENDING = collect.STATE_DIR / "pending.json"
        self.now = datetime.now(timezone.utc)
        self.fake = []
        collect.COLLECTORS["sessions"] = lambda since, tm: [
            collect.item("sessions", "claude-message", self.now - timedelta(minutes=n), "w", None,
                         f"please always do thing number {n}", ("s", n), tm) for n in self.fake]

    def test_collect_commit_then_only_new(self):
        self.fake = [1, 2, 3]
        r = call("collect", "--sources", "sessions")
        self.assertEqual(r["counts"]["total"], 3)
        self.assertEqual(call("collect", "--sources", "sessions")["counts"]["total"], 3)  # not committed yet
        call("commit")
        self.assertEqual(call("collect", "--sources", "sessions")["counts"]["total"], 0)
        self.fake = [1, 2, 3, 4]
        r = call("collect", "--sources", "sessions")
        self.assertEqual([i["text"][-1] for i in r["items"]], ["4"])

    def test_cap_drains_oldest_first(self):
        self.fake = list(range(1, 6))
        r = call("collect", "--sources", "sessions", "--cap", "2")
        self.assertEqual(r["sources"]["sessions"]["capped"], 3)
        self.assertEqual(len(r["items"]), 2)
        call("commit")
        r2 = call("collect", "--sources", "sessions", "--cap", "10")
        self.assertEqual(r2["counts"]["total"], 3)

    def test_failed_source_keeps_watermark(self):
        def boom(since, tm):
            raise RuntimeError("down")
        collect.COLLECTORS["sessions"] = boom
        r = call("collect", "--sources", "sessions")
        self.assertIn("error", r["sources"]["sessions"])
        call("commit")
        self.assertNotIn("sessions", collect.load_state()["sources"])

    def test_voice_accumulates_on_commit_only(self):
        f = collect.STATE_DIR / "slack.json"
        f.write_text(json.dumps([{"at": self.now.isoformat(), "where": "#x", "link": "https://s/9",
                                  "text": "Shipped it :tada: thanks all"}]))
        r = call("collect", "--sources", "", "--extra", str(f))
        self.assertNotIn("_v", r["items"][0])
        self.assertEqual(r["voice_delta"]["slack"]["messages"], 1)
        self.assertNotIn("voice", collect.load_state())
        call("commit")
        v = call("voice")
        self.assertEqual(v["slack"]["emoji"][0][0], ":tada:")

    def test_extra_slack_advances_watermark(self):
        f = collect.STATE_DIR / "slack.json"
        f.write_text(json.dumps([{"at": self.now.isoformat(), "where": "#x", "link": "https://s/1",
                                  "text": "I prefer short replies in threads"}]))
        r = call("collect", "--sources", "", "--extra", str(f))
        self.assertEqual(r["counts"]["total"], 1)
        call("commit")
        f.write_text("[]")
        r = call("collect", "--sources", "", "--extra", str(f))
        self.assertEqual(r["counts"]["total"], 0)
        self.assertIn("slack", collect.load_state()["sources"])


if __name__ == "__main__":
    unittest.main()
