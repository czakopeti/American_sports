#!/usr/bin/env python3
"""Download, predict, write data/odds.json and site/index.html. Exit 1 if every league failed."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sports.build import build, write_site  # noqa: E402


def main() -> int:
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    today = datetime.now(timezone.utc).date()
    payload = build(ROOT, cfg, today)
    for e in payload["errors"]:
        print("FAILED", e)
    if not payload["sports"]:
        return 1
    previous = ROOT / "data" / "odds.json"
    if payload["errors"] and previous.exists():
        # Keep the last good copy of any league that failed today.
        old = {s["key"]: s for s in json.loads(previous.read_text(encoding="utf-8")).get("sports", [])}
        have = {s["key"] for s in payload["sports"]}
        payload["sports"] += [s | {"stale": True} for k, s in old.items() if k not in have]
        order = list(cfg["sports"])
        payload["sports"].sort(key=lambda s: order.index(s["key"]))
    (ROOT / "data").mkdir(exist_ok=True)
    previous.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_site(ROOT, payload)
    for s in payload["sports"]:
        print(f"{s['label']} {s['season']}: {s['played']} played, favourite won {s['fav_won']}, current {s['current']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
