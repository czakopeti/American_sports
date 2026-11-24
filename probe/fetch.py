import io, sys, urllib.request, pandas as pd
UA = {"User-Agent": "Mozilla/5.0 (fair-odds hobby page; credit MoneyPuck.com)"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120) as r:
        return r.read()
for u in ["https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv",
          "https://moneypuck.com/moneypuck/playerData/seasonSummary/2026/regular/teams.csv"]:
    try:
        b = get(u); print("OK", u, len(b))
        df = pd.read_csv(io.BytesIO(b), low_memory=False)
        print(df.columns.tolist()); print(df.head(3).T.to_string()[:3000])
        if "gameId" in df:
            print(df.season.value_counts().sort_index().tail(4)); print(df.situation.value_counts())
            keep = df[df.season >= 2024]
            keep.to_csv("probe/mp_teams_games.csv.gz", index=False, compression="gzip")
            print("saved", keep.shape)
    except Exception as e:
        print("FAIL", u, e)
