"""Turn predictions into the page data and write the site."""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from sports import data, market, model


def _num(v, d=2):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), d)


def sport_json(key: str, cfg: dict, ua: str, today: date, min_home: int, store: dict | None = None, notes: list | None = None) -> dict:
    sc = cfg["sports"][key]
    cur, prev = data.nfl(sc, ua, today) if key == "nfl" else data.daily(key, sc, ua, today, min_home)
    if sc.get("three_way"):
        periods = data.nhl_period_types(sc, ua, cur, today)
        cur["pt"] = cur.gid.map(periods)
        cur["fhs"], cur["fas"] = cur.hs, cur.as_          # final score, kept for display
        # Fit on regulation goals: the overtime or shootout winner's extra goal is taken off.
        extra = cur.pt.isin(["OT", "SO"]) & cur.done
        cur.loc[extra & (cur.hs > cur.as_), "hs"] -= 1
        cur.loc[extra & (cur.as_ > cur.hs), "as_"] -= 1
    P, home = model.predict_season(cur, prev, sc)
    draw_rate = None
    if sc.get("three_way"):
        # Independent Poisson goals give too few regulation draws. Scale the draw chance so the
        # average matches the share of last season's games that went to overtime or a shootout.
        prev_types = data.nhl_period_types(sc, ua, prev, pd.Timestamp(prev.group.max()).date()) if len(prev) else {}
        known = [t for t in prev_types.values() if t]
        if len(known) >= 200:
            draw_rate = sum(t in ("OT", "SO") for t in known) / len(known)
            mean_d = float(P.px.mean())
            k = (draw_rate * (1 - mean_d)) / (mean_d * (1 - draw_rate))
            tot = P.p1 + k * P.px + P.p2
            P["p1"], P["px"], P["p2"] = P.p1 / tot, k * P.px / tot, P.p2 / tot
    store = {} if store is None else store
    if sc.get("espn_path"):
        # Bookmaker moneylines for games not started yet; a failure only costs today's prices.
        mine = [{"t": r.kickoff, "h": r.home, "a": r.away} for r in P.itertuples()]
        try:
            now = datetime.now(timezone.utc)
            market.refresh(store, key, sc["espn_path"], mine, sc.get("espn_aliases", {}), ua, today, now)
            market.backfill(store, key, sc["espn_path"], mine, sc.get("espn_aliases", {}), ua, today, cfg.get("closing_price_days", 7), now)
        except Exception as exc:  # noqa: BLE001
            if notes is not None:
                notes.append(f"{sc['label']} bookmaker prices: {exc}")
    book = store.get(key, {})
    groups = []
    for grp, g in P.groupby("group", sort=True):
        games = []
        for r in g.sort_values("kickoff").itertuples():
            item = {"t": r.kickoff, "a": r.away, "h": r.home, "ea": _num(r.ea, 1), "eh": _num(r.eh, 1), "ph": _num(r.ph, 4)}
            if r.done:
                item.update(as_=int(r.as_), hs=int(r.hs))
            if key == "nfl":
                item.update(sp=_num(r.spread, 1), tot=_num(r.total, 1), mla=_num(r.ml_away, 0), mlh=_num(r.ml_home, 0))
                bh, ba = market.ml_to_decimal(item["mlh"]), market.ml_to_decimal(item["mla"])
                if bh and ba:
                    item.update(bh=bh, ba=ba)
            else:
                b = book.get(market.key({"t": r.kickoff, "a": r.away, "h": r.home}))
                if b:
                    item.update(bh=b["bh"], ba=b["ba"])
            # Our home chance for the bookmaker's market: the moneyline, overtime included.
            pm = r.ph
            if sc.get("three_way"):
                pm = r.p1 + sc.get("overtime_home_share", 0.5) * r.px
            item["pm"] = _num(pm, 4)
            if sc.get("three_way"):
                item.update(p1=_num(r.p1, 4), px=_num(r.px, 4), p2=_num(r.p2, 4))
                if r.done:
                    item.update(as_=int(r.fas), hs=int(r.fhs))
                    pt = getattr(r, "pt", None)
                    if isinstance(pt, str):
                        item["pt"] = pt
                        item["reg"] = 1 if pt in ("OT", "SO") else (0 if r.fhs > r.fas else 2)
            games.append(item)
        groups.append({"g": str(grp), "games": games})
    open_groups = [x["g"] for x in groups if any("hs" not in m for m in x["games"])]
    played = P[P.done]
    fh = played.fhs if "fhs" in played else played.hs
    fa = played.fas if "fas" in played else played.as_
    hits = int(((played.ph > 0.5) == (fh > fa)).sum()) if len(played) else 0
    extra = {}
    if sc.get("three_way") and "pt" in played and played.pt.notna().any():
        known = played[played.pt.notna()]
        reg = known.pt.isin(["OT", "SO"]).map({True: 1, False: None})
        reg = reg.where(reg.notna(), (known.fhs < known.fas).map({False: 0, True: 2}))
        pick = known[["p1", "px", "p2"]].to_numpy().argmax(axis=1)
        extra = {"reg_known": int(len(known)), "reg_fav_won": int((pick == reg.astype(int).to_numpy()).sum()),
                 "reg_draws": int(known.pt.isin(["OT", "SO"]).sum())}
    season = int(cur.season.iloc[0])
    label = f"{season}" if key == "nfl" else f"{season - 1}–{str(season)[-2:]}"
    return {"key": key, "label": sc["label"], "season": label, "unit": sc["unit"], "group_kind": sc["group"],
            "home_advantage": round(home, 2), "current": open_groups[0] if open_groups else (groups[-1]["g"] if groups else None),
            "played": int(len(played)), "fav_won": hits, "groups": groups,
            "draw_rate_last_season": None if draw_rate is None else round(draw_rate, 3)} | extra


def build(root: Path, cfg: dict, today: date) -> dict:
    out = {"updated": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "sports": [], "errors": []}
    store_path = root / "data" / "market.json"
    store = market.load(store_path)
    for key in cfg["sports"]:
        try:
            out["sports"].append(sport_json(key, cfg, cfg["user_agent"], today, cfg["min_home_games_for_team"], store, out["errors"]))
        except Exception as exc:  # noqa: BLE001 - one league failing must not hide the others
            out["errors"].append(f"{cfg['sports'][key]['label']}: {exc}")
    market.save(store_path, store)
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
