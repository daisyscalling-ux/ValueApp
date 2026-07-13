"""
marketnews.py — allgemeine Markt-News mit Kurzzusammenfassungen.

Zieht kuratierte RSS-Feeds grosser Finanzportale (mit echten Kurztexten) und
liefert je Sektion die wichtigsten, aktuellsten Meldungen:
  US-Markt, DAX/Deutschland, Asien  +  Aktien-News (allgemein).

Robust: schlaegt ein Feed fehl, fuellen die anderen die Sektion. Jede Meldung
enthaelt Headline, Quelle, Datum, Link und eine gekuerzte Zusammenfassung.
"""
from __future__ import annotations
import re
import html as _html

try:
    import requests
except Exception:
    requests = None

# Kuratierte Feeds je Sektion (mehrere pro Sektion = Ausfallsicherheit)
FEEDS = {
    "US-Markt": [
        "https://feeds.marketwatch.com/marketwatch/topstories/",
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",   # CNBC Markets
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # CNBC Top News
        "https://feeds.bloomberg.com/markets/news.rss",           # Bloomberg Markets
        # Reuters ueber Google-News (Reuters eigene RSS sind groesstenteils eingestellt)
        "https://news.google.com/rss/search?q=site:reuters.com+when:2d&hl=en-US&gl=US&ceid=US:en",
    ],
    "DAX": [
        "https://www.tagesschau.de/wirtschaft/index~rss2.xml",
        "https://www.handelsblatt.com/contentexport/feed/finanzen",
        "https://www.finanzen.net/rss/news",
    ],
    "Asien": [
        "https://asia.nikkei.com/rss/feed/nar",
        "https://www.scmp.com/rss/92/feed",                        # SCMP Business
        "https://www.cnbc.com/id/19832390/device/rss/rss.html",   # CNBC Asia
    ],
    "WSJ": [
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",       # WSJ Markets
        "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",     # WSJ US Business
        "https://feeds.a.dj.com/rss/RSSWSJD.xml",              # WSJ Technology
        "https://feeds.a.dj.com/rss/RSSWorldNews.xml",         # WSJ World News
    ],
    "Aktien-News": [
        "https://www.investing.com/rss/news_25.rss",              # Stock Market News
        "https://feeds.marketwatch.com/marketwatch/marketpulse/",
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",   # CNBC Markets
        "https://feeds.bloomberg.com/technology/news.rss",        # Bloomberg Tech
        "https://news.google.com/rss/search?q=site:reuters.com+business+when:2d&hl=en-US&gl=US&ceid=US:en",
    ],
    "Yahoo US": [
        "https://finance.yahoo.com/news/rssindex",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
    ],
}

# Bekannte HART-paywalled Domains -> "Paywall moeglich". Nicht abschliessend,
# aber deckt die wichtigsten Finanzquellen ab. Reuters ist "metered" (erste
# Artikel frei) -> als eher frei behandelt, aber separat gekennzeichnet.
_PAYWALLED = {
    "bloomberg.com", "wsj.com", "ft.com", "nytimes.com", "economist.com",
    "barrons.com", "seekingalpha.com", "investors.com", "theinformation.com",
    "thetimes.co.uk", "nikkei.com", "asia.nikkei.com", "scmp.com",
    "handelsblatt.com",
}
_METERED = {"reuters.com"}          # metered: meist lesbar, kann aber zumachen
# Ueberwiegend frei lesbare Domains (nur zur Kennzeichnung)
_FREE = {"cnbc.com", "marketwatch.com", "finanzen.net", "tagesschau.de",
         "investing.com", "finance.yahoo.com", "yahoo.com"}

_ATOM = "{http://www.w3.org/2005/Atom}"
_CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"


def _clean(text, maxlen=320):
    if not text:
        return ""
    text = _html.unescape(text)                   # erst Entities aufloesen
    text = re.sub(r"<[^>]+>", " ", text)          # dann HTML-Tags raus
    text = _html.unescape(text)                   # evtl. Reste
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(Mehr lesen|Read more|Continue reading).*$", "", text).strip()
    if len(text) > maxlen:
        text = text[:maxlen].rsplit(" ", 1)[0] + " \u2026"
    return text


def _parse_date(s):
    if not s:
        return 0.0
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).timestamp()
    except Exception:
        try:
            import datetime as dt
            return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0


def _domain(url):
    try:
        return re.sub(r"^www\.", "", url.split("/")[2]).lower()
    except Exception:
        return ""


def _matches(domain, dset):
    return any(domain == d or domain.endswith("." + d) for d in dset)


def access_of(url, source_url=""):
    """Klassifiziert die Lesbarkeit: 'frei', 'metered' oder 'paywall'.
    Nutzt bevorzugt die echte Quell-Domain (source_url aus Google-News)."""
    dom = _domain(source_url) or _domain(url)
    if _matches(dom, _PAYWALLED):
        return "paywall"
    if _matches(dom, _METERED):
        return "metered"
    return "frei"                      # bekannt frei ODER unbekannt -> als frei behandeln


def fetch_feed(url, limit=12):
    if requests is None:
        return []
    try:
        import xml.etree.ElementTree as ET
        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(r.content)
    except Exception:
        return []

    out = []
    chan = root.find(".//channel")
    chan_title = (chan.findtext("title") if chan is not None else None) or _domain(url)

    items = root.findall(".//item")
    if items:
        for it in items[:limit]:
            desc = it.findtext("description") or it.findtext(_CONTENT)
            srcel = it.find("source")
            src_url = srcel.get("url") if srcel is not None else ""
            link = (it.findtext("link") or "").strip()
            out.append({
                "headline": (it.findtext("title") or "").strip(),
                "url": link,
                "source": (srcel.text if srcel is not None else None) or chan_title,
                "ts": _parse_date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")),
                "summary": _clean(desc),
                "access": access_of(link, src_url),
            })
    else:  # Atom
        for e in root.findall(f".//{_ATOM}entry")[:limit]:
            le = e.find(f"{_ATOM}link")
            href = le.get("href") if le is not None else ""
            out.append({
                "headline": (e.findtext(f"{_ATOM}title") or "").strip(),
                "url": href,
                "source": chan_title,
                "ts": _parse_date(e.findtext(f"{_ATOM}updated") or e.findtext(f"{_ATOM}published")),
                "summary": _clean(e.findtext(f"{_ATOM}summary") or e.findtext(f"{_ATOM}content")),
                "access": access_of(href),
            })
    return [x for x in out if x["headline"]]


def get_section(section, limit=12, free_only=False):
    """Meldungen einer Sektion: gemerged, dedupliziert, neueste zuerst.
    free_only=True blendet Artikel mit 'paywall'-Status aus."""
    items, seen = [], set()
    for url in FEEDS.get(section, []):
        for it in fetch_feed(url):
            key = it["headline"][:80].lower()
            if key in seen:
                continue
            if free_only and it.get("access") == "paywall":
                continue
            seen.add(key)
            items.append(it)
    items.sort(key=lambda x: x["ts"], reverse=True)
    return items[:limit]
