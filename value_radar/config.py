"""
auth.py — einfaches, robustes Passwort-Gate fuer die Streamlit-App.

Das Passwort steht NICHT im Code, sondern in den Streamlit-Secrets
(.streamlit/secrets.toml lokal bzw. "Secrets" in Streamlit Cloud):

    APP_PASSWORD = "dein-langes-passwort"

Ablauf:
  - Ist kein Passwort gesetzt (lokal, ohne Secret), laeuft die App ungeschuetzt
    weiter  -> so blockiert das Gate die lokale Entwicklung nicht.
  - Ist ein Passwort gesetzt, erscheint ein Login, bis es korrekt eingegeben
    wurde. Danach bleibt man fuer die Session eingeloggt.

Biometrie: Das Feld heisst "password" (type=password), damit iCloud-
Schluesselbund / Google-Passwortmanager / Bitwarden es erkennen und per
Fingerabdruck/FaceID automatisch ausfuellen koennen.
"""
from __future__ import annotations
import hmac
import time
import streamlit as st


def _configured_password():
    """Passwort aus Secrets holen; None, wenn nicht gesetzt."""
    try:
        pw = st.secrets.get("APP_PASSWORD")
    except Exception:
        pw = None
    return pw or None


def require_login():
    """Zeigt das Login-Gate. Gibt True zurueck, wenn Zugriff erlaubt ist,
    sonst stoppt es die Ausfuehrung (st.stop())."""
    expected = _configured_password()

    # Kein Passwort konfiguriert -> App laeuft offen (z.B. lokal)
    if expected is None:
        return True

    if st.session_state.get("auth_ok"):
        return True

    st.markdown(
        '<div style="max-width:420px;margin:8vh auto 0;text-align:center">'
        '<div style="font-size:30px;font-weight:800;color:var(--amber);'
        'letter-spacing:1px">VALUE RADAR</div>'
        '<div style="color:var(--muted);margin:6px 0 18px">Gesch\u00fctzter Bereich '
        '\u2013 bitte anmelden</div></div>',
        unsafe_allow_html=True)

    c = st.columns([1, 2, 1])
    with c[1]:
        # Kleine Sperre gegen Brute-Force: nach Fehlversuchen kurz warten
        locked_until = st.session_state.get("auth_locked_until", 0)
        wait = int(locked_until - time.time())
        if wait > 0:
            st.error(f"Zu viele Fehlversuche. Bitte {wait}s warten.")
            st.stop()

        with st.form("login_form", clear_on_submit=False):
            pw = st.text_input("Passwort", type="password", key="password",
                               help="Im Passwortmanager speichern \u2013 dann per "
                                    "Fingerabdruck/FaceID automatisch ausf\u00fcllen.")
            ok = st.form_submit_button("Anmelden", use_container_width=True)

        if ok:
            if hmac.compare_digest(str(pw), str(expected)):
                st.session_state["auth_ok"] = True
                st.session_state.pop("auth_fails", None)
                st.session_state.pop("password", None)   # Passwort nicht im State halten
                st.rerun()
            else:
                fails = st.session_state.get("auth_fails", 0) + 1
                st.session_state["auth_fails"] = fails
                if fails >= 5:
                    st.session_state["auth_locked_until"] = time.time() + 30
                    st.session_state["auth_fails"] = 0
                st.error("Falsches Passwort.")
        st.caption("Tipp: Passwort einmal im Browser/Passwortmanager speichern, "
                   "dann geht die Anmeldung per Biometrie.")
    st.stop()
