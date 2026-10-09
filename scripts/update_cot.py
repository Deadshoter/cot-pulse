"""Fetch the CFTC Legacy futures-only COT report for all markets and write data/cot.json.

Cheap when nothing changed: it first asks CFTC for the latest report date and exits
if data/cot.json already has it. Pass --force to rebuild anyway.
Prints changed=true|false to $GITHUB_OUTPUT when running in GitHub Actions.
"""
import os
import sys
import urllib.parse
from datetime import date, timedelta

from common import MARKETS, http_json, load, save, now_iso

API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
HEADERS = {"X-App-Token": os.environ["CFTC_APP_TOKEN"]} if os.environ.get("CFTC_APP_TOKEN") else {}
CODES = ",".join(f"'{c}'" for c in MARKETS)
WEEKS = 160


def query(params):
    return http_json(API + "?" + urllib.parse.urlencode(params), headers=HEADERS)


def set_output(changed):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")


def main():
    force = "--force" in sys.argv
    current = load("cot.json")
    latest = query({
        "$select": "max(report_date_as_yyyy_mm_dd) as d",
        "$where": f"cftc_contract_market_code in({CODES})",
    })[0]["d"][:10]
    if current and current.get("asOf") == latest and not force:
        print(f"COT unchanged ({latest})")
        set_output(False)
        return

    since = (date.fromisoformat(latest) - timedelta(weeks=WEEKS)).isoformat()
    rows = query({
        "$select": ",".join([
            "report_date_as_yyyy_mm_dd", "cftc_contract_market_code", "open_interest_all",
            "noncomm_positions_long_all", "noncomm_positions_short_all",
            "comm_positions_long_all", "comm_positions_short_all",
        ]),
        "$where": f"cftc_contract_market_code in({CODES}) AND report_date_as_yyyy_mm_dd > '{since}'",
        "$order": "report_date_as_yyyy_mm_dd",
        "$limit": 50000,
    })

    by = {c: {} for c in MARKETS}
    for r in rows:
        c = r["cftc_contract_market_code"]
        if c in by:
            by[c][r["report_date_as_yyyy_mm_dd"][:10]] = r
    dates = sorted({d for c in by for d in by[c]})
    if len(dates) < 60:
        raise SystemExit(f"Too little history returned ({len(dates)} weeks) — refusing to overwrite data")

    markets = {}
    for c, rec in by.items():
        if not rec:
            print(f"warning: no rows for {c}")
            continue
        nc, cm, oi, prev = [], [], [], None
        for d in dates:
            r = rec.get(d, prev)  # carry forward if a market skipped a week
            if r is None:
                r = rec[min(rec)]
            nc.append(int(r["noncomm_positions_long_all"]) - int(r["noncomm_positions_short_all"]))
            cm.append(int(r["comm_positions_long_all"]) - int(r["comm_positions_short_all"]))
            oi.append(int(r["open_interest_all"]))
            prev = r
        last = rec.get(dates[-1], prev)
        markets[c] = {
            "nc": nc, "cm": cm, "oi": oi,
            "ls": {
                "ncl": int(last["noncomm_positions_long_all"]), "ncs": int(last["noncomm_positions_short_all"]),
                "cml": int(last["comm_positions_long_all"]), "cms": int(last["comm_positions_short_all"]),
            },
        }

    save("cot.json", {"asOf": dates[-1], "fetchedAt": now_iso(), "dates": dates, "markets": markets})
    print(f"COT updated to {dates[-1]} ({len(dates)} weeks, {len(markets)} markets)")
    set_output(True)


if __name__ == "__main__":
    main()
