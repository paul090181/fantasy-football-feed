import json
import urllib.request
from datetime import datetime, timezone

LEAGUE_ID = "1385955289206910976"
BASE = "https://api.sleeper.app/v1"


def get_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "fantasy-football-feed/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


print("Downloading Sleeper league data...")

league = get_json(f"{BASE}/league/{LEAGUE_ID}")
users = get_json(f"{BASE}/league/{LEAGUE_ID}/users")
rosters = get_json(f"{BASE}/league/{LEAGUE_ID}/rosters")
players = get_json(f"{BASE}/players/nfl")
nfl_state = get_json(f"{BASE}/state/nfl")

# Sleeper exposes current-week projections through the same public service,
# although this endpoint is not part of the formally documented v1 API.
# Keep the feed working even if projections are temporarily unavailable.
projection_week = nfl_state.get("week")
projection_season = nfl_state.get("season")
projection_season_type = nfl_state.get("season_type", "regular")
projection_source = None
projections_by_player = {}

try:
    projection_rows = get_json(
        f"https://api.sleeper.app/projections/nfl/"
        f"{projection_season}/{projection_week}"
        f"?season_type={projection_season_type}"
    )
    projections_by_player = {
        str(row.get("player_id")): row
        for row in projection_rows
        if row.get("player_id") is not None
    }
    projection_source = "Sleeper projections endpoint"
except Exception as exc:
    print(f"Warning: projections unavailable: {exc}")

scoring_settings = league.get("scoring_settings", {})
roster_positions = league.get("roster_positions", [])


def projection_for(player_id):
    row = projections_by_player.get(str(player_id))
    if not row:
        return None

    stats = row.get("stats") or {}
    projected_points = sum(
        float(stats.get(stat_name, 0) or 0) * float(point_value or 0)
        for stat_name, point_value in scoring_settings.items()
        if stat_name in stats
    )

    return {
        "week": row.get("week"),
        "season": row.get("season"),
        "season_type": row.get("season_type"),
        "opponent": row.get("opponent"),
        "game_date": row.get("date"),
        "projected_points": round(projected_points, 2),
        "pts_ppr": stats.get("pts_ppr"),
        "pts_half_ppr": stats.get("pts_half_ppr"),
        "pts_std": stats.get("pts_std"),
        "updated_at": row.get("updated_at"),
        "company": row.get("company"),
    }

# Convert Sleeper user IDs into manager names
user_names = {}
for user in users:
    user_names[user["user_id"]] = (
        user.get("metadata", {}).get("team_name")
        or user.get("display_name")
        or user["user_id"]
    )

# Build readable rosters
readable_rosters = []

rostered_player_ids = set()

for roster in rosters:
    player_ids = roster.get("players") or []
    rostered_player_ids.update(player_ids)
    starter_ids = roster.get("starters") or []
    starter_slots = {
        str(player_id): roster_positions[index]
        for index, player_id in enumerate(starter_ids)
        if index < len(roster_positions) and player_id not in {None, "0"}
    }

    roster_players = []

    for player_id in player_ids:
        player = players.get(player_id, {})

        roster_players.append({
            "player_id": player_id,
            "name": player.get("full_name", player_id),
            "position": player.get("position"),
            "team": player.get("team"),
            "status": player.get("status"),
            "injury_status": player.get("injury_status"),
            "is_starter": str(player_id) in starter_slots,
            "starter_slot": starter_slots.get(str(player_id)),
            "projection": projection_for(player_id),
        })

    readable_rosters.append({
        "roster_id": roster.get("roster_id"),
        "owner_id": roster.get("owner_id"),
        "manager": user_names.get(
            roster.get("owner_id"),
            roster.get("owner_id")
        ),
        "settings": roster.get("settings", {}),
        "starter_ids": starter_ids,
        "starter_slots": [
            {
                "slot": roster_positions[index]
                if index < len(roster_positions)
                else None,
                "player_id": player_id,
                "player_name": players.get(str(player_id), {}).get(
                    "full_name",
                    player_id,
                ),
            }
            for index, player_id in enumerate(starter_ids)
        ],
        "players": roster_players,
    })

# Build a useful free-agent pool.
# Restrict it to fantasy-relevant offensive players, kickers and defenses
# so the output doesn't contain thousands of irrelevant NFL players.
free_agents = []

