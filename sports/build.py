"""Turn predictions into the page data and write the site."""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from sports import data, model


def _num(v, d=2):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), d)


def sport_json(key: str, cfg: dict, ua: str, today: date, min_home: int) -> dict:
    sc = cfg["sports"][key]
    cur, prev = data.nfl(sc, ua, today) if key == "nfl" else data.daily(key, sc, ua, today, min_home)
    P, home = model.predict_season(cur, prev, sc)
    groups = []
    for grp, g in P.groupby("group", sort=True):
        games = []
        for r in g.sort_values("kickoff").itertuples():
            item = {"t": r.kickoff, "a": r.away, "h": r.home, "ea": _num(r.ea, 1), "eh": _num(r.eh, 1), "ph": _num(r.ph, 4)}
            if r.done:
                item.update(as_=int(r.as_), hs=int(r.hs))
            if key == "nfl":
                item.update(sp=_num(r.spread, 1), tot=_num(r.total, 1), mla=_num(r.ml_away, 0), mlh=_num(r.ml_home, 0))
            games.append(item)
        groups.append({"g": str(grp), "games": games})
    open_groups = [x["g"] for x in groups if any("hs" not in m for m in x["games"])]
    played = P[P.done]
    hits = int(((played.ph > 0.5) == (played.hs > played.as_)).sum()) if len(played) else 0
    season = int(cur.season.iloc[0])
    label = f"{season}" if key == "nfl" else f"{season - 1}–{str(season)[-2:]}"
    return {"key": key, "label": sc["label"], "season": label, "unit": sc["unit"], "group_kind": sc["group"],
            "home_advantage": round(home, 2), "current": open_groups[0] if open_groups else (groups[-1]["g"] if groups else None),
            "played": int(len(played)), "fav_won": hits, "groups": groups}


def build(root: Path, cfg: dict, today: date) -> dict:
    out = {"updated": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "sports": [], "errors": []}
    for key in cfg["sports"]:
        try:
            out["sports"].append(sport_json(key, cfg, cfg["user_agent"], today, cfg["min_home_games_for_team"]))
        except Exception as exc:  # noqa: BLE001 - one league failing must not hide the others
            out["errors"].append(f"{cfg['sports'][key]['label']}: {exc}")
    return out


def write_site(root: Path, payload: dict) -> Path:
    web = root / "web"
    html = (web / "index.html").read_text(encoding="utf-8")
    css = (web / "style.css").read_text(encoding="utf-8")
    js = (web / "app.js").read_text(encoding="utf-8")
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    html = html.replace("/*CSS*/", css).replace("/*DATA*/", blob).replace("/*JS*/", js)
    site = root / "site"; site.mkdir(exist_ok=True)
    (site / "index.html").write_text(html, encoding="utf-8")
    return site / "index.html"
