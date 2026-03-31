#!/usr/bin/env python3
"""
PDF dokumentace pro exafs_action (fail2ban + ExaFS integrace).
Grafický styl dle CESNET Design Manuálu v2/2019.

Spuštění:  python3 doc/generate_docs.py
Výstup:    doc/exafs_action_documentation.pdf
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Preformatted,
    Table, TableStyle, PageBreak, HRFlowable, KeepTogether,
    BaseDocTemplate, Frame, PageTemplate,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus.doctemplate import NextPageTemplate
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT

# ── Rozměry stránky ────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN_L = 2.2 * cm
MARGIN_R = 2.0 * cm
MARGIN_T = 2.0 * cm
MARGIN_B = 1.8 * cm
FOOTER_H = 1.2 * cm

# ── Barvy dle CESNET Design Manuálu 2019 ──────────────────────────────────────
C_BLUE   = colors.HexColor("#0068A2")   # CESNET Blue (primární)
C_FRESH  = colors.HexColor("#00A1DE")   # Fresh Blue (doplňková)
C_GREY   = colors.HexColor("#5A5A5A")   # CESNET Grey (text)
C_LGREY  = colors.HexColor("#AAAAAA")   # Light Grey
C_XLIGHT = colors.HexColor("#F4F6F8")   # velmi světlá plocha (tabulky)
C_WHITE  = colors.white
C_NOTE_BG = colors.HexColor("#EEF6FC")
C_NOTE_BD = colors.HexColor("#00A1DE")
C_WARN_BG = colors.HexColor("#FFF4E5")
C_WARN_BD = colors.HexColor("#F27930")
C_CODE_BG = colors.HexColor("#F5F5F5")
C_CODE_BD = colors.HexColor("#AAAAAA")

# ── Styly ──────────────────────────────────────────────────────────────────────
def S(name, **kw):
    return ParagraphStyle(name, **kw)

st = {
    "cover_title": S("CoverTitle",
        fontSize=28, leading=34, textColor=C_WHITE,
        fontName="Helvetica-Bold", alignment=TA_LEFT, spaceAfter=4),
    "cover_sub": S("CoverSub",
        fontSize=13, leading=18, textColor=colors.HexColor("#BFD8EC"),
        fontName="Helvetica", alignment=TA_LEFT, spaceAfter=3),
    "cover_meta": S("CoverMeta",
        fontSize=9, leading=13, textColor=colors.HexColor("#99C0D8"),
        fontName="Helvetica", alignment=TA_LEFT),
    "h1": S("H1",
        fontSize=15, leading=20, textColor=C_BLUE,
        fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=7),
    "h2": S("H2",
        fontSize=12, leading=16, textColor=C_GREY,
        fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=5),
    "h3": S("H3",
        fontSize=10.5, leading=14, textColor=C_BLUE,
        fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=3),
    "body": S("Body",
        fontSize=9.5, leading=14, textColor=C_GREY,
        fontName="Helvetica", spaceAfter=5, alignment=TA_JUSTIFY),
    "body_l": S("BodyL",
        fontSize=9.5, leading=14, textColor=C_GREY,
        fontName="Helvetica", spaceAfter=5),
    "bullet": S("Bullet",
        fontSize=9.5, leading=14, textColor=C_GREY,
        fontName="Helvetica", spaceAfter=2,
        leftIndent=14, bulletIndent=3),
    "code": S("Code",
        fontSize=8, leading=12, textColor=colors.HexColor("#2C3E50"),
        fontName="Courier", backColor=C_CODE_BG,
        borderColor=C_CODE_BD, borderWidth=0.4, borderPad=7,
        spaceAfter=7, spaceBefore=2),
    "note": S("Note",
        fontSize=9, leading=13, textColor=colors.HexColor("#005A8A"),
        fontName="Helvetica", backColor=C_NOTE_BG,
        borderColor=C_NOTE_BD, borderWidth=1.2,
        borderPad=7, spaceAfter=7),
    "warn": S("Warn",
        fontSize=9, leading=13, textColor=colors.HexColor("#7A3500"),
        fontName="Helvetica", backColor=C_WARN_BG,
        borderColor=C_WARN_BD, borderWidth=1.2,
        borderPad=7, spaceAfter=7),
    "toc1": S("TOC1",
        fontSize=11, leading=16, fontName="Helvetica-Bold",
        textColor=C_BLUE, leftIndent=0, spaceAfter=2),
    "toc2": S("TOC2",
        fontSize=9.5, leading=13, fontName="Helvetica",
        textColor=C_GREY, leftIndent=14, spaceAfter=1),
}

# ── Zkratky ────────────────────────────────────────────────────────────────────
def h1(t):   return Paragraph(t, st["h1"])
def h2(t):   return Paragraph(t, st["h2"])
def h3(t):   return Paragraph(t, st["h3"])
def p(t):    return Paragraph(t, st["body"])
def pl(t):   return Paragraph(t, st["body_l"])
def note(t): return Paragraph(f"<b>Note:</b>  {t}", st["note"])
def warn(t): return Paragraph(f"<b>Warning:</b>  {t}", st["warn"])
def sp(n=6): return Spacer(1, n)
def hr():    return HRFlowable(width="100%", thickness=0.5, color=C_LGREY, spaceAfter=4)

def code(t):
    return Preformatted(t, st["code"])

def bullets(items):
    return [Paragraph(f"&bull;&nbsp;&nbsp;{i}", st["bullet"]) for i in items]

def tbl(data, widths=None, header=True):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    ts = [
        ("BACKGROUND",    (0, 0), (-1,  0 if header else -1), C_BLUE if header else C_XLIGHT),
        ("TEXTCOLOR",     (0, 0), (-1,  0), C_WHITE if header else C_GREY),
        ("FONTNAME",      (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("LEADING",       (0, 0), (-1, -1), 12),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_WHITE, C_XLIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.3, C_LGREY),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TEXTCOLOR",     (0, 1), (-1, -1), C_GREY),
    ]
    t.setStyle(TableStyle(ts))
    return t

# ── CESNET logo (programatické kreslení dle design manuálu) ───────────────────
# Binární zápis 'c' (ASCII 99 = 1100011) — 1=nahoře, 0=dole
BINARY_C = [1, 1, 0, 0, 0, 1, 1]

def draw_cesnet_logo(cv, x, y, sq=20, color=C_BLUE, text_color=C_GREY):
    """
    Nakreslí logo CESNET dle design manuálu:
    - binární proužek 1100011 (písmeno 'c')
    - mezera mezi čtverečky = 60 % šířky čtverečku
    - horní čtverečky = jedničky, dolní = nuly
    - nápis 'cesnet' pod proužkem, velikost 72 % výšky čtverečku
    """
    gap = sq * 0.6
    axis_y = y + sq * 0.5      # osa oddělující horní a dolní čtverečky
    upper_y = axis_y + sq * 0.1
    lower_y = axis_y - sq * 1.1

    cv.setFillColor(color)
    for i, bit in enumerate(BINARY_C):
        sq_x = x + i * (sq + gap)
        sq_y = upper_y if bit == 1 else lower_y
        cv.rect(sq_x, sq_y, sq, sq, fill=1, stroke=0)

    cv.setFillColor(text_color)
    cv.setFont("Helvetica-Bold", sq * 0.72)
    cv.drawString(x, lower_y - sq * 0.85, "cesnet")

def logo_total_width(sq=20):
    return len(BINARY_C) * sq + (len(BINARY_C) - 1) * sq * 0.6

# ── Dekorace stran ────────────────────────────────────────────────────────────
def page_cover(cv, doc):
    cv.saveState()
    # Modrý boční pruh vlevo
    cv.setFillColor(C_BLUE)
    cv.rect(0, 0, 1.1 * cm, PAGE_H, fill=1, stroke=0)
    # Tenký fresh blue proužek
    cv.setFillColor(C_FRESH)
    cv.rect(1.1 * cm, 0, 0.22 * cm, PAGE_H, fill=1, stroke=0)
    # Zápatí
    cv.setFillColor(C_LGREY)
    cv.setFont("Helvetica", 7.5)
    cv.drawString(2.3 * cm, 0.7 * cm,
                  "cesnet.cz  \u00b7  exafs_action \u2014 fail2ban + ExaFS Integration")
    cv.restoreState()

def page_normal(cv, doc):
    cv.saveState()
    # Záhlaví — modrá linka
    top_y = PAGE_H - MARGIN_T + 1.5 * mm
    cv.setStrokeColor(C_BLUE)
    cv.setLineWidth(1.5)
    cv.line(MARGIN_L, top_y, PAGE_W - MARGIN_R, top_y)

    # Logo vpravo nahoře (malé)
    sq = 5.5
    lw = logo_total_width(sq)
    draw_cesnet_logo(cv,
        x=PAGE_W - MARGIN_R - lw,
        y=PAGE_H - MARGIN_T + 2.5 * mm,
        sq=sq, color=C_BLUE, text_color=C_GREY)

    # Zápatí
    cv.setFillColor(C_LGREY)
    cv.setFont("Helvetica", 7.5)
    cv.drawString(MARGIN_L, FOOTER_H * 0.45,
                  "exafs_action  \u00b7  fail2ban + ExaFS RTBH Integration")
    cv.setFillColor(C_BLUE)
    cv.setFont("Helvetica-Bold", 8)
    cv.drawRightString(PAGE_W - MARGIN_R, FOOTER_H * 0.45, str(doc.page))
    cv.setStrokeColor(C_XLIGHT)
    cv.setLineWidth(0.4)
    cv.line(MARGIN_L, FOOTER_H * 0.8, PAGE_W - MARGIN_R, FOOTER_H * 0.8)
    cv.restoreState()

# ── Dokument s TOC ─────────────────────────────────────────────────────────────
class CesnetDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, **kw)
        cover_frame  = Frame(0, 0, PAGE_W, PAGE_H, id="cover")
        normal_frame = Frame(
            MARGIN_L, FOOTER_H + 2 * mm,
            PAGE_W - MARGIN_L - MARGIN_R,
            PAGE_H - MARGIN_T - FOOTER_H - 5 * mm,
            id="normal")
        self.addPageTemplates([
            PageTemplate("cover",  frames=[cover_frame],  onPage=page_cover),
            PageTemplate("normal", frames=[normal_frame], onPage=page_normal),
        ])

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            s = flowable.style.name
            t = flowable.getPlainText()
            if s == "H1":   self.notify("TOCEntry", (0, t, self.page, None))
            elif s == "H2": self.notify("TOCEntry", (1, t, self.page, None))

# ── Titulní strana s logem (flowable) ─────────────────────────────────────────
class CoverLogo(Spacer):
    """Nakreslí velké CESNET logo na titulní straně."""
    def draw(self):
        draw_cesnet_logo(self.canv,
            x=2.5 * cm, y=self.height * 0.15,
            sq=18, color=C_WHITE,
            text_color=colors.HexColor("#BFD8EC"))

# ══════════════════════════════════════════════════════════════════════════════
# OBSAH DOKUMENTU
# ══════════════════════════════════════════════════════════════════════════════
def build():
    OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "exafs_action_documentation.pdf")
    doc = CesnetDoc(
        OUTPUT, pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B,
        title="exafs_action — fail2ban + ExaFS Integration",
        author="CESNET / fail2ban ExaFS Integration",
        subject="BGP RTBH blocking via fail2ban and ExaFS",
    )
    story = []

    # ── TITULNÍ STRANA ──────────────────────────────────────────────────────
    story.append(Spacer(1, PAGE_H * 0.20))
    story.append(CoverLogo(1, 2.2 * cm))
    story.append(sp(10))
    story.append(Paragraph("exafs_action", st["cover_title"]))
    story.append(Paragraph("fail2ban Integration with ExaFS BGP RTBH", st["cover_sub"]))
    story.append(sp(18))
    story.append(HRFlowable(width="65%", thickness=1, color=colors.HexColor("#3388BB"),
                             hAlign="LEFT"))
    story.append(sp(18))
    story.append(Paragraph(
        "Automatically blocks malicious IPs at the network level using BGP Remotely "
        "Triggered Black Hole rules managed via ExaFS REST API.",
        st["cover_meta"]))
    story.append(sp(10))
    story.append(Paragraph("Version 1.1  \u00b7  2026  \u00b7  MIT License",
                            st["cover_meta"]))
    story.append(Paragraph(
        '<a href="https://github.com/CESNET/exafs" color="#99C0D8">github.com/CESNET/exafs</a>',
        st["cover_meta"]))
    story.append(PageBreak())

    # ── OBSAH ───────────────────────────────────────────────────────────────
    story.append(NextPageTemplate("normal"))
    story.append(h1("Contents"))
    toc = TableOfContents()
    toc.levelStyles = [st["toc1"], st["toc2"]]
    toc.dotsMinLevel = 0
    story.append(toc)
    story.append(PageBreak())

    # ── 1. OVERVIEW ─────────────────────────────────────────────────────────
    story.append(h1("1. Overview"))
    story.append(p(
        "<b>exafs_action</b> integrates <b>fail2ban</b> with the <b>ExaFS</b> web application "
        "(CESNET) to block malicious IPs at the network level. Instead of a local firewall rule, "
        "the script creates a BGP RTBH rule via the ExaFS REST API — traffic from the banned IP "
        "is dropped across the entire network infrastructure."
    ))
    story.append(tbl([
        ["Component",       "Host",            "Role"],
        ["fail2ban",        "Monitored host",  "Detects malicious activity from logs"],
        ["exafs_action.py", "Monitored host",  "Translates ban/unban into ExaFS API calls"],
        ["ExaFS",           "Separate server", "Manages BGP RTBH rules via REST API"],
        ["ExaBGP",          "Network device",  "Propagates BGP messages to the network"],
    ], widths=[3.8*cm, 4.5*cm, 8.2*cm]))
    story.append(sp(4))
    story.append(note(
        "fail2ban and exafs_action.py run on a <b>different host</b> than ExaFS. "
        "Communication uses HTTPS. Both IPv4 and IPv6 are supported (addresses and CIDR networks)."
    ))
    story.append(PageBreak())

    # ── 2. REQUIREMENTS & INSTALLATION ──────────────────────────────────────
    story.append(h1("2. Requirements & Installation"))

    story.append(h2("2.1 Requirements"))
    story.append(tbl([
        ["Requirement", "Details"],
        ["Linux",       "RHEL/CentOS 8+, Debian 11+, Ubuntu 20.04+"],
        ["Python",      "3.8 or later"],
        ["fail2ban",    "0.11 or later"],
        ["requests",    "2.28.0 or later — pip3 install requests"],
        ["ExaFS",       "Running instance accessible via HTTPS, API key generated, "
                        "RTBH community configured"],
    ], widths=[3.8*cm, 12.7*cm]))

    story.append(h2("2.2 Installation Steps"))
    story.append(code(
        "# 1. Python dependency\n"
        "pip3 install -r requirements.txt\n\n"
        "# 2. Main script\n"
        "cp exafs_action.py /usr/local/bin/exafs_action.py\n"
        "chmod +x /usr/local/bin/exafs_action.py\n\n"
        "# 3. fail2ban action plugin\n"
        "cp action.d/exafs.conf /etc/fail2ban/action.d/exafs.conf\n\n"
        "# 4. Configuration (fill in url, api_key, community)\n"
        "cp exafs.cfg.example /etc/fail2ban/exafs.cfg\n"
        "chmod 600 /etc/fail2ban/exafs.cfg\n\n"
        "# 5. Whitelist\n"
        "cp exafs-whitelist.conf /etc/fail2ban/exafs-whitelist.conf\n"
        "chmod 600 /etc/fail2ban/exafs-whitelist.conf\n\n"
        "# 6. Man page (optional)\n"
        "cp exafs_action.1 /usr/local/share/man/man1/\n"
        "gzip /usr/local/share/man/man1/exafs_action.1 && mandb"
    ))
    story.append(PageBreak())

    # ── 3. CONFIGURATION ────────────────────────────────────────────────────
    story.append(h1("3. Configuration"))

    story.append(h2("3.1 /etc/fail2ban/exafs.cfg"))
    story.append(code(
        "[exafs]\n"
        "url            = https://exafs.example.com   # no trailing slash\n"
        "api_key        = YOUR_API_KEY_HERE            # Administration -> API keys\n"
        "community      = 1                            # Administration -> Communities\n"
        "whitelist_file = /etc/fail2ban/exafs-whitelist.conf"
    ))
    story.append(note(
        "Obtain the API key in ExaFS: <b>Administration &rarr; API keys &rarr; Generate new key</b>. "
        "The JWT token is valid up to 90 minutes and renewed automatically "
        "5 minutes before expiry — no manual action required."
    ))

    story.append(h2("3.2 fail2ban — /etc/fail2ban/jail.local"))
    story.append(code(
        "[sshd]\n"
        "enabled  = true\n"
        "action   = exafs\n"
        "bantime  = 3600\n"
        "findtime = 600\n"
        "maxretry = 5\n\n"
        "# Combine with local firewall:\n"
        "# action = %(action_mwl)s\n"
        "#          exafs"
    ))

    story.append(h2("3.3 Whitelist — /etc/fail2ban/exafs-whitelist.conf"))
    story.append(p(
        "Addresses in the whitelist are <b>never</b> blocked via ExaFS regardless of "
        "fail2ban decisions. The file is hot-reloaded on modification — no restart needed. "
        "Supports IPv4 and IPv6 in CIDR notation. Lines starting with # are comments."
    ))
    story.append(code(
        "# Management network\n"
        "10.10.10.0/24\n\n"
        "# Monitoring server\n"
        "203.0.113.10\n\n"
        "# IPv6 prefix\n"
        "2001:db8::/32"
    ))
    story.append(warn(
        "Always whitelist management networks and monitoring servers "
        "to prevent accidentally locking out administrative access."
    ))
    story.append(PageBreak())

    # ── 4. USAGE ────────────────────────────────────────────────────────────
    story.append(h1("4. Usage"))

    story.append(h2("4.1 Command Reference"))
    story.append(tbl([
        ["Command",                                    "Description"],
        ["exafs_action.py ban <ip> <seconds>",         "Create RTBH rule (IPv4/IPv6, CIDR supported)"],
        ["exafs_action.py unban <ip>",                 "Delete RTBH rule"],
        ["exafs_action.py list",                       "List locally tracked bans"],
        ["  … --dry-run",                              "Simulate without calling ExaFS API"],
        ["  … --verbose",                              "Enable DEBUG log output"],
        ["  … --config /path/exafs.cfg",               "Use a custom configuration file"],
    ], widths=[7.2*cm, 9.3*cm]))

    story.append(h2("4.2 Examples"))
    story.append(code(
        "# Ban for 1 hour\n"
        "exafs_action.py ban 1.2.3.4       3600\n"
        "exafs_action.py ban 2001:db8::1   86400\n"
        "exafs_action.py ban 10.0.0.0/24   3600\n\n"
        "# Unban\n"
        "exafs_action.py unban 1.2.3.4\n\n"
        "# List\n"
        "exafs_action.py list\n"
        "  IP address                                    ExaFS rule_id\n"
        "  ------------------------------------------------------------\n"
        "  1.2.3.4                                       42\n"
        "  2001:db8::1                                   43\n\n"
        "# Test configuration without calling ExaFS\n"
        "exafs_action.py ban 1.2.3.4 3600 --dry-run --verbose"
    ))
    story.append(PageBreak())

    # ── 5. ARCHITECTURE ─────────────────────────────────────────────────────
    story.append(h1("5. Architecture & Behaviour"))

    story.append(h2("5.1 Authentication — JWT Token"))
    story.append(p(
        "The API key is exchanged for a JWT token via <b>GET /api/v3/auth</b> "
        "(header: <i>x-api-key</i>). The token is cached in "
        "<i>/var/lib/fail2ban/exafs/token.json</i> (mode 600). "
        "A fresh token is fetched proactively 5 minutes before expiry, "
        "or reactively upon HTTP 401."
    ))

    story.append(h2("5.2 Network Error Handling"))
    story.append(tbl([
        ["Situation",                             "Behaviour"],
        ["Connection error / timeout",            "Up to 3 retries — delays 2 s / 4 s / 8 s"],
        ["HTTP 429 or 5xx",                       "Up to 3 retries with exponential backoff"],
        ["HTTP 401 Unauthorized",                 "Token cache cleared, one automatic retry"],
        ["HTTP 409 Conflict (IP already blocked)","Warning logged — not an error"],
        ["HTTP 404 on unban",                     "Rule already gone — warning logged, continues"],
        ["All retries exhausted",                 "Error logged, exit code 1"],
    ], widths=[7*cm, 9.5*cm]))

    story.append(h2("5.3 Files"))
    story.append(tbl([
        ["File",                                       "Purpose",                          "Mode"],
        ["/etc/fail2ban/exafs.cfg",                    "URL, API key, community, whitelist","600"],
        ["/etc/fail2ban/exafs-whitelist.conf",         "Never-blocked addresses (hot-reload)","600"],
        ["/etc/fail2ban/action.d/exafs.conf",          "fail2ban action plugin",           "644"],
        ["/var/lib/fail2ban/exafs/token.json",         "Cached JWT token + expiry",        "600"],
        ["/var/lib/fail2ban/exafs/rules.json",         "IP -> ExaFS rule_id map",          "644"],
        ["/var/log/fail2ban-exafs.log",                "Action log",                       "644"],
    ], widths=[6.5*cm, 7*cm, 1.8*cm]))
    story.append(PageBreak())

    # ── 6. TESTING ──────────────────────────────────────────────────────────
    story.append(h1("6. Testing"))

    story.append(h2("6.1 Unit Tests"))
    story.append(p("No running ExaFS instance needed — all HTTP calls are mocked."))
    story.append(code(
        "python3 -m pytest test_exafs_action.py -v\n"
        "# or\n"
        "python3 test_exafs_action.py --verbose\n\n"
        "# Result: 41 passed, 7 skipped (integration) in ~0.2 s"
    ))
    story.append(tbl([
        ["Test class",        "Coverage"],
        ["TestParseIP",       "IPv4/IPv6 address and network parsing"],
        ["TestNetworkFields", "ExaFS payload field generation for all address types"],
        ["TestTokenCache",    "JWT caching, expiry detection, refresh"],
        ["TestBan",           "Ban flow, payload, 409 handling, dry-run"],
        ["TestUnban",         "Unban flow, 404 handling, unknown IP, dry-run"],
        ["TestWhitelist",     "CIDR matching, hot-reload, integration with ban()"],
        ["TestRetryLogic",    "5xx/429 retry, connection errors, 401 token refresh"],
        ["TestIntegration",   "Live ExaFS API — opt-in via --integration flag"],
    ], widths=[4.5*cm, 12*cm]))

    story.append(h2("6.2 Integration Tests"))
    story.append(code(
        "python3 test_exafs_action.py \\\n"
        "    --integration --config /etc/fail2ban/exafs.cfg --verbose"
    ))
    story.append(warn(
        "Integration tests create real RTBH rules in ExaFS. "
        "Run only against a test environment. "
        "Test IPs: 192.0.2.1 (RFC 5737) and 2001:db8::1 (RFC 3849)."
    ))
    story.append(PageBreak())

    # ── 7. TROUBLESHOOTING ──────────────────────────────────────────────────
    story.append(h1("7. Troubleshooting"))

    story.append(h2("7.1 Logs"))
    story.append(code(
        "tail -f /var/log/fail2ban-exafs.log\n"
        "grep ERROR /var/log/fail2ban-exafs.log\n"
        "journalctl -t exafs_action -f"
    ))

    story.append(h2("7.2 Common Issues"))
    story.append(tbl([
        ["Error",                            "Likely cause",          "Fix"],
        ["Config file not found",
         "exafs.cfg missing",
         "cp exafs.cfg.example /etc/fail2ban/exafs.cfg"],
        ["Failed to obtain JWT token",
         "Wrong api_key or URL",
         "curl -H 'x-api-key: KEY' https://exafs.example.com/api/v3/auth"],
        ["JSONDecodeError / non-JSON response",
         "url= includes /api/v3 (should not)",
         "url must be base URL only: https://exafs.example.com"],
        ["No stored rule_id for <ip>",
         "rules.json missing",
         "Delete rule manually in ExaFS UI"],
        ["Permission denied /var/lib/fail2ban/exafs",
         "Wrong ownership",
         "chown root /var/lib/fail2ban/exafs && chmod 700 ..."],
    ], widths=[4.2*cm, 4.8*cm, 7.5*cm]))

    story.append(h2("7.3 Verify ExaFS Connectivity"))
    story.append(code(
        "# Test API key — expected: {\"token\": \"eyJ...\"}\n"
        "curl -s -H 'x-api-key: YOUR_API_KEY' \\\n"
        "     https://exafs.example.com/api/v3/auth\n\n"
        "# Dry-run full flow\n"
        "exafs_action.py ban 192.0.2.1 60 --dry-run --verbose"
    ))

    story.append(sp(20))
    story.append(hr())
    story.append(pl(
        "ExaFS is an open-source project by CESNET (MIT) — "
        '<a href="https://github.com/CESNET/exafs" color="#0068A2">github.com/CESNET/exafs</a>'
    ))

    # ── BUILD ────────────────────────────────────────────────────────────────
    doc.multiBuild(story)
    print(f"PDF created: {OUTPUT}")


if __name__ == "__main__":
    build()
