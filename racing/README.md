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

## Download results

```bash
python -m racing.results                     # races in the next 24 hours, plus recent days
python -m racing.results --date 2026-10-17   # one race day
```

This writes `racing/data/results-<date>.csv` with one row per runner in every
settled WIN market for each race day: date, course, country, market time (UTC),
market id, race name, selection id, runner, BSP, result (`WINNER`, `LOSER` or
`REMOVED`) and whether it was a non-runner. Races that haven't been settled yet
are left out until the next run. It places no bets.

Countries come from `BETFAIR_COUNTRIES` in `racing/.env` (for example
`GB,IE,AU`). Each race is filed under its local date at the course, so a
Flemington card stays together even though it starts before midnight UTC. On
Windows that needs time zone data: run `pip install tzdata` once in the
virtual environment.

Betfair stops listing a market (with its course and runner names) once it
closes, so each run saves every race starting in the next 24 hours to
`racing/data/racecard-<date>.json`, then rewrites the results for the last
three race days. Two runs a day, about 12 hours apart, cover every race.
Results stay available for settled markets for roughly 90 days, but only for
days whose race card was saved. Older seasons come from the Betfair historical
data files instead. `racing/data/` is gitignored.

### Run it automatically on Windows

`run_results.bat` in the repo root runs the download and appends its output to
`racing\data\log.txt`. Schedule it twice a day, about 12 hours apart, from
Command Prompt (the PC has to be on and logged in at those times). For GB, IE
and AU racing, 10:00 and 22:30 UTC work all year; use the matching local times:

```bat
schtasks /create /tn "Betfair results morning" /tr "%CD%\run_results.bat" /sc daily /st 10:00
schtasks /create /tn "Betfair results evening" /tr "%CD%\run_results.bat" /sc daily /st 22:30
```
