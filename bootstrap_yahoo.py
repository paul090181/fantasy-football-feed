"""One-time Yahoo OAuth bootstrap for GitHub Actions."""

import os

from yahoo_feed import exchange_authorization_code, encrypt_refresh_token, extract_authorization_code


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


token = exchange_authorization_code(
    client_id=required("YAHOO_CLIENT_ID"),
    client_secret=required("YAHOO_CLIENT_SECRET"),
    code=extract_authorization_code(required("YAHOO_AUTHORIZATION_CODE")),
    redirect_uri=required("YAHOO_REDIRECT_URI"),
)
refresh_token = token.get("refresh_token")
if not refresh_token:
    raise RuntimeError("Yahoo did not return a refresh token")

encrypted = encrypt_refresh_token(refresh_token, required("YAHOO_TOKEN_KEY"))
with open("yahoo_refresh_token.enc", "wb") as handle:
    handle.write(encrypted)

print("Yahoo authorization succeeded; encrypted refresh token created.")
