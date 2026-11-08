"""Bookmaker prices: American to decimal odds, ESPN rows paired with our games, and only pre-game prices saved."""
import unittest
from datetime import date, datetime, timezone
from unittest import mock

from sports import market

BOARD = {"events": [
    {"date": "2026-11-08T18:00Z", "competitions": [{"competitors": [{"homeAway": "home", "team": {"abbreviation": "BOS"}}, {"homeAway": "away", "team": {"abbreviation": "TB"}}],
     "odds": [{"provider": {"name": "DraftKings"}, "moneyline": {"home": {"close": {"odds": "-148"}}, "away": {"close": {"odds": "+124"}}}}]}]},
    {"date": "2026-11-09T00:00Z", "competitions": [{"competitors": [{"homeAway": "home", "team": {"abbreviation": "NJ"}}, {"homeAway": "away", "team": {"abbreviation": "SJ"}}],
     "odds": [{"provider": {"name": "DraftKings"}, "moneyline": {"home": {"open": {"odds": "EVEN"}}, "away": {"close": {"odds": "+100"}}}}]}]},
    {"date": "2026-11-09T01:00Z", "competitions": [{"competitors": [{"homeAway": "home", "team": {"abbreviation": "EDM"}}, {"homeAway": "away", "team": {"abbreviation": "NYR"}}]}]},
]}


class MarketTest(unittest.TestCase):
    def test_american_to_decimal(self):
        self.assertAlmostEqual(market.ml_to_decimal("-148"), 1.676, places=3)
        self.assertEqual(market.ml_to_decimal("+124"), 2.24)
        self.assertEqual(market.ml_to_decimal(150.0), 2.5)
        self.assertIsNone(market.ml_to_decimal("EVEN"))
        self.assertIsNone(market.ml_to_decimal(None))

    def test_parse_and_match_with_aliases(self):
        rows = market.parse_scoreboard(BOARD)
        self.assertEqual([(r["home"], r["away"]) for r in rows], [("BOS", "TB")])  # no usable price on the others
        ours = [{"t": "2026-11-08T18:00:00Z", "h": "BOS", "a": "TBL"}, {"t": "2026-11-08T18:00:00Z", "h": "NYI", "a": "PIT"}]
        self.assertEqual(market.match(rows, ours, {"TB": "TBL"})[0][1], ours[0])
        # Without the alias the one nearby game sharing the home side is taken.
        self.assertEqual(market.match(rows, ours, {})[0][1], ours[0])

    def test_only_games_not_started_are_saved(self):
        ours = [{"t": "2026-11-08T18:00:00Z", "h": "BOS", "a": "TBL"}]
        store = {"nhl": {"2026-11-08|TBL|BOS": {"bh": 1.7, "ba": 2.2, "book": "DraftKings", "at": "x"}}}
        with mock.patch.object(market, "_get", return_value=b'{"events": []}') as g:
            g.side_effect = lambda url, ua: __import__("json").dumps(BOARD).encode()
            n = market.refresh(store, "nhl", "hockey/nhl", ours, {"TB": "TBL"}, "ua", date(2026, 11, 8), datetime(2026, 11, 8, 19, tzinfo=timezone.utc))
        self.assertEqual(n, 0)
        self.assertEqual(store["nhl"]["2026-11-08|TBL|BOS"]["bh"], 1.7)  # the pre-game price stays
        with mock.patch.object(market, "_get", side_effect=lambda url, ua: __import__("json").dumps(BOARD).encode()):
            market.refresh(store, "nhl", "hockey/nhl", ours, {"TB": "TBL"}, "ua", date(2026, 11, 8), datetime(2026, 11, 8, 12, tzinfo=timezone.utc))
        self.assertEqual(store["nhl"]["2026-11-08|TBL|BOS"]["bh"], 1.676)

    def test_closing_price_and_backfill(self):
        core = {"items": [
            {"provider": {"name": "Other", "priority": 2}, "homeTeamOdds": {"moneyLine": 100}, "awayTeamOdds": {"moneyLine": -120}},
            {"provider": {"name": "DraftKings", "priority": 1},
             "homeTeamOdds": {"moneyLine": 230, "close": {"moneyLine": {"decimal": 3.3}}},
             "awayTeamOdds": {"moneyLine": -285, "close": {"moneyLine": {"decimal": 1.35}}}}]}
        self.assertEqual(market.closing_price(core), {"bh": 3.3, "ba": 1.35, "book": "DraftKings"})
        board = {"events": [{"id": "9", "date": "2026-11-05T00:00Z", "competitions": [{"status": {"type": {"completed": True}},
                 "competitors": [{"homeAway": "home", "team": {"abbreviation": "NY"}}, {"homeAway": "away", "team": {"abbreviation": "BOS"}}]}]}]}
        ours = [{"t": "2026-11-05T00:00:00Z", "h": "NY", "a": "BOS"}]
        store = {"nba": {"2026-11-05|BOS|NY": {"bh": 3.0, "ba": 1.4, "book": "DraftKings", "at": "x"}}}
        js = __import__("json")
        fake = lambda url, ua: js.dumps(core if "core.api" in url else board).encode()  # noqa: E731
        with mock.patch.object(market, "_get", side_effect=fake):
            n = market.backfill(store, "nba", "basketball/nba", ours, {}, "ua", date(2026, 11, 8), 7, datetime(2026, 11, 8, tzinfo=timezone.utc))
        self.assertEqual(store["nba"]["2026-11-05|BOS|NY"]["bh"], 3.3)  # the closing price replaces the earlier one
        self.assertTrue(store["nba"]["2026-11-05|BOS|NY"]["close"])
        self.assertEqual(n, 1)
        with mock.patch.object(market, "_get", side_effect=fake):
            self.assertEqual(market.backfill(store, "nba", "basketball/nba", ours, {}, "ua", date(2026, 11, 8), 7, datetime(2026, 11, 8, tzinfo=timezone.utc)), 0)


if __name__ == "__main__":
    unittest.main()
