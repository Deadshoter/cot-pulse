"""Fetch prices and write data/prices.json.

For every market: the latest price, plus the daily close on (or just before) each COT
report date, so the site can show "price since the report" and the AI sees price history.
Source: Yahoo Finance via the yfinance library (it handles Yahoo's anti-bot checks that
block plain requests from cloud servers). A market that fails keeps its previous values.
"""
import math
from datetime import date, datetime, timedelta, timezone

import yfinance as yf

from common import MARKETS, load, save, now_iso


def sig(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return float(f"{float(v):.5g}")


def main():
    cot = load("cot.json")
    if not cot:
        raise SystemExit("data/cot.json missing - run update_cot.py first")
    dates = cot["dates"]
    start = (date.fromisoformat(dates[0]) - timedelta(days=10)).isoformat()
    old = (load("prices.json") or {}).get("markets", {})
    tickers = list(MARKETS.values())

    daily = yf.download(tickers, start=start, interval="1d", auto_adjust=False,
                        progress=False, threads=True, group_by="ticker")
    out, ok = {}, 0
    for code, ticker in MARKETS.items():
        try:
            closes = daily[ticker]["Close"].dropna()
            pts = [(ts.date().isoformat(), float(v)) for ts, v in closes.items()]
            if len(pts) < 50:
                raise ValueError(f"only {len(pts)} daily points")
            last, last_time = pts[-1][1], None
            try:
                intraday = yf.Ticker(ticker).history(period="1d", interval="5m")["Close"].dropna()
                if len(intraday):
                    last = float(intraday.iloc[-1])
                    last_time = intraday.index[-1].to_pydatetime().astimezone(timezone.utc)
            except Exception as e:
                print(f"note: intraday {ticker}: {e}")
            series, j, v = [], 0, None
            for d in dates:
                while j < len(pts) and pts[j][0] <= d:
                    v = pts[j][1]
                    j += 1
                series.append(sig(v))
            out[code] = {
                "ticker": ticker, "last": sig(last),
                "lastTime": (last_time or datetime.now(timezone.utc)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "atReport": series,
            }
            ok += 1
        except Exception as e:
            print(f"warning: {ticker}: {e}")
            if code in old and len(old[code].get("atReport", [])) == len(dates):
                out[code] = old[code]
    if ok == 0:
        raise SystemExit("All price requests failed - keeping previous prices.json")
    save("prices.json", {"updatedAt": now_iso(), "cotAsOf": cot["asOf"], "markets": out})
    print(f"Prices updated: {ok}/{len(MARKETS)}")


if __name__ == "__main__":
    main()
