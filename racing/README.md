# Racing 2026: Betfair API connection

A small, read-only client built on the `betfairlightweight` library in this repo.
It logs in with your own Betfair app key and lists today's horse racing WIN
markets. It never places bets.

## Setup

1. From the repo root, create a virtual environment and install the library:

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -e .
   ```

2. Copy the example settings and fill in your own details:

   ```bash
   cp racing/.env.example racing/.env      # Windows: copy racing\.env.example racing\.env
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
python -m unittest racing.test_config racing.test_results
```

## Download a day's results

```bash
python -m racing.results                     # today (UTC)
python -m racing.results --date 2026-10-17   # a chosen day
```

This writes `racing/data/results-<date>.csv` with one row per runner in every
settled WIN market: date, course, market time (UTC), market id, race name,
selection id, runner, BSP, result (`WINNER`, `LOSER` or `REMOVED`) and whether
it was a non-runner. Races that haven't been settled yet are left out until
the next run. It places no bets.

Betfair stops listing a market (with its course and runner names) once it
closes, so each run saves that day's race card to
`racing/data/racecard-<date>.json` and adds to it. Run it once before racing
starts and again after the last race. Results stay available for settled
markets for roughly 90 days, but only for days whose race card was saved.
Older seasons come from the Betfair historical data files instead.
`racing/data/` is gitignored.
