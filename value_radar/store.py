"""
store.py — einfache lokale Persistenz fuer gespeicherte Portfolios.

Speichert in einer JSON-Datei im Home-Verzeichnis des Nutzers, sodass die
Portfolios Neustarts der App ueberleben. Jedes Portfolio ist eine Liste von
Positionen: {"ticker": str, "value": float, "date": "YYYY-MM-DD" | None}.
"""
from __future__ import annotations
import json
import os

PATH = os.path.join(os.path.expanduser("~"), ".value_radar_portfolios.json")


def _sheet():
    """Google-Sheets-Backend, falls konfiguriert & erreichbar, sonst None."""
    try:
        import gsheet
        return gsheet if gsheet.available() else None
    except Exception:
        return None


def backend() -> str:
    """'sheet' wenn Google Sheets aktiv ist, sonst 'file'."""
    return "sheet" if _sheet() is not None else "file"


def load_all() -> dict:
    g = _sheet()
    if g is not None:
        d = g.load_all()
        if d is not None:
            return d
    try:
        with open(PATH, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _write(d: dict) -> bool:
    g = _sheet()
    if g is not None:
        if g.save_all(d):
            return True
        # Sheets-Schreiben fehlgeschlagen -> zusaetzlich lokal sichern
    try:
        with open(PATH, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def save(name: str, records: list) -> bool:
    name = (name or "").strip()
    if not name:
        return False
    d = load_all()
    d[name] = records
    return _write(d)


def delete(name: str) -> bool:
    d = load_all()
    if name in d:
        d.pop(name, None)
        return _write(d)
    return False


def names() -> list:
    return sorted(load_all().keys())


def export_json() -> str:
    """Alle gespeicherten Portfolios als JSON-Text (fuer Download-Backup)."""
    return json.dumps(load_all(), ensure_ascii=False, indent=2)


def import_json(raw, merge: bool = True) -> int:
    """Portfolios aus einem Backup (JSON-Text/-Bytes/-dict) einlesen.
    merge=True fuegt zu vorhandenen hinzu (gleiche Namen werden ueberschrieben),
    merge=False ersetzt alles. Rueckgabe: Anzahl importierter Portfolios."""
    try:
        data = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
    except Exception:
        return 0
    if not isinstance(data, dict):
        return 0
    d = load_all() if merge else {}
    n = 0
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, list):
            d[k] = v
            n += 1
    _write(d)
    return n


# ---------------------------------------------------------------------------
# Watchlist + Aenderungs-Feed (fuer Nacht-Job "precompute" und Startseite).
# Liegen in der Zusatz-Ablage (Google-Sheet A2) bzw. lokal in einer Aux-Datei.
# ---------------------------------------------------------------------------
AUX_PATH = os.path.join(os.path.expanduser("~"), ".value_radar_aux.json")


def _load_aux() -> dict:
    g = _sheet()
    if g is not None:
        try:
            return g.load_aux() or {}
        except Exception:
            pass
    try:
        with open(AUX_PATH, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_aux(d: dict) -> bool:
    """WICHTIG: Ist das Google Sheet der aktive Speicher, wird auch von dort GELESEN.
    Schlaegt das Schreiben dorthin fehl, hilft die lokale Datei nicht - der Eintrag
    waere beim naechsten Laden weg. Deshalb wird in diesem Fall FALSE zurueckgegeben
    (frueher: True, weil die lokale Kopie 'geklappt' hat -> stiller Datenverlust)."""
    g = _sheet()
    if g is not None:
        ok = False
        try:
            ok = bool(g.save_aux(d))
        except Exception as e:
            print(f"[store] Google-Sheet-Fehler: {e}")
        if ok:
            return True
        print("[store] Google-Sheet-Speichern FEHLGESCHLAGEN. Daten wurden nur lokal "
              "gesichert und sind beim naechsten Laden nicht sichtbar!")
        try:                                  # trotzdem lokal sichern (Notkopie)
            with open(AUX_PATH, "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return False
    try:
        with open(AUX_PATH, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_watchlist() -> list:
    wl = _load_aux().get("watchlist", [])
    return wl if isinstance(wl, list) else []


def set_watchlist(tickers: list) -> bool:
    d = _load_aux()
    seen, clean = set(), []
    for t in tickers:
        t = str(t or "").strip().upper()
        if t and t not in seen:
            seen.add(t)
            clean.append(t)
    d["watchlist"] = clean
    return _save_aux(d)


def watchlist_add(ticker: str) -> bool:
    wl = get_watchlist()
    t = str(ticker or "").strip().upper()
    if t and t not in wl:
        wl.append(t)
    return set_watchlist(wl)


def watchlist_remove(ticker: str) -> bool:
    t = str(ticker or "").strip().upper()
    return set_watchlist([x for x in get_watchlist() if x != t])


def get_changes() -> list:
    """Aenderungs-Feed (vom Nacht-Job erzeugt) fuer die Startseite."""
    ch = _load_aux().get("changes", [])
    return ch if isinstance(ch, list) else []


def set_changes(items: list) -> bool:
    d = _load_aux()
    d["changes"] = items[:60]
    return _save_aux(d)


def get_snapshot() -> dict:
    """Letzter Berechnungs-Stand (fuer den Tagesvergleich im Nacht-Job)."""
    snap = _load_aux().get("snapshot", {})
    return snap if isinstance(snap, dict) else {}


def set_snapshot(snap: dict) -> bool:
    d = _load_aux()
    d["snapshot"] = snap
    d["snapshot_ts"] = __import__("time").time()
    return _save_aux(d)


def get_briefing() -> str:
    """KI-Nacht-Briefing (Text) fuer die Startseite."""
    b = _load_aux().get("briefing", "")
    return b if isinstance(b, str) else ""


def set_briefing(text: str) -> bool:
    d = _load_aux()
    d["briefing"] = (text or "")[:8000]
    d["briefing_ts"] = __import__("time").time()
    return _save_aux(d)


def get_hf() -> dict:
    """Fortlaufende Hedgefonds-Papier-Portfolios (je Strategie)."""
    d = _load_aux().get("hedgefund", {})
    return d if isinstance(d, dict) else {}


def set_hf(d: dict) -> bool:
    a = _load_aux()
    a["hedgefund"] = d
    return _save_aux(a)


def get_pf_log() -> list:
    """Manuelles Portfolio-Logbuch (Verkaeufe, Kaeufe, eigene Eintraege)."""
    lg = _load_aux().get("pf_log", [])
    return lg if isinstance(lg, list) else []


def set_pf_log(entries: list) -> bool:
    d = _load_aux()
    d["pf_log"] = (entries or [])[:250]
    return _save_aux(d)


def pf_log_add(entry: dict) -> bool:
    lg = get_pf_log()
    lg.insert(0, entry)
    return set_pf_log(lg)


def get_signals() -> list:
    """Signal-Tagebuch (Vorwaerts-Test der Scorecard/Radar-Signale)."""
    s = _load_aux().get("signals", [])
    return s if isinstance(s, list) else []


def set_signals(entries: list) -> bool:
    d = _load_aux()
    d["signals"] = (entries or [])[:250]
    return _save_aux(d)


def get_earnings() -> list:
    """Anstehende Quartalstermine samt Einordnung (vom Nacht-Job erzeugt).

    Bewusst vorberechnet: Ein Scan ueber den S&P 500 kostet mehrere hundert
    Abrufe - das ist im Browser nicht zumutbar und wuerde in Rate-Limits
    laufen."""
    e = _load_aux().get("earnings", [])
    return e if isinstance(e, list) else []


def set_earnings(items: list) -> bool:
    d = _load_aux()
    d["earnings"] = items[:80]
    return _save_aux(d)


def get_transkripte() -> list:
    """Neu erschienene Earnings Calls (vom Nacht-Job gefunden).

    Bewusst NUR die Kopfdaten - Ticker, Datum, Quartal. Die Volltexte
    (50.000+ Zeichen je Stueck) werden erst beim Oeffnen geholt; sie hier
    zu speichern waeren mehrere Megabyte, die niemand liest."""
    t = _load_aux().get("transkripte", [])
    return t if isinstance(t, list) else []


def set_transkripte(items: list) -> bool:
    d = _load_aux()
    d["transkripte"] = items[:200]
    return _save_aux(d)


def get_kommentar(name: str) -> str:
    """Eigener Notiz-/Kommentartext zu einem Portfolio (frei editierbar)."""
    komm = _load_aux().get("kommentare", {})
    if isinstance(komm, dict):
        return str(komm.get(name, "") or "")
    return ""


def set_kommentar(name: str, text: str) -> bool:
    d = _load_aux()
    komm = d.get("kommentare")
    if not isinstance(komm, dict):
        komm = {}
    komm[name] = (text or "")[:5000]      # Deckel gegen versehentliche Riesen
    d["kommentare"] = komm
    return _save_aux(d)


def get_pos_kommentare(portfolio: str) -> dict:
    """Kommentare je Position eines Portfolios: {ticker_or_raw: text}.

    Wird fuer die Kommentar-Spalte in der Positionstabelle gebraucht. Der
    Schluessel ist der (grossgeschriebene) Ticker/Eingabewert der Position."""
    alle = _load_aux().get("pos_kommentare", {})
    if isinstance(alle, dict):
        p = alle.get(portfolio, {})
        return p if isinstance(p, dict) else {}
    return {}


def set_pos_kommentare(portfolio: str, komm: dict) -> bool:
    """Speichert den kompletten Kommentar-Satz eines Portfolios auf einmal."""
    d = _load_aux()
    alle = d.get("pos_kommentare")
    if not isinstance(alle, dict):
        alle = {}
    # Nur nicht-leere Kommentare behalten, Laenge deckeln
    sauber = {str(k).upper(): str(v)[:2000]
              for k, v in (komm or {}).items() if str(v or "").strip()}
    alle[portfolio] = sauber
    d["pos_kommentare"] = alle
    return _save_aux(d)


def get_transkript_status() -> dict:
    """Diagnose-Status des letzten Transkript-Scans (fuer den Earnings-Tab)."""
    s = _load_aux().get("transkript_status", {})
    return s if isinstance(s, dict) else {}


def set_transkript_status(status: dict) -> bool:
    d = _load_aux()
    d["transkript_status"] = status or {}
    return _save_aux(d)
