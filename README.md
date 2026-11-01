# American sports: fair odds

Our own ratings, expected scores, win chances and fair odds (1 ÷ chance, no bookmaker margin) for the **NFL**, **NBA** and **NHL**.
Live page: GitHub Pages of this repository. Updated twice a day by `.github/workflows/update.yml`.

## Data
- NFL: [nflverse](https://github.com/nflverse/nflverse-data) schedules and scores, with the closing spread, total and moneylines shown for comparison.
- NBA and NHL: [sportsdataverse](https://github.com/sportsdataverse) schedules and scores (hoopR / fastRhockey).

## Model (`sports/model.py`)
Opponent-adjusted attack and defence from scores, fitted by ridge least squares.
Expected home score = level + attack(home) − defence(away) + home advantage ÷ 2, and the mirror image for the away side.
Early in a season each club is pulled towards a share of last season's final rating. Every NFL week and every NBA/NHL date is predicted only from earlier games.

| | Last season carried over | Prior weight | Home advantage | Win chance |
|---|---|---|---|---|
| NFL | 50% | 8 | 2.6 points | normal, sd 13.2 |
| NBA | 50% | 10 | last season's average home margin | normal, sd 14.6 |
| NHL | 30% | 40 | last season's average home margin | Poisson goals, overtime split evenly |

The NBA and NHL settings were chosen on the 2025–26 season, each date predicted only from earlier dates.
The model knows nothing about injuries, rest or lineups.

## Run locally
```
pip install -r requirements.txt
python scripts/run.py      # writes data/odds.json and site/index.html
python -m unittest discover -s tests
```
