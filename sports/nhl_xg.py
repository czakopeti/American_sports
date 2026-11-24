"""NHL team strength from expected goals (xG), adjusted for the opponent.

Hockey's counterpart of football's xG: every unblocked shot is worth the chance that a shot like it
(distance, angle, rebound, rush, shot type) goes in, from MoneyPuck.com's model. Goals are rare and
noisy; expected goals settle much sooner. The same opponent-adjusted fit as the goals model
(sports/model.py) runs on each game's xG for and against, all situations, flurry-adjusted (a quick
second shot after a save does not count twice). Last season's xG ratings start the season.

Data: MoneyPuck.com, game-level team data, updated nightly; free for non-commercial use with credit.
Downloaded at most once a day and kept in data/nhl_xg.csv so the hourly runs do not fetch it again.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from sports import model
from sports.data import _get

URL = "https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv"
COLS = ["gameId", "season", "gameDate", "team", "home_or_away", "situation", "position", "playoffGame", "flurryAdjustedxGoalsFor"]


def _download(ua: str, seasons: set[int]) -> pd.DataFrame:
    d = pd.read_csv(io.BytesIO(_get(URL, ua)), usecols=COLS, low_memory=False)
    d = d[(d.situation == "all") & (d.position == "Team Level") & (d.playoffGame == 0) & d.season.isin(seasons)]
    h = d[d.home_or_away == "HOME"][["gameId", "season", "gameDate", "team", "flurryAdjustedxGoalsFor"]]
    a = d[d.home_or_away == "AWAY"][["gameId", "team", "flurryAdjustedxGoalsFor"]]
    g = h.merge(a, on="gameId", suffixes=("_h", "_a"))
    return pd.DataFrame({"gid": g.gameId.astype("int64"), "season": g.season, "date": g.gameDate,
                         "home": g.team_h, "away": g.team_a,
                         "xh": g.flurryAdjustedxGoalsFor_h.round(3), "xa": g.flurryAdjustedxGoalsFor_a.round(3)})


def load(root: Path, ua: str, seasons: set[int], notes: list | None = None) -> pd.DataFrame:
    """xG per game for the given MoneyPuck seasons (the year a season starts), from the daily cache."""
    path = root / "data" / "nhl_xg.csv"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cached = pd.read_csv(path) if path.exists() else None
    fresh = cached is not None and str(cached.fetched.iloc[0]) == today and seasons <= set(cached.season)
    if fresh:
        return cached
    try:
        g = _download(ua, seasons)
        g["fetched"] = today
        g.to_csv(path, index=False)
        return g
    except Exception as exc:  # noqa: BLE001 - yesterday's copy is nearly as good
        if cached is not None and seasons <= set(cached.season):
            if notes is not None:
                notes.append(f"NHL expected goals: MoneyPuck not reached ({exc}); using the copy from {cached.fetched.iloc[0]}")
            return cached
        raise


def apply(P: pd.DataFrame, cur: pd.DataFrame, prev: pd.DataFrame, sc: dict, root: Path, ua: str, notes: list | None = None):
    """Replace the goals model's expected goals and chances with the xG model's. Returns (P, home advantage)."""
    season = int(cur.season.iloc[0])          # ours: the year the season ends
    xg = load(root, ua, {season - 1, season - 2}, notes)
    by = xg.set_index("gid")[["xh", "xa"]]

    def with_xg(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        j = out.gid.map(by.xh), out.gid.map(by.xa)
        out["hs"], out["as_"] = j
        out["done"] = out.done & out.hs.notna() & out.as_.notna()
        return out

    c2, p2 = with_xg(cur), with_xg(prev)
    if not p2.done.any():
        raise ValueError("no expected goals for last season")
    cfg = dict(sc) | {"prior_share": sc["xg"]["prior_share"], "prior_weight": sc["xg"]["prior_weight"], "home_advantage": "previous_season"}
    X, home = model.predict_season(c2, p2, cfg)
    out = P.copy()
    for col in ("eh", "ea", "ph", "p1", "px", "p2"):
        if col in X:
            out[col] = X[col]
    return out, home
