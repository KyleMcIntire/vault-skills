#!/usr/bin/env python3
"""Write a fictional offline fixture: two local feed files, a feed list and a pins file.

Usage: make_fixture.py OUT_DIR
Then:  fetch_news.py 7 --feeds OUT_DIR/feeds.json --pins OUT_DIR/pins.json
(no --location, so no network is used)
"""
import json
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
now = datetime.now(timezone.utc)
rss = f"""<rss><channel>
<item><title>Acme Cluster 1.2.7 released</title><link>https://example.com/r/1</link><pubDate>{format_datetime(now)}</pubDate><description>Changelog: fixes a bug in Kubernetes scheduling</description></item>
<item><title>Unrelated cooking post</title><link>https://example.com/r/2</link><pubDate>{format_datetime(now)}</pubDate><description>Soup</description></item>
<item><title>Supply chain attack hits a popular package</title><link>https://example.com/s/1</link><pubDate>{format_datetime(now)}</pubDate><description>Malicious versions published</description></item>
</channel></rss>"""
(out / "rss.xml").write_text(rss)
atom = f"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>v1.2.9</title><link href="https://example.com/rel/1.2.9"/><updated>{now.strftime('%Y-%m-%dT%H:%M:%SZ')}</updated><content>What's Changed: things</content></entry></feed>"""
(out / "atom.xml").write_text(atom)
(out / "feeds.json").write_text(json.dumps({
    "keywords": ["Kubernetes"], "ignore_title_regex": "",
    "sources": [
        {"name": "Fixture blog", "url": str(out / "rss.xml"), "kind": "filter"},
        {"name": "Fixture security", "url": str(out / "rss.xml"), "kind": "security"},
        {"name": "Acme releases", "url": str(out / "atom.xml"), "kind": "release", "product": "Acme Cluster"},
        {"name": "Unreachable", "url": "https://feeds.invalid/none.xml", "kind": "all"}]}))
(out / "pins.json").write_text(json.dumps({"Acme Cluster": [{"version": "1.2.3", "where": "fixture pins"}]}))
print("fixture written to", out)
