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


def diagnose() -> str:
    """Gibt im Klartext zurueck, WARUM Google Sheets (nicht) funktioniert.
    Macht echte Aufrufe -> nur auf Knopfdruck verwenden, nicht bei jedem Rerun."""
    try:
        import streamlit as st
    except Exception as e:
        return f"Streamlit nicht verf\u00fcgbar: {e}"
    try:
        creds = st.secrets.get("gcp_service_account")
    except Exception:
        creds = None
    try:
        sid = st.secrets.get("GSHEET_ID")
    except Exception:
        sid = None
    if not creds:
        return ("Der Secrets-Block [gcp_service_account] fehlt (oder ist leer). "
                "In den Secrets muss die Zeile [gcp_service_account] \u00fcber "
                "type = \"service_account\" stehen.")
    if not sid:
        return "GSHEET_ID fehlt in den Secrets."
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except Exception as e:
        return f"Google-Pakete nicht installiert (requirements.txt?): {e}"
    try:
        c = Credentials.from_service_account_info(dict(creds), scopes=_SCOPES)
    except Exception as e:
        return ("Zugangsdaten ung\u00fcltig \u2013 meist ist der private_key nicht "
                f"vollst\u00e4ndig/korrekt kopiert. Details: {e}")
    try:
        gc = gspread.authorize(c)
    except Exception as e:
        return f"Authentifizierung fehlgeschlagen: {e}"
    try:
        sh = gc.open_by_key(str(sid))
    except Exception as e:
        return ("Sheet nicht erreichbar. Pr\u00fcfe: (1) Google-Sheets-API im Projekt "
                "aktiviert? (2) Sheet mit der client_email als Bearbeiter geteilt? "
                "(3) GSHEET_ID korrekt? "
                f"Details: {e}")
    try:
        sh.sheet1.acell("A1").value
        return "OK"
    except Exception as e:
        return f"Zugriff auf Tabellenblatt 1 fehlgeschlagen: {e}"
