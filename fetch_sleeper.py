import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, median

LEAGUE_ID = "1385955289206910976"
MY_TEAM_NAME = "Nacua Matata"
BASE = "https://api.sleeper.app/v1"

DATA_WARNINGS = []


def get_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "fantasy-football-feed/2.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def try_get_json(url, label, default):
    try:
        return get_json(url)
    except Exception as exc:
        warning = f"{label} unavailable: {exc}"
        DATA_WARNINGS.append(warning)
        print(f"Warning: {warning}")
        return default


def epoch_ms_to_iso(value):
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(
            float(value) / 1000.0,
            tz=timezone.utc,
        ).isoformat()
    except Exception:
        return None


def points_from_stats(stats, scoring_settings):
    if not stats:
        return None
    points = 0.0
    found = False
    for stat_name, point_value in scoring_settings.items():
        if stat_name in stats:
            found = True
            try:
                points += float(stats.get(stat_name, 0) or 0) * float(point_value or 0)
            except (TypeError, ValueError):
                pass
    return round(points, 2) if found else None


def compact_game_stats(stats):
    if not stats:
        return None
    useful = [
        "pass_att", "pass_cmp", "pass_yd", "pass_td", "pass_int",
        "rush_att", "rush_yd", "rush_td",
        "rec_tgt", "rec", "rec_yd", "rec_td",
        "fum_lost",
        "off_snp", "tm_off_snp",
        "fgm", "fga", "xpm", "xpa",
        "sack", "int", "fum_rec", "def_td", "pts_allow",
    ]
    result = {key: stats.get(key) for key in useful if key in stats}
    off_snp = stats.get("off_snp")
    tm_off_snp = stats.get("tm_off_snp")
    try:
        if off_snp is not None and tm_off_snp:
            result["snap_pct"] = round(float(off_snp) / float(tm_off_snp), 3)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return result or None


previous_daily = None
if os.path.exists("sleeper_daily.json"):
    try:
        with open("sleeper_daily.json", "r", encoding="utf-8") as f:
            previous_daily = json.load(f)
    except Exception as exc:
        DATA_WARNINGS.append(f"Previous daily file could not be read: {exc}")


print("Downloading Sleeper league data...")

league = get_json(f"{BASE}/league/{LEAGUE_ID}")
users = get_json(f"{BASE}/league/{LEAGUE_ID}/users")
rosters = get_json(f"{BASE}/league/{LEAGUE_ID}/rosters")
players = get_json(f"{BASE}/players/nfl")
nfl_state = get_json(f"{BASE}/state/nfl")

scoring_settings = league.get("scoring_settings", {})
roster_positions = league.get("roster_positions", [])
league_settings = league.get("settings", {})
waiver_budget = int(league_settings.get("waiver_budget") or 0)

current_week = int(nfl_state.get("week") or 1)
projection_week = current_week
projection_season = nfl_state.get("season")
projection_season_type = nfl_state.get("season_type", "regular")

projection_source = None
projections_by_player = {}
projection_rows = try_get_json(
    f"https://api.sleeper.app/projections/nfl/"
    f"{projection_season}/{projection_week}"
    f"?season_type={projection_season_type}",
    "Sleeper projections",
    [],
)
if projection_rows:
    projections_by_player = {
        str(row.get("player_id")): row
        for row in projection_rows
        if row.get("player_id") is not None
    }
    projection_source = "Sleeper projections endpoint"


def projection_for(player_id):
    row = projections_by_player.get(str(player_id))
    if not row:
        return None
    stats = row.get("stats") or {}
    return {
        "week": row.get("week"),
        "season": row.get("season"),
        "season_type": row.get("season_type"),
        "opponent": row.get("opponent"),
        "game_date": row.get("date"),
        "projected_points": points_from_stats(stats, scoring_settings),
        "pts_ppr": stats.get("pts_ppr"),
        "pts_half_ppr": stats.get("pts_half_ppr"),
        "pts_std": stats.get("pts_std"),
        "updated_at": row.get("updated_at"),
        "company": row.get("company"),
    }


stats_by_week = {}
for week in sorted({w for w in (current_week - 1, current_week) if w >= 1}):
    rows = try_get_json(
        f"https://api.sleeper.app/stats/nfl/"
        f"{projection_season}/{week}"
        f"?season_type={projection_season_type}",
        f"Sleeper stats week {week}",
        [],
    )
    stats_by_week[week] = {
        str(row.get("player_id")): (row.get("stats") or {})
        for row in rows
        if row.get("player_id") is not None
    }


