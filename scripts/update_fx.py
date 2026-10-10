"""Fetch exchange rates and spot prices for the lot calculator; write data/fx.json.

usd: how many US dollars one unit of each currency is worth (USD = 1).
px:  latest price for non-forex instruments (metals, indices, energy, crypto), used to
     pre-fill the entry price. Source: Yahoo Finance via yfinance. One batch request.
"""
import math

import yfinance as yf

from common import load, save, now_iso

FX = {  # currency -> (Yahoo ticker, True if the quote is USD per unit, False if units per USD)
    "EUR": ("EURUSD=X", True), "GBP": ("GBPUSD=X", True), "AUD": ("AUDUSD=X", True),
    "NZD": ("NZDUSD=X", True), "JPY": ("JPY=X", False), "CHF": ("CHF=X", False),
    "CAD": ("CAD=X", False), "CNY": ("CNY=X", False),
}
PX = {
    "XAUUSD": "GC=F", "XAGUSD": "SI=F", "XPTUSD": "PL=F", "COPPER": "HG=F",
    "US30": "^DJI", "US500": "^GSPC", "NAS100": "^NDX", "GER40": "^GDAXI", "UK100": "^FTSE", "JP225": "^N225",
    "USOIL": "CL=F", "UKOIL": "BZ=F", "NGAS": "NG=F", "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD",
}


def last_close(df, ticker):
    try:
        s = df[ticker]["Close"].dropna()
        v = float(s.iloc[-1])
        return None if math.isnan(v) else v
    except Exception:
        return None


def main():
    tickers = [t for t, _ in FX.values()] + list(PX.values())
    df = yf.download(tickers, period="5d", interval="1d", progress=False, threads=True, group_by="ticker", auto_adjust=False)
    old = load("fx.json") or {}
    usd, px = {"USD": 1.0}, {}
    for ccy, (t, direct) in FX.items():
        v = last_close(df, t)
        if v:
            usd[ccy] = round(v if direct else 1 / v, 8)
        elif ccy in old.get("usd", {}):
            usd[ccy] = old["usd"][ccy]
    for name, t in PX.items():
        v = last_close(df, t)
        if v:
            px[name] = float(f"{v:.6g}")
        elif name in old.get("px", {}):
            px[name] = old["px"][name]
    if len(usd) < 4:
        raise SystemExit("Too few exchange rates - keeping previous fx.json")
    save("fx.json", {"updatedAt": now_iso(), "usd": usd, "px": px})
    print(f"FX: {len(usd)} currencies, {len(px)} prices")


if __name__ == "__main__":
    main()
