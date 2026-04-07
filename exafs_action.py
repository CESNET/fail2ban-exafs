#!/usr/bin/env python3
"""
ExaFS fail2ban action script

Integrates fail2ban with ExaFS (https://github.com/CESNET/exafs) to block
malicious IPs via BGP RTBH (Remotely Triggered Black Hole) rules.

Usage:
    exafs_action.py ban   <ip> <bantime_seconds> [--dry-run]
    exafs_action.py unban <ip>                   [--dry-run]
    exafs_action.py list

Configuration: /etc/fail2ban/exafs.cfg
"""

import sys
import json
import os
import ipaddress
import time
import fcntl
import argparse
import logging
import logging.handlers
import configparser
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Union

try:
    import requests
    from requests.exceptions import ConnectionError, Timeout, HTTPError, RequestException
except ImportError:
    print("ERROR: 'requests' library not installed. Run: pip3 install requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_FILE  = "/etc/fail2ban/exafs.cfg"
DEFAULT_WHITELIST    = "/etc/fail2ban/exafs-whitelist.conf"
CACHE_DIR            = Path("/var/lib/fail2ban/exafs")
TOKEN_CACHE_FILE     = CACHE_DIR / "token.json"
RULES_FILE           = CACHE_DIR / "rules.json"
LOG_FILE             = "/var/log/fail2ban-exafs.log"

# JWT: ExaFS issues tokens valid for 90 min; we refresh 5 min before expiry
TOKEN_CACHE_TTL_SEC = 85 * 60
TOKEN_REFRESH_BUFFER_SEC = 300

# Retry settings for transient network/server errors
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 2   # seconds; delay = base ^ attempt  (2, 4, 8 …)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# Whitelist — adresy a sítě nikdy neblokované přes ExaFS RTBH
# ---------------------------------------------------------------------------

class WhitelistChecker:
    """
    Načte seznam IP adres/sítí ze souboru a kontroluje, zda zadaná
    adresa do whitelistu patří.  Soubor je sledován pomocí mtime —
    při změně se automaticky přenačte (hot-reload) bez restartu fail2ban.

    Formát souboru: jedna položka na řádek, notace CIDR (IPv4 i IPv6).
    Řádky začínající '#' a prázdné řádky jsou ignorovány.
    """

    def __init__(self, whitelist_file: Optional[str] = None):
        self._path: Optional[Path] = Path(whitelist_file) if whitelist_file else None
        self._networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []
        self._mtime: float = 0.0
        if self._path:
            self._load()

    # ------------------------------------------------------------------
    # Interní metody
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Načte (nebo přenačte) whitelist ze souboru, pokud se změnil."""
        if self._path is None:
            return
        try:
            mtime = self._path.stat().st_mtime
        except FileNotFoundError:
            if self._networks:
                log.warning("Whitelist soubor nenalezen: %s — whitelist vyprázdněn", self._path)
                self._networks = []
                self._mtime = 0.0
            return

        if mtime == self._mtime:
            return  # soubor se nezměnil, není třeba přenačítat

        networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []
        try:
            with self._path.open() as fh:
                for lineno, raw in enumerate(fh, start=1):
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        networks.append(ipaddress.ip_network(line, strict=False))
                    except ValueError:
                        log.warning("Whitelist řádek %d — neplatný záznam '%s', přeskočen", lineno, line)
        except OSError as exc:
            log.error("Nelze číst whitelist %s: %s", self._path, exc)
            return

        self._mtime = mtime
        self._networks = networks
        log.info("Whitelist načten: %d záznamů z %s", len(networks), self._path)

    # ------------------------------------------------------------------
    # Veřejné API
    # ------------------------------------------------------------------

    def is_whitelisted(self, ip_str: str) -> bool:
        """
        Vrátí True, pokud ip_str patří do některé sítě ve whitelistu.
        Před kontrolou provede hot-reload, pokud se soubor změnil.
        """
        self._load()
        if not self._networks:
            return False
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            log.error("Neplatná IP adresa předaná do whitelistu: %s", ip_str)
            return False
        # Normalize IPv4-mapped IPv6 (::ffff:x.x.x.x) to IPv4
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            addr = addr.ipv4_mapped
        for net in self._networks:
            if addr in net:
                log.info(
                    "IP %s je ve whitelistu (shoda s %s) — ban přeskočen", ip_str, net
                )
                return True
        return False

    @property
    def networks(self) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
        """Vrátí aktuální seznam načtených sítí (pro testy)."""
        self._load()
        return list(self._networks)


# ---------------------------------------------------------------------------
# Logging — file + syslog (so fail2ban's log aggregation picks it up)
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("exafs_action")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")

    # File handler
    try:
        fh = logging.FileHandler(LOG_FILE)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except PermissionError:
        pass  # non-root test runs won't have write access

    # Syslog handler (fail2ban reads syslog)
    try:
        sh = logging.handlers.SysLogHandler(address="/dev/log")
        sh.setFormatter(logging.Formatter("exafs_action[%(process)d]: %(levelname)s %(message)s"))
        logger.addHandler(sh)
    except (FileNotFoundError, OSError):
        pass  # /dev/log may not exist on macOS or in CI

    # Stderr — always present so errors surface when called by fail2ban
    eh = logging.StreamHandler(sys.stderr)
    eh.setFormatter(fmt)
    logger.addHandler(eh)

    return logger


log = setup_logging()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_config(config_file: str) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if not os.path.exists(config_file):
        log.error("Config file not found: %s", config_file)
        sys.exit(1)
    cfg.read(config_file)
    return cfg


def _sanitize_response_body(text: str, max_len: int = 200) -> str:
    """Sanitize response body for safe logging."""
    sanitized = re.sub(r'[^\x20-\x7E]', '?', text[:max_len])
    sanitized = re.sub(
        r'(token|key|secret|password|authorization)["\s:=]+\S+',
        r'\1=<REDACTED>', sanitized, flags=re.IGNORECASE,
    )
    return sanitized


# ---------------------------------------------------------------------------
# HTTP helper — retry with exponential backoff + 401 token refresh
# ---------------------------------------------------------------------------

def _do_request(method: str, url: str, token_getter, **kwargs) -> requests.Response:
    """
    Execute an HTTP request with:
      - Exponential backoff on connection errors and 5xx/429 responses
      - Automatic token refresh on 401 (one retry only)

    token_getter() is called to obtain a fresh JWT; pass None to skip
    auth headers (used for the /auth endpoint itself).
    """
    attempt = 0
    token_refreshed = False

    while True:
        if token_getter is not None:
            kwargs.setdefault("headers", {})
            kwargs["headers"]["x-access-token"] = token_getter()

        try:
            resp = requests.request(method, url, timeout=10, **kwargs)
        except (ConnectionError, Timeout) as exc:
            if attempt < RETRY_ATTEMPTS:
                delay = RETRY_BACKOFF_BASE ** attempt
                log.warning("Network error (%s), retrying in %ds (attempt %d/%d)…",
                            exc, delay, attempt + 1, RETRY_ATTEMPTS)
                time.sleep(delay)
                attempt += 1
                continue
            log.error("Request failed after %d attempts: %s", RETRY_ATTEMPTS, exc)
            raise

        # Token expired → refresh once and retry immediately
        if resp.status_code == 401 and not token_refreshed and token_getter is not None:
            log.info("Received 401 — clearing token cache and retrying with fresh token")
            _clear_token_cache()
            token_refreshed = True
            continue

        # Transient server-side errors → backoff and retry
        if resp.status_code in RETRYABLE_STATUS and attempt < RETRY_ATTEMPTS:
            delay = RETRY_BACKOFF_BASE ** attempt
            log.warning("HTTP %d from ExaFS, retrying in %ds (attempt %d/%d)…",
                        resp.status_code, delay, attempt + 1, RETRY_ATTEMPTS)
            time.sleep(delay)
            attempt += 1
            continue

        return resp


# ---------------------------------------------------------------------------
# JWT token management
# ---------------------------------------------------------------------------

def _clear_token_cache():
    if TOKEN_CACHE_FILE.exists():
        TOKEN_CACHE_FILE.unlink(missing_ok=True)


def get_jwt_token(exafs_url: str, api_key: str) -> str:
    """Return a valid JWT token, fetching a new one from ExaFS when necessary."""
    _ensure_cache_dir()

    if TOKEN_CACHE_FILE.exists():
        try:
            data = json.loads(TOKEN_CACHE_FILE.read_text())
            if data.get("expires_at", 0) > time.time() + TOKEN_REFRESH_BUFFER_SEC:
                return data["token"]
        except (json.JSONDecodeError, KeyError):
            pass

    log.info("Fetching new JWT token from ExaFS")
    try:
        resp = _do_request(
            "GET",
            f"{exafs_url}/api/v3/auth",
            token_getter=None,           # no auth header for this call
            headers={"x-api-key": api_key},
        )
        resp.raise_for_status()
    except RequestException as exc:
        log.error("Failed to obtain JWT token: %s", exc)
        sys.exit(1)

    try:
        token = resp.json().get("token")
    except (json.JSONDecodeError, ValueError) as exc:
        log.error("ExaFS /api/v3/auth returned non-JSON response (status %d): %s — body: %s",
                  resp.status_code, exc, _sanitize_response_body(resp.text))
        sys.exit(1)

    if not token:
        log.error("ExaFS /api/v3/auth response did not contain a token — body: %s",
                  _sanitize_response_body(resp.text))
        sys.exit(1)

    TOKEN_CACHE_FILE.write_text(
        json.dumps({"token": token, "expires_at": time.time() + TOKEN_CACHE_TTL_SEC})
    )
    TOKEN_CACHE_FILE.chmod(0o600)
    return token


# ---------------------------------------------------------------------------
# Rule ID storage
# ---------------------------------------------------------------------------

def _ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_rules() -> dict:
    _ensure_cache_dir()
    if RULES_FILE.exists():
        try:
            return json.loads(RULES_FILE.read_text())
        except json.JSONDecodeError:
            log.warning("rules.json is corrupt — starting fresh")
    return {}


def _save_rules(rules: dict):
    _ensure_cache_dir()
    tmp = RULES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(rules, indent=2))
    tmp.replace(RULES_FILE)


def _rules_lock():
    _ensure_cache_dir()
    return open(CACHE_DIR / "rules.lock", "w")


# ---------------------------------------------------------------------------
# IP helpers
# ---------------------------------------------------------------------------

def parse_ip(ip_str: str):
    """Parse ip_str as an address or network; exits on invalid input."""
    for factory in (ipaddress.ip_address, lambda s: ipaddress.ip_network(s, strict=False)):
        try:
            return factory(ip_str)
        except ValueError:
            pass
    log.error("Invalid IP address or network: %s", ip_str)
    sys.exit(1)


def network_fields(addr) -> dict:
    """Return ipv4/ipv4_mask or ipv6/ipv6_mask dict for the ExaFS payload."""
    if isinstance(addr, ipaddress.IPv4Address):
        return {"ipv4": str(addr), "ipv4_mask": 32}
    if isinstance(addr, ipaddress.IPv4Network):
        return {"ipv4": str(addr.network_address), "ipv4_mask": addr.prefixlen}
    if isinstance(addr, ipaddress.IPv6Address):
        return {"ipv6": str(addr), "ipv6_mask": 128}
    # IPv6Network
    return {"ipv6": str(addr.network_address), "ipv6_mask": addr.prefixlen}


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def ban(ip_str: str, bantime: int, exafs_url: str, api_key: str,
        community: int, dry_run: bool = False,
        whitelist: Optional[WhitelistChecker] = None):
    """Create an RTBH rule in ExaFS for the given IP."""

    # Whitelist kontrola — pokud je adresa na whitelistu, ban se přeskočí
    if whitelist and whitelist.is_whitelisted(ip_str):
        return

    addr = parse_ip(ip_str)
    expires = datetime.now() + timedelta(seconds=bantime)
    expires_str = expires.strftime("%m/%d/%Y %H:%M")

    payload = {
        "community": community,
        "expires": expires_str,
        "comment": "fail2ban auto-block",
        **network_fields(addr),
    }

    if dry_run:
        log.info("[DRY-RUN] Would POST /rules/rtbh: %s", json.dumps(payload))
        return

    def token_getter():
        return get_jwt_token(exafs_url, api_key)

    try:
        resp = _do_request(
            "POST",
            f"{exafs_url}/api/v3/rules/rtbh",
            token_getter=token_getter,
            headers={"Content-Type": "application/json"},
            json=payload,
        )
    except RequestException as exc:
        log.error("Failed to ban %s: %s", ip_str, exc)
        sys.exit(1)

    # 409 Conflict — IP is already blocked in ExaFS; not a fatal error
    if resp.status_code == 409:
        log.warning("ExaFS reports %s is already blocked (409 Conflict) — skipping", ip_str)
        return

    try:
        resp.raise_for_status()
    except HTTPError as exc:
        log.error("ExaFS error banning %s: %s — %s", ip_str, exc, _sanitize_response_body(resp.text))
        sys.exit(1)

    try:
        rule_id = resp.json().get("rule", {}).get("id")
    except (json.JSONDecodeError, ValueError) as exc:
        log.error("ExaFS /api/v3/rules/rtbh returned non-JSON response (status %d): %s — body: %s",
                  resp.status_code, exc, _sanitize_response_body(resp.text))
        sys.exit(1)

    if rule_id is None:
        log.error("ExaFS did not return a rule id for %s — body: %s",
                  ip_str, _sanitize_response_body(resp.text))
        sys.exit(1)

    with _rules_lock() as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            rules = _load_rules()
            rules[ip_str] = rule_id
            _save_rules(rules)
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

    log.info("Banned %s → ExaFS rule_id=%s, expires=%s", ip_str, rule_id, expires_str)


def unban(ip_str: str, exafs_url: str, api_key: str, dry_run: bool = False):
    """Delete the RTBH rule in ExaFS for the given IP."""
    with _rules_lock() as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            rules = _load_rules()
            rule_id = rules.get(ip_str)
            if rule_id is None:
                log.warning("No stored rule_id for %s — nothing to unban", ip_str)
                return
            if not dry_run:
                rules.pop(ip_str)
                _save_rules(rules)
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

    if dry_run:
        log.info("[DRY-RUN] Would DELETE /rules/rtbh/%s (ip=%s)", rule_id, ip_str)
        return

    def token_getter():
        return get_jwt_token(exafs_url, api_key)

    try:
        resp = _do_request(
            "DELETE",
            f"{exafs_url}/api/v3/rules/rtbh/{rule_id}",
            token_getter=token_getter,
        )
    except RequestException as exc:
        log.error("Failed to unban %s (rule_id=%s): %s", ip_str, rule_id, exc)
        sys.exit(1)

    if resp.status_code == 404:
        log.warning("Rule %s for %s not found in ExaFS (already expired?)", rule_id, ip_str)
    else:
        try:
            resp.raise_for_status()
        except HTTPError as exc:
            log.error("ExaFS error unbanning %s: %s — %s", ip_str, exc, _sanitize_response_body(resp.text))
            sys.exit(1)

    log.info("Unbanned %s ← deleted ExaFS rule_id=%s", ip_str, rule_id)


def list_banned():
    """Print currently tracked ban entries from local rules.json."""
    rules = _load_rules()
    if not rules:
        print("No active bans tracked locally.")
        return
    print(f"{'IP address':<45} {'ExaFS rule_id'}")
    print("-" * 60)
    for ip, rule_id in sorted(rules.items()):
        print(f"{ip:<45} {rule_id}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ExaFS fail2ban action script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ban   192.168.1.1 3600
  %(prog)s ban   2001:db8::1 86400
  %(prog)s unban 192.168.1.1
  %(prog)s list
  %(prog)s ban   10.0.0.1 3600 --dry-run
""",
    )
    parser.add_argument("action", choices=["ban", "unban", "list"], help="Action to perform")
    parser.add_argument("ip", nargs="?", help="IP address or CIDR (required for ban/unban)")
    parser.add_argument(
        "bantime", type=int, nargs="?", default=3600,
        help="Ban duration in seconds (ban only, default: 3600)",
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE,
                        help=f"Config file path (default: {DEFAULT_CONFIG_FILE})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Log what would happen without calling ExaFS API")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger("exafs_action").setLevel(logging.DEBUG)

    if args.action == "list":
        list_banned()
        return

    if not args.ip:
        parser.error(f"'ip' argument is required for action '{args.action}'")

    cfg = load_config(args.config)
    try:
        exafs_url = cfg.get("exafs", "url").rstrip("/")
        api_key = cfg.get("exafs", "api_key")
        community = cfg.getint("exafs", "community")
    except (configparser.NoSectionError, configparser.NoOptionError) as exc:
        log.error("Missing configuration: %s", exc)
        sys.exit(1)

    # Volitelný whitelist — pokud klíč chybí, použije se výchozí cesta
    whitelist_file = cfg.get("exafs", "whitelist_file", fallback=DEFAULT_WHITELIST)
    whitelist = WhitelistChecker(whitelist_file)

    if args.action == "ban":
        ban(args.ip, args.bantime, exafs_url, api_key, community,
            dry_run=args.dry_run, whitelist=whitelist)
    elif args.action == "unban":
        unban(args.ip, exafs_url, api_key, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
