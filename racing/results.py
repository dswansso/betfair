"""
Read-only results download: writes one CSV row per runner for each day's
settled horse racing WIN markets, with BSP, result and non-runners. It places
no bets.

    python -m racing.results                  # races in the next 24 hours, plus recent days
    python -m racing.results --date 2026-10-17

Betfair's listMarketCatalogue stops returning a market once it closes, so
course and runner names have to be captured while the market is still open.
Each run saves every race starting in the next 24 hours to
racing/data/racecard-<date>.json, filed by the race's local date at the
course, then rewrites racing/data/results-<date>.csv for the last few days.
Two runs a day about 12 hours apart cover every race. Results
(listMarketBook) stay available for settled markets for roughly 90 days, but
only for markets whose race card was saved.
"""

import argparse
import csv
import datetime
import json
import os
import sys
import zoneinfo

from betfairlightweight import filters
from betfairlightweight.exceptions import BetfairError

from racing.check_connection import HORSE_RACING_EVENT_TYPE_ID
from racing.config import ConfigError, create_client, load_config, login

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# listMarketBook allows a total request weight of 200; SP_TRADED weighs 7 per market.
BOOK_CHUNK_SIZE = 25

# Default runs save races starting up to this far ahead, and also catch races
# that started recently but haven't settled yet.
LOOKAHEAD = datetime.timedelta(hours=24)
LOOKBACK = datetime.timedelta(hours=6)

# Default runs rewrite the results of race days up to this many days old.
RECENT_DAYS = 3

CSV_COLUMNS = [
    "date",
    "course",
    "country",
    "market_time_utc",
    "market_id",
    "market_name",
    "selection_id",
    "runner",
    "bsp",
    "result",
    "non_runner",
]


def day_window(day: datetime.date):
    """Covers every course's local day for this date, from UTC+14 to UTC-12."""
    midnight = datetime.datetime.combine(day, datetime.time.min, datetime.timezone.utc)
    return midnight - datetime.timedelta(hours=14), midnight + datetime.timedelta(
        hours=36
    )


def upcoming_window(now: datetime.datetime):
    return now - LOOKBACK, now + LOOKAHEAD


def race_date(market: dict) -> str:
    """The race's date at the course, falling back to the UTC date if the time zone is unknown."""
    start = datetime.datetime.fromisoformat(
        market["marketStartTime"].replace("Z", "+00:00")
    )
    try:
        zone = zoneinfo.ZoneInfo((market.get("event") or {}).get("timezone"))
    except (zoneinfo.ZoneInfoNotFoundError, TypeError, ValueError):
        zone = datetime.timezone.utc
    return start.astimezone(zone).date().isoformat()


def racecard_path(day: datetime.date) -> str:
    return os.path.join(DATA_DIR, "racecard-%s.json" % day.isoformat())


def results_path(day: datetime.date) -> str:
    return os.path.join(DATA_DIR, "results-%s.csv" % day.isoformat())


