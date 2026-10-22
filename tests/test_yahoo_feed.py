import json
import os
import tempfile
import unittest
from unittest.mock import patch
from requests import HTTPError

import yahoo_feed


class YahooOAuthTests(unittest.TestCase):
    def test_extract_authorization_code_decodes_full_redirect_url(self):
        redirect = "https://localhost:8080/?code=abc%2Fdef%3D&state=state-value"
        self.assertEqual("abc/def=", yahoo_feed.extract_authorization_code(redirect))

    def test_extract_authorization_code_accepts_code_only(self):
        self.assertEqual("plain-code", yahoo_feed.extract_authorization_code("plain-code"))

    def test_authorization_url_uses_configured_redirect_and_read_access(self):
        url = yahoo_feed.build_authorization_url(
            client_id="client-id",
            redirect_uri="https://localhost:8080/",
            state="fixed-state",
        )
        self.assertIn("client_id=client-id", url)
        self.assertIn("redirect_uri=https%3A%2F%2Flocalhost%3A8080%2F", url)
        self.assertIn("response_type=code", url)
        self.assertIn("state=fixed-state", url)

    @patch("yahoo_feed.requests.post")
    def test_refresh_access_token_uses_basic_auth_and_rotates_refresh_token(self, post):
        post.return_value.raise_for_status.return_value = None
        post.return_value.json.return_value = {
            "access_token": "new-access",
            "refresh_token": "rotated-refresh",
            "expires_in": 3600,
        }

        token = yahoo_feed.refresh_access_token(
            client_id="client-id",
            client_secret="client-secret",
            refresh_token="old-refresh",
        )

        self.assertEqual("new-access", token["access_token"])
        self.assertEqual("rotated-refresh", token["refresh_token"])
        _, kwargs = post.call_args
        self.assertEqual(("client-id", "client-secret"), kwargs["auth"])
        self.assertEqual("refresh_token", kwargs["data"]["grant_type"])
        self.assertEqual("old-refresh", kwargs["data"]["refresh_token"])

    @patch("yahoo_feed.requests.post")
    def test_refresh_keeps_existing_token_when_yahoo_does_not_rotate_it(self, post):
        post.return_value.raise_for_status.return_value = None
        post.return_value.json.return_value = {
            "access_token": "new-access",
            "expires_in": 3600,
        }

        token = yahoo_feed.refresh_access_token(
            client_id="client-id",
            client_secret="client-secret",
            refresh_token="old-refresh",
        )

        self.assertEqual("old-refresh", token["refresh_token"])


class YahooDataTests(unittest.TestCase):
    @patch("yahoo_feed.requests.get")
    def test_yahoo_get_classifies_unprovisioned_application(self, get):
        get.return_value.status_code = 403
        get.return_value.ok = False
        get.return_value.text = (
            '{"error":{"description":"This application is not authorized '
            'to perform this action."}}'
        )
        with self.assertRaises(yahoo_feed.YahooAuthorizationPending):
            yahoo_feed.yahoo_get("access-token", "game/nfl")

    @patch("yahoo_feed.requests.get")
    def test_yahoo_get_includes_provider_error_body(self, get):
        get.return_value.status_code = 403
        get.return_value.ok = False
        get.return_value.text = '{"error":{"description":"Fantasy access denied"}}'
        with self.assertRaisesRegex(HTTPError, "Fantasy access denied"):
            yahoo_feed.yahoo_get("access-token", "game/nfl")

    def test_build_snapshot_discovers_league_and_team_then_fetches_core_resources(self):
        calls = []

        def get(resource):
            calls.append(resource)
            if resource.endswith("/leagues"):
                return {"league_key": "449.l.123"}
            if resource.endswith("/teams") and resource.startswith("users;"):
                return {"team_key": "449.l.123.t.7"}
            return {"resource": resource}

        snapshot = yahoo_feed.build_snapshot(get, generated_at="2026-10-22T12:00:00Z")

        self.assertEqual("yahoo", snapshot["platform"])
        self.assertEqual("449.l.123", snapshot["league_key"])
        self.assertEqual("449.l.123.t.7", snapshot["team_key"])
        self.assertIn("league/449.l.123/settings", calls)
        self.assertIn("league/449.l.123/standings", calls)
        self.assertIn("league/449.l.123/scoreboard", calls)
        self.assertIn("league/449.l.123/transactions", calls)
        self.assertIn("team/449.l.123.t.7/roster", calls)
    def test_recursive_values_finds_keys_inside_yahoo_numbered_objects(self):
        payload = {
            "fantasy_content": {
                "users": {
                    "0": {
                        "user": [
                            {
                                "games": {
                                    "0": {
                                        "game": [
                                            {
                                                "leagues": {
                                                    "0": {
                                                        "league": [
                                                            {"league_key": "449.l.123"},
                                                            {"name": "Paul's League"},
                                                        ]
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        self.assertEqual(["449.l.123"], yahoo_feed.recursive_values(payload, "league_key"))

    def test_write_json_is_atomic_and_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "yahoo_snapshot.json")
            yahoo_feed.write_json_atomic(path, {"platform": "yahoo", "ok": True})
            with open(path, encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual({"platform": "yahoo", "ok": True}, saved)
            self.assertFalse(os.path.exists(path + ".tmp"))

    def test_encrypted_token_round_trip_does_not_expose_plaintext(self):
        encrypted = yahoo_feed.encrypt_refresh_token(
            "refresh-token-value",
            "a private encryption passphrase with enough entropy",
        )
        self.assertNotIn(b"refresh-token-value", encrypted)
        self.assertEqual(
            "refresh-token-value",
            yahoo_feed.decrypt_refresh_token(
                encrypted,
                "a private encryption passphrase with enough entropy",
            ),
        )

    def test_wrong_token_key_cannot_decrypt(self):
        encrypted = yahoo_feed.encrypt_refresh_token(
            "refresh-token-value",
            "correct private encryption passphrase",
        )
        with self.assertRaises(Exception):
            yahoo_feed.decrypt_refresh_token(encrypted, "wrong passphrase")


if __name__ == "__main__":
    unittest.main()