def recent_stats_for(player_id):
    output = []
    pid = str(player_id)
    for week in sorted(stats_by_week):
        stats = stats_by_week[week].get(pid)
        if not stats:
            continue
        output.append({
            "week": week,
            "fantasy_points": points_from_stats(stats, scoring_settings),
            "usage": compact_game_stats(stats),
        })
    return output


def player_base(player_id):
    player = players.get(str(player_id), {})
    return {
        "player_id": str(player_id),
        "name": player.get("full_name", str(player_id)),
        "position": player.get("position"),
        "fantasy_positions": player.get("fantasy_positions"),
        "team": player.get("team"),
        "active": player.get("active"),
        "status": player.get("status"),
        "injury_status": player.get("injury_status"),
        "injury_body_part": player.get("injury_body_part"),
        "injury_notes": player.get("injury_notes"),
        "injury_start_date": player.get("injury_start_date"),
        "practice_participation": player.get("practice_participation"),
        "practice_description": player.get("practice_description"),
        "depth_chart_position": player.get("depth_chart_position"),
        "depth_chart_order": player.get("depth_chart_order"),
        "news_updated": player.get("news_updated"),
        "years_exp": player.get("years_exp"),
        "age": player.get("age"),
        "search_rank": player.get("search_rank"),
        "projection": projection_for(player_id),
        "recent_stats": recent_stats_for(player_id),
    }


user_names = {}
user_display_names = {}
for user in users:
    user_id = user.get("user_id")
    user_display_names[user_id] = user.get("display_name") or user_id
    user_names[user_id] = (
        user.get("metadata", {}).get("team_name")
        or user.get("display_name")
        or user_id
    )

readable_rosters = []
rostered_player_ids = set()
roster_manager_by_id = {}
roster_owner_by_id = {}

for roster in rosters:
    roster_id = roster.get("roster_id")
    owner_id = roster.get("owner_id")
    manager = user_names.get(owner_id, owner_id)
    roster_manager_by_id[int(roster_id)] = manager
    roster_owner_by_id[int(roster_id)] = owner_id

    player_ids = [str(pid) for pid in (roster.get("players") or [])]
    rostered_player_ids.update(player_ids)
    starter_ids = [str(pid) if pid is not None else None for pid in (roster.get("starters") or [])]
    reserve_ids = {str(pid) for pid in (roster.get("reserve") or [])}
    taxi_ids = {str(pid) for pid in (roster.get("taxi") or [])}

    starter_slots = {
        str(player_id): roster_positions[index]
        for index, player_id in enumerate(starter_ids)
        if index < len(roster_positions) and player_id not in {None, "0"}
    }

    roster_players = []
    for player_id in player_ids:
        card = player_base(player_id)
        card.update({
            "is_starter": player_id in starter_slots,
            "starter_slot": starter_slots.get(player_id),
            "is_reserve": player_id in reserve_ids,
            "is_taxi": player_id in taxi_ids,
        })
        roster_players.append(card)

    settings = roster.get("settings", {}) or {}
    budget_used = int(settings.get("waiver_budget_used") or 0)
    readable_rosters.append({
        "roster_id": roster_id,
        "owner_id": owner_id,
        "manager": manager,
        "owner_display_name": user_display_names.get(owner_id),
        "settings": settings,
        "faab": {
            "season_budget": waiver_budget,
            "used": budget_used,
            "remaining": max(0, waiver_budget - budget_used) if waiver_budget else None,
        },
        "waiver_position": settings.get("waiver_position"),
        "starter_ids": starter_ids,
        "reserve_ids": sorted(reserve_ids),
        "taxi_ids": sorted(taxi_ids),
        "starter_slots": [
            {
                "slot": roster_positions[index] if index < len(roster_positions) else None,
                "player_id": player_id,
                "player_name": players.get(str(player_id), {}).get("full_name", player_id),
            }
            for index, player_id in enumerate(starter_ids)
        ],
        "projected_starter_points": round(sum(
            (projection_for(pid) or {}).get("projected_points") or 0
            for pid in starter_ids
            if pid not in {None, "0"}
        ), 2),
        "players": roster_players,
    })


def record_points(settings):
    whole = settings.get("fpts") or 0
    decimal = settings.get("fpts_decimal") or 0
    try:
        return round(float(whole) + float(decimal) / 100.0, 2)
    except (TypeError, ValueError):
        return whole


