import time
import certifi
import requests
import pandas as pd

BASE = "https://api.deadlock-api.com"
DAYS_BACK = 30                       # ban stats can't go earlier than March 1, 2026
BUCKET = "start_time_day"            # try "start_time_week" for bigger samples per row
MATCH_MODE = None                    # e.g. "ranked" for ranked only; None = API default

now = int(time.time())
MIN_TS = now - DAYS_BACK * 86400

RANK_NAMES = {1: "Initiate", 2: "Seeker", 3: "Alchemist", 4: "Arcanist",
              5: "Ritualist", 6: "Emissary", 7: "Archon", 8: "Oracle",
              9: "Phantom", 10: "Ascendant", 11: "Eternus"}

def get(path, params=None):
    for _ in range(6):
        r = requests.get(BASE + path, params=params, timeout=60, verify=certifi.where())
        if r.status_code == 503:     # API load shedding: wait and retry
            time.sleep(int(r.headers.get("Retry-After", 5)))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Gave up on {path}")

def pull(path):
    frames = []
    badges = [(t, s) for t in range(1, 12) for s in range(1, 7)]   # 66 combos
    for i, (tier, sub) in enumerate(badges, 1):
        badge = tier * 10 + sub
        params = {
            "bucket": BUCKET,
            "min_unix_timestamp": MIN_TS,
            "max_unix_timestamp": now,
            "min_average_badge": badge,
            "max_average_badge": badge,
        }
        if MATCH_MODE:
            params["match_mode"] = MATCH_MODE
        df = pd.json_normalize(get(path, params))
        df["badge"] = badge
        df["rank_tier"] = tier
        df["rank_name"] = RANK_NAMES[tier]
        df["subrank"] = sub
        frames.append(df)
        print(f"{path} [{i}/{len(badges)}] badge {badge}: {len(df)} rows")
        time.sleep(0.6)              # stay under the 200 req/min limit
    return pd.concat(frames, ignore_index=True)

# ---- hero names ----
heroes = pd.json_normalize(get("/v1/assets/heroes"))
hero_names = heroes[["id", "name"]].rename(columns={"id": "hero_id", "name": "hero_name"})

# ---- pick rate + win rate by rank, subrank and date ----
stats = pull("/v1/analytics/hero-stats")
print("hero-stats columns:", list(stats.columns))

group_cols = [c for c in ["badge", "bucket"] if c in stats.columns]
stats["win_rate"] = stats["wins"] / stats["matches"]
stats["pick_rate"] = stats["matches"] / stats.groupby(group_cols)["matches"].transform("sum")
stats = stats.merge(hero_names, on="hero_id", how="left")
stats.to_csv("hero_stats_by_rank_subrank_and_date.csv", index=False)
print("Saved hero_stats_by_rank_subrank_and_date.csv")

# ---- bans by rank, subrank and date (raw export) ----
bans = pull("/v1/analytics/hero-ban-stats")
print("hero-ban-stats columns:", list(bans.columns))
bans = bans.merge(hero_names, on="hero_id", how="left")
bans.to_csv("hero_bans_by_rank_subrank_and_date.csv", index=False)
print("Saved hero_bans_by_rank_subrank_and_date.csv")