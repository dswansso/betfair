# Racing 2026: Betfair API connection

A small, read-only client built on the `betfairlightweight` library in this repo.
It logs in with your own Betfair app key and lists today's horse racing WIN
markets. It never places bets.

## Setup

1. Install the dependencies from the repo root:

   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

2. Copy the example settings and fill in your own details:

   ```bash
   cp racing/.env.example racing/.env
   ```

   `racing/.env` is gitignored. Keep your app key, username and password in
   that file (or in environment variables) and never commit them. Variables
   already set in your shell take priority over the file.

   - `BETFAIR_APP_KEY`: the delayed key is fine for this check.
   - `BETFAIR_REGION`: `international` (betfair.com) or `au` (betfair.com.au).
   - `BETFAIR_CERTS_DIR`: leave blank for interactive login. Set it to a folder
     holding your `.crt` and `.key` to use certificate (bot) login instead.

## Run the connection check

```bash
python -m racing.check_connection
```

You should see `Logged in to Betfair` followed by a list of today's markets.
With the delayed key, prices returned by later calls lag the live market.

## Tests

```bash
python -m unittest racing.test_config
```
