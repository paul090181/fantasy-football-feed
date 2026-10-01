import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
PUBLIC_GAME_URL = "https://fantasysports.yahooapis.com/fantasy/v2/game/nfl?format=json"
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


def post_refresh_token(client_id, client_secret, refresh_token):
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "redirect_uri": REDIRECT_URI,
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")

    credentials = base64.b64encode(
        f"{client_id}:{client_secret}".encode("utf-8")
    ).decode("ascii")

    request = urllib.request.Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "fantasy-football-feed/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}
        error = payload.get("error") or f"HTTP {exc.code}"
        description = payload.get("error_description")
        safe_message = f"Yahoo token refresh failed: {error}"
        if description:
            safe_message += f" - {description}"
        raise RuntimeError(safe_message) from None


def describe_api_error(exc):
    raw = exc.read().decode("utf-8", errors="replace").strip()
    if not raw:
        return f"HTTP {exc.code}"

    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            description = (
                payload.get("description")
                or payload.get("error_description")
                or payload.get("message")
                or payload.get("error")
            )
            if description:
                return f"HTTP {exc.code}: {description}"
    except json.JSONDecodeError:
        pass

    # Yahoo Fantasy often returns XML errors. Extract only the human-readable
    # description so logs stay useful without dumping full response bodies.
    import re

    match = re.search(r"<description>(.*?)</description>", raw, flags=re.I | re.S)
    if match:
        description = re.sub(r"\s+", " ", match.group(1)).strip()
        return f"HTTP {exc.code}: {description}"

    compact = re.sub(r"\s+", " ", raw)
    return f"HTTP {exc.code}: {compact[:300]}"


def get_json(url, access_token):
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": "fantasy-football-feed/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(describe_api_error(exc)) from None


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
    print(f"Stored Yahoo refresh token length: {len(refresh_token)} characters")

    token_response = post_refresh_token(client_id, client_secret, refresh_token)

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

    # Probe a basic game resource first. If this is forbidden too, the problem is
    # app-level Fantasy API authorization rather than the user's league/team data.
    try:
        public_response = get_json(PUBLIC_GAME_URL, access_token)
        if "fantasy_content" not in public_response:
            raise RuntimeError(
                "Yahoo basic game probe returned no fantasy_content"
            )
        print("Yahoo basic Fantasy API probe succeeded.")
    except RuntimeError as exc:
        raise RuntimeError(f"Yahoo basic Fantasy API probe failed: {exc}") from None

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
        print(f"Yahoo Fantasy API request failed with HTTP {exc.code}.", file=sys.stderr)
        raise
