"""Opponent-adjusted attack and defence from scores, by ridge least squares.

Expected score for the home side = level + attack[home] - defence[away] + home/2,
and for the away side = level + attack[away] - defence[home] - home/2. Before the
season's games pile up, every club is pulled towards a share of last season's
final rating. Each group (NFL week, NBA/NHL date) is predicted only from earlier groups.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def fit(games: pd.DataFrame, teams: list[str], prior_att: np.ndarray, prior_def: np.ndarray, weight: float, home: float):
    ix = {t: i for i, t in enumerate(teams)}
    n, N = len(games), len(teams)
    A = np.zeros((2 * n, 2 * N + 1)); y = np.zeros(2 * n)
    h = games.home.map(ix).to_numpy(); a = games.away.map(ix).to_numpy(); r = np.arange(n)
    A[2 * r, 0] = 1; A[2 * r, 1 + h] = 1; A[2 * r, 1 + N + a] = -1; y[2 * r] = games.hs.to_numpy(float) - home / 2
    A[2 * r + 1, 0] = 1; A[2 * r + 1, 1 + a] = 1; A[2 * r + 1, 1 + N + h] = -1; y[2 * r + 1] = games.as_.to_numpy(float) + home / 2
    R = np.zeros((2 * N, 2 * N + 1)); R[:, 1:] = math.sqrt(weight) * np.eye(2 * N)
    rhs = np.concatenate([y, math.sqrt(weight) * np.concatenate([prior_att, prior_def])])
    s = np.linalg.lstsq(np.vstack([A, R]), rhs, rcond=None)[0]
    att, de = s[1:N + 1], s[N + 1:]
    return float(s[0]), att - att.mean(), de - de.mean()


def win_normal(margin: float, sd: float) -> float:
    return 0.5 * (1 + math.erf(margin / (sd * math.sqrt(2))))


def win_poisson(lh: float, la: float, ot_home: float) -> float:
    lh, la = max(lh, 0.2), max(la, 0.2)
    ph = [math.exp(-lh) * lh ** k / math.factorial(k) for k in range(16)]
    pa = [math.exp(-la) * la ** k / math.factorial(k) for k in range(16)]
    win = sum(ph[i] * pa[j] for i in range(16) for j in range(i))
    tie = sum(ph[i] * pa[i] for i in range(16))
    return win + tie * ot_home


def three_way(lh: float, la: float) -> tuple[float, float, float]:
    """Regulation-time home win, draw, away win from independent Poisson goals."""
    lh, la = max(lh, 0.2), max(la, 0.2)
    ph = [math.exp(-lh) * lh ** k / math.factorial(k) for k in range(16)]
    pa = [math.exp(-la) * la ** k / math.factorial(k) for k in range(16)]
    w = sum(ph[i] * pa[j] for i in range(16) for j in range(i))
    d = sum(ph[i] * pa[i] for i in range(16))
    return w, d, 1 - w - d


def predict_season(cur: pd.DataFrame, prev: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, float]:
    teams = sorted(set(cur.home) | set(cur.away))
    pdone = prev[prev.done & prev.home.isin(teams) & prev.away.isin(teams)]
    if cfg["home_advantage"] == "previous_season":
        home = float((pdone.hs - pdone.as_).mean()) if len(pdone) else 0.0
    else:
        home = float(cfg["home_advantage"])
    if len(pdone):
        lvl0, att0, def0 = fit(pdone, teams, np.zeros(len(teams)), np.zeros(len(teams)), 1e-3, home)
    else:
        lvl0, att0, def0 = float((cur[cur.done].hs.mean() + cur[cur.done].as_.mean()) / 2), np.zeros(len(teams)), np.zeros(len(teams))
    pa, pd_ = cfg["prior_share"] * att0, cfg["prior_share"] * def0
    done = cur[cur.done]
    cache: dict[int, tuple] = {}
    rows = []
    for grp in sorted(cur.group.unique()):
        past = done[done.group < grp]
        k = len(past)
        if k not in cache:
            cache[k] = fit(past, teams, pa, pd_, cfg["prior_weight"], home) if k else (lvl0, pa, pd_)
        lvl, att, de = cache[k]
        ix = {t: i for i, t in enumerate(teams)}
        for g in cur[cur.group == grp].itertuples():
            eh = lvl + att[ix[g.home]] - de[ix[g.away]] + home / 2
            ea = lvl + att[ix[g.away]] - de[ix[g.home]] - home / 2
            row = {"idx": g.Index, "eh": eh, "ea": ea}
            if cfg["unit"] == "goals":
                row["ph"] = win_poisson(eh, ea, cfg.get("overtime_home_share", 0.5))
                if cfg.get("three_way"):
                    row["p1"], row["px"], row["p2"] = three_way(eh, ea)
            else:
                row["ph"] = win_normal(eh - ea, cfg["margin_sd"])
            rows.append(row)
    P = pd.DataFrame(rows).set_index("idx")
    return cur.join(P), home
