"""Retail crowd sentiment from Myfxbook Community Outlook; writes data/sentiment.json.

For every symbol on the public outlook page: share of traders' volume in shorts and longs,
volume in lots and number of open positions. Myfxbook refreshes the page every few minutes.
Prints changed=true|false to $GITHUB_OUTPUT.
"""
import os
import re
import time
import urllib.request

from common import UA, load, save, now_iso

URL = "https://www.myfxbook.com/community/outlook"
ROW = re.compile(
    r'<td rowspan="2">([A-Z0-9.]{3,12})</td>\s*<td>Short</td>\s*<td[^>]*>(\d+)%</td>\s*<td[^>]*>([\d.,]+) lots</td>\s*<td[^>]*>(\d+)</td>'
    r'\s*</tr>\s*<tr>\s*<td>Long</td>\s*<td[^>]*>(\d+)%</td>\s*<td[^>]*>([\d.,]+) lots</td>\s*<td[^>]*>(\d+)</td>')


def fetch():
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f"Myfxbook request failed: {last}")


def set_output(changed):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")


def main():
    html = fetch()
    sym = {}
    for s, sp, sv, sn, lp, lv, ln in ROW.findall(html):
        sym[s] = {"s": int(sp), "l": int(lp), "sv": float(sv.replace(",", "")), "lv": float(lv.replace(",", "")),
                  "sn": int(sn), "ln": int(ln)}
    if len(sym) < 10:
        raise SystemExit(f"Parsed only {len(sym)} symbols - page format changed? Keeping previous file")
    old = load("sentiment.json") or {}
    if old.get("symbols") == sym:
        print(f"Sentiment unchanged ({len(sym)} symbols)")
        set_output(False)
        return
    save("sentiment.json", {"updatedAt": now_iso(), "source": "Myfxbook Community Outlook", "symbols": sym})
    print(f"Sentiment updated: {len(sym)} symbols")
    set_output(True)


if __name__ == "__main__":
    main()
