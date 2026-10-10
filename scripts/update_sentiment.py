"""Retail crowd sentiment: Dukascopy SWFX Sentiment Index; writes data/sentiment.json.

For each instrument: share of Dukascopy clients' volume in longs and shorts (percent),
now and 6 hours / 1 day / 5 days ago. Prints changed=true|false to $GITHUB_OUTPUT.
"""
import json
import os
import time
import urllib.request

from common import UA, load, save, now_iso

URL = "https://jetta.dukascopy.com/v1/sentiments/instruments"
CODES = ["XAU-USD", "XAG-USD", "COPPER.CMD-USD", "LIGHT.CMD-USD", "GAS.CMD-USD", "DOLLAR.IDX-USD",
         "EUR-USD", "GBP-USD", "USD-JPY", "AUD-USD", "USD-CAD", "USA500.IDX-USD", "USATECH.IDX-USD",
         "BTC-USD", "ETH-USD"]


def fetch():
    body = json.dumps({"instrumentCodes": CODES}).encode()
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(URL, data=body, method="POST", headers={
                "User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json",
                "Origin": "https://widgets.dukascopy.com", "Referer": "https://widgets.dukascopy.com/"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f"Dukascopy request failed: {last}")


def set_output(changed):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")


def main():
    data = fetch()
    sym = {}
    for it in data.get("instrumentIndexes", []):
        ix = it.get("indexes") or {}
        last = ix.get("LAST")
        if not last:
            continue
        row = {"l": last["long"], "s": last["short"]}
        for k, short in (("SIX_HOURS", "l6h"), ("ONE_DAY", "l1d"), ("FIVE_DAYS", "l5d")):
            if ix.get(k):
                row[short] = ix[k]["long"]
        sym[it["instrumentCode"]] = row
    if len(sym) < 8:
        raise SystemExit(f"Got only {len(sym)} instruments - API changed? Keeping previous file")
    old = load("sentiment.json") or {}
    if old.get("symbols") == sym:
        print(f"Sentiment unchanged ({len(sym)} instruments)")
        set_output(False)
        return
    save("sentiment.json", {"updatedAt": now_iso(), "source": "Dukascopy SWFX Sentiment Index", "symbols": sym})
    print(f"Sentiment updated: {len(sym)} instruments")
    set_output(True)


if __name__ == "__main__":
    main()
