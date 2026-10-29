#!/usr/bin/env python3
"""Recent items from RSS/Atom feeds, filtered by keyword, plus an optional weather forecast.

Usage: fetch_news.py [days=7] [--feeds FILE] [--rss URL ...] [--seen DIR] [--pins FILE]
                     [--location "City, Region" | --lat N --lon N [--tz ZONE]] [--location-name NAME]
                     [--local-area REGEX]

  --feeds FILE      JSON feed list (default: references/example-feeds.json next to this script). Edit a
                    copy for your own list; see that file for the format.
  --rss URL         extra feed, repeatable (kind "all"); pass integrations.news_feeds.rss here.
  --seen DIR        drop items whose link already appears in a note under DIR (previous digests).
  --pins FILE       JSON of versions you run, to annotate release items with a pin_note.
  --location        weather location as "City, Region" (geocoded with Open-Meteo) or --lat/--lon.
                    Omit all of them to skip the weather.
  --local-area      regex of place names; "local" feeds keep only stories that match it.

Prints JSON: items (newest first), local news, weather (forecast, AQI, and US National Weather Service
alerts when available), counts and errors per source, and pins. Read-only, standard library only.
A source that cannot be reached is reported under errors, never raised.
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
DEFAULT_FEEDS = HERE / "references" / "example-feeds.json"

# "now available in <Region>" posts match on service names but rarely matter.
REGIONAL = re.compile(r"\b(now )?(available|expands?|launch(es|ed)?)\b.*\b(in|to)\b.*\b(Regions?|Tokyo|Osaka|Sydney|Mumbai|Frankfurt|Ireland|London|Paris|Milan|Stockholm|Zurich|Spain|Seoul|Singapore|Jakarta|Hong Kong|Bahrain|UAE|Cape Town|Canada|Calgary|Mexico|Israel|Thailand|Taipei|Malaysia|New Zealand)\b", re.I)
# Titles that read like an incident or an urgent flaw.
INCIDENT = re.compile(r"certificate authorit|\bCA\b.*(compromis|key|revok|distrust)|intermediate|root (CA|certificate)|distrust|compromis|supply[- ]chain|malicious|backdoor|trojan|zero-day|0-day|actively exploit|in the wild|critical (flaw|vulnerabilit|bug)|remote code execution|\bRCE\b|breach|key leak|leaked (key|secret|credential)|emergency directive|known exploited", re.I)
CISA_URGENT = re.compile(r"emergency directive|known exploited|KEV|alert|\bAA\d", re.I)
PRERELEASE = re.compile(r"-(rc|alpha|beta|pre)\b|\b(rc|alpha|beta)\d", re.I)
# Accepts "v1.2.3", "1.2.3 / 2026-10-21", "Istio 1.31.2"; skips "chore: bump version" tag noise.
RELEASE_TITLE = re.compile(r"^(\w+/)?([A-Za-z][\w .-]*?[ -])?v?\d+\.\d+")
VERSION = re.compile(r"v?(\d+)\.(\d+)(?:\.(\d+))?")
NS = {"a": "http://www.w3.org/2005/Atom"}
EXCERPT = 600
RELEASE_EXCERPT = 900
LOCAL_PER_SOURCE = 8
LOCAL_DAYS = 3
ENTITIES = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "#39": "'"}


def parse_date(text):
    text = (text or "").strip()
    try:
        return parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return datetime.fromisoformat(text.replace("Z", "+00:00"))


def entries(root):
    for it in root.iter("item"):
        yield (it.findtext("title", ""), it.findtext("link", ""), it.findtext("pubDate"),
               it.findtext("description", ""))
    for it in root.findall("a:entry", NS):
        link = it.find("a:link", NS)
        yield (it.findtext("a:title", "", NS), link.get("href") if link is not None else "",
               it.findtext("a:updated", None, NS), it.findtext("a:content", "", NS))


def plain(html):
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"&(amp|lt|gt|quot|#39);", lambda m: ENTITIES[m.group(1)], text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_bytes(url):
    if url.startswith("file://") or Path(url).exists():  # local file, for offline tests
        return Path(url.removeprefix("file://")).read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "vault-skills-get-news/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def load(source, cutoff, patterns, ignore, local_area):
    name, url, kind = source["name"], source["url"], source.get("kind", "all")
    try:
        feed = list(entries(ET.fromstring(fetch_bytes(url))))
    except Exception as exc:  # report, never hide, a failed source
        return name, [], f"{type(exc).__name__}: {exc}"
    out = []
    local = kind.startswith("local")
    start_of_window = cutoff
    if local:  # local news goes stale fast: look back at most LOCAL_DAYS
        start_of_window = max(cutoff, datetime.now(timezone.utc) - timedelta(days=LOCAL_DAYS))
    for title, link, date, body in feed:
        try:
            when = parse_date(date)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if when < start_of_window:
            continue
        text_body = plain(body)
        text = title + " " + text_body
        hits = [k for k, p in patterns.items() if p.search(text)]
        in_title = any(p.search(title) for p in patterns.values())
        if kind == "local-filter" and not (local_area and local_area.search(text)):
            continue
        if ignore and ignore.search(title):
            continue
        if kind == "filter":
            # Keep a title hit, or a body hit on two different keywords; drop regional rollouts.
            if not (in_title or len(hits) >= 2):
                continue
            if REGIONAL.search(title):
                continue
        if kind == "release" and (PRERELEASE.search(title) or not RELEASE_TITLE.search(title)):
            continue
        if kind == "security" and not INCIDENT.search(title):
            continue
        if kind == "cisa" and not (CISA_URGENT.search(title) or INCIDENT.search(title)):
            continue
        excerpt = text_body[:EXCERPT]
        if kind == "release":  # skip install and signature boilerplate; start at the changes
            start = re.search(r"\b(Changelog|OS Changes|Bug Fixes|What's Changed)\b", text_body)
            excerpt = text_body[start.start():][:RELEASE_EXCERPT] if start else text_body[:RELEASE_EXCERPT]
        out.append({"source": name, "product": source.get("product"), "date": when.astimezone().date().isoformat(),
                    "title": title.strip(), "link": link, "matched": hits, "in_title": in_title or kind != "filter",
                    "security": not local and (kind in ("security", "cisa") or bool(INCIDENT.search(title))),
                    "local": local, "excerpt": excerpt})
    if local:
        out = sorted(out, key=lambda i: i["date"], reverse=True)[:LOCAL_PER_SOURCE]
    return name, out, None


def triple(text):
    return tuple(int(x or 0) for x in VERSION.search(text).groups())


def pin_note(item, pins):
    """Compare a release item's version with the pins for its product."""
    product = item.get("product")
    m = VERSION.search(item["title"])
    if not (product and m and product in pins):
        return None
    new = triple(item["title"])
    notes = []
    for p in pins[product]:
        cur = triple(p["version"])
        if new[:2] == cur[:2] and new > cur:
            notes.append(f"newer patch of pinned {p['version']} ({p['where']})")
        elif new == cur:
            notes.append(f"matches pin {p['version']} ({p['where']})")
    if not notes and all(new[:2] > triple(p["version"])[:2] for p in pins[product]):
        notes.append("newer minor than every pin")
    return "; ".join(notes) or "other line than the pins"


