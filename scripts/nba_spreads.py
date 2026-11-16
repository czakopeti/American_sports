"""One-off: closing DraftKings spreads for every NBA regular-season game, last season and this one."""
import csv, json, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sports import data, market  # noqa: E402

ua = json.loads(Path("config.json").read_text())["user_agent"]
ranges = [(date(2025, 10, 20), date(2026, 4, 14)), (date(2026, 10, 19), date.today())]
days = [a + timedelta(days=i) for a, b in ranges for i in range((b - a).days + 1)]


def board(d):
    try:
        j = json.loads(data._get(market.SCOREBOARD.format(path="basketball/nba", day=d.strftime("%Y%m%d")), ua))
    except Exception:
        return []
    out = []
    for e in j.get("events", []):
        if (e.get("season") or {}).get("type") != 2:
            continue
        c = e["competitions"][0]
        if not c["status"]["type"].get("completed"):
            continue
        side = {t["homeAway"]: t for t in c["competitors"]}
        out.append({"id": e["id"], "date": d.isoformat(), "season": e["season"]["year"],
                     "home": side["home"]["team"]["abbreviation"], "away": side["away"]["team"]["abbreviation"],
                     "hs": int(side["home"]["score"]), "as": int(side["away"]["score"])})
    return out


with ThreadPoolExecutor(8) as ex:
    games = [g for lst in ex.map(board, days) for g in lst]
print("games", len(games), flush=True)


def line(t, when):
    ps = ((t.get(when) or {}).get("pointSpread") or {}).get("american")
    od = ((t.get(when) or {}).get("spread") or {}).get("decimal")
    try:
        return float(str(ps).replace("+", "")) if ps not in (None, "") else None, float(od) if od else None
    except ValueError:
        return None, None


def odds(g):
    try:
        j = json.loads(data._get(market.CORE_ODDS.format(sport="basketball", league="nba", id=g["id"]), ua))
    except Exception:
        return g
    items = sorted(j.get("items", []), key=lambda i: (i.get("provider") or {}).get("priority", 99))
    for i in items:
        h, a = i.get("homeTeamOdds") or {}, i.get("awayTeamOdds") or {}
        hl, ho = line(h, "close")
        al, ao = line(a, "close")
        if hl is None and i.get("spread") is not None:
            # "spread" is the home line in ESPN's list; the favourite flag gives its sign.
            hl = -abs(float(i["spread"])) if h.get("favorite") else abs(float(i["spread"]))
        if hl is None:
            continue
        ol, _ = line(h, "open")
        g.update(home_line=hl, home_odds=ho or 1.91, away_odds=ao or 1.91, open_home_line=ol, book=(i.get("provider") or {}).get("name"))
        break
    return g


with ThreadPoolExecutor(12) as ex:
    games = list(ex.map(odds, games))
Path("probe").mkdir(exist_ok=True)
keys = ["season", "date", "id", "away", "home", "as", "hs", "home_line", "home_odds", "away_odds", "open_home_line", "book"]
with open("probe/nba_spreads.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    w.writerows(sorted(games, key=lambda g: (g["date"], g["id"])))
print("with lines", sum(1 for g in games if g.get("home_line") is not None), flush=True)
