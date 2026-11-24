"""One-off: which bookmaker and which price (closing or not) ESPN gives for NHL games, last season vs this."""
import json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sports import data, market
ua = json.loads(Path("config.json").read_text())["user_agent"]
days = [d.strftime("%Y%m%d") for d in list(pd.date_range("2025-10-10", "2026-04-15", freq="9D")) + list(pd.date_range("2026-10-02", "2026-11-22", freq="5D"))]
def board(d):
    try: return [(d, e) for e in market.finished_events(json.loads(data._get(market.SCOREBOARD.format(path="hockey/nhl", day=d), ua)))]
    except Exception as exc: print("board fail", d, exc); return []
with ThreadPoolExecutor(8) as ex: evs = [x for l in ex.map(board, days) for x in l]
def odds(de):
    d, e = de
    try: j = json.loads(data._get(market.CORE_ODDS.format(sport="hockey", league="nhl", id=e["id"]), ua))
    except Exception as exc: return [{"day": d, "id": e["id"], "err": str(exc)[:60]}]
    rows = []
    for i in j.get("items", []):
        p = i.get("provider") or {}
        h, a = i.get("homeTeamOdds") or {}, i.get("awayTeamOdds") or {}
        g = lambda t, k: ((t.get(k) or {}).get("moneyLine") or {}).get("american") if isinstance(t.get(k), dict) else None
        rows.append({"day": d, "id": e["id"], "home": e["home"], "away": e["away"], "provider": p.get("name"), "prio": p.get("priority"),
                     "ml_h": h.get("moneyLine"), "ml_a": a.get("moneyLine"), "open_h": g(h, "open"), "close_h": g(h, "close"),
                     "open_a": g(a, "open"), "close_a": g(a, "close"), "picked": market.closing_price({"items": [i]})})
    return rows or [{"day": d, "id": e["id"], "err": "no items"}]
with ThreadPoolExecutor(12) as ex: R = pd.DataFrame([r for l in ex.map(odds, evs) for r in l])
R.to_csv("probe/odds_check.csv", index=False)
R["season"] = (R.day < "20260801").map({True: "2025-26", False: "2026-27"})
print(R.groupby(["season", "provider", "prio"], dropna=False).size())
first = R.dropna(subset=["provider"]).sort_values("prio").groupby("id").head(1)
print(first.groupby("season").apply(lambda x: pd.Series({"games": len(x), "has_close": x.close_h.notna().mean(), "has_open": x.open_h.notna().mean(),
      "providers": x.provider.value_counts().to_dict()})))
print(first[["season","day","home","away","provider","ml_h","open_h","close_h","ml_a","open_a","close_a"]].groupby("season").head(6).to_string())
