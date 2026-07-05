"""
gsheet_store.py — dauerhafte Portfolio-Speicherung in Google Sheets.

Warum: Die Streamlit Cloud hat ein fluechtiges Dateisystem (Reboot loescht die
lokale JSON-Datei). Ein Google Sheet liegt ausserhalb und ueberlebt Reboots.

Ablauf/Setup (siehe GOOGLE_SHEETS_SETUP.md):
  - Google-Service-Account anlegen, Sheets-API aktivieren
  - Das Ziel-Sheet mit der Service-Account-E-Mail teilen (Bearbeiter)
  - In den Streamlit-Secrets hinterlegen:
        GSHEET_ID = "<Sheet-ID aus der URL>"
        [gcp_service_account]
        ... (Inhalt der Service-Account-JSON) ...

Speicherformat: das gesamte Portfolio-Dict wird als JSON in Zelle A1 eines
Arbeitsblatts "portfolios" abgelegt (einfach, robust, weit unter dem Zell-Limit).

Alles ist defensiv: Ist nichts/fehlerhaft konfiguriert, liefert available()
False und die App nutzt den lokalen Datei-Speicher (store.py). Kein Absturz.
"""
from __future__ import annotations
import json

# leichter Prozess-Cache, um Google-API-Aufrufe (Quota) zu sparen
_CACHE = {"data": None, "loaded": False}


def _secrets():
    try:
        import streamlit as st
        sa = st.secrets.get("gcp_service_account")
        sheet_id = st.secrets.get("GSHEET_ID") or st.secrets.get("gsheet_id")
        # st.secrets-Objekte in echte dicts wandeln
        if sa is not None:
            sa = dict(sa)
        return sa, sheet_id
    except Exception:
        return None, None


def available() -> bool:
    """True, wenn Sheets nutzbar konfiguriert ist (Secrets + Bibliothek)."""
    sa, sheet_id = _secrets()
    if not sa or not sheet_id:
        return False
    try:
        import gspread  # noqa: F401
        from google.oauth2.service_account import Credentials  # noqa: F401
        return True
    except Exception:
        return False


def _ws():
    """Arbeitsblatt-Handle (mit einfachem Modul-Cache)."""
    if _CACHE.get("_ws") is not None:
        return _CACHE["_ws"]
    import gspread
    from google.oauth2.service_account import Credentials
    sa, sheet_id = _secrets()
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(sa, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet("portfolios")
    except Exception:
        ws = sh.add_worksheet(title="portfolios", rows=10, cols=2)
    _CACHE["_ws"] = ws
    return ws


def refresh():
    """Cache leeren (erzwingt frisches Laden aus dem Sheet)."""
    _CACHE["data"] = None
    _CACHE["loaded"] = False


def load_all() -> dict:
    if _CACHE["loaded"] and _CACHE["data"] is not None:
        return _CACHE["data"]
    try:
        ws = _ws()
        raw = ws.acell("A1").value
        d = json.loads(raw) if raw else {}
        if not isinstance(d, dict):
            d = {}
    except Exception:
        d = {}
    _CACHE["data"] = d
    _CACHE["loaded"] = True
    return d


def _write(d: dict) -> bool:
    try:
        ws = _ws()
        ws.update_acell("A1", json.dumps(d, ensure_ascii=False))
        _CACHE["data"] = d
        _CACHE["loaded"] = True
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
    return json.dumps(load_all(), ensure_ascii=False, indent=2)


def import_json(raw, merge: bool = True) -> int:
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
