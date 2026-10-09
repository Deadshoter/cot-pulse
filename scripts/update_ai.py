"""Write short AI arguments ("why funds are long/short") for every market to data/ai.json.

Runs only when a new COT report arrived (or with --force) and ANTHROPIC_API_KEY is set.
One request per market; a market that fails keeps its previous text.
"""
import json
import os
import sys

from common import MARKETS, NAMES, RELIABILITY, analyze, http_json, load, save, now_iso

MODEL = os.environ.get("AI_MODEL") or "claude-sonnet-5-5"
API = "https://api.anthropic.com/v1/messages"
REL = {1: "низкая", 2: "средняя", 3: "высокая"}


def prompt(code, cot, prices):
    m = cot["markets"][code]
    p = (prices.get("markets") or {}).get(code, {})
    at = p.get("atReport") or [None] * len(cot["dates"])
    a = analyze(m, at, p.get("last"))
    dates = cot["dates"]
    t = len(dates) - 1
    rows = "\n".join(
        f"{dates[i]}: фонды нетто {m['nc'][i]}, хеджеры нетто {m['cm'][i]}, открытый интерес {m['oi'][i]}, цена {at[i] if at[i] is not None else 'н/д'}"
        for i in range(t - 7, t + 1)
    )
    side_ru = "нетто-лонг" if a["side"] == "long" else "нетто-шорт"
    rel, rel_note = RELIABILITY[code]
    since = "н/д" if a["since_report"] is None else f"{a['since_report'] * 100:.1f}%"
    return f"""Ты объясняешь трейдеру отчёт COT (CFTC) простым языком, по-русски. Рынок: {NAMES[code]}.
Данные на {dates[t]} (позиции на вторник, опубликованы в пятницу):
- Крупные фонды (некоммерческие участники): {side_ru} {a['net']} контрактов; лонги {m['ls']['ncl']}, шорты {m['ls']['ncs']} ({round(a['pct_long'] * 100)}% позиций в лонг).
- Изменение нетто за неделю {a['d1']}, за 4 недели {a['d4']}.
- Положение нетто-позиции в диапазоне 3 лет: {round(a['index'])} из 100 (0 — максимальный шорт за 3 года, 100 — максимальный лонг).
- Хеджеры (коммерческие участники): {'нетто-лонг' if a['hedge'] == 'long' else 'нетто-шорт'} {a['hedge_net']}.
- Цена с даты отчёта: {since}.
- Показательность COT для этого рынка: {REL[rel]}. {rel_note}
Последние 8 недель:
{rows}

Задача: коротко объясни, почему по этим данным фонды в {'лонге' if a['side'] == 'long' else 'шорте'} и насколько это убедительно. Опирайся только на цифры выше — ты не знаешь новостей и реальных мотивов фондов, не придумывай их. Можно упомянуть общеизвестную структуру рынка (например, что хеджеры обычно против фондов). Без советов «покупать/продавать».
Ответь только JSON без пояснений: {{"args":["3 аргумента, каждый до 25 слов, с конкретными цифрами"],"use":"одно предложение: как трейдеру учитывать это на неделе","caveat":"одно предложение: главное ограничение этого вывода"}}"""


def ask(text, key):
    body = json.dumps({"model": MODEL, "max_tokens": 900, "messages": [{"role": "user", "content": text}]}).encode()
    j = http_json(API, data=body, timeout=120, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    out = "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")
    start, end = out.find("{"), out.rfind("}")
    res = json.loads(out[start:end + 1])
    if not isinstance(res.get("args"), list) or not res["args"]:
        raise ValueError("no args in answer")
    return {"args": [str(x) for x in res["args"][:4]], "use": str(res.get("use", "")), "caveat": str(res.get("caveat", ""))}


def main():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("ANTHROPIC_API_KEY not set — skipping AI arguments")
        return
    cot, prices = load("cot.json"), load("prices.json") or {}
    old = load("ai.json") or {}
    if old.get("cotAsOf") == cot["asOf"] and len(old.get("markets", {})) == len(MARKETS) and "--force" not in sys.argv:
        print("AI arguments already match this report")
        return
    markets, ok = {}, 0
    for code in MARKETS:
        try:
            markets[code] = ask(prompt(code, cot, prices), key)
            markets[code]["side"] = "long" if cot["markets"][code]["nc"][-1] >= 0 else "short"
            ok += 1
        except Exception as e:
            print(f"warning: AI for {code}: {e}")
            if code in old.get("markets", {}):
                markets[code] = {**old["markets"][code], "stale": True}
    save("ai.json", {"cotAsOf": cot["asOf"], "generatedAt": now_iso(), "model": MODEL, "markets": markets})
    print(f"AI arguments: {ok}/{len(MARKETS)}")


if __name__ == "__main__":
    main()
