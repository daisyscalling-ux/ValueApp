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
    "Aktien-News": [
        "https://www.investing.com/rss/news_25.rss",              # Stock Market News
        "https://feeds.marketwatch.com/marketwatch/marketpulse/",
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",   # CNBC Markets
    ],
    "Yahoo US": [
        "https://finance.yahoo.com/news/rssindex",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
    ],
}

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
        return re.sub(r"^www\.", "", url.split("/")[2])
    except Exception:
        return ""


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
            out.append({
                "headline": (it.findtext("title") or "").strip(),
                "url": (it.findtext("link") or "").strip(),
                "source": (srcel.text if srcel is not None else None) or chan_title,
                "ts": _parse_date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")),
                "summary": _clean(desc),
            })
    else:  # Atom
        for e in root.findall(f".//{_ATOM}entry")[:limit]:
            le = e.find(f"{_ATOM}link")
            out.append({
                "headline": (e.findtext(f"{_ATOM}title") or "").strip(),
                "url": le.get("href") if le is not None else "",
                "source": chan_title,
                "ts": _parse_date(e.findtext(f"{_ATOM}updated") or e.findtext(f"{_ATOM}published")),
                "summary": _clean(e.findtext(f"{_ATOM}summary") or e.findtext(f"{_ATOM}content")),
            })
    return [x for x in out if x["headline"]]


def get_section(section, limit=12):
    """Meldungen einer Sektion: gemerged, dedupliziert, neueste zuerst."""
    items, seen = [], set()
    for url in FEEDS.get(section, []):
        for it in fetch_feed(url):
            key = it["headline"][:80].lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(it)
    items.sort(key=lambda x: x["ts"], reverse=True)
    return items[:limit]
