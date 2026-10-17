"""
Read-only results download: writes one CSV row per runner for a day's settled
horse racing WIN markets, with BSP, result and non-runners. It places no bets.

    python -m racing.results                  # today (UTC)
    python -m racing.results --date 2026-10-17

Betfair's listMarketCatalogue stops returning a market once it closes, so
course and runner names have to be captured while the market is still open.
Each run saves the day's race card to racing/data/racecard-<date>.json and
adds to it, so run this once before racing starts and again after the last
race. Results (listMarketBook) stay available for settled markets for
roughly 90 days, but only for markets whose race card was saved.
"""

import argparse
import csv
import datetime
import json
import os
import sys

from betfairlightweight import filters
from betfairlightweight.exceptions import BetfairError

from racing.check_connection import HORSE_RACING_EVENT_TYPE_ID
from racing.config import ConfigError, create_client, load_config, login

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# listMarketBook allows a total request weight of 200; SP_TRADED weighs 7 per market.
BOOK_CHUNK_SIZE = 25

CSV_COLUMNS = [
    "date",
    "course",
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
    start = datetime.datetime.combine(day, datetime.time.min, datetime.timezone.utc)
    end = start + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
    return start, end


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


def merge_catalogue(racecard: dict, catalogues: list) -> int:
    """Adds lightweight listMarketCatalogue results to the race card; returns how many were new."""
    added = 0
    for market in catalogues:
        event = market.get("event") or {}
        if market["marketId"] not in racecard:
            added += 1
        racecard[market["marketId"]] = {
            "course": event.get("venue") or event.get("name"),
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
                    "date": (market["market_time_utc"] or "")[:10],
                    "course": market["course"],
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


def fetch_catalogue(client, config, day: datetime.date) -> list:
    start, end = day_window(day)
    return client.betting.list_market_catalogue(
        filter=filters.market_filter(
            event_type_ids=[HORSE_RACING_EVENT_TYPE_ID],
            market_countries=config.countries,
            market_type_codes=["WIN"],
            market_start_time=filters.time_range(
                from_=start.isoformat(), to=end.isoformat()
            ),
        ),
        market_projection=["EVENT", "MARKET_START_TIME", "RUNNER_DESCRIPTION"],
        sort="FIRST_TO_START",
        max_results=1000,
        lightweight=True,
    )


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
        default=datetime.datetime.now(datetime.timezone.utc).date(),
        help="race day as YYYY-MM-DD (UTC), default today",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        config = load_config()
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1

    client = create_client(config)
    try:
        login(client, config)
    except BetfairError as e:
        print("Login failed: %s" % e, file=sys.stderr)
        return 1

    card_file = racecard_path(args.date)
    racecard = load_racecard(card_file)
    try:
        added = merge_catalogue(racecard, fetch_catalogue(client, config, args.date))
        save_racecard(card_file, racecard)
        print(
            "Race card for %s: %s WIN markets saved (%s new)."
            % (args.date, len(racecard), added)
        )
        books = fetch_books(client, sorted(racecard)) if racecard else []
    except BetfairError as e:
        print("Request failed: %s" % e, file=sys.stderr)
        return 1
    finally:
        client.logout()

    if not racecard:
        print(
            "No race card saved for %s. Betfair only lists markets before they "
            "close, so run this on the day before racing finishes." % args.date
        )
        return 0

    rows = rows_from_books(racecard, books)
    settled = len({r["market_id"] for r in rows})
    out_file = results_path(args.date)
    write_csv(out_file, rows)
    print(
        "%s races settled, %s still to come or unsettled."
        % (settled, len(racecard) - settled)
    )
    print("Wrote %s runners to %s" % (len(rows), out_file))
    return 0


if __name__ == "__main__":
    sys.exit(main())
