# fail2ban-exafs

fail2ban action plugin that blocks IPs via [ExaFS](https://github.com/CESNET/exafs) BGP RTBH rules. Instead of local iptables blocks, it creates network-level RTBH rules through the ExaFS REST API.

## How it works

1. fail2ban detects abuse (brute force, port scan, etc.)
2. Calls `exafs_action.py ban <ip> <bantime>`
3. Script authenticates via JWT, creates an RTBH rule in ExaFS
4. IP is blocked at the BGP level across the network
5. On unban, the rule is deleted from ExaFS

Supports IPv4, IPv6, single addresses and CIDR networks.

## Requirements

- Python 3.6+
- `requests` library (`pip3 install requests`)
- fail2ban
- ExaFS instance with API access

## Installation

```bash
# Script
cp exafs_action.py /usr/local/bin/exafs_action.py
chmod +x /usr/local/bin/exafs_action.py

# fail2ban action definition
cp action.d/exafs.conf /etc/fail2ban/action.d/exafs.conf

# Configuration
cp exafs.cfg.example /etc/fail2ban/exafs.cfg
chmod 600 /etc/fail2ban/exafs.cfg
# Edit /etc/fail2ban/exafs.cfg — set url, api_key, community

# Whitelist (optional)
cp exafs-whitelist.conf /etc/fail2ban/exafs-whitelist.conf
chmod 600 /etc/fail2ban/exafs-whitelist.conf

# Man page (optional)
cp exafs_action.1 /usr/local/share/man/man1/
gzip /usr/local/share/man/man1/exafs_action.1
mandb

# Dependencies
pip3 install -r requirements.txt
```

## Configuration

### exafs.cfg

```ini
[exafs]
url            = https://exafs.example.com
api_key        = YOUR_API_KEY
community      = 1
whitelist_file = /etc/fail2ban/exafs-whitelist.conf
```

Get the API key from ExaFS: Administration > API keys.
Get the community ID from: Administration > Communities.

### fail2ban jail

Add the action to any jail in `/etc/fail2ban/jail.local`:

```ini
[sshd]
enabled = true
action  = exafs
```

### Whitelist

One CIDR entry per line in `/etc/fail2ban/exafs-whitelist.conf`. Changes are picked up automatically (hot-reload via mtime check) — no fail2ban restart needed.

```
10.10.10.0/24
192.168.1.0/24
2001:db8::/32
```

## Usage

```bash
# Ban an IP for 1 hour
exafs_action.py ban 192.168.1.1 3600

# Ban an IPv6 address for 24 hours
exafs_action.py ban 2001:db8::1 86400

# Unban
exafs_action.py unban 192.168.1.1

# List active bans (local cache)
exafs_action.py list

# Dry run — log what would happen without calling the API
exafs_action.py ban 10.0.0.1 3600 --dry-run

# Verbose logging
exafs_action.py ban 10.0.0.1 3600 --verbose

# Custom config path
exafs_action.py --config /path/to/exafs.cfg ban 10.0.0.1 3600
```

## File paths

| Path | Purpose |
|------|---------|
| `/etc/fail2ban/exafs.cfg` | Configuration (API key, URL, community) |
| `/etc/fail2ban/exafs-whitelist.conf` | IPs/networks that are never blocked |
| `/etc/fail2ban/action.d/exafs.conf` | fail2ban action plugin definition |
| `/var/lib/fail2ban/exafs/token.json` | Cached JWT token |
| `/var/lib/fail2ban/exafs/rules.json` | IP-to-rule-ID mapping |
| `/var/log/fail2ban-exafs.log` | Log file |

## Resilience

- Exponential backoff retry on network errors and 5xx/429 responses (3 attempts)
- Automatic JWT token refresh on 401
- Graceful handling of 409 (IP already blocked) and 404 (rule already expired)
- File locking on `rules.json` for concurrent access
- Logging to file, syslog, and stderr

## Tests

```bash
# Unit tests (no ExaFS needed)
python3 test_exafs_action.py -v

# Integration tests (requires running ExaFS)
python3 test_exafs_action.py --integration --config /etc/fail2ban/exafs.cfg -v
```
