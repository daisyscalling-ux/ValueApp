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
import os

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_WS = "unset"          # Cache: "unset" | None | worksheet-Objekt


def _creds_and_id():
    """Zugangsdaten + Sheet-ID beschaffen. Funktioniert BEIDES:
    - in Streamlit ueber st.secrets
    - standalone (Cron/GitHub-Actions) ueber Umgebungsvariablen:
        GSHEET_ID  und  GCP_SERVICE_ACCOUNT (kompletter JSON-String)
        oder GOOGLE_APPLICATION_CREDENTIALS (Pfad zur JSON-Datei)."""
    creds_info, sheet_id = None, None
    # 1) Streamlit-Secrets (App-Kontext)
    try:
        import streamlit as st
        try:
            creds_info = st.secrets.get("gcp_service_account")
            sheet_id = st.secrets.get("GSHEET_ID")
        except Exception:
            pass
    except Exception:
        pass
    # 2) Umgebungsvariablen (Standalone/Cron)
    if not sheet_id:
        sheet_id = os.getenv("GSHEET_ID")
    if not creds_info:
        raw = os.getenv("GCP_SERVICE_ACCOUNT")
        if raw:
            try:
                creds_info = json.loads(raw)
            except Exception:
                creds_info = None
    if not creds_info:
        path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    creds_info = json.load(fh)
            except Exception:
                creds_info = None
    return creds_info, sheet_id


def _worksheet():
    """Gibt das Worksheet zurueck oder None. Prozessweit gecacht."""
    global _WS
    if _WS != "unset":
        return _WS
    _WS = None
    try:
        creds_info, sheet_id = _creds_and_id()
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


# --- Zusatz-Ablage (Watchlist, Snapshot, Aenderungs-Feed) in Zelle A2 ---------
# Portfolios bleiben unveraendert in A1; alles Weitere liegt als EIN JSON in A2.
# Google Sheets erlaubt max. 50.000 Zeichen JE ZELLE. Die Zusatzdaten (Hedgefonds-
# Historie, Snapshot, Logbuch, Signale) sprengen das schnell -> das Speichern schlug
# lautlos fehl und ALLES war weg. Deshalb: JSON auf mehrere Zellen aufteilen.
_AUX_CHUNK = 45000
_AUX_ROWS = 30                      # A2..A31 -> bis ~1,35 Mio Zeichen


def load_aux() -> dict:
    ws = _worksheet()
    if ws is None:
        return {}
    try:
        cells = ws.get(f"A2:A{1 + _AUX_ROWS}") or []
        parts = [(row[0] if row else "") for row in cells]
        raw = "".join(p for p in parts if p)
        if not raw:
            return {}
        d = json.loads(raw)
        return d if isinstance(d, dict) else {}
    except Exception as e:
        print(f"[gsheet] load_aux fehlgeschlagen: {e}")
        return {}


def save_aux(d: dict) -> bool:
    ws = _worksheet()
    if ws is None:
        return False
    try:
        raw = json.dumps(d, ensure_ascii=False)
        chunks = [raw[i:i + _AUX_CHUNK] for i in range(0, len(raw), _AUX_CHUNK)]
        if len(chunks) > _AUX_ROWS:
            print(f"[gsheet] AUX zu gross: {len(raw)} Zeichen "
                  f"({len(chunks)} Bloecke, max {_AUX_ROWS}) - wird gekuerzt gespeichert!")
            return False
        # freie Zeilen mit leeren Werten ueberschreiben (sonst bleiben Reste stehen)
        values = [[c] for c in chunks] + [[""]] * (_AUX_ROWS - len(chunks))
        ws.update(range_name=f"A2:A{1 + _AUX_ROWS}", values=values)
        return True
    except Exception as e:
        print(f"[gsheet] save_aux fehlgeschlagen: {e}")
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