def load_racecard(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_racecard(path: str, racecard: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(racecard, f, indent=1, sort_keys=True)


def group_by_date(catalogues: list) -> dict:
    by_date = {}
    for market in catalogues:
        by_date.setdefault(race_date(market), []).append(market)
    return by_date


def merge_catalogue(racecard: dict, catalogues: list) -> int:
    """Adds lightweight listMarketCatalogue results to the race card; returns how many were new."""
    added = 0
    for market in catalogues:
        event = market.get("event") or {}
        if market["marketId"] not in racecard:
            added += 1
        racecard[market["marketId"]] = {
            "date": race_date(market),
            "course": event.get("venue") or event.get("name"),
            "country": event.get("countryCode"),
            "market_name": market.get("marketName"),
            "market_time_utc": market.get("marketStartTime"),
            "runners": {
                str(r["selectionId"]): r.get("runnerName")
                for r in market.get("runners", [])
            },
        }
    return added


def rows_from_books(racecard: dict, books: list) -> list:
    """Builds CSV rows from lightweight listMarketBook results for CLOSED markets only."""
    rows = []
    for book in books:
        if book.get("status") != "CLOSED":
            continue
        market = racecard[book["marketId"]]
        for runner in book.get("runners", []):
            status = runner.get("status")
            selection_id = str(runner["selectionId"])
            rows.append(
                {
                    "date": market.get("date")
                    or (market["market_time_utc"] or "")[:10],
                    "course": market["course"],
                    "country": market.get("country") or "",
                    "market_time_utc": market["market_time_utc"],
                    "market_id": book["marketId"],
                    "market_name": market["market_name"],
                    "selection_id": selection_id,
                    "runner": market["runners"].get(selection_id, ""),
                    "bsp": (runner.get("sp") or {}).get("actualSP") or "",
                    "result": status,
                    "non_runner": "yes" if status == "REMOVED" else "no",
                }
            )
    rows.sort(key=lambda r: (r["market_time_utc"] or "", r["market_id"]))
    return rows


def write_csv(path: str, rows: list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def fetch_catalogue(client, config, start, end) -> list:
    # One request per country keeps each response well inside Betfair's size limit.
    markets = []
    for country in config.countries:
        markets.extend(
            client.betting.list_market_catalogue(
                filter=filters.market_filter(
                    event_type_ids=[HORSE_RACING_EVENT_TYPE_ID],
                    market_countries=[country],
                    market_type_codes=["WIN"],
                    market_start_time=filters.time_range(
                        from_=start.isoformat(), to=end.isoformat()
                    ),
                ),
                market_projection=["EVENT", "MARKET_START_TIME", "RUNNER_DESCRIPTION"],
                sort="FIRST_TO_START",
                max_results=200,
                lightweight=True,
            )
        )
    return markets


def recent_card_dates(today: datetime.date) -> set:
    """Dates of race cards already saved within the last RECENT_DAYS days."""
    if not os.path.isdir(DATA_DIR):
        return set()
    oldest = (today - datetime.timedelta(days=RECENT_DAYS)).isoformat()
    dates = set()
    for name in os.listdir(DATA_DIR):
        if name.startswith("racecard-") and name.endswith(".json"):
            day = name[len("racecard-") : -len(".json")]
            if day >= oldest:
                dates.add(day)
    return dates


def fetch_books(client, market_ids: list) -> list:
    books = []
    for i in range(0, len(market_ids), BOOK_CHUNK_SIZE):
        books.extend(
            client.betting.list_market_book(
                market_ids=market_ids[i : i + BOOK_CHUNK_SIZE],
                price_projection=filters.price_projection(
                    price_data=filters.price_data(sp_traded=True)
                ),
                lightweight=True,
            )
        )
    return books


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument(
        "--date",
        type=datetime.date.fromisoformat,
        help="one race day as YYYY-MM-DD (the course's local date); "
        "default is races in the next 24 hours plus the last few days",
    )
    return parser.parse_args(argv)


def update_day(client, day: str, new_markets: list) -> None:
    card_file = racecard_path(datetime.date.fromisoformat(day))
    racecard = load_racecard(card_file)
    added = merge_catalogue(racecard, new_markets)
    if not racecard:
        print(
            "%s: no race card saved. Betfair only lists races before they finish, "
            "so this day can't be filled in now." % day
        )
        return
    save_racecard(card_file, racecard)
    rows = rows_from_books(racecard, fetch_books(client, sorted(racecard)))
    settled = len({r["market_id"] for r in rows})
    out_file = results_path(datetime.date.fromisoformat(day))
    write_csv(out_file, rows)
    print(
        "%s: %s races saved (%s new), %s settled, %s still to come or unsettled. "
        "Wrote %s runners to %s"
        % (
            day,
            len(racecard),
            added,
            settled,
            len(racecard) - settled,
            len(rows),
            out_file,
        )
    )


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        config = load_config()
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1

    if not zoneinfo.available_timezones():
        print(
            "Time zone data is missing, so races are filed by UTC date. "
            "Run: pip install tzdata"
        )

    client = create_client(config)
    try:
        login(client, config)
    except BetfairError as e:
        print("Login failed: %s" % e, file=sys.stderr)
        return 1

    try:
        if args.date:
            by_date = group_by_date(
                fetch_catalogue(client, config, *day_window(args.date))
            )
            days = {args.date.isoformat()}
        else:
            now = datetime.datetime.now(datetime.timezone.utc)
            by_date = group_by_date(
                fetch_catalogue(client, config, *upcoming_window(now))
            )
            days = set(by_date) | recent_card_dates(now.date())
        for day in sorted(days):
            update_day(client, day, by_date.get(day, []))
    except BetfairError as e:
        print("Request failed: %s" % e, file=sys.stderr)
        return 1
    finally:
        client.logout()

    if not days:
        print("No races found for %s." % ", ".join(config.countries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