WMO = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "freezing fog",
       51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
       61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
       71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains", 80: "rain showers",
       81: "rain showers", 82: "heavy rain showers", 85: "snow showers", 86: "heavy snow showers",
       95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail"}
AQI_BANDS = [(50, "Good"), (100, "Moderate"), (150, "Unhealthy for sensitive groups"),
             (200, "Unhealthy"), (300, "Very unhealthy"), (10_000, "Hazardous")]


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "vault-skills-get-news/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def geocode(text):
    """Resolve "City, Region" to coordinates with Open-Meteo's geocoder."""
    city = text.split(",")[0].strip()
    res = get_json("https://geocoding-api.open-meteo.com/v1/search?count=5&name=" + urllib.parse.quote(city)).get("results") or []
    rest = [p.strip().lower() for p in text.split(",")[1:]]
    for r in res:  # prefer a result whose region or country matches the rest of the text
        if not rest or any(p in (r.get("admin1", "") + " " + r.get("country", "") + " " + r.get("country_code", "")).lower() for p in rest):
            return {"name": text, "lat": r["latitude"], "lon": r["longitude"], "tz": r.get("timezone", "auto")}
    if res:
        return {"name": text, "lat": res[0]["latitude"], "lon": res[0]["longitude"], "tz": res[0].get("timezone", "auto")}
    raise ValueError(f"could not geocode {text!r}")


