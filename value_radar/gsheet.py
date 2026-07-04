"""
gsheet.py — optionaler Google-Sheets-Speicher fuer Portfolios.

Damit ueberleben gespeicherte Portfolios auch Reboots der Streamlit-Cloud
(das dortige Dateisystem ist fluechtig). Die Portfolios werden als EIN JSON-Text
in Zelle A1 eines Google Sheets abgelegt (einfach, robust, ein Nutzer).

Aktiv NUR, wenn in den Streamlit-Secrets beides gesetzt ist:
    [gcp_service_account]        # der komplette Service-Account-JSON-Inhalt
    ...
    GSHEET_ID = "<Sheet-ID aus der URL>"

Ist das nicht gesetzt oder tritt ein Fehler auf, meldet available() = False,
und store.py nutzt automatisch den lokalen Datei-Speicher. Nichts crasht.
"""
from __future__ import annotations
import json

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_WS = "unset"          # Cache: "unset" | None | worksheet-Objekt


def _worksheet():
    """Gibt das Worksheet zurueck oder None. Ergebnis wird prozessweit gecacht,
    damit nicht bei jedem Rerun neu authentifiziert wird."""
    global _WS
    if _WS != "unset":
        return _WS
    _WS = None
    try:
        import streamlit as st
        creds_info = None
        sheet_id = None
        try:
            creds_info = st.secrets.get("gcp_service_account")
            sheet_id = st.secrets.get("GSHEET_ID")
        except Exception:
            return None
        if not creds_info or not sheet_id:
            return None
        import gspread
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_info(dict(creds_info), scopes=_SCOPES)
        gc = gspread.authorize(creds)
        _WS = gc.open_by_key(str(sheet_id)).sheet1
    except Exception:
        _WS = None
    return _WS


def available() -> bool:
    try:
        return _worksheet() is not None
    except Exception:
        return False


def load_all():
    """Alle Portfolios als dict, oder None wenn Sheets nicht verfuegbar."""
    ws = _worksheet()
    if ws is None:
        return None
    try:
        raw = ws.acell("A1").value
        if not raw:
            return {}
        d = json.loads(raw)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_all(d: dict) -> bool:
    ws = _worksheet()
    if ws is None:
        return False
    try:
        ws.update_acell("A1", json.dumps(d, ensure_ascii=False))
        return True
    except Exception:
        return False


def reset_cache():
    global _WS
    _WS = "unset"
