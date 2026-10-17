"""
Loads Betfair credentials from environment variables, or from a
gitignored racing/.env file, and builds a betfairlightweight APIClient.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional

import betfairlightweight

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

# betfairlightweight routes its "new_zealand" locale to identitysso.betfair.com.au
# and api.betfair.com.au, which is the endpoint pair Australian accounts use too.
REGION_LOCALES = {
    "international": None,
    "au": "new_zealand",
}


class ConfigError(Exception):
    pass


@dataclass
class BetfairConfig:
    username: str
    password: str = field(repr=False)
    app_key: str = field(repr=False)
    region: str = "international"
    certs_dir: Optional[str] = None
    countries: List[str] = field(default_factory=lambda: ["GB", "IE"])

    @property
    def locale(self) -> Optional[str]:
        return REGION_LOCALES[self.region]


def load_env_file(path: str = ENV_FILE) -> None:
    """Reads KEY=VALUE lines into os.environ without overriding variables already set."""
    if not os.path.isfile(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key.strip(), value)


def load_config(env: Optional[dict] = None) -> BetfairConfig:
    if env is None:
        load_env_file()
        env = os.environ

    missing = [
        name
        for name in ("BETFAIR_USERNAME", "BETFAIR_PASSWORD", "BETFAIR_APP_KEY")
        if not env.get(name)
    ]
    if missing:
        raise ConfigError(
            "Missing %s. Set them in racing/.env (see racing/.env.example)."
            % ", ".join(missing)
        )

    region = (env.get("BETFAIR_REGION") or "international").strip().lower()
    if region not in REGION_LOCALES:
        raise ConfigError(
            "BETFAIR_REGION must be one of: %s" % ", ".join(REGION_LOCALES)
        )

    countries = [
        c.strip().upper()
        for c in (env.get("BETFAIR_COUNTRIES") or "GB,IE").split(",")
        if c.strip()
    ]

    return BetfairConfig(
        username=env["BETFAIR_USERNAME"],
        password=env["BETFAIR_PASSWORD"],
        app_key=env["BETFAIR_APP_KEY"],
        region=region,
        certs_dir=env.get("BETFAIR_CERTS_DIR") or None,
        countries=countries,
    )


def create_client(config: BetfairConfig) -> betfairlightweight.APIClient:
    return betfairlightweight.APIClient(
        config.username,
        config.password,
        app_key=config.app_key,
        certs=config.certs_dir,
        locale=config.locale,
    )


def login(client: betfairlightweight.APIClient, config: BetfairConfig) -> None:
    if config.certs_dir:
        client.login()
    else:
        client.login_interactive()
