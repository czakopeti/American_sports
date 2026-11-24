"""NFL team strength from EPA (expected points added) per play, adjusted for the opponent.

The NFL counterpart of expected goals: every run and pass is worth the change in the expected points of
the drive. Each club gets an offence rating (EPA per play above average, given the defences it faced) and a
defence rating (EPA per play allowed above average, given the offences it faced), found by iterating the
two together. Recent weeks count more; last season's ratings, shrunk toward average, start the season.
A rating gap becomes an expected margin and a win chance with a fit from earlier seasons
(config/nfl_epa.json, rebuilt with scripts/nfl_epa_prior.py).
"""
from __future__ import annotations

import io
import json
import math
from pathlib import Path

import pandas as pd

from sports.data import _get

PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{year}.parquet"
COLS = ["game_id", "season", "week", "season_type", "home_team", "away_team", "posteam", "epa", "wp",
        "home_score", "away_score", "qb_kneel", "qb_spike", "pass", "rush"]


def game_epa(pbp: pd.DataFrame) -> pd.DataFrame:
    """One row per regular-season game: week, home, away, final score and each side's EPA per play.

    Runs and passes only, kneels and spikes out, and only while the game is in doubt
    (win probability 5-95%), so garbage time does not count.
    """
    p = pbp[pbp.season_type == "REG"]
    res = p.groupby("game_id").agg(season=("season", "first"), week=("week", "first"), home=("home_team", "first"),
                                   away=("away_team", "first"), hs=("home_score", "max"), as_=("away_score", "max")).reset_index()
    q = p[((p["pass"] == 1) | (p["rush"] == 1)) & p.epa.notna() & (p.qb_kneel != 1) & (p.qb_spike != 1) & p.posteam.notna()]
    q = q[(q.wp >= 0.05) & (q.wp <= 0.95)]
    off = q.groupby(["game_id", "posteam"]).epa.mean().to_dict()
    res["eh"] = [off.get((g, h)) for g, h in zip(res.game_id, res.home)]
    res["ea"] = [off.get((g, a)) for g, a in zip(res.game_id, res.away)]
    return res.dropna(subset=["eh", "ea"]).sort_values("week")


def load_season(year: int, ua: str) -> pd.DataFrame:
    return game_epa(pd.read_parquet(io.BytesIO(_get(PBP_URL.format(year=year), ua)), columns=COLS))


def ratings(games: pd.DataFrame, teams: list[str], upto: int, prior: dict, tau: float, k: float, iters: int = 8) -> tuple[dict, dict]:
    """Offence and defence ratings from the games before week `upto` (EPA per play above average)."""
    ms = games[games.week < upto]
    avg = float(pd.concat([ms.eh, ms.ea]).mean()) if len(ms) else 0.0
    o = {t: 0.0 for t in teams}
    d = {t: 0.0 for t in teams}
    by: dict[str, list] = {t: [] for t in teams}
    for r in ms.itertuples():
        q = math.exp(-(upto - 1 - r.week) / tau)
        if r.home in by:
            by[r.home].append((r.away, q, r.eh - avg, r.ea - avg))
        if r.away in by:
            by[r.away].append((r.home, q, r.ea - avg, r.eh - avg))
    p = lambda t: prior.get(t, [0.0, 0.0])  # noqa: E731
    for _ in range(iters):
        for t in teams:
            n, w = k * p(t)[0], k
            for opp, q, f, _a in by[t]:
                n += q * (f - d.get(opp, 0.0)); w += q
            o[t] = n / w
        m = sum(o.values()) / len(o)
        o = {t: v - m for t, v in o.items()}
        for t in teams:
            n, w = k * p(t)[1], k
            for opp, q, _f, a in by[t]:
                n += q * (a - o.get(opp, 0.0)); w += q
            d[t] = n / w
        m = sum(d.values()) / len(d)
        d = {t: v - m for t, v in d.items()}
    return o, d


def net(o: dict, d: dict, home: str, away: str) -> float:
    """How much more EPA per play the home side should gain than the away side."""
    return (o.get(home, 0.0) + d.get(away, 0.0)) - (o.get(away, 0.0) + d.get(home, 0.0))


def win(margin: float, sd: float) -> float:
    return 0.5 * (1 + math.erf(margin / (sd * math.sqrt(2))))


def apply(P: pd.DataFrame, root: Path, ua: str) -> pd.DataFrame:
    """Replace the points model's win chances for the current season with the EPA model's.

    The expected total stays the points model's; the expected margin comes from EPA, so the
    expected score splits that total by the EPA margin.
    """
    m = json.loads((root / "config" / "nfl_epa.json").read_text(encoding="utf-8"))
    season = int(P.season.iloc[0])
    if season != m["season"]:
        raise ValueError(f"EPA prior is for {m['season']}, the season is {season}: run scripts/nfl_epa_prior.py")
    games = load_season(season, ua)
    teams = sorted(set(P.home) | set(P.away))
    out = P.copy()
    cache: dict[int, tuple] = {}
    for i, r in out.iterrows():
        wk = int(r.group)
        if wk not in cache:
            cache[wk] = ratings(games, teams, wk, m["prior"], m["tau"], m["k"])
        o, d = cache[wk]
        mg = m["c"] * net(o, d, r.home, r.away) + m["hfa"]
        total = r.eh + r.ea
        out.at[i, "ph"] = win(mg, m["sd"])
        out.at[i, "eh"], out.at[i, "ea"] = (total + mg) / 2, (total - mg) / 2
    return out
