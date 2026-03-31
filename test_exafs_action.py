#!/usr/bin/env python3
"""
Testy pro exafs_action.py

Obsahuje:
  - Unit testy s mockovaným HTTP (nevyžadují běžící ExaFS)
  - Integrační test volající skutečné ExaFS API (přeskočí se bez --integration)

Spuštění unit testů:
    python3 -m pytest test_exafs_action.py -v
    python3 test_exafs_action.py          # bez pytest

Spuštění integračních testů:
    python3 test_exafs_action.py --integration --config /etc/fail2ban/exafs.cfg
"""

import argparse
import configparser
import ipaddress
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Patch cache paths BEFORE importing the module under test so the tests
# work without root permissions and don't touch /var/lib/fail2ban.
# ---------------------------------------------------------------------------
import exafs_action as sut  # noqa: E402  (imported after sys.path manipulation)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int, body: dict) -> MagicMock:
    """Create a fake requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body)
    if status_code >= 400:
        from requests.exceptions import HTTPError
        resp.raise_for_status.side_effect = HTTPError(
            f"HTTP {status_code}", response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _token_resp(token="test-jwt-token"):
    return _make_response(200, {"token": token})


def _ban_resp(rule_id=42):
    return _make_response(201, {
        "message": "RTBH Rule saved",
        "rule": {
            "id": rule_id,
            "ipv4": "1.2.3.4",
            "ipv4_mask": 32,
            "expires": "12/31/2099 23:59",
        },
    })


def _delete_resp():
    return _make_response(200, {"message": "rule deleted"})


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestParseIP(unittest.TestCase):
    def test_ipv4_address(self):
        r = sut.parse_ip("192.168.1.1")
        self.assertIsInstance(r, ipaddress.IPv4Address)

    def test_ipv4_network(self):
        r = sut.parse_ip("10.0.0.0/8")
        self.assertIsInstance(r, ipaddress.IPv4Network)

    def test_ipv6_address(self):
        r = sut.parse_ip("2001:db8::1")
        self.assertIsInstance(r, ipaddress.IPv6Address)

    def test_ipv6_network(self):
        r = sut.parse_ip("2001:db8::/32")
        self.assertIsInstance(r, ipaddress.IPv6Network)

    def test_invalid_raises_sysexit(self):
        with self.assertRaises(SystemExit):
            sut.parse_ip("not-an-ip")


class TestNetworkFields(unittest.TestCase):
    def test_ipv4_address(self):
        f = sut.network_fields(ipaddress.ip_address("1.2.3.4"))
        self.assertEqual(f, {"ipv4": "1.2.3.4", "ipv4_mask": 32})

    def test_ipv4_network(self):
        f = sut.network_fields(ipaddress.ip_network("10.0.0.0/24"))
        self.assertEqual(f, {"ipv4": "10.0.0.0", "ipv4_mask": 24})

    def test_ipv6_address(self):
        f = sut.network_fields(ipaddress.ip_address("2001:db8::1"))
        self.assertEqual(f, {"ipv6": "2001:db8::1", "ipv6_mask": 128})

    def test_ipv6_network(self):
        f = sut.network_fields(ipaddress.ip_network("2001:db8::/32"))
        self.assertEqual(f, {"ipv6": "2001:db8::", "ipv6_mask": 32})


class TestTokenCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_cache_dir = sut.CACHE_DIR
        self._orig_token_file = sut.TOKEN_CACHE_FILE
        sut.CACHE_DIR = Path(self.tmp.name)
        sut.TOKEN_CACHE_FILE = sut.CACHE_DIR / "token.json"

    def tearDown(self):
        sut.CACHE_DIR = self._orig_cache_dir
        sut.TOKEN_CACHE_FILE = self._orig_token_file
        self.tmp.cleanup()

    @patch("exafs_action.requests.request")
    def test_token_fetched_and_cached(self, mock_req):
        mock_req.return_value = _token_resp("abc123")
        token = sut.get_jwt_token("https://exafs.test", "key1")
        self.assertEqual(token, "abc123")
        # Second call should use cache — no additional HTTP request
        token2 = sut.get_jwt_token("https://exafs.test", "key1")
        self.assertEqual(token2, "abc123")
        self.assertEqual(mock_req.call_count, 1)

    @patch("exafs_action.requests.request")
    def test_expired_token_triggers_refresh(self, mock_req):
        mock_req.return_value = _token_resp("fresh-token")
        # Write a stale token
        sut.TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        sut.TOKEN_CACHE_FILE.write_text(
            json.dumps({"token": "old-token", "expires_at": time.time() - 1})
        )
        token = sut.get_jwt_token("https://exafs.test", "key1")
        self.assertEqual(token, "fresh-token")
        self.assertEqual(mock_req.call_count, 1)

    @patch("exafs_action.requests.request")
    def test_valid_cached_token_not_refreshed(self, mock_req):
        sut.TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        sut.TOKEN_CACHE_FILE.write_text(
            json.dumps({"token": "cached", "expires_at": time.time() + 9999})
        )
        token = sut.get_jwt_token("https://exafs.test", "key1")
        self.assertEqual(token, "cached")
        mock_req.assert_not_called()


class TestBan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_cache_dir = sut.CACHE_DIR
        self._orig_token_file = sut.TOKEN_CACHE_FILE
        self._orig_rules_file = sut.RULES_FILE
        sut.CACHE_DIR = Path(self.tmp.name)
        sut.TOKEN_CACHE_FILE = sut.CACHE_DIR / "token.json"
        sut.RULES_FILE = sut.CACHE_DIR / "rules.json"
        # Pre-cache a valid token so we don't need to mock /auth
        sut.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        sut.TOKEN_CACHE_FILE.write_text(
            json.dumps({"token": "valid-token", "expires_at": time.time() + 9999})
        )

    def tearDown(self):
        sut.CACHE_DIR = self._orig_cache_dir
        sut.TOKEN_CACHE_FILE = self._orig_token_file
        sut.RULES_FILE = self._orig_rules_file
        self.tmp.cleanup()

    @patch("exafs_action.requests.request")
    def test_ban_ipv4_stores_rule_id(self, mock_req):
        mock_req.return_value = _ban_resp(rule_id=99)
        sut.ban("1.2.3.4", 3600, "https://exafs.test", "key", 1)
        rules = json.loads(sut.RULES_FILE.read_text())
        self.assertEqual(rules["1.2.3.4"], 99)

    @patch("exafs_action.requests.request")
    def test_ban_ipv6_stores_rule_id(self, mock_req):
        mock_req.return_value = _ban_resp(rule_id=77)
        sut.ban("2001:db8::1", 7200, "https://exafs.test", "key", 1)
        rules = json.loads(sut.RULES_FILE.read_text())
        self.assertEqual(rules["2001:db8::1"], 77)

    @patch("exafs_action.requests.request")
    def test_ban_sends_correct_payload(self, mock_req):
        mock_req.return_value = _ban_resp()
        sut.ban("10.0.0.1", 1800, "https://exafs.test", "apikey", 3)
        _, kwargs = mock_req.call_args
        payload = kwargs.get("json") or mock_req.call_args[1].get("json")
        self.assertEqual(payload["ipv4"], "10.0.0.1")
        self.assertEqual(payload["ipv4_mask"], 32)
        self.assertEqual(payload["community"], 3)
        self.assertIn("expires", payload)

    @patch("exafs_action.requests.request")
    def test_ban_409_does_not_exit(self, mock_req):
        """Duplicate ban (409 Conflict) must not crash the script."""
        mock_req.return_value = _make_response(409, {"message": "already exists"})
        # Should not raise SystemExit
        sut.ban("1.2.3.4", 3600, "https://exafs.test", "key", 1)

    def test_ban_dry_run_does_not_call_api(self):
        """dry-run must not make any HTTP requests."""
        with patch("exafs_action.requests.request") as mock_req:
            sut.ban("1.2.3.4", 3600, "https://exafs.test", "key", 1, dry_run=True)
            mock_req.assert_not_called()


class TestUnban(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_cache_dir = sut.CACHE_DIR
        self._orig_token_file = sut.TOKEN_CACHE_FILE
        self._orig_rules_file = sut.RULES_FILE
        sut.CACHE_DIR = Path(self.tmp.name)
        sut.TOKEN_CACHE_FILE = sut.CACHE_DIR / "token.json"
        sut.RULES_FILE = sut.CACHE_DIR / "rules.json"
        sut.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        sut.TOKEN_CACHE_FILE.write_text(
            json.dumps({"token": "valid-token", "expires_at": time.time() + 9999})
        )
        # Pre-populate rules
        sut.RULES_FILE.write_text(json.dumps({"1.2.3.4": 42, "2001:db8::1": 43}))

    def tearDown(self):
        sut.CACHE_DIR = self._orig_cache_dir
        sut.TOKEN_CACHE_FILE = self._orig_token_file
        sut.RULES_FILE = self._orig_rules_file
        self.tmp.cleanup()

    @patch("exafs_action.requests.request")
    def test_unban_removes_rule_id(self, mock_req):
        mock_req.return_value = _delete_resp()
        sut.unban("1.2.3.4", "https://exafs.test", "key")
        rules = json.loads(sut.RULES_FILE.read_text())
        self.assertNotIn("1.2.3.4", rules)
        self.assertIn("2001:db8::1", rules)   # other entries untouched

    @patch("exafs_action.requests.request")
    def test_unban_calls_correct_endpoint(self, mock_req):
        mock_req.return_value = _delete_resp()
        sut.unban("1.2.3.4", "https://exafs.test", "key")
        url = mock_req.call_args[0][1]
        self.assertIn("/rules/rtbh/42", url)

    @patch("exafs_action.requests.request")
    def test_unban_404_does_not_exit(self, mock_req):
        """404 on unban (rule already expired) must not crash the script."""
        resp = MagicMock()
        resp.status_code = 404
        resp.raise_for_status.return_value = None
        mock_req.return_value = resp
        sut.unban("1.2.3.4", "https://exafs.test", "key")

    @patch("exafs_action.requests.request")
    def test_unban_unknown_ip_is_noop(self, mock_req):
        sut.unban("9.9.9.9", "https://exafs.test", "key")
        mock_req.assert_not_called()

    def test_unban_dry_run_does_not_call_api(self):
        with patch("exafs_action.requests.request") as mock_req:
            sut.unban("1.2.3.4", "https://exafs.test", "key", dry_run=True)
            mock_req.assert_not_called()


class TestWhitelist(unittest.TestCase):
    """Testy WhitelistChecker — hot-reload, CIDR matching, IPv4/IPv6."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wl_path = os.path.join(self.tmp.name, "whitelist.conf")

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, content: str):
        """Zapíše obsah do whitelist souboru."""
        with open(self.wl_path, "w") as fh:
            fh.write(content)

    # ── základní funkčnost ──────────────────────────────────────────────

    def test_whitelisted_ipv4_address(self):
        self._write("10.10.10.0/24\n")
        wl = sut.WhitelistChecker(self.wl_path)
        self.assertTrue(wl.is_whitelisted("10.10.10.1"))
        self.assertTrue(wl.is_whitelisted("10.10.10.254"))

    def test_not_whitelisted_ipv4_outside_range(self):
        self._write("10.10.10.0/24\n")
        wl = sut.WhitelistChecker(self.wl_path)
        self.assertFalse(wl.is_whitelisted("10.10.11.1"))
        self.assertFalse(wl.is_whitelisted("192.168.1.1"))

    def test_whitelisted_single_ipv4(self):
        self._write("203.0.113.42\n")
        wl = sut.WhitelistChecker(self.wl_path)
        self.assertTrue(wl.is_whitelisted("203.0.113.42"))
        self.assertFalse(wl.is_whitelisted("203.0.113.43"))

    def test_whitelisted_ipv6_network(self):
        self._write("2001:db8::/32\n")
        wl = sut.WhitelistChecker(self.wl_path)
        self.assertTrue(wl.is_whitelisted("2001:db8::1"))
        self.assertTrue(wl.is_whitelisted("2001:db8:ffff::1"))

    def test_not_whitelisted_ipv6_outside_range(self):
        self._write("2001:db8::/32\n")
        wl = sut.WhitelistChecker(self.wl_path)
        self.assertFalse(wl.is_whitelisted("2001:db9::1"))

    def test_whitelisted_single_ipv6(self):
        self._write("::1\n")
        wl = sut.WhitelistChecker(self.wl_path)
        self.assertTrue(wl.is_whitelisted("::1"))
        self.assertFalse(wl.is_whitelisted("::2"))

    def test_multiple_networks(self):
        self._write("10.10.10.0/24\n192.168.0.0/16\n2001:db8::/32\n")
        wl = sut.WhitelistChecker(self.wl_path)
        self.assertTrue(wl.is_whitelisted("10.10.10.50"))
        self.assertTrue(wl.is_whitelisted("192.168.99.1"))
        self.assertTrue(wl.is_whitelisted("2001:db8::cafe"))
        self.assertFalse(wl.is_whitelisted("8.8.8.8"))

    # ── formát souboru ──────────────────────────────────────────────────

    def test_comments_and_blank_lines_ignored(self):
        self._write("# komentář\n\n10.10.10.0/24\n# další komentář\n")
        wl = sut.WhitelistChecker(self.wl_path)
        self.assertEqual(len(wl.networks), 1)
        self.assertTrue(wl.is_whitelisted("10.10.10.1"))

    def test_invalid_entry_skipped_others_loaded(self):
        self._write("10.10.10.0/24\nnot-an-ip\n192.168.1.0/24\n")
        wl = sut.WhitelistChecker(self.wl_path)
        # Neplatný záznam přeskočen, ostatní načteny
        self.assertEqual(len(wl.networks), 2)
        self.assertTrue(wl.is_whitelisted("10.10.10.5"))
        self.assertTrue(wl.is_whitelisted("192.168.1.1"))

    # ── chybějící/nedostupný soubor ─────────────────────────────────────

    def test_missing_whitelist_file_returns_false(self):
        """Neexistující soubor → whitelist se tiše přeskočí, ban proběhne."""
        wl = sut.WhitelistChecker("/tmp/neexistuje-whitelist-exafs.conf")
        self.assertFalse(wl.is_whitelisted("10.10.10.1"))

    def test_none_whitelist_returns_false(self):
        """WhitelistChecker bez souboru → vždy False."""
        wl = sut.WhitelistChecker(None)
        self.assertFalse(wl.is_whitelisted("10.10.10.1"))

    # ── hot-reload ──────────────────────────────────────────────────────

    def test_hot_reload_adds_new_network(self):
        """Změna souboru se projeví při dalším volání is_whitelisted."""
        self._write("10.10.10.0/24\n")
        wl = sut.WhitelistChecker(self.wl_path)
        self.assertFalse(wl.is_whitelisted("192.168.1.1"))

        # Simulujeme změnu souboru — zapíšeme nový obsah s jiným mtime
        time.sleep(0.01)
        self._write("10.10.10.0/24\n192.168.1.0/24\n")
        # Vynutíme detekci změny (mtime se liší)
        wl._mtime = 0.0

        self.assertTrue(wl.is_whitelisted("192.168.1.1"))
        self.assertEqual(len(wl.networks), 2)

    def test_hot_reload_removes_network(self):
        """Odebrání sítě ze souboru se projeví při dalším volání."""
        self._write("10.10.10.0/24\n192.168.1.0/24\n")
        wl = sut.WhitelistChecker(self.wl_path)
        self.assertTrue(wl.is_whitelisted("192.168.1.1"))

        time.sleep(0.01)
        self._write("10.10.10.0/24\n")
        wl._mtime = 0.0

        self.assertFalse(wl.is_whitelisted("192.168.1.1"))
        self.assertTrue(wl.is_whitelisted("10.10.10.1"))

    # ── integrace s ban() ───────────────────────────────────────────────

    def test_ban_skipped_for_whitelisted_ip(self):
        """Whitelistovaná IP nesmí zavolat ExaFS API."""
        self._write("10.10.10.0/24\n")
        wl = sut.WhitelistChecker(self.wl_path)

        tmp = tempfile.TemporaryDirectory()
        orig_cache = sut.CACHE_DIR
        orig_token = sut.TOKEN_CACHE_FILE
        orig_rules = sut.RULES_FILE
        sut.CACHE_DIR = Path(tmp.name)
        sut.TOKEN_CACHE_FILE = sut.CACHE_DIR / "token.json"
        sut.RULES_FILE = sut.CACHE_DIR / "rules.json"

        try:
            with patch("exafs_action.requests.request") as mock_req:
                sut.ban("10.10.10.50", 3600, "https://exafs.test", "key", 1, whitelist=wl)
                mock_req.assert_not_called()
            # rules.json nesmí existovat
            self.assertFalse(sut.RULES_FILE.exists())
        finally:
            sut.CACHE_DIR = orig_cache
            sut.TOKEN_CACHE_FILE = orig_token
            sut.RULES_FILE = orig_rules
            tmp.cleanup()

    def test_ban_proceeds_for_non_whitelisted_ip(self):
        """IP mimo whitelist musí projít celým ban procesem."""
        self._write("10.10.10.0/24\n")
        wl = sut.WhitelistChecker(self.wl_path)

        tmp = tempfile.TemporaryDirectory()
        orig_cache = sut.CACHE_DIR
        orig_token = sut.TOKEN_CACHE_FILE
        orig_rules = sut.RULES_FILE
        sut.CACHE_DIR = Path(tmp.name)
        sut.TOKEN_CACHE_FILE = sut.CACHE_DIR / "token.json"
        sut.RULES_FILE = sut.CACHE_DIR / "rules.json"
        sut.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        sut.TOKEN_CACHE_FILE.write_text(
            json.dumps({"token": "valid-token", "expires_at": time.time() + 9999})
        )

        try:
            with patch("exafs_action.requests.request") as mock_req:
                mock_req.return_value = _ban_resp(rule_id=77)
                sut.ban("1.2.3.4", 3600, "https://exafs.test", "key", 1, whitelist=wl)
                mock_req.assert_called_once()
            rules = json.loads(sut.RULES_FILE.read_text())
            self.assertEqual(rules["1.2.3.4"], 77)
        finally:
            sut.CACHE_DIR = orig_cache
            sut.TOKEN_CACHE_FILE = orig_token
            sut.RULES_FILE = orig_rules
            tmp.cleanup()


