"""Refresh and save Paul's read-only Yahoo Fantasy Football feed."""

import os
import sys

from yahoo_feed import (
    build_snapshot,
    decrypt_refresh_token,
    encrypt_refresh_token,
    refresh_access_token,
    write_json_atomic,
    yahoo_get,
    YahooAuthorizationPending,
)


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


client_id = required("YAHOO_CLIENT_ID")
client_secret = required("YAHOO_CLIENT_SECRET")
token_key = required("YAHOO_TOKEN_KEY")

with open("yahoo_refresh_token.enc", "rb") as handle:
    old_refresh_token = decrypt_refresh_token(handle.read(), token_key)

token = refresh_access_token(client_id, client_secret, old_refresh_token)
new_refresh_token = token["refresh_token"]
if new_refresh_token != old_refresh_token:
    with open("yahoo_refresh_token.enc", "wb") as handle:
        handle.write(encrypt_refresh_token(new_refresh_token, token_key))

try:
    snapshot = build_snapshot(lambda resource: yahoo_get(token["access_token"], resource))
except YahooAuthorizationPending:
    write_json_atomic(
        "yahoo_status.json",
        {
            "platform": "yahoo",
            "state": "awaiting_yahoo_api_provisioning",
            "message": "Yahoo has not activated Fantasy Sports API access for this Client ID yet.",
        },
    )
    print("Yahoo Fantasy API provisioning is still pending; no credentials need to be changed.")
    sys.exit(0)
write_json_atomic("yahoo_snapshot.json", snapshot)
write_json_atomic(
    "yahoo_daily.json",
    {
        "schema_version": snapshot["schema_version"],
        "platform": snapshot["platform"],
        "generated_at": snapshot["generated_at"],
        "league_key": snapshot["league_key"],
        "team_key": snapshot["team_key"],
        "resources": {
            key: snapshot["resources"][key]
            for key in ("scoreboard", "standings", "transactions", "roster")
        },
    },
)
write_json_atomic(
    "yahoo_status.json",
    {
        "platform": "yahoo",
        "state": "connected",
        "generated_at": snapshot["generated_at"],
        "league_key": snapshot["league_key"],
        "team_key": snapshot["team_key"],
    },
)
print(f"Yahoo snapshot updated at {snapshot['generated_at']}")
