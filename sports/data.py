"""Download and normalise schedules and scores. One row per game:
season, group (NFL week or US Eastern date), kickoff (UTC ISO), away, home, as_, hs, done,
plus market lines for the NFL (closing spread, total and moneylines from nflverse)."""
from __future__ import annotations

import io
import json
import urllib.request
from datetime import date

import pandas as pd


def _get(url: str, ua: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def _season_end_year(today: date) -> int:
    return today.year + 1 if today.month >= 8 else today.year


def nfl(cfg: dict, ua: str, today: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    g = pd.read_csv(io.BytesIO(_get(cfg["games_url"], ua)), low_memory=False)
    g = g[g.game_type == "REG"].copy()
    started = g[pd.to_datetime(g.gameday) <= pd.Timestamp(today)]
    season = int(started.season.max())

    def norm(s: pd.DataFrame) -> pd.DataFrame:
        et = pd.to_datetime(s.gameday + " " + s.gametime.fillna("13:00")).dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward")
        return pd.DataFrame({
            "season": s.season.values, "group": s.week.astype(int).values,
            "kickoff": et.dt.tz_convert("UTC").dt.strftime("%Y-%m-%dT%H:%M:%SZ").values,
            "away": s.away_team.values, "home": s.home_team.values,
            "as_": s.away_score.values, "hs": s.home_score.values, "done": s.result.notna().values,
            "spread": s.spread_line.values, "total": s.total_line.values,
            "ml_away": s.away_moneyline.values, "ml_home": s.home_moneyline.values,
        })
    return norm(g[g.season == season]), norm(g[g.season == season - 1])


def _espn_like(cfg: dict, ua: str, year: int, kind: str) -> pd.DataFrame:
    d = pd.read_parquet(io.BytesIO(_get(cfg["schedule_url"].format(year=year), ua)))
    if kind == "nba":
        d = d[d.season_type == 2]
        out = pd.DataFrame({"away": d.away_abbreviation, "home": d.home_abbreviation,
                            "as_": pd.to_numeric(d.away_score, errors="coerce"), "hs": pd.to_numeric(d.home_score, errors="coerce"),
                            "done": d.status_type_completed == True, "t": pd.to_datetime(d.game_date_time, utc=True)})  # noqa: E712
    else:
        d = d[d.game_type == "R"]
        out = pd.DataFrame({"away": d.away_team_abbr, "home": d.home_team_abbr, "as_": d.away_score, "hs": d.home_score,
                            "done": d.home_score.notna(), "t": pd.to_datetime(d.game_time, utc=True), "gid": d.game_id.astype("int64")})
    out = out[out.t.notna()].copy()
    out["season"] = year
    out["group"] = out.t.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    out["kickoff"] = out.t.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return out.drop(columns="t").sort_values("kickoff").reset_index(drop=True)


def daily(kind: str, cfg: dict, ua: str, today: date, min_home: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    end = _season_end_year(today)
    cur = _espn_like(cfg, ua, end, kind)
    if not len(cur) or not cur.done.any():
        end -= 1
        cur = _espn_like(cfg, ua, end, kind)
    prev = _espn_like(cfg, ua, end - 1, kind)
    # Exhibition sides (All-Star teams and the like) play only a handful of games.
    teams = cur.home.value_counts()
    keep = set(teams[teams >= min(min_home, int(teams.max()))].index) if len(teams) else set()
    if not cur.done.any() or cur.home.value_counts().max() < min_home:
        keep = set(cur.home) | set(cur.away)
    cur = cur[cur.home.isin(keep) & cur.away.isin(keep)]
    pt = prev.home.value_counts(); pkeep = set(pt[pt >= min_home].index)
    prev = prev[prev.home.isin(pkeep) & prev.away.isin(pkeep)]
    return cur.reset_index(drop=True), prev.reset_index(drop=True)


def nhl_period_types(cfg: dict, ua: str, cur: pd.DataFrame, today: date) -> dict:
    """Last period of each finished game (REG, OT or SO) from the NHL's own schedule feed.

    Returns {} if the feed cannot be reached; the page then shows final scores only.
    """
    out: dict[int, str] = {}
    if not len(cur):
        return out
    day = pd.Timestamp(cur.group.min())
    end = pd.Timestamp(today) + pd.Timedelta(days=1)
    for _ in range(60):
        if day > end:
            break
        try:
            j = json.loads(_get(cfg["period_feed"].format(date=day.strftime("%Y-%m-%d")), ua))
        except Exception:  # noqa: BLE001 - optional detail
            return out
        for w in j.get("gameWeek", []):
            for g in w.get("games", []):
                t = (g.get("gameOutcome") or {}).get("lastPeriodType")
                if t:
                    out[int(g["id"])] = t
        nxt = j.get("nextStartDate")
        day = pd.Timestamp(nxt) if nxt else day + pd.Timedelta(days=7)
    return out