standings = []
for roster in readable_rosters:
    settings = roster.get("settings", {})
    standings.append({
        "roster_id": roster["roster_id"],
        "manager": roster["manager"],
        "wins": settings.get("wins", 0),
        "losses": settings.get("losses", 0),
        "ties": settings.get("ties", 0),
        "points_for": record_points(settings),
        "waiver_position": roster.get("waiver_position"),
        "faab_remaining": roster.get("faab", {}).get("remaining"),
    })
standings.sort(
    key=lambda row: (
        -(row.get("wins") or 0),
        row.get("losses") or 0,
        -(row.get("points_for") or 0),
    )
)
for index, row in enumerate(standings, start=1):
    row["rank"] = index


my_roster = next(
    (
        roster for roster in readable_rosters
        if str(roster.get("manager", "")).strip().lower() == MY_TEAM_NAME.lower()
    ),
    None,
)
my_roster_id = int(my_roster["roster_id"]) if my_roster else None
if my_roster is None:
    DATA_WARNINGS.append(
        f"Could not find team '{MY_TEAM_NAME}' in current league rosters."
    )


free_agents = []
for player_id, player in players.items():
    pid = str(player_id)
    if pid in rostered_player_ids:
        continue
    position = player.get("position")
    if position not in {"QB", "RB", "WR", "TE", "K", "DEF"}:
        continue
    if player.get("active") is not True:
        continue
    free_agents.append(player_base(pid))


def free_agent_sort_key(player):
    projection = (player.get("projection") or {}).get("projected_points")
    search_rank = player.get("search_rank")
    return (
        projection is None,
        -(projection or 0),
        search_rank is None,
        search_rank if search_rank is not None else 999999,
    )


free_agents.sort(key=free_agent_sort_key)

free_agents_by_position = {}
for position in ["QB", "RB", "WR", "TE", "K", "DEF"]:
    pool = [p for p in free_agents if p.get("position") == position]
    free_agents_by_position[position] = pool[:40]


transactions_by_week = {}
for week in range(1, current_week + 1):
    transactions_by_week[week] = try_get_json(
        f"{BASE}/league/{LEAGUE_ID}/transactions/{week}",
        f"transactions week {week}",
        [],
    )


def tx_player_rows(mapping, direction):
    rows = []
    for player_id, roster_id in (mapping or {}).items():
        player = players.get(str(player_id), {})
        try:
            rid = int(roster_id)
        except (TypeError, ValueError):
            rid = roster_id
        rows.append({
            "player_id": str(player_id),
            "name": player.get("full_name", str(player_id)),
            "position": player.get("position"),
            "team": player.get("team"),
            f"{direction}_roster_id": rid,
            f"{direction}_manager": roster_manager_by_id.get(rid),
        })
    return rows


enriched_transactions = []
for week, transactions in transactions_by_week.items():
    for tx in transactions:
        settings = tx.get("settings") or {}
        roster_ids = []
        for roster_id in (tx.get("roster_ids") or []):
            try:
                roster_ids.append(int(roster_id))
            except (TypeError, ValueError):
                roster_ids.append(roster_id)

        bid = settings.get("waiver_bid")
        try:
            bid = int(bid) if bid is not None else None
        except (TypeError, ValueError):
            pass

        enriched_transactions.append({
            "week": week,
            "transaction_id": tx.get("transaction_id"),
            "type": tx.get("type"),
            "status": tx.get("status"),
            "created": tx.get("created"),
            "created_utc": epoch_ms_to_iso(tx.get("created")),
            "status_updated": tx.get("status_updated"),
            "status_updated_utc": epoch_ms_to_iso(tx.get("status_updated")),
            "waiver_bid": bid,
            "roster_ids": roster_ids,
            "managers": [roster_manager_by_id.get(rid) for rid in roster_ids],
            "creator_user_id": tx.get("creator"),
            "creator_display_name": user_display_names.get(tx.get("creator")),
            "adds": tx_player_rows(tx.get("adds"), "to"),
            "drops": tx_player_rows(tx.get("drops"), "from"),
            "draft_picks": tx.get("draft_picks") or [],
            "metadata": tx.get("metadata") or {},
            "leg": tx.get("leg"),
            "consenter_ids": tx.get("consenter_ids") or [],
        })

