"""
briefing.py — Schnell-Briefing fuer Nachrichten.

Fuer Leser, die informiert bleiben wollen, ohne lange Artikel zu lesen:
  - key_points():  extrahiert die 1-2 wichtigsten Saetze einer Meldung
                   (Frequenz-Ranking + Bonus fuer Zahlen/Prozente/Geldbetraege,
                   Reihenfolge bleibt erhalten, jeder Punkt kurz gekappt)
  - tags_for():    ordnet jeder Meldung 1-2 Themen-Chips zu (Fed/Zinsen,
                   Earnings, KI/Chips, ...), damit man in Sekunden sieht,
                   worum es geht und ob es einen betrifft

Bewusst ohne KI/Netz: rein extraktiv, deterministisch, offline-faehig.
"""
from __future__ import annotations
import re

# Kleine Stoppwortliste (EN + DE), reicht fuer Frequenz-Ranking
_STOP = set("""
the a an and or but of to in on for with at by from as is are was were be been
this that these those it its he she they we you his her their our your not no
will would can could may might has have had do does did more most other into
über der die das und oder aber von zu im in auf für mit bei aus als ist sind
war waren sein wird werden kann könnte nicht kein eine einer einem einen des
dem den auch nach vor um an es sich hat haben mehr sehr wie bereits laut nun
""".split())

# Themen-Chips: (Stichwoerter, Emoji, Label). Reihenfolge = Prioritaet.
_TAGS = [
    (("fed", "zins", "ezb", "interest rate", "rate cut", "rate hike", "powell",
      "lagarde", "notenbank", "central bank", "treasury yield"), "\U0001f3db\ufe0f", "Zinsen/Fed"),
    (("inflation", "cpi", "verbraucherpreis", "ppi"), "\U0001f4c8", "Inflation"),
    (("earnings", "quartalszahlen", "quarterly", "guidance", "revenue beat",
      "profit", "quartalsbericht", "eps"), "\U0001f4ca", "Earnings"),
    (("nvidia", " ai ", "artificial intelligence", "ki-", "chip", "semiconductor",
      "halbleiter", "openai", "datacenter", "data center"), "\U0001f916", "KI/Chips"),
    (("übernahme", "takeover", "merger", "acquisition", "acquire", "fusion",
      "buyout", "deal "), "\U0001f91d", "M&A/Deal"),
    (("oil", "öl", "gas", "opec", "energie", "energy", "uran", "crude"), "\u26a1", "Energie"),
    (("bitcoin", "crypto", "krypto", "ethereum"), "\u20bf", "Krypto"),
    (("tariff", "zoll", "zölle", "sanction", "sanktion", "handelskrieg",
      "trade war", "geopolit", "ukraine", "taiwan", "china "), "\U0001f30d", "Geo/Politik"),
    (("bank", "banken", "jpmorgan", "goldman", "deutsche bank"), "\U0001f3e6", "Banken"),
    (("auto", "tesla", "volkswagen", "ev ", "electric vehicle", "e-auto"), "\U0001f697", "Auto/EV"),
    (("dax", "s&p", "nasdaq", "dow", "nikkei", "aktienmarkt", "stocks", "wall street",
      "börse", "markets"), "\U0001f4c9", "Märkte"),
]


def tags_for(headline: str, summary: str = "", max_tags: int = 2) -> list:
    """-> Liste [(emoji, label)], maximal max_tags, Prioritaet nach _TAGS-Reihenfolge."""
    text = f" {headline or ''} {summary or ''} ".lower()
    out = []
    for kws, emoji, label in _TAGS:
        if any(k in text for k in kws):
            out.append((emoji, label))
            if len(out) >= max_tags:
                break
    return out


def _sentences(text: str) -> list:
    if not text:
        return []
    # grobe Satztrennung, robust gegen Abkuerzungen wie "U.S." / "z.B."
    parts = re.split(r"(?<![A-Z\u00c4\u00d6\u00dc])(?<!\bz\.B)(?<=[.!?])\s+(?=[A-Z\u00c4\u00d6\u00dc0-9\u201e\"])",
                     text.strip())
    return [p.strip() for p in parts if len(p.strip()) >= 25]


def _words(text: str) -> list:
    return [w for w in re.findall(r"[a-z\u00e4\u00f6\u00fc\u00df]{3,}", (text or "").lower())
            if w not in _STOP]


def key_points(headline: str, summary: str, max_points: int = 2,
               maxlen: int = 200) -> list:
    """Extrahiert die wichtigsten Saetze der Zusammenfassung.
    Ranking: Wort-Frequenz (inkl. Headline-Woerter doppelt) + Bonus fuer
    Zahlen/Prozente/Geldbetraege. Reihenfolge des Originals bleibt erhalten."""
    sents = _sentences(summary or "")
    if not sents:
        return []
    if len(sents) <= max_points:
        chosen = sents
    else:
        freq = {}
        for w in _words(summary):
            freq[w] = freq.get(w, 0) + 1
        for w in _words(headline):                    # Headline-Woerter zaehlen doppelt
            freq[w] = freq.get(w, 0) + 2
        scored = []
        for i, sent in enumerate(sents):
            ws = _words(sent)
            base = sum(freq.get(w, 0) for w in ws) / (len(ws) or 1)
            if re.search(r"\d+[.,]?\d*\s*(%|prozent|mrd|mio|billion|million|dollar|euro|\$|\u20ac)",
                         sent.lower()):
                base *= 1.35                          # Zahlen/Betraege = konkrete Info
            if i == 0:
                base *= 1.15                          # Lead-Satz leicht bevorzugen
            scored.append((base, i, sent))
        top = sorted(scored, key=lambda x: -x[0])[:max_points]
        chosen = [s for _b, _i, s in sorted(top, key=lambda x: x[1])]
    out = []
    for c in chosen:
        if len(c) > maxlen:
            c = c[:maxlen].rsplit(" ", 1)[0] + " \u2026"
        out.append(c)
    return out


