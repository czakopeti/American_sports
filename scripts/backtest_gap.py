"""One-off: our pre-game win chances and closing moneylines for this season and last, per sport.

Writes probe/backtest_<sport>.csv. NFL prices come from nflverse; NBA and NHL from ESPN's odds history.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sports import data, market, model  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads((ROOT / "config.json").read_text())
ua = cfg["user_agent"]
out_dir = ROOT / "probe"
out_dir.mkdir(exist_ok=True)


def nhl_adjust(sc, cur, prev):
    if not sc.get("three_way"):
        return cur
    periods = data.nhl_period_types(sc, ua, cur, pd.Timestamp(cur.group.max()).date() if len(cur) else date.today())
    cur = cur.copy()
    cur["pt"] = cur.gid.map(periods)
    cur["fhs"], cur["fas"] = cur.hs, cur.as_
    extra = cur.pt.isin(["OT", "SO"]) & cur.done
    cur.loc[extra & (cur.hs > cur.as_), "hs"] -= 1
    cur.loc[extra & (cur.as_ > cur.hs), "as_"] -= 1
    return cur


def chances(sc, cur, prev):
    P, _ = model.predict_season(cur, prev, sc)
    if sc.get("three_way"):
        prev_types = data.nhl_period_types(sc, ua, prev, pd.Timestamp(prev.group.max()).date()) if len(prev) else {}
        known = [t for t in prev_types.values() if t]
        if len(known) >= 200:
            dr = sum(t in ("OT", "SO") for t in known) / len(known)
            md = float(P.px.mean())
            k = (dr * (1 - md)) / (md * (1 - dr))
            tot = P.p1 + k * P.px + P.p2
            P["p1"], P["px"], P["p2"] = P.p1 / tot, k * P.px / tot, P.p2 / tot
        P["pm"] = P.p1 + sc.get("overtime_home_share", 0.5) * P.px
        P["hs"], P["as_"] = P.fhs, P.fas
    else:
        P["pm"] = P.ph
    return P


def espn_prices(sc, P):
    path = sc["espn_path"]
    sp, lg = path.split("/")
    games = [{"t": r.kickoff, "h": r.home, "a": r.away} for r in P.itertuples()]
    days = sorted(set(P.group))

    def board(d):
        try:
            return market.finished_events(json.loads(data._get(market.SCOREBOARD.format(path=path, day=d.replace("-", "")), ua)))
        except Exception:
            return []
    with ThreadPoolExecutor(8) as ex:
        evs = [e for lst in ex.map(board, days) for e in lst]
    pairs = market.match(evs, games, sc.get("espn_aliases", {}))

    def price(pair):
        r, g = pair
        try:
            c = market.closing_price(json.loads(data._get(market.CORE_ODDS.format(sport=sp, league=lg, id=r["id"]), ua)))
        except Exception:
            c = None
        return market.key(g), c
    with ThreadPoolExecutor(12) as ex:
        res = dict(ex.map(price, pairs))
    print(path, "days", len(days), "events", len(evs), "matched", len(pairs), "priced", sum(1 for v in res.values() if v), flush=True)
    return res


for key in ("nfl", "nba", "nhl"):
    sc = cfg["sports"][key]
    rows = []
    if key == "nfl":
        g = pd.read_csv(__import__("io").BytesIO(data._get(sc["games_url"], ua)), low_memory=False)
        g = g[g.game_type == "REG"]
        today = date.today()
        seasons = []
        cur, prev = data.nfl(sc, ua, today)
        s = int(cur.season.iloc[0])
        pprev = data.nfl(sc, ua, date(s - 1, 12, 1))  # last season and the one before
        seasons = [(cur, prev), pprev]
    else:
        cur, prev = data.daily(key, sc, ua, date.today(), cfg["min_home_games_for_team"])
        last_end = int(cur.season.iloc[0]) - 1
        pcur, pprev = data.daily(key, sc, ua, date(last_end, 3, 1), cfg["min_home_games_for_team"])
        seasons = [(cur, prev), (pcur, pprev)]
    for c, p in seasons:
        c = nhl_adjust(sc, c, p) if key == "nhl" else c
        p = nhl_adjust(sc, p, p.iloc[:0]) if key == "nhl" and len(p) else p
        P = chances(sc, c, p)
        P = P[P.done]
        if key == "nfl":
            P["bh"] = P.ml_home.map(market.ml_to_decimal)
            P["ba"] = P.ml_away.map(market.ml_to_decimal)
        else:
            pr = espn_prices(sc, P)
            P["bh"] = [((pr.get(market.key({"t": r.kickoff, "a": r.away, "h": r.home})) or {}).get("bh")) for r in P.itertuples()]
            P["ba"] = [((pr.get(market.key({"t": r.kickoff, "a": r.away, "h": r.home})) or {}).get("ba")) for r in P.itertuples()]
        for r in P.itertuples():
            rows.append({"season": int(r.season), "group": r.group, "t": r.kickoff, "away": r.away, "home": r.home,
                         "as": int(r.as_), "hs": int(r.hs), "pm": round(float(r.pm), 4), "bh": r.bh, "ba": r.ba})
    pd.DataFrame(rows).to_csv(out_dir / f"backtest_{key}.csv", index=False)
    print(key, len(rows), "games", flush=True)