class TestRetryLogic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_cache_dir = sut.CACHE_DIR
        self._orig_token_file = sut.TOKEN_CACHE_FILE
        self._orig_rules_file = sut.RULES_FILE
        sut.CACHE_DIR = Path(self.tmp.name)
        sut.TOKEN_CACHE_FILE = sut.CACHE_DIR / "token.json"
        sut.RULES_FILE = sut.CACHE_DIR / "rules.json"
        sut.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        sut.TOKEN_CACHE_FILE.write_text(
            json.dumps({"token": "valid-token", "expires_at": time.time() + 9999})
        )

    def tearDown(self):
        sut.CACHE_DIR = self._orig_cache_dir
        sut.TOKEN_CACHE_FILE = self._orig_token_file
        sut.RULES_FILE = self._orig_rules_file
        self.tmp.cleanup()

    @patch("exafs_action.time.sleep")
    @patch("exafs_action.requests.request")
    def test_retry_on_503(self, mock_req, mock_sleep):
        """Script should retry on 503 and succeed on 3rd attempt."""
        mock_req.side_effect = [
            _make_response(503, {"error": "service unavailable"}),
            _make_response(503, {"error": "service unavailable"}),
            _ban_resp(rule_id=10),
        ]
        sut.ban("1.2.3.4", 3600, "https://exafs.test", "key", 1)
        self.assertEqual(mock_req.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("exafs_action.time.sleep")
    @patch("exafs_action.requests.request")
    def test_all_retries_exhausted_raises_sysexit(self, mock_req, mock_sleep):
        """Persistent 503 after all retries must exit with error."""
        mock_req.return_value = _make_response(503, {"error": "service unavailable"})
        with self.assertRaises(SystemExit):
            sut.ban("1.2.3.4", 3600, "https://exafs.test", "key", 1)

    @patch("exafs_action.time.sleep")
    @patch("exafs_action.requests.request")
    def test_token_refresh_on_401(self, mock_req, mock_sleep):
        """401 should trigger one token refresh and retry."""
        fresh_token_resp = _token_resp("fresh-jwt")
        mock_req.side_effect = [
            _make_response(401, {"error": "Unauthorized"}),   # first attempt
            fresh_token_resp,                                  # /auth call
            _ban_resp(rule_id=55),                            # retry with new token
        ]
        sut.ban("1.2.3.4", 3600, "https://exafs.test", "key", 1)
        rules = json.loads(sut.RULES_FILE.read_text())
        self.assertEqual(rules["1.2.3.4"], 55)

    @patch("exafs_action.time.sleep")
    @patch("exafs_action.requests.request")
    def test_connection_error_retried(self, mock_req, mock_sleep):
        from requests.exceptions import ConnectionError as ReqConnError
        mock_req.side_effect = [
            ReqConnError("Connection refused"),
            ReqConnError("Connection refused"),
            _ban_resp(rule_id=20),
        ]
        sut.ban("1.2.3.4", 3600, "https://exafs.test", "key", 1)
        self.assertEqual(mock_req.call_count, 3)


# ---------------------------------------------------------------------------
# Integration tests — skipped unless --integration is passed
# ---------------------------------------------------------------------------

class TestIntegration(unittest.TestCase):
    """
    Volají skutečné ExaFS API.
    Spusťte s: python3 test_exafs_action.py --integration --config /etc/fail2ban/exafs.cfg

    POZOR: Test skutečně vytvoří a smaže RTBH pravidlo v ExaFS!
    Použijte testovací IP, která není v produkci blokována.
    """

    TEST_IPV4 = "192.0.2.1"     # TEST-NET-1 (RFC 5737) — bezpečná testovací IP
    TEST_IPV6 = "2001:db8::1"   # dokumentační prefix (RFC 3849)
    BANTIME = 120               # 2 minuty

    @classmethod
    def setUpClass(cls):
        if not getattr(cls, "_enabled", False):
            raise unittest.SkipTest("Integration tests disabled (use --integration)")
        cfg = load_config_from_file(cls._config_file)
        cls.url = cfg.get("exafs", "url").rstrip("/")
        cls.key = cfg.get("exafs", "api_key")
        cls.community = cfg.getint("exafs", "community")
        # Use a temp dir so we don't need root
        cls.tmp = tempfile.TemporaryDirectory()
        sut.CACHE_DIR = Path(cls.tmp.name)
        sut.TOKEN_CACHE_FILE = sut.CACHE_DIR / "token.json"
        sut.RULES_FILE = sut.CACHE_DIR / "rules.json"

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_01_token_fetch(self):
        token = sut.get_jwt_token(self.url, self.key)
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 10)
        print(f"\n  JWT token obtained: {token[:20]}…")

    def test_02_ban_ipv4(self):
        sut.ban(self.TEST_IPV4, self.BANTIME, self.url, self.key, self.community)
        rules = json.loads(sut.RULES_FILE.read_text())
        self.assertIn(self.TEST_IPV4, rules)
        print(f"\n  IPv4 ban OK, rule_id={rules[self.TEST_IPV4]}")

    def test_03_ban_ipv6(self):
        sut.ban(self.TEST_IPV6, self.BANTIME, self.url, self.key, self.community)
        rules = json.loads(sut.RULES_FILE.read_text())
        self.assertIn(self.TEST_IPV6, rules)
        print(f"\n  IPv6 ban OK, rule_id={rules[self.TEST_IPV6]}")

    def test_04_ban_duplicate_409(self):
        """Druhý ban stejné IP nesmí selhat."""
        sut.ban(self.TEST_IPV4, self.BANTIME, self.url, self.key, self.community)

    def test_05_unban_ipv4(self):
        sut.unban(self.TEST_IPV4, self.url, self.key)
        rules = json.loads(sut.RULES_FILE.read_text())
        self.assertNotIn(self.TEST_IPV4, rules)
        print(f"\n  IPv4 unban OK")

    def test_06_unban_ipv6(self):
        sut.unban(self.TEST_IPV6, self.url, self.key)
        rules = json.loads(sut.RULES_FILE.read_text())
        self.assertNotIn(self.TEST_IPV6, rules)
        print(f"\n  IPv6 unban OK")

    def test_07_whitelist_skips_ban(self):
        """Whitelistovaná IP nesmí být zablokována — API se nevolá."""
        wl_file = os.path.join(self.__class__.tmp.name, "wl.conf")
        with open(wl_file, "w") as fh:
            fh.write(f"{self.TEST_IPV4}\n")
        wl = sut.WhitelistChecker(wl_file)

        rules_before = json.loads(sut.RULES_FILE.read_text()) if sut.RULES_FILE.exists() else {}
        sut.ban(self.TEST_IPV4, self.BANTIME, self.url, self.key, self.community, whitelist=wl)
        rules_after = json.loads(sut.RULES_FILE.read_text()) if sut.RULES_FILE.exists() else {}

        self.assertEqual(rules_before, rules_after, "Whitelist IP nesmí vytvořit nové pravidlo")
        print(f"\n  Whitelist OK — {self.TEST_IPV4} přeskočen")