def reading_secs(headline: str, summary: str) -> int:
    """Geschaetzte Lesezeit des Briefings in Sekunden (200 Woerter/Min)."""
    n = len((headline or "").split()) + sum(len(p.split())
                                            for p in key_points(headline, summary))
    return max(5, round(n / 200 * 60))


# ---------------------------------------------------------------------------
# News -> moegliche Markt-/Aktien-Implikationen (Denkanstoss, KEIN Anlagerat)
# ---------------------------------------------------------------------------
# (Stichwoerter, Wirkrichtung, betroffene Bereiche, Beispiel-Ticker)
_IMPLICATIONS = [
    (("heat", "heatwave", "hitze", "record temperature", "travel", "tourism", "reise",
      "urlaub", "vacation", "flight", "airline"), "up",
     "Reise/Tourismus/Airlines", ["booking", "airbnb", "delta", "lufthansa", "ryanair"]),
    (("rate cut", "zinssenkung", "senkt die zinsen", "dovish", "lockerung"), "up",
     "Wachstums-/Tech-Aktien, Immobilien (niedrigere Zinsen)", ["nasdaq", "reits"]),
    (("rate hike", "zinserh", "hawkish", "raises rates"), "down",
     "Wachstums-/Tech-Aktien tendenziell belastet; Banken-Zinsmarge steigt",
     ["banks"]),
    (("oil", "\u00f6l", "opec", "crude", "gas price", "energiepreis"), "up",
     "Energie/\u00d6lkonzerne; Fluggesellschaften/Logistik belastet",
     ["exxon", "shell", "totalenergies"]),
    (("chip", "semiconductor", "halbleiter", "ai demand", "datacenter", "data center"), "up",
     "Halbleiter/AI-Infrastruktur", ["nvidia", "amd", "asml", "tsmc"]),
    (("ev ", "electric vehicle", "e-auto", "battery", "lithium"), "up",
     "E-Mobilit\u00e4t/Batterie/Rohstoffe", ["tesla", "byd", "albemarle"]),
    (("defense spending", "military", "r\u00fcstung", "verteidigung", "nato", "missile",
      "warplane", "artillery", "munition"), "up",
     "R\u00fcstung/Verteidigung", ["rheinmetall", "lockheed", "rtx"]),
    (("drug", "fda approval", "medikament", "zulassung", "clinical trial", "pharma"), "up",
     "Pharma/Biotech (je nach Ausgang)", ["pfizer", "lilly", "novo nordisk"]),
    (("housing", "immobili", "mortgage", "bau", "construction"), "up",
     "Bau/Immobilien/Baustoffe", ["homebuilders"]),
    (("harvest", "drought", "crop", "ernte", "d\u00fcrre", "agriculture", "getreide"), "up",
     "Agrar/Lebensmittel/D\u00fcnger", ["adm", "nutrien", "bayer"]),
    (("cyber", "hack", "ransomware", "datenleck", "breach"), "up",
     "Cybersecurity", ["crowdstrike", "palo alto", "zscaler"]),
    (("tariff", "zoll", "z\u00f6lle", "trade war", "handelskrieg", "sanction", "sanktion"), "down",
     "Exportabh\u00e4ngige Industrie/Autobauer; Unsicherheit f\u00fcr breite M\u00e4rkte",
     ["automakers", "industrials"]),
    (("weak jobs", "layoffs", "arbeitslos", "rezession", "recession", "slowdown"), "down",
     "Zykliker/Konsum belastet; defensive Werte relativ st\u00e4rker",
     ["consumer discretionary"]),
    (("gold", "safe haven", "sichere hafen"), "up",
     "Gold/Minen (Krisen-Nachfrage)", ["barrick", "newmont"]),
    (("bitcoin", "crypto", "krypto", "ethereum"), "up",
     "Krypto-nahe Aktien/Miner", ["coinbase", "marathon"]),
]


def implications(headline: str, summary: str = "", max_items: int = 2) -> list:
    """Leitet aus einer Meldung moegliche Markt-Effekte ab (Denkanstoss).
    Rueckgabe: Liste [{dir:'up'/'down', area:str, tickers:[...]}].
    Bewusst simpel/heuristisch - ausdruecklich KEIN Anlagerat."""
    text = f" {headline or ''} {summary or ''} ".lower()
    out, seen = [], set()
    for kws, direction, area, tickers in _IMPLICATIONS:
        if any(k in text for k in kws) and area not in seen:
            seen.add(area)
            out.append({"dir": direction, "area": area, "tickers": tickers})
            if len(out) >= max_items:
                break
    return out
