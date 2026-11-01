"""Model sanity and the no-look-ahead rule."""
import unittest

import numpy as np
import pandas as pd

from sports.model import predict_season, win_normal, win_poisson

CFG = {"prior_share": 0.5, "prior_weight": 8, "home_advantage": 2.0, "margin_sd": 13.0, "unit": "points"}


def games(rows, season=1):
    return pd.DataFrame([{"season": season, "group": g, "kickoff": f"2000-01-{g:02d}T18:00:00Z", "away": a, "home": h,
                          "as_": s2, "hs": s1, "done": s1 is not None} for g, a, h, s2, s1 in rows])


class ModelTest(unittest.TestCase):
    def test_win_functions(self):
        self.assertAlmostEqual(win_normal(0, 13), 0.5)
        self.assertGreater(win_normal(7, 13), 0.5)
        self.assertAlmostEqual(win_poisson(3, 3, 0.5), 0.5, places=6)
        self.assertGreater(win_poisson(3.5, 2.5, 0.5), 0.5)

    def test_later_results_do_not_change_earlier_predictions(self):
        prev = games([(1, "A", "B", 20, 24), (1, "C", "D", 17, 21), (2, "B", "C", 10, 30), (2, "D", "A", 14, 28)], season=0)
        base = [(1, "A", "B", 20, 27), (1, "C", "D", 13, 16), (2, "A", "C", None, None), (2, "B", "D", None, None)]
        p1, _ = predict_season(games(base), prev, CFG)
        changed = base[:2] + [(2, "A", "C", 40, 3), (2, "B", "D", 0, 50)]
        p2, _ = predict_season(games(changed), prev, CFG)
        np.testing.assert_allclose(p1.eh.values, p2.eh.values)
        np.testing.assert_allclose(p1.ph.values, p2.ph.values)


if __name__ == "__main__":
    unittest.main()