for player_id, player in players.items():
    if player_id in rostered_player_ids:
        continue

    position = player.get("position")

    if position not in {"QB", "RB", "WR", "TE", "K", "DEF"}:
        continue

    if player.get("active") is not True:
        continue

    free_agents.append({
        "player_id": player_id,
        "name": player.get("full_name", player_id),
        "position": position,
        "team": player.get("team"),
        "status": player.get("status"),
        "injury_status": player.get("injury_status"),
        "search_rank": player.get("search_rank"),
        "projection": projection_for(player_id),
    })

# Put the more fantasy-relevant players toward the top.
free_agents.sort(
    key=lambda p: (
        p["search_rank"] is None,
        p["search_rank"] if p["search_rank"] is not None else 999999
    )
)

snapshot = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "league_id": LEAGUE_ID,
    "league": league,
    "nfl_state": nfl_state,
    "projection_metadata": {
        "available": bool(projections_by_player),
        "source": projection_source,
        "season": projection_season,
        "season_type": projection_season_type,
        "week": projection_week,
        "scoring": "Calculated from league scoring_settings",
    },
    "managers": users,
    "rosters": readable_rosters,
    "free_agents": free_agents,
}

with open("sleeper_snapshot.json", "w", encoding="utf-8") as f:
    json.dump(snapshot, f, indent=2)

print(
    f"Done: {len(readable_rosters)} rosters and "
    f"{len(free_agents)} free agents saved."
)# Create a smaller daily file for ChatGPT analysis
daily_feed = {
    "generated_at_utc": snapshot["generated_at_utc"],
    "league_id": LEAGUE_ID,
    "league_name": league.get("name"),
    "settings": {
        "num_teams": league.get("settings", {}).get("num_teams"),
        "waiver_budget": league.get("settings", {}).get("waiver_budget"),
        "waiver_day_of_week": league.get("settings", {}).get(
            "waiver_day_of_week"
        ),
        "daily_waivers_hour": league.get("settings", {}).get(
            "daily_waivers_hour"
        ),
        "roster_positions": roster_positions,
        "scoring_settings": scoring_settings,
    },
    "nfl_state": nfl_state,
    "projection_metadata": snapshot["projection_metadata"],
    "rosters": readable_rosters,
    "free_agents": free_agents[:300],
}

with open("sleeper_daily.json", "w", encoding="utf-8") as f:
    json.dump(daily_feed, f, separators=(",", ":"))

print("Compact daily feed saved to sleeper_daily.json")

# Build a simple HTML page that ChatGPT can read easily
html = []

html.append("<!DOCTYPE html>")
html.append("<html>")
html.append("<head>")
html.append("<meta charset='utf-8'>")
html.append("<title>Fantasy Football Feed</title>")
html.append("</head>")
html.append("<body>")

html.append("<h1>Fantasy Football Feed</h1>")
html.append(f"<p>Last updated: {snapshot['generated_at_utc']}</p>")

html.append("<h2>Sleeper League</h2>")
html.append(f"<p><strong>League:</strong> {league.get('name')}</p>")
html.append(f"<p><strong>Teams:</strong> {league.get('settings', {}).get('num_teams')}</p>")

html.append("<h2>Rosters</h2>")

for roster in readable_rosters:
    html.append(f"<h3>{roster['manager']}</h3>")
    html.append("<ul>")

    for player in roster["players"]:
        injury = player.get("injury_status")
        injury_text = f" - {injury}" if injury else ""

        html.append(
            f"<li>{player['name']} - "
            f"{player.get('position')} - "
            f"{player.get('team')}"
            f"{injury_text}</li>"
        )

    html.append("</ul>")

html.append("<h2>Top Available Players</h2>")
html.append("<ul>")

for player in free_agents[:100]:
    injury = player.get("injury_status")
    injury_text = f" - {injury}" if injury else ""

    html.append(
        f"<li>{player['name']} - "
        f"{player.get('position')} - "
        f"{player.get('team')}"
        f"{injury_text}</li>"
    )

html.append("</ul>")

html.append(
    "<p><a href='sleeper_daily.json'>Raw Sleeper Daily Data</a></p>"
)

html.append("</body>")
html.append("</html>")

with open("index.html", "w", encoding="utf-8") as f:
    f.write("\n".join(html))

print("Readable HTML feed saved to index.html")