# ---------------------------------------------------------------------------
# Config loader helper (used by integration tests)
# ---------------------------------------------------------------------------

def load_config_from_file(path: str) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read(path)
    return cfg


# ---------------------------------------------------------------------------
# CLI for running tests directly (python3 test_exafs_action.py)
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run ExaFS action tests")
    parser.add_argument("--integration", action="store_true",
                        help="Enable integration tests against a real ExaFS instance")
    parser.add_argument("--config", default="/etc/fail2ban/exafs.cfg",
                        help="Config file for integration tests")
    parser.add_argument("--verbose", "-v", action="store_true")
    args, remaining = parser.parse_known_args()

    if args.integration:
        TestIntegration._enabled = True
        TestIntegration._config_file = args.config

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestParseIP))
    suite.addTests(loader.loadTestsFromTestCase(TestNetworkFields))
    suite.addTests(loader.loadTestsFromTestCase(TestTokenCache))
    suite.addTests(loader.loadTestsFromTestCase(TestBan))
    suite.addTests(loader.loadTestsFromTestCase(TestUnban))
    suite.addTests(loader.loadTestsFromTestCase(TestWhitelist))
    suite.addTests(loader.loadTestsFromTestCase(TestRetryLogic))
    if args.integration:
        suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    verbosity = 2 if args.verbose else 1
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
