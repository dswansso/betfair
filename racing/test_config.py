import os
import tempfile
import unittest
from unittest import mock

from racing import config

BASE_ENV = {
    "BETFAIR_USERNAME": "user",
    "BETFAIR_PASSWORD": "pass",
    "BETFAIR_APP_KEY": "key",
}


class LoadConfigTest(unittest.TestCase):
    def test_defaults(self):
        cfg = config.load_config(BASE_ENV)
        self.assertEqual(cfg.region, "international")
        self.assertIsNone(cfg.locale)
        self.assertIsNone(cfg.certs_dir)
        self.assertEqual(cfg.countries, ["GB", "IE"])

    def test_au_region_uses_com_au_endpoints(self):
        cfg = config.load_config(dict(BASE_ENV, BETFAIR_REGION="AU"))
        client = config.create_client(cfg)
        self.assertIn("betfair.com.au", client.identity_uri)
        self.assertIn("betfair.com.au", client.api_uri)

    def test_missing_credentials(self):
        with self.assertRaises(config.ConfigError) as ctx:
            config.load_config({"BETFAIR_USERNAME": "user"})
        self.assertIn("BETFAIR_APP_KEY", str(ctx.exception))

    def test_bad_region(self):
        with self.assertRaises(config.ConfigError):
            config.load_config(dict(BASE_ENV, BETFAIR_REGION="mars"))

    def test_secrets_not_in_repr(self):
        cfg = config.load_config(BASE_ENV)
        self.assertNotIn("pass", repr(cfg))
        self.assertNotIn("key", repr(cfg))

    def test_login_mode(self):
        client = mock.Mock()
        config.login(client, config.load_config(BASE_ENV))
        client.login_interactive.assert_called_once()
        client.login.assert_not_called()

        client = mock.Mock()
        config.login(client, config.load_config(dict(BASE_ENV, BETFAIR_CERTS_DIR="/c")))
        client.login.assert_called_once()


class LoadEnvFileTest(unittest.TestCase):
    def test_reads_file_without_overriding(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
            f.write('# comment\nRACING_TEST_A="quoted"\nRACING_TEST_B=file\n')
        try:
            with mock.patch.dict(os.environ, {"RACING_TEST_B": "shell"}):
                config.load_env_file(f.name)
                self.assertEqual(os.environ["RACING_TEST_A"], "quoted")
                self.assertEqual(os.environ["RACING_TEST_B"], "shell")
        finally:
            os.unlink(f.name)
