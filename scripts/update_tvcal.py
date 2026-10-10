"""Fetch the economic calendar (TradingView) and write data/calendar.json.

Covers 7 days back and 12 days ahead for the major currencies: time, currency, country,
importance, title, actual, forecast and previous values. The file is rewritten only when
the events actually changed, so the frequent workflow commits nothing between releases.
Prints changed=true|false to $GITHUB_OUTPUT.
"""
import os
import urllib.parse
from datetime import datetime, timedelta, timezone

from common import http_json, load, save, now_iso

API = "https://economic-calendar.tradingview.com/events"
COUNTRIES = "US,EU,DE,FR,IT,GB,JP,CA,AU,NZ,CH,CN"
HEADERS = {"Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/"}


def set_output(changed):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")


def main():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    q = urllib.parse.urlencode({
        "from": (now - timedelta(days=7)).isoformat().replace("+00:00", ".000Z"),
        "to": (now + timedelta(days=12)).isoformat().replace("+00:00", ".000Z"),
        "countries": COUNTRIES,
    })
    j = http_json(API + "?" + q, headers=HEADERS, retries=3)
    rows = j.get("result", j) if isinstance(j, dict) else j
    if not isinstance(rows, list) or len(rows) < 20:
        raise SystemExit("Unexpected calendar response - keeping previous file")
    events = []
    for e in rows:
        events.append({
            "id": str(e.get("id", "")), "d": e["date"], "c": e.get("currency") or "", "co": (e.get("country") or "").lower(),
            "t": e.get("title") or e.get("indicator") or "", "per": e.get("period") or "",
            "i": "hol" if e.get("indicator") == "Holidays" else {1: "high", 0: "med"}.get(e.get("importance"), "low"),
            "a": e.get("actual"), "f": e.get("forecast"), "p": e.get("previous"), "u": e.get("unit") or "",
            "s": e.get("scale") or "",
        })
    events.sort(key=lambda x: (x["d"], {"high": 0, "med": 1, "low": 2, "hol": 3}[x["i"]]))
    old = load("calendar.json") or {}
    if old.get("source") == "TradingView" and old.get("events") == events:
        print(f"Calendar unchanged ({len(events)} events)")
        set_output(False)
        return
    save("calendar.json", {"updatedAt": now_iso(), "source": "TradingView", "events": events})
    print(f"Calendar updated: {len(events)} events")
    set_output(True)


if __name__ == "__main__":
    main()
