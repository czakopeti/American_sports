"""One-off: opening and closing moneylines (first-priority bookmaker on ESPN) for this season's NBA and NHL games."""
import json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sports import data, market
ua = json.loads(Path("config.json").read_text())["user_agent"]
SPORTS = {"nba": ("basketball/nba", "basketball", "nba", "2026-10-19"), "nhl": ("hockey/nhl", "hockey", "nhl", "2026-09-30")}
def dec(t, k):
    x = (t.get(k) or {}) if isinstance(t.get(k), dict) else {}
    ml = x.get("moneyLine") or {}
    if ml.get("decimal"): return float(ml["decimal"])
    return market.ml_to_decimal(ml.get("american"))
rows = []
for sp, (path, s1, s2, start) in SPORTS.items():
    days = [d.strftime("%Y%m%d") for d in pd.date_range(start, "2026-11-24")]
    def board(d):
        try: return [e for e in market.finished_events(json.loads(data._get(market.SCOREBOARD.format(path=path, day=d), ua)))]
        except Exception as exc: print("board fail", sp, d, exc); return []
    with ThreadPoolExecutor(8) as ex: evs = [e for l in ex.map(board, days) for e in l]
    evs = list({e["id"]: e for e in evs}.values())
    def odds(e):
        try: j = json.loads(data._get(market.CORE_ODDS.format(sport=s1, league=s2, id=e["id"]), ua))
        except Exception as exc: return dict(e, sport=sp, err=str(exc)[:80])
        items = sorted(j.get("items", []), key=lambda i: (i.get("provider") or {}).get("priority", 99))
        for i in items:
            name = (i.get("provider") or {}).get("name", "")
            if "Live" in name: continue
            h, a = i.get("homeTeamOdds") or {}, i.get("awayTeamOdds") or {}
            r = dict(e, sport=sp, book=name, oh=dec(h, "open"), oa=dec(a, "open"), ch=dec(h, "close"), ca=dec(a, "close"))
            if r["ch"] and r["ca"]: return r
        return dict(e, sport=sp, err="no prices")
    with ThreadPoolExecutor(12) as ex: rows += list(ex.map(odds, evs))
df = pd.DataFrame(rows); df.to_csv("probe/open_prices.csv", index=False)
print(df.groupby("sport").agg(n=("id", "size"), open=("oh", "count"), close=("ch", "count")))
