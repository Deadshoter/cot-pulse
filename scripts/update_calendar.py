"""Fetch the Forex Factory economic calendar and write data/calendar.json.

Source: the official Forex Factory calendar export (nfs.faireconomy.media). It covers the
current week (Sunday-Saturday, New York time) with title, currency, time, impact,
forecast and previous values. Events from the last 7 days are kept, so the site still
shows the past week on Saturdays before the next week is published.
The feed is rate-limited by its owner; this script makes one request per run.
"""
from datetime import datetime, timedelta, timezone

from common import http_json, load, save, now_iso

FEED = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
KEEP_DAYS = 7


def norm(e):
    """Feed rows use long names; rows already saved use short ones."""
    if "title" in e:
        return {"t": e["title"], "c": e["country"], "d": e["date"], "i": e.get("impact", ""),
                "f": e.get("forecast", ""), "p": e.get("previous", "")}
    return e


def main():
    fresh = http_json(FEED, retries=2)
    if not isinstance(fresh, list):
        raise SystemExit("Unexpected calendar format")
    old = (load("calendar.json") or {}).get("events", [])
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    merged = {}
    for raw in old + fresh:
        e = norm(raw)
        try:
            when = datetime.fromisoformat(e["d"])
        except Exception:
            continue
        if when < cutoff:
            continue
        merged[e["d"] + "|" + e["c"] + "|" + e["t"]] = e
    events = sorted(merged.values(), key=lambda x: datetime.fromisoformat(x["d"]))
    save("calendar.json", {"updatedAt": now_iso(), "source": "Forex Factory", "events": events})
    print(f"Calendar: {len(events)} events")


if __name__ == "__main__":
    main()
