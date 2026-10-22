# Fantasy Football Feed

Automated, read-only snapshots for Paul's Sleeper and Yahoo fantasy-football leagues.

## Yahoo authorization

Yahoo uses OAuth 2.0. Client credentials and the token-encryption key live only in GitHub Actions secrets. The long-lived refresh token is committed only as encrypted ciphertext in `yahoo_refresh_token.enc`; access tokens and plaintext refresh tokens are never committed or printed.

Required Actions secrets:

- `YAHOO_CLIENT_ID`
- `YAHOO_CLIENT_SECRET`
- `YAHOO_TOKEN_KEY` (a unique passphrase of at least 24 characters)

Use `yahoo_authorize.html` to obtain the one-time authorization code, then run the **Authorize Yahoo Fantasy Feed** workflow once. The hourly **Update Yahoo Fantasy Feed** workflow starts after the encrypted token file exists.