def weather(loc):
    """Forecast, AQI and NWS alerts for loc. Failures are reported in the result, not hidden."""
    lat, lon, tz = loc["lat"], loc["lon"], urllib.parse.quote(loc["tz"], safe="")
    out = {"location": loc["name"], "errors": {}}
    try:
        w = get_json(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&timezone={tz}"
            "&temperature_unit=fahrenheit&wind_speed_unit=mph&forecast_days=3"
            "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
            "precipitation_sum,cloud_cover_mean,wind_speed_10m_max,sunrise,sunset")["daily"]
        out["days"] = [{
            "date": w["time"][i],
            "high": round(w["temperature_2m_max"][i]), "low": round(w["temperature_2m_min"][i]),
            "rain_chance": w["precipitation_probability_max"][i],
            "sky_percent": round(w["cloud_cover_mean"][i]) if w.get("cloud_cover_mean", [None] * 3)[i] is not None else None,
            "condition": WMO.get(w["weather_code"][i], f"code {w['weather_code'][i]}"),
            "wind_max_mph": round(w["wind_speed_10m_max"][i]),
            "sunrise": w["sunrise"][i][-5:], "sunset": w["sunset"][i][-5:],
        } for i in range(len(w["time"]))]
    except Exception as exc:
        out["errors"]["forecast"] = f"{type(exc).__name__}: {exc}"
    try:
        a = get_json(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}"
                     f"&timezone={tz}&current=us_aqi&hourly=us_aqi&forecast_days=1")
        values = [v for v in a["hourly"]["us_aqi"] if v is not None]
        now, peak = a["current"]["us_aqi"], max(values) if values else None
        band = lambda v: next((name for limit, name in AQI_BANDS if v <= limit), "") if v is not None else None
        out["aqi"] = {"now": now, "peak_today": peak, "category": band(peak if peak is not None else now)}
    except Exception as exc:
        out["errors"]["aqi"] = f"{type(exc).__name__}: {exc}"
    try:  # US only: elsewhere this fails and is reported
        feats = get_json(f"https://api.weather.gov/alerts/active?point={lat},{lon}")["features"]
        out["alerts"] = [{"event": f["properties"]["event"], "severity": f["properties"]["severity"],
                          "headline": f["properties"]["headline"], "ends": f["properties"].get("ends")}
                         for f in feats]
    except Exception as exc:
        out["errors"]["alerts"] = f"{type(exc).__name__}: {exc} (alerts come from the US National Weather Service)"
    return out


def seen_links(directory):
    links = set()
    for md in Path(directory).glob("*.md"):
        links.update(re.findall(r"https?://[^\s)\]>]+", md.read_text(encoding="utf-8", errors="replace")))
    return links


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("days", nargs="?", type=int, default=7)
    ap.add_argument("--feeds", default=str(DEFAULT_FEEDS))
    ap.add_argument("--rss", action="append", default=[])
    ap.add_argument("--seen")
    ap.add_argument("--pins")
    ap.add_argument("--location")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--tz", default="auto")
    ap.add_argument("--location-name")
    ap.add_argument("--local-area")
    a = ap.parse_args()

    try:
        cfg = json.loads(Path(a.feeds).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        sys.exit(f"cannot read feed list {a.feeds}: {exc}")
    sources = list(cfg.get("sources", []))
    for url in a.rss:
        sources.append({"name": urlparse(url).netloc or url, "url": url, "kind": "all"})
    if not sources:
        sys.exit("no feeds: pass --feeds FILE or --rss URL")
    patterns = {k: re.compile(r"\b" + re.escape(k) + r"\b", re.I) for k in cfg.get("keywords", [])}
    ignore = re.compile(cfg["ignore_title_regex"], re.I) if cfg.get("ignore_title_regex") else None
    local_area = re.compile(a.local_area, re.I) if a.local_area else None

    pins, pin_error = {}, None
    if a.pins:
        try:
            pins = {k: v for k, v in json.loads(Path(a.pins).read_text(encoding="utf-8")).items() if not k.startswith("_")}
        except (OSError, ValueError) as exc:
            pin_error = f"{type(exc).__name__}: {exc}"

    cutoff = datetime.now(timezone.utc) - timedelta(days=a.days)
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        results = list(pool.map(lambda s: load(s, cutoff, patterns, ignore, local_area), sources))
    items = [i for _, found, _ in results for i in found]
    seen = seen_links(a.seen) if a.seen and Path(a.seen).is_dir() else set()
    dropped = [i for i in items if i["link"] in seen]
    items = [i for i in items if i["link"] not in seen]
    for i in items:
        note = pin_note(i, pins)
        if note:
            i["pin_note"] = note
    items.sort(key=lambda i: i["date"], reverse=True)
    local = [i for i in items if i["local"]]
    items = [i for i in items if not i["local"]]

    wx = None
    loc = None
    try:
        if a.lat is not None and a.lon is not None:
            loc = {"name": a.location_name or f"{a.lat},{a.lon}", "lat": a.lat, "lon": a.lon, "tz": a.tz}
        elif a.location:
            loc = geocode(a.location)
            if a.location_name:
                loc["name"] = a.location_name
    except Exception as exc:
        wx = {"errors": {"location": f"{type(exc).__name__}: {exc}"}}
    if loc:
        wx = weather(loc)
    json.dump({"days": a.days, "items": items, "local": local, "weather": wx,
               "already_in_digests": len(dropped), "pins": {"found": pins, "error": pin_error},
               "errors": {n: e for n, _, e in results if e},
               "counts": {n: len(f) for n, f, _ in results}}, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
