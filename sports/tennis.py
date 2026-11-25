"""Tennis picks for the Bets page, read from the tennis dashboard (czakopeti/tennis), which is not changed.

The rule: back the worse-ranked player when the bookmaker's odds are at or above the dashboard's fair
odds and at most `max_odds`. The dashboard's files: data/todays_analysis.json (today's and tomorrow's
matches: ranks, fair odds odds1/odds2, bookmaker odds book_odds_home/away for player 1/2) and
data/history/<date>.json (the same matches with the winner once known). Match times are Budapest time.
Like the other leagues, a pick goes into the bet log when it is first shown before the match, at that
price, and stays even if the signal goes away.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sports.data import _get

RAW = "https://raw.githubusercontent.com/czakopeti/tennis/main/{path}"
BUD = ZoneInfo("Europe/Budapest")


def side_of(m: dict, max_odds: float) -> int | None:
    """1 or 2: the worse-ranked player, if the rule backs him or her; else None."""
    r1, r2 = m.get("rank1"), m.get("rank2")
    if not r1 or not r2 or r1 == r2:
        return None
    side = 1 if r1 > r2 else 2
    book = m.get("book_odds_home") if side == 1 else m.get("book_odds_away")
    fair = m.get("odds1") if side == 1 else m.get("odds2")
    if not book or not fair:
        return None
    return side if fair <= book <= max_odds else None


def start(m: dict) -> tuple[str, bool]:
    """Match start in UTC (ISO), and whether the time is known (unknown: end of that day, Budapest)."""
    d = m.get("match_date")
    t = m.get("time")
    known = bool(t) and not m.get("time_unknown") and ":" in str(t)
    hh, mm = (int(x) for x in str(t).split(":")[:2]) if known else (23, 59)
    local = datetime.strptime(d, "%Y-%m-%d").replace(hour=hh, minute=mm, tzinfo=BUD)
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), known


def build(tc: dict, ua: str, log: dict, now: datetime) -> dict:
    rule = tc["rule"]
    rows = json.loads(_get(RAW.format(path="data/todays_analysis.json"), ua))
    tl = log.setdefault("tennis", {})
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    picks = []
    for m in rows:
        if not m.get("match_date") or not m.get("player1") or not m.get("player2"):
            continue
        t, known = start(m)
        upcoming = datetime.fromisoformat(t.replace("Z", "+00:00")) > now
        side = side_of(m, rule["max_odds"])
        key = f"{m['match_date']}|{m['player1']}|{m['player2']}|{rule['name']}"
        if upcoming and side:
            price = m["book_odds_home"] if side == 1 else m["book_odds_away"]
            prob = m.get("prob1") if side == 1 else (1 - m["prob1"] if m.get("prob1") is not None else None)
            p = {"t": t, "time_known": known, "date": m["match_date"], "p1": m["player1"], "p2": m["player2"],
                 "side": side, "price": price, "fair": m.get("odds1") if side == 1 else m.get("odds2"), "prob": prob,
                 "rank1": m.get("rank1"), "rank2": m.get("rank2"), "tour": m.get("tour"), "event": m.get("tournament")}
            picks.append(p)
            e = tl.get(key)
            if e is None or e["side"] != side:
                tl[key] = {k: p[k] for k in ("t", "date", "p1", "p2", "side", "tour", "event")} | {
                    "rule": rule["name"], "first_at": stamp, "price": price, "last_at": stamp, "last_price": price, "on": True}
            else:
                e.update(last_at=stamp, last_price=price, on=True)
                e.pop("off_at", None)
        elif upcoming and key in tl and tl[key].get("on"):
            tl[key].update(on=False, off_at=stamp)
    # Settle from the dashboard's daily history files (winner 1 or 2).
    days: dict[str, list] = {}
    for e in tl.values():
        if "won" not in e and datetime.fromisoformat(e["t"].replace("Z", "+00:00")) < now:
            days.setdefault(e["date"], []).append(e)
    for d, es in days.items():
        try:
            hist = json.loads(_get(RAW.format(path=f"data/history/{d}.json"), ua)).get("matches", [])
        except Exception:  # noqa: BLE001 - not written yet; try again next time
            continue
        by = {(h.get("player1"), h.get("player2")): h for h in hist}
        for e in es:
            h = by.get((e["p1"], e["p2"]))
            if h and h.get("winner") in (1, 2):
                won = h["winner"] == e["side"]
                e.update(won=won, profit=round(e["price"] - 1 if won else -1, 3), score=h.get("score") or "")
                if h.get("retired"):
                    e["retired"] = True
    live = sorted((e for e in tl.values() if e["date"] >= rule["tracking_from"]), key=lambda e: e["t"])
    # Keep the payload small: matches of the last 60 days.
    cut = (now - timedelta(days=60)).strftime("%Y-%m-%d")
    return {"key": "tennis", "label": tc.get("label", "Tennis"), "picks": sorted(picks, key=lambda p: p["t"]),
            "rule": rule | {"live": [e for e in live if e["date"] >= cut]}}