enriched_transactions.sort(
    key=lambda tx: (tx.get("week") or 0, tx.get("created") or 0),
    reverse=True,
)


claim_groups = defaultdict(list)
for tx in enriched_transactions:
    if tx.get("type") != "waiver":
        continue
    for add in tx.get("adds") or []:
        claim_groups[(tx["week"], add["player_id"])].append(tx)

waiver_results = []
for (week, player_id), claims in claim_groups.items():
    completed = [tx for tx in claims if tx.get("status") == "complete"]
    for winner in completed:
        player = players.get(str(player_id), {})
        bids = sorted(
            [
                tx.get("waiver_bid")
                for tx in claims
                if isinstance(tx.get("waiver_bid"), int)
            ],
            reverse=True,
        )
        roster_id = winner.get("roster_ids", [None])[0] if winner.get("roster_ids") else None
        waiver_results.append({
            "week": week,
            "player_id": player_id,
            "player_name": player.get("full_name", player_id),
            "position": player.get("position"),
            "team": player.get("team"),
            "winning_bid": winner.get("waiver_bid"),
            "winning_roster_id": roster_id,
            "winning_manager": roster_manager_by_id.get(roster_id),
            "claim_count_observed": len(claims),
            "bids_observed": bids,
            "second_highest_bid_observed": bids[1] if len(bids) > 1 else None,
            "dropped": winner.get("drops") or [],
            "transaction_id": winner.get("transaction_id"),
            "processed_utc": winner.get("status_updated_utc"),
        })

waiver_results.sort(
    key=lambda row: (row.get("week") or 0, row.get("processed_utc") or ""),
    reverse=True,
)


completed_paid_waivers = [
    row for row in waiver_results
    if isinstance(row.get("winning_bid"), int)
]
all_winning_bids = [row["winning_bid"] for row in completed_paid_waivers]

position_bids = defaultdict(list)
for row in completed_paid_waivers:
    position_bids[row.get("position") or "UNKNOWN"].append(row["winning_bid"])

manager_market = []
for roster in readable_rosters:
    rid = int(roster["roster_id"])
    wins = [row for row in completed_paid_waivers if row.get("winning_roster_id") == rid]
    attempts = [
        tx for tx in enriched_transactions
        if tx.get("type") == "waiver" and rid in (tx.get("roster_ids") or [])
    ]
    win_bids = [row["winning_bid"] for row in wins]
    manager_market.append({
        "roster_id": rid,
        "manager": roster["manager"],
        "faab_remaining_official": roster.get("faab", {}).get("remaining"),
        "waiver_wins_observed": len(wins),
        "waiver_claim_attempts_observed": len(attempts),
        "faab_spent_on_observed_wins": sum(win_bids),
        "average_winning_bid": round(mean(win_bids), 2) if win_bids else None,
        "median_winning_bid": median(win_bids) if win_bids else None,
        "max_winning_bid": max(win_bids) if win_bids else None,
        "zero_dollar_wins": sum(1 for bid in win_bids if bid == 0),
    })

waiver_market = {
    "season_budget": waiver_budget,
    "completed_waivers_observed": len(completed_paid_waivers),
    "total_faab_spent_observed": sum(all_winning_bids),
    "average_winning_bid": round(mean(all_winning_bids), 2) if all_winning_bids else None,
    "median_winning_bid": median(all_winning_bids) if all_winning_bids else None,
    "max_winning_bid": max(all_winning_bids) if all_winning_bids else None,
    "by_position": {
        position: {
            "count": len(bids),
            "average": round(mean(bids), 2),
            "median": median(bids),
            "max": max(bids),
        }
        for position, bids in sorted(position_bids.items())
        if bids
    },
    "manager_behavior": manager_market,
    "top_winning_bids": sorted(
        completed_paid_waivers,
        key=lambda row: row.get("winning_bid") or 0,
        reverse=True,
    )[:25],
    "recent_results": waiver_results[:50],
}


matchups_by_week = {}
for week in sorted({w for w in (current_week - 1, current_week) if w >= 1}):
    matchups_by_week[week] = try_get_json(
        f"{BASE}/league/{LEAGUE_ID}/matchups/{week}",
        f"matchups week {week}",
        [],
    )

roster_projection = {
    int(roster["roster_id"]): roster.get("projected_starter_points")
    for roster in readable_rosters
}


