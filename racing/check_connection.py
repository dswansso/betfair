"""
Read-only connection check: logs in, lists today's horse racing WIN markets
and logs out. It places no bets.

    python -m racing.check_connection
"""

import datetime
import sys

from betfairlightweight import filters
from betfairlightweight.exceptions import BetfairError

from racing.config import ConfigError, create_client, load_config, login

HORSE_RACING_EVENT_TYPE_ID = "7"


def todays_window():
    now = datetime.datetime.now(datetime.timezone.utc)
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    return now, end


def main() -> int:
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
    print("Logged in to Betfair (%s)." % config.region)

    try:
        start, end = todays_window()
        markets = client.betting.list_market_catalogue(
            filter=filters.market_filter(
                event_type_ids=[HORSE_RACING_EVENT_TYPE_ID],
                market_countries=config.countries,
                market_type_codes=["WIN"],
                market_start_time=filters.time_range(
                    from_=start.isoformat(), to=end.isoformat()
                ),
            ),
            market_projection=["EVENT", "MARKET_START_TIME"],
            sort="FIRST_TO_START",
            max_results=50,
        )
        print(
            "%s horse racing WIN markets left today (%s, UTC):"
            % (len(markets), ",".join(config.countries))
        )
        for market in markets:
            print(
                "  %s  %s  %s  %s"
                % (
                    market.market_start_time.strftime("%H:%M"),
                    market.market_id,
                    market.event.venue or market.event.name,
                    market.market_name,
                )
            )
    except BetfairError as e:
        print("Market request failed: %s" % e, file=sys.stderr)
        return 1
    finally:
        client.logout()

    return 0


if __name__ == "__main__":
    sys.exit(main())
