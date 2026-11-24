"""Turn predictions into the page data and write the site."""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from sports import data, epa, market, model, nhl_xg


def _num(v, d=2):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), d)


def side_pick(pm: float, bh: float, ba: float, rule: dict) -> str | None:
    """A rule on one named side ("bet": "h" or "a"), read off the numbers as the table shows them
    (one decimal): our chance incl. overtime above "min_ours" (%), and the gap (ours minus the
    bookmaker's, margin taken out, in points) above "gap_above", below "gap_below" or at most "gap_at_most"."""
    ih, ia = 1 / bh, 1 / ba
    qh = ih / (ih + ia)
    side = rule["bet"]
    ours = pm if side == "h" else 1 - pm
    book = qh if side == "h" else 1 - qh
    o, g = round(ours * 100, 1), round((ours - book) * 100, 1)
    if "min_ours" in rule and not o > rule["min_ours"]:
        return None
    if "gap_above" in rule and not g > rule["gap_above"]:
        return None
    if "gap_below" in rule and not g < rule["gap_below"]:
        return None
    if "gap_at_most" in rule and not g <= rule["gap_at_most"]:
        return None
    return side


def rule_pick(pm: float, bh: float, ba: float, rule: dict) -> str | None:
    """Our favourite, when the bookmaker (margin taken out) rates it between min_gap and max_gap above us.

    With "side": "a" (or "h") only when our favourite is the away (or home) team; with "min_ours" only when
    our chance for it is above that.
    """
    ih, ia = 1 / bh, 1 / ba
    qh = ih / (ih + ia)
    home = pm >= 0.5
    if rule.get("side") and rule["side"] != ("h" if home else "a"):
        return None
    ours, theirs = (pm, qh) if home else (1 - pm, 1 - qh)
    gap = theirs - ours
    if rule.get("min_ours") is not None and not ours > rule["min_ours"]:
        return None
    if rule["min_gap"] <= gap < rule["max_gap"]:
        return "h" if home else "a"
    return None


ROOT_DIR = Path(__file__).resolve().parents[1]


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
    if sc.get("epa"):
        # NFL: win chances and the expected margin from opponent-adjusted EPA per play.
        try:
            P = epa.apply(P, ROOT_DIR, ua)
            home = json.loads((ROOT_DIR / "config" / "nfl_epa.json").read_text(encoding="utf-8"))["hfa"]
        except Exception as exc:  # noqa: BLE001 - the points model still stands
            if notes is not None:
                notes.append(f"{sc['label']} EPA model not used this time ({exc}); showing the points model")
    if sc.get("xg"):
        # NHL: expected goals and chances from opponent-adjusted expected goals (MoneyPuck.com).
        try:
            P, home = nhl_xg.apply(P, cur, prev, sc, ROOT_DIR, ua, notes)
        except Exception as exc:  # noqa: BLE001 - the goals model still stands
            if notes is not None:
                notes.append(f"{sc['label']} expected-goals model not used this time ({exc}); showing the goals model")
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
    rules = sc.get("rules") or ([sc["rule"]] if sc.get("rule") else [])
    records: list[list] = [[] for _ in rules]
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
            for rule, record in zip(rules, records):
                if not (item.get("bh") and item.get("ba")):
                    break
                pick = (side_pick if "bet" in rule else rule_pick)(pm, item["bh"], item["ba"], rule)
                if not pick:
                    continue
                item.setdefault("picks", []).append([rule["name"], pick])
                if not r.done:
                    continue
                # Final score: overtime and shootout included (NHL, where hs/as_ hold the regulation score).
                hs, as_ = int(getattr(r, "fhs", r.hs)), int(getattr(r, "fas", r.as_))
                pt = getattr(r, "pt", None)
                if rule.get("market") == "reg":
                    # The 60-minute result, paid at our own 60-minute odds (no bookmaker three-way prices here).
                    if not isinstance(pt, str):
                        continue
                    won = pt not in ("OT", "SO") and ((hs > as_) if pick == "h" else (as_ > hs))
                    price = round(1 / (r.p1 if pick == "h" else r.p2), 3)
                else:
                    won = (hs > as_) if pick == "h" else (as_ > hs)
                    price = item["bh"] if pick == "h" else item["ba"]
                rec = {"t": r.kickoff, "a": r.away, "h": r.home, "side": pick, "price": price,
                       "as_": as_, "hs": hs, "won": bool(won), "profit": round(price - 1 if won else -1, 3)}
                if isinstance(pt, str) and pt != "REG":
                    rec["pt"] = pt
                record.append(rec)
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
    if rules:
        extra["rules"] = [dict(rule) | {"record": record} for rule, record in zip(rules, records)]
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