def build_matchup_groups(week, rows):
    groups = defaultdict(list)
    for row in rows:
        rid = int(row.get("roster_id"))
        groups[row.get("matchup_id")].append({
            "roster_id": rid,
            "manager": roster_manager_by_id.get(rid),
            "points": row.get("points"),
            "custom_points": row.get("custom_points"),
            "projected_starter_points": roster_projection.get(rid),
            "starters": row.get("starters") or [],
            "players": row.get("players") or [],
            "starters_points": row.get("starters_points") or [],
            "players_points": row.get("players_points") or {},
        })
    return [
        {"week": week, "matchup_id": matchup_id, "teams": teams}
        for matchup_id, teams in groups.items()
    ]


current_matchups = build_matchup_groups(
    current_week,
    matchups_by_week.get(current_week, []),
)
previous_matchups = (
    build_matchup_groups(current_week - 1, matchups_by_week.get(current_week - 1, []))
    if current_week > 1 else []
)

my_matchup = None
if my_roster_id is not None:
    for matchup in current_matchups:
        if any(team.get("roster_id") == my_roster_id for team in matchup["teams"]):
            my_matchup = matchup
            break


trend_adds = try_get_json(
    f"{BASE}/players/nfl/trending/add?lookback_hours=24&limit=100",
    "24-hour add trends",
    [],
)
trend_drops = try_get_json(
    f"{BASE}/players/nfl/trending/drop?lookback_hours=24&limit=100",
    "24-hour drop trends",
    [],
)


def enrich_trends(rows):
    result = []
    for row in rows:
        pid = str(row.get("player_id"))
        player = players.get(pid, {})
        result.append({
            "player_id": pid,
            "name": player.get("full_name", pid),
            "position": player.get("position"),
            "team": player.get("team"),
            "count": row.get("count"),
            "is_available_in_this_league": pid not in rostered_player_ids,
            "projection": projection_for(pid),
            "injury_status": player.get("injury_status"),
        })
    return result


player_trends = {
    "lookback_hours": 24,
    "adds": enrich_trends(trend_adds),
    "drops": enrich_trends(trend_drops),
}


def state_from_daily(feed):
    state = {}
    if not feed:
        return state

    for roster in feed.get("rosters", []) or []:
        manager = roster.get("manager")
        for player in roster.get("players", []) or []:
            pid = str(player.get("player_id"))
            state[pid] = {
                "name": player.get("name"),
                "team": player.get("team"),
                "status": player.get("status"),
                "injury_status": player.get("injury_status"),
                "practice_participation": player.get("practice_participation"),
                "rostered_by": manager,
            }

    for player in feed.get("free_agents", []) or []:
        pid = str(player.get("player_id"))
        state.setdefault(pid, {
            "name": player.get("name"),
            "team": player.get("team"),
            "status": player.get("status"),
            "injury_status": player.get("injury_status"),
            "practice_participation": player.get("practice_participation"),
            "rostered_by": None,
        })

    return state


previous_state = state_from_daily(previous_daily)
current_state = {}
for roster in readable_rosters:
    for player in roster["players"]:
        current_state[str(player["player_id"])] = {
            "name": player.get("name"),
            "team": player.get("team"),
            "status": player.get("status"),
            "injury_status": player.get("injury_status"),
            "practice_participation": player.get("practice_participation"),
            "rostered_by": roster.get("manager"),
        }
for player in free_agents:
    current_state.setdefault(str(player["player_id"]), {
        "name": player.get("name"),
        "team": player.get("team"),
        "status": player.get("status"),
        "injury_status": player.get("injury_status"),
        "practice_participation": player.get("practice_participation"),
        "rostered_by": None,
    })

status_changes = []
for player_id in sorted(set(previous_state) & set(current_state)):
    before = previous_state[player_id]
    after = current_state[player_id]
    changed_fields = {}
    for field in [
        "team", "status", "injury_status",
        "practice_participation", "rostered_by",
    ]:
        if before.get(field) != after.get(field):
            changed_fields[field] = {
                "from": before.get(field),
                "to": after.get(field),
            }
    if changed_fields:
        status_changes.append({
            "player_id": player_id,
            "name": after.get("name") or before.get("name"),
            "changes": changed_fields,
        })


