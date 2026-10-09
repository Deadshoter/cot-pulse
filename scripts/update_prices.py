"""Fetch prices from Yahoo Finance and write data/prices.json.

For every market: the latest price, plus the daily close on (or just before) each COT
report date, so the site can show "price since the report" and the AI sees price history.
A market that fails to load keeps its previous values; the run fails only if all fail.
"""
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone

from common import MARKETS, http_json, load, save, now_iso

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{}?{}"


def fetch(ticker, start):
    p1 = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    qs = urllib.parse.urlencode({"period1": p1, "period2": int(time.time()), "interval": "1d"})
    j = http_json(CHART.format(urllib.parse.quote(ticker), qs))
    res = j["chart"]["result"][0]
    closes = res["indicators"]["quote"][0]["close"]
    pts = [(datetime.fromtimestamp(ts, timezone.utc).date().isoformat(), c)
           for ts, c in zip(res.get("timestamp") or [], closes) if c is not None]
    meta = res["meta"]
    last = meta.get("regularMarketPrice") or (pts[-1][1] if pts else None)
    last_time = meta.get("regularMarketTime")
    return pts, last, last_time


def sig(v):
    return None if v is None else float(f"{v:.5g}")


def main():
    cot = load("cot.json")
    if not cot:
        raise SystemExit("data/cot.json missing — run update_cot.py first")
    dates = cot["dates"]
    start = date.fromisoformat(dates[0]) - timedelta(days=10)
    old = (load("prices.json") or {}).get("markets", {})
    out, ok = {}, 0
    for code, ticker in MARKETS.items():
        try:
            pts, last, last_time = fetch(ticker, start)
            series, j, v = [], 0, None
            for d in dates:
                while j < len(pts) and pts[j][0] <= d:
                    v = pts[j][1]
                    j += 1
                series.append(sig(v))
            out[code] = {
                "ticker": ticker, "last": sig(last),
                "lastTime": datetime.fromtimestamp(last_time, timezone.utc).isoformat().replace("+00:00", "Z") if last_time else None,
                "atReport": series,
            }
            ok += 1
        except Exception as e:
            print(f"warning: {ticker}: {e}")
            if code in old and len(old[code].get("atReport", [])) == len(dates):
                out[code] = old[code]
        time.sleep(0.4)
    if ok == 0:
        raise SystemExit("All price requests failed — keeping previous prices.json")
    save("prices.json", {"updatedAt": now_iso(), "cotAsOf": cot["asOf"], "markets": out})
    print(f"Prices updated: {ok}/{len(MARKETS)}")


if __name__ == "__main__":
    main()
