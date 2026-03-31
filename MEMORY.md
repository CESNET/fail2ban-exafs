# MEMORY — fail2ban + ExaFS Integration Project

## Datum poslední aktualizace
2026-03-23

## Pracovní adresář
`/Users/adamec/Moje/claude/fail2ban/`

---

## Co je projekt

Integrace **fail2ban** s **ExaFS** (CESNET, https://github.com/CESNET/exafs).
fail2ban detekuje škodlivý provoz a volá `exafs_action.py`, který přes REST API
vytvoří/smaže RTBH (Remotely Triggered Black Hole) pravidlo v ExaFS.
ExaFS pak blokuje IP na úrovni BGP sítě — ne jen lokálně na hostiteli.

**Klíčová omezení zadání:**
- Používá se **pouze RTBH** (ne FlowSpec)
- Podporovány jsou IPv4 i IPv6
- API klíč se vloží ručně do konfiguračního souboru
- JWT token má životnost **max 90 minut**, expirace spravuje fail2ban
- fail2ban běží na **jiném stroji** než ExaFS

---

## ExaFS REST API (zjištěno z GitHub repo)

| Akce | Metoda | Endpoint |
|------|--------|----------|
| Získat JWT token | GET | `/api/v3/auth` |
| Vytvořit RTBH pravidlo | POST | `/api/v3/rules/rtbh` |
| Smazat RTBH pravidlo | DELETE | `/api/v3/rules/rtbh/{rule_id}` |

**Autentizace:**
- Header pro token: `x-api-key: {api_key}`
- Header pro API volání: `x-access-token: {jwt_token}`
- JWT algoritmus: HS256, výchozí platnost ~30 min (nastavitelné)

**Payload pro vytvoření RTBH pravidla:**
```json
{
  "community": 1,
  "expires": "10/25/2050 14:46",
  "ipv4": "1.2.3.4",
  "ipv4_mask": 32,
  "comment": "fail2ban auto-block"
}
```
Nebo pro IPv6: pole `ipv6` + `ipv6_mask` (0–128).

**Response (HTTP 201):**
```json
{ "rule": { "id": 42, "ipv4": "1.2.3.4", ... } }
```
Rule ID je `response.json()["rule"]["id"]`.

---

## Soubory projektu

| Soubor | Popis |
|--------|-------|
| `exafs_action.py` | Hlavní skript — akce ban/unban/list + WhitelistChecker |
| `action.d/exafs.conf` | fail2ban action plugin |
| `exafs.cfg.example` | Šablona konfiguračního souboru |
| `exafs-whitelist.conf` | Příklad whitelistu (obsahuje 10.10.10.0/24) |
| `test_exafs_action.py` | Unit testy (41 passed) + integrační testy (opt-in) |
| `requirements.txt` | Python závislosti (`requests`) |
| `exafs_action.1` | Man page (groff formát) |
| `exafs_action_documentation.pdf` | PDF dokumentace (EN) |
| `generate_docs.py` | Generátor PDF dokumentace (reportlab) |
| `MEMORY.md` | Tento soubor |

---

## Architektura exafs_action.py

### Klíčové konstanty
```python
DEFAULT_CONFIG_FILE  = "/etc/fail2ban/exafs.cfg"
DEFAULT_WHITELIST    = "/etc/fail2ban/exafs-whitelist.conf"
CACHE_DIR            = Path("/var/lib/fail2ban/exafs")
TOKEN_CACHE_FILE     = CACHE_DIR / "token.json"
RULES_FILE           = CACHE_DIR / "rules.json"
TOKEN_CACHE_TTL_SEC  = 85 * 60   # 85 minut
RETRY_ATTEMPTS       = 3
RETRY_BACKOFF_BASE   = 2         # delay = base^attempt (2, 4, 8 s)
RETRYABLE_STATUS     = {429, 500, 502, 503, 504}
```

### Třídy a funkce
- `WhitelistChecker` — načítá CIDR záznamy, hot-reload přes mtime, IPv4+IPv6
- `setup_logging()` — file + syslog (/dev/log) + stderr
- `load_config()` — INI soubor přes configparser
- `_do_request()` — HTTP s retry (exponential backoff) + auto token refresh při 401
- `get_jwt_token()` — cache v token.json (chmod 600), refresh před expirací
- `ban()` — POST /rules/rtbh, uloží rule_id do rules.json, flock pro souběžnost
- `unban()` — DELETE /rules/rtbh/{id}, odstraní z rules.json
- `list_banned()` — výpis rules.json

### Parametry ban()
```python
def ban(ip_str, bantime, exafs_url, api_key, community,
        dry_run=False, whitelist=None)
```

---

## Konfigurační soubor /etc/fail2ban/exafs.cfg

```ini
[exafs]
url            = https://exafs.example.com
api_key        = VASE_API_KEY_ZDE
community      = 1
whitelist_file = /etc/fail2ban/exafs-whitelist.conf
```
Oprávnění: `chmod 600`

---

## Whitelist

- Soubor: `/etc/fail2ban/exafs-whitelist.conf`
- Formát: jedna položka na řádek, CIDR notace, komentáře přes `#`
- **Hot-reload** — přenačte se automaticky při změně mtime (bez restartu)
- Příklad: `10.10.10.0/24` (management síť)
- Chybějící soubor → jen warning, ban proběhne normálně
- Neplatný záznam → warning, ostatní záznamy zůstanou

---

## Testy

```bash
# Unit testy (bez ExaFS)
python3 -m pytest test_exafs_action.py -v
# nebo
python3 test_exafs_action.py --verbose

# Integrační testy (vyžadují běžící ExaFS)
python3 test_exafs_action.py --integration --config /etc/fail2ban/exafs.cfg --verbose
```

### Test třídy
| Třída | Počet testů | Co testuje |
|-------|------------|------------|
| TestParseIP | 5 | Parsování IPv4/IPv6 adres a sítí |
| TestNetworkFields | 4 | Generování ExaFS payload polí |
| TestTokenCache | 3 | JWT cache, expiry, refresh |
| TestBan | 5 | ban akce, payload, 409, dry-run |
| TestUnban | 5 | unban, 404, neznámá IP, dry-run |
| TestWhitelist | 14 | CIDR matching, hot-reload, integrace s ban() |
| TestRetryLogic | 4 | retry 5xx, conn error, 401 token refresh |
| TestIntegration | 7 | Live ExaFS (opt-in, přeskočeny bez --integration) |

**Celkem: 41 passed, 7 skipped (integrační)**

---

## Zpracované funkcionality (hotovo)

- [x] Základní ban/unban přes ExaFS RTBH API
- [x] Podpora IPv4 i IPv6 (adresy i CIDR sítě)
- [x] JWT token cache + auto-refresh
- [x] Retry s exponential backoff (síťové chyby, 5xx, 429)
- [x] Auto token refresh při 401
- [x] Graceful handling 409 (IP již blokována)
- [x] Graceful handling 404 (pravidlo již smazáno)
- [x] `--dry-run` režim
- [x] `list` akce
- [x] Syslog podpora
- [x] fail2ban action plugin (`action.d/exafs.conf`)
- [x] Unit testy (mock HTTP)
- [x] Integrační testy (live ExaFS)
- [x] Man page (EN)
- [x] PDF dokumentace (EN)
- [x] **Whitelist** — adresy nikdy neblokované, hot-reload, IPv4+IPv6 CIDR

---

## Možná budoucí rozšíření (neimplementováno)

- [ ] Podpora více ExaFS instancí / profilů v jednom cfg
- [ ] Webhook notifikace při banu
- [ ] Prometheus metrics endpoint
- [ ] Automatické čištění expirovaných záznamů z rules.json
- [ ] Podpora FlowSpec pravidel (zatím jen RTBH)

---

## Instalace na cílovém systému

```bash
cp exafs_action.py /usr/local/bin/exafs_action.py
chmod +x /usr/local/bin/exafs_action.py
cp action.d/exafs.conf /etc/fail2ban/action.d/exafs.conf
cp exafs.cfg.example /etc/fail2ban/exafs.cfg
chmod 600 /etc/fail2ban/exafs.cfg
cp exafs-whitelist.conf /etc/fail2ban/exafs-whitelist.conf
chmod 600 /etc/fail2ban/exafs-whitelist.conf
# Man page
cp exafs_action.1 /usr/local/share/man/man1/
gzip /usr/local/share/man/man1/exafs_action.1
mandb
```
