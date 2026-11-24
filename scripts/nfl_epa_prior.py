"""Build config/nfl_epa.json for a new NFL season: last season's ratings and the margin fit.

Run once a year, before the season starts: python scripts/nfl_epa_prior.py 2026
It plays the two previous seasons week by week with sports/epa.py, carries the final ratings forward
(shrunk toward average), and fits expected margin = c x EPA gap + home advantage on every game, with the
standard deviation of the misses for the win chance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sports import epa  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
season = int(sys.argv[1])
TAU, K, SHRINK = 4.0, 6.0, 0.7  # chosen on the 2025 season, checked on 2026 (see README)
ua = json.loads((ROOT / "config.json").read_text())["user_agent"]

prior: dict = {}
xs, ys = [], []
for year in (season - 2, season - 1):
    g = epa.load_season(year, ua)
    teams = sorted(set(g.home) | set(g.away))
    for wk in sorted(g.week.unique()):
        o, d = epa.ratings(g, teams, wk, prior, TAU, K)
        for r in g[g.week == wk].itertuples():
            xs.append(epa.net(o, d, r.home, r.away)); ys.append(r.hs - r.as_)
    o, d = epa.ratings(g, teams, 99, prior, TAU, K)
    prior = {t: [round(o[t] * SHRINK, 5), round(d[t] * SHRINK, 5)] for t in teams}

X = np.c_[xs, np.ones(len(xs))]
c, h = np.linalg.lstsq(X, np.array(ys, float), rcond=None)[0]
sd = float(np.std(np.array(ys) - X @ [c, h]))
out = {"season": season, "tau": TAU, "k": K, "shrink": SHRINK, "c": round(float(c), 3), "hfa": round(float(h), 3),
       "sd": round(sd, 3), "fit_games": len(ys), "prior": prior}
(ROOT / "config" / "nfl_epa.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
print({k: v for k, v in out.items() if k != "prior"})
