#!/usr/bin/env python3
"""
PDF documentation generator for exafs_action (fail2ban + ExaFS integration).
Usage:  python3 generate_docs.py
Output: exafs_action_documentation.pdf
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Preformatted,
    Table, TableStyle, PageBreak, HRFlowable, KeepTogether,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

PAGE_W, PAGE_H = A4
MARGIN = 2.5 * cm

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
C_BLUE   = colors.HexColor("#1a5276")
C_LBLUE  = colors.HexColor("#2e86c1")
C_GRAY   = colors.HexColor("#555555")
C_LGRAY  = colors.HexColor("#f2f3f4")
C_DGRAY  = colors.HexColor("#cccccc")
C_GREEN  = colors.HexColor("#1e8449")
C_RED    = colors.HexColor("#c0392b")
C_CODE   = colors.HexColor("#2c3e50")
C_CODEBG = colors.HexColor("#f8f9fa")

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
base_styles = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, **kw)

styles = {
    "title": S("DocTitle",
        fontSize=26, leading=32, textColor=C_BLUE,
        alignment=TA_CENTER, fontName="Helvetica-Bold", spaceAfter=6),
    "subtitle": S("DocSubtitle",
        fontSize=13, leading=18, textColor=C_GRAY,
        alignment=TA_CENTER, fontName="Helvetica", spaceAfter=4),
    "version": S("DocVersion",
        fontSize=10, leading=14, textColor=C_GRAY,
        alignment=TA_CENTER, fontName="Helvetica"),
    "h1": S("H1",
        fontSize=16, leading=20, textColor=C_BLUE,
        fontName="Helvetica-Bold", spaceBefore=18, spaceAfter=8,
        borderPad=4),
    "h2": S("H2",
        fontSize=13, leading=17, textColor=C_LBLUE,
        fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6),
    "h3": S("H3",
        fontSize=11, leading=15, textColor=C_CODE,
        fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4),
    "body": S("Body",
        fontSize=10, leading=15, textColor=C_CODE,
        fontName="Helvetica", spaceAfter=6, alignment=TA_JUSTIFY),
    "body_left": S("BodyLeft",
        fontSize=10, leading=15, textColor=C_CODE,
        fontName="Helvetica", spaceAfter=6),
    "bullet": S("Bullet",
        fontSize=10, leading=15, textColor=C_CODE,
        fontName="Helvetica", spaceAfter=3,
        leftIndent=16, bulletIndent=4, bulletFontName="Helvetica"),
    "code": S("Code",
        fontSize=8.5, leading=13, textColor=C_CODE,
        fontName="Courier", backColor=C_CODEBG,
        borderColor=C_DGRAY, borderWidth=0.5, borderPad=6,
        spaceAfter=8, leftIndent=0),
    "note": S("Note",
        fontSize=9.5, leading=14, textColor=colors.HexColor("#7d6608"),
        fontName="Helvetica", backColor=colors.HexColor("#fef9e7"),
        borderColor=colors.HexColor("#f0c040"), borderWidth=1,
        borderPad=8, spaceAfter=8),
    "warn": S("Warn",
        fontSize=9.5, leading=14, textColor=colors.HexColor("#6e2222"),
        fontName="Helvetica", backColor=colors.HexColor("#fdedec"),
        borderColor=C_RED, borderWidth=1,
        borderPad=8, spaceAfter=8),
    "toc_h1": S("TOC1",
        fontSize=11, leading=16, fontName="Helvetica-Bold", textColor=C_BLUE,
        leftIndent=0, spaceAfter=2),
    "toc_h2": S("TOC2",
        fontSize=10, leading=14, fontName="Helvetica", textColor=C_GRAY,
        leftIndent=16, spaceAfter=1),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def h1(text):    return Paragraph(text, styles["h1"])
def h2(text):    return Paragraph(text, styles["h2"])
def h3(text):    return Paragraph(text, styles["h3"])
def p(text):     return Paragraph(text, styles["body"])
def pl(text):    return Paragraph(text, styles["body_left"])
def note(text):  return Paragraph(f"<b>Note:</b> {text}", styles["note"])
def warn(text):  return Paragraph(f"<b>Warning:</b> {text}", styles["warn"])
def sp(n=6):     return Spacer(1, n)
def hr():        return HRFlowable(width="100%", thickness=0.5, color=C_DGRAY, spaceAfter=4)

def code(text):
    return Preformatted(text, styles["code"])

def bullet(items):
    return [Paragraph(f"&bull;&nbsp;&nbsp;{item}", styles["bullet"]) for item in items]

def table(data, col_widths=None, header=True):
    t = Table(data, colWidths=col_widths)
    ts = [
        ("BACKGROUND", (0,0), (-1, 0 if header else -1), C_BLUE if header else C_LGRAY),
        ("TEXTCOLOR",  (0,0), (-1, 0), colors.white if header else C_CODE),
        ("FONTNAME",   (0,0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("LEADING",    (0,0), (-1,-1), 13),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, C_LGRAY]),
        ("GRID",       (0,0), (-1,-1), 0.4, C_DGRAY),
        ("VALIGN",     (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING",(0,0), (-1,-1), 6),
        ("TOPPADDING",  (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
    ]
    t.setStyle(TableStyle(ts))
    return t

# ---------------------------------------------------------------------------
# Page decorators
# ---------------------------------------------------------------------------

def cover_page(canvas, doc):
    canvas.saveState()
    # Header bar
    canvas.setFillColor(C_BLUE)
    canvas.rect(0, PAGE_H - 3.5*cm, PAGE_W, 3.5*cm, fill=1, stroke=0)
    # Footer bar
    canvas.setFillColor(C_LBLUE)
    canvas.rect(0, 0, PAGE_W, 1.5*cm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 9)
    canvas.drawCentredString(PAGE_W/2, 0.55*cm, "fail2ban + ExaFS Integration  |  CESNET")

    canvas.restoreState()

def normal_page(canvas, doc):
    canvas.saveState()
    # Top line
    canvas.setStrokeColor(C_LBLUE)
    canvas.setLineWidth(1.5)
    canvas.line(MARGIN, PAGE_H - MARGIN + 4, PAGE_W - MARGIN, PAGE_H - MARGIN + 4)
    # Footer
    canvas.setFillColor(C_GRAY)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(MARGIN, 1.2*cm, "exafs_action -- fail2ban + ExaFS Integration")
    canvas.drawRightString(PAGE_W - MARGIN, 1.2*cm, f"Page {doc.page}")
    canvas.setStrokeColor(C_DGRAY)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 1.5*cm, PAGE_W - MARGIN, 1.5*cm)
    canvas.restoreState()

# ---------------------------------------------------------------------------
# Document builder
# ---------------------------------------------------------------------------

class TocDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, **kw)
        self.addPageTemplates([
            PageTemplate("cover",  frames=[Frame(MARGIN, MARGIN, PAGE_W-2*MARGIN, PAGE_H-2*MARGIN, id="cover")],  onPage=cover_page),
            PageTemplate("normal", frames=[Frame(MARGIN, 1.8*cm, PAGE_W-2*MARGIN, PAGE_H-MARGIN-1.8*cm, id="normal")], onPage=normal_page),
        ])

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            style = flowable.style.name
            text  = flowable.getPlainText()
            if style == "H1":
                self.notify("TOCEntry", (0, text, self.page, None))
            elif style == "H2":
                self.notify("TOCEntry", (1, text, self.page, None))


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

def build():
    OUTPUT = "exafs_action_documentation.pdf"
    doc = TocDoc(
        OUTPUT,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
        title="exafs_action -- Documentation",
        author="CESNET / fail2ban ExaFS Integration",
    )

    story = []

    # ------------------------------------------------------------------
    # COVER
    # ------------------------------------------------------------------
    story.append(Spacer(1, 3.5*cm))
    story.append(Paragraph("exafs_action", styles["title"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("fail2ban Integration with ExaFS", styles["subtitle"]))
    story.append(Paragraph("Blocking Malicious Traffic via BGP RTBH", styles["subtitle"]))
    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width="60%", thickness=1.5, color=C_LBLUE, hAlign="CENTER"))
    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph("Version 1.0  |  2025", styles["version"]))
    story.append(Paragraph("License: MIT", styles["version"]))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        'ExaFS: <a href="https://github.com/CESNET/exafs" color="#2e86c1">github.com/CESNET/exafs</a>',
        styles["version"]))

    story.append(PageBreak())

    # ------------------------------------------------------------------
    # OBSAH
    # ------------------------------------------------------------------
    from reportlab.platypus.doctemplate import NextPageTemplate
    story.append(NextPageTemplate("normal"))

    story.append(h1("Table of Contents"))
    toc = TableOfContents()
    toc.levelStyles = [styles["toc_h1"], styles["toc_h2"]]
    toc.dotsMinLevel = 0
    story.append(toc)
    story.append(PageBreak())

    # ------------------------------------------------------------------
    # 1. ÚVOD
    # ------------------------------------------------------------------
    story.append(h1("1. Introduction"))
    story.append(p(
        "This document describes the installation, configuration and usage of "
        "<b>exafs_action</b> — an integration between <b>fail2ban</b> and the "
        "<b>ExaFS</b> web application (CESNET). The goal is to automatically block "
        "IP addresses detected by fail2ban using BGP RTBH rules managed via ExaFS."
    ))

    story.append(h2("1.1 What is ExaFS"))
    story.append(p(
        "ExaFS is a Python/Flask web application for managing BGP (Border Gateway Protocol) "
        "rules to protect networks against DDoS attacks and other malicious traffic. "
        "It acts as a control layer for ExaBGP, allowing administrators to create and remove "
        "FlowSpec (IPv4/IPv6) and RTBH rules without direct access to network equipment."
    ))

    story.append(h2("1.2 How the Integration Works"))
    story.append(p(
        "fail2ban monitors system logs, detects repeated failed login attempts or other "
        "suspicious activity, and calls a configured action when a threshold is exceeded. "
        "Instead of a standard <i>iptables/nftables</i> block, <b>exafs_action.py</b> is "
        "called, which creates an RTBH rule via the ExaFS REST API. The BGP network node "
        "then blocks traffic from that IP address at the network level, not just on the host."
    ))

    flow_data = [
        ["Component", "Location", "Role"],
        ["fail2ban", "Monitored host", "Detects malicious traffic"],
        ["exafs_action.py", "Monitored host", "Calls ExaFS API (ban/unban)"],
        ["ExaFS", "Separate server", "Manages BGP RTBH rules"],
        ["ExaBGP", "Network device", "Propagates BGP messages into the network"],
    ]
    story.append(table(flow_data, col_widths=[4*cm, 5*cm, 7.5*cm]))
    story.append(sp(10))

    story.append(note(
        "exafs_action.py and fail2ban run on a <b>different host</b> than ExaFS. "
        "Communication is via HTTPS REST API."
    ))
    story.append(PageBreak())

    # ------------------------------------------------------------------
    # 2. POŽADAVKY
    # ------------------------------------------------------------------
    story.append(h1("2. Requirements"))

    story.append(h2("2.1 Operating System"))
    story.extend(bullet([
        "Linux (RHEL/CentOS 8+, Debian 11+, Ubuntu 20.04+)",
        "Python 3.8 or later",
        "fail2ban 0.11 or later",
    ]))

    story.append(h2("2.2 Python Dependencies"))
    story.append(code("pip3 install requests>=2.28.0"))

    story.append(h2("2.3 ExaFS"))
    story.extend(bullet([
        "Running ExaFS instance accessible via HTTPS",
        "Generated API key (Administration -> API keys)",
        "RTBH community ID configured in ExaFS",
        "Network reachability: monitored host -> ExaFS (TCP 443)",
    ]))
    story.append(PageBreak())

    # ------------------------------------------------------------------
    # 3. INSTALACE
    # ------------------------------------------------------------------
    story.append(h1("3. Installation"))

    story.append(h2("3.1 Download Files"))
    story.append(p("Clone or copy the project files to the target host:"))
    story.append(code(
        "git clone https://github.com/vasorg/fail2ban-exafs.git\n"
        "cd fail2ban-exafs"
    ))

    story.append(h2("3.2 Install Python Dependencies"))
    story.append(code("pip3 install -r requirements.txt"))

    story.append(h2("3.3 Install the Main Script"))
    story.append(code(
        "cp exafs_action.py /usr/local/bin/exafs_action.py\n"
        "chmod +x /usr/local/bin/exafs_action.py"
    ))

    story.append(h2("3.4 Install the fail2ban Action Plugin"))
    story.append(code("cp action.d/exafs.conf /etc/fail2ban/action.d/exafs.conf"))

    story.append(h2("3.5 Create the Configuration File"))
    story.append(code(
        "cp exafs.cfg.example /etc/fail2ban/exafs.cfg\n"
        "chmod 600 /etc/fail2ban/exafs.cfg    # readable by root only\n"
        "nano /etc/fail2ban/exafs.cfg          # fill in url, api_key, community"
    ))

    story.append(h2("3.6 Install the Man Page"))
    story.append(code(
        "cp exafs_action.1 /usr/local/share/man/man1/\n"
        "gzip /usr/local/share/man/man1/exafs_action.1\n"
        "mandb"
    ))

    story.append(h2("3.7 Create the Runtime Data Directory"))
    story.append(p(
        "The script creates this directory automatically on first run. "
        "To create it manually:"
    ))
    story.append(code(
        "mkdir -p /var/lib/fail2ban/exafs\n"
        "chmod 700 /var/lib/fail2ban/exafs"
    ))
    story.append(PageBreak())

    # ------------------------------------------------------------------
    # 4. KONFIGURACE
    # ------------------------------------------------------------------
    story.append(h1("4. Configuration"))

    story.append(h2("4.1 /etc/fail2ban/exafs.cfg"))
    story.append(p(
        "The main configuration file contains access credentials for ExaFS. "
        "The file must be protected from reading by other users (chmod 600)."
    ))
    story.append(code(
        "[exafs]\n\n"
        "# ExaFS server URL (no trailing slash)\n"
        "url = https://exafs.example.com\n\n"
        "# API key generated in ExaFS (Administration -> API keys)\n"
        "api_key = YOUR_API_KEY_HERE\n\n"
        "# RTBH community ID configured in ExaFS\n"
        "# Find it in ExaFS: Administration -> Communities\n"
        "community = 1"
    ))

    story.append(h2("4.2 Obtaining an API Key in ExaFS"))
    story.extend(bullet([
        "Log in to the ExaFS web interface",
        "Go to <b>Administration -> API keys</b>",
        "Click <b>Generate new key</b>",
        "Copy the generated key into the configuration file",
    ]))
    story.append(note(
        "The JWT token derived from the API key is valid for 90 minutes. "
        "The script automatically renews it 5 minutes before expiry -- "
        "no manual management is required."
    ))

    story.append(h2("4.3 Enabling in fail2ban (jail.local)"))
    story.append(p(
        "Add or edit the relevant jail section in "
        "<b>/etc/fail2ban/jail.local</b>:"
    ))
    story.append(code(
        "[sshd]\n"
        "enabled  = true\n"
        "action   = exafs\n"
        "bantime  = 3600    ; seconds (1 hour)\n"
        "findtime = 600\n"
        "maxretry = 5"
    ))

    story.append(h2("4.4 Combining with Other Actions"))
    story.append(p(
        "exafs can be combined with other actions, for example to apply "
        "both a local iptables block and a network-level block via ExaFS:"
    ))
    story.append(code(
        "[sshd]\n"
        "action = %(action_mwl)s\n"
        "         exafs"
    ))

    story.append(h2("4.5 Overriding the Configuration File Path"))
    story.append(p(
        "To use a different configuration file (e.g. for multiple jails "
        "with different ExaFS instances), set in <b>jail.local</b>:"
    ))
    story.append(code(
        "[sshd]\n"
        "action = exafs[config=/etc/fail2ban/exafs-prod.cfg]"
    ))

    story.append(h2("4.6 Whitelist Configuration"))
    story.append(p(
        "The whitelist prevents certain IP addresses and networks from ever being "
        "blocked via ExaFS RTBH — regardless of fail2ban decisions. "
        "This is essential for protecting management networks, monitoring servers, "
        "trusted partners, and any address that must remain reachable at all times."
    ))
    story.append(p(
        "The whitelist file path is set in <b>exafs.cfg</b> with the "
        "<b>whitelist_file</b> option (default: "
        "<i>/etc/fail2ban/exafs-whitelist.conf</i>). "
        "If the file does not exist, the whitelist is simply skipped."
    ))
    story.append(code(
        "[exafs]\n"
        "url            = https://exafs.example.com\n"
        "api_key        = YOUR_API_KEY_HERE\n"
        "community      = 1\n"
        "whitelist_file = /etc/fail2ban/exafs-whitelist.conf"
    ))

    story.append(h3("Whitelist File Format"))
    story.append(p(
        "One entry per line. CIDR notation is supported for both IPv4 and IPv6. "
        "Lines beginning with <b>#</b> and blank lines are ignored."
    ))
    story.append(code(
        "# /etc/fail2ban/exafs-whitelist.conf\n"
        "\n"
        "# Internal management network\n"
        "10.10.10.0/24\n"
        "\n"
        "# Trusted monitoring server\n"
        "203.0.113.10\n"
        "\n"
        "# IPv6 management prefix\n"
        "2001:db8::/32\n"
        "\n"
        "# RFC 1918 private ranges (uncomment as needed)\n"
        "# 10.0.0.0/8\n"
        "# 172.16.0.0/12\n"
        "# 192.168.0.0/16"
    ))
    story.append(code(
        "chmod 600 /etc/fail2ban/exafs-whitelist.conf    # readable by root only"
    ))

    story.append(h3("Hot-Reload"))
    story.append(p(
        "The whitelist file is automatically reloaded on every ban action "
        "when its modification time (mtime) changes. "
        "Changes take effect <b>immediately</b> without restarting fail2ban or the script."
    ))

    wl_data = [
        ["Feature", "Detail"],
        ["File format", "Plain text, one entry per line, CIDR notation"],
        ["IPv4 support", "Addresses and networks (e.g. 10.10.10.0/24, 192.0.2.1)"],
        ["IPv6 support", "Addresses and networks (e.g. 2001:db8::/32, ::1)"],
        ["Comments", "Lines starting with # are ignored"],
        ["Hot-reload", "Automatic on file change (mtime), no restart needed"],
        ["Missing file", "Warning logged, ban proceeds normally"],
        ["Invalid entry", "Warning logged, entry skipped, others still applied"],
    ]
    story.append(table(wl_data, col_widths=[5*cm, 11.5*cm]))
    story.append(note(
        "Always include management network addresses and monitoring servers "
        "in the whitelist to prevent accidentally blocking administrative access."
    ))
    story.append(PageBreak())

    # ------------------------------------------------------------------
    # 5. POUŽITÍ
    # ------------------------------------------------------------------
    story.append(h1("5. Usage"))

    story.append(h2("5.1 Automatic Usage via fail2ban"))
    story.append(p(
        "Once correctly configured in jail.local, fail2ban calls the script automatically. "
        "No manual intervention is required."
    ))

    story.append(h2("5.2 Manual Invocation"))
    story.append(p("The script can be called directly from the command line:"))

    cmd_data = [
        ["Action", "Command"],
        ["Ban IPv4", "exafs_action.py ban 1.2.3.4 3600"],
        ["Ban IPv6", "exafs_action.py ban 2001:db8::1 86400"],
        ["Ban network", "exafs_action.py ban 10.0.0.0/24 3600"],
        ["Unban IP", "exafs_action.py unban 1.2.3.4"],
        ["List active bans", "exafs_action.py list"],
        ["Dry-run simulation", "exafs_action.py ban 1.2.3.4 3600 --dry-run"],
        ["Custom config file", "exafs_action.py --config /etc/exafs.cfg ban 1.2.3.4 3600"],
        ["Verbose output", "exafs_action.py ban 1.2.3.4 3600 --verbose"],
    ]
    story.append(table(cmd_data, col_widths=[4.5*cm, 12*cm]))

    story.append(h2("5.3 Listing Active Bans"))
    story.append(code(
        "$ exafs_action.py list\n\n"
        "IP address                                    ExaFS rule_id\n"
        "------------------------------------------------------------\n"
        "1.2.3.4                                       42\n"
        "2001:db8::1                                   43\n"
        "10.0.0.0/24                                   44"
    ))

    story.append(h2("5.4 Dry-Run Mode"))
    story.append(p(
        "Use the <b>--dry-run</b> flag to verify the configuration and behaviour "
        "without actually calling the ExaFS API. The script only logs what it would do."
    ))
    story.append(code(
        "$ exafs_action.py ban 1.2.3.4 3600 --dry-run\n"
        "2025-01-01 12:00:00 exafs_action INFO [DRY-RUN] Would POST /rules/rtbh: "
        '{\"community\": 1, \"expires\": \"01/01/2025 13:00\", '
        '\"ipv4\": \"1.2.3.4\", \"ipv4_mask\": 32, \"comment\": \"fail2ban auto-block\"}'
    ))
    story.append(PageBreak())

    # ------------------------------------------------------------------
    # 6. TESTOVÁNÍ
    # ------------------------------------------------------------------
    story.append(h1("6. Testing"))

    story.append(h2("6.1 Unit Tests"))
    story.append(p(
        "Unit tests do not require a running ExaFS instance -- HTTP calls are mocked. "
        "They cover IP address parsing, JWT cache management, ban/unban logic, "
        "the retry mechanism, and error handling."
    ))
    story.append(code(
        "# Run all unit tests\n"
        "python3 test_exafs_action.py --verbose\n\n"
        "# Or using pytest\n"
        "python3 -m pytest test_exafs_action.py -v"
    ))
    story.append(p("Test classes and coverage:"))
    test_data = [
        ["Test Class", "What it covers"],
        ["TestParseIP", "IPv4/IPv6 address and network parsing, invalid input"],
        ["TestNetworkFields", "ExaFS payload field generation for all address types"],
        ["TestTokenCache", "JWT token fetching, caching, expiry and refresh"],
        ["TestBan", "Ban action: IPv4/IPv6, payload, 409 Conflict, dry-run"],
        ["TestUnban", "Unban action: rule deletion, 404, unknown IP, dry-run"],
        ["TestWhitelist", "Whitelist: CIDR matching, hot-reload, IPv4/IPv6, ban integration"],
        ["TestRetryLogic", "Retry on 5xx/429, connection errors, 401 token refresh"],
        ["TestIntegration", "Live ExaFS API tests (opt-in, --integration flag)"],
    ]
    story.append(table(test_data, col_widths=[5.5*cm, 11*cm]))
    story.append(code(
        "# Expected output (unit tests only):\n"
        "test_invalid_raises_sysexit (TestParseIP) ... ok\n"
        "test_ipv4_address (TestParseIP) ... ok\n"
        "...\n"
        "test_ban_skipped_for_whitelisted_ip (TestWhitelist) ... ok\n"
        "test_hot_reload_adds_new_network (TestWhitelist) ... ok\n"
        "...\n"
        "test_token_refresh_on_401 (TestRetryLogic) ... ok\n"
        "----------------------------------------------------------------------\n"
        "Ran 36 tests in 0.042s\n"
        "OK"
    ))

    story.append(h2("6.2 Integration Tests"))
    story.append(p(
        "Integration tests call the real ExaFS API and create/delete an actual "
        "RTBH rule. They use safe test IP addresses (RFC 5737, RFC 3849)."
    ))
    story.append(warn(
        "Integration tests will create a real RTBH rule in ExaFS! "
        "Run only against a test environment."
    ))
    story.append(code(
        "python3 test_exafs_action.py \\\n"
        "    --integration \\\n"
        "    --config /etc/fail2ban/exafs.cfg \\\n"
        "    --verbose"
    ))

    story.append(h2("6.3 Manual Configuration Verification"))
    story.append(code(
        "# Test ExaFS reachability and API key validity\n"
        "exafs_action.py ban 192.0.2.1 60 --dry-run --verbose\n\n"
        "# Try a real ban with a short block duration\n"
        "exafs_action.py ban 192.0.2.1 60\n"
        "exafs_action.py list\n"
        "exafs_action.py unban 192.0.2.1"
    ))
    story.append(PageBreak())

    # ------------------------------------------------------------------
    # 7. ARCHITEKTURA
    # ------------------------------------------------------------------
    story.append(h1("7. Architecture and Behaviour"))

    story.append(h2("7.1 JWT Token Cache"))
    story.append(p(
        "ExaFS JWT tokens are valid for 90 minutes. The script caches the token in "
        "<b>/var/lib/fail2ban/exafs/token.json</b> (chmod 600) and reuses it until "
        "it expires. The token is renewed automatically:"
    ))
    story.extend(bullet([
        "5 minutes before expiry (proactive renewal)",
        "Immediately upon receiving HTTP 401 Unauthorized (reactive renewal)",
    ]))

    story.append(h2("7.2 Rule ID Storage"))
    story.append(p(
        "Each RTBH rule receives a unique <b>rule_id</b> from ExaFS. "
        "The script stores it in <b>/var/lib/fail2ban/exafs/rules.json</b> "
        "so it can issue the DELETE request on unban. "
        "Writes are protected by a file lock (flock) for safe concurrent access."
    ))

    story.append(h2("7.3 Retry and Network Error Handling"))
    retry_data = [
        ["Situation", "Behaviour"],
        ["Transient network error (timeout, conn. refused)", "3 attempts, delay 2s/4s/8s"],
        ["HTTP 5xx or 429 Too Many Requests", "3 attempts, delay 2s/4s/8s"],
        ["HTTP 401 Unauthorized (expired token)", "Token refresh + 1 retry"],
        ["HTTP 409 Conflict (IP already blocked)", "Warning logged, no error"],
        ["HTTP 404 on unban (rule already expired)", "Warning logged, no error"],
        ["All retries exhausted", "Error message + exit code 1"],
    ]
    story.append(table(retry_data, col_widths=[8.5*cm, 8*cm]))

    story.append(h2("7.4 Logging"))
    story.append(p("The script logs to three destinations simultaneously:"))
    story.extend(bullet([
        "<b>/var/log/fail2ban-exafs.log</b> -- file with timestamps",
        "<b>/dev/log</b> (syslog) -- integrates with the fail2ban log chain",
        "<b>stderr</b> -- visible when called directly",
    ]))

    story.append(h2("7.5 Runtime Files"))
    files_data = [
        ["File", "Contents", "Permissions"],
        ["/var/lib/fail2ban/exafs/token.json", "Cached JWT token + expiry time", "600"],
        ["/var/lib/fail2ban/exafs/rules.json", "IP to ExaFS rule_id map", "644"],
        ["/var/lib/fail2ban/exafs/rules.lock", "Lock file for concurrent access", "644"],
        ["/var/log/fail2ban-exafs.log", "Action log file", "644"],
    ]
    story.append(table(files_data, col_widths=[6.5*cm, 6*cm, 3*cm]))
    story.append(PageBreak())

    # ------------------------------------------------------------------
    # 8. ŘEŠENÍ PROBLÉMŮ
    # ------------------------------------------------------------------
    story.append(h1("8. Troubleshooting"))

    story.append(h2("8.1 Checking the Log"))
    story.append(code(
        "# Follow the log in real time\n"
        "tail -f /var/log/fail2ban-exafs.log\n\n"
        "# Search for errors\n"
        "grep ERROR /var/log/fail2ban-exafs.log"
    ))

    story.append(h2("8.2 Common Issues"))

    problems = [
        ("Config file not found",
         "The file /etc/fail2ban/exafs.cfg does not exist.",
         "cp exafs.cfg.example /etc/fail2ban/exafs.cfg && nano /etc/fail2ban/exafs.cfg"),
        ("Failed to obtain JWT token",
         "Wrong api_key or ExaFS URL, or the server is unreachable.",
         "curl -v -H 'x-api-key: YOUR_KEY' https://exafs.example.com/auth"),
        ("No stored rule_id for <ip>",
         "Unban was called for an IP that was not banned by this script (or rules.json was deleted).",
         "Ignore, or delete the rule manually in the ExaFS UI."),
        ("Permission denied: /var/lib/fail2ban/exafs",
         "Script is running as an unprivileged user.",
         "chown root:root /var/lib/fail2ban/exafs && chmod 700 /var/lib/fail2ban/exafs"),
    ]

    for err, cause, fix in problems:
        story.append(KeepTogether([
            h3(f"Error: {err}"),
            Paragraph(f"<b>Cause:</b> {cause}", styles["body_left"]),
            Paragraph("<b>Fix:</b>", styles["body_left"]),
            code(fix),
        ]))

    story.append(h2("8.3 Verifying Communication with ExaFS"))
    story.append(code(
        "# Test ExaFS reachability\n"
        "curl -k https://exafs.example.com/auth \\\n"
        "     -H 'x-api-key: YOUR_API_KEY'\n\n"
        "# Expected response:\n"
        '# {"token": "eyJ..."}'
    ))
    story.append(PageBreak())

    # ------------------------------------------------------------------
    # 9. PŘEHLED SOUBORŮ
    # ------------------------------------------------------------------
    story.append(h1("9. Project File Overview"))

    files2_data = [
        ["File", "Description"],
        ["exafs_action.py", "Main script -- ban/unban/list actions + WhitelistChecker"],
        ["action.d/exafs.conf", "fail2ban action plugin"],
        ["exafs.cfg.example", "Configuration file template (incl. whitelist_file option)"],
        ["exafs-whitelist.conf", "Whitelist of addresses/networks never blocked (example)"],
        ["test_exafs_action.py", "Unit and integration tests (incl. TestWhitelist)"],
        ["requirements.txt", "Python dependencies (requests)"],
        ["exafs_action.1", "Man page (incl. WHITELIST section)"],
        ["exafs_action_documentation.pdf", "This document"],
    ]
    story.append(table(files2_data, col_widths=[6.5*cm, 10*cm]))

    story.append(sp(20))
    story.append(hr())
    story.append(Paragraph(
        "Documentation created for the fail2ban + ExaFS integration project. "
        "ExaFS is an open-source project by CESNET, MIT license.",
        styles["body"]
    ))

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    doc.multiBuild(story)
    print(f"PDF created: {OUTPUT}")


if __name__ == "__main__":
    build()
