import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
FANTASY_URL = (
    "https://fantasysports.yahooapis.com/fantasy/v2/"
    "users;use_login=1/games;game_keys=nfl/teams?format=json"
)
REDIRECT_URI = "https://localhost:8080/"


def require_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def post_form(url, fields):
    body = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "fantasy-football-feed/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def get_json(url, access_token):
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": "fantasy-football-feed/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def collect_values(node, key):
    values = []
    if isinstance(node, dict):
        for current_key, value in node.items():
            if current_key == key and isinstance(value, (str, int, float)):
                values.append(str(value))
            values.extend(collect_values(value, key))
    elif isinstance(node, list):
        for value in node:
            values.extend(collect_values(value, key))
    return values


def main():
    client_id = require_env("YAHOO_CLIENT_ID")
    client_secret = require_env("YAHOO_CLIENT_SECRET")
    refresh_token = require_env("YAHOO_REFRESH_TOKEN")

    token_response = post_form(
        TOKEN_URL,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )

    access_token = token_response.get("access_token")
    if not access_token:
        raise RuntimeError("Yahoo token refresh returned no access_token")

    print("Yahoo OAuth refresh succeeded.")

    returned_refresh = token_response.get("refresh_token")
    if returned_refresh and returned_refresh != refresh_token:
        print(
            "::warning::Yahoo returned a different refresh token. "
            "The stored YAHOO_REFRESH_TOKEN may need to be updated before a future run."
        )

    fantasy_response = get_json(FANTASY_URL, access_token)
    if "fantasy_content" not in fantasy_response:
        raise RuntimeError("Yahoo Fantasy API response did not contain fantasy_content")

    team_keys = sorted(set(collect_values(fantasy_response, "team_key")))
    league_keys = sorted(set(collect_values(fantasy_response, "league_key")))

    print("Yahoo Fantasy API request succeeded.")
    print(f"Authenticated NFL fantasy teams discovered: {len(team_keys)}")
    print(f"Associated league keys discovered: {len(league_keys)}")

    if not team_keys:
        print(
            "::warning::The OAuth connection works, but no current NFL fantasy team "
            "was returned for the authorized Yahoo account."
        )


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"Yahoo request failed with HTTP {exc.code}.", file=sys.stderr)
        raise
