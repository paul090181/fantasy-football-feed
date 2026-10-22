"""Yahoo Fantasy Sports read-only feed helpers."""

from __future__ import annotations

import json
import os
import tempfile
import base64
import hashlib
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from cryptography.fernet import Fernet


AUTHORIZATION_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
FANTASY_API = "https://fantasysports.yahooapis.com/fantasy/v2"


def _fernet(passphrase: str) -> Fernet:
    if len(passphrase) < 24:
        raise ValueError("Yahoo token encryption passphrase must be at least 24 characters")
    key = base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_refresh_token(refresh_token: str, passphrase: str) -> bytes:
    return _fernet(passphrase).encrypt(refresh_token.encode("utf-8"))


def decrypt_refresh_token(encrypted: bytes, passphrase: str) -> str:
    return _fernet(passphrase).decrypt(encrypted).decode("utf-8")


def build_authorization_url(client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
    )
    return f"{AUTHORIZATION_URL}?{query}"


def extract_authorization_code(value: str) -> str:
    value = value.strip()
    if value.startswith(("http://", "https://")):
        codes = parse_qs(urlparse(value).query).get("code", [])
        if not codes or not codes[0]:
            raise ValueError("Redirect URL does not contain a Yahoo authorization code")
        return codes[0]
    if not value:
        raise ValueError("Yahoo authorization code is empty")
    return value


def exchange_authorization_code(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    response = requests.post(
        TOKEN_URL,
        auth=(client_id, client_secret),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict[str, Any]:
    response = requests.post(
        TOKEN_URL,
        auth=(client_id, client_secret),
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    response.raise_for_status()
    token = response.json()
    token.setdefault("refresh_token", refresh_token)
    return token


def yahoo_get(access_token: str, resource: str) -> dict[str, Any]:
    response = requests.get(
        f"{FANTASY_API}/{resource.lstrip('/')}",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"format": "json"},
        timeout=45,
    )
    response.raise_for_status()
    return response.json()


def recursive_values(value: Any, key: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            if child_key == key:
                found.append(child_value)
            found.extend(recursive_values(child_value, key))
    elif isinstance(value, list):
        for child in value:
            found.extend(recursive_values(child, key))
    return found


def unique(values: Iterable[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def build_snapshot(get, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    leagues = get("users;use_login=1/games;game_codes=nfl/leagues")
    league_keys = unique(recursive_values(leagues, "league_key"))
    if not league_keys:
        raise RuntimeError("Yahoo returned no NFL fantasy leagues for the authorized user")

    # Yahoo returns seasons newest-first in normal operation. Numeric game keys
    # are embedded at the start of each league key, so select the newest key.
    league_key = max(league_keys, key=lambda value: int(str(value).split(".", 1)[0]))
    owned_teams = get("users;use_login=1/games;game_codes=nfl/teams")
    team_keys = [
        value
        for value in unique(recursive_values(owned_teams, "team_key"))
        if str(value).startswith(f"{league_key}.t.")
    ]
    if not team_keys:
        raise RuntimeError(f"Yahoo returned no owned team for league {league_key}")
    team_key = team_keys[0]

    resources = {
        "league": get(f"league/{league_key}"),
        "settings": get(f"league/{league_key}/settings"),
        "standings": get(f"league/{league_key}/standings"),
        "scoreboard": get(f"league/{league_key}/scoreboard"),
        "teams": get(f"league/{league_key}/teams"),
        "transactions": get(f"league/{league_key}/transactions"),
        "roster": get(f"team/{team_key}/roster"),
        "matchups": get(f"team/{team_key}/matchups"),
    }
    return {
        "schema_version": 1,
        "platform": "yahoo",
        "generated_at": generated_at,
        "league_key": league_key,
        "team_key": team_key,
        "discovery": {"leagues": leagues, "owned_teams": owned_teams},
        "resources": resources,
    }


def write_json_atomic(path: str, payload: dict[str, Any]) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(prefix=".yahoo-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_path, path)
    except BaseException:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise
