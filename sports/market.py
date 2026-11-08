"""Bookmaker moneylines for the NBA and NHL from ESPN's scoreboard (DraftKings prices), kept in data/market.json.

ESPN shows a price only until the game starts, so every run saves the latest pre-game price per game:
the record is what could have been bet before tip-off or puck drop. NFL prices come from nflverse.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sports.data import _get

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={day}"
CORE_ODDS = "https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/events/{id}/competitions/{id}/odds"


def ml_to_decimal(ml) -> float | None:
    try:
        v = float(str(ml).replace("+", ""))
    except (TypeError, ValueError):
        return None
    if v == 0 or -100 < v < 100:
        return None
    return round(1 + v / 100, 3) if v > 0 else round(1 + 100 / -v, 3)


def parse_scoreboard(j: dict) -> list[dict]:
    """One row per game with a moneyline: kickoff (UTC), ESPN home and away codes, decimal prices."""
    out = []
    for e in j.get("events", []):
        c = (e.get("competitions") or [{}])[0]
        side = {t.get("homeAway"): t.get("team", {}).get("abbreviation") for t in c.get("competitors", [])}
        odds = (c.get("odds") or [None])[0]
        if not odds or not side.get("home") or not side.get("away"):
            continue
        ml = odds.get("moneyline") or {}
        cur = lambda s: (ml.get(s) or {}).get("close", {}).get("odds") or (ml.get(s) or {}).get("open", {}).get("odds")  # noqa: E731
        h, a = ml_to_decimal(cur("home")), ml_to_decimal(cur("away"))
        if h is None or a is None:
            continue
        t = datetime.strptime(e["date"].replace("Z", ""), "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
        out.append({"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "home": side["home"], "away": side["away"], "bh": h, "ba": a,
                    "book": (odds.get("provider") or {}).get("name", "")})
    return out


def finished_events(j: dict) -> list[dict]:
    """Games ESPN marks as completed: event id, kickoff (UTC), ESPN home and away codes."""
    out = []
    for e in j.get("events", []):
        c = (e.get("competitions") or [{}])[0]
        if not (c.get("status") or e.get("status") or {}).get("type", {}).get("completed"):
            continue
        side = {t.get("homeAway"): t.get("team", {}).get("abbreviation") for t in c.get("competitors", [])}
        if side.get("home") and side.get("away"):
            t = datetime.strptime(e["date"].replace("Z", ""), "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
            out.append({"id": e["id"], "t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "home": side["home"], "away": side["away"]})
    return out


def closing_price(j: dict) -> dict | None:
    """The closing moneyline of the first-priority bookmaker in ESPN's odds list for one game."""
    items = sorted(j.get("items", []), key=lambda i: (i.get("provider") or {}).get("priority", 99))
    for i in items:
        def dec(side):
            t = i.get(side) or {}
            v = ((t.get("close") or {}).get("moneyLine") or {}).get("decimal")
            return float(v) if v else ml_to_decimal(t.get("moneyLine"))
        h, a = dec("homeTeamOdds"), dec("awayTeamOdds")
        if h and a and h > 1 and a > 1:
            return {"bh": round(h, 3), "ba": round(a, 3), "book": (i.get("provider") or {}).get("name", "")}
    return None


def match(rows: list[dict], games: list[dict], aliases: dict) -> list[tuple[dict, dict]]:
    """Pair ESPN rows with our games: same teams after the alias table, or, failing that,
    the one game of ours within three hours that shares at least one team code."""
    pairs = []
    for r in rows:
        h, a = aliases.get(r["home"], r["home"]), aliases.get(r["away"], r["away"])
        t = datetime.fromisoformat(r["t"].replace("Z", "+00:00"))
        near = [g for g in games if abs((datetime.fromisoformat(g["t"].replace("Z", "+00:00")) - t).total_seconds()) <= 3 * 3600]
        exact = [g for g in near if g["h"] == h and g["a"] == a]
        loose = [g for g in near if g["h"] == h or g["a"] == a]
        g = exact[0] if exact else (loose[0] if len(loose) == 1 else None)
        if g:
            pairs.append((r, g))
    return pairs


def backfill(store: dict, sport: str, path: str, games: list[dict], aliases: dict, ua: str, today: date, days: int, now: datetime) -> int:
    """Closing prices for the games of the last few days, so played games show the price just before the start.
    A game that already has its closing price is not asked again."""
    book = store.setdefault(sport, {})
    league_sport, league = path.split("/")
    n = 0
    for k in range(days, -1, -1):
        d = today - timedelta(days=k)
        j = json.loads(_get(SCOREBOARD.format(path=path, day=d.strftime("%Y%m%d")), ua))
        evs = finished_events(j)
        for r, g in match(evs, games, aliases):
            if book.get(key(g), {}).get("close"):
                continue
            try:
                c = closing_price(json.loads(_get(CORE_ODDS.format(sport=league_sport, league=league, id=r["id"]), ua)))
            except Exception:  # noqa: BLE001 - one game without odds must not stop the rest
                c = None
            if c:
                book[key(g)] = {**c, "close": True, "at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
                n += 1
    return n


def key(g: dict) -> str:
    return f"{g['t'][:10]}|{g['a']}|{g['h']}"


def refresh(store: dict, sport: str, path: str, games: list[dict], aliases: dict, ua: str, today: date, now: datetime) -> int:
    """Save the latest price of every game that has not started yet. Returns how many were saved."""
    book = store.setdefault(sport, {})
    n = 0
    for d in (today - timedelta(days=1), today, today + timedelta(days=1)):
        j = json.loads(_get(SCOREBOARD.format(path=path, day=d.strftime("%Y%m%d")), ua))
        for r, g in match(parse_scoreboard(j), games, aliases):
            if datetime.fromisoformat(g["t"].replace("Z", "+00:00")) <= now:
                continue
            book[key(g)] = {"bh": r["bh"], "ba": r["ba"], "book": r["book"], "at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
            n += 1
    return n


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def save(path: Path, store: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