recent_transaction_weeks = {
    week for week in range(max(1, current_week - 2), current_week + 1)
}
recent_transactions = [
    tx for tx in enriched_transactions
    if tx.get("week") in recent_transaction_weeks
]
my_transactions = [
    tx for tx in enriched_transactions
    if my_roster_id is not None and my_roster_id in (tx.get("roster_ids") or [])
]


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
    "data_quality": {
        "warnings": DATA_WARNINGS,
        "previous_feed_available_for_change_detection": previous_daily is not None,
    },
    "managers": users,
    "rosters": readable_rosters,
    "standings": standings,
    "my_team": my_roster,
    "free_agents": free_agents,
    "free_agents_by_position": free_agents_by_position,
    "transactions": enriched_transactions,
    "waiver_market": waiver_market,
    "current_matchups": current_matchups,
    "previous_matchups": previous_matchups,
    "my_matchup": my_matchup,
    "player_trends": player_trends,
    "status_changes": status_changes,
}

with open("sleeper_snapshot.json", "w", encoding="utf-8") as f:
    json.dump(snapshot, f, indent=2)

print(
    f"Done: {len(readable_rosters)} rosters, "
    f"{len(free_agents)} free agents, "
    f"{len(enriched_transactions)} transactions, "
    f"{len(waiver_results)} processed waiver results."
)

daily_feed = {
    "generated_at_utc": snapshot["generated_at_utc"],
    "league_id": LEAGUE_ID,
    "league_name": league.get("name"),
    "settings": {
        "num_teams": league_settings.get("num_teams"),
        "waiver_budget": league_settings.get("waiver_budget"),
        "waiver_day_of_week": league_settings.get("waiver_day_of_week"),
        "daily_waivers_hour": league_settings.get("daily_waivers_hour"),
        "roster_positions": roster_positions,
        "scoring_settings": scoring_settings,
    },
    "nfl_state": nfl_state,
    "projection_metadata": snapshot["projection_metadata"],
    "data_quality": snapshot["data_quality"],
    "my_team_name": MY_TEAM_NAME,
    "my_roster_id": my_roster_id,
    "my_team": my_roster,
    "standings": standings,
    "my_matchup": my_matchup,
    "current_matchups": current_matchups,
    "previous_matchups": previous_matchups,
    "rosters": readable_rosters,
    "free_agents": free_agents[:300],
    "free_agents_by_position": free_agents_by_position,
    "recent_transactions": recent_transactions,
    "my_transactions": my_transactions[:100],
    "waiver_market": waiver_market,
    "player_trends": player_trends,
    "status_changes": status_changes,
}

with open("sleeper_daily.json", "w", encoding="utf-8") as f:
    json.dump(daily_feed, f, separators=(",", ":"))

print("Compact daily feed saved to sleeper_daily.json")

html = []
html.append("<!DOCTYPE html>")
html.append("<html>")
html.append("<head><meta charset='utf-8'><title>Fantasy Football Feed</title></head>")
html.append("<body>")
html.append("<h1>Fantasy Football Feed</h1>")
html.append(f"<p>Last updated: {snapshot['generated_at_utc']}</p>")
html.append(f"<p><strong>League:</strong> {league.get('name')}</p>")
html.append(f"<p><strong>Week:</strong> {current_week}</p>")

if my_roster:
    html.append("<h2>My Team</h2>")
    html.append(
        f"<p><strong>{my_roster['manager']}</strong> | "
        f"FAAB remaining: {my_roster.get('faab', {}).get('remaining')} | "
        f"Waiver priority: {my_roster.get('waiver_position')}</p>"
    )

html.append("<h2>Recent Waiver Results</h2><ul>")
for row in waiver_results[:20]:
    html.append(
        f"<li>Week {row.get('week')}: {row.get('player_name')} "
        f"to {row.get('winning_manager')} for "
        f"FAAB {row.get('winning_bid')} "
        f"({row.get('claim_count_observed')} observed claim(s))</li>"
    )
html.append("</ul>")

html.append("<h2>Top Available Players by Position</h2>")
for position, pool in free_agents_by_position.items():
    html.append(f"<h3>{position}</h3><ul>")
    for player in pool[:10]:
        projection = (player.get("projection") or {}).get("projected_points")
        html.append(
            f"<li>{player['name']} - {player.get('team')} "
            f"- proj {projection} - {player.get('injury_status') or 'healthy'}</li>"
        )
    html.append("</ul>")

html.append("<p><a href='sleeper_daily.json'>Raw Sleeper Daily Data</a></p>")
html.append("</body></html>")

with open("index.html", "w", encoding="utf-8") as f:
    f.write("\n".join(html))

print("Readable HTML feed saved to index.html")
