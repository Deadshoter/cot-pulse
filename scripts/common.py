"""Shared settings and helpers for COT Pulse update scripts (Python 3.9+, stdlib only)."""
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# CFTC contract market code -> Yahoo Finance ticker
MARKETS = {
    "088691": "GC=F",      # Gold, COMEX
    "084691": "SI=F",      # Silver, COMEX
    "085692": "HG=F",      # Copper, COMEX
    "067651": "CL=F",      # WTI crude, NYMEX
    "023651": "NG=F",      # Natural gas, NYMEX
    "098662": "DX-Y.NYB",  # US Dollar Index, ICE
    "099741": "6E=F",      # Euro FX, CME
    "096742": "6B=F",      # British pound, CME
    "097741": "6J=F",      # Japanese yen, CME
    "232741": "6A=F",      # Australian dollar, CME
    "090741": "6C=F",      # Canadian dollar, CME
    "13874A": "ES=F",      # E-mini S&P 500, CME
    "209742": "NQ=F",      # E-mini Nasdaq 100, CME
    "133741": "BTC-USD",   # Bitcoin, CME
    "146021": "ETH-USD",   # Ether, CME
}

NAMES = {
    "088691": "Золото", "084691": "Серебро", "085692": "Медь", "067651": "Нефть WTI",
    "023651": "Природный газ", "098662": "Индекс доллара (DXY)", "099741": "Евро",
    "096742": "Британский фунт", "097741": "Японская иена", "232741": "Австралийский доллар",
    "090741": "Канадский доллар", "13874A": "S&P 500", "209742": "Nasdaq 100",
    "133741": "Bitcoin", "146021": "Ether",
}

# How representative exchange-traded COT positions are for the market (shown on the site, sent to the AI).
RELIABILITY = {
    "088691": (3, "COMEX — главная площадка фьючерсов на золото; не видны ETF и спрос центробанков."),
    "084691": (3, "COMEX — основной фьючерсный рынок серебра; рынок узкий, сдвиги позиций сильно двигают цену."),
    "085692": (2, "Основная торговля медью идёт на LME и SHFE, которых нет в отчёте CFTC."),
    "067651": (2, "Один физический контракт NYMEX; часть позиций — в других контрактах WTI и в Brent (ICE)."),
    "023651": (2, "Рынок, где доминируют производители; шорт фондов в газе бывает затяжным, цену сильно двигает погода."),
    "098662": (1, "Фьючерс на индекс доллара маленький; настроение по доллару точнее видно по сумме позиций в валютах."),
    "099741": (2, "Фьючерсы CME — малая часть валютного рынка, но позиции фондов — широко отслеживаемый индикатор."),
    "096742": (2, "Фьючерсы CME — малая часть валютного рынка, но позиции фондов — традиционный индикатор настроения."),
    "097741": (2, "Фьючерсы CME — малая часть валютного рынка; позиции по иене связаны с керри-трейдом и резко разворачиваются."),
    "232741": (2, "Фьючерсы CME — малая часть валютного рынка; индикатор аппетита к риску."),
    "090741": (2, "Фьючерсы CME — малая часть валютного рынка; позиции часто следуют за нефтью."),
    "13874A": (1, "Шорт фондов в S&P часто означает хедж портфеля акций или арбитраж, а не ставку на падение."),
    "209742": (2, "Часть позиций — хеджи портфелей, но спекулятивная составляющая выражена сильнее, чем в S&P 500."),
    "133741": (1, "CME — малая часть рынка биткоина; шорты фондов часто — арбитраж «купил ETF, продал фьючерс»."),
    "146021": (1, "CME — малая часть рынка эфира; позиции фондов во многом арбитражные, открытый интерес небольшой."),
}

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def http_json(url, headers=None, data=None, retries=3, timeout=30):
    """GET (or POST when data is given) and parse JSON, retrying transient failures."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:  # network hiccup, timeout, bad JSON
            last = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"request failed: {url[:120]}: {last}")


def load(name, default=None):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(name, obj):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------- metrics (mirror of the site's logic) ----------

def analyze(m, prices_at_dates=None, last_price=None):
    """m: market dict from cot.json. Returns the numbers the site and the AI use."""
    nc, cm, oi = m["nc"], m["cm"], m["oi"]
    t = len(nc) - 1
    net = nc[t]
    side = "long" if net >= 0 else "short"
    window = nc[-156:]
    lo, hi = min(window), max(window)
    index = 50.0 if hi == lo else (net - lo) / (hi - lo) * 100
    ls = m["ls"]
    pct_long = ls["ncl"] / max(1, ls["ncl"] + ls["ncs"])
    d1 = net - nc[t - 1]
    d4 = net - nc[t - 4]
    pr = None
    if prices_at_dates and last_price and prices_at_dates[t]:
        pr = last_price / prices_at_dates[t] - 1
    return {
        "net": net, "side": side, "index": index, "pct_long": pct_long,
        "d1": d1, "d4": d4, "hedge": "long" if cm[t] >= 0 else "short",
        "hedge_net": cm[t], "oi": oi[t], "since_report": pr,
    }
