#!/usr/bin/env python3
"""
dashboard.py — Web-Oberflaeche fuer das Value-Radar (Terminal-Look).

Start:  streamlit run dashboard.py        Browser: http://localhost:8501

  - Einzelanalyse: Chart-Zeitraeume (Intraday/1W/1M/6M/12M/5J), rebasiert auf 0%
  - Screener: marktweit (gegen "alles"), mit Filtern; Spalten Name/Ticker/Preis/
    6M/1J/YTD/Land/Sektor/Analyst (B/H/S)/Score
  - Alle Geldbetraege in EUR
"""
from __future__ import annotations
import time
import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

import providers
import scoring
import screener_presets as sp
import valuation
import intel as intel_mod
import market_screener as ms
import matrices as mx
import scorecard as sc
import portfolio as pf
import store
import these as these_mod
import radar as radar
import marketnews as mn
import briefing as bfg
import translate as tr
import config
import auth

st.set_page_config(page_title="VALUE RADAR", page_icon="\u25e2",
                   layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&display=swap');
:root{--bg:#0A0E14;--panel:#121821;--line:#1F2733;--fg:#E6E1D3;
  --muted:#6B7686;--amber:#FFB000;--green:#3FB950;--red:#F85149;}
.stApp{background:var(--bg);}
/* Beim Tab-Wechsel laeuft das Skript neu. Streamlit laesst den ALTEN Frame
   abgedunkelt stehen, bis der neue fertig ist - dadurch sah man kurz die
   Inhalte des vorherigen Tabs. Veraltete Bloecke werden jetzt AUSGEBLENDET
   statt abgedunkelt: lieber kurz Leerraum als fremder Inhalt.
   Streamlit markiert veraltete Elemente mit [data-stale="true"]. */
[data-stale="true"]{opacity:0 !important; transition:none !important;}
.element-container[data-stale="true"]{display:none !important;}
/* Aeltere/neuere Streamlit-Versionen benennen das Attribut unterschiedlich -
   beide Schreibweisen abdecken, damit es versionsunabhaengig greift. */
.stApp [class*="stale"]{opacity:0 !important;}
div[data-testid="stVerticalBlock"] > div[data-stale="true"]{display:none !important;}
/* Dezenter Ladebalken oben, solange das Skript laeuft - fuellt die kurze
   Leere beim Tab-Wechsel, ohne fremden Inhalt zu zeigen. Streamlit setzt
   [data-test-script-state="running"] am App-Container. */
[data-test-script-state="running"]::before,
[data-testid="stApp"][data-test-script-state="running"]::before{
  content:""; position:fixed; top:0; left:0; right:0; height:2px; z-index:9999;
  background:linear-gradient(90deg,transparent,var(--amber),transparent);
  background-size:50% 100%; animation:vrload 1s linear infinite;}
@keyframes vrload{0%{background-position:-50% 0;}100%{background-position:150% 0;}}
html,body,[class*="css"]{font-family:'JetBrains Mono',ui-monospace,monospace;}
.vr-head{border:1px solid var(--line);border-left:3px solid var(--amber);
  background:var(--panel);padding:14px 18px;margin-bottom:18px;}
.vr-head .logorow{display:flex;align-items:center;gap:12px;}
.vr-head .logorow img{height:38px;width:auto;display:block;}
.vr-head .brand{color:var(--amber);font-weight:800;letter-spacing:3px;font-size:20px;}
.vr-head .brand .caret{animation:blink 1.1s steps(1) infinite;}
@keyframes blink{50%{opacity:0;}}
.vr-head .status{color:var(--muted);font-size:12px;margin-top:2px;}
.vr-card{border:1px solid var(--line);background:var(--panel);padding:14px 16px;
  height:100%;min-height:104px;display:flex;flex-direction:column;justify-content:center;}
.vr-card .k{color:var(--muted);font-size:11px;letter-spacing:1.5px;text-transform:uppercase;}
.vr-card .v{font-size:24px;font-weight:700;margin-top:4px;}
.vr-card .sub{font-size:12px;color:var(--muted);margin-top:2px;min-height:16px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.row{display:flex;align-items:center;gap:12px;margin:7px 0;}
.row .lbl{width:130px;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:1px;}
.row .track{flex:1;height:14px;background:#0d1219;border:1px solid var(--line);position:relative;}
.row .fill{height:100%;}
.row .val{width:42px;text-align:right;font-weight:700;}
.sec-title{color:var(--amber);font-weight:700;letter-spacing:2px;border-bottom:1px solid var(--line);
  padding-bottom:6px;margin:6px 0 12px;font-size:13px;}
.pill{display:inline-block;border:1px solid var(--line);padding:2px 9px;margin:3px;
  font-size:12px;color:var(--fg);background:#0d1219;}
.news a{color:var(--fg);text-decoration:none;border-bottom:1px dotted var(--muted);}
.news a:hover{color:var(--amber);}
.news-box{border:1px solid var(--line);background:#0d1219;padding:10px 12px;margin:8px 0;
  border-left:2px solid var(--amber);}
.news-box a{color:var(--fg);text-decoration:none;font-weight:500;line-height:1.35;}
.news-box a:hover{color:var(--amber);}
.news-box .meta{color:var(--muted);font-size:11px;margin-top:6px;letter-spacing:.5px;
  text-transform:uppercase;}
.news-box .sum{color:var(--fg);opacity:.82;font-size:12.5px;margin-top:6px;
  line-height:1.45;font-weight:400;}
.na{color:var(--muted);font-style:italic;}
.px-big{font-size:34px;font-weight:800;}
.px-chg{font-size:15px;font-weight:700;margin-top:2px;}
hr{border-color:var(--line);}
/* Navigation als Boxen: linksbuendig, ganze Zeile klickbar */
/* ---- NAVIGATION: alle drei Button-Typen (navtop/navsub/navgrp) EXPLIZIT
   ansprechen, damit Hintergrund UND Linksbuendigkeit ueberall greifen.
   (Die generische Sidebar-Regel erfasste die Ueberpunkt-Boxen nicht.) ---- */
div[class*="st-key-navtop_"] .stButton>button,
div[class*="st-key-navsub_"] .stButton>button,
div[class*="st-key-navgrp_"] .stButton>button,
section[data-testid="stSidebar"] .stButton>button{
  text-align:left !important; justify-content:flex-start !important;
  border-radius:8px; border:1px solid rgba(255,255,255,.18);
  padding:10px 12px 10px 16px; margin:2px 0; min-height:46px;
  font-weight:600; letter-spacing:.3px;
  background:rgba(255,255,255,.10) !important;}
/* Linksbuendigkeit ROBUST: Button, alle Kinder, p und div. width:100% am
   p/div, sonst zentriert der Flex-Container das schmale Textelement. */
div[class*="st-key-navtop_"] .stButton>button *,
div[class*="st-key-navsub_"] .stButton>button *,
div[class*="st-key-navgrp_"] .stButton>button *,
section[data-testid="stSidebar"] .stButton>button *{
  text-align:left !important;}
div[class*="st-key-navtop_"] .stButton>button p,
div[class*="st-key-navsub_"] .stButton>button p,
div[class*="st-key-navgrp_"] .stButton>button p,
div[class*="st-key-navtop_"] .stButton>button div,
div[class*="st-key-navsub_"] .stButton>button div,
div[class*="st-key-navgrp_"] .stButton>button div,
section[data-testid="stSidebar"] .stButton>button p,
section[data-testid="stSidebar"] .stButton>button div{
  text-align:left !important; margin:0 !important; width:100% !important;
  justify-content:flex-start !important;}
div[class*="st-key-navtop_"] .stButton>button:hover,
div[class*="st-key-navsub_"] .stButton>button:hover,
div[class*="st-key-navgrp_"] .stButton>button:hover,
section[data-testid="stSidebar"] .stButton>button:hover{
  border-color:var(--amber); color:var(--amber);
  background:rgba(255,255,255,.16) !important;}
/* Aktiver (primary) Nav-Button: kraeftiges Amber */
div[class*="st-key-navtop_"] .stButton>button[kind="primary"],
div[class*="st-key-navgrp_"] .stButton>button[kind="primary"],
section[data-testid="stSidebar"] .stButton>button[kind="primary"]{
  background:var(--amber) !important; border-color:var(--amber);}
/* Der Button-Text steht (laut DOM) in einem div.stMarkdownContainer, NICHT
   in einem <p>. Diesen sowie einen evtl. Tooltip-Flex-Wrapper links
   ausrichten - sonst zentriert Streamlit die Ueberpunkte. */
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
div[class*="st-key-navgrp_"] [data-testid="stMarkdownContainer"],
div[class*="st-key-navtop_"] [data-testid="stMarkdownContainer"],
div[class*="st-key-navsub_"] [data-testid="stMarkdownContainer"]{
  text-align:left !important; width:100% !important;}
section[data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"],
div[class*="st-key-navgrp_"] [data-testid="stTooltipHoverTarget"]{
  justify-content:flex-start !important; width:100% !important;}
/* Ueberpunkte (mit Pfeil): kraeftiger, Pfeil etwas groesser */
div[class*="st-key-navgrp_"] .stButton>button p{ font-weight:800 !important; font-size:15px; }
/* Unterpunkte: leicht eingerueckt */
div[class*="st-key-navsub_"] .stButton>button p{ padding-left:22px; }
/* Klickbare Ticker-Buttons in Ergebnislisten (Screener/Radar/Peers) */
.tickcell .stButton>button{
  font-weight:800; color:var(--amber); background:transparent;
  border:1px solid var(--line); border-radius:6px; padding:4px 8px;
  width:100%; text-align:left;}
.tickcell .stButton>button:hover{border-color:var(--amber);
  background:rgba(255,176,0,.08);}
.rowline{border-bottom:1px solid var(--line); padding:2px 0;}
/* ---- Mobile Top-Icon-Navigation (nur Handys). Verankert an den BUTTON-Keys
   (st-key-mnav_*), die Streamlit versionsunabhaengig als CSS-Klassen setzt -
   unabhaengig davon, wo die Container-Klasse landet. ---- */
div[class*="st-key-mnav_"]{display:none;}          /* Desktop: Nav-Buttons aus */
@media (max-width: 820px){
  html, body{overflow-x:hidden;}                    /* nur Seite, NICHT die Container */
  section[data-testid="stSidebar"]{display:none !important;}
  [data-testid="stSidebarCollapsedControl"],
  [data-testid="collapsedControl"],
  [data-testid="stSidebarCollapseButton"]{display:none !important;}
  header[data-testid="stHeader"]{height:0 !important; min-height:0 !important;}
  /* Bekannter, kleiner Seitenabstand des Hauptcontainers -> die Nav zieht sich
     per negativem Rand exakt um diesen Betrag nach aussen = echt Rand zu Rand. */
  section[data-testid="stMain"] .block-container,
  section.main .block-container{
    padding-left:12px !important; padding-right:12px !important;
    padding-top:6px !important; max-width:100% !important;}

  div[class*="st-key-mnav_"]{display:block; min-width:0 !important;}
  div[data-testid="stVerticalBlock"]:has(> div[class*="st-key-mnav_"]),
  .st-key-mobilenav [data-testid="stVerticalBlock"]:has(div[class*="st-key-mnav_"]){
    display:grid !important; grid-template-columns:repeat(4, 1fr) !important;
    gap:3px !important;
    margin-left:-12px !important; margin-right:-12px !important; margin-bottom:8px;
    background:rgba(10,14,20,.98);
    border-bottom:2px solid var(--amber); padding:4px 3px;}  /* = Rand zu Rand */
  div[class*="st-key-mnav_"] .stButton{width:100% !important;}
  div[class*="st-key-mnav_"] .stButton>button{
    width:100% !important; min-height:0; padding:8px 0 6px 0;
    border:1px solid var(--line); border-radius:7px; box-shadow:none;
    background:rgba(255,255,255,.03); color:var(--muted); overflow:hidden;
    font-size:20px; line-height:1.05; white-space:nowrap;}
  div[class*="st-key-mnav_"] .stButton>button p{font-size:20px; margin:0; line-height:1.05;}
  div[class*="st-key-mnav_"] .stButton>button[kind="primary"]{
    background:var(--amber); border-color:var(--amber);}
}
/* ---- Klickbare Listen (vr-rows): Ticker = Link ---- */
div[class*="st-key-tkbtn_"] .stButton>button,
div[class*="st-key-tkbtn_"] button{
  background:transparent !important; border:none !important; box-shadow:none !important;
  color:var(--amber) !important; font-weight:800; padding:2px 0 !important;
  min-height:0 !important; font-size:13px; text-align:left; letter-spacing:.5px;
  width:100%;}
div[class*="st-key-tkbtn_"] button:hover{text-decoration:underline;}
.vr-lg{display:grid; gap:0 10px; align-items:center; font-size:12.5px;
  white-space:nowrap; overflow:hidden; padding:5px 0;}
.vr-lg>div{overflow:hidden; text-overflow:ellipsis; min-width:0;}
.vr-lg .num{text-align:right; font-variant-numeric:tabular-nums;}
.vr-th{color:var(--muted); text-transform:uppercase; font-size:10.5px;
  letter-spacing:1px; font-weight:700; padding:4px 0;}
/* ---- Professionelle eigene Tabellen (vr-table): dunkel, unabhaengig vom Theme ---- */
.vr-twrap{border:1px solid var(--line); background:var(--panel);
  border-radius:6px; overflow-x:auto; margin:2px 0 6px 0;}
table.vr-table{width:100%; border-collapse:collapse; font-family:inherit;
  font-size:12.5px; color:var(--fg); min-width:520px;}
table.vr-table th{position:sticky; top:0; background:#121821; color:var(--muted);
  text-transform:uppercase; letter-spacing:1px; font-size:10.5px; font-weight:700;
  text-align:left; padding:9px 12px; border-bottom:1px solid var(--line);
  white-space:nowrap;}
table.vr-table td{padding:8px 12px; border-bottom:1px solid rgba(31,39,51,.55);
  white-space:nowrap;}
table.vr-table tr:last-child td{border-bottom:none;}
table.vr-table tbody tr:hover{background:rgba(255,176,0,.05);}
table.vr-table td.num, table.vr-table th.num{text-align:right;
  font-variant-numeric:tabular-nums;}
table.vr-table .tick{color:var(--amber);font-weight:800;}
/* Ansicht-Umschalter (Strategien/Logbuch) soll wie Tabs aussehen */
div[role="radiogroup"]:has(input[aria-label*="Logbuch"]){gap:0 !important;
  border-bottom:1px solid var(--line);margin-bottom:10px;}
div[role="radiogroup"]:has(input[aria-label*="Logbuch"]) label{
  padding:6px 16px !important;margin:0 !important;border-bottom:2px solid transparent;
  font-weight:700;letter-spacing:.04em;}
div[role="radiogroup"]:has(input[aria-label*="Logbuch"]) label:has(input:checked){
  color:var(--amber) !important;border-bottom:2px solid var(--amber);}
div[role="radiogroup"]:has(input[aria-label*="Logbuch"]) label > div:first-child{
  display:none !important;}
table.vr-table .sellbtn{display:inline-block;width:20px;height:20px;line-height:18px;
  text-align:center;border:1px solid #F85149;border-radius:3px;color:#F85149;
  font-size:11px;font-weight:700;text-decoration:none;background:rgba(248,81,73,.08);}
table.vr-table .sellbtn:hover{background:#F85149;color:#0A0E14;}
table.vr-table .vr-link{cursor:pointer;}
table.vr-table .vr-link:hover{text-decoration:underline;}
/* unsichtbare Ziel-Buttons fuer klickbare Ticker (per JS ausgeloest) */
div[class*="st-key-hb_"]{display:none !important;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Zugriffsschutz: nur mit korrektem Passwort (aus Secrets). Ohne gesetztes
# Passwort (z.B. lokal) laeuft die App normal weiter.
auth.require_login()


# ===========================================================================
# ZUGANGSSCHUTZ — Passwort-Gate (Passwort liegt in st.secrets, NICHT im Code)
# ===========================================================================
def _check_password() -> bool:
    """Zeigt einen Login-Screen, wenn in den Secrets ein 'APP_PASSWORD' gesetzt ist.
    Ohne gesetztes Passwort (z.B. lokal) laeuft die App offen \u2013 localhost ist
    ohnehin nur fuer dich erreichbar. Das Passwort wird NIE im Klartext im Code
    oder in der Session gespeichert (nur ein 'authentifiziert'-Flag)."""
    import hmac
    try:
        configured = str(st.secrets.get("APP_PASSWORD", "") or "")
    except Exception:
        configured = ""
    if not configured:
        return True                       # kein Passwort gesetzt -> offen (lokal)
    if st.session_state.get("_authed"):
        return True

    st.markdown('<div class="vr-head"><div class="brand">VALUE RADAR '
                '<span class="caret">\u25ae</span></div>'
                '<div class="status">\U0001f512 Gesch\u00fctzter Zugang \u2013 bitte anmelden'
                '</div></div>', unsafe_allow_html=True)
    with st.form("login_form"):
        pw = st.text_input("Passwort", type="password",
                           help="Im Passwortmanager speichern \u2013 dann per "
                                "Fingerabdruck/FaceID automatisch ausf\u00fcllen.")
        submitted = st.form_submit_button("Anmelden")
    if submitted:
        if hmac.compare_digest(pw, configured):
            st.session_state["_authed"] = True
            st.rerun()
        else:
            st.error("Falsches Passwort.")
    st.caption("Tipp: Speichere das Passwort in deinem Passwortmanager "
               "(iCloud-Schl\u00fcsselbund, Google, Bitwarden \u2026). Der entsperrt sich "
               "per Fingerabdruck/FaceID und f\u00fcllt das Feld automatisch aus.")
    return False


if not _check_password():
    st.stop()


TIMEFRAMES = {
    "Intraday": ("1d", "5m"), "1 Woche": ("5d", "30m"), "1 Monat": ("1mo", "1d"),
    "6 Monate": ("6mo", "1d"), "12 Monate": ("1y", "1d"), "5 Jahre": ("5y", "1wk"),
}


def score_color(v):
    if v is None:
        return "var(--muted)"
    return "var(--green)" if v >= 66 else ("var(--amber)" if v >= 40 else "var(--red)")


def score_hex(v):
    """Konkrete Hex-Farbe fuer st.dataframe-Zellen (CSS-Variablen wirken dort nicht)."""
    try:
        v = float(v)
    except Exception:
        return "#6B7686"
    return "#3FB950" if v >= 66 else ("#FFB000" if v >= 40 else "#F85149")


def de(x, dec=2):
    """Deutsche Zahlenformatierung: 1.234,56"""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "\u00a7").replace(".", ",").replace("\u00a7", ".")


def sym_eur(x):
    return "\u2014" if x is None else f"\u20ac{de(x, 2)}"


def parse_eur(s):
    """Akzeptiert deutsche UND englische Geldformate und behandelt Punkte/Kommas
    geldgerecht: '1.500,50'->1500.5, '2.000'->2000, '2,5'->2.5, '1,500.50'->1500.5."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip().replace(" ", "").replace("\u20ac", "")
    if not t:
        return None
    has_c, has_d = "," in t, "." in t
    if has_c and has_d:
        if t.rfind(",") > t.rfind("."):          # Komma ist Dezimaltrenner
            t = t.replace(".", "").replace(",", ".")
        else:                                     # Punkt ist Dezimaltrenner
            t = t.replace(",", "")
    elif has_c:
        after = t.split(",")[-1]
        t = t.replace(",", "") if (t.count(",") > 1 or len(after) == 3) else t.replace(",", ".")
    elif has_d:
        after = t.split(".")[-1]
        if t.count(".") > 1 or len(after) == 3:   # Tausendertrennzeichen
            t = t.replace(".", "")
    try:
        return float(t)
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_fundamentals(t): return providers.get_fundamentals(t)


# Manueller Cache fuer tiefe Fundamentaldaten: {ticker: (zeit, daten)}. Anders
# als st.cache_data speichert er UNVOLLSTAENDIGE roic-Ergebnisse nur ganz kurz
# (60 s), vollstaendige lange (1 h). So repariert sich eine roic-Luecke beim
# naechsten Aufruf selbst, statt eine Stunde zu kleben (Grund fuer den frueher
# noetigen App-Neustart). Pro Titel getrennt - kein gegenseitiges Leeren.
_DEEP_CACHE = {}
_DEEP_TTL_OK = 3600
_DEEP_TTL_LUECKE = 60


def load_fundamentals_deep(t):
    import time as _t
    _hit = _DEEP_CACHE.get(t)
    if _hit:
        _zeit, _daten, _voll = _hit
        _ttl = _DEEP_TTL_OK if _voll else _DEEP_TTL_LUECKE
        if _t.time() - _zeit < _ttl:
            return _daten
    _daten = providers.get_fundamentals(t, deep=True)
    # Kein Default True mehr: Wenn providers das Feld nicht setzt, ist der
    # Abruf im Zweifel unvollstaendig und wird kurz gecacht. Andersherum
    # klebte eine Datenluecke eine Stunde lang.
    _voll = bool(_daten and _daten.get("_vollstaendig", False))
    _DEEP_CACHE[t] = (_t.time(), _daten, _voll)
    return _daten


def deep_cache_info(t):
    """Alter und Vollstaendigkeit des Cache-Eintrags - fuer die Anzeige.

    Zeigt, ob zwei Oberflaechen denselben Datenstand sehen. Genau hier lag
    die Ursache dafuer, dass Portfolio und Einzelanalyse fuer dieselbe Aktie
    verschiedene Upsides anzeigten.
    """
    import time as _t
    _hit = _DEEP_CACHE.get(t)
    if not _hit:
        return None
    _zeit, _daten, _voll = _hit
    return {"alter_s": int(_t.time() - _zeit), "vollstaendig": _voll,
            "luecke_prognose": (_daten or {}).get("_luecke_prognose") or [],
            "luecke_kern": (_daten or {}).get("_luecke_kern") or [],
            "quellen": (_daten or {}).get("data_sources")}
@st.cache_data(ttl=1800, show_spinner=False)
def load_intel(t, name=None): return intel_mod.gather(t, name=name)
@st.cache_data(ttl=900, show_spinner=False)
def load_history(t, p, i): 
    h = providers.get_price_history(t, period=p, interval=i)
    return h[["Close"]].reset_index() if (h is not None and not h.empty) else None
@st.cache_data(ttl=1800, show_spinner=False)
def fx_to_eur(c): return providers.get_fx_to_eur(c)


_DE_SUFFIX_PRIORITY = {
    "DE": 1, "F": 2, "MU": 3, "SG": 4, "BE": 5, "HM": 6, "HA": 7, "DU": 8,
    "VI": 9, "L": 10, "PA": 11, "AS": 12, "MI": 13, "SW": 14, "MC": 15,
    # Cross-Listings (.XC) sind Zweitnotierungen - sie verlieren immer gegen
    # die echte Boersennotierung desselben Unternehmens.
    "XC": 60, "IL": 61,
}


def _canon_base(t):
    """Basissymbol UND Prioritaet - erkennt auch .XC-Zweitnotierungen.

    Ohne Sonderbehandlung ueberleben BHPL.XC und BHP.L beide, weil ihre
    Basissymbole ("BHPL" vs "BHP") verschieden aussehen. Bei .XC haengt
    aber ein L (fuer London) am Symbol: BHPL.XC = BHP + L, SHELL.XC =
    SHEL + L, BPL.XC = BP + L. Das wird hier abgeschnitten, damit beide
    Schreibweisen auf dieselbe Basis fallen."""
    if "." not in t:
        return t, 0
    base, suf = t.split(".", 1)
    suf = suf.upper()
    pri = _DE_SUFFIX_PRIORITY.get(suf, 50)
    if suf in ("XC", "IL") and len(base) > 2 and base.endswith("L"):
        base = base[:-1]                      # BHPL -> BHP (= BHP.L)
    return base, pri


def _collapse_listings(tickers):
    """Doppel-Notierungen DERSELBEN Aktie (z.B. AMZ.DE + AMZ.F, BHP.L +
    BHPL.XC) auf eine reduzieren - heimatnaehere Notierung gewinnt."""
    out, base_pos = [], {}
    for t in tickers:
        base, pri = _canon_base(t)
        if base not in base_pos:
            base_pos[base] = len(out)
            out.append(t)
        else:
            i = base_pos[base]
            _pb, prev_pri = _canon_base(out[i])
            if pri < prev_pri:
                out[i] = t
    return out


@st.cache_data(ttl=1800, show_spinner=False)
def load_universe(regions, min_mcap_eur_bn, size, max_mcap_eur_bn=None,
                  ascending=False):
    """Gecachtes Universum mit STABILEM Schluessel (EUR-Schwelle, kein Live-FX).

    max_mcap_eur_bn + ascending = Suche nach KLEINEREN, wenig beachteten Titeln.
    Ohne sie sortiert der Screener nach Marktkapitalisierung absteigend - dann
    kommen immer nur die Schwergewichte (AVGO & Co.)."""
    usd = providers.get_fx_to_eur("USD") or 0.92
    _max = (max_mcap_eur_bn * 1e9) / usd if max_mcap_eur_bn else None
    tickers, src = ms.get_universe(list(regions), (min_mcap_eur_bn * 1e9) / usd,
                                   int(size), _max, bool(ascending))
    return _collapse_listings(tickers), src


def mcap_eur_bn(fd):
    """Marktkapitalisierung in Mrd. EUR (einheitlich fuer Radar & Screener)."""
    return ((fd.get("market_cap") or 0) * (fd.get("_fx") or 1.0)) / 1e9
@st.cache_data(ttl=3600, show_spinner=False)
def load_scores(t, fund_hint=None):
    """Berechnet Piotroski F, Altman Z, Beneish M, Dorseys Moat-Profitabilitaet
    und die Cashflow-Gewinn-Divergenz aus roic-Jahresdaten. Gibt ein Dict mit
    allen Scores (None je Score, wenn Daten fehlen)."""
    import scores as _sc
    _leer = {"f": None, "z": None, "m": None, "moat": None, "cf_div": None}
    try:
        import roic as _r
        inc = _r.income_annual(t, limit=6) or []
        bal = _r.balance_annual(t, limit=6) or []
        cf = _r.cashflow_annual(t, limit=6) or []
    except Exception:
        return _leer
    akt, vorjahr = _sc.jahres_paar(inc, bal, cf)
    if akt is None:
        return _leer
    sektor = (fund_hint or {}).get("sector") if fund_hint else None
    try:
        f = _sc.piotroski_f(akt, vorjahr, sektor, fund_hint)
    except Exception:
        f = None
    try:
        z = _sc.altman_z(akt, sektor, fund_hint)
    except Exception:
        z = None
    try:
        m = _sc.beneish_m(akt, vorjahr, sektor, fund_hint)
    except Exception:
        m = None
    try:
        moat = _sc.dorsey_moat(inc, bal, cf, jahre=5)
    except Exception:
        moat = None
    try:
        cf_div = _sc.cashflow_gewinn_divergenz(inc, cf, jahre=3)
    except Exception:
        cf_div = None
    return {"f": f, "z": z, "m": m, "moat": moat, "cf_div": cf_div}



@st.cache_data(ttl=3600, show_spinner=False)
def load_screen_extras(t): return providers.get_screen_extras(t)
@st.cache_data(ttl=86400, show_spinner=False)
def load_div_years(t): return providers.get_dividend_years(t)
@st.cache_data(ttl=86400, show_spinner=False)
def load_price_on(t, date): return providers.get_price_on(t, date)
@st.cache_data(ttl=21600, show_spinner=False)
def load_earnings_history(t): return providers.get_earnings_history(t)
@st.cache_data(ttl=60, show_spinner=False)
def load_intraday_price(t): return providers.get_intraday_price(t)
@st.cache_data(ttl=60, show_spinner=False)
def load_intraday_quote(t, cur): return providers.get_intraday_quote(t, cur)
@st.cache_data(ttl=1800, show_spinner=False)
def load_analyst(t): return providers.get_analyst_ratings(t)
@st.cache_data(ttl=600, show_spinner=False)
def search_symbols(q): return providers.search_symbol(q)


def search_to_ticker(roh):
    """Name oder Ticker -> sauberer Ticker. Nutzt dieselbe Suchlogik wie die
    Einzelanalyse: exakter Symbol-Treffer bevorzugt, sonst der erste Treffer,
    sonst die Eingabe selbst in Grossbuchstaben."""
    qv = (roh or "").strip()
    if not qv:
        return None
    try:
        mm = search_symbols(qv)
        if mm:
            exact = next((m for m in mm
                          if m.get("symbol", "").upper() == qv.upper()), None)
            return (exact or mm[0])["symbol"].upper()
    except Exception:
        pass
    return qv.upper()
@st.cache_data(ttl=86400, show_spinner=False)
def load_firmenname(t):
    """Ticker -> Firmenname, dauerhaft gespeichert.

    AUDIT-BEFUND D1: Diese Funktion war mit @st.cache_data versehen und der
    Docstring sagte "24h gecacht" - aber dieser Cache ist prozessgebunden und
    nach jedem App-Neustart leer. In der Earnings-Call-Liste wurden dann bis
    zu 40 Namen NACHEINANDER ueber get_fundamentals() aufgeloest, jeweils mit
    Netzabruf. Die Seite zeigte die Zeile "85 aktuelle Calls" und blieb
    danach minutenlang stehen - es sah aus, als laedt sie nicht mehr.

    Firmennamen aendern sich praktisch nie. Sie gehoeren deshalb in den
    dauerhaften Speicher, nicht in einen Sitzungscache: einmal aufgeloest,
    ueberlebt der Name jeden Neustart.
    """
    try:
        gespeichert = store.get_anreicherung(t, "name", max_alter_tage=365)
        if gespeichert:
            return gespeichert
    except Exception:
        pass
    try:
        f = providers.get_fundamentals(t, deep=False)
        nm = (f or {}).get("name")
        if nm and nm != t:
            try:
                store.set_anreicherung(t, "name", nm)
            except Exception:
                pass
            return nm
    except Exception:
        pass
    return t
@st.cache_data(ttl=1800, show_spinner=False)
def load_history_full(t):
    h = providers.get_price_history(t, period="1y", interval="1d")
    if h is not None and not h.empty:
        cols = [c for c in ["Close", "Volume"] if c in h.columns]
        return h[cols].reset_index(drop=True)
    return None
@st.cache_data(ttl=1800, show_spinner=False)
def load_extras(t): return providers.get_signal_extras(t)
@st.cache_data(ttl=1800, show_spinner=False)
def load_8k(t): return providers.get_recent_8k(t)
@st.cache_data(ttl=1800, show_spinner=False)
def load_event_news(t, name): return providers.get_event_news(name or t)
@st.cache_data(ttl=1800, show_spinner=False)
def load_eps_rev(t): return providers.get_eps_revision_light(t)
@st.cache_data(ttl=1800, show_spinner=False)
def load_insider(t): return providers.get_insider_light(t)
@st.cache_data(ttl=1200, show_spinner=False)
@st.cache_data(ttl=600, show_spinner=False)
def load_marketnews(section, free_only=False): return mn.get_section(section, free_only=free_only)
@st.cache_data(ttl=86400, show_spinner=False)
def tr_de(text): return tr.translate_text(text, "de")


def _berlin_now():
    """Aktuelle Zeit in Europe/Berlin (deutsche Zeit), robust ohne Zusatzpakete."""
    import datetime as dt
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Europe/Berlin"))
    except Exception:
        return dt.datetime.now()


def fmt_ts(ts):
    if not ts:
        return ""
    try:
        import datetime as dt
        try:
            from zoneinfo import ZoneInfo
            return (dt.datetime.fromtimestamp(ts, ZoneInfo("Europe/Berlin"))
                    .strftime("%d.%m.%Y %H:%M"))
        except Exception:
            return dt.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return ""


def esc(s):
    return html.escape(s or "")


def news_sort_key(n):
    """Datum einer News als sortierbarer Zeitstempel (neueste zuerst).
    RSS liefert RFC-2822 (z.B. 'Wed, 16 Jul 2026 08:00:00 +0000'); manche Quellen
    ISO. Fehlt/verrutscht das Datum, wandert die Meldung ans Ende statt die
    Sortierung zu sprengen."""
    s = n.get("datetime") or n.get("published") or n.get("date") or ""
    if not s:
        return 0.0
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).timestamp()
    except Exception:
        pass
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def fmt_news_date(s):
    if not s:
        return ""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).strftime("%d.%m.%Y")
    except Exception:
        return str(s)[:10]


def clean_headline(h):
    """Google-News haengt ' - Publisher' an; entfernen."""
    if h and " - " in h:
        return h.rsplit(" - ", 1)[0]
    return h or "\u2014"


def card(col, label, value, sub="", color="var(--fg)"):
    col.markdown(f'<div class="vr-card"><div class="k">{label}</div>'
                 f'<div class="v" style="color:{color}">{value}</div>'
                 f'<div class="sub">{sub}</div></div>', unsafe_allow_html=True)


def info_icon(text):
    """Dezentes, schoenes Info-Icon mit Hover-Tooltip (title=). Kleiner
    gefuellter Kreis mit i statt der frueheren duennen Umrandung - passt
    besser ins dunkle Terminal-Design."""
    if not text:
        return ""
    return (f'<span title="{esc(text)}" style="cursor:help;display:inline-flex;'
            f'align-items:center;justify-content:center;width:14px;height:14px;'
            f'font-size:10px;font-style:italic;font-weight:600;line-height:1;'
            f'color:var(--bg,#0A0E14);background:var(--muted);border-radius:50%;'
            f'margin-left:5px;vertical-align:middle;opacity:0.75">i</span>')


# --- Eigene SVG-Charts (kein altair -> immun gegen Python/altair-Versionsbrueche) ---
def _svg_esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def svg_index_chart(vals, times, base_val, color, height=132):
    """Kompaktes Index-Chart mit 0-Linie (Vortagesschluss/Tagesstart als Referenz),
    Zeit-Achse unten und Wert-Achse rechts. Fuellung gruen ueber / rot unter der
    0-Linie. Fuer die 'Maerkte heute'-Kacheln (2 nebeneinander)."""
    vals = [float(v) for v in vals if v is not None]
    if len(vals) < 2:
        return "<span class='na'>n/a</span>"
    base = float(base_val) if base_val else vals[0]
    W, H = 400, 150                      # festes Seitenverhaeltnis -> keine Verzerrung
    pad_l, pad_r, pad_t, pad_b = 6, 54, 12, 20
    pw, ph = W - pad_l - pad_r, H - pad_t - pad_b
    lo, hi = min(min(vals), base), max(max(vals), base)
    rng = (hi - lo) or 1.0

    def X(i):
        return pad_l + i / (len(vals) - 1) * pw

    def Y(v):
        return pad_t + (1 - (v - lo) / rng) * ph

    pts = [(X(i), Y(v)) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    y0 = Y(base)
    # Flaeche zwischen Linie und 0-Linie
    area = (f'{pad_l:.1f},{y0:.1f} ' + line + f' {X(len(vals)-1):.1f},{y0:.1f}')
    up = vals[-1] >= base
    fill = "rgba(63,185,80,.14)" if up else "rgba(248,81,73,.14)"
    # Zeit-Labels (Anfang/Ende)
    def _t(i):
        try:
            return times[i].strftime("%H:%M")
        except Exception:
            return ""
    t0, t1 = _t(0), _t(-1)
    # Wert-Labels (Hoch/Tief/0-Linie) rechts
    def _fmt(v):
        return f"{v:,.0f}".replace(",", ".")
    return (
        f'<svg viewBox="0 0 {W} {H}" '
        f'style="display:block;width:100%;height:auto">'
        f'<polygon points="{area}" fill="{fill}" stroke="none"/>'
        # 0-Linie (Referenz)
        f'<line x1="{pad_l}" y1="{y0:.1f}" x2="{pad_l+pw}" y2="{y0:.1f}" '
        f'stroke="#6B7686" stroke-width="1" stroke-dasharray="3,3" '
        f'vector-effect="non-scaling-stroke"/>'
        f'<polyline points="{line}" fill="none" stroke="{color}" '
        f'stroke-width="1.8" vector-effect="non-scaling-stroke"/>'
        # Wert-Achse (rechts): Hoch, 0-Linie, Tief
        f'<text x="{pad_l+pw+3}" y="{pad_t+7:.1f}" fill="#8b95a3" '
        f'font-size="9">{_fmt(hi)}</text>'
        f'<text x="{pad_l+pw+3}" y="{y0+3:.1f}" fill="#9aa4b2" '
        f'font-size="9">{_fmt(base)}</text>'
        f'<text x="{pad_l+pw+3}" y="{pad_t+ph:.1f}" fill="#8b95a3" '
        f'font-size="9">{_fmt(lo)}</text>'
        # Zeit-Achse (unten): Start / Ende
        f'<text x="{pad_l}" y="{H-4}" fill="#8b95a3" font-size="9">{t0}</text>'
        f'<text x="{pad_l+pw}" y="{H-4}" fill="#8b95a3" font-size="9" '
        f'text-anchor="end">{t1}</text>'
        f'</svg>')


def svg_sparkline(vals, color, height=44):
    vals = [float(v) for v in vals if v is not None]
    if len(vals) < 2:
        return "<span class='na'>n/a</span>"
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    W = 240
    pts = " ".join(f"{i/(len(vals)-1)*W:.1f},{height-4-((v-lo)/rng)*(height-8):.1f}"
                   for i, v in enumerate(vals))
    return (f'<svg viewBox="0 0 {W} {height}" width="100%" height="{height}" '
            f'preserveAspectRatio="none" style="display:block">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>')


def interactive_price_chart(prices, pcts, labels, sym="\u20ac", height=260):
    """Interaktiver Kursverlauf wie bei Broker-Apps: beim Hovern erscheint eine
    vertikale Linie mit Kurs und Uhrzeit/Datum an der Mausposition. Die Linie
    ist gruen ueber dem Startkurs, rot darunter - der Startpunkt ist die
    gestrichelte 0-Linie. Rendert als eigenstaendiges HTML/JS (components.html)."""
    prices = [float(p) for p in prices if p is not None]
    pcts = [float(p) for p in pcts if p is not None]
    if len(prices) < 2:
        return None
    import json as _json
    _p = _json.dumps([round(x, 4) for x in prices])
    _pc = _json.dumps([round(x, 3) for x in pcts])
    _lb = _json.dumps([str(x) for x in labels][:len(prices)])
    _sym = _json.dumps(sym)
    # HTML/JS: Canvas-Chart mit Hover. Farbe segmentweise (gruen ueber 0, rot
    # drunter). Tooltip zeigt Kurs + Label an der Mausposition.
    return f"""
<div style="width:100%;font-family:monospace">
  <div id="vrtip" style="height:20px;color:#9aa4b2;font-size:12px;margin-bottom:2px"></div>
  <canvas id="vrcanvas" style="width:100%;height:{height}px;display:block"></canvas>
</div>
<script>
(function(){{
  const prices = {_p}, pcts = {_pc}, labels = {_lb}, sym = {_sym};
  const cv = document.getElementById('vrcanvas');
  const tip = document.getElementById('vrtip');
  const dpr = window.devicePixelRatio || 1;
  function resize(){{
    cv.width = cv.clientWidth * dpr;
    cv.height = {height} * dpr;
  }}
  resize();
  const ctx = cv.getContext('2d');
  const GREEN = '#3FB950', RED = '#F85149', GREY = '#6B7686';
  const lastPct = pcts[pcts.length-1];
  const mainColor = lastPct >= 0 ? GREEN : RED;
  const lo = Math.min(...pcts, 0), hi = Math.max(...pcts, 0);
  const rng = (hi - lo) || 1;
  const pad = 12 * dpr;
  function X(i){{ return i/(prices.length-1) * cv.width; }}
  function Y(p){{ return pad + (hi - p)/rng * (cv.height - 2*pad); }}
  function draw(hoverIdx){{
    ctx.clearRect(0,0,cv.width,cv.height);
    // 0-Linie (Startkurs)
    const zy = Y(0);
    ctx.strokeStyle = GREY; ctx.lineWidth = 1*dpr;
    ctx.setLineDash([4*dpr,4*dpr]);
    ctx.beginPath(); ctx.moveTo(0,zy); ctx.lineTo(cv.width,zy); ctx.stroke();
    ctx.setLineDash([]);
    // Flaeche
    ctx.beginPath();
    ctx.moveTo(0, Y(pcts[0]));
    for(let i=1;i<pcts.length;i++) ctx.lineTo(X(i), Y(pcts[i]));
    ctx.lineTo(cv.width, zy); ctx.lineTo(0, zy); ctx.closePath();
    ctx.fillStyle = mainColor; ctx.globalAlpha = 0.10; ctx.fill();
    ctx.globalAlpha = 1;
    // Linie segmentweise gruen/rot je nach Vorzeichen
    ctx.lineWidth = 1.8*dpr;
    for(let i=1;i<pcts.length;i++){{
      ctx.strokeStyle = (pcts[i] >= 0 ? GREEN : RED);
      ctx.beginPath();
      ctx.moveTo(X(i-1), Y(pcts[i-1]));
      ctx.lineTo(X(i), Y(pcts[i]));
      ctx.stroke();
    }}
    // Hover: vertikale Linie + Punkt
    if(hoverIdx !== null){{
      const hx = X(hoverIdx), hy = Y(pcts[hoverIdx]);
      ctx.strokeStyle = GREY; ctx.lineWidth = 1*dpr;
      ctx.beginPath(); ctx.moveTo(hx,0); ctx.lineTo(hx,cv.height); ctx.stroke();
      ctx.fillStyle = (pcts[hoverIdx] >= 0 ? GREEN : RED);
      ctx.beginPath(); ctx.arc(hx,hy,4*dpr,0,2*Math.PI); ctx.fill();
    }}
  }}
  function onMove(ev){{
    const r = cv.getBoundingClientRect();
    const x = (ev.clientX - r.left) / r.width;
    let idx = Math.round(x * (prices.length-1));
    idx = Math.max(0, Math.min(prices.length-1, idx));
    const pc = pcts[idx];
    const col = pc >= 0 ? '#3FB950' : '#F85149';
    tip.innerHTML = '<b style="color:#e6e6e6">' + sym + ' ' +
      prices[idx].toLocaleString('de-DE',{{minimumFractionDigits:2,maximumFractionDigits:2}}) +
      '</b> <span style="color:'+col+'">(' + (pc>=0?'+':'') + pc.toFixed(2) + ' %)</span>' +
      ' <span style="color:#6B7686">\u00b7 ' + (labels[idx]||'') + '</span>';
    draw(idx);
  }}
  function onLeave(){{ tip.innerHTML=''; draw(null); }}
  cv.addEventListener('mousemove', onMove);
  cv.addEventListener('mouseleave', onLeave);
  window.addEventListener('resize', function(){{ resize(); draw(null); }});
  draw(null);
}})();
</script>
"""


def svg_area_chart(pcts, color, height=250):
    """Flaechen-/Linienchart der prozentualen Entwicklung, mit Nulllinie."""
    pcts = [float(p) for p in pcts if p is not None]
    if len(pcts) < 2:
        return "<span class='na'>Kein Kursverlauf verf\u00fcgbar.</span>"
    lo, hi = min(pcts + [0.0]), max(pcts + [0.0])
    rng = (hi - lo) or 1.0
    W, H, pad = 700, height, 10

    def yy(p):
        return pad + (hi - p) / rng * (H - 2 * pad)

    def xx(i):
        return i / (len(pcts) - 1) * W
    line_pts = " ".join(f"{xx(i):.1f},{yy(p):.1f}" for i, p in enumerate(pcts))
    area_pts = f"0,{yy(lo):.1f} " + line_pts + f" {W},{yy(lo):.1f}"
    zy = yy(0.0)
    return (
        f'<svg viewBox="0 0 {W} {H}" '
        f'style="display:block;width:100%;height:auto">'
        f'<polygon points="{area_pts}" fill="{color}" opacity="0.12"/>'
        f'<line x1="0" y1="{zy:.1f}" x2="{W}" y2="{zy:.1f}" stroke="#6B7686" '
        f'stroke-width="1" stroke-dasharray="4 4"/>'
        f'<polyline points="{line_pts}" fill="none" stroke="{color}" '
        f'stroke-width="1.8" vector-effect="non-scaling-stroke"/>'
        f'<text x="6" y="14" fill="#6B7686" font-size="11" font-family="monospace">'
        f'+{hi:.1f}%</text>'
        f'<text x="6" y="{H-6}" fill="#6B7686" font-size="11" font-family="monospace">'
        f'{lo:.1f}%</text></svg>')


def _render_autodepot():
    """Selbstverwaltetes 50k-Papierdepot: Wert, Positionen, Trades, Steuerung."""
    import autodepot as ad
    st.markdown('<div class="sec-title">\U0001f916 AUTO-DEPOT \u00b7 50.000 \u20ac '
                'selbstverwaltet</div>', unsafe_allow_html=True)
    st.caption("Ein Papierdepot, das nach festen Regeln aus Screener, Radar und "
               "Momentum kauft: gleichgewichtet (10\u201315 Positionen), Obergrenze "
               "je Titel, Long und Short (ungehebelt), mit Stop-Loss, "
               "Take-Profit, nachgezogenem Gewinn-Stop und Teilverkauf. "
               "**Mechanische Regeln, keine Prognose \u2013 kein Anlagerat.**")

    k = ad.kennzahlen()

    # Kennzahlen-Karten
    c = st.columns(4)
    _farbe = "var(--green)" if k["rendite_pct"] >= 0 else "var(--red)"
    card(c[0], "Depotwert", f"{k['wert']:,.0f} \u20ac".replace(",", "."))
    card(c[1], "Rendite", f"{k['rendite_pct']:+.2f} %", color=_farbe)
    card(c[2], "Investiert",
         f"{100 - k['cash_quote']:.0f} %",
         sub=f"Cash {k['cash_quote']:.0f} %")
    card(c[3], "Positionen", str(k["n_positionen"]),
         sub=(f"Trefferquote {k['trefferquote']:.0f} %"
              if k["trefferquote"] is not None else "noch keine Exits"))

    if k.get("neustart_am"):
        _tage = (time.time() - k["neustart_am"]) / 86400
        _hinweis = f"L\u00e4uft seit {_tage:.0f} Tagen"
        if k.get("neustart_grund"):
            _hinweis += f" \u00b7 Neustart: {k['neustart_grund']}"
        if _tage < 30:
            _hinweis += " \u00b7 \u26a0\ufe0f zu kurz f\u00fcr eine Beurteilung"
        st.caption(_hinweis)

    st.markdown("---")

    # Steuerung
    _s1, _s2 = st.columns([2, 1])
    _shorts = _s1.checkbox("Short-Positionen zulassen (max. 1x)", value=True,
                           key="ad_shorts")
    if _s2.button("\u25b6 Depot aktualisieren", key="ad_run",
                  use_container_width=True):
        with st.spinner("Scanne M\u00e4rkte und passe das Depot an \u2026 "
                        "(kann 1\u20132 Minuten dauern)"):
            try:
                ad.durchlauf(scan_size=200, erlauben_shorts=_shorts)
                st.success("Depot aktualisiert.")
                st.rerun()
            except Exception as _e:
                st.error(f"Aktualisierung fehlgeschlagen: {_e}")
    st.caption("Ein Durchlauf pr\u00fcft zuerst Ausstiege (Stop-Loss, Take-Profit, "
               "Gewinn-Stop, erloschene Signale), dann f\u00fcllt er freie Slots mit "
               "neuen Signalen. Das Depot muss nicht voll investiert sein.")

    st_ = ad.lade()

    # Offene Positionen
    if st_["positions"]:
        st.markdown('<div class="vr-th">Offene Positionen</div>',
                    unsafe_allow_html=True)
        _pdata = []
        for p in st_["positions"]:
            _pe, _ = ad._price_eur(p["ticker"])
            _wert = (p["qty"] * _pe) if _pe else (p["qty"] * p["entry_eur"])
            _pdata.append({
                "Ticker": p["ticker"],
                "Name": (p.get("name") or "")[:20],
                "Richtung": "\u2191 Long" if p["dir"] == "long" else "\u2193 Short",
                "Wert \u20ac": round(_wert),
                "G/V %": p.get("pl_pct"),
                "Peak %": p.get("peak_pl"),
                "Gewinn-Stop": (f"+{p['trail_stop']:.0f} %"
                                if p.get("trail_stop") is not None else "\u2014"),
                "Quelle": p.get("quelle", ""),
            })
        vr_table(_pdata, signed_cols=("G/V %", "Peak %"),
                 height=min(len(_pdata) * 40 + 46, 460))
    else:
        st.info("Noch keine Positionen. \u201eDepot aktualisieren\u201c startet den "
                "ersten Kauf-Durchlauf.")

    # Handelshistorie
    if st_["trades"]:
        with st.expander(f"\U0001f4d3 Handelshistorie ({len(st_['trades'])})"):
            _tdata = []
            for t in st_["trades"][:60]:
                try:
                    _dt = datetime.fromtimestamp(t.get("ts") or 0).strftime("%d.%m. %H:%M")
                except Exception:
                    _dt = "\u2014"
                _akt = {"open": "Kauf", "close": "Verkauf",
                        "teilverkauf": "Teilverkauf"}.get(t.get("action"), t.get("action"))
                _tdata.append({
                    "Zeit": _dt,
                    "Aktion": _akt,
                    "Ticker": t.get("ticker"),
                    "Richtung": t.get("dir", ""),
                    "G/V %": t.get("pl_pct"),
                    "Gewinn \u20ac": t.get("gain_eur"),
                    "Grund": t.get("why", ""),
                })
            vr_table(_tdata, signed_cols=("G/V %", "Gewinn \u20ac"),
                     height=min(len(_tdata) * 38 + 44, 480))

    # Neustart
    with st.expander("\u21bb Depot zur\u00fccksetzen"):
        st.caption("Setzt das Depot auf 50.000 \u20ac Cash zur\u00fcck und l\u00f6scht alle "
                   "Positionen und die Historie. Nicht r\u00fcckg\u00e4ngig zu machen.")
        _grund = st.text_input("Grund (optional)", key="ad_reset_grund",
                               placeholder="z.B. Regeln ge\u00e4ndert")
        if st.button("Depot jetzt zur\u00fccksetzen", key="ad_reset"):
            ad.reset(_grund or "manueller Neustart")
            st.success("Depot zur\u00fcckgesetzt.")
            st.rerun()

    st.caption("**Ehrlich eingeordnet:** Dieses Depot misst, ob die Kombination "
               "der Scan-Signale mit diesen Regeln \u00fcber Monate etwas taugt. "
               "Ein positiver Verlauf \u00fcber wenige Wochen ist Zufall, kein Beleg. "
               "Kein Anlagerat.")


def render_trackrecord():
    """Trefferbilanz: was ist aus unseren Signalen geworden - gegen den Index."""
    _tb_view = st.radio("Ansicht",
                        ["\U0001f4c8 Signal-Tagebuch", "\U0001f916 Auto-Depot (50k)"],
                        horizontal=True, key="tb_view", label_visibility="collapsed")
    if _tb_view.endswith("Auto-Depot (50k)"):
        _render_autodepot()
        return

    st.markdown('<div class="sec-title">\U0001f4c8 TREFFERBILANZ \u00b7 Signal-Tagebuch'
                '</div>', unsafe_allow_html=True)
    try:
        import trackrecord as tr
        rows = tr.evaluate()
        summ = tr.summary(rows)
        _stored = tr.store.get_signals() or []
    except Exception as e:
        st.error(f"Trefferbilanz nicht verf\u00fcgbar: {e}")
        return

    # Ehrliche Diagnose: unterscheidet "gar nichts gespeichert" von "gespeichert,
    # aber noch nicht auswertbar" (Kurs fehlt / zu frisch). Vorher stand pauschal
    # "keine Signale erfasst" - auch wenn welche da waren.
    if not rows and _stored:
        _n_reif = sum(1 for e in _stored
                      if (time.time() - (e.get("ts") or time.time())) / 86400 >= 14)
        st.warning(
            f"\u26a0\ufe0f **{len(_stored)} Signale gespeichert**, aber keines l\u00e4sst sich "
            "gerade auswerten. H\u00e4ufigste Ursachen: aktuelle Kurse nicht abrufbar "
            "(API-Limit/Ticker), oder die Signale sind noch keine 14 Tage alt "
            f"({_n_reif} bereits reif).")
    elif not rows:
        st.info("Noch keine Signale erfasst. Der automatische Lauf (2\u00d7 t\u00e4glich) "
                "h\u00e4lt jedes Screener-/Radar-Signal fest. Aussagekr\u00e4ftig wird das "
                "erst nach einigen Wochen und vielen F\u00e4llen.")

    # --- Diagnose: liest NUR die gespeicherten Nachtlauf-Ergebnisse. Fuehrt
    #     KEINEN Live-Scan aus - der wuerde in der App-Umgebung nach einigen
    #     Minuten abbrechen (Screener/Radar scannen hunderte Titel; das gehoert
    #     in den Nachtlauf auf GitHub, nicht in den Browser).
    with st.expander("\U0001f527 Warum (keine) Signale? Diagnose", expanded=not rows):
        try:
            import trackrecord as _trd
            _sig = _trd.store.get_signals() or []
        except Exception:
            _sig = []
        _quellen = {}
        for _s in _sig:
            _q = _s.get("quelle", "?")
            _quellen[_q] = _quellen.get(_q, 0) + 1
        st.write(f"**Gespeicherte Signale gesamt:** {len(_sig)}")
        if _quellen:
            st.write("Nach Quelle: " + " \u00b7 ".join(
                f"{k}: {v}" for k, v in sorted(_quellen.items())))
        # Status des letzten Nachtlaufs, falls verfuegbar
        try:
            _tstat = _trd.store.get_transkript_status() if hasattr(
                _trd.store, "get_transkript_status") else {}
        except Exception:
            _tstat = {}
        st.caption(
            "Diese Liste f\u00fcllt der **Nachtlauf** (GitHub), nicht die App. "
            "Der Live-Scan von Screener/Radar l\u00e4uft NICHT im Browser \u2013 er "
            "scannt hunderte Titel und w\u00fcrde hier nach einigen Minuten "
            "abbrechen (das war die Ursache f\u00fcr das ewige Laden + Sprung zur "
            "Startseite). Wenn hier 0 Screener-/Radar-Signale stehen, im "
            "GitHub-Actions-Log des letzten Laufs nach der Zeile "
            "\u201eSignal-Erfassung startet\u201c und \u201eAbstand zur Zone\u201c schauen \u2013 "
            "die zeigen, ob die Scans Kandidaten fanden und ob die Kaufzone "
            "griff.")
        if not _sig:
            st.warning("Noch keine Signale gespeichert. Starte den "
                       "GitHub-Actions-Workflow und pr\u00fcfe danach das Log.")

    if not rows:
        return

    if summ.get("n"):
        c = st.columns(4)
        _ae = summ.get("avg_excess")
        card(c[0], "Signale (\u2265 14 Tage)", str(summ["n"]),
             f"{summ['n_all']} insgesamt erfasst")
        card(c[1], "Win %", f"{summ['win_pct']} %", "Anteil im Plus",
             "var(--green)" if summ["win_pct"] >= 50 else "var(--red)")
        card(c[2], "\u00d8 Rendite", f"{summ['avg_ret']:+.1f} %", "seit Signal",
             "var(--green)" if summ["avg_ret"] >= 0 else "var(--red)")
        card(c[3], "\u00d8 vs. S&P 500",
             f"{_ae:+.1f} %" if _ae is not None else "\u2014",
             (f"{summ['beat_pct']} % schlagen den Index"
              if summ.get("beat_pct") is not None else ""),
             "var(--green)" if (_ae or 0) >= 0 else "var(--red)")
        if _ae is not None and _ae < 0:
            st.warning("\u26a0\ufe0f Die Signale liegen im Schnitt **hinter** dem Index. "
                       "Ein Indexfonds w\u00e4re bislang die bessere Wahl gewesen \u2013 "
                       "genau daf\u00fcr ist diese Messung da.")
    else:
        st.info(f"{summ.get('n_all', 0)} Signale erfasst, aber noch keines ist "
                "14 Tage alt. Zu fr\u00fch f\u00fcr ein Urteil.")

    # Drei getrennte Tabellen untereinander: Screener, Radar, Kontrollgruppe.
    # Verdaechtige Zeilen (Einheiten-Mischmasch) werden getrennt ausgewiesen,
    # damit sie sichtbar bleiben, aber die Auswertung nicht verfaelschen.
    _bad = [r for r in rows if r.get("suspekt")]
    _ok = [r for r in rows if not r.get("suspekt")]

    def _tab(titel, quelle, hinweis, extra=None, short=False, filt=None):
        # quelle=None + filt=<Funktion> erlaubt Tabellen, die nicht nach der
        # Quelle, sondern nach einem anderen Merkmal gruppieren (z.B. das
        # Scorecard-Urteil).
        sub = ([r for r in _ok if filt(r)] if filt
               else [r for r in _ok if r.get("quelle") == quelle])
        st.markdown(f'<div class="sec-title" style="margin-top:16px">{titel} '
                    f'<span style="opacity:.6;font-size:12px">({len(sub)})</span>'
                    '</div>', unsafe_allow_html=True)
        if not sub:
            st.caption(hinweis)
            return
        d = []
        for r in sub:
            _dt_ein = ""
            try:
                _dt_ein = datetime.fromtimestamp(r.get("ts") or 0).strftime("%d.%m.%y")
            except Exception:
                _dt_ein = "\u2014"
            row = {"Ticker": r["ticker"],
                   "Name": (r.get("name") or "")[:22],
                   "Einstieg am": _dt_ein,
                   "Tage": r["days"],
                   "Einstieg": round(r["entry_px"], 2),
                   "Whg": (r.get("entry_ccy") or "").strip() or "\u2014",
                   "Einstieg \u20ac": (r.get("entry_eur")
                                       if r.get("entry_eur") is not None
                                       else "\u2014")}
            # quellenspezifische Spalten VOR den Renditespalten
            for lbl, key, fmt in (extra or []):
                v = r.get(key)
                row[lbl] = fmt(v) if (v is not None and v != "") else "\u2014"
            row["Kurs %"] = r["ret_pct"]
            if short:
                # Diese Titel wurden als SCHWACH eingestuft - die passende
                # Position waere short. Faellt der Kurs, ist die Short-Rendite
                # positiv. Reine Modellrechnung: ohne Leihgebuehr, Spread und
                # Dividendenausgleich, die bei echten Shorts anfallen.
                row["Short %"] = round(-r["ret_pct"], 1)
                row["vs. Index %"] = (round(-r["ret_pct"] - (r.get("bench_pct") or 0), 1)
                                      if r.get("bench_pct") is not None else None)
            else:
                row["S&P %"] = r.get("bench_pct")
                row["vs. Index %"] = r.get("excess_pct")
            d.append(row)
        vr_table(d, signed_cols=("Kurs %", "Short %", "S&P %", "vs. Index %",
                                 "Upside %"),
                 height=min(len(d) * 40 + 46, 420))

    # Kaufkandidaten zuerst - das ist die Auswahl, die einer echten
    # Kaufentscheidung entspricht. Die Kontrollgruppe bleibt aussen vor,
    # sie ist bewusst schwach ausgewaehlt.
    _BUY = getattr(tr, "BUY_VERDICTS", ("Kaufkandidat",))

    def _ist_kauf(r):
        return (r.get("quelle") in ("Screener", "Radar")
                and (r.get("vkey") == "buy"
                     or str(r.get("verdict", "")).strip() in _BUY))

    _tab("\u2705 KAUFKANDIDATEN (Scorecard erf\u00fcllt)", None,
         "Noch keine Kaufkandidaten erfasst. Die Scorecard vergibt dieses "
         "Urteil, wenn **alle** Pflichtkriterien erf\u00fcllt sind und "
         "mindestens ein Bonuspunkt dazukommt.",
         extra=[("Quelle", "quelle", lambda v: str(v)),
                ("Score", "score", lambda v: round(v)),
                ("Upside %", "upside", lambda v: round(v, 1)),
                ("Strategie", "strategie", lambda v: str(v))],
         filt=_ist_kauf)

    # Kaufkandidaten, die GESPEICHERT sind, aber gerade keinen Kurs liefern
    # (haeufig Londoner Pence-Titel wie FRES.L bei API-Limit). Ohne diesen
    # Hinweis verschwinden sie spurlos - man denkt, es gebe keine.
    _ok_ticker = {r["ticker"] for r in rows}
    _fehlt = [e for e in _stored
              if e.get("quelle") in ("Screener", "Radar")
              and (e.get("vkey") == "buy"
                   or str(e.get("verdict", "")).strip() in _BUY)
              and e["ticker"] not in _ok_ticker]
    if _fehlt:
        st.caption(
            f"\u2139\ufe0f {len(_fehlt)} weitere(r) Kaufkandidat(en) gespeichert, "
            "aber gerade **kein Kurs abrufbar** (API-Limit oder Ticker \u2013 "
            "oft Londoner Titel): "
            + ", ".join(sorted(e["ticker"] for e in _fehlt)[:12])
            + (" \u2026" if len(_fehlt) > 12 else "")
            + ". Beim n\u00e4chsten Laden erneut pr\u00fcfen.")
    st.caption("Diese Titel h\u00e4tte die Regel \u201enur Kaufkandidaten kaufen\u201c "
               "tats\u00e4chlich gekauft. Sie erscheinen zus\u00e4tzlich unten in "
               "ihrer jeweiligen Quelle. Kein Anlagerat.")

    _tab("\U0001f50e SCREENER", "Screener",
         "Noch keine Screener-Signale erfasst.",
         extra=[("Score", "score", lambda v: round(v)),
                ("Upside %", "upside", lambda v: round(v, 1)),
                ("Strategie", "strategie", lambda v: str(v))])
    _tab("\U0001f4e1 RADAR", "Radar",
         "Noch keine Radar-Signale erfasst.",
         extra=[("Radar-Score", "score", lambda v: round(v)),
                ("Ebenen", "firing", lambda v: f"{int(v)}/4"),
                ("Upside %", "upside", lambda v: round(v, 1))])
    _tab("\U0001f680 MOMENTUM", "Momentum",
         "Noch keine Momentum-Signale erfasst. Der Nachtlauf schreibt die "
         "Top-Momentum-Titel mit und testet sie gegen den S&P 500.",
         extra=[("Mom-Score", "score", lambda v: round(v)),
                ("12\u20131 %", "mom_12_1", lambda v: round(v, 1)),
                ("vs Branche", "rel_staerke", lambda v: round(v, 1))])
    _tab("\U0001f4c5 EARNINGS \u00b7 POSITIV ERWARTET", "Earnings+",
         "Noch keine Termine mit klarem Positiv-Muster erfasst.",
         extra=[("Beat-Quote", "score", lambda v: f"{round(v)} %"),
                ("L\u00fccke", "luecke", lambda v: f"{int(v):+d}"),
                ("Lage", "merkmal", lambda v: str(v)),
                ("Spricht daf\u00fcr", "strategie", lambda v: str(v))])
    _tab("\U0001f4c5 EARNINGS \u00b7 NEGATIV ERWARTET (als Short gerechnet)",
         "Earnings-",
         "Noch keine Termine mit klarem Negativ-Muster erfasst.",
         extra=[("Beat-Quote", "score", lambda v: f"{round(v)} %"),
                ("Lage", "merkmal", lambda v: str(v))],
         short=True)
    st.caption("Diese beiden Gruppen protokollieren die **Earnings-Logik**: "
               "Gr\u00fcn hie\u00df \u201e\u00fcbertrifft meist und wird belohnt\u201c, Rot hie\u00df "
               "\u201everfehlt h\u00e4ufig\u201c. Hier zeigt sich, ob die Einsch\u00e4tzung "
               "getragen hat \u2013 gemessen ab dem Tag der Aufnahme, also VOR "
               "dem Termin. Kein Anlagerat.")

    _tab("\U0001f9ea GEGEN DEN STROM (experimentell)", "Contrarian",
         "Noch keine Kandidaten erfasst. Gesucht werden Titel mit niedrigen "
         "Erwartungen, bei denen harte Zahlen dagegen sprechen.",
         extra=[("Niedrige Erwartung", "merkmal", lambda v: str(v)),
                ("Spricht dagegen", "strategie", lambda v: str(v))])
    _tab("\u26a0\ufe0f KONTROLLGRUPPE (schwache Setups \u00b7 als Short gerechnet)", "Negativ",
         "Noch keine schwachen Setups erfasst \u2013 der n\u00e4chtliche Lauf "
         "sammelt sie ab jetzt automatisch.",
         extra=[("Score", "score", lambda v: round(v)),
                ("Upside %", "upside", lambda v: round(v, 1)),
                ("Merkmal", "merkmal", lambda v: str(v))],
         short=True)

    if _bad:
        with st.expander(f"\u26a0\ufe0f {len(_bad)} Signale mit fehlerhaften Kursdaten "
                         "(aus der Auswertung ausgeschlossen)"):
            st.caption("Diese Zeilen zeigen unrealistische Renditen \u2013 fast immer "
                       "ein Einheitenproblem (z. B. Pence gegen Pfund, Faktor 100). "
                       "Sie flie\u00dfen in KEINE Statistik ein. Nach dem n\u00e4chsten "
                       "n\u00e4chtlichen Lauf sollten sie verschwinden; bleiben sie, "
                       "l\u00f6sche die betroffenen Signale im Speicher.")
            vr_table([{"Ticker": r["ticker"],
                       "Name": (r.get("name") or "")[:20],
                       "Quelle": r.get("quelle", ""),
                       "Tage": r["days"], "Einstieg": round(r["entry_px"], 2),
                       "Rendite %": r["ret_pct"]} for r in _bad],
                     signed_cols=("Rendite %",),
                     height=min(len(_bad) * 40 + 46, 300))

    # === Signale verwalten (loeschen + neu aufbauen) ===
    with st.expander("\U0001f9f9 DUBLETTEN BEREINIGEN"):
        st.caption("Entfernt Eintr\u00e4ge aus L\u00e4ufen **vor** der Entdopplung: "
                   "dieselbe Firma unter mehreren Symbolen (GOOGL, GOOG, "
                   "ABEC.DE, ABE0.F) sowie Zweitnotierungen wie `.IL` und "
                   "`.XC`. Behalten wird je Firma und Quelle die **\u00e4lteste** "
                   "Zeile \u2013 die hat die l\u00e4ngste Historie.")
        st.caption("Warum `.IL`/`.XC` ganz raus: Diese Zweitnotierungen "
                   "liefern oft keinen Firmennamen und ihre Kurse stehen in "
                   "einer anderen Einheit als die Heimatnotierung \u2013 daher "
                   "die unsinnigen \u221252 bis \u221262 %. Die Heimatnotierung "
                   "derselben Firma bleibt erhalten.")
        if st.button("\U0001f9f9 Jetzt bereinigen", key="tb_dedupe",
                     use_container_width=True):
            try:
                import trackrecord as _tk
                _ent, _bleibt, _raus = _tk.bereinige_dubletten()
                if _ent:
                    st.success(f"{_ent} Dublette(n) entfernt, {_bleibt} "
                               "Eintr\u00e4ge bleiben.")
                    st.caption("Entfernt: " + ", ".join(str(x) for x in _raus[:25])
                               + (" \u2026" if len(_raus) > 25 else ""))
                    st.cache_data.clear()
                else:
                    st.info("Keine Dubletten gefunden.")
            except Exception as _e:
                st.error(f"Bereinigung fehlgeschlagen: {_e}")

    with st.expander("\U0001f5d1\ufe0f Signale zur\u00fccksetzen"):
        st.caption("Bereits erfasste Signale werden vom n\u00e4chtlichen Lauf "
                   "**\u00fcbersprungen** \u2013 er f\u00fcgt nur neue Ticker hinzu. Nach "
                   "\u00c4nderungen an der Bewertung bleiben Alt-Eintr\u00e4ge daher mit "
                   "ihren veralteten Zahlen stehen. Hier kannst du eine Gruppe "
                   "l\u00f6schen, damit sie beim n\u00e4chsten Lauf frisch erfasst wird.")
        st.caption("\u2139\ufe0f **Momentum einmal zur\u00fccksetzen empfohlen:** Ein "
                   "Fehler hatte den Einstiegskurs von Momentum-Signalen in "
                   "Euro statt Handelsw\u00e4hrung gespeichert (z.B. 382 statt 440) "
                   "\u2013 das ergab einen erfundenen Gewinn. Ab jetzt korrekt; "
                   "die alten Momentum-Eintr\u00e4ge einmal l\u00f6schen, dann erfasst "
                   "der n\u00e4chste Lauf sie sauber.")
        _zc1, _zc2 = st.columns([1, 1])
        _welche = _zc1.selectbox("Welche Gruppe?",
                                 ["Screener", "Radar", "Momentum", "Negativ",
                                  "Contrarian", "Earnings+", "Earnings-", "ALLE"],
                                 key="tr_clear_pick")
        _anz = len([r for r in rows
                    if _welche == "ALLE" or r.get("quelle") == _welche])
        _zc2.metric("betroffen", _anz)
        _sicher = st.checkbox(
            f"Ja, **{_welche}** wirklich l\u00f6schen \u2013 das l\u00e4sst sich nicht "
            "r\u00fcckg\u00e4ngig machen.", key="tr_clear_ok")
        if st.button("\U0001f5d1\ufe0f Jetzt l\u00f6schen", disabled=not _sicher,
                     use_container_width=True, key="tr_clear_go"):
            try:
                weg, rest = tr.clear(None if _welche == "ALLE" else _welche)
                if weg:
                    st.success(f"{weg} Signale gel\u00f6scht, {rest} verbleiben. "
                               "Der n\u00e4chste n\u00e4chtliche Lauf erfasst sie neu \u2013 "
                               "oder starte den Workflow in GitHub manuell.")
                    st.cache_data.clear()
                else:
                    st.error("Nichts gel\u00f6scht. M\u00f6glich, wenn der Speicher "
                             "gerade nicht schreibbar ist.")
            except Exception as e:
                st.error(f"L\u00f6schen fehlgeschlagen: {e}")

    # === Statistik nach Quelle (Screener / Radar) + Euro-Modellrechnung ===
    st.markdown('<div class="sec-title" style="margin-top:18px">\U0001f4ca '
                'STATISTIK NACH QUELLE</div>', unsafe_allow_html=True)
    _sc1, _sc2 = st.columns([1, 1])
    _quelle = _sc1.selectbox("Quelle", ["Screener", "Radar", "Negativ", "Alle"],
                             index=0, key="tr_src")
    _q = None if _quelle == "Alle" else _quelle
    _invest = _sc2.number_input("Modell-Einsatz je Signal (\u20ac)", min_value=0,
                                value=1000, step=250, key="tr_invest",
                                help="Nur eine Was-w\u00e4re-wenn-Rechnung: h\u00e4ttest du "
                                     "bei JEDEM Signal diesen Betrag investiert. Kein "
                                     "echtes Geld \u2013 ein Signal ist kein Trade.")
    try:
        sst = tr.source_stats(_q, invest_eur=_invest or None, rows=rows)
    except Exception as e:
        sst = {"n": 0}
        st.caption(f"(Statistik nicht verf\u00fcgbar: {e})")

    if sst.get("n"):
        _c = st.columns(4)
        card(_c[0], "Gewonnen / Verloren", f"{sst['wins']} / {sst['losses']}",
             f"{sst['n']} reife Signale",
             "var(--green)" if sst["wins"] >= sst["losses"] else "var(--red)")
        card(_c[1], "Win %", f"{sst['win_pct']} %", "im Plus",
             "var(--green)" if sst["win_pct"] >= 50 else "var(--red)")
        card(_c[2], "\u00d8 Rendite", f"{sst['avg_ret']:+.1f} %",
             f"best {sst['best']:+.0f} / worst {sst['worst']:+.0f}",
             "var(--green)" if sst["avg_ret"] >= 0 else "var(--red)")
        _ae = sst.get("avg_excess")
        card(_c[3], "\u00d8 vs. S&P 500",
             f"{_ae:+.1f} %" if _ae is not None else "\u2014", "Ueberrendite",
             "var(--green)" if (_ae or 0) >= 0 else "var(--red)")

        _m = sst.get("model")
        if _m:
            st.markdown('<div class="sec-title" style="margin-top:10px;'
                        'font-size:13px;opacity:.85">\U0001f4b6 MODELLRECHNUNG '
                        '(kein echtes Geld)</div>', unsafe_allow_html=True)
            _mc = st.columns(3)
            card(_mc[0], "Fiktiv investiert", sym_eur(_m["invested"]),
                 f"{sym_eur(_m['per_signal'])} je Signal")
            card(_mc[1], "Modell-Ergebnis", sym_eur(_m["final"]), "Summe aller Signale")
            _g = _m["gain_eur"]
            card(_mc[2], "Modell-G/V", f"{'+' if _g >= 0 else ''}{sym_eur(_g)}",
                 f"{_m['gain_pct']:+.1f} %",
                 "var(--green)" if _g >= 0 else "var(--red)")
            st.caption("\u26a0\ufe0f Reine Was-w\u00e4re-wenn-Rechnung: gleicher Betrag auf "
                       "jedes Signal, ohne Geb\u00fchren, Spread oder Steuern. Ein Screener-"
                       "Signal ist kein Trade \u2013 echtes Euro-G/V steht nur im "
                       "Portfolio- und Hedgefonds-Logbuch. Kein Anlagerat.")
    else:
        st.info(f"Noch keine reifen {_quelle}-Signale (\u2265 14 Tage). Die Statistik "
                "f\u00fcllt sich, sobald die ersten Signale alt genug sind.")

    # === DIE KERNFRAGE: schlaegt die Scorecard-Regel den Index? ===
    st.markdown('<div class="sec-title" style="margin-top:18px">\U0001f3af '
                'REGEL: \u201eNUR KAUFKANDIDATEN KAUFEN\u201c</div>',
                unsafe_allow_html=True)
    try:
        _strat = tr.strategy_stats(rows)
    except Exception as e:
        _strat = None
        st.caption(f"(nicht verf\u00fcgbar: {e})")
    if _strat and _strat.get("gefiltert"):
        _g, _a = _strat["gefiltert"], _strat.get("alle")
        _k = st.columns(3)
        card(_k[0], "Nur Kaufkandidaten",
             f"{_g['avg_ret']:+.1f} %",
             f"{_g['n']} Signale \u00b7 {_g['win_pct']} % im Plus",
             "var(--green)" if _g["avg_ret"] >= 0 else "var(--red)")
        card(_k[1], "vs. S&P 500",
             (f"{_g['avg_excess']:+.1f} Pp." if _g.get("avg_excess") is not None
              else "\u2014"),
             (f"Index selbst: {_g['avg_bench']:+.1f} %"
              if _g.get("avg_bench") is not None else ""),
             "var(--green)" if (_g.get("avg_excess") or 0) > 0 else "var(--red)")
        card(_k[2], "Vorteil durch den Filter",
             (f"{_strat['vorteil']:+.1f} Pp." if _strat.get("vorteil") is not None
              else "\u2014"),
             (f"ungefiltert: {_a['avg_excess']:+.1f} Pp. vs. Index"
              if _a and _a.get("avg_excess") is not None else ""),
             "var(--green)" if (_strat.get("vorteil") or 0) > 0 else "var(--amber)")
        st.info(f"**Urteil:** {_strat['urteil']}")
        st.caption("Simuliert die Regel \u201eich kaufe nur, was die Scorecard als "
                   "**Kaufkandidat** einstuft\u201c \u2013 also alle Pflichtkriterien "
                   "erf\u00fcllt plus mindestens ein Bonuspunkt. Verglichen wird "
                   "gegen den Index UND gegen alle Signale ohne diesen Filter. "
                   "Nur wenn beide Vergleiche positiv sind, tr\u00e4gt die Scorecard "
                   "etwas bei. Ohne Geb\u00fchren, Spread und Steuern \u2013 "
                   "kein Anlagerat.")
    else:
        st.info("Noch keine Kaufkandidaten mit 14 Tagen Historie. Die Scorecard "
                "vergibt \u201eKaufkandidat\u201c bewusst selten \u2013 es kann einige "
                "Wochen dauern, bis genug F\u00e4lle zusammenkommen.")

    # === TRENNT DIE SCORECARD? (Treffer vs. Kontrollgruppe) ===
    st.markdown('<div class="sec-title" style="margin-top:18px">\u2696\ufe0f '
                'TRENNT DIE AUSWAHL? (Gegenprobe)</div>', unsafe_allow_html=True)
    try:
        disc = tr.discrimination(rows)
    except Exception as e:
        disc = None
        st.caption(f"(Gegenprobe nicht verf\u00fcgbar: {e})")
    if disc and disc.get("gut") and disc.get("schlecht"):
        _g, _s, _sp = disc["gut"], disc["schlecht"], disc["spread"]
        _dc = st.columns(3)
        card(_dc[0], "Treffer (Screener/Radar)", f"{_g['avg_ret']:+.1f} %",
             f"{_g['n']} Signale \u00b7 {_g['win_pct']} % im Plus",
             "var(--green)" if _g["avg_ret"] >= 0 else "var(--red)")
        card(_dc[1], "Kontrollgruppe (schwach)", f"{_s['avg_ret']:+.1f} %",
             f"{_s['n']} Signale \u00b7 als Short: {-_s['avg_ret']:+.1f} %",
             "var(--red)" if _s["avg_ret"] >= 0 else "var(--green)")
        card(_dc[2], "Abstand", f"{_sp:+.1f} Pp.", disc["urteil"],
             "var(--green)" if _sp > 5 else
             ("var(--red)" if _sp < -5 else "var(--amber)"))
        st.caption("Die Kontrollgruppe sind bewusst erfasste **schwache** Setups "
                   "(niedriger Score oder negatives Potenzial). Nur der ABSTAND "
                   "z\u00e4hlt: Im steigenden Markt gewinnt fast alles \u2013 eine hohe "
                   "Trefferquote allein beweist nichts. Kein Anlagerat.")
    else:
        st.info("Die Gegenprobe braucht schwache Setups mit \u2265 14 Tagen Historie. "
                "Der n\u00e4chtliche Lauf erfasst sie ab jetzt automatisch \u2013 die "
                "Auswertung erscheint in etwa zwei Wochen.")

    # === Funktioniert die SCORECARD? (die eigentliche Kernfrage) ===
    st.markdown('<div class="sec-title" style="margin-top:18px">\U0001f9ea '
                'FUNKTIONIERT DIE SCORECARD?</div>', unsafe_allow_html=True)
    st.caption("Schlagen \u201eKaufkandidat\u201c-Titel wirklich die \u201eVerwerfen\u201c-Titel? "
               "Nur wenn die besseren Urteile \u00fcber viele F\u00e4lle auch besser "
               "abschneiden, hat die Scorecard bewiesen, dass sie etwas kann. "
               "Braucht Zeit und viele Signale \u2013 vorher ist die Aussage d\u00fcnn.")
    try:
        bv = tr.by_verdict(rows)
    except Exception as e:
        bv = {"groups": []}
        st.caption(f"(Scorecard-Auswertung nicht verf\u00fcgbar: {e})")
    if bv.get("groups"):
        _vcol = {"Kaufkandidat": "var(--green)", "Solide \u2013 Watchlist": "#9DCE57",
                 "Knapp \u2013 Watchlist": "var(--amber)", "Verwerfen": "var(--red)"}
        vdata = [{"Urteil": g["verdict"], "Signale": g["n"], "Win %": g["win_pct"],
                  "\u00d8 Rendite %": g["avg_ret"],
                  "\u00d8 vs. Index %": g["avg_excess"]} for g in bv["groups"]]
        vr_table(vdata, signed_cols=("\u00d8 Rendite %", "\u00d8 vs. Index %"),
                 height=min(len(vdata) * 40 + 46, 260))
        if bv.get("monotonic") is True:
            st.success("\u2705 Die Rangfolge stimmt: bessere Urteile \u2192 h\u00f6here "
                       "\u00dcberrendite. Das ist genau das erhoffte Muster (noch "
                       "vorl\u00e4ufig, aber ermutigend).")
        elif bv.get("monotonic") is False:
            st.warning("\u26a0\ufe0f Die Rangfolge stimmt (noch) nicht \u2013 bessere Urteile "
                       "schneiden nicht durchweg besser ab. Entweder ist die Stichprobe "
                       "zu klein, oder die Scorecard trennt nicht so gut wie gedacht. "
                       "Beides ist wertvoll zu wissen.")
    else:
        st.info("Noch keine reifen Signale mit Scorecard-Urteil. Der Nacht-Job "
                "schreibt ab jetzt zu jedem Signal das Urteil mit \u2013 nach einigen "
                "Wochen wird diese Tabelle aussagekr\u00e4ftig.")

    # === Kalibrierung: trifft ein hoher Score haeufiger? ===
    try:
        cal = tr.calibration(rows)
    except Exception:
        cal = {"bands": []}
    if cal.get("bands"):
        with st.expander("\U0001f4d0 Kalibrierung \u2013 trifft ein hoher Score h\u00e4ufiger?"):
            st.caption("Ein gut kalibriertes System zeigt: je h\u00f6her das Score-Band, "
                       "desto h\u00f6her Win % und \u00dcberrendite. Wenn nicht, sagt der "
                       "genaue Score-Wert weniger aus als gedacht.")
            cdata = [{"Score-Band": b["band"], "Signale": b["n"], "Win %": b["win_pct"],
                      "\u00d8 Rendite %": b["avg_ret"],
                      "\u00d8 vs. Index %": b["avg_excess"]} for b in cal["bands"]]
            vr_table(cdata, signed_cols=("\u00d8 Rendite %", "\u00d8 vs. Index %"),
                     height=min(len(cdata) * 40 + 46, 240))


def render_pf_stats():
    """Statistik im Logbuch: Gesamt-G/V (gruen/rot) und Win-Quote - offen (laufende
    Positionen, aus der zuletzt berechneten Analyse) und realisiert (aus dem Logbuch)."""
    st.markdown('<div class="sec-title">STATISTIK</div>', unsafe_allow_html=True)

    # --- Offene Positionen (von der Analyse-Ansicht hinterlegt) ---
    _o = st.session_state.get("pf_stats_open") or {}
    n_scored, n_wins = _o.get("scored", 0), _o.get("wins", 0)
    win_pct = (n_wins / n_scored * 100) if n_scored else None
    gain_open = _o.get("gain")
    cost_open = _o.get("cost") or 0
    gain_open_pct = (gain_open / cost_open * 100) if (gain_open is not None and cost_open) else None
    scored, wins = range(n_scored), range(n_wins)

    # --- Realisiert (Logbuch) ---
    try:
        log = store.get_pf_log()
    except Exception:
        log = []
    sells = [e for e in log if e.get("typ") == "Verkauf" and e.get("gv_eur") is not None]
    gain_real = sum(e["gv_eur"] for e in sells) if sells else None
    win_real = ((sum(1 for e in sells if e["gv_eur"] > 0) / len(sells) * 100)
                if sells else None)

    total = (gain_open or 0) + (gain_real or 0)

    def _sig(v):
        return "var(--green)" if (v or 0) >= 0 else "var(--red)"

    def _eur(v):
        return ("+" if (v or 0) >= 0 else "\u2212") + sym_eur(abs(v or 0))

    c = st.columns(4)
    card(c[0], "G/V offen",
         _eur(gain_open) if gain_open is not None else "\u2014",
         f"{gain_open_pct:+.1f} % auf Einsatz" if gain_open_pct is not None else "",
         _sig(gain_open))
    card(c[1], "Win % (offen)",
         f"{win_pct:.0f} %" if win_pct is not None else "\u2014",
         f"{len(wins)} von {len(scored)} im Plus" if scored else "kein Buy-in erfasst",
         "var(--green)" if (win_pct or 0) >= 50 else "var(--red)")
    card(c[2], "G/V realisiert",
         _eur(gain_real) if gain_real is not None else "\u2014",
         f"aus {len(sells)} Verk\u00e4ufen" if sells else "noch keine Verk\u00e4ufe",
         _sig(gain_real))
    card(c[3], "Win % (realisiert)",
         f"{win_real:.0f} %" if win_real is not None else "\u2014",
         f"{sum(1 for e in sells if e['gv_eur'] > 0)} von {len(sells)} Gewinner"
         if sells else "\u2014",
         "var(--green)" if (win_real or 0) >= 50 else "var(--red)")

    if gain_open is not None or gain_real is not None:
        st.markdown(
            f'<div style="margin-top:6px;font-size:17px">Gesamt (offen + realisiert): '
            f'<b style="color:{_sig(total)}">{_eur(total)}</b></div>',
            unsafe_allow_html=True)
    if not n_scored:
        st.caption("Offene Werte erscheinen, sobald ein Portfolio in der Ansicht "
                   "\u201eAnalyse\u201c geladen wurde.")
    st.caption("Win % = Anteil der Positionen bzw. protokollierten Verk\u00e4ufe im Plus. "
               "Realisierte Werte stammen aus dem Logbuch \u2013 sie sind nur so "
               "vollst\u00e4ndig wie deine Eintr\u00e4ge. Kein Anlagerat.")


def render_hf_logbook():
    """Automatisches Logbuch: alle ausgefuehrten Trades ALLER Strategien."""
    try:
        hf = store.get_hf() or {}
    except Exception:
        hf = {}
    names = {"marktneutral": "Marktneutral", "130/30": "130/30",
             "quality_long": "Qualit\u00e4ts-Long", "core_ko": "Aktien + KO 3x",
             "screener_long": "Screener-Test"}
    entries = []
    for k, s in hf.items():
        for t in s.get("trades", []):
            entries.append({**t, "_strat": names.get(k, k)})
    if not entries:
        st.info("Noch keine Trades protokolliert. Sobald der automatische Lauf "
                "(2\u00d7 t\u00e4glich) oder \u201eJetzt pr\u00fcfen\u201c eine Position "
                "er\u00f6ffnet oder schlie\u00dft, erscheint sie hier.")
        return
    entries.sort(key=lambda e: -(e.get("ts") or 0))

    # ---------- Statistik ueber alle Strategien ----------
    closed = [e for e in entries if e.get("action") == "close"
              and e.get("pl_pct") is not None]
    wins = [e for e in closed if (e.get("pl_pct") or 0) > 0]
    win_pct = (len(wins) / len(closed) * 100) if closed else None
    gain_eur = sum(e.get("gain_eur") or 0 for e in closed) if closed else None
    avg_pct = (sum(e["pl_pct"] for e in closed) / len(closed)) if closed else None
    depot_val = sum(s.get("value_eur") or 0 for s in hf.values())
    depot_start = sum(s.get("start_capital") or 0 for s in hf.values())
    depot_ret = ((depot_val / depot_start - 1) * 100) if depot_start else None

    def _sig(v):
        return "var(--green)" if (v or 0) >= 0 else "var(--red)"

    def _eur(v):
        return ("+" if (v or 0) >= 0 else "\u2212") + sym_eur(abs(v or 0))

    st.markdown('<div class="sec-title">STATISTIK \u00b7 alle Strategien</div>',
                unsafe_allow_html=True)
    sc = st.columns(4)
    card(sc[0], "G/V realisiert",
         _eur(gain_eur) if gain_eur is not None else "\u2014",
         f"aus {len(closed)} geschlossenen Trades" if closed else "noch keine",
         _sig(gain_eur))
    card(sc[1], "Win %",
         f"{win_pct:.0f} %" if win_pct is not None else "\u2014",
         f"{len(wins)} von {len(closed)} im Plus" if closed else "\u2014",
         "var(--green)" if (win_pct or 0) >= 50 else "var(--red)")
    card(sc[2], "\u00d8 Trade",
         f"{avg_pct:+.1f} %" if avg_pct is not None else "\u2014",
         "Durchschnitt je Trade", _sig(avg_pct))
    card(sc[3], "Depotwert gesamt", sym_eur(depot_val),
         f"{depot_ret:+.1f} % seit Start" if depot_ret is not None else "",
         _sig(depot_ret))

    # Aufschluesselung je Strategie
    per = []
    for k, s in hf.items():
        cl = [t for t in s.get("trades", [])
              if t.get("action") == "close" and t.get("pl_pct") is not None]
        w = sum(1 for t in cl if t["pl_pct"] > 0)
        v0, v1 = s.get("start_capital") or 0, s.get("value_eur") or 0
        per.append({"Strategie": names.get(k, k),
                    "Wert \u20ac": round(v1, 2),
                    "Rendite %": round((v1 / v0 - 1) * 100, 2) if v0 else None,
                    "Trades": len(cl),
                    "Win %": round(w / len(cl) * 100) if cl else None,
                    "G/V \u20ac": round(sum(t.get("gain_eur") or 0 for t in cl), 2) if cl else None,
                    "Offen": len(s.get("positions", []))})
    if per:
        vr_table(per, signed_cols=("Rendite %", "G/V \u20ac"),
                 height=min(len(per) * 40 + 46, 260))
    st.caption("Realisiert = nur geschlossene Trades. Offene Positionen stecken im "
               "Depotwert. Papierhandel \u2013 ohne Geb\u00fchren, Spread und Leihkosten.")

    st.markdown('<div class="sec-title" style="margin-top:12px">TRADES</div>',
                unsafe_allow_html=True)
    fc = st.columns([1.3, 1.3, 1])
    strat_f = fc[0].selectbox("Strategie", ["alle"] + sorted({e["_strat"] for e in entries}),
                              key="hf_log_strat")
    act_f = fc[1].selectbox("Art", ["alle", "nur K\u00e4ufe/Er\u00f6ffnungen",
                                    "nur Verk\u00e4ufe/Schlie\u00dfungen"], key="hf_log_act")
    rows = [e for e in entries
            if (strat_f == "alle" or e["_strat"] == strat_f)
            and (act_f == "alle"
                 or (act_f.startswith("nur K\u00e4ufe") and e.get("action") == "open")
                 or (act_f.startswith("nur Verk") and e.get("action") == "close"))]
    fc[2].metric("Eintr\u00e4ge", len(rows))

    data = [{"Zeitpunkt": fmt_ts(e.get("ts")), "Strategie": e["_strat"],
             "Aktion": ("\U0001f7e2 Kauf" if e.get("action") == "open"
                        else "\U0001f534 Verkauf"),
             "Ticker": e.get("ticker", ""), "Richtung": e.get("dir", ""),
             "G/V %": e.get("pl_pct"), "G/V \u20ac": e.get("gain_eur"),
             "Grund": e.get("why", "")} for e in rows[:200]]
    vr_table(data, signed_cols=("G/V %", "G/V \u20ac"),
             height=min(len(data) * 40 + 46, 620))
    st.caption("Automatisch protokolliert bei jedem Lauf. \u201eGrund\u201c: Signal = "
               "neue Position \u00b7 Take-Profit / Stop-Loss / Gewinn-Stop / Knock-out = "
               "Schlie\u00dfung nach Regel.")
    try:
        st.download_button("\u2b07\ufe0f Als CSV",
                           pd.DataFrame(data).to_csv(index=False).encode("utf-8"),
                           "hedgefonds_logbuch.csv", "text/csv",
                           use_container_width=True)
    except Exception:
        pass


def render_pf_logbook():
    """Portfolio-Logbuch: Statistik + automatische Verkaeufe + manuelle Eintraege."""
    render_pf_stats()
    st.markdown('<div class="sec-title" style="margin-top:12px">TRANSAKTIONEN</div>',
                unsafe_allow_html=True)
    try:
        log = store.get_pf_log()
    except Exception:
        log = []

    with st.expander("\u2795 Transaktion manuell eintragen", expanded=not log):
        try:
            _pfs = store.names()
        except Exception:
            _pfs = []
        _cur = st.session_state.get("pf_cur_name", "")
        _opts = _pfs if _pfs else []
        _opts = _opts + ["\u2014 ohne Zuordnung \u2014"]
        _idx = _opts.index(_cur) if _cur in _opts else len(_opts) - 1
        m_pf = st.selectbox("Portfolio / Strategie", _opts, index=_idx, key="pfl_pf")
        c1 = st.columns([1, 1, 1])
        m_typ = c1[0].selectbox("Typ", ["Verkauf", "Kauf", "Dividende", "Sonstiges"],
                                key="pfl_typ")
        m_tk = c1[1].text_input("Ticker", key="pfl_tk", placeholder="z.B. AAPL")
        m_dt = c1[2].text_input("Datum", value=_berlin_now().strftime("%d.%m.%Y"),
                                key="pfl_dt")
        c2 = st.columns([1, 1, 1])
        m_qty = c2[0].text_input("Anzahl", key="pfl_qty", placeholder="St\u00fcck")
        m_px = c2[1].text_input("Kurs \u20ac", key="pfl_px", placeholder="je Aktie")
        m_gv = c2[2].text_input("G/V \u20ac (optional)", key="pfl_gv")
        m_note = st.text_input("Notiz", key="pfl_note",
                               placeholder="z.B. Teilverkauf, Gewinnmitnahme")
        if st.button("\U0001f4be Eintragen", use_container_width=True):
            if not (m_tk or "").strip():
                st.warning("Bitte einen Ticker angeben.")
            else:
                q, p = parse_eur(m_qty), parse_eur(m_px)
                store.pf_log_add({
                    "ts": time.time(), "datum": m_dt or "",
                    "portfolio": ("" if m_pf.startswith("\u2014") else m_pf),
                    "typ": m_typ, "ticker": m_tk.strip().upper(),
                    "anzahl": q, "kurs_eur": p,
                    "betrag_eur": round((q or 0) * (p or 0), 2) if (q and p) else None,
                    "gv_eur": parse_eur(m_gv), "notiz": (m_note or "").strip(),
                    "quelle": "manuell"})
                for k in ("pfl_tk", "pfl_qty", "pfl_px", "pfl_gv", "pfl_note"):
                    st.session_state.pop(k, None)
                st.rerun()

    if not log:
        st.info("Noch keine Eintr\u00e4ge. Verk\u00e4ufe \u00fcber den \u2715-Button in der "
                "Positionstabelle landen automatisch hier \u2013 oder oben manuell "
                "eintragen.")
        return

    # --- Filter nach Portfolio / Strategie ---
    _pf_vorhanden = sorted({(e.get("portfolio") or "").strip()
                            for e in log if (e.get("portfolio") or "").strip()})
    _log_gefiltert = log
    if _pf_vorhanden:
        _filter_opts = ["Alle"] + _pf_vorhanden + ["\u2014 ohne Zuordnung \u2014"]
        _f_pf = st.selectbox("Nach Portfolio filtern", _filter_opts,
                             key="pfl_filter")
        if _f_pf == "\u2014 ohne Zuordnung \u2014":
            _log_gefiltert = [e for e in log
                              if not (e.get("portfolio") or "").strip()]
        elif _f_pf != "Alle":
            _log_gefiltert = [e for e in log
                              if (e.get("portfolio") or "").strip() == _f_pf]

    data = [{"Datum": e.get("datum", ""), "Typ": e.get("typ", ""),
             "Ticker": e.get("ticker", ""), "Anzahl": e.get("anzahl"),
             "Kurs \u20ac": e.get("kurs_eur"), "Betrag \u20ac": e.get("betrag_eur"),
             "G/V \u20ac": e.get("gv_eur"), "Portfolio": e.get("portfolio", ""),
             "Quelle": e.get("quelle", ""), "Notiz": (e.get("notiz") or "")[:30]}
            for e in _log_gefiltert]
    if not data:
        st.info("Keine Eintr\u00e4ge f\u00fcr dieses Portfolio.")
        return
    vr_table(data, signed_cols=("G/V \u20ac",), height=min(len(data) * 40 + 46, 620))

    realized = sum(e.get("gv_eur") or 0 for e in _log_gefiltert
                   if e.get("typ") == "Verkauf")
    _hinweis = ("" if _log_gefiltert is log
                else " (gefiltert auf das gew\u00e4hlte Portfolio)")
    st.caption(f"Realisiertes Ergebnis aus protokollierten Verk\u00e4ufen{_hinweis}: "
               f"{'+' if realized >= 0 else '\u2212'}{sym_eur(abs(realized))} "
               "(nur aus den hier eingetragenen G/V-Werten \u2013 unvollst\u00e4ndig, wenn "
               "du Eintr\u00e4ge ohne G/V erfasst hast).")

    lc = st.columns([2, 1])
    try:
        lc[0].download_button("\u2b07\ufe0f Als CSV",
                              pd.DataFrame(data).to_csv(index=False).encode("utf-8"),
                              "portfolio_logbuch.csv", "text/csv",
                              use_container_width=True)
    except Exception:
        pass
    _del = lc[1].selectbox("Eintrag l\u00f6schen", ["\u2014"] + [
        f"{i+1}. {e.get('datum','')} {e.get('typ','')} {e.get('ticker','')}"
        for i, e in enumerate(log)], key="pfl_del")
    if _del != "\u2014" and st.button("\U0001f5d1\ufe0f L\u00f6schen",
                                      use_container_width=True):
        idx = int(_del.split(".")[0]) - 1
        if 0 <= idx < len(log):
            log.pop(idx)
            store.set_pf_log(log)
            st.rerun()


def positions_status(upside, ret_pct):
    """Ordnet eine Position in eines von vier Feldern ein - aus dem Zusammenspiel
    von Upside (lohnt der Kauf HEUTE noch?) und Position-Rendite (bin ich im
    Plus/Minus?). Gibt (symbol, kurztext) zurueck. KEIN Anlagerat - nur eine
    Sortierhilfe fuer die eigene Pruefung.

    Die Leitfrage bleibt immer: 'Wuerde ich zum heutigen Kurs neu kaufen?'
      Upside +, egal ob Position +/- : Tool sieht noch Potenzial -> These pruefen
      Upside -, Position +           : nicht mehr billig, aber im Gewinn
      Upside -, Position -           : beide Signale negativ -> genau pruefen
    """
    if upside is None:
        return ("", "")
    im_plus = (ret_pct is None) or (ret_pct >= 0)
    if upside >= 0 and im_plus:
        return ("\U0001f7e2", "Upside + / im Plus \u2013 laeuft")
    if upside >= 0 and not im_plus:
        return ("\U0001f535", "Upside + / im Minus \u2013 These pr\u00fcfen")
    if upside < 0 and im_plus:
        return ("\U0001f7e1", "Upside \u2212 / im Plus \u2013 nicht nachkaufen")
    return ("\U0001f534", "Upside \u2212 / im Minus \u2013 genau pr\u00fcfen")


def read_url(url, access=""):
    """Leitet Artikel hinter einer Paywall ueber removepaywall.com um.
    Format: https://removepaywall.com/<vollstaendige Original-URL>.
    Frei lesbare Artikel bleiben unveraendert (kein Umweg noetig)."""
    u = (url or "").strip()
    if not u or not u.startswith("http"):
        return u or "#"
    if str(access).lower() in ("paywall", "metered"):
        return "https://removepaywall.com/" + u
    return u


def display_upside(v, price):
    """EINE Upside-Logik fuer alle Oberflaechen (Einzelanalyse, Portfolio,
    Watchlist): Modell-Upside, wenn der Fair Value nicht gekappt wurde; sonst
    Analysten-Kursziel als Rueckfall. Verhindert, dass dieselbe Aktie je nach
    Tab verschiedene Upsides zeigt."""
    capped = v.get("fair_value_capped")
    up_model = v.get("upside_pct")
    atgt = v.get("analyst_target")
    if up_model is not None and not capped:
        return up_model
    if atgt and price:
        return round((atgt / price - 1) * 100, 1)
    return up_model


def _vr_cell(c, v, score_cols, signed_cols):
    """Zellen-HTML fuer vr_rows (Format wie vr_table)."""
    num = isinstance(v, (int, float)) and not isinstance(v, bool)
    cls = "num" if num else ""
    if v is None or (num and isinstance(v, float) and pd.isna(v)):
        return f'<div class="{cls}"><span class="na">\u2014</span></div>'
    if c in score_cols and num:
        return (f'<div class="{cls}" style="color:{score_hex(v)};'
                f'font-weight:700">{v:.0f}</div>')
    if c in signed_cols and num:
        colr = "#3FB950" if v >= 0 else "#F85149"
        sgn = "+" if v >= 0 else "\u2212"
        return (f'<div class="{cls}" style="color:{colr};font-weight:700">'
                f'{sgn}{de(abs(v), 2)}</div>')
    if isinstance(v, float):
        return f'<div class="{cls}">{de(v, 2)}</div>'
    if isinstance(v, int):
        return f'<div class="{cls}">{v}</div>'
    return f'<div>{esc(str(v))}</div>'


def vr_rows(rows, key_prefix, score_cols=(), signed_cols=(), name_col="Name",
            nav="Einzelanalyse"):
    """Klickbare Profi-Liste: der ORANGENE TICKER ist der Link (oeffnet die
    Einzelanalyse direkt). Kopf & Zeilen nutzen dieselbe Spaltengeometrie."""
    if not rows:
        return
    other = [c for c in rows[0].keys() if c != "Ticker"]
    tmpl = " ".join("minmax(0,1.7fr)" if c == name_col else "minmax(0,1fr)"
                    for c in other)
    ratio = [1.0, max(len(other), 2) * 1.15]

    def _isnum(c):
        return any(isinstance(r.get(c), (int, float)) and not isinstance(r.get(c), bool)
                   for r in rows)
    hc = st.columns(ratio)
    hc[0].markdown('<div class="vr-th">Ticker</div>', unsafe_allow_html=True)
    hc[1].markdown('<div class="vr-lg" style="grid-template-columns:' + tmpl + '">'
                   + "".join(f'<div class="vr-th{" num" if _isnum(c) else ""}">'
                             f'{esc(str(c))}</div>' for c in other)
                   + '</div>', unsafe_allow_html=True)
    for i, r in enumerate(rows):
        tk = str(r.get("Ticker") or "")
        # KEINE Pro-Zeilen-st.container(key=...): Streamlit gruppiert Keyed-
        # Container und zerreisst sonst die Liste. Nur st.columns (sequenziell).
        rc = st.columns(ratio)
        if rc[0].button(tk or "\u2014", key=f"tkbtn_{key_prefix}_{i}",
                        use_container_width=True):
            st.session_state["pending_search"] = tk
            st.session_state["pending_nav"] = nav
            st.rerun()
        rc[1].markdown('<div class="vr-lg" style="grid-template-columns:' + tmpl + '">'
                       + "".join(_vr_cell(c, r.get(c), score_cols, signed_cols)
                                 for c in other)
                       + '</div>', unsafe_allow_html=True)


def _trend_metrics(closes):
    """200-Tage-Linie, Momentum (20/60T) und annualisierte 30T-Volatilitaet.
    Entscheidend fuer Shorts: NICHT gegen einen laufenden Aufwaertstrend shorten."""
    import statistics
    cl = [float(c) for c in (closes or []) if c and c > 0]
    if len(cl) < 30:
        return {}
    price = cl[-1]
    sma200 = sum(cl[-200:]) / min(len(cl), 200)
    mom20 = (cl[-1] / cl[-21] - 1) if len(cl) > 21 else None
    mom60 = (cl[-1] / cl[-61] - 1) if len(cl) > 61 else None
    rets = [cl[i] / cl[i - 1] - 1 for i in range(max(1, len(cl) - 30), len(cl))]
    vol = (statistics.pstdev(rets) * (252 ** 0.5) * 100) if len(rets) > 2 else None
    return {"sma200": sma200, "above_sma": price > sma200,
            "mom20": mom20, "mom60": mom60, "vol": vol}


@st.cache_data(ttl=1800, show_spinner=False)
def longshort_candidates(regions, min_mcap_eur_bn, size):
    """Einheitlicher Long/Short-Screen ueber ein begrenztes Universum (flache
    Datentiefe, um API-Limits zu schonen). Rueckgabe: (longs, shorts).

    LONG  = Qualitaet hoch + klarer Bewertungs-Upside + kein Absturz-Momentum.
    SHORT = deutlich ueberbewertet + schwaechere Qualitaet + KEIN starker
            Aufwaertstrend (sonst Squeeze-Gefahr). Volatilitaet = nur Kontext.
    """
    tickers, _src = load_universe(regions, min_mcap_eur_bn, size)
    # ---- Doppelnotierungen entfernen (Schicht 1: bekannte Doppelklassen) ----
    # Gleiche Firma, zwei Aktienklassen (z.B. Alphabet GOOGL/GOOG). Wir behalten
    # nur EINE - bevorzugt die stimmberechtigte / liquidere Klasse.
    _DOPPELKLASSEN = {
        "GOOG": "GOOGL", "GOOGL": "GOOGL",     # Alphabet -> A-Aktie behalten
        "BRK.B": "BRK.A", "BRK.A": "BRK.A", "BRK-B": "BRK.A", "BRK-A": "BRK.A",
        "BRKB": "BRK.A", "BRKA": "BRK.A",
        "FOX": "FOXA", "FOXA": "FOXA",          # Fox
        "NWS": "NWSA", "NWSA": "NWSA",          # News Corp
        "UAA": "UA", "UA": "UA",                # Under Armour
        "LEN.B": "LEN", "LEN": "LEN",           # Lennar
        "HEI.A": "HEI", "HEI": "HEI",           # Heico
    }
    _gesehen_klasse = set()
    _bereinigt = []
    for t in tickers:
        _kanon = _DOPPELKLASSEN.get(t.upper())
        if _kanon:
            if _kanon in _gesehen_klasse:
                continue          # zweite Klasse derselben Firma -> raus
            _gesehen_klasse.add(_kanon)
        _bereinigt.append(t)
    tickers = _bereinigt

    try:
        import hedgefund as _hf
        _gate = _hf._quality_gate
    except Exception:
        _gate = None
    longs, shorts = [], []
    _gesehen_namen = {}      # Schicht 2: Dedup nach Firmenname (ISIN-aehnlich)
    for t in tickers:
        f = load_fundamentals(t)
        price = f.get("price")
        if not price:
            continue
        # Schicht 2: Dedup nach ISIN bzw. normalisiertem Firmennamen. Faengt
        # Doppelnotierungen ab, die nicht in der Klassen-Tabelle stehen
        # (z.B. gleiche Firma an zwei Boersen, unbekannte Doppelklassen).
        _isin = f.get("isin")
        _nm = (f.get("name") or "").strip().lower()
        # Namen normalisieren: Rechtsformen/Klassenzusaetze entfernen
        for _suffix in (" inc", " corp", " co", " ltd", " plc", " ag", " sa",
                        " nv", " class a", " class b", " class c", " cl a",
                        " cl b", " a", " b", " c", ".", ","):
            if _nm.endswith(_suffix):
                _nm = _nm[:-len(_suffix)].strip()
        _key = _isin or _nm
        if _key:
            if _key in _gesehen_namen:
                continue          # gleiche Firma schon gesehen -> ueberspringen
            _gesehen_namen[_key] = t
        ep = valuation.classify_playbook(f)
        s = scoring.score_stock(f, None, preset=ep)
        comp = s.get("composite")
        v = valuation.fair_value(f, None, ep)
        up = display_upside(v, price)
        if comp is None or up is None:
            continue
        # Datenqualitaets-Gate: fehlende Kennzahlen werden im Scoring mit 50
        # aufgefuellt -> ohne diese Pruefung rutschen datenarme Notierungen durch.
        if _gate is not None:
            # Flache Daten -> mildere Schwelle (4/9). Das Depot pruft spaeter tief.
            _ok, _why = _gate(f, s, v, "long" if up >= 0 else "short", min_groups=4)
            if not _ok:
                continue
        hist = load_history_full(t)
        tm = _trend_metrics(list(hist["Close"])) if (hist is not None and not hist.empty) else {}
        above = tm.get("above_sma")
        mom20, mom60, vol = tm.get("mom20"), tm.get("mom60"), tm.get("vol")
        fx = fx_to_eur(f.get("currency", "USD")) or 1.0
        trend = ("\u2191 \u00fcber 200T" if above else "\u2193 unter 200T") if above is not None else "\u2014"

        # NEU: wissenschaftliche Fundamental-Scores (Piotroski/Altman/Beneish)
        _sc = load_scores(t, {"sector": f.get("sector"),
                              "market_cap": f.get("market_cap"),
                              "_ist_bank": f.get("_ist_bank")})
        _fsc = _sc.get("f")
        _zsc = _sc.get("z")
        _msc = _sc.get("m")
        _f_score = _fsc.get("score") if _fsc else None
        _z_val = _zsc.get("z") if _zsc else None
        _m_val = _msc.get("m") if _msc else None
        # Short-Interest als Squeeze-Warnung
        _short_pct = f.get("short_pct_float")

        base = {"Ticker": t, "Name": (f.get("name") or "")[:18],
                "Kurs \u20ac": round(price * fx, 2), "Comp.": round(comp),
                "Upside %": round(up, 1),
                "F": _f_score if _f_score is not None else "\u2014",
                "Z": _z_val if _z_val is not None else "\u2014",
                "M": _m_val if _m_val is not None else "\u2014",
                "Vola %": round(vol) if vol else None, "Trend": trend}

        # ---------------------------------------------------------------
        # LONG: Qualitaet + Bewertungsabstand + fundamentale STAERKE.
        # Der Piotroski F-Score >= 7 filtert Value-Fallen (billige Titel,
        # die nur billig sind, weil sie kranken). Wenn kein F-Score da ist,
        # faellt die Logik auf die alte Regel zurueck (mildere Schwelle).
        # ---------------------------------------------------------------
        _long_basis = comp >= 58 and up >= 10 and (mom60 is None or mom60 > -0.20)
        if _long_basis:
            if _f_score is None or _f_score >= 7:
                # F-Score verstaerkt die Chance; ohne F etwas vorsichtiger
                _f_bonus = 0
                if _f_score is not None:
                    _f_bonus = (_f_score - 6) * 4    # 7->4, 8->8, 9->12
                lscore = comp * 0.6 + min(up, 60) * 0.5 + (6 if above else 0) + _f_bonus
                _tag = ("\u2b50 F%d" % _f_score) if _f_score is not None else ""
                longs.append({**base, "Chance": round(lscore), "Signal": _tag})

        # ---------------------------------------------------------------
        # SHORT: ueberbewertet + schwaechere Qualitaet + FORENSISCHE
        # Warnsignale (niedriger Altman Z ODER hoher Beneish M) + kein
        # starker Aufwaertstrend (Squeeze-Schutz). Nur eine Kombination aus
        # Ueberbewertung UND echtem fundamentalem Problem ist ein Short-Fit.
        # ---------------------------------------------------------------
        if up <= -20 and comp <= 52:
            strong_uptrend = bool(above and (mom60 or 0) > 0.15)
            rolling_over = (mom20 or 0) < 0
            # forensisches Warnsignal?
            _z_warn = (_z_val is not None and _z_val < 1.81)      # Pleiterisiko
            _m_warn = (_m_val is not None and _m_val > -2.22)     # Manipulation
            _forensik = _z_warn or _m_warn
            # Squeeze-Gefahr: hohe Short-Interest
            _squeeze = (_short_pct is not None and _short_pct > 0.10)
            if (not strong_uptrend and (not above or rolling_over)
                    and not _squeeze):
                # Grundfit; forensische Warnung erhoeht ihn deutlich
                sscore = (-up) * 0.5 + (60 - comp) * 0.4 \
                    + (10 if rolling_over else 0) - (15 if above else 0)
                if _forensik:
                    sscore += 20
                _warnung = []
                if _z_warn:
                    _warnung.append("Z<1.8 Pleiterisiko")
                if _m_warn:
                    _warnung.append("M>-2.22 Bilanz?")
                shorts.append({**base, "Risiko-Fit": round(sscore),
                               "Warnung": " \u00b7 ".join(_warnung) or "\u2014"})

    longs.sort(key=lambda r: -r["Chance"])
    shorts.sort(key=lambda r: -r["Risiko-Fit"])
    return longs[:15], shorts[:15]


def hedgefund_proposal(longs, shorts, strategy, capital_eur):
    """Baut aus den Long/Short-Kandidaten einen Portfolio-Vorschlag nach einer
    klassischen Hedgefonds-Strategie. Rein regelbasiert und deterministisch:
    Gewicht ~ Signalstaerke, gedeckelt (max 12 % je Position), normalisiert.

    Strategien:
      'marktneutral'  Long 100 % / Short 100 %  (Netto ~0: Marktrichtung egal,
                      es zaehlt nur Long-schlaegt-Short)
      '130/30'        Long 130 % / Short 30 %   (klassisch; braucht real Margin!)
      'quality_long'  Long 100 % / kein Short   (Qualitaets-Buch, kein Hebel)
    """
    LEGS = {"marktneutral": (1.0, 1.0), "130/30": (1.3, 0.3),
            "quality_long": (1.0, 0.0)}
    long_x, short_x = LEGS.get(strategy, (1.0, 0.0))

    def _book(rows, key, budget, n_max=8):
        rows = [r for r in rows if r.get("Kurs \u20ac")][:n_max]
        if not rows or budget <= 0:
            return [], 0.0
        raw = [max(float(r.get(key) or 0), 1.0) for r in rows]
        w = [x / sum(raw) for x in raw]
        cap_amt = 0.15 * capital_eur          # harter Klumpen-Deckel: 15 % je Position
        book = []
        for r, wi in zip(rows, w):
            amt = min(budget * wi, cap_amt)   # KEINE Renormalisierung: greift der
            shares = int(amt / r["Kurs \u20ac"])  # Deckel, bleibt Kapital uninvestiert
            book.append({"Ticker": r["Ticker"], "Name": r["Name"],
                         "Kurs \u20ac": r["Kurs \u20ac"], "Comp.": r.get("Comp."),
                         "Upside %": r.get("Upside %"), "Trend": r.get("Trend"),
                         "Gewicht %": round(amt / capital_eur * 100, 1),
                         "Betrag \u20ac": round(amt, 0), "St\u00fcck": shares})
        return book, sum(b["Betrag \u20ac"] for b in book)

    lbook, lsum = _book(longs, "Chance", capital_eur * long_x)
    sbook, ssum = _book(shorts, "Risiko-Fit", capital_eur * short_x)
    gross = (lsum + ssum) / capital_eur * 100 if capital_eur else 0
    net = (lsum - ssum) / capital_eur * 100 if capital_eur else 0

    def _wavg(book, key):
        tot = sum(b["Betrag \u20ac"] for b in book)
        vals = [(b.get(key), b["Betrag \u20ac"]) for b in book if b.get(key) is not None]
        return (sum(v * w for v, w in vals) / tot) if (tot and vals) else None
    return {"long": lbook, "short": sbook,
            "gross_pct": round(gross), "net_pct": round(net),
            "l_comp": _wavg(lbook, "Comp."), "l_up": _wavg(lbook, "Upside %"),
            "s_up": _wavg(sbook, "Upside %")}


def vr_table(rows, score_cols=(), signed_cols=(), height=None):
    """Professionelle dunkle Tabelle (eigenes HTML statt st.dataframe-Canvas):
    unabhaengig vom Streamlit-Theme, gleiche Optik auf Web & Mobile, innen
    horizontal scrollbar statt die Seite zu verbreitern.
    rows: Liste von dicts (gleiche Keys). score_cols: 0-100 farbig.
    signed_cols: +gruen/-rot mit Vorzeichen."""
    if not rows:
        return
    cols = list(rows[0].keys())
    num_cols = set()
    for c in cols:
        for r in rows:
            v = r.get(c)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                num_cols.add(c)
                break
    ths = "".join(f'<th class="{"num" if c in num_cols else ""}">{esc(str(c))}</th>'
                  for c in cols)
    body = ""
    for r in rows:
        tds = ""
        for c in cols:
            v = r.get(c)
            cls = "num" if c in num_cols else ""
            if v is None or (isinstance(v, float) and pd.isna(v)):
                tds += f'<td class="{cls}"><span class="na">\u2014</span></td>'
                continue
            if c in score_cols and isinstance(v, (int, float)):
                tds += (f'<td class="{cls}" style="color:{score_hex(v)};'
                        f'font-weight:700">{v:.0f}</td>')
            elif c in signed_cols and isinstance(v, (int, float)):
                colr = "#3FB950" if v >= 0 else "#F85149"
                sgn = "+" if v >= 0 else "\u2212"
                tds += (f'<td class="{cls}" style="color:{colr};font-weight:700">'
                        f'{sgn}{de(abs(v), 2)}</td>')
            elif isinstance(v, float):
                tds += f'<td class="{cls}">{de(v, 2)}</td>'
            elif isinstance(v, int):
                tds += f'<td class="{cls}">{v}</td>'
            elif c.lower() == "ticker":
                _tk = esc(str(v))
                tds += (f'<td><a href="?open={_tk}" target="_self" '
                        f'class="tick" style="text-decoration:none">{_tk}</a></td>')
            elif c == "\u2013\u2013":            # Aktionsspalte: kleiner Verkaufs-Button
                _sk = esc(str(v))
                tds += (f'<td style="text-align:center">'
                        f'<a href="?sell={_sk}" target="_self" class="sellbtn" '
                        f'title="{_sk} verkaufen (mit Best\u00e4tigung)">\u2715</a></td>'
                        if v else '<td></td>')
            else:
                tds += f'<td>{esc(str(v))}</td>'
        body += f"<tr>{tds}</tr>"
    hstyle = f'style="max-height:{height}px;overflow-y:auto"' if height else ""
    st.markdown(f'<div class="vr-twrap" {hstyle}><table class="vr-table">'
                f'<thead><tr>{ths}</tr></thead><tbody>{body}</tbody></table></div>',
                unsafe_allow_html=True)


def svg_hbars(pairs, color="#FFB000"):
    """pairs: Liste (label, wert%). Horizontale Balken."""
    pairs = [(str(k), float(v)) for k, v in pairs if v is not None]
    if not pairs:
        return "<span class='na'>n/a</span>"
    maxv = max(v for _, v in pairs) or 1.0
    W = 700
    barh, gap = 18, 12
    H = len(pairs) * (barh + gap) + 6
    lab_w, bar_x = 0.30 * W, 0.30 * W
    rows, y = "", 6
    for label, v in pairs:
        w = max(v, 0) / maxv * (W - bar_x - 60)
        rows += (
            f'<text x="0" y="{y+13}" fill="#9AA4B2" font-size="12" '
            f'font-family="monospace">{_svg_esc(label[:16])}</text>'
            f'<rect x="{bar_x:.0f}" y="{y}" width="{w:.1f}" height="{barh}" '
            f'fill="{color}" rx="2"/>'
            f'<text x="{bar_x + w + 6:.1f}" y="{y+13}" fill="#E6E1D3" font-size="12" '
            f'font-family="monospace">{v:.1f}%</text>')
        y += barh + gap
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" height="{H}" '
            f'style="display:block">{rows}</svg>')


# ---------------------------------------------------------------------------
# Landing-Page-Helfer: Index-Charts + automatische Hot-Picks
# ---------------------------------------------------------------------------
INDICES = [("S&P 500", "^GSPC"), ("Dow Jones", "^DJI"), ("Nasdaq", "^IXIC"),
           ("DAX", "^GDAXI"), ("Nikkei 225", "^N225")]


@st.cache_data(ttl=900, show_spinner=False)
def load_index(ticker):
    h = providers.get_price_history(ticker, period="1d", interval="5m")
    if h is None or getattr(h, "empty", True):
        h = providers.get_price_history(ticker, period="5d", interval="60m")
    if h is None or h.empty:
        return None
    return h[["Close"]].copy()          # DatetimeIndex fuer die Zeit-Achse behalten


def opportunity_score(composite, upside, reliable):
    """Verbindet Qualitaet (Composite) und Bewertung (Fair-Value-Upside) kohaerent.
    Nur verlaessliche Upsides verschieben den Score; gekappte/unsichere bleiben neutral."""
    base = composite or 0.0
    if reliable and upside is not None:
        base += max(min(upside, 40.0), -30.0) * 0.5     # +40% -> +20, -30% -> -15
    return max(0.0, min(100.0, base))


@st.cache_data(ttl=1800, show_spinner=False)
def home_radar_picks(n=10):
    # Radar gehoert auf Inflektions-/Breakout-Kandidaten, nicht auf Mega-Caps.
    universe = []
    seen = set()
    for lst in radar.THEMES.values():
        for t in lst:
            if t not in seen:
                seen.add(t)
                universe.append(t)
    loaded = []
    for t in universe:
        f = load_fundamentals(t)
        if f.get("price"):
            f["_fx"] = providers.get_fx_to_eur(f.get("currency", "USD")) or 1.0
            loaded.append(f)
    deduped = radar.dedupe_by_name(loaded)[:30]          # Rechenaufwand begrenzen
    res = []
    for f in deduped:
        t = f["ticker"]
        r = radar.compute(f, load_history_full(t), load_eps_rev(t), load_insider(t),
                          load_8k(t), load_event_news(t, f.get("name")))
        res.append({"ticker": t, "name": f.get("name"), "score": r["score"],
                    "firing": r["firing"], "sector": f.get("sector"),
                    "price_eur": round((f.get("price") or 0) * f["_fx"], 2)})
    res.sort(key=lambda x: x["score"], reverse=True)
    return res[:n]


@st.cache_data(ttl=1800, show_spinner=False)
def home_screener_picks(n=10, regions=("us", "de", "fr", "gb", "nl", "ch", "ca", "jp", "hk"),
                        min_score=55):
    tickers, _src = load_universe(tuple(regions), 5.0, max(60, n + 40))
    rows, names = [], set()
    for t in tickers:
        f = load_fundamentals(t)
        if not f.get("price"):
            continue
        f["_fx"] = providers.get_fx_to_eur(f.get("currency", "USD")) or 1.0
        ep = valuation.classify_playbook(f)
        comp = scoring.score_stock(f, None, preset=ep)["composite"]
        if (comp or 0) < min_score:                    # schwache Titel ausblenden
            continue
        v = valuation.fair_value(f, None, ep)
        capped = v.get("fair_value_capped")
        up = v.get("upside_pct") if not capped else None    # nur gekappte Extremwerte raus (fuer Score)
        up_anzeige = display_upside(v, f.get("price"))       # konsistente Anzeige ueberall
        reliable = v.get("reliable", False)
        rows.append({"ticker": f["ticker"], "name": f.get("name"), "sector": f.get("sector"),
                     "country": f.get("country"),
                     "price_eur": round((f.get("price") or 0) * f["_fx"], 2),
                     "score": comp, "upside": up_anzeige, "reliable": reliable, "capped": bool(capped),
                     "confidence": v.get("confidence"),
                     "opportunity": round(opportunity_score(comp, up, reliable), 1)})
    rows.sort(key=lambda r: (r["opportunity"] or 0), reverse=True)
    out = []
    for r in rows:
        nm = (r["name"] or r["ticker"]).lower()
        if nm in names:
            continue
        names.add(nm)
        out.append(r)
    return out[:n]


_GOLD_TICKERS = {"GLD", "IAU", "SGOL", "GLDM", "PHAU.L", "4GLD.DE", "EGLN.L",
                 "GC=F", "XAUUSD=X", "SLV", "PSLV", "SIVR", "GDX", "GDXJ",
                 "PHYS", "GOLD", "0GLD.DE", "WGLD.L"}


def build_portfolio_rows(records, inc_radar=False, inc_pl=True, live=False,
                         require_size=True):
    """records: Liste von {ticker, value, date}. Baut die angereicherten Zeilen
    fuer portfolio.analyze (Composite, Upside, Fair Value, Sektor, Land, optional
    Radar und Gewinn/Verlust seit Kauf). Loest Firmennamen automatisch zu Tickern auf.

    require_size=False -> auch Zeilen OHNE Anzahl/Wert (Watchlist!). Vorher wurden
    diese kommentarlos verworfen, weshalb die Watchlist immer leer blieb, obwohl
    die Titel gespeichert waren.
    Rueckgabe: (rows, invalid, resolved-mapping)."""
    import pandas as _pd
    rows, invalid, resolved = [], [], []
    for rec in records:
        raw = str(rec.get("ticker") or "").strip()
        val = parse_eur(rec.get("value"))
        shares = parse_eur(rec.get("shares"))
        has_val = val is not None and val > 0
        has_shares = shares is not None and shares > 0
        if not raw:
            continue
        if require_size and not has_val and not has_shares:
            continue
        tk = raw.upper()
        f = load_fundamentals_deep(tk)          # dieselbe Datentiefe wie Einzelanalyse
        if not f.get("price"):                  # -> identischer Composite/Upside
            mm = search_symbols(raw)
            if mm:
                tk = mm[0]["symbol"].upper()
                f = load_fundamentals_deep(tk)
                if tk != raw.upper():
                    resolved.append((raw, tk))
        if not f.get("price"):
            invalid.append(raw)
            continue
        native_cur = f.get("currency", "USD")
        fx = fx_to_eur(native_cur) or 1.0
        p_now = f.get("price")
        live_used = False
        if live:                                    # minutengenauer Kurs fuer Wert & G/V
            p_live, cur_live = load_intraday_quote(tk, native_cur)
            if p_live and p_live > 0:
                # Sicherung gegen einen falschen Live-Kurs. Zwei Faelle:
                #   - Pence statt Pfund (BP.L: 645 statt 6,45), Faktor ~100
                #   - falsche Boersennotierung desselben Kuerzels (PRU an der
                #     LSE statt NYSE), Faktor ~8
                # Beides zeigt sich als deutliche Abweichung vom bereits
                # korrekten Basiskurs. Toleranz 25 % (mehr als jede normale
                # Intraday-Bewegung); darueber wird der Basiskurs behalten.
                _basis = f.get("price")
                _ok = True
                if _basis and _basis > 0:
                    _v = p_live / _basis
                    _ok = 0.75 <= _v <= 1.25
                if _ok:
                    p_now = p_live
                    fx = fx_to_eur(cur_live) or 1.0   # Waehrung wandert nur
                    live_used = True                  # bei akzeptiertem Kurs mit
                # sonst: p_now, fx und Waehrung bleiben beim Basiskurs
        # Wert bestimmen: Stueckzahl x Kurs (exakt) hat Vorrang, sonst manueller Wert
        if has_shares and p_now:
            value_eur = shares * p_now * fx
        elif has_val:
            value_eur = val
        elif not require_size:
            value_eur = 0.0          # Watchlist: kein Bestand, aber gueltige Zeile
        else:
            invalid.append(raw)
            continue
        ep = valuation.classify_playbook(f)
        comp = scoring.score_stock(f, None, preset=ep)["composite"]
        v = valuation.fair_value(f, None, ep)
        capped = v.get("fair_value_capped")
        up_reliable = display_upside(v, f.get("price"))   # EINE Logik ueberall
        fv_reliable = v.get("fair_value") if not capped else None
        rscore = None
        if inc_radar:
            rr2 = radar.compute(f, load_history_full(tk), load_eps_rev(tk),
                                load_insider(tk), load_8k(tk),
                                load_event_news(tk, f.get("name")))
            rscore = rr2["score"]
        ret_pct = cost_eur = gain_eur = None
        price_eur = (p_now or 0) * fx
        if inc_pl:
            avg_buyin = parse_eur(rec.get("avg_buyin"))
            if avg_buyin and avg_buyin > 0 and price_eur:
                # Buy-in ist der EUR-Kaufkurs je Aktie (wie im Depot angezeigt).
                # G/V = aktueller EUR-Kurs vs. EUR-Kaufkurs -> erfasst Kurs- UND
                # Wechselkurs-Aenderung seit Kauf, genau wie im echten Depot.
                ret_pct = (price_eur / avg_buyin - 1) * 100
                if has_shares:
                    cost_eur = shares * avg_buyin                  # exakt, bereits EUR
            else:
                kd = rec.get("date")
                if kd is not None and (not _pd.isna(kd) if hasattr(_pd, "isna") else True):
                    try:
                        date_str = _pd.to_datetime(kd).date().isoformat()
                    except Exception:
                        date_str = None
                    if date_str:
                        p_then = load_price_on(tk, date_str)
                        if p_then and p_now and p_then > 0:
                            ret_pct = (p_now / p_then - 1) * 100   # Kursrendite (Handelswaehrung)
                            if has_shares:
                                cost_eur = shares * p_then * fx
            if ret_pct is not None:
                if cost_eur is None:
                    denom = 1 + ret_pct / 100
                    cost_eur = value_eur / denom if denom else None
                gain_eur = value_eur - cost_eur if cost_eur is not None else None
        # Instrumententyp: ETFs/Fonds/Rohstoffe (Gold) sind KEINE Einzelaktien und
        # sollen den Aktien-Gesamtscore nicht verwaessern (ein FTSE All-World hat
        # keinen sinnvollen "Composite" oder "Fair Value"). Erkennung ueber Yahoos
        # quoteType plus ein paar bekannte Gold-/Rohstoff-Ticker.
        _qt = str(f.get("type") or "").upper()
        _nm = (f.get("name") or "").upper()
        is_fund = _qt in ("ETF", "MUTUALFUND", "MONEYMARKET", "INDEX")
        is_commodity = (_qt in ("COMMODITY", "FUTURE")
                        or tk.upper() in _GOLD_TICKERS
                        or "GOLD" in _nm or "SILBER" in _nm or "SILVER" in _nm)
        # Zusaetzliche Erkennung ueber die Datenlage: Wenn KEINE einzige
        # Fundamentalkennzahl vorliegt (kein Umsatz, Gewinn, Marge, Buchwert),
        # ist es kein operatives Einzelunternehmen. Faengt Faelle, in denen die
        # Datenquelle keinen 'type' liefert - z.B. roic bei VWRL, das sonst
        # faelschlich als Aktie mit irrefuehrendem Score (~50) durchlief.
        _hat_fundamentaldaten = any(
            f.get(k) is not None for k in
            ("eps_trailing", "revenue", "operating_margin", "roe",
             "pe_trailing", "book_value_ps", "ebitda", "net_income"))
        if not _hat_fundamentaldaten and not is_commodity:
            is_fund = True
        is_single_stock = not (is_fund or is_commodity)
        # Score und Upside sind fuer Nicht-Aktien nicht aussagekraeftig - der
        # Composite fuellt fehlende Kennzahlen mit Mittelwerten auf und landet
        # dann bei ~50, was nichts misst. Fuer Fonds/Rohstoffe verwerfen.
        if not is_single_stock:
            comp = None
            up_reliable = None
            fv_reliable = None
        rows.append({
            "ticker": tk, "name": f.get("name"), "value_eur": float(value_eur),
            "raw": raw,          # urspruenglicher Eingabewert (fuer Loeschung/Match)
            "shares": shares if has_shares else None,
            "sector": f.get("sector"), "country": f.get("country"),
            "composite": comp, "upside": up_reliable,
            "instrument": ("ETF/Fonds" if is_fund else
                           "Rohstoff" if is_commodity else "Aktie"),
            "is_single_stock": is_single_stock,
            "price_eur": (p_now or 0) * fx, "live": live_used,
            "fair_value_eur": fv_reliable * fx if fv_reliable else None,
            "entry_eur": (v.get("entry_price") * fx) if v.get("entry_price") else None,
            "radar": rscore, "playbook": ep,
            "ret_pct": ret_pct, "cost_eur": cost_eur, "gain_eur": gain_eur})
    return rows, invalid, resolved


def pf_records_to_df(recs):
    if not recs:
        return None
    return pd.DataFrame([
        {"Ticker": r.get("ticker", ""),
         "Anzahl": ("" if r.get("shares") in (None, "") else str(r.get("shares"))),
         "\u00d8 Buy-in": ("" if r.get("avg_buyin") in (None, "") else str(r.get("avg_buyin"))),
         "Kaufdatum": (pd.to_datetime(r["date"]).date() if r.get("date") else None)}
        for r in recs])


def ticker_open_bar(tickers, key_prefix, nav="Einzelanalyse"):
    """Zeile klickbarer Ticker (kein Auswahl-Haken). Klick \u2192 \u00f6ffnet die Aktie."""
    seen, uniq = set(), []
    for t in tickers:
        t = str(t or "").strip()
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    if not uniq:
        return
    st.caption("\U0001f50e Ticker anklicken, um die Aktie zu \u00f6ffnen:")
    per = 8
    for start in range(0, len(uniq), per):
        chunk = uniq[start:start + per]
        cols = st.columns(per)
        for i, t in enumerate(chunk):
            if cols[i].button(t, key=f"{key_prefix}_{t}_{start}", use_container_width=True):
                st.session_state["pending_search"] = t
                st.session_state["pending_nav"] = nav
                st.rerun()


def portfolio_candidates(analysis, held_tickers, held_names):
    """Ergaenzungs-Ideen: solide Titel (Score >= 50) mit brauchbarem Bewertungs-
    Upside, aus breitem Laenderkreis. Gestaffelt, damit fast immer etwas erscheint:
    erst klar unterbewertet (>= +10%), sonst leicht unterbewertet (>= 0%), sonst die
    quaitativ besten mit nicht-gekapptem Fair Value. Gekappte Extremwerte fliegen raus."""
    pool = home_screener_picks(60, regions=("us", "de", "fr", "gb", "nl",
                                            "ch", "ca", "jp", "hk"), min_score=50)
    gaps = set(analysis["gaps"])
    dom_country = next(iter(analysis.get("country_alloc", {})), None)

    def usable(p):
        return (p["ticker"] not in held_tickers
                and (p["name"] or "").lower() not in held_names
                and not p.get("capped"))

    def rank(p):
        opp = p.get("opportunity") or 0
        bonus = 0
        if p.get("sector") in gaps:
            bonus += 6
        if dom_country and p.get("country") and p["country"] != dom_country:
            bonus += 3
        return opp + bonus

    base = [p for p in pool if usable(p)]
    strong = [p for p in base if (p.get("upside") or -999) >= 10]
    mild = [p for p in base if 0 <= (p.get("upside") or -999) < 10]
    rest = [p for p in base if p not in strong and p not in mild]  # Upside None oder < 0
    ordered = (sorted(strong, key=rank, reverse=True)
               + sorted(mild, key=rank, reverse=True)
               + sorted(rest, key=rank, reverse=True))
    if len(ordered) < 3:
        # Sicherheitsnetz: breiterer Scan ohne Score-Schwelle, rein nach Qualitaet -
        # es soll praktisch nie "keine Ideen" heissen.
        wide = home_screener_picks(60, regions=("us", "de", "fr", "gb", "nl", "ch",
                                                "ca", "jp", "hk", "au", "se"), min_score=0)
        extra = sorted([p for p in wide if usable(p)],
                       key=lambda p: (p.get("score") or 0), reverse=True)
        seen = {p["ticker"] for p in ordered}
        for p in extra:
            if p["ticker"] not in seen:
                ordered.append(p)
                seen.add(p["ticker"])
    return ordered[:6]


PAGES = ["Start", "News", "Einzelanalyse", "Aktienvergleich", "Radar",
         "Screener", "Momentum",
         "Watchlist", "Long/Short", "Portfoliocheck", "Trefferbilanz",
         "Earnings Calls", "Umfeld"]

# Kategorisierte Navigation: Ueberpunkte mit Unterpunkten. Der interne nav-Wert
# bleibt unveraendert (z.B. "Portfoliocheck"), nur das Label wird angezeigt.
# Ueberpunkte MIT Kindern sind selbst navigierbar (oeffnen eine eigene Seite)
# und zusaetzlich auf-/zuklappbar. Reihenfolge und Benennung wie gewuenscht.
NAV_GROUPS = [
    {"key": "Start", "label": "Start", "icon": "\U0001f3e0", "children": []},
    {"key": "News", "label": "News", "icon": "\U0001f4f0", "children": []},
    {"key": "Earnings Calls", "label": "Earnings Calls",
     "icon": "\U0001f399\ufe0f", "children": []},
    {"key": "AktienMarkt", "label": "Aktien und Markt Analyse",
     "icon": "\U0001f4ca", "children": [
        ("Einzelanalyse", "Einzelanalyse", "\U0001f4c8"),
        ("Aktienvergleich", "Aktienvergleich", "\u2696\ufe0f"),
        ("Radar", "Radar", "\U0001f3af"),
        ("Screener", "Screener", "\U0001f50d"),
        ("Momentum", "Momentum", "\U0001f680"),
        ("Umfeld", "Umfeld", "\U0001f30d"),
     ]},
    {"key": "MyValueApp", "label": "My Value App", "icon": "\U0001f4bc",
     "children": [
        ("Portfoliocheck", "Portfolio", "\U0001f4bc"),
        ("Watchlist", "Watchlist", "\u2b50"),
     ]},
    {"key": "StrategieStatistik", "label": "Strategie und Statistik",
     "icon": "\U0001f3c6", "children": [
        ("Trefferbilanz", "Trefferbilanz", "\U0001f3c6"),
        ("Long/Short", "Long/Short", "\u2696\ufe0f"),
        ("Backtest", "Backtest", "\U0001f9ea"),
        ("ThesenTrack", "Thesen-Bilanz", "\U0001f4dd"),
     ]},
]
# Ueberpunkte, die selbst eine eigene Seite haben (kein reiner Container).
# "AktienMarkt", "MyValueApp", "StrategieStatistik" sind eigene Landeseiten.
NAV_GROUP_SEITEN = {"AktienMarkt", "MyValueApp", "StrategieStatistik"}
# Auch die Ueberpunkt-Landeseiten sind gueltige nav-Ziele.
PAGES = PAGES + ["AktienMarkt", "MyValueApp", "StrategieStatistik"]
ICONS = {"Start": "\U0001f3e0", "Einzelanalyse": "\U0001f4c8", "Radar": "\U0001f3af",
         "Screener": "\U0001f50d", "Momentum": "\U0001f680",
         "Watchlist": "\u2b50", "Long/Short": "\u2696\ufe0f",
         "Portfoliocheck": "\U0001f4bc", "News": "\U0001f4f0",
         "Trefferbilanz": "\U0001f3c6", "Earnings Calls": "\U0001f399\ufe0f",
         "Umfeld": "\U0001f30d"}
_scroll_top_now = False
# Klick auf einen orangenen Ticker-Link (?open=TICKER) in einer vr_table:
# in die Einzelanalyse springen. Der Parameter wird sofort wieder entfernt.
try:
    _open_tk = st.query_params.get("open")
except Exception:
    _open_tk = None
try:
    _sell_tk = st.query_params.get("sell")
except Exception:
    _sell_tk = None
if _sell_tk:                                  # Verkaufs-Button in der Positionstabelle
    st.session_state["pf_confirm_sell"] = str(_sell_tk).upper()
    st.session_state["pending_nav"] = "Portfoliocheck"
    try:
        del st.query_params["sell"]
    except Exception:
        try:
            st.query_params.clear()
        except Exception:
            pass
if _open_tk:
    st.session_state["pending_search"] = str(_open_tk).upper()
    st.session_state["pending_nav"] = "Einzelanalyse"
    try:
        del st.query_params["open"]
    except Exception:
        try:
            st.query_params.clear()
        except Exception:
            pass
if "pending_nav" in st.session_state:
    st.session_state["nav"] = st.session_state.pop("pending_nav")
    _scroll_top_now = True                       # Link-Klick (auch Ticker/Peer) -> hoch
st.session_state.setdefault("nav", "Start")
nav = st.session_state["nav"]
if st.session_state.get("_last_nav") != nav:     # Tab-Wechsel -> hoch
    _scroll_top_now = True
    st.session_state["_last_nav"] = nav

# Mobile Top-Icon-Navigation: erscheint via CSS nur auf Handys, ganz oben, Rand
# zu Rand. Buttons OHNE st.columns - das CSS-Grid ordnet sie in 6 gleiche Zellen
# (robust gegen Streamlit-Versionswechsel). Icons statt Text: passt auf jedes Display.
MOBILE_NAV = {"Start": "\U0001f3e0", "News": "\U0001f4f0",
              "Einzelanalyse": "\U0001f4c8", "Aktienvergleich": "\u2696\ufe0f",
              "Radar": "\U0001f3af",
              "Screener": "\U0001f50d", "Momentum": "\U0001f680",
              "Watchlist": "\u2b50",
              "Long/Short": "\U0001f4c9", "Portfoliocheck": "\U0001f4bc",
              "Trefferbilanz": "\U0001f3c6", "Backtest": "\U0001f9ea",
              "ThesenTrack": "\U0001f4dd",
              "Earnings Calls": "\U0001f399\ufe0f",
              "Umfeld": "\U0001f30d"}
_mnav = st.container(key="mobilenav")
with _mnav:
    for _pg, _icon in MOBILE_NAV.items():
        if st.button(_icon, key=f"mnav_{_pg}", use_container_width=True,
                     help=_pg, type=("primary" if _pg == nav else "secondary")):
            # st.rerun() ist noetig: der restliche Seiteninhalt wurde in DIESEM
            # Durchlauf schon mit dem alten nav gezeichnet. Ohne Rerun muesste
            # man zweimal tippen, bis die neue Seite erscheint.
            if _pg != nav:
                st.session_state["nav"] = _pg
                st.rerun()

try:
    from assets_logo import LGI_LOGO_B64
    _logo_html = (f'<img src="data:image/png;base64,{LGI_LOGO_B64}" '
                  f'alt="Lohrer Global Investment">')
except Exception:
    _logo_html = ""

try:
    import precompute as _pcv
    _BUILD = getattr(_pcv, "CODE_VERSION", "?")
except Exception:
    _BUILD = "?"

st.markdown(
    '<div class="vr-head"><div class="logorow">' + _logo_html +
    '<div class="brand">VALUE RADAR <span class="caret">\u25ae</span></div></div>'
    '<div class="status">// vor die welle kommen &nbsp;\u00b7&nbsp; lokales terminal '
    '&nbsp;\u00b7&nbsp; anzeige in EUR &nbsp;\u00b7&nbsp; daten: yfinance'
    + ('  +finnhub' if config.FINNHUB_API_KEY else '')
    + ' &nbsp;\u00b7&nbsp; <span style="opacity:.7">Build ' + _BUILD + '</span></div></div>',
    unsafe_allow_html=True)

if _scroll_top_now:
    # Nach Navigation/Ticker-Klick zuverlaessig an den Seitenanfang springen.
    components.html(
        "<script>setTimeout(function(){try{"
        "var d=window.parent.document;"
        "var m=d.querySelector('section.main')||d.querySelector('[data-testid=\"stMain\"]');"
        "if(m){m.scrollTo({top:0,left:0,behavior:'auto'});}"
        "window.parent.scrollTo({top:0,behavior:'auto'});"
        "d.sessionStorage.setItem('vr_scroll','0');"     # gespeicherte Position zuruecksetzen
        "}catch(e){}},60);</script>", height=0)
else:
    # SCROLL-ERHALTUNG: Bei jeder Interaktion (Expander, Button, data_editor)
    # loest Streamlit einen Rerun aus und der Browser springt nach oben. Wir
    # merken die Scroll-Position laufend im sessionStorage und stellen sie nach
    # dem Rerun wieder her - AUSSER bei Tab-Wechsel/Link (dann greift der
    # Block oben). So bleibt die Ansicht dort, wo der Nutzer gerade war.
    components.html(
        "<script>(function(){try{"
        "var d=window.parent.document;"
        "var m=d.querySelector('section.main')||d.querySelector('[data-testid=\"stMain\"]');"
        "if(!m){return;}"
        # gespeicherte Position wiederherstellen
        "var y=parseInt(d.sessionStorage.getItem('vr_scroll')||'0',10);"
        "if(y>0){[50,150,300,500].forEach(function(t){setTimeout(function(){try{m.scrollTo({top:y,left:0,behavior:'auto'});}catch(e){}},t);});}"
        # laufend die aktuelle Position speichern
        "if(!m._vrScrollHook){m._vrScrollHook=true;"
        "m.addEventListener('scroll',function(){"
        "d.sessionStorage.setItem('vr_scroll',String(m.scrollTop));},{passive:true});}"
        "}catch(e){}})();</script>", height=0)

with st.sidebar:
    st.markdown('<div class="sec-title">NAVIGATION</div>', unsafe_allow_html=True)

    # Aufklapp-Zustand je Gruppe (Start: alles zugeklappt).
    _open_groups = st.session_state.setdefault("_nav_open", set())

    def _nav_button(_key, _label, _icon, _active, _indent=False):
        btype = "primary" if _active else "secondary"
        # Einrueckung ueber Key-Praefix + CSS (padding-left), NICHT ueber
        # Leerzeichen - die erzeugten den sichtbaren Kasten-Versatz.
        _pfx = "navsub" if _indent else "navtop"
        if st.button(_label, key=f"{_pfx}_{_key}",
                     use_container_width=True, type=btype):
            # st.rerun() noetig, sonst Doppelklick (Seite unten schon mit
            # altem nav gezeichnet).
            if not _active:
                st.session_state["nav"] = _key
                st.rerun()

    for grp in NAV_GROUPS:
        kinder = grp.get("children") or []
        if not kinder:
            # Einfacher Punkt ohne Unterpunkte
            _nav_button(grp["key"], grp["label"], grp["icon"], grp["key"] == nav)
            continue

        # Ueberpunkt MIT Kindern: EIN Button, Pfeil links IN der Box. Klick auf
        # die ganze Box klappt auf/zu. Navigiert wird ueber die Unterpunkte.
        offen = grp["key"] in _open_groups
        kind_keys = [k for k, _, _ in kinder]
        grp_aktiv = (nav == grp["key"]) or (nav in kind_keys)
        btype = "primary" if grp_aktiv else "secondary"
        # Pfeil als Zeichen IM Label (kein CSS-Targeting noetig - das griff in
        # deiner Streamlit-Version nicht). Der Key bleibt STABIL (nur grp-key),
        # sonst behandelt Streamlit den Button beim Umschalten als neuen und
        # der Klick geht verloren -> das war der Doppelklick.
        _car = "\u25be" if offen else "\u25b8"   # ▾ offen / ▸ zu
        # KEIN help= mehr: der Tooltip erzeugte einen zusaetzlichen Flex-
        # Wrapper (stTooltipHoverTarget), der den Button-Inhalt ZENTRIERTE -
        # nur die Ueberpunkte hatten dadurch eine andere DOM-Struktur und
        # blieben zentriert/ohne Hintergrund. Ohne help= ist die Struktur
        # identisch zu den Top-Punkten und das CSS greift ueberall gleich.
        if st.button(f"{_car} {grp['label']}",
                     key=f"navgrp_{grp['key']}",
                     use_container_width=True, type=btype):
            if offen:
                _open_groups.discard(grp["key"])
            else:
                _open_groups.add(grp["key"])
                if grp["key"] in NAV_GROUP_SEITEN:
                    st.session_state["nav"] = grp["key"]
            st.session_state["_nav_open"] = _open_groups
            st.rerun()
        # Unterpunkte nur zeigen, wenn aufgeklappt
        if offen:
            for _ckey, _clabel, _cicon in kinder:
                _nav_button(_ckey, _clabel, _cicon, _ckey == nav, _indent=True)
    st.markdown("---")


# Playbook laeuft immer automatisch im Hintergrund (nicht mehr in der UI)
preset = "Auto"


def resolve_preset(f):
    """Effektives Playbook: immer automatisch anhand Branche & Wachstum."""
    return valuation.classify_playbook(f)

# ===========================================================================
# START — Landing Page (Index-Charts, Hot Picks, Hot News)
# ===========================================================================
if nav == "Start":
    # --- Neue Hedgefonds-Trades (alle Strategien, letzte 48 h) ---
    try:
        _hfs = store.get_hf() or {}
    except Exception:
        _hfs = {}
    _sname = {"marktneutral": "Marktneutral", "130/30": "130/30",
              "quality_long": "Qualit\u00e4ts-Long", "core_ko": "Aktien + KO 3x",
             "screener_long": "Screener-Test"}
    _cut = time.time() - 48 * 3600
    _newtr = []
    for _k, _s in _hfs.items():
        for _t in _s.get("trades", []):
            if (_t.get("ts") or 0) >= _cut:
                _newtr.append({**_t, "_strat": _sname.get(_k, _k)})
    _newtr.sort(key=lambda e: -(e.get("ts") or 0))
    if _newtr:
        st.markdown('<div class="sec-title">\u2696\ufe0f NEUE TRADES '
                    '(Long/Short \u00b7 letzte 48 h)</div>', unsafe_allow_html=True)
        _td = [{"Zeit": fmt_ts(_t.get("ts")),
                "Aktion": ("\U0001f7e2 Kauf" if _t.get("action") == "open"
                           else "\U0001f534 Verkauf"),
                "Ticker": _t.get("ticker", ""),
                "Richtung": str(_t.get("dir", "")),
                "G/V %": _t.get("pl_pct"), "G/V \u20ac": _t.get("gain_eur"),
                "Strategie": _t["_strat"], "Grund": _t.get("why", "")}
               for _t in _newtr[:8]]
        vr_table(_td, signed_cols=("G/V %", "G/V \u20ac"),
                 height=min(len(_td) * 40 + 46, 380))
        if st.button("\u2696\ufe0f Zum Long/Short-Logbuch", use_container_width=True):
            st.session_state["pending_nav"] = "Long/Short"
            st.session_state["ls_view"] = "\U0001f4d3 Logbuch"
            st.rerun()
        st.markdown("---")

    # --- Neue Screener-/Radar-Signale (letzte 48 h) ---
    # Bisher zeigte die Startseite NUR Hedgefonds-Trades. Die Signale aus
    # Screener und Radar - die eigentliche Ideenquelle - tauchten hier gar
    # nicht auf, obwohl sie naechtlich erfasst werden.
    try:
        _sig = store.get_signals() or []
    except Exception:
        _sig = []
    _scut = time.time() - 48 * 3600
    _neu = [s for s in _sig
            if (s.get("ts") or 0) >= _scut and s.get("quelle") in ("Screener", "Radar")]
    _neu.sort(key=lambda e: -(e.get("ts") or 0))
    if _neu:
        st.markdown('<div class="sec-title">\U0001f195 NEUE SIGNALE '
                    '(Screener &amp; Radar \u00b7 letzte 48 h)</div>',
                    unsafe_allow_html=True)
        _sd = []
        for _s in _neu[:10]:
            _sd.append({
                "Zeit": fmt_ts(_s.get("ts")),
                "Quelle": ("\U0001f50e Screener" if _s.get("quelle") == "Screener"
                           else "\U0001f4e1 Radar"),
                "Ticker": _s.get("ticker", ""),
                "Score": _s.get("score"),
                "Upside %": _s.get("upside"),
                "Urteil": _s.get("verdict", "") or "\u2014",
                "Strategie": _s.get("strategie", "") or "\u2014",
            })
        vr_table(_sd, signed_cols=("Upside %",),
                 height=min(len(_sd) * 40 + 46, 420))
        st.caption("Frisch erfasste Signale des n\u00e4chtlichen Laufs. Sie werden "
                   "in der Trefferbilanz weiterverfolgt \u2013 belastbar erst ab "
                   "14 Tagen. Kein Anlagerat.")
        if st.button("\U0001f4c8 Zur Trefferbilanz", use_container_width=True,
                     key="start_to_tr"):
            st.session_state["pending_nav"] = "Trefferbilanz"
            st.rerun()
        st.markdown("---")

    # --- KI-Nacht-Briefing (Claude), falls vorhanden ---
    try:
        _brief = store.get_briefing()
    except Exception:
        _brief = ""
    if _brief:
        st.markdown('<div class="sec-title">\U0001f9e0 KI-BRIEFING</div>',
                    unsafe_allow_html=True)
        st.markdown(
            '<div class="news-box" style="border-left:3px solid var(--amber)">'
            + esc(_brief).replace("\n", "<br>")
            + '<div class="meta">Automatisch \u00fcber Nacht von Claude erstellt \u00b7 '
              'kein Anlagerat</div></div>', unsafe_allow_html=True)
        st.markdown("---")

    # --- Watchlist-Alarm: Titel in Kaufzone (aus dem Nacht-Snapshot, ohne Netz) ---
    try:
        _wl = set(store.get_watchlist())
        _snap = store.get_snapshot() if _wl else {}
        _bz = []
        for _t in _wl:
            _s = _snap.get(_t) if isinstance(_snap, dict) else None
            if _s and _s.get("entry") and _s.get("price") and _s["price"] <= _s["entry"]:
                _bz.append((_t, _s.get("price"), _s.get("entry")))
    except Exception:
        _bz = []
    if _bz:
        st.markdown('<div class="sec-title">\u2b50 WATCHLIST-ALARM</div>',
                    unsafe_allow_html=True)
        for _t, _p, _e in _bz:
            st.markdown(
                f'<div class="news-box" style="border-color:#3FB950;padding:8px 12px">'
                f'\U0001f3af <a href="?open={esc(_t)}" target="_self" class="tick" '
                f'style="text-decoration:none">{esc(_t)}</a> in Kaufzone \u2013 '
                f'Kurs \u2248{_p:.2f} \u2264 Einstieg \u2248{_e:.2f}'
                f'<div class="meta">Watchlist \u00b7 Stand letzte Nacht-Berechnung</div></div>',
                unsafe_allow_html=True)
        st.caption("Orangenen Ticker anklicken \u2192 Einzelanalyse. Kein Anlagerat.")
        st.markdown("---")

    # --- Was hat sich geaendert (aus dem Nacht-Job, falls vorhanden) ---
    try:
        _changes = store.get_changes()
    except Exception:
        _changes = []
    if _changes:
        st.markdown('<div class="sec-title">WAS HAT SICH GE\u00c4NDERT</div>',
                    unsafe_allow_html=True)
        _kind_icon = {"buyzone": "\U0001f3af", "composite": "\U0001f4ca",
                      "upside_flip": "\U0001f504", "upside_jump": "\U0001f4c8",
                      "radar": "\U0001f4e1", "new_idea": "\u2728"}
        st.caption("Breiter Marktscan \u00fcber alle Branchen und f\u00fcnf L\u00e4nder \u2013 "
                   "starke Spr\u00fcnge in Composite, Radar-Score oder Upside. "
                   "\U0001f4ca Composite \u00b7 \U0001f4e1 Radar \u00b7 \U0001f4c8 Upside \u00b7 "
                   "\U0001f3af Kaufzone. Nach Quelle gruppiert.")
        # Nach Quelle (section) gruppieren, damit die vielen Meldungen gestaffelt
        # und uebersichtlich in eigenen Tabellen erscheinen statt in einer langen
        # Liste. Reihenfolge: die eigenen Listen zuerst, dann der breite Markt.
        _sec_reihenfolge = ["Portfolio", "Watchlist", "Markt", "Screener", "Radar"]
        _sec_titel = {"Portfolio": "\U0001f4bc Portfolio", "Watchlist": "\U0001f440 Watchlist",
                      "Markt": "\U0001f30d Markt (Screener + Radar)",
                      "Screener": "\U0001f50d Screener", "Radar": "\U0001f4e1 Radar"}
        _gruppen = {}
        for _c in _changes:
            _gruppen.setdefault(_c.get("section") or "Sonstige", []).append(_c)
        # bekannte Sections in fester Reihenfolge, danach evtl. unbekannte
        _sortiert = [s for s in _sec_reihenfolge if s in _gruppen]
        _sortiert += [s for s in _gruppen if s not in _sec_reihenfolge]
        for _sec in _sortiert:
            _eintr = _gruppen[_sec]
            _titel = _sec_titel.get(_sec, "\U0001f4cc " + _sec)
            # alle Gruppen beim Start zugeklappt
            _auf = False
            with st.expander(f"{_titel}  ({len(_eintr)})", expanded=_auf):
                _rows = []
                for _c in _eintr:
                    _ic = _kind_icon.get(_c.get("kind"), "\u2022")
                    _rows.append({
                        "Wann": fmt_ts(_c.get("ts")) or "",
                        "": _ic,
                        "Ticker": str(_c.get("ticker") or ""),
                        "Name": (str(_c.get("name") or ""))[:22],
                        "\u00c4nderung": str(_c.get("text") or "")})
                vr_table(_rows, height=min(len(_rows) * 38 + 46, 420))
        st.caption("Automatisch \u00fcber Nacht berechnet \u00b7 kein Anlagerat. "
                   "Ticker in die Einzelanalyse eingeben f\u00fcr Details.")
        st.markdown("---")

    st.markdown("---")

    saved_all = store.load_all()
    if saved_all:
        st.markdown('<div class="sec-title">MEINE PORTFOLIOS</div>', unsafe_allow_html=True)
        st.caption("Mit aktuellen Kursen berechnet \u2013 dieselben Werte wie im "
                   "MyValueApp-Tab. \u201e\u00d6ffnen\u201c l\u00e4dt das Portfolio in den Check.")
        if True:
            def render_saved_portfolio(pname, precs):
                with st.spinner(f"Berechne {pname} ..."):
                    prows, _inv, _res = build_portfolio_rows(
                        precs, inc_radar=False, inc_pl=True, live=True)
                if not prows:
                    st.markdown(
                        f'<div class="news-box" style="font-size:12px"><b>{esc(pname)}</b>'
                        '<div class="meta">keine g\u00fcltigen Positionen</div></div>',
                        unsafe_allow_html=True)
                else:
                    an = pf.analyze(prows)
                    pvcol = {"buy": "var(--green)", "watch": "var(--amber)",
                             "drop": "var(--red)"}[an["vkey"]]
                    pl_line = ""
                    if an["have_pl"] and an["pl_return"] is not None:
                        g = an["pl_gain"]
                        gcol = "var(--green)" if g >= 0 else "var(--red)"
                        pl_line = (f'<div style="font-size:11px;color:{gcol}">G/V: '
                                   f'{an["pl_return"]:+.2f} % \u00b7 '
                                   f'{"+" if g >= 0 else "\u2212"}{sym_eur(abs(g))}</div>')
                    st.markdown(
                        f'<div class="news-box" style="font-size:12px;line-height:1.45">'
                        f'<b style="font-size:13px">{esc(pname)}</b> &nbsp;'
                        f'<b style="color:{pvcol}">{an["label"]} \u00b7 {an["score"]:.2f}/100</b>'
                        f'<div class="meta" style="font-size:11px">{sym_eur(an["total_eur"])} \u00b7 '
                        f'{an["n"]} Pos. \u00b7 gr\u00f6\u00dfte {an["max_pos"]*100:.2f} % \u00b7 '
                        f'{esc(an["max_sector_name"])} {an["max_sector"]*100:.2f} %</div>'
                        f'{pl_line}</div>', unsafe_allow_html=True)
                    prsort = sorted(prows, key=lambda r: -r["weight"])
                    pdata = [{"Ticker": r["ticker"], "Name": (r["name"] or "")[:16],
                              "Wert \u20ac": round(r["value_eur"], 2),
                              "Gew. %": round(r["weight"] * 100, 2),
                              "Sektor": (r["sector"] or "")[:12],
                              "Comp.": (round(r["composite"])
                                        if r.get("composite") is not None else None),
                              "Upside %": round(r["upside"], 2) if r.get("upside") is not None else None,
                              **({"Kauf %": round(r["ret_pct"], 2) if r.get("ret_pct") is not None else None}
                                 if an["have_pl"] else {}),
                              "Status": positions_status(
                                  r.get("upside"),
                                  r.get("ret_pct") if an["have_pl"] else None)[0]}
                             for r in prsort]
                    vr_table(pdata, score_cols=("Comp.",),
                             signed_cols=("Upside %", "Kauf %"),
                             height=min(len(pdata) * 38 + 46, 360))
                if st.button("\u00d6ffnen", key=f"open_pf_{pname}", use_container_width=True):
                    st.session_state["pf_pending_load"] = pname
                    st.session_state["pending_nav"] = "Portfoliocheck"
                    st.rerun()

            items = list(saved_all.items())
            for i in range(0, len(items), 2):       # zwei Portfolios pro Zeile nebeneinander
                cols = st.columns(2)
                for j, (pname, precs) in enumerate(items[i:i + 2]):
                    with cols[j]:
                        render_saved_portfolio(pname, precs)



# ===========================================================================
# UEBERPUNKT-SEITEN (kategorisierte Navigation)
# ===========================================================================
if nav == "AktienMarkt":
    st.markdown('<div class="sec-title">AKTIEN UND MARKT ANALYSE</div>',
                unsafe_allow_html=True)
    st.caption("W\u00e4hle links einen Unterpunkt \u2013 Einzelanalyse, Radar, "
               "Screener, Momentum oder Umfeld. Unten der Tagesverlauf der "
               "wichtigsten Indizes.")

    # Die 5 Index-Maerkte in EINER Reihe (kompakter als auf der alten Startseite)
    st.markdown('<div class="sec-title" style="margin-top:8px">M\u00c4RKTE '
                'HEUTE</div>', unsafe_allow_html=True)
    _mcols = st.columns(len(INDICES))
    for _col, (_nm, _tk) in zip(_mcols, INDICES):
        with _col:
            _h = load_index(_tk)
            if _h is None or _h.empty:
                st.markdown(f'<div style="font-weight:700;font-size:12px">{_nm}</div>'
                            '<span class="na">n/a</span>', unsafe_allow_html=True)
                continue
            _closes = list(_h["Close"])
            _times = list(_h.index)
            _b, _last = float(_closes[0]), float(_closes[-1])
            _pct = (_last / _b - 1) * 100 if _b else 0
            _hexc = "#3FB950" if _pct >= 0 else "#F85149"
            st.markdown(
                f'<div style="font-weight:700;font-size:12px">{_nm}</div>'
                f'<div style="color:{_hexc};font-size:14px;font-weight:700">'
                f'{_pct:+.2f} %</div>'
                + svg_index_chart(_closes, _times, _b, _hexc, height=96),
                unsafe_allow_html=True)
    st.caption("Tagesverlauf je Index \u00b7 gestrichelte Linie = Startwert (0 %).")

if nav == "MyValueApp":
    st.markdown('<div class="sec-title">MY VALUE APP</div>',
                unsafe_allow_html=True)
    st.caption("Deine gespeicherten Portfolios und die Watchlist. W\u00e4hle "
               "links Portfolio oder Watchlist \u2013 oder \u00f6ffne unten ein "
               "Portfolio direkt.")
    _saved_all = store.load_all()
    if not _saved_all:
        st.info("Noch keine Portfolios gespeichert. Lege im Portfoliocheck "
                "eines an.")
    else:
        st.markdown('<div class="sec-title" style="margin-top:8px">MEINE '
                    'PORTFOLIOS</div>', unsafe_allow_html=True)
        st.caption("Beim \u00d6ffnen neu berechnet.")

        def _render_pf_kachel(pname, precs):
            with st.spinner(f"Berechne {pname} ..."):
                prows, _inv, _res = build_portfolio_rows(precs, inc_radar=False,
                                                         inc_pl=True)
            if not prows:
                st.markdown(
                    f'<div class="news-box" style="font-size:12px"><b>{esc(pname)}</b>'
                    '<div class="meta">keine g\u00fcltigen Positionen</div></div>',
                    unsafe_allow_html=True)
            else:
                an = pf.analyze(prows)
                pvcol = ("#3FB950" if an["score"] >= 66 else
                         "#E3B341" if an["score"] >= 45 else "#F85149")
                pl_line = ""
                if an.get("have_pl") and an.get("pl_return") is not None:
                    g = an.get("pl_gain_eur") or 0
                    pl_line = (f'<div class="meta" style="font-size:11px">Kauf-Perf. '
                               f'{an["pl_return"]:+.2f} % \u00b7 '
                               f'{"+" if g >= 0 else "\u2212"}{sym_eur(abs(g))}</div>')
                st.markdown(
                    f'<div class="news-box" style="font-size:12px;line-height:1.45">'
                    f'<b style="font-size:13px">{esc(pname)}</b> &nbsp;'
                    f'<b style="color:{pvcol}">{an["label"]} \u00b7 {an["score"]:.2f}/100</b>'
                    f'<div class="meta" style="font-size:11px">{sym_eur(an["total_eur"])} \u00b7 '
                    f'{an["n"]} Pos. \u00b7 gr\u00f6\u00dfte {an["max_pos"]*100:.2f} % \u00b7 '
                    f'{esc(an["max_sector_name"])} {an["max_sector"]*100:.2f} %</div>'
                    f'{pl_line}</div>', unsafe_allow_html=True)
                prsort = sorted(prows, key=lambda r: -r["weight"])
                pdata = [{"Ticker": r["ticker"], "Name": (r["name"] or "")[:16],
                          "Wert \u20ac": round(r["value_eur"], 2),
                          "Gew. %": round(r["weight"] * 100, 2),
                          "Sektor": (r["sector"] or "")[:12],
                          "Comp.": (round(r["composite"])
                                    if r.get("composite") is not None else None),
                          "Upside %": round(r["upside"], 2) if r.get("upside") is not None else None,
                          **({"Kauf %": round(r["ret_pct"], 2) if r.get("ret_pct") is not None else None}
                             if an["have_pl"] else {}),
                          "Status": positions_status(
                              r.get("upside"),
                              r.get("ret_pct") if an["have_pl"] else None)[0]}
                         for r in prsort]
                vr_table(pdata, score_cols=("Comp.",),
                         signed_cols=("Upside %", "Kauf %"),
                         height=min(len(pdata) * 38 + 46, 360))
            if st.button("\u00d6ffnen", key=f"mva_open_pf_{pname}",
                         use_container_width=True):
                st.session_state["pf_pending_load"] = pname
                st.session_state["pending_nav"] = "Portfoliocheck"
                st.rerun()

        _items = list(_saved_all.items())
        for _i in range(0, len(_items), 2):
            _cols = st.columns(2)
            for _j, (_pname, _precs) in enumerate(_items[_i:_i + 2]):
                with _cols[_j]:
                    _render_pf_kachel(_pname, _precs)

if nav == "StrategieStatistik":
    st.markdown('<div class="sec-title">STRATEGIE UND STATISTIK</div>',
                unsafe_allow_html=True)
    st.caption("W\u00e4hle links einen Unterpunkt \u2013 Trefferbilanz "
               "(Signal-Tagebuch & Auto-Depot) oder Long/Short.")


# ===========================================================================
# EINZELANALYSE (Tabs: Analyse, Scorecard, Matrix 1, Matrix 2)
# ===========================================================================
if nav == "Aktienvergleich":
    st.markdown('<div class="sec-title">\u2696\ufe0f AKTIENVERGLEICH</div>',
                unsafe_allow_html=True)
    st.caption("Zwei oder drei Aktien nebeneinander \u2013 Scores, Kurse, Fair "
               "Value und Finanzkennzahlen im direkten Vergleich. Name oder "
               "Ticker eingeben. Kein Anlagerat.")

    _vc = st.columns(3)
    _t1 = _vc[0].text_input("Aktie 1", key="vgl_t1",
                            placeholder="z.B. NVDA")
    _t2 = _vc[1].text_input("Aktie 2", key="vgl_t2",
                            placeholder="z.B. AMD")
    _t3 = _vc[2].text_input("Aktie 3 (optional)", key="vgl_t3",
                            placeholder="z.B. AVGO")

    def _vgl_daten(roh):
        """Sammelt alle Vergleichswerte fuer einen Ticker. Nutzt exakt dieselbe
        Kette wie die Einzelanalyse (deep-Fundamentaldaten, Playbook, Score,
        Fair Value), damit die Zahlen konsistent sind."""
        tk = search_to_ticker(roh) if roh else None
        if not tk:
            return None
        try:
            f = load_fundamentals_deep(tk)
            if not f or not f.get("price"):
                return None
            ep = valuation.classify_playbook(f)
            sc = scoring.score_stock(f, None, preset=ep)
            v = valuation.fair_value(f, None, ep)
            cats = sc.get("category_scores", {})
            fv = v.get("fair_value_capped") or v.get("fair_value")
            price = f.get("price")
            # Quantum-Score wie in der Einzelanalyse (buendelt alle Sichten)
            try:
                _q = scoring.quantum_score(sc.get("composite"), v, None,
                                           momentum=cats.get("momentum"))
                _quantum = _q.get("score")
            except Exception:
                _quantum = None
            return {
                "ticker": tk, "name": f.get("name") or tk,
                "playbook": ep,
                "quantum": _quantum,
                "composite": sc.get("composite"),
                "quality": cats.get("quality"), "value": cats.get("value"),
                "growth": cats.get("growth"), "momentum": cats.get("momentum"),
                "price": price, "fair_value": fv,
                "upside": (round((fv / price - 1) * 100, 1)
                           if fv and price else None),
                "pe": f.get("pe_trailing"), "pb": f.get("pb"),
                "ev_ebitda": f.get("ev_ebitda"),
                "roe": f.get("roe"), "roa": f.get("roa"),
                "operating_margin": f.get("operating_margin"),
                "gross_margin": f.get("gross_margin"),
                "fcf_yield": f.get("fcf_yield"),
                "revenue_growth": f.get("revenue_growth"),
                "debt_to_equity": f.get("debt_to_equity"),
                "dividend_yield": f.get("dividend_yield"),
                "beta": f.get("beta"),
                "market_cap": f.get("market_cap"),
                "sector": f.get("sector"), "country": f.get("country"),
                # NEU: Solvenz/Qualitaets-Scores (Altman Z, Piotroski F, Moat)
                **(lambda _s: {
                    "altman_z": (_s.get("z") or {}).get("z") if _s.get("z") else None,
                    "altman_zone": (_s.get("z") or {}).get("zone") if _s.get("z") else None,
                    "piotroski_f": (_s.get("f") or {}).get("score") if _s.get("f") else None,
                    "moat_urteil": (_s.get("moat") or {}).get("moat_urteil") if _s.get("moat") else None,
                })(load_scores(tk, {"sector": f.get("sector"),
                                    "market_cap": f.get("market_cap"),
                                    "_ist_bank": f.get("_ist_bank")})),
                # bewertungskritische Felder AUCH mitspeichern, damit die
                # Datenquellen-Diagnose sie korrekt als vorhanden/roic erkennt
                # (sonst meldet sie faelschlich "fehlt", obwohl roic sie liefert).
                "book_value_ps": f.get("book_value_ps"),
                "eps_forward": f.get("eps_forward"),
                "free_cashflow": f.get("free_cashflow"),
                "ebitda": f.get("ebitda"),
                "net_debt": f.get("net_debt"),
                "target_mean": f.get("target_mean"),
                # Diagnose: Datenquellen-Herkunft (aendert keine Berechnung)
                "_roic_aktiv": bool(f.get("_roic")),
                "_roic_felder": f.get("_roic_felder") or [],
                "_data_sources": f.get("data_sources") or "",
            }
        except Exception:
            return None

    _eingaben = [x for x in (_t1, _t2, _t3) if x and x.strip()]
    if len(_eingaben) < 2:
        st.info("Mindestens zwei Aktien eingeben, um den Vergleich zu starten.")
    else:
        with st.spinner("Analysiere \u2026"):
            _daten = [d for d in (_vgl_daten(x) for x in _eingaben) if d]
        if len(_daten) < 2:
            st.warning("Konnte nicht genug Aktien laden \u2013 bitte Ticker/Namen "
                       "pr\u00fcfen (mind. zwei m\u00fcssen gefunden werden).")
        else:
            # Ampel-Bewertung je Kennzahl: gibt "gruen"/"gelb"/"rot"/None.
            # Schwellen bewusst einfach und transparent - eine grobe Einordnung,
            # kein Ersatz fuer die volle Scorecard der Einzelanalyse.
            def _ampel_kennzahl(key, wert):
                if not isinstance(wert, (int, float)):
                    return None
                # (gut_ab, mittel_ab) - je nach Richtung. hib=True: hoeher besser
                schwellen = {
                    "pe": (15, 25, False), "pb": (2, 4, False),
                    "ev_ebitda": (10, 16, False),
                    "roe": (0.15, 0.08, True), "roa": (0.07, 0.03, True),
                    "operating_margin": (0.18, 0.10, True),
                    "gross_margin": (0.40, 0.25, True),
                    "fcf_yield": (0.05, 0.02, True),
                    "revenue_growth": (0.10, 0.03, True),
                    "debt_to_equity": (0.6, 1.5, False),
                    "dividend_yield": (0.03, 0.01, True),
                }
                if key not in schwellen:
                    return None
                gut, mittel, hib = schwellen[key]
                # debt_to_equity kommt teils in % (yfinance) -> normalisieren
                if key == "debt_to_equity" and wert > 5:
                    wert = wert / 100.0
                if hib:
                    return ("gruen" if wert >= gut else
                            "gelb" if wert >= mittel else "rot")
                else:
                    return ("gruen" if wert <= gut else
                            "gelb" if wert <= mittel else "rot")

            def _kategorie_ampel(daten_eintrag, keys):
                """Aggregiert die Einzel-Ampeln einer Kategorie zu einer
                Gesamt-Ampel: ueberwiegend gruen -> gruen, ueberwiegend rot ->
                rot, sonst gelb."""
                amps = [_ampel_kennzahl(k, daten_eintrag.get(k)) for k in keys]
                amps = [a for a in amps if a]
                if not amps:
                    return None
                g = amps.count("gruen")
                r = amps.count("rot")
                if g > r and g >= len(amps) / 2:
                    return "gruen"
                if r > g and r >= len(amps) / 2:
                    return "rot"
                return "gelb"

            _amp_symbol = {"gruen": "\U0001f7e2", "gelb": "\U0001f7e1",
                           "rot": "\U0001f534"}

            # -----------------------------------------------------------
            # SCORE-UEBERSICHT im Stil "Bewertung / Profitabilitaet /
            # Solvenz" nebeneinander, mit BEST-Markierung je Kategorie.
            # -----------------------------------------------------------
            st.markdown("#### \u00dcberblick")

            def _prof_score(d):
                """0-100 Profitabilitaets-Score aus ROE, Marge, FCF-Rendite."""
                teile = []
                if isinstance(d.get("roe"), (int, float)):
                    teile.append(min(max(d["roe"] / 0.25, 0), 1))
                if isinstance(d.get("operating_margin"), (int, float)):
                    teile.append(min(max(d["operating_margin"] / 0.30, 0), 1))
                if isinstance(d.get("fcf_yield"), (int, float)):
                    teile.append(min(max(d["fcf_yield"] / 0.08, 0), 1))
                if isinstance(d.get("gross_margin"), (int, float)):
                    teile.append(min(max(d["gross_margin"] / 0.50, 0), 1))
                return round(sum(teile) / len(teile) * 100) if teile else None

            def _solv_score(d):
                """0-100 Solvenz-Score, primaer aus Altman Z, sonst D/E."""
                z = d.get("altman_z")
                if isinstance(z, (int, float)):
                    # Z 1.0 -> 0, Z 4.0 -> 100 (linear, gekappt)
                    return round(min(max((z - 1.0) / 3.0, 0), 1) * 100)
                de = d.get("debt_to_equity")
                if isinstance(de, (int, float)):
                    if de > 5:
                        de = de / 100.0
                    return round(min(max((1.5 - de) / 1.5, 0), 1) * 100)
                return None

            # Werte je Aktie berechnen
            for d in _daten:
                d["_prof"] = _prof_score(d)
                d["_solv"] = _solv_score(d)
            # BEST je Kategorie bestimmen (hoechster Wert)
            def _best_idx(werte):
                gultig = [(i, w) for i, w in enumerate(werte) if isinstance(w, (int, float))]
                return max(gultig, key=lambda x: x[1])[0] if gultig else None
            _best_up = _best_idx([d.get("upside") for d in _daten])
            _best_prof = _best_idx([d.get("_prof") for d in _daten])
            _best_solv = _best_idx([d.get("_solv") for d in _daten])

            _ocols = st.columns(len(_daten))
            for _i, (d, _col) in enumerate(zip(_daten, _ocols)):
                with _col:
                    st.markdown(f"**{d['name'][:20]}** \u00b7 {d['ticker']}")
                    # Bewertung
                    _up = d.get("upside")
                    if isinstance(_up, (int, float)):
                        _uptxt = ("%.0f%% unterbewertet" % _up if _up > 0
                                  else "%.0f%% \u00fcberbewertet" % abs(_up))
                        _best1 = " \U0001f3c6" if _i == _best_up else ""
                        st.markdown(f"Bewertung: **{_uptxt}**{_best1}")
                    # Profitabilitaet
                    if d.get("_prof") is not None:
                        _best2 = " \U0001f3c6" if _i == _best_prof else ""
                        st.markdown(f"Profitabilit\u00e4t: **{d['_prof']}/100**{_best2}")
                    # Solvenz
                    if d.get("_solv") is not None:
                        _best3 = " \U0001f3c6" if _i == _best_solv else ""
                        _zone = d.get("altman_zone")
                        _ztxt = (f" ({_zone})" if _zone else "")
                        st.markdown(f"Solvenz: **{d['_solv']}/100**{_best3}{_ztxt}")
                    # Moat + F-Score als Zusatz
                    _mo = d.get("moat_urteil")
                    if _mo:
                        _mo_sym = {"breit": "\U0001f7e2 breit", "schmal": "\U0001f7e1 schmal",
                                   "keiner": "\U0001f534 keiner"}.get(_mo, _mo)
                        st.markdown(f"Burggraben: {_mo_sym}")
                    _pf = d.get("piotroski_f")
                    if _pf is not None:
                        st.markdown(f"Piotroski F: **{_pf}/9**")
            st.caption("\U0001f3c6 = bester Wert der Auswahl je Kategorie. "
                       "Profitabilit\u00e4t/Solvenz als 0\u2013100 zusammengefasst. "
                       "Details in der Tabelle unten.")
            st.markdown("---")
            # welche keys gehoeren zu welcher Kategorie-Ueberschrift
            _kat_keys = {
                "Bewertungskennzahlen": ["pe", "pb", "ev_ebitda"],
                "Profitabilit\u00e4t": ["roe", "roa", "operating_margin",
                                        "gross_margin", "fcf_yield"],
                "Wachstum & Bilanz": ["revenue_growth", "debt_to_equity",
                                       "dividend_yield"],
            }

            def _pct(x): return f"{x*100:.1f} %" if isinstance(x, (int, float)) else "\u2014"
            def _num(x, d=2): return f"{x:.{d}f}" if isinstance(x, (int, float)) else "\u2014"
            def _mc(x):
                if not isinstance(x, (int, float)):
                    return "\u2014"
                return f"{x/1e9:.1f} Mrd" if x < 1e12 else f"{x/1e12:.2f} Bio"

            # Zeilen: (Label, key, Formatierer, hoeher-ist-besser|None)
            _zeilen = [
                ("__H__", "Bewertung / Scores", None, None),
                ("Quantum-Score", "quantum", lambda x: _num(x, 0), True),
                ("Composite", "composite", lambda x: _num(x, 0), True),
                ("Qualit\u00e4t", "quality", lambda x: _num(x, 0), True),
                ("Value", "value", lambda x: _num(x, 0), True),
                ("Growth", "growth", lambda x: _num(x, 0), True),
                ("Momentum", "momentum", lambda x: _num(x, 0), True),
                ("__H__", "Kurs & Fair Value", None, None),
                ("Kurs", "price", lambda x: _num(x, 2), None),
                ("Fair Value", "fair_value", lambda x: _num(x, 2), None),
                ("Upside", "upside", lambda x: (f"{x:+.1f} %"
                          if isinstance(x, (int, float)) else "\u2014"), True),
                ("Playbook", "playbook", lambda x: str(x), None),
                ("__H__", "Bewertungskennzahlen", None, None),
                ("KGV (P/E)", "pe", lambda x: _num(x, 1), False),
                ("KBV (P/B)", "pb", lambda x: _num(x, 2), False),
                ("EV/EBITDA", "ev_ebitda", lambda x: _num(x, 1), False),
                ("__H__", "Profitabilit\u00e4t", None, None),
                ("Eigenkapitalrendite", "roe", _pct, True),
                ("Gesamtkapitalrendite", "roa", _pct, True),
                ("Operative Marge", "operating_margin", _pct, True),
                ("Bruttomarge", "gross_margin", _pct, True),
                ("Free-Cashflow-Rendite", "fcf_yield", _pct, True),
                ("__H__", "Wachstum & Bilanz", None, None),
                ("Umsatzwachstum", "revenue_growth", _pct, True),
                ("Verschuldung (D/E)", "debt_to_equity",
                 lambda x: _num(x, 2), False),
                ("Dividendenrendite", "dividend_yield", _pct, True),
                ("Beta", "beta", lambda x: _num(x, 2), None),
                ("Marktkap.", "market_cap", _mc, None),
                ("Sektor", "sector", lambda x: str(x)[:20] if x else "\u2014", None),
            ]

            # Kurzbeschreibungen je Kennzahl fuer das Info-Icon (Hover-Tooltip).
            # Max. zwei Saetze - erklaert die Kennzahl und, wo relevant, warum
            # sie bei manchen Firmen (z.B. Banken) fehlt.
            _info = {
                "quantum": "Gesamtnote des Tools (0\u2013100), die Qualit\u00e4t, "
                           "Bewertung und Momentum b\u00fcndelt. H\u00f6her ist besser.",
                "composite": "Fundamentaler Gesamtscore aus Qualit\u00e4t, Bewertung, "
                             "Wachstum und Momentum (0\u2013100).",
                "quality": "Bilanz- und Ertragsqualit\u00e4t: Rendite, Margen, "
                           "Verschuldung. H\u00f6her = solider.",
                "value": "Wie g\u00fcnstig die Aktie relativ zu ihren Fundamentaldaten "
                         "ist. H\u00f6her = g\u00fcnstiger bewertet.",
                "growth": "Wachstumsdynamik bei Umsatz und Gewinn. H\u00f6her = "
                          "st\u00e4rkeres Wachstum.",
                "momentum": "Kursst\u00e4rke relativ zur eigenen 52-Wochen-Spanne. "
                            "H\u00f6her = n\u00e4her am Jahreshoch.",
                "price": "Aktueller Kurs in Handelsw\u00e4hrung.",
                "fair_value": "Modellbasierter fairer Wert aus mehreren "
                              "Bewertungsmethoden. Bei Banken KBV/KGV-basiert, "
                              "sonst inkl. DCF.",
                "upside": "Abstand des Kurses zum Fair Value in Prozent. Positiv "
                          "= Kurs unter dem fairen Wert (Luft nach oben).",
                "playbook": "Automatisch gew\u00e4hltes Bewertungsprofil (quality, "
                            "financial, cyclical, inflection) je nach Firmentyp.",
                "pe": "Kurs-Gewinn-Verh\u00e4ltnis: Kurs geteilt durch Gewinn je "
                      "Aktie. Niedriger = g\u00fcnstiger, aber branchenabh\u00e4ngig.",
                "pb": "Kurs-Buchwert-Verh\u00e4ltnis: Kurs relativ zum bilanziellen "
                      "Eigenkapital. Wichtig vor allem bei Banken.",
                "ev_ebitda": "Unternehmenswert relativ zum operativen Gewinn "
                             "(EBITDA). Bei Banken/Versicherern nicht "
                             "aussagekr\u00e4ftig \u2013 fehlt dort bewusst.",
                "roe": "Eigenkapitalrendite: Gewinn relativ zum Eigenkapital. "
                       "H\u00f6her = effizienter Kapitaleinsatz.",
                "roa": "Gesamtkapitalrendite: Gewinn relativ zur Bilanzsumme. "
                       "H\u00f6her = besser, bei Banken naturgem\u00e4\u00df niedrig.",
                "operating_margin": "Operative Marge: operativer Gewinn je Euro "
                                     "Umsatz. H\u00f6her = profitabler.",
                "gross_margin": "Bruttomarge: Umsatz minus Herstellkosten. Bei "
                                "Banken kaum definiert \u2013 fehlt dort oft.",
                "fcf_yield": "Free-Cashflow-Rendite: frei verf\u00fcgbarer Cashflow "
                             "relativ zum Unternehmenswert. Bei Banken nicht "
                             "sinnvoll berechenbar \u2013 fehlt dort.",
                "revenue_growth": "Umsatzwachstum gegen\u00fcber dem Vorjahr. "
                                  "H\u00f6her = st\u00e4rkeres Wachstum.",
                "debt_to_equity": "Verschuldungsgrad: Fremd- zu Eigenkapital. "
                                  "Niedriger = solider; bei Banken strukturell "
                                  "hoch und nur bedingt vergleichbar.",
                "dividend_yield": "Dividendenrendite: Dividende relativ zum "
                                  "Kurs. H\u00f6her = mehr Aussch\u00fcttung, aber auf "
                                  "Nachhaltigkeit achten.",
                "beta": "Schwankung relativ zum Markt. \u00dcber 1 = schwankungs"
                        "freudiger als der Markt, unter 1 = ruhiger.",
                "market_cap": "B\u00f6rsenwert: Kurs mal Anzahl Aktien.",
                "sector": "Branche/Sektor der Firma.",
            }

            def _label_mit_info(label, key):
                """Label + kleines eingekreistes i mit Hover-Tooltip (title=)."""
                txt = _info.get(key)
                if not txt:
                    return esc(label)
                return (f'{esc(label)} <span title="{esc(txt)}" '
                        f'style="cursor:help;color:var(--muted);font-size:0.85em;'
                        f'border:1px solid var(--muted);border-radius:50%;'
                        f'padding:0 4px;margin-left:4px">i</span>')

            # HTML-Tabelle bauen (eine Spalte je Aktie)
            _html = ['<table style="width:100%;border-collapse:collapse;'
                     'font-size:0.9em">']
            # Kopfzeile
            _html.append('<tr><th style="text-align:left;padding:6px 8px;'
                         'border-bottom:2px solid var(--amber)">Kennzahl</th>')
            for d in _daten:
                _html.append(
                    f'<th style="text-align:right;padding:6px 8px;'
                    f'border-bottom:2px solid var(--amber)">'
                    f'{esc(d["name"][:18])}<br>'
                    f'<span style="color:var(--muted);font-size:0.85em">'
                    f'{esc(d["ticker"])}</span></th>')
            _html.append('</tr>')

            for label, key, fmt, hib in _zeilen:
                if label == "__H__":
                    # Kategorie-Ueberschrift: falls es fuer diese Kategorie
                    # Ampel-Kennzahlen gibt, je Aktie eine Status-Ampel zeigen.
                    _keys = _kat_keys.get(key)
                    _amp_zellen = ""
                    if _keys:
                        for d in _daten:
                            _a = _kategorie_ampel(d, _keys)
                            _amp_zellen += (
                                f'<td style="text-align:right;padding:10px 8px 4px">'
                                f'{_amp_symbol.get(_a, "") if _a else ""}</td>')
                    else:
                        _amp_zellen = ('<td></td>' * len(_daten))
                    _html.append(
                        f'<tr><td style="padding:10px 8px 4px;color:var(--amber);'
                        f'font-weight:600;font-size:0.82em;'
                        f'text-transform:uppercase;letter-spacing:0.05em">'
                        f'{esc(key)}</td>{_amp_zellen}</tr>')
                    continue
                # Werte holen, besten markieren
                _werte = [d.get(key) for d in _daten]
                _num_werte = [(i, w) for i, w in enumerate(_werte)
                              if isinstance(w, (int, float))]
                _best_idx = None
                if hib is not None and len(_num_werte) >= 2:
                    _best_idx = (max(_num_werte, key=lambda p: p[1])[0] if hib
                                 else min(_num_werte, key=lambda p: p[1])[0])
                _html.append(
                    f'<tr><td style="padding:4px 8px;color:var(--fg);'
                    f'border-bottom:1px solid rgba(255,255,255,0.05)">'
                    f'{_label_mit_info(label, key)}</td>')
                for i, d in enumerate(_daten):
                    _v = fmt(d.get(key)) if fmt else "\u2014"
                    _stil = ("color:var(--green);font-weight:600"
                             if i == _best_idx else "color:var(--fg)")
                    _html.append(
                        f'<td style="text-align:right;padding:4px 8px;{_stil};'
                        f'border-bottom:1px solid rgba(255,255,255,0.05)">'
                        f'{_v}</td>')
                _html.append('</tr>')
            _html.append('</table>')
            st.markdown("".join(_html), unsafe_allow_html=True)
            st.caption("\U0001f7e2 Gr\u00fcn = der bessere Wert im direkten Vergleich "
                       "(bei Kennzahlen, wo eine Richtung eindeutig besser ist). "
                       "Bei KGV/KBV/EV-EBITDA/Verschuldung gilt: niedriger = "
                       "g\u00fcnstiger. Die Ampel je Kategorie fasst deren Kennzahlen "
                       "grob zusammen (\U0001f7e2 gut \u00b7 \U0001f7e1 gemischt \u00b7 "
                       "\U0001f534 schwach). Fair Value und Upside sind "
                       "modellbasiert. Kein Anlagerat.")

            # --- Weitere Firmen aus der Branche vorschlagen ---
            _peers = {
                # Grossbanken / Investmentbanken
                "JPM": ["GS", "MS", "BAC", "C", "WFC"],
                "MS": ["GS", "JPM", "BAC", "C"],
                "GS": ["MS", "JPM", "BAC", "C"],
                "BAC": ["JPM", "WFC", "C", "MS"],
                "C": ["JPM", "BAC", "WFC", "GS"],
                "WFC": ["JPM", "BAC", "C", "USB"],
                # Halbleiter
                "NVDA": ["AMD", "AVGO", "TSM", "INTC", "QCOM"],
                "AMD": ["NVDA", "INTC", "AVGO", "TSM"],
                "INTC": ["AMD", "NVDA", "TSM", "TXN"],
                "AVGO": ["NVDA", "QCOM", "TXN", "AMD"],
                # Datacenter / Kuehlung / Power
                "ETN": ["VRT", "JCI", "PWR", "EMR", "PH"],
                "VRT": ["ETN", "JCI", "PWR", "NVT"],
                # Big Tech
                "AAPL": ["MSFT", "GOOGL", "META", "AMZN"],
                "MSFT": ["AAPL", "GOOGL", "AMZN", "ORCL"],
                "GOOGL": ["META", "MSFT", "AMZN", "AAPL"],
                "META": ["GOOGL", "SNAP", "PINS", "MSFT"],
                # Pharma
                "LLY": ["NVO", "PFE", "MRK", "ABBV"],
                "PFE": ["MRK", "JNJ", "ABBV", "BMY"],
                # Auto
                "TSLA": ["GM", "F", "RIVN", "BYDDY"],
            }
            _vgl_ticker = {d["ticker"] for d in _daten}
            # Sektor der verglichenen Titel (fuer den Fallback)
            _vgl_sektoren = {d.get("sector") for d in _daten if d.get("sector")}
            # Kandidaten sammeln: Peers aller verglichenen Titel, die selbst
            # nicht schon im Vergleich stehen
            _kandidaten = {}
            for d in _daten:
                for p in _peers.get(d["ticker"], []):
                    if p not in _vgl_ticker:
                        _kandidaten[p] = _kandidaten.get(p, 0) + 1
            # nach Haeufigkeit sortieren (Peer mehrerer Titel = relevanter)
            _vorschlaege = sorted(_kandidaten, key=lambda p: -_kandidaten[p])[:4]
            if _vorschlaege:
                st.markdown('<div class="vr-th" style="margin-top:16px">'
                            'Weitere Firmen aus der Branche</div>',
                            unsafe_allow_html=True)
                st.caption("Zum direkt Danebenstellen \u2013 einfach oben eintragen.")
                _pcols = st.columns(len(_vorschlaege))
                for _i, _pt in enumerate(_vorschlaege):
                    if _pcols[_i].button(f"+ {_pt}", key=f"vgl_add_{_pt}",
                                         use_container_width=True):
                        # in das erste freie Eingabefeld setzen
                        if not st.session_state.get("vgl_t2"):
                            st.session_state["vgl_t2"] = _pt
                        elif not st.session_state.get("vgl_t3"):
                            st.session_state["vgl_t3"] = _pt
                        else:
                            st.session_state["vgl_t3"] = _pt
                        st.rerun()

            # --- Diagnose: Datenquellen je Titel (aendert keine Berechnung) ---
            with st.expander("\U0001f50e Datenquellen-Diagnose (woher kommen die "
                             "Werte?)"):
                st.caption("Zeigt, ob roic.ai den Titel abdeckt und welche "
                           "bewertungskritischen Felder vorhanden sind. So sehen "
                           "wir, ob eine fehlende Kennzahl an roic, an yfinance "
                           "oder an der Datenlage selbst liegt.")
                # bewertungskritische Felder + Klartext-Label
                _krit = [
                    ("book_value_ps", "Buchwert/Aktie (fuer KBV-Fair-Value)"),
                    ("eps_forward", "Forward-EPS (fuer faires KGV)"),
                    ("free_cashflow", "Free Cashflow (fuer DCF)"),
                    ("ebitda", "EBITDA (fuer EV/EBITDA)"),
                    ("pb", "KBV"), ("pe_trailing", "KGV"),
                    ("target_mean", "Analysten-Kursziel"),
                    ("roe", "Eigenkapitalrendite"),
                    ("net_debt", "Nettoverschuldung"),
                ]
                for d in _daten:
                    _rf = set(d.get("_roic_felder") or [])
                    _cov = "\U0001f7e2 roic deckt ab" if d.get("_roic_aktiv") \
                        else "\U0001f7e1 kein roic \u2013 nur yfinance/FMP"
                    st.markdown(f"**{d['name']} ({d['ticker']})** \u00b7 {_cov} \u00b7 "
                                f"Quellen: {d.get('_data_sources') or '\u2014'}")
                    # Welche kritischen Felder fehlen ganz (im Vergleichsdatensatz)?
                    _zeilen_diag = []
                    for _fk, _flabel in _krit:
                        # der Vergleich speichert das KGV umbenannt als "pe"
                        if _fk == "pe_trailing":
                            _vorhanden = d.get("pe") is not None
                        else:
                            _vorhanden = d.get(_fk) is not None
                        _von_roic = _fk in _rf
                        if _vorhanden is True:
                            _sym = "\U0001f7e2 roic" if _von_roic else "\u2713"
                        elif _vorhanden is False:
                            _sym = "\u2717 fehlt"
                        else:
                            _sym = "\u2013"
                        _zeilen_diag.append(f"{_sym}  {_flabel}")
                    st.markdown("<div style='font-size:0.85em;color:var(--muted);"
                                "margin:2px 0 10px 12px'>"
                                + "<br>".join(esc(z) for z in _zeilen_diag)
                                + "</div>", unsafe_allow_html=True)
                st.caption("\U0001f7e2 roic = Wert kam von roic.ai \u00b7 \u2713 = vorhanden "
                           "(andere Quelle) \u00b7 \u2717 fehlt = Feld nicht verf\u00fcgbar "
                           "(dann kann die zugeh\u00f6rige Berechnung nicht laufen). "
                           "Wenn ein Titel \u201ekein roic\u201c zeigt, deckt roic.ai ihn "
                           "nicht ab \u2013 dann h\u00e4ngt alles an yfinance, das gerade "
                           "bei Banken l\u00fcckenhaft ist.")

                # --- roic-Direkttest: warum liefert bundle() nichts? ---
                st.markdown("---")
                st.caption("**roic-Direkttest:** pr\u00fcft die einzelnen "
                           "roic-Endpunkte f\u00fcr den ersten Titel. Zeigt, ob der "
                           "Abruf klappt (Key/Endpunkt/Symbol) oder leer bleibt.")
                _dt_c = st.columns(2)
                if _dt_c[1].button("\U0001f5d1\ufe0f Cache leeren + neu laden",
                                   key="vgl_cache_clear",
                                   use_container_width=True):
                    # Wenn nach dem Leeren die roic-Felder da sind, war es ein
                    # veralteter Cache-Eintrag (von vor der roic-Verfuegbarkeit).
                    st.cache_data.clear()
                    st.success("Cache geleert \u2013 Vergleich wird neu berechnet.")
                    st.rerun()
                if _dt_c[0].button("\U0001f50c roic-Endpunkte testen",
                                   key="vgl_roic_test",
                                   use_container_width=True):
                    try:
                        import roic as _rt
                        _tt = _daten[0]["ticker"]
                        st.write(f"Test-Titel: **{_tt}**")
                        st.write(f"roic aktiviert (Key vorhanden): "
                                 f"**{_rt.enabled()}**")
                        st.write(f"covers({_tt}): **{_rt.covers(_tt)}**")
                        try:
                            _symn = _rt._sym(_tt)
                            st.write(f"roic-Symbol: **{_symn}**")
                        except Exception as _se:
                            st.write(f"Symbol-Aufl\u00f6sung Fehler: {_se}")
                        # einzelne Endpunkte
                        for _lbl, _fn in [("profile", _rt.profile),
                                          ("enterprise_value", _rt.enterprise_value),
                                          ("ratios_profitability",
                                           _rt.ratios_profitability),
                                          ("multiples", _rt.multiples)]:
                            try:
                                _r = _fn(_tt)
                                if _r:
                                    _keys = list(_r.keys())[:6] if isinstance(_r, dict) else _r
                                    st.write(f"\u2705 {_lbl}: liefert Daten "
                                             f"({len(_r) if hasattr(_r,'__len__') else '?'} "
                                             f"Felder) z.B. {_keys}")
                                else:
                                    st.write(f"\u274c {_lbl}: LEER (None/leer)")
                            except Exception as _fe:
                                st.write(f"\u274c {_lbl}: Fehler {_fe}")
                        # kompletter bundle
                        try:
                            _b = _rt.bundle(_tt)
                            _gefuellt = {k: v for k, v in (_b or {}).items()
                                         if v is not None and not k.startswith("_")}
                            st.write(f"**bundle():** {len(_gefuellt)} gef\u00fcllte "
                                     f"Felder von {len(_b or {})} gesamt")
                            if _gefuellt:
                                st.code(", ".join(sorted(_gefuellt.keys())))
                        except Exception as _be:
                            st.write(f"bundle() Fehler: {_be}")
                    except Exception as _e:
                        import traceback
                        st.error(f"Test fehlgeschlagen: {_e}")
                        st.code(traceback.format_exc()[-1500:])


if nav == "Einzelanalyse":
    # Beim ERSTEN Betreten wird bewusst nichts geladen (frueher startete hier MU).
    # Sobald eine Aktie analysiert wurde, bleibt sie fuer die Sitzung stehen -
    # ein Tab-Wechsel laedt sie also wieder, ohne neu zu suchen.
    if "ea_search" not in st.session_state:
        st.session_state["ea_search"] = ""
    if "pending_search" in st.session_state:
        st.session_state["ea_search"] = st.session_state.pop("pending_search")
    qtext = st.text_input("Aktie analysieren \u2013 Name oder Ticker eingeben",
                          key="ea_search", placeholder="z.B. Micron, NVDA, SAP.DE, ASML.AS")
    qv = qtext.strip()
    ticker = ""
    if qv:
        mm = search_symbols(qv)
        if mm:
            exact = next((x for x in mm if x["symbol"].upper() == qv.upper()), None)
            ticker = (exact or mm[0])["symbol"].upper()
        else:
            ticker = qv.upper()
    run = False

    ea_tabs = st.tabs(["  ANALYSE  ", "  SCORECARD  ", "  MATRIX 1  ", "  MATRIX 2  "])
    with ea_tabs[0]:
        if ticker:
            with st.spinner(f"Lade {ticker} ... (Mehrquellen-Abgleich)"):
                f = load_fundamentals_deep(ticker)
            if not f.get("price"):
                st.error(f"Keine Daten f\u00fcr '{ticker}'. Ticker pr\u00fcfen "
                         "(z.B. MU, NVDA, ASML.AS, SAP.DE).")
            else:
                # Auslands-Zweitnotierung erkennen (APC.DE / 0R2V.L fuer Apple):
                # Wenn die ISIN ein anderes Land ausweist als die Boerse des
                # eingegebenen Tickers, ist es eine Zweitnotierung. Wir zeigen
                # die Daten (dieselbe Firma), weisen aber auf die Heimatboerse
                # hin und bieten - falls auffindbar - den Heimatticker an.
                try:
                    import precompute as _pcz
                    if _pcz.heimat_oder_none(ticker, f.get("isin")):
                        _heim = None
                        _mm2 = search_symbols(f.get("name") or "")
                        for _c in (_mm2 or []):
                            _s = _c.get("symbol", "")
                            if _pcz._ticker_land(_s) == _pcz._isin_land(f.get("isin")):
                                _heim = _s.upper()
                                break
                        if _heim and _heim != ticker:
                            st.info(f"**{ticker}** ist eine Zweitnotierung von "
                                    f"{f.get('name')}. Heimatb\u00f6rse: **{_heim}**.")
                            if st.button(f"\u2192 Zu {_heim} wechseln",
                                         key="ea_heimat"):
                                st.session_state["pending_search"] = _heim
                                st.rerun()
                        else:
                            st.caption(f"Hinweis: {ticker} ist eine Auslands-"
                                       "Zweitnotierung \u2013 dieselbe Firma wie an "
                                       "der Heimatb\u00f6rse.")
                except Exception:
                    pass
                cur = f.get("currency", "USD")
                mult = fx_to_eur(cur)
                if mult is None:
                    mult, sym = 1.0, cur
                    st.warning(f"EUR-Kurs f\u00fcr {cur} nicht abrufbar \u2013 Werte in {cur}.")
                else:
                    sym = "\u20ac"

                def m(v, dash="\u2014"):
                    return dash if v is None else f"{sym}{de(v*mult)}"

                intel = load_intel(ticker, f.get("name"))
                f["_catalyst_score"] = intel.get("catalyst_score", 50.0)
                ep = resolve_preset(f)
                s = scoring.score_stock(f, None, preset=ep)
                v = valuation.fair_value(f, None, preset=ep)

                st.markdown(f"### {f.get('name','')} `{ticker}`")
                st.caption(f"{f.get('sector','?')} / {f.get('industry','?')}  \u00b7  "
                           f"{f.get('country','?')}  \u00b7  Heimatw\u00e4hrung: {cur}")
                try:
                    _wl = store.get_watchlist()
                except Exception:
                    _wl = []
                _in_wl = ticker.upper() in _wl
                if st.button(("\u2605 Auf Watchlist" if _in_wl else "\u2606 Zur Watchlist"),
                             key="wl_toggle",
                             help="Watchlist-Titel werden im Nacht-Job t\u00e4glich "
                                  "vorberechnet und bei \u00c4nderungen gemeldet."):
                    try:
                        _ok = (store.watchlist_remove(ticker) if _in_wl
                               else store.watchlist_add(ticker))
                    except Exception as _e:
                        _ok = False
                        st.error(f"Speichern fehlgeschlagen: {_e}")
                    if _ok is False:
                        st.error("\u26a0\ufe0f Konnte die Watchlist **nicht speichern** "
                                 "(Google Sheet nicht erreichbar oder voll). Der Eintrag "
                                 "w\u00e4re beim n\u00e4chsten Laden wieder weg \u2013 "
                                 "siehe Diagnose im Watchlist-Tab.")
                    else:
                        st.rerun()
                bsum = (f.get("business_summary") or "").strip()
                if bsum:
                    short = bsum[:380].rsplit(" ", 1)[0] + (" \u2026" if len(bsum) > 380 else "")
                    st.markdown(f'<div class="meta" style="line-height:1.5;margin:2px 0 6px">'
                                f'{esc(short)}</div>', unsafe_allow_html=True)
                    if len(bsum) > 380:
                        with st.expander("Vollst\u00e4ndige Unternehmensbeschreibung"):
                            st.write(bsum)
                for wmsg in (f.get("_warnings") or []):
                    st.caption(f"\u26a0 {esc(wmsg)}")

                # Datenluecken erkennen: fehlen Kernkennzahlen, wird der Score kuenstlich
                # Richtung 50 gezogen (fehlende Werte = neutral). Das passiert bei
                # Rate-Limits der Gratis-Datenquellen. Nutzer darauf hinweisen.
                _core = ["roe", "gross_margin", "operating_margin", "revenue_growth",
                         "net_debt_ebitda", "current_ratio"]
                _missing = [k for k in _core if f.get(k) is None]
                if len(_missing) >= 3:
                    # Ursache benennen statt pauschal "Rate-Limit" zu raten.
                    # Mit roic.ai ist das Limit meist NICHT mehr die Ursache -
                    # dann fehlen die Felder wirklich fuer diesen Titel.
                    try:
                        import roic as _rcw
                        _rc_an = _rcw.enabled()
                        _rc_deckt = _rc_an and _rcw.covers(ticker)
                        _rc_pence = _rcw.is_pence_market(ticker)
                    except Exception:
                        _rc_an = _rc_deckt = _rc_pence = False

                    if f.get("_roic"):
                        _ursache = ("Die Werte kamen von **roic.ai**, dort fehlen "
                                    "sie f\u00fcr diesen Titel. Kein Limit-Problem \u2013 "
                                    "erneutes Laden \u00e4ndert daran nichts.")
                    elif _rc_pence:
                        _ursache = ("Dieser Titel notiert in Pence (London). "
                                    "roic.ai ist daf\u00fcr bewusst gesperrt, weil der "
                                    "Anbieter dort einen best\u00e4tigten Umrechnungs"
                                    "fehler hat. Daten kommen von yfinance.")
                    elif _rc_an and not _rc_deckt:
                        _ursache = ("F\u00fcr diesen Titel ist roic.ai nicht "
                                    "freigeschaltet, die Daten kommen von "
                                    "yfinance \u2013 dort k\u00f6nnen Limits greifen.")
                    elif _rc_an:
                        _ursache = ("roic.ai lieferte f\u00fcr diesen Titel nichts, "
                                    "es wurde auf yfinance zur\u00fcckgefallen. "
                                    "Erneutes Laden kann helfen.")
                    else:
                        _ursache = ("Datenquelle ist yfinance/Finnhub \u2013 dort "
                                    "greifen Limits. Erneutes Laden kann helfen.")
                    st.warning(f"\u26a0 **{len(_missing)} Kernkennzahlen fehlen** "
                               f"({', '.join(_missing)}). Der Score wird dadurch "
                               "Richtung 50 gezogen, weil fehlende Werte neutral "
                               f"z\u00e4hlen \u2013 er ist also eher zu niedrig. {_ursache}")

                # Quantum Score: Meta-Score ueber Qualitaet/Bewertung/Analysten/Momentum
                q = scoring.quantum_score(s["composite"], v, intel.get("analyst"),
                                          momentum=s["category_scores"].get("momentum"))

                c = st.columns(6)
                _q_info = info_icon(
                    "Gesamtnote des Tools (0\u2013100): b\u00fcndelt Qualit\u00e4t, "
                    "Bewertung, Analysten und Momentum und zieht teure Titel "
                    "(negativer Upside) sowie m\u00f6gliche Value-Traps ab. "
                    "H\u00f6her ist besser.")
                _comp_info = info_icon(
                    "Fundamentaler Gesamtscore (0\u2013100) aus sechs Kategorien: "
                    "Bewertung, Qualit\u00e4t, Wachstum, Bilanzgesundheit, Momentum "
                    "und Katalysator \u2013 jeweils Durchschnitt der zugeh\u00f6rigen "
                    "Kennzahlen. Misst die Substanz, nicht den Kaufzeitpunkt.")
                if q["score"] is not None:
                    card(c[0], "\u269b\ufe0f Quantum Score" + _q_info, f"{q['score']:.0f}",
                         "/ 100", score_color(q["score"]))
                else:
                    card(c[0], "\u269b\ufe0f Quantum Score" + _q_info, "\u2014")
                comp = s["composite"]
                card(c[1], "Composite Score" + _comp_info, f"{comp:.0f}",
                     "Value-Trap!" if s["value_trap"] else "/ 100", score_color(comp))
                card(c[2], "Kurs", m(v["price"]), "aktuell")
                up = display_upside(v, f.get("price"))   # identisch zum Portfolio
                card(c[3], "Fair Value", m(v["fair_value"]),
                     f"Upside {de(up,2)}%" if up is not None else "\u2014",
                     "var(--green)" if (up or 0) > 0 else "var(--red)")
                card(c[4], "12M-Target", m(v["target_12m"]),
                     f"Analysten: {m(v['analyst_target'])}" if v.get("analyst_target") else "\u2014")
                card(c[5], f"Einstieg (MoS {int(v['margin_of_safety']*100)}%)",
                     m(v["entry_price"]), "Kaufzone \u2264 Preis", "var(--amber)")

                if q["score"] is not None and q.get("parts"):
                    st.caption("\u269b\ufe0f Quantum-Aufschl\u00fcsselung: "
                               + "  \u00b7  ".join(f"{k} {x}" for k, x in q["parts"].items()))

                # Schmidlin-Kennzahlen (kompakt): ungehebelte ROE, dyn.
                # Verschuldungsgrad, Net-Net, PEG. Ergaenzen den fairen Wert.
                _uroe = v.get("ungehebelte_roe")
                _dvg = valuation.dynamischer_verschuldungsgrad(f)
                _nn = v.get("net_net")
                _peg = valuation.peg_ratio(f)
                # Dorsey-Scores laden (Moat, Cashflow-Divergenz)
                _dsc = load_scores(ticker, {"sector": f.get("sector"),
                                            "market_cap": f.get("market_cap"),
                                            "_ist_bank": f.get("_ist_bank")})
                _moat = _dsc.get("moat")
                _cfdiv = _dsc.get("cf_div")
                _fsc = _dsc.get("f")
                _zsc = _dsc.get("z")
                _msc = _dsc.get("m")

                # =====================================================
                # AMPEL-ZUSAMMENFASSUNG - der 5-Sekunden-Blick.
                # Bewertung, Qualitaet, Moat, Bilanz, Warnsignale.
                # =====================================================
                _ampel = []
                # kleine Hilfsfunktion: Text mit Hover-Erklaerung (Tooltip)
                def _tip(text, erklaerung):
                    return (f'<span title="{erklaerung}" '
                            f'style="border-bottom:1px dotted #666;cursor:help">'
                            f'{text}</span>')
                # Bewertung (Upside)
                if up is not None:
                    _b = "\U0001f7e2" if up > 10 else "\U0001f7e1" if up > -10 else "\U0001f534"
                    _btxt = ("%.0f%% unterbewertet" % up if up > 0
                             else "%.0f%% \u00fcberbewertet" % abs(up))
                    _ampel.append(f"{_b} " + _tip("Bewertung",
                        "Abstand zwischen Kurs und fairem Wert. Gr\u00fcn = deutlich "
                        "unterbewertet.") + f": {_btxt}")
                # Qualitaet (Piotroski F)
                if _fsc and _fsc.get("score") is not None:
                    _fs = _fsc["score"]
                    _b = "\U0001f7e2" if _fs >= 7 else "\U0001f7e1" if _fs >= 4 else "\U0001f534"
                    _ampel.append(f"{_b} " + _tip("Qualit\u00e4t",
                        "Piotroski F-Score (0\u20139): fundamentale St\u00e4rke aus neun "
                        "Kriterien. 7\u20139 = solide, 0\u20133 = schwach.") + f": {_fs}/9")
                # Moat
                if _moat:
                    _b = {"breit": "\U0001f7e2", "schmal": "\U0001f7e1",
                          "keiner": "\U0001f534"}.get(_moat["moat_urteil"], "\U0001f7e1")
                    _mtxt = {"breit": "breiter Burggraben", "schmal": "schmaler Burggraben",
                             "keiner": "kein Burggraben"}.get(_moat["moat_urteil"], "")
                    _ampel.append(f"{_b} " + _tip(_mtxt,
                        "Dauerhafter Wettbewerbsvorteil (Dorsey), gemessen an "
                        "anhaltend hoher Profitabilit\u00e4t \u00fcber mehrere Jahre."))
                # Bilanz/Solvenz (Altman Z)
                if _zsc and _zsc.get("z") is not None:
                    _z = _zsc["z"]
                    _b = "\U0001f7e2" if _z >= 3 else "\U0001f7e1" if _z >= 1.8 else "\U0001f534"
                    _ampel.append(f"{_b} " + _tip("Bilanz",
                        "Altman Z-Score: misst das Pleiterisiko. \u00dcber 3 sicher, "
                        "unter 1,8 kritisch.") + f": {_z:.1f}")
                # Warnsignale (Beneish M, Cashflow-Divergenz)
                _warns = []
                if _msc and _msc.get("verdaechtig"):
                    _warns.append("Bilanzverdacht (Beneish)")
                if _cfdiv and _cfdiv.get("warnung"):
                    _warns.append("Cashflow-Divergenz")
                if _warns:
                    _ampel.append("\U0001f534 Warnsignal: " + ", ".join(_warns))
                else:
                    _ampel.append("\u2705 keine Warnsignale")
                if _ampel:
                    st.markdown("**Auf einen Blick:** &nbsp; "
                                + " &nbsp;\u00b7&nbsp; ".join(_ampel),
                                unsafe_allow_html=True)

                if q["score"] is not None and q.get("parts"):
                    st.caption("\u269b\ufe0f Quantum-Aufschl\u00fcsselung: "
                               + "  \u00b7  ".join(f"{k} {x}" for k, x in q["parts"].items()))

                # =====================================================
                # IMMER SICHTBAR: kritische, situative Warnungen.
                # Diese duerfen NICHT weggeklappt werden.
                # =====================================================
                if _cfdiv and _cfdiv.get("warnung"):
                    _schwere = ("\U0001f534 **Starkes Warnsignal**" if _cfdiv.get("stark")
                                else "\U0001f7e1 Warnsignal")
                    _cf_richtung = "f\u00e4llt" if _cfdiv["cashflow_wachstum"] < 0 else "w\u00e4chst kaum"
                    st.warning(f"{_schwere} (Dorsey Red Flag): Der Gewinn w\u00e4chst "
                               f"({_cfdiv['gewinn_wachstum']*100:+.0f}%), aber der "
                               f"operative Cashflow {_cf_richtung} "
                               f"({_cfdiv['cashflow_wachstum']*100:+.0f}%). Das kann "
                               f"hei\u00dfen, dass Ums\u00e4tze gebucht, aber nicht kassiert "
                               f"werden \u2013 pr\u00fcfe Forderungen und Vorr\u00e4te. (Dorseys "
                               f"Lucent-Beispiel begann genau so.)")
                if v.get("mos_verwendet") and v.get("mos_verwendet") != v.get("margin_of_safety"):
                    st.caption(f"\u2139\ufe0f Wegen erh\u00f6hten Risikos verlangt das Modell "
                               f"einen gr\u00f6\u00dferen Sicherheitsabschlag: "
                               f"**{int(v['mos_verwendet']*100)}%** statt "
                               f"{int((v.get('margin_of_safety') or 0)*100)}% "
                               f"(Schmidlin: unsichere Titel brauchen mehr Marge).")

                # ============================================================
                # KENNZAHLEN + NACHRICHTEN, sichtbar statt zugeklappt.
                # Das Faktische zuerst, die Modellrechnung danach. Die
                # ausfuehrlichen Aufklapper weiter unten bleiben - das hier
                # ist die Uebersicht, nicht ihr Ersatz.
                # ============================================================
                # Vor dem Aufruf pruefen, ob die Zusatzmodule auf dem Stand
                # sind. Ohne diese Pruefung erscheint sonst eine kryptische
                # AttributeError-Meldung, obwohl schlicht eine Datei beim
                # Hochladen vergessen wurde - genau das ist zweimal passiert.
                # MINDEST-Stand, nicht exakter Stand.
                #
                # Vorher wurde auf Gleichheit geprueft. Nach einer Aenderung
                # an ui_bewertung.py (Stand .27) meldete das Dashboard die
                # Datei als veraltet, weil hier noch .25 stand - obwohl sie
                # NEUER war. Eine Warnung, die bei korrekt hochgeladenen
                # Dateien anschlaegt, bringt niemandem etwas: Man gewoehnt
                # sich an sie und uebersieht sie, wenn sie einmal stimmt.
                #
                # Entscheidend ist ausserdem nicht die Zahl, sondern ob die
                # gebrauchten Funktionen da sind. Deshalb zaehlt vor allem
                # die zweite Pruefung.
                _ERWARTET = "2026.09.25"

                def _modul_alt(mod, noetig=()):
                    if any(not hasattr(mod, x) for x in noetig):
                        return True
                    ver = getattr(mod, "__version__", None)
                    # Kein Marker -> nicht beurteilbar, aber die Funktionen
                    # sind da. Das reicht.
                    if not ver:
                        return False
                    return str(ver) < _ERWARTET

                try:
                    import kennzahl_kacheln as _kk
                    import ui_bewertung as _uib

                    _veraltet = [
                        n for n, m, f in (
                            ("ui_bewertung.py", _uib,
                             ("kennzahl_kacheln", "news_karte", "sparkline")),
                            ("kennzahl_kacheln.py", _kk, ("rendern",)),
                        ) if _modul_alt(m, f)]
                    if _veraltet:
                        st.warning("Veralteter Dateistand: "
                                   + ", ".join(_veraltet)
                                   + f" \u2014 erwartet wird {_ERWARTET}. "
                                     "Bitte diese Dateien erneut hochladen und "
                                     "die App neu starten.", icon="\u26a0\ufe0f")
                        raise RuntimeError("Modulstand veraltet")

                    @st.cache_data(ttl=21600, show_spinner=False)
                    def _kopf_daten(t):
                        hist, news, bil, zus = [], [], None, None
                        try:
                            import roic as _r
                            if _r.enabled():
                                hist = _r.kennzahl_historie(t, 12) or []
                                if _r.covers(t):
                                    news = _r.news(t, 12) or []
                                    # Bilanzkennzahlen fuer den Kachelstreifen.
                                    # Dieselbe Quelle wie der Aufklapper weiter
                                    # unten, nur einmal geladen.
                                    import kennzahlen as _kz2
                                    _roh2 = _r.ratios_alle(t)
                                    bil = _kz2.bewerte(_roh2)
                                    zus = _kz2.zusammenfassung(bil) if bil else None
                        except Exception:
                            pass
                        return {"hist": hist, "news": news,
                                "bilanz": bil, "bilanz_zus": zus}

                    _kd = _kopf_daten(ticker)
                    if _kd["hist"] or _kd["news"] or _kd["bilanz"]:
                        _uib.inject_css("dunkel")
                        _kk.rendern(_kd["hist"], _kd["news"],
                                    fx=fx_to_eur(f.get("currency") or "USD") or 1.0,
                                    waehrung="EUR", nummer_start=1,
                                    bilanz=_kd["bilanz"],
                                    bilanz_zusammenfassung=_kd["bilanz_zus"])
                except RuntimeError:
                    pass                       # Hinweis steht bereits oben
                except Exception as _e_kk:
                    st.caption(f"Kennzahlen-\u00dcbersicht nicht verf\u00fcgbar ({_e_kk}).")

                # =====================================================
                # DETAILS AUF ABRUF: alle Kennzahl-Erklaerungen in EINEM
                # zugeklappten Block. Kurz oben, tief auf Wunsch.
                # =====================================================
                with st.expander("\U0001f52c Kennzahlen im Detail (Schmidlin, "
                                 "Dorsey, Piotroski, Altman, Beneish)",
                                 expanded=False):
                    # Kacheln: (Label, Wert-Text, Farbe, Hover-Erklaerung)
                    _kacheln = []
                    _GR, _GE, _RO = "var(--green)", "var(--amber)", "var(--red)"
                    if _uroe is not None:
                        _c = _GR if _uroe >= 0.15 else _GE if _uroe >= 0.08 else _RO
                        _kacheln.append(("Ungeh. EKR", f"{_uroe*100:.0f}%", _c,
                            "Ungehebelte Eigenkapitalrendite: wie rentabel die Firma "
                            "ohne den Effekt der Verschuldung arbeitet. \u00dcber 15% stark."))
                    if _dvg is not None:
                        _c = _GR if _dvg < 3 else _GE if _dvg < 5 else _RO
                        _kacheln.append(("Schuldenfrei in", f"{_dvg:.1f} J", _c,
                            "Jahre, um mit dem operativen Cashflow alle Schulden zu "
                            "tilgen. Unter 3 solide, \u00fcber 5 kritisch."))
                    if _nn is not None:
                        _unter = v.get("unter_net_net")
                        _c = _GR if _unter else _GE
                        _kacheln.append(("Net-Net-Wert", m(_nn), _c,
                            "Was bei Zerschlagung je Aktie \u00fcbrig bliebe "
                            "(Umlaufverm\u00f6gen minus alle Schulden). "
                            + ("Kurs liegt darunter \u2013 seltenes starkes Signal!"
                               if _unter else "Negativer Wert ist normal.")))
                    if _peg is not None:
                        _c = _GR if _peg < 1 else _GE if _peg < 1.3 else _RO
                        _kacheln.append(("PEG", f"{_peg:.2f}", _c,
                            "KGV geteilt durch Gewinnwachstum. Unter 1 g\u00fcnstig, um 1 "
                            "fair, \u00fcber 1,3 teuer. Nur so gut wie die Wachstumsannahme."))
                    if _fsc and _fsc.get("score") is not None:
                        _fs = _fsc["score"]
                        _c = _GR if _fs >= 7 else _GE if _fs >= 4 else _RO
                        _kacheln.append(("Piotroski F", f"{_fs}/9", _c,
                            "Fundamentale St\u00e4rke aus neun Kriterien (Profitabilit\u00e4t, "
                            "Verschuldung, Effizienz). 7\u20139 solide, 0\u20133 schwach."))
                    if _zsc and _zsc.get("z") is not None:
                        _z = _zsc["z"]
                        _c = _GR if _z >= 3 else _GE if _z >= 1.8 else _RO
                        _kacheln.append(("Altman Z", f"{_z:.1f}", _c,
                            "Pleiterisiko. \u00dcber 3 sicher, 1,8\u20133 Graubereich, "
                            "unter 1,8 kritisch."))
                    if _msc and _msc.get("m") is not None:
                        _verd = _msc.get("verdaechtig")
                        _c = _RO if _verd else _GR
                        _kacheln.append(("Beneish M", f"{_msc['m']:.1f}", _c,
                            "Wahrscheinlichkeit von Bilanzmanipulation. \u00dcber \u22122,22 "
                            "verd\u00e4chtig." + (" HIER VERD\u00c4CHTIG!" if _verd else "")))
                    if _moat:
                        _c = {"breit": _GR, "schmal": _GE, "keiner": _RO}.get(
                            _moat["moat_urteil"], _GE)
                        _mtxt = {"breit": "breit", "schmal": "schmal",
                                 "keiner": "keiner"}.get(_moat["moat_urteil"], "")
                        _fcf = _moat.get("fcf_sales_akt")
                        _nm = _moat.get("net_margin_akt")
                        _det = []
                        if _fcf is not None:
                            _det.append(f"FCF/Umsatz {_fcf:.0f}% (Ziel 5%)")
                        if _nm is not None:
                            _det.append(f"Nettomarge {_nm:.0f}% (Ziel 15%)")
                        _kacheln.append(("Burggraben", _mtxt, _c,
                            "Dauerhafter Wettbewerbsvorteil (Dorsey), gemessen an "
                            "anhaltend hoher Profitabilit\u00e4t \u00fcber "
                            f"{_moat['jahre_geprueft']} Jahre. "
                            + " \u00b7 ".join(_det)))
                    # Kacheln im selben Streifen wie die Finanzlage.
                    #
                    # Vorher: Raster mit drei Spalten - jede Kachel ein Drittel
                    # Bildschirmbreite fuer eine zweistellige Zahl, acht
                    # Kennzahlen brauchten drei Reihen. Jetzt passen dieselben
                    # acht in eine Reihe, und sie sind untereinander
                    # vergleichbar statt verteilt.
                    if _kacheln:
                        try:
                            import ui_bewertung as _uib2
                            _uib2.inject_css("dunkel")
                            _uib2.pruef_streifen(
                                _kacheln,
                                titel="Kennzahlen im Detail",
                                untertitel="Schmidlin, Dorsey, Piotroski, "
                                           "Altman, Beneish \u2013 Momentaufnahme "
                                           "der Bilanz, keine Prognose.",
                                fusszeile="Mit der Maus \u00fcber eine Kachel "
                                          "fahren zeigt die Erkl\u00e4rung.")
                        except Exception:
                            for _r in range(0, len(_kacheln), 3):
                                _cols = st.columns(3)
                                for _col, (_lab, _val, _col_c, _tipp) in zip(
                                        _cols, _kacheln[_r:_r+3]):
                                    _col.markdown(
                                        f'<div title="{_tipp}" style="cursor:help;'
                                        f'border:1px solid #222;border-radius:8px;'
                                        f'padding:8px 10px;margin-bottom:6px">'
                                        f'<div style="font-size:11px;color:#888">'
                                        f'{_lab}</div>'
                                        f'<div style="font-size:18px;font-weight:600;'
                                        f'color:{_col_c}">{_val}</div></div>',
                                        unsafe_allow_html=True)

                # Value-Trap-Warnung: der Titel bleibt eine Idee, aber mit
                # Vorsicht. "Zu guenstig" ist oft eine Falle, kein Geschenk.
                _vtw = q.get("value_trap_warnung") or []
                if _vtw:
                    # Kurz halten: die Einzelgruende stehen ausgeklappt darunter,
                    # die Erklaerung wiederholt sich sonst auf jeder Seite.
                    st.warning("**M\u00f6gliche Value-Trap** \u2013 selbst pr\u00fcfen, "
                               "bevor du kaufst.", icon="\u26a0\ufe0f")
                    with st.expander(f"Gr\u00fcnde ({len(_vtw)})", expanded=False):
                        st.markdown("\n".join(f"\u2022 {w}" for w in _vtw))

                st.markdown('<div style="height:26px"></div>', unsafe_allow_html=True)
                # ============================================================
                # BEWERTUNG IM DETAIL — Reverse DCF, Szenarien, Herkunft
                # Rendering liegt in ui_bewertung.py / bewertung_seite.py,
                # damit dieser Block hier schlank bleibt. Faellt das Modul aus,
                # laeuft die Seite unveraendert weiter.
                # ============================================================
                try:
                    import bewertung_seite as _bs

                    # Zweite Pruefstelle. Sie verglich ebenfalls auf
                    # Gleichheit und meldete deshalb weiter "veraltet",
                    # nachdem die erste schon auf Mindeststand umgestellt war.
                    # Entscheidend ist, ob die gebrauchte Funktion die noetigen
                    # Parameter kennt - nicht welche Zahl im Marker steht.
                    import inspect as _insp

                    _noetig = ("fx", "waehrung", "start_abschnitt")
                    try:
                        _params = _insp.signature(_bs.rendern).parameters
                        _fehlt = [p for p in _noetig if p not in _params]
                    except (AttributeError, ValueError, TypeError):
                        _fehlt = list(_noetig)
                    if _fehlt:
                        st.warning(
                            "Veralteter Dateistand: bewertung_seite.py fehlen "
                            "die Parameter " + ", ".join(_fehlt)
                            + ". Bitte die Datei erneut hochladen und die App "
                              "neu starten.", icon="\u26a0\ufe0f")
                        raise RuntimeError("Modulstand veraltet")

                    @st.cache_data(ttl=21600, show_spinner=False)
                    def _bewertung_reihen(t):
                        """Historienreihen fuer Reverse DCF, Perzentil und
                        Schaetzguete. Alles optional - was fehlt, faellt weg."""
                        out = {"pe_hist": None, "umsatz": None, "eps": None,
                               "fcf": None, "ni": None}
                        try:
                            import roic as _r
                            if _r.enabled() and _r.multiples_ok(t):
                                out["pe_hist"] = _r.pe_history(t, 10)
                            if _r.enabled():
                                hist = _r.kennzahl_historie(t, 12) or []
                                hist = sorted(hist, key=lambda z: str(z.get("jahr") or ""))
                                out["umsatz"] = [z["revenue"] for z in hist if z.get("revenue")]
                                out["eps"] = [z["eps"] for z in hist if z.get("eps")]
                                out["ni"] = [z["net_income"] for z in hist
                                             if z.get("net_income")]
                        except Exception:
                            pass
                        if not out["umsatz"]:
                            try:                      # Rueckfall auf yfinance
                                fin = providers.get_financials(t) or {}
                                out["umsatz"] = list(reversed(fin.get("revenue") or [])) or None
                                out["fcf"] = list(reversed(fin.get("fcf") or [])) or None
                            except Exception:
                                pass
                        return out

                    _reihen = _bewertung_reihen(ticker)

                    # Bewusst NICHT in einem Expander: Terminalwert-Anteil,
                    # Herkunft des Fair Value und das Reverse-DCF-Urteil sind
                    # genau die Warnungen, die man nicht wegklicken koennen soll.
                    # Nur das Wachstum-x-Cash-Gitter bleibt eingeklappt.
                    # In EUR anzeigen: die Kacheln oben rechnen ebenfalls um,
                    # zwei Waehrungen auf einer Seite sind nicht lesbar.
                    _fx_eur = fx_to_eur(f.get("currency") or "USD") or 1.0
                    _bs.rendern(f, v, preset=ep, ticker=ticker, peer_funds=None,
                                pe_hist=_reihen.get("pe_hist"),
                                umsatz_reihe=_reihen.get("umsatz"),
                                eps_reihe=_reihen.get("eps"),
                                fcf_reihe=_reihen.get("fcf"),
                                ni_reihe=_reihen.get("ni"),
                                fx=_fx_eur, waehrung="EUR", theme="dunkel",
                                start_abschnitt=3,
                                # Bewusst False: st.fragment kann hier nicht
                                # greifen, weil der Block in aeusseren
                                # Containern sitzt (Tabs/Spalten). Das Umschalten
                                # laedt die Seite neu - dafuer funktioniert es.
                                ohne_reload=False)

                    # Datenherkunft sichtbar machen: fehlt eine Reihe, fehlt der
                    # zugehoerige Abschnitt - dann soll man wissen warum.
                    _quellen = [
                        ("KGV-Historie", _reihen.get("pe_hist")),
                        ("Umsatzreihe", _reihen.get("umsatz")),
                        ("EPS-Reihe", _reihen.get("eps")),
                        ("Cashflow-Reihe", _reihen.get("fcf")),
                    ]
                    _fehlt = [n for n, w in _quellen if not w]
                    if _fehlt:
                        st.caption("Nicht verf\u00fcgbar f\u00fcr diesen Titel: "
                                   + ", ".join(_fehlt)
                                   + " \u2014 die davon abh\u00e4ngigen Abschnitte "
                                     "fehlen deshalb.")
                except RuntimeError:
                    pass                       # Hinweis steht bereits oben
                except Exception as _e_bw:
                    st.caption(f"Bewertungsdetails nicht verf\u00fcgbar ({_e_bw}).")

                left, right = st.columns([1, 1])

                with left:
                    st.markdown('<div class="sec-title">SCORING-MATRIX</div>', unsafe_allow_html=True)
                    # Erklaerte Matrix: je Kategorie ein Aufklapper mit den
                    # Kennzahlen, die den Wert treiben - statt nackter Zahlen.
                    try:
                        import scoring as _scng
                        import ui_bewertung as _uim
                        _erk = _scng.score_erklaerung(s, f)
                        _uim.inject_css("dunkel")
                        _uim.score_matrix_erklaert(s["category_scores"], _erk)
                    except Exception:
                        rows = ""
                        for k, val in s["category_scores"].items():
                            rows += (f'<div class="row"><span class="lbl">{k}</span>'
                                     f'<div class="track"><div class="fill" '
                                     f'style="width:{val}%;background:{score_color(val)}"></div></div>'
                                     f'<span class="val">{val:.0f}</span></div>')
                        st.markdown(rows, unsafe_allow_html=True)
                    rg = v["reverse_dcf_implied_growth"]
                    st.caption(f"WACC {v['wacc']:.3f}  \u00b7  Reverse-DCF impliziert g = "
                               f"{(rg*100):.2f}%" if rg is not None else f"WACC {v['wacc']:.3f}")
                    conf = v.get("confidence")
                    cmap = {"hoch": "var(--green)", "mittel": "var(--amber)",
                            "niedrig": "var(--red)"}.get(conf, "var(--muted)")
                    st.markdown(f'<div class="meta">Verl\u00e4sslichkeit Fair Value: '
                                f'<b style="color:{cmap}">{esc(conf or "?")}</b> '
                                f'({v.get("n_methods", 0)} Methoden)</div>',
                                unsafe_allow_html=True)
                    if v.get("fair_value_capped"):
                        st.caption("\u26a0 Fair Value durch Sicherheits-Deckel begrenzt "
                                   "(Methoden weit auseinander \u2013 vorsichtig interpretieren).")
                    if not v.get("reliable"):
                        st.caption("\u26a0 Niedrige Verl\u00e4sslichkeit \u2013 Upside hier nur grob. "
                                   "Dieser Titel wird nicht als Vorschlag verwendet.")

                with right:
                    # KURSVERLAUF entfernt - in der Value-Analyse wenig
                    # relevant. Stattdessen der FAIR-VALUE-VERLAUF: wie sich
                    # die Modell-Einschaetzung ueber die Zeit entwickelt hat.
                    st.markdown('<div id="vr-chart-anchor"></div>',
                                unsafe_allow_html=True)
                    try:
                        import verlauf as _vl_fv
                        import ui_bewertung as _uifv
                        _fv_hist = _vl_fv.lesen(ticker)
                        _uifv.inject_css("dunkel")
                        # Fair Values liegen in EUR vor (fx-umgerechnet); der
                        # Kurs zum Vergleich wird mit demselben Faktor skaliert.
                        _kurs_eur = (f.get("price") or 0) * mult if f.get("price") else None
                        _uifv.fairvalue_verlauf(_fv_hist, "EUR",
                                                aktueller_kurs=_kurs_eur)
                    except Exception as _e_fv:
                        st.caption(f"Fair-Value-Verlauf nicht verfuegbar ({_e_fv}).")

                    lo, hi, pr = f.get("52w_low"), f.get("52w_high"), f.get("price")
                    if lo and hi and pr and hi > lo:
                        pos = (pr - lo) / (hi - lo) * 100
                        pos = max(0.0, min(pos, 100.0))   # sauber begrenzen
                        st.caption(f"52W: {m(lo)} \u2500\u2500 [{pos:.2f}%] \u2500\u2500 {m(hi)}")

                # ============================================================
                # EIGENES 12-MONATS-ZIEL - der 'eigene Analyst'. Verdichtet
                # Fair Value + Wachstum(qualitaetsgewichtet) + Bewertungs-
                # historie + Marktregime zu EINEM eigenstaendigen Ziel, das
                # bewusst vom Analystenkonsens abweichen darf - transparent.
                # ============================================================
                # Marktregime + Bewertungskontext werden fuer das eigene Ziel
                # noch gebraucht (nur als Rechengroesse, nicht mehr angezeigt).
                try:
                    import regime as _reg
                    _bk = _reg.bewertungs_kontext(f, fair_value=v.get("fair_value"))
                    _mr = _reg.markt_regime()
                except Exception:
                    _bk, _mr = None, None
                try:
                    _ez = valuation.eigenes_ziel(
                        f, fair_value=v.get("fair_value"), preset=ep,
                        regime_ampel=(_mr or {}).get("ampel"),
                        pe_perzentil=(_bk or {}).get("pe_perzentil"),
                        analyst_target=v.get("analyst_target"))
                except Exception:
                    _ez = None

                if _ez and _ez.get("ziel"):
                    with st.expander("\U0001f3af Eigenes 12-Monats-Ziel "
                                     "(dein Analyst)", expanded=True):
                        _zc = st.columns(3)
                        card(_zc[0], "Eigenes Ziel", m(_ez["ziel"]),
                             f"Upside {de(_ez['upside_pct'],1)}%"
                             if _ez.get("upside_pct") is not None else "\u2014",
                             "var(--green)" if (_ez.get("upside_pct") or 0) > 0
                             else "var(--red)")
                        card(_zc[1], "Analysten-Ziel", m(v.get("analyst_target")),
                             (f"wir {'+' if (_ez.get('vs_analyst') or 0) >= 0 else ''}"
                              f"{de(_ez['vs_analyst'],1)}% ggu."
                              if _ez.get("vs_analyst") is not None else "\u2014"))
                        card(_zc[2], "Fair Value (heute)", m(v.get("fair_value")),
                             "Basis des Ziels", "var(--muted)")
                        st.caption("So entstand das Ziel (nachvollziehbar):")
                        for _s in _ez.get("herleitung", []):
                            st.markdown(f'<div class="meta">\u2022 {esc(_s)}</div>',
                                        unsafe_allow_html=True)
                        _vsa = _ez.get("vs_analyst")
                        if _vsa is not None and abs(_vsa) >= 10:
                            _ri = "optimistischer" if _vsa > 0 else "vorsichtiger"
                            st.caption(f"\u2192 Wir sind {abs(_vsa):.0f}% {_ri} als "
                                       f"der Analystenkonsens \u2013 auf Basis von "
                                       f"Wachstumsqualitaet, Bewertungshistorie und "
                                       f"Marktregime, nicht aus Kontakten/News.")
                        st.caption("Ausgewogener Sch\u00e4tzwert aus vorhandenen "
                                   "Zahlen \u2013 kein Anlagerat. Auftragsbest\u00e4nde/"
                                   "Ank\u00fcndigungen flie\u00dfen NICHT ein (nicht in den "
                                   "strukturierten Daten enthalten).")

                dv = v.get("model_vs_analyst_pct")
                if dv is not None and abs(dv) >= 25:
                    acnt = v.get("analyst_count")
                    st.caption(f"\u2696\ufe0f Modell {m(v.get('model_fair_value'))} vs. "
                               f"Analysten-Konsens {m(v.get('analyst_target'))}"
                               + (f" ({acnt:.0f} Analysten)" if acnt else "")
                               + f": Analysten sehen {dv:+.0f}% ggü. Modell \u2013 unser Fair Value "
                                 "gewichtet beide. Gro\u00dfe Divergenz = Bewertung h\u00e4ngt an der "
                                 "Wachstumsstory, nicht an heutigen Zahlen.")

                # Hinweis, wenn roic-Werte umgerechnet werden mussten
                if f.get("_roic_fx"):
                    st.caption(
                        f"\u2139\ufe0f Kennzahlen von roic.ai wurden mit dem "
                        f"Faktor **{f['_roic_fx']}** auf die Handelsw\u00e4hrung "
                        "umgerechnet (der Anbieter normalisiert internationale "
                        "Abschl\u00fcsse auf USD). Der Faktor stammt aus dem "
                        "Verh\u00e4ltnis beider Kursquellen, nicht aus einem "
                        "Wechselkurs \u2013 kleine Abweichungen sind m\u00f6glich, "
                        "wenn die Kurse von verschiedenen Handelstagen stammen.")

                # --- NOTBEHELF-WARNUNG: keine Methode lieferte ein Ergebnis
                if v.get("used_fallback"):
                    st.error(
                        "\u26a0\ufe0f **Der Fair Value ist hier KEINE Bewertung.** "
                        "Keine einzige Methode (KGV, KBV, DCF, EV/EBITDA, "
                        "Analystenziel) lieferte ein plausibles Ergebnis \u2013 "
                        "meist wegen fehlender oder widerspr\u00fcchlicher "
                        "Fundamentaldaten. Angezeigt wird deshalb nur ein "
                        "Notbehelf: der gegen den Kurs geklammerte Median, "
                        "also faktisch **der halbe oder doppelte Kurs**. "
                        "Eine Upside von genau \u221250 % oder +100 % ist das "
                        "Erkennungszeichen. **Diese Zahl bitte ignorieren.**")
                    _fehlend = [k for k in ("eps_trailing", "eps_forward",
                                            "book_value_ps", "revenue", "ebitda",
                                            "target_mean", "free_cashflow",
                                            "total_debt", "sector")
                                if not f.get(k)]
                    if _fehlend:
                        st.caption("Fehlende Felder: " + ", ".join(_fehlend))

                # --- Analysten-Streuung (eigenes Feld, kein Eingriff in die Rechnung)
                try:
                    _sp = valuation.analyst_spread(f)
                except Exception:
                    _sp = None
                if _sp and _sp.get("spanne_pct") is not None:
                    _spc = st.columns(3)
                    card(_spc[0], "Kursziel niedrigstes", m(_sp["low"]),
                         "pessimistischster Analyst", "var(--red)")
                    card(_spc[1], "Kursziel h\u00f6chstes", m(_sp["high"]),
                         "optimistischster Analyst", "var(--green)")
                    card(_spc[2], "Uneinigkeit",
                         f"{_sp['spanne_pct']:.0f} %",
                         (f"Faktor {_sp['faktor']} \u00b7 {_sp['n']} Analysten"
                          if _sp.get("faktor") and _sp.get("n")
                          else _sp["einstufung"]),
                         "var(--green)" if _sp["vertrauen"] >= 0.85 else
                         ("var(--amber)" if _sp["vertrauen"] >= 0.6 else "var(--red)"))
                    if _sp["vertrauen"] < 0.85:
                        st.warning(f"**Analysten {_sp['einstufung']}.** Das "
                                   f"12M-Target von {m(_sp['mean'])} ist der "
                                   f"Mittelwert aus {m(_sp['low'])} und "
                                   f"{m(_sp['high'])}. Es tr\u00e4gt je nach Preset "
                                   "25 bis 40 % unseres Fair Value \u2013 bei dieser "
                                   "Streuung sollte man ihm entsprechend wenig "
                                   "Gewicht beimessen.")

                # --- Aktualit\u00e4t: meldet der Titel demn\u00e4chst?
                try:
                    import regime as _rgv
                    _ne = _rgv.next_earnings(ticker, max_wochen=8)
                    _fr = valuation.datenaktualitaet(f, _ne["tage"] if _ne else None)
                    if _fr["stufe"] in ("kritisch", "achtung"):
                        st.warning(f"\u23f0 **{_fr['hinweis']}.** Fair Value und "
                                   "Scores beruhen auf den zuletzt gemeldeten "
                                   "Zahlen.")
                    elif _fr["stufe"] == "hinweis":
                        st.caption(f"\u23f0 {_fr['hinweis']}")
                except Exception:
                    pass

                # Die Detail-Reiter (Finanzlage, Bewertungshistorie,
                # Profil & Nachrichten) samt Tabellen wurden entfernt:
                # Ihre Inhalte stehen bereits oben - Finanzlage als
                # Kachelstreifen, Kennzahlen im Detail im Aufklapper,
                # Nachrichten im Kopfbereich.

                # --- Relative Bewertung: historisches Band + Sektor-Vergleich ---
                try:
                    import relval
                    _rv = relval.summarize(f)
                    _hist, _peer = _rv["hist"], _rv["peer"]
                    if _hist.get("text") or _peer.get("verdict"):
                        st.markdown('<div class="sec-title" style="margin-top:12px">'
                                    'RELATIVE BEWERTUNG</div>', unsafe_allow_html=True)
                        _rc = st.columns(2)
                        _vc = {"guenstig": "var(--green)", "teuer": "var(--red)",
                               "neutral": "var(--muted)", "fair": "var(--muted)"}
                        with _rc[0]:
                            if _hist.get("pe_now") and _hist.get("pe_hist_median"):
                                _pct = _hist.get("pe_pctile")
                                _pct_txt = str(_pct) if _pct is not None else "\u2014"
                                card(st, "KGV vs. eigene Historie",
                                     f"{_hist['pe_now']:.1f}",
                                     f"Schnitt {_hist['pe_hist_median']:.1f} \u00b7 "
                                     f"Perzentil {_pct_txt}",
                                     _vc.get(_hist.get("verdict"), "var(--fg)"))
                            else:
                                st.caption("Historisches KGV-Band: keine ausreichende "
                                           "Historie (FMP-Ratios n\u00f6tig).")
                        with _rc[1]:
                            if _peer.get("avg_disc") is not None:
                                card(st, f"vs. Sektor ({esc(_peer['sector'])})",
                                     f"{_peer['avg_disc']:+.0f}%",
                                     "\u00d8 Ab-/Aufschlag auf KGV & EV/EBITDA",
                                     _vc.get(_peer.get("verdict"), "var(--fg)"))
                            else:
                                st.caption("Sektor-Vergleich: keine Multiples verf\u00fcgbar.")
                        if _hist.get("text"):
                            st.caption("\U0001f4ca " + _hist["text"])
                        st.caption("Sektor-Vergleich nutzt typische Sektor-Multiples "
                                   "(kein echter Einzel-Peer-Vergleich) \u2013 Orientierung, "
                                   "kein exakter Wert. Kein Anlagerat.")
                except Exception as _e:
                    pass

                # Frischer Katalysator / "Kurs vorausgeeilt"-Warnung (aus Kurshistorie).
                # Defensiv: faellt eine aeltere radar.py ohne catalyst_flag auf, wird der
                # Block einfach uebersprungen statt die Analyse abzubrechen.
                _cf = None
                if hasattr(radar, "catalyst_flag"):
                    try:
                        _hc = load_history_full(ticker)
                        _closes = ([float(x) for x in _hc["Close"].dropna().tolist()]
                                   if _hc is not None and not _hc.empty else [])
                        _cf = radar.catalyst_flag(_closes, price=f.get("price"),
                                                  fair_value=v.get("fair_value"))
                    except Exception:
                        _cf = None
                if _cf and _cf.get("trigger"):
                    _up = (_cf.get("info") or {}).get("dir") == "up"
                    _col = "#3FB950" if _up else "#F85149"
                    st.markdown(
                        f'<div class="news-box" style="border-color:{_col}">'
                        f'<b style="color:{_col}">{esc(_cf["trigger"])}</b>'
                        + (f'<div class="sum">\u26a0\ufe0f {esc(_cf["warning"])}</div>'
                           if _cf.get("warning") else "")
                        + '<div class="meta">Frisch erkannter Kurs-Katalysator \u2013 '
                          'zum Beobachten und Lernen, kein Anlagerat.</div></div>',
                        unsafe_allow_html=True)


                st.markdown('<div class="sec-title" style="margin-top:10px">'
                            'KATALYSATOR \u00b7 INTEL</div>', unsafe_allow_html=True)
                ic = st.columns(4)
                cs = intel.get("catalyst_score", 50)
                card(ic[0], "Catalyst Score", f"{cs:.2f}", "/ 100", score_color(cs))
                sent = intel.get("news_sentiment", 0)
                scl = "var(--green)" if sent > 0.1 else ("var(--red)" if sent < -0.1 else "var(--amber)")
                card(ic[1], "News-Sentiment", f"{sent:+.2f}", "Schlagwort-Proxy", scl)
                ins = intel.get("insider") or {}
                card(ic[2], "Insider-Trades (30 Tage)",
                     f"{ins.get('recent_buys', 0)} K\u00e4ufe / {ins.get('recent_sells', 0)} Verk\u00e4ufe"
                     if ins else "n/a",
                     "gemeldete Insider-Transaktionen")
                an = intel.get("analyst") or {}
                card(ic[3], "Analysten",
                     f"{an.get('buy','\u2014')}B / {an.get('hold','\u2014')}H / {an.get('sell','\u2014')}S"
                     if an else "n/a")

                # --- TEST: Liefert der Finnhub-Zugang Rating-Changes je Bank? ---
                # roic bietet KEINE Analysten-Meinungsdaten, daher nur Finnhub.
                # Dieser Test zeigt, ob dein Zugang die Upgrade/Downgrade-Events
                # liefert (Plan-abhaengig), bevor wir ein Feature darauf bauen.
                with st.expander("\U0001f9ea Test: Rating-Changes (Upgrade/Downgrade) "
                                 "verf\u00fcgbar?"):
                    st.caption("Pr\u00fcft, ob dein Finnhub-Zugang einzelne "
                               "Rating-\u00c4nderungen je Bank mit Datum liefert "
                               "(z.B. \u201eBarclays: Overweight \u2192 Buy\u201c). roic hat "
                               "solche Meinungsdaten nicht \u2013 daher nur Finnhub.")
                    if st.button("\U0001f52c Rating-Changes abrufen",
                                 key=f"rc_test_{ticker}"):
                        try:
                            _rc = providers.get_rating_changes(ticker)
                            if _rc:
                                st.success(f"\u2705 Finnhub liefert Rating-Changes "
                                           f"\u2013 {len(_rc)} Eintr\u00e4ge f\u00fcr {ticker}:")
                                _rows = [{"Datum": r["datum"], "Firma": r["firma"],
                                          "Von": r["von"] or "\u2014",
                                          "Auf": r["zu"] or "\u2014",
                                          "Aktion": r["aktion"]} for r in _rc]
                                vr_table(_rows)
                                st.caption("\u2705 Der Zugang funktioniert \u2013 wir "
                                           "k\u00f6nnen daraus ein festes Feature bauen.")
                            else:
                                st.warning("\u274c Keine Rating-Changes zur\u00fcck. "
                                           "Entweder liefert dein Finnhub-Plan diesen "
                                           "Endpunkt nicht (oft nur in kostenpflichtigen "
                                           "Tarifen), oder es gibt f\u00fcr diesen Titel "
                                           "gerade keine. Probier einen gro\u00dfen "
                                           "US-Titel wie NVDA oder AAPL.")
                        except Exception as _e:
                            st.error(f"Test fehlgeschlagen: {_e}")

                # (Der zweite Nachrichten-Block an dieser Stelle wurde
                #  entfernt - die Meldungen stehen jetzt oben unter
                #  'Profil, Nachrichten, Peers & Earnings Call'.)
                st.markdown("**Peers / Wettbewerber**")
                peers = intel.get("peers") or []
                if not peers:
                    st.markdown('<span class="na">n/a (Finnhub-Key n\u00f6tig)</span>',
                                unsafe_allow_html=True)
                else:
                    with st.spinner("Lade Wettbewerber-Kennzahlen ..."):
                        prowz = []
                        for ptk in peers[:6]:
                            if ptk.upper() == ticker.upper():
                                continue
                            pf_ = load_fundamentals_deep(ptk)
                            if not pf_.get("price"):
                                continue
                            pep = valuation.classify_playbook(pf_)
                            pcomp = scoring.score_stock(pf_, None, preset=pep)["composite"]
                            pv = valuation.fair_value(pf_, None, pep)
                            atgt = pv.get("analyst_target")
                            prowz.append({
                                "Ticker": pf_["ticker"],
                                "Name": (pf_.get("name") or "")[:18],
                                "Score": round(pcomp),
                                "Kurs": round(pf_["price"], 2),
                                "Fair Value": pv.get("fair_value"),
                                "Upside %": display_upside(pv, pf_.get("price")),
                                "Analysten-Ziel": atgt,
                                "Ziel-Upside %": (round((atgt / pf_["price"] - 1) * 100, 2)
                                                  if atgt and pf_.get("price") else None)})
                    if prowz:
                        vr_rows(prowz, key_prefix="peer",
                                score_cols=("Score",),
                                signed_cols=("Upside %", "Ziel-Upside %"))
                        st.caption("\U0001f449 Orangenen Ticker anklicken \u2192 \u00f6ffnet "
                                   "den Wettbewerber. Kurse/Werte in Handelsw\u00e4hrung "
                                   "des jeweiligen Titels.")
                    else:
                        st.markdown("".join(f'<span class="pill">{p}</span>' for p in peers),
                                    unsafe_allow_html=True)

                # -----------------------------------------------------------
                # EARNINGS: "Wird der Beat bezahlt?" - Surprise vs Kursreaktion.
                # Zeigt, ob gute Zahlen vom Markt belohnt werden (oft nicht!).
                # -----------------------------------------------------------
                with st.expander("\U0001f4c8 Earnings: Kursreaktion auf Zahlen",
                                 expanded=False):
                    with st.spinner("Lade Earnings-Historie \u2026"):
                        _eh = load_earnings_history(ticker)
                    if not _eh:
                        # Ohne Analystenkonsens ist "Wird der Beat bezahlt?"
                        # nicht zu beantworten - roic liefert die Schaetzungen
                        # nicht. Die TERMINE liegen aber vor, und Tageskurse
                        # auch. Damit laesst sich eine verwandte Frage klaeren:
                        # Haelt die erste Reaktion, oder verpufft sie?
                        try:
                            import earnings_reaktion as _er
                            import ui_bewertung as _uier

                            @st.cache_data(ttl=21600, show_spinner=False)
                            def _reaktion_laden(t):
                                return _er.erheben(t)

                            with st.spinner("Kursreaktion um die Termine \u2026"):
                                _rk = _reaktion_laden(ticker)
                            _uier.inject_css("dunkel")
                            _uier.earnings_reaktion_karte(_rk)
                        except Exception as _e_er:
                            st.caption(f"Kursreaktion nicht berechenbar "
                                       f"({_e_er}).")
                    else:
                        st.caption("Jeder Punkt ist ein Quartal: **EPS-\u00dcberraschung** "
                                   "(wie stark der Gewinn die Sch\u00e4tzung schlug) gegen "
                                   "die **Kursreaktion** am Tag danach. Die Kernfrage: "
                                   "Wird ein Gewinn-Beat vom Markt \u00fcberhaupt belohnt? "
                                   "Gr\u00fcn = Kurs stieg, rot = Kurs fiel.")
                        # Streudiagramm (Altair)
                        _pts = [e for e in _eh
                                if e.get("eps_surprise_pct") is not None
                                and e.get("price_reaction_pct") is not None]
                        if _pts:
                            try:
                                import pandas as _pd
                                import altair as _alt
                                _df = _pd.DataFrame([{
                                    "EPS-\u00dcberraschung %": e["eps_surprise_pct"],
                                    "Kursreaktion %": e["price_reaction_pct"],
                                    "Quartal": e["datum"],
                                    "Reaktion": ("positiv" if e["price_reaction_pct"] >= 0
                                                 else "negativ"),
                                } for e in _pts])
                                _chart = _alt.Chart(_df).mark_circle(
                                    size=120, opacity=0.75).encode(
                                    x=_alt.X("EPS-\u00dcberraschung %:Q"),
                                    y=_alt.Y("Kursreaktion %:Q"),
                                    color=_alt.Color("Reaktion:N", scale=_alt.Scale(
                                        domain=["positiv", "negativ"],
                                        range=["#3FB950", "#F85149"]), legend=None),
                                    tooltip=["Quartal", "EPS-\u00dcberraschung %",
                                             "Kursreaktion %"],
                                ).properties(height=280)
                                st.altair_chart(_chart, use_container_width=True)
                                # Kernaussage: korreliert Beat mit Kursreaktion?
                                _npos = sum(1 for e in _pts if e["price_reaction_pct"] >= 0)
                                _quote = round(_npos / len(_pts) * 100)
                                st.markdown(f"**Bei {_quote}% der Quartale stieg der "
                                            f"Kurs** nach den Zahlen ({_npos} von "
                                            f"{len(_pts)}). "
                                            + ("Der Markt belohnt die Zahlen "
                                               "\u00fcberwiegend." if _quote >= 60 else
                                               "Gute Zahlen f\u00fchren hier oft NICHT zu "
                                               "steigenden Kursen \u2013 ein wichtiges "
                                               "Warnsignal gegen die Annahme \u201eBeat "
                                               "= Kurs rauf\u201c." if _quote <= 40 else
                                               "Gemischtes Bild \u2013 der Beat allein "
                                               "sagt wenig \u00fcber die Kursreaktion."))
                            except Exception as _ce:
                                st.caption(f"Diagramm nicht darstellbar ({_ce}).")
                        # Tabelle
                        _tab = []
                        for e in _eh:
                            _tab.append({
                                "Quartal": e["datum"],
                                "EPS Ist": e.get("eps_actual"),
                                "EPS Sch\u00e4tz.": e.get("eps_est"),
                                "\u00dcberrasch. %": e.get("eps_surprise_pct"),
                                "Kursreaktion %": e.get("price_reaction_pct"),
                            })
                        vr_table(_tab, signed_cols=("\u00dcberrasch. %", "Kursreaktion %"),
                                 height=min(len(_tab) * 38 + 46, 460))
                        st.caption("Kursreaktion = Schlusskurs am ersten Handelstag "
                                   "nach dem Bericht gegen den letzten Tag davor. "
                                   "Datenquelle liefert typischerweise die letzten "
                                   "8\u201312 Quartale.")
    def _prep_for_matrix(t):
        # WICHTIG: deep=True wie in der Einzelanalyse (Zeile ~2544). Sonst
        # laedt die Scorecard flachere Daten und der Composite weicht ab
        # (z.B. 68 statt 70) - der Nutzer sieht zwei verschiedene Scores fuer
        # dieselbe Aktie.
        f = load_fundamentals_deep(t)
        if not f.get("price"):
            return None
        intel = load_intel(t, f.get("name"))
        f["_catalyst_score"] = intel.get("catalyst_score", 50)
        hist = load_history_full(t)
        extras = load_extras(t)
        sig = mx.build_signals(f, hist, intel.get("analyst"), extras)
        cur = f.get("currency", "USD")
        mlt = fx_to_eur(cur)
        sym = "\u20ac" if mlt is not None else cur
        mlt = mlt or 1.0
        return f, intel, sig, sym, mlt


    def _crit_row(name, options, idx_auto, why, key, fmt):
        c1, c2, c3 = st.columns([2.2, 2.3, 3.5])
        c1.markdown(f"**{name}**")
        sel = c2.selectbox(name, range(len(options)), index=idx_auto, key=key,
                           format_func=fmt, label_visibility="collapsed")
        c3.caption(why)
        return sel
    with ea_tabs[1]:
        prep = _prep_for_matrix(ticker)
        if prep is None:
            st.info("Aktie links eingeben/ausw\u00e4hlen \u2013 dann pr\u00fcft die Scorecard automatisch "
                    "alle Gates.")
        else:
            f, intel, sig, sym, mlt = prep
            ep = resolve_preset(f)
            comp = scoring.score_stock(f, None, preset=ep)["composite"]
            valu = valuation.fair_value(f, None, ep)
            extras = load_screen_extras(ticker)
            rkey = f"radar_one_{ticker}"

            # ============================================================
            # NEUE PRUEFUNG statt Scorecard + Matrix 1/2.
            #
            # Vorher liefen hier zwei unabhaengige Siebe: die Scorecard mit
            # sechs eigenen Pflicht-Gates und - im Screener - kandidat.
            # gate_pruefen() mit acht anderen. Derselbe Titel konnte hier
            # "Kaufkandidat" sein und dort ausgeschlossen werden.
            #
            # pruefung.pruefe() ruft dieselben Gates auf wie der Screener.
            # Widersprueche sind damit ausgeschlossen. Matrix 1 faellt weg
            # (Inhalte stehen in Finanzlage, Forensik und Momentum), aus
            # Matrix 2 bleibt das fundamentale Momentum als Bonuskriterium.
            # ============================================================
            _neu_ok = False
            try:
                import kandidat as _kd
                import pruefung as _pr
                import ui_bewertung as _uip

                _k = _kd.pruefe(ticker, fund=f)
                _hist_um = None
                try:
                    import providers as _pv
                    _hist_um = _pv.umsatz_historie(ticker, 15)
                except Exception:
                    pass
                _erg = _pr.pruefe(_k, "value", historie=_hist_um)
                _uip.inject_css("dunkel")
                _uip.gate_karte(_erg)
                _neu_ok = True
            except Exception as _e_pr:
                st.caption(f"Neue Pr\u00fcfung nicht verf\u00fcgbar ({_e_pr}) \u2013 "
                           f"alte Scorecard als R\u00fcckfall.")

            # Der alte Scorecard-Block stand hier (63 Zeilen). Er hat
            # Matrix 1 und 2 zu einem zweiten Urteil verrechnet, das dem
            # des Screeners widersprechen konnte. Ersetzt durch
            # pruefung.pruefe() oben - dieselben Gates wie im Screener.
            #
            # matrices.py und scorecard.py bleiben vorerst auf der Platte,
            # weil precompute.py und hedgefund.py sie noch aufrufen. Sie
            # gehoeren in denselben Umbau, aber nicht in denselben Schritt.
            if not _neu_ok:
                st.warning("Die Pr\u00fcfung konnte nicht berechnet werden. "
                           "Details stehen in der Meldung dar\u00fcber.")
    with ea_tabs[2]:
        prep = _prep_for_matrix(ticker)
        if prep is None:
            st.error(f"Keine Daten f\u00fcr '{ticker}'.")
        else:
            f, intel, sig, sym, mlt = prep
            auto = mx.auto_m1(sig)
            st.markdown(f"### Matrix 1 \u00b7 Setup-Score \u2014 {f.get('name','')} `{ticker}`")
            st.caption("Jedes Kriterium ist automatisch erkannt (Begr\u00fcndung rechts) und "
                       "per Dropdown nachjustierbar. Punkte: 1 (schwach) \u2013 3 (stark).")
            total = 0
            for key, name, levels, where in mx.M1_SPEC:
                idx_a, why = auto.get(key, (1, ""))
                sel = _crit_row(name, levels, idx_a, f"{why}  \u00b7  _{where}_",
                                f"m1_{ticker}_{key}",
                                (lambda i, lv=levels: f"{i+1} P \u00b7 {lv[i]}"))
                total += sel + 1
            cls = mx.classify_m1(total)
            st.markdown("<br>", unsafe_allow_html=True)
            cc = st.columns([1, 2])
            card(cc[0], "Gesamt-Score", f"{total}/45", cls, score_color(total / 45 * 100))

            vs = mx.valuation_summary(f, resolve_preset(f))

            def e(x):
                return "\u2014" if x is None else f"{sym}{de(x*mlt)}"
            with cc[1]:
                st.markdown('<div class="sec-title">BEWERTUNG & ENTRY (eigene Engine)</div>',
                            unsafe_allow_html=True)
                vr_table([
                    {"Modell": "Forward-Multiple (KGV)", "Wert": e(vs["forward_multiple_pe"])},
                    {"Modell": "EV/EBITDA-Modell", "Wert": e(vs["ev_ebitda_model"])},
                    {"Modell": "DCF-Modell", "Wert": e(vs["dcf_model"])},
                    {"Modell": "Fair Value (Blend)", "Wert": e(vs["fair_value"])},
                ])
            vr_table([
                {"Entry-Preis": "ohne DCF", "Basis": e(vs["entry_no_dcf"]),
                 "MOS 10%": e(vs["entry_no_dcf_mos"][0.10]),
                 "MOS 15%": e(vs["entry_no_dcf_mos"][0.15]),
                 "MOS 20%": e(vs["entry_no_dcf_mos"][0.20])},
                {"Entry-Preis": "mit DCF", "Basis": e(vs["entry_dcf"]),
                 "MOS 10%": e(vs["entry_dcf_mos"][0.10]),
                 "MOS 15%": e(vs["entry_dcf_mos"][0.15]),
                 "MOS 20%": e(vs["entry_dcf_mos"][0.20])},
            ])
    with ea_tabs[3]:
        prep = _prep_for_matrix(ticker)
        if prep is None:
            st.error(f"Keine Daten f\u00fcr '{ticker}'.")
        else:
            f, intel, sig, sym, mlt = prep
            autom = mx.auto_m2(sig)
            st.markdown(f"### Matrix 2 \u00b7 Gewichteter Score \u2014 {f.get('name','')} `{ticker}`")
            st.caption("0\u201310 Punkte je Kriterium (4 Stufen). Kategorie-Beitrag = "
                       "(Summe/Max) \u00d7 Gewicht \u00d7 100. Gesamt 0\u2013100.")
            total = 0.0
            for cat, weight, crits in mx.M2_CATS:
                st.markdown(f'<div class="sec-title">{cat} \u00b7 Gewicht {int(weight*100)}%</div>',
                            unsafe_allow_html=True)
                raw, mx_pts = 0, len(crits) * 10
                for key, name, buckets in crits:
                    idx_a, why = autom.get(key, (1, ""))
                    sel = _crit_row(name, buckets, idx_a, why, f"m2_{ticker}_{key}",
                                    (lambda i, bk=buckets: f"{mx.M2_BUCKET_SCORE[i]}/10 \u00b7 {bk[i]}"))
                    raw += mx.M2_BUCKET_SCORE[sel]
                contrib = raw / mx_pts * weight * 100
                total += contrib
                st.caption(f"\u2192 {cat}: {raw}/{mx_pts} Punkte  \u00b7  Beitrag **{contrib:.2f}**")
            st.markdown("<br>", unsafe_allow_html=True)
            card(st.columns([1, 2])[0], "Gesamtscore", f"{total:.2f}/100", "gewichtet",
                 score_color(total))

# ===========================================================================
# TAB — NEWS (allgemeine Markt-News mit Kurz-Zusammenfassung)
# ===========================================================================
if nav == "News":
    st.markdown('<div class="sec-title">MARKT-NEWS</div>', unsafe_allow_html=True)
    st.caption("\U0001f4a1 Im Briefing-Modus zeigt jede Meldung einen m\u00f6glichen Markt-Effekt "
               "(\u2197/\u2198 Bereich + Beispiel-Ticker) \u2013 als Denkanstoss zum "
               "Weiterrecherchieren, ausdr\u00fccklich KEIN Anlagerat.")
    nc = st.columns([1.3, 1, 1, 1.2])
    if nc[0].button("\U0001f504 News aktualisieren", use_container_width=True):
        load_marketnews.clear()                    # Cache leeren = frische Daten
        if hasattr(tr, "_CACHE"):
            tr._CACHE.clear()                      # auch Uebersetzungen neu holen
        for _k in [k for k in st.session_state if str(k).startswith("news_count_")]:
            st.session_state[_k] = 10              # Anzeigezaehler zuruecksetzen
    de_on = nc[1].checkbox("\U0001f1e9\U0001f1ea Deutsch", value=tr.available(),
                           disabled=not tr.available(),
                           help="\u00dcbersetzt englische Quellen ins Deutsche. "
                                "Erster Aufruf langsamer.")
    brief_on = nc[2].checkbox("\u26a1 Briefing", value=True,
                              help="Schnell-Briefing: nur Themen-Chips + die 1\u20132 "
                                   "wichtigsten Kernpunkte je Meldung. F\u00fcr Details "
                                   "abschalten oder Headline anklicken.")
    free_only = nc[3].checkbox("\U0001f513 nur frei lesbar", value=False,
                               help="Blendet Artikel bekannter Paywall-Quellen "
                                    "(Bloomberg, WSJ, FT \u2026) aus. Reuters ist "
                                    "\u201emetered\u201c (erste Artikel frei).")
    st.caption("Quellen: WSJ, CNBC, Reuters, Bloomberg, MarketWatch, Tagesschau u.a. \u00b7 "
               "\U0001f513 frei lesbar \u00b7 \U0001f513\u26a0 Reuters metered \u00b7 "
               "\U0001f512 Paywall m\u00f6glich. Headline \u00f6ffnet den Artikel.")
    if not tr.available():
        st.caption("F\u00fcr die \u00dcbersetzung: `pip install deep-translator`")

    if True:
        # WSJ zuerst (Wunsch). Es wird IMMER nur die gewaehlte Sektion geladen
        # (st.radio), und das automatisch beim ersten Betreten - kein Knopfdruck
        # mehr noetig. Der 10-Minuten-Cache sorgt dafuer, dass ein erneuter Besuch
        # sofort da ist.
        # WSJ-Ressorts direkt in der Hauptauswahl - gleichrangig mit den
        # uebrigen Quellen. Kurze Beschriftungen, damit die Reihe auf dem
        # Handy umbrechen kann statt zu ueberlaufen.
        sections = ["WSJ Business", "WSJ Markets", "WSJ World",
                    "US-Markt", "Yahoo US", "DAX", "Asien", "Aktien-News"]
        _sec = st.radio("Bereich", sections, horizontal=True,
                        label_visibility="collapsed", key="news_section")
        # Anzeigename -> Sektionsname in marketnews.FEEDS
        _sec = {"WSJ Markets": "WSJ Markets & Finance"}.get(_sec, _sec)

        for section in [_sec]:
            if True:
                # WSJ ist komplett hinter einer Paywall - der "nur frei lesbar"-Filter
                # wuerde den Bereich leer machen. Hier greift stattdessen die
                # Weiterleitung ueber removepaywall.com (siehe read_url).
                _fo = False if section.startswith("WSJ") else free_only
                if section.startswith("WSJ"):
                    st.caption("\U0001f512 Alle WSJ-Artikel liegen hinter der Paywall. "
                               "Jede Headline wird automatisch \u00fcber "
                               "**removepaywall.com** ge\u00f6ffnet. Klappt nur, wenn "
                               "dort eine Archiv-Version des Artikels existiert.")
                with st.spinner(f"Lade {section} ..."
                                + (" + \u00fcbersetze ..." if (de_on and section != 'DAX') else "")):
                    items = load_marketnews(section, free_only=_fo)
                    translate_here = de_on and section != "DAX"
                if not items:
                    st.markdown('<span class="na">Aktuell keine Meldungen abrufbar '
                                '(Feeds evtl. kurz nicht erreichbar \u2013 erneut '
                                'aktualisieren).</span>', unsafe_allow_html=True)
                total_secs = 0
                # Sichtbare Artikelzahl je Sektion merken (WSJ zaehlt unabhaengig
                # von DAX etc.). Start: 10, der Button unten erhoeht in 10er-Schritten.
                _cnt_key = f"news_count_{section}"
                _show_n = st.session_state.get(_cnt_key, 10)
                _shown = items[:_show_n]
                # Alle zu uebersetzenden Texte EINMAL sammeln und als Batch
                # uebersetzen (statt je Headline/Punkt eine eigene Netzanfrage).
                _trmap = {}
                if translate_here and _shown:
                    _bucket = []
                    for n in _shown:
                        _bucket.append(n.get("headline") or "")
                        if brief_on:
                            for p in bfg.key_points(n.get("headline") or "",
                                                    n.get("summary") or "", max_points=2):
                                _bucket.append(p)
                        else:
                            _bucket.append(n.get("summary") or "")
                    _uniq = list(dict.fromkeys(t for t in _bucket if t))
                    _tr = tr.translate_batch(_uniq, "de")
                    _trmap = dict(zip(_uniq, _tr))

                def _T(s):
                    return _trmap.get(s, s) if translate_here else s

                for n in _shown:
                    head_raw = n.get("headline") or ""
                    summ_raw = n.get("summary") or ""
                    url = esc(read_url(n.get("url"), n.get("access", "frei")))
                    src = esc(n.get("source") or "")
                    date = fmt_ts(n.get("ts"))
                    flag = " \U0001f1e9\U0001f1ea" if translate_here else ""
                    _acc = n.get("access", "frei")
                    acc_badge = ({"frei": '<span style="color:#3FB950">\U0001f513 frei</span>',
                                  "metered": '<span style="color:#FFB000">\U0001f513\u26a0 metered '
                                             '\u2192 removepaywall</span>',
                                  "paywall": '<span style="color:#F85149">\U0001f512 Paywall '
                                             '\u2192 removepaywall</span>'}
                                 .get(_acc, "")) + " \u00b7 "
                    if brief_on:
                        chips = bfg.tags_for(head_raw, summ_raw)
                        points = bfg.key_points(head_raw, summ_raw, max_points=2)
                        total_secs += bfg.reading_secs(head_raw, summ_raw)
                        head = _T(head_raw)
                        if translate_here:
                            points = [_T(p) for p in points]
                        chip_html = "".join(
                            f'<span class="pill">{e} {esc(l)}</span>' for e, l in chips)
                        pts_html = "".join(
                            f'<div class="sum">\u2022 {esc(p)}</div>' for p in points)
                        impl = bfg.implications(head_raw, summ_raw)
                        impl_html = ""
                        if impl:
                            parts = []
                            for im in impl:
                                arrow = "\u2197" if im["dir"] == "up" else "\u2198"
                                acol = "#3FB950" if im["dir"] == "up" else "#F85149"
                                tks = ", ".join(t.upper() for t in im["tickers"][:3])
                                parts.append(f'<span style="color:{acol}">{arrow}</span> '
                                             f'{esc(im["area"])} <span class="na">'
                                             f'({esc(tks)})</span>')
                            impl_html = ('<div class="sum" style="margin-top:5px">'
                                         '\U0001f4a1 M\u00f6glicher Effekt: '
                                         + " \u00b7 ".join(parts) + '</div>')
                        meta = acc_badge + src + (f" \u00b7 {date}" if date else "") + flag
                        st.markdown(
                            f'<div class="news-box">{chip_html}'
                            f'<a href="{url}" target="_blank">{esc(head)}</a>'
                            f'{pts_html}{impl_html}<div class="meta">{meta}</div></div>',
                            unsafe_allow_html=True)
                    else:
                        head = _T(head_raw)
                        summ = _T(summ_raw)
                        sum_html = f'<div class="sum">{esc(summ)}</div>' if summ else ""
                        meta = acc_badge + src + (f" \u00b7 {date}" if date else "") + flag
                        st.markdown(
                            f'<div class="news-box"><a href="{url}" target="_blank">'
                            f'{esc(head)}</a>{sum_html}<div class="meta">{meta}</div></div>',
                            unsafe_allow_html=True)
                if brief_on and items:
                    st.caption(f"\u23f1 Briefing-Lesezeit gesamt: ~{max(total_secs // 60, 1)} Min. "
                               f"f\u00fcr {len(_shown)} Meldungen.")

                # Button unter den Artikeln: weitere Nachrichten laden.
                _remaining = len(items) - len(_shown)
                if _remaining > 0:
                    _more = min(10, _remaining)
                    if st.button(f"\u2b07\ufe0f {_more} weitere Nachrichten laden "
                                 f"({_remaining} verf\u00fcgbar)",
                                 key=f"news_more_{section}", use_container_width=True):
                        st.session_state[_cnt_key] = len(_shown) + _more
                        st.rerun()
                elif len(_shown) > 10:
                    # alle gezeigt - Moeglichkeit, wieder einzuklappen
                    if st.button("\u2b06\ufe0f Weniger anzeigen",
                                 key=f"news_less_{section}", use_container_width=True):
                        st.session_state[_cnt_key] = 10
                        st.rerun()
                elif items:
                    st.caption("Das sind alle aktuell verf\u00fcgbaren Meldungen dieser "
                               "Quelle. Mit \u201eNews aktualisieren\u201c neu laden.")


# ===========================================================================
# TAB — RADAR (Das Micron von morgen)
# ===========================================================================
if nav == "Trefferbilanz":
    render_trackrecord()

if nav == "Radar":
    if True:
        st.markdown('<div class="sec-title">RADAR</div>',
                    unsafe_allow_html=True)
        st.caption("Scannt vier Frueh-Signal-Ebenen \u2014 Events (SEC-8-K + News), "
                   "Fundamental, Schaetzungs-Momentum, stille Akkumulation.")

        mode = st.radio("Suchradius", ["Themen-Universum (eng & schnell)",
                                       "Branche marktweit",
                                       "Marktweit (alle Branchen)"], horizontal=True)
        theme, branch, rg, rmcap = None, None, None, None
        if mode.startswith("Themen"):
            theme = st.selectbox("Thema", list(radar.THEMES.keys()))
        elif mode.startswith("Branche"):
            bc = st.columns([1.4, 1])
            branch = bc[0].selectbox("Branche", list(radar.BRANCHES.keys()))
            rmcap = bc[1].number_input("Min. Market Cap (Mrd. \u20ac)", value=1.0, step=0.5)
            rg = st.multiselect("L\u00e4nder/Regionen", ms.REGION_CHOICES,
                                default=ms.DEFAULT_REGIONS,
                                help="us, de, nl, fr, gb, ch, it, es, se, dk, fi, no, ca, jp, hk, au")
        else:
            rc = st.columns([1.2, 1])
            _REGION_SETS = {
                "Nordamerika": ["us", "ca"],
                "Europa": ["de", "nl", "fr", "gb", "ch", "it", "es", "se", "dk", "fi", "no"],
                "Asien": ["jp", "hk", "sg", "kr", "tw", "in", "au"],
                "Weltweit": ["us", "ca", "de", "nl", "fr", "gb", "ch", "it", "es",
                             "se", "jp", "hk", "au"],
                "Eigene Auswahl": None,
            }
            _rset = rc[0].selectbox("Region", list(_REGION_SETS.keys()), index=0,
                                    key="rad_region")
            rmcap = rc[1].number_input("Min. Market Cap (Mrd. \u20ac)", value=1.0, step=0.5)
            if _REGION_SETS[_rset] is None:
                rg = st.multiselect("L\u00e4nder/Regionen", ms.REGION_CHOICES,
                                    default=ms.DEFAULT_REGIONS)
            else:
                rg = _REGION_SETS[_rset]
                st.caption("Abgedeckt: " + ", ".join(rg))

        # --- Groessenklasse: gegen die "immer nur Schwergewichte"-Schlagseite ---
        _SIZE_CLASSES = {
            "Alle Gr\u00f6\u00dfen (gr\u00f6\u00dfte zuerst)": (None, False),
            "\U0001f50e Wenig beachtet: Small Caps 0,3\u20135 Mrd": (5.0, True),
            "\U0001f50e Nebenwerte 0,1\u20131 Mrd (sehr klein)": (1.0, True),
            "Mid Caps 5\u201350 Mrd": (50.0, True),
            "Schwergewichte > 50 Mrd": (None, False),
        }
        _sc_label = st.selectbox("Gr\u00f6\u00dfenklasse", list(_SIZE_CLASSES.keys()),
                                 index=0, key="rad_size",
                                 help="Der Screener sortiert normalerweise nach "
                                      "Marktkapitalisierung ABSTEIGEND - deshalb "
                                      "tauchen immer dieselben Konzerne auf. Die "
                                      "\u201ewenig beachtet\u201c-Klassen kehren das um "
                                      "und deckeln die Gr\u00f6\u00dfe nach oben.")
        _rmax_cap, _asc = _SIZE_CLASSES[_sc_label]
        if _sc_label.startswith("Schwergewichte"):
            rmcap = max(rmcap or 0.0, 50.0)
        elif _sc_label.startswith("Mid"):
            rmcap = max(rmcap or 0.0, 5.0)
        elif "0,3" in _sc_label:
            rmcap = max(rmcap or 0.0, 0.3)
        elif "0,1" in _sc_label:
            rmcap = max(rmcap or 0.0, 0.1)

        rmax = st.number_input("Max. Titel scannen", value=40, min_value=10, max_value=300,
                               step=10, key="radar_rmax",
                               help="Mehr = mehr Treffer, aber langsamer "
                               "(Events werden je Titel geladen).")
        if not config.FINNHUB_API_KEY:
            st.caption("\u2139 Ohne Finnhub-Key: Insider via yfinance (l\u00fcckenhaft), "
                       "Events via SEC-8-K (nur US) + News-Trigger.")
        scan = st.button("\u25b6 RADAR SCANNEN", use_container_width=True)

        if scan:
            rmcap_bn = rmcap or 0.0
            if theme:
                tickers = radar.THEMES[theme]
            elif branch:
                # groesseres Roh-Universum holen, da nach Branche stark gefiltert wird
                tickers, _src = load_universe(tuple(rg or ms.DEFAULT_REGIONS),
                                              rmcap_bn, int(rmax) * 8)
            else:
                tickers, _src = load_universe(tuple(rg or ms.DEFAULT_REGIONS),
                                              rmcap_bn, int(rmax) * 2,
                                              _rmax_cap, _asc)

            # 1) Fundamentaldaten laden + Mindest-Marktkap. erzwingen (wie im Screener)
            #    + Doppel-Listings (1YD.DE/.F/.XC ...) entfernen
            # Parallel geladen: jeder Titel ist ein langsamer Netzabruf, der
            # meist nur wartet. Sequenziell dauert das bei 150 Titeln Minuten
            # und Streamlit bricht ab.
            from concurrent.futures import ThreadPoolExecutor, as_completed
            loaded = []
            prog = st.progress(0.0, text="Lade Universum ...")
            _fertig = 0
            _ges = len(tickers)

            def _lade_einen(t):
                f = load_fundamentals(t)
                if f.get("price"):
                    f["_fx"] = fx_to_eur(f.get("currency", "USD")) or 1.0
                    if theme or mcap_eur_bn(f) >= rmcap_bn:
                        return f
                return None

            with ThreadPoolExecutor(max_workers=8) as _pool:
                _futs = {_pool.submit(_lade_einen, t): t for t in tickers}
                for _fut in as_completed(_futs):
                    try:
                        f = _fut.result(timeout=20)
                        if f:
                            loaded.append(f)
                    except Exception:
                        pass
                    _fertig += 1
                    prog.progress(_fertig / max(_ges, 1),
                                  text=f"Lade Universum \u2026 {_fertig}/{_ges}")
            if branch:                                  # nach Hauptbranche filtern
                sec, kw = radar.BRANCHES[branch]
                loaded = [f for f in loaded if radar.in_branch(f, sec, kw)]
            deduped = radar.dedupe_by_name(loaded)[:int(rmax)]

            # 2) Radar nur auf den bereinigten Titeln berechnen - ebenfalls
            #    parallel, da compute() mehrere Zusatzabrufe je Titel macht.
            results = []
            _fertig2 = 0

            def _radar_einen(f):
                t = f["ticker"]
                r = radar.compute(f, load_history_full(t), load_eps_rev(t),
                                  load_insider(t), load_8k(t),
                                  load_event_news(t, f.get("name")))
                r["_fx"] = f.get("_fx") or 1.0
                r["_price"] = f.get("price")
                r["_mcap"] = f.get("market_cap")
                r["_analysts"] = f.get("analyst_count")
                return r

            with ThreadPoolExecutor(max_workers=6) as _pool:
                _futs = {_pool.submit(_radar_einen, f): f for f in deduped}
                for _fut in as_completed(_futs):
                    try:
                        results.append(_fut.result(timeout=30))
                    except Exception:
                        pass
                    _fertig2 += 1
                    prog.progress(_fertig2 / max(len(deduped), 1),
                                  text=f"Scanne \u2026 {_fertig2}/{len(deduped)}")
            prog.empty()
            results.sort(key=lambda x: x["score"], reverse=True)
            st.session_state["radar_results"] = results          # bleibt erhalten
            st.session_state.pop("radar_last_pick", None)

        # --- Anzeige aus dem Speicher (ueberlebt Tab-Wechsel) ---
        results = st.session_state.get("radar_results")
        if results:
            # Optionaler Filter: nur wenig beachtete Titel (kaum Analysten-Abdeckung)
            _only_hidden = st.checkbox(
                "\U0001f50e Nur wenig beachtete Titel (h\u00f6chstens 8 Analysten)",
                value=False, key="rad_hidden",
                help="Titel mit vielen Analysten sind durchleuchtet. Wenige oder gar "
                     "keine Analysten = eher unentdeckt. Ohne Analysten-Daten wird der "
                     "Titel als 'unbeobachtet' behandelt und bleibt drin.")
            _shown = [r for r in results
                      if (not _only_hidden) or ((r.get("_analysts") or 0) <= 8)]
            if _only_hidden and not _shown:
                st.info("Keiner der Treffer ist gering abgedeckt \u2013 Filter zeigt nichts. "
                        "Tipp: Gr\u00f6\u00dfenklasse \u201eSmall Caps\u201c w\u00e4hlen.")

            def _mc(v):
                if not v:
                    return None
                return round(v / 1e9, 1)

            rows = [{"Ticker": r["ticker"], "Name": (r["name"] or "")[:22],
                     "Radar-Score": r["score"], "Qualit\u00e4t": r["layers"].get("quality", 0),
                     "Ereignisse": r["layers"]["events"],
                     "Fundamental": r["layers"]["fundamental"],
                     "Sch\u00e4tzungen": r["layers"]["estimates"],
                     "Akkumulation": r["layers"]["accumulation"],
                     "Aktive Ebenen": r["firing"],
                     "Gr\u00f6\u00dfe Mrd": _mc(r.get("_mcap")),
                     "Analysten": r.get("_analysts"),
                     "Preis \u20ac": round((r["_price"] or 0) * r["_fx"], 2),
                     "Sektor": (r["sector"] or "")[:14]} for r in _shown]
            df = pd.DataFrame(rows)
            vr_table(rows, score_cols=("Radar-Score", "Qualit\u00e4t", "Ereignisse",
                                       "Fundamental", "Sch\u00e4tzungen", "Akkumulation"),
                     height=460)
            st.caption("Werte 0\u2013100. Qualit\u00e4t = Fundamentalsockel (ROE, Marge, "
                       "Cashflow, Verschuldung) \u2013 macht gute Aktien auch OHNE "
                       "frisches Ereignis sichtbar \u00b7 Ereignisse = 8-K/News \u00b7 "
                       "Fundamental = Wachstum/Backlog \u00b7 Sch\u00e4tzungen = Analysten "
                       "heben Gewinnsch\u00e4tzungen \u00b7 Akkumulation = Insiderk\u00e4ufe/"
                       "Volumen/Chart \u00b7 Aktive Ebenen = Koinzidenz.")
            st.caption("\U0001f449 Orangenen Ticker anklicken \u2192 \u00f6ffnet die Einzelanalyse.")

            st.markdown('<div class="sec-title" style="margin-top:14px">'
                        'TOP-TREFFER \u00b7 KONKRETE TRIGGER</div>', unsafe_allow_html=True)
            shown = 0
            for r in results:
                if r["score"] <= 5 or shown >= 8:
                    continue
                shown += 1
                trg = "".join(f'<div class="meta">\u00b7 {esc(t)}</div>' for t in r["triggers"][:7]) \
                    or '<div class="meta">\u00b7 (keine starken Trigger)</div>'
                st.markdown(
                    f'<div class="news-box"><a>{esc(r["ticker"])} \u2014 {esc(r["name"])}</a> '
                    f'<span style="color:{score_color(r["score"])};font-weight:700">'
                    f'&nbsp;Radar {r["score"]}</span>{trg}</div>', unsafe_allow_html=True)
            if shown == 0:
                st.info("Keine auff\u00e4lligen Frueh-Signale im gescannten Universum.")
            st.caption("Hinweis: Radar liefert Kandidaten, keine Kaufsignale \u2013 "
                       "jeden Treffer einzeln pr\u00fcfen (Matrix 1/2 & Bewertung).")
        else:
            pass


# ===========================================================================
# TAB 2 — SCREENER (marktweit)
# ===========================================================================
if nav == "Screener":
    st.markdown('<div class="sec-title">MARKTWEITER SCREENER</div>', unsafe_allow_html=True)

    # ---------------------------------------------------------------------
    # "Wenn ich heute kaufen m\u00fcsste" - derselbe Scan wie im Nachtlauf,
    # aber sofort. Bewusst ganz oben: das ist der schnellste Weg zu einer
    # Gesamtsicht, ohne auf den n\u00e4chsten Cron zu warten.
    # ---------------------------------------------------------------------
    with st.expander("\u26a1 WENN ICH HEUTE KAUFEN M\u00dcSSTE \u00b7 Scan auf Knopfdruck",
                     expanded=False):
        st.caption("F\u00fchrt denselben Scan aus wie der n\u00e4chtliche Job \u2013 gleiche "
                   "Kriterien, gleiche Kennzahlen \u2013 nur eben jetzt. Ergebnis: "
                   "Composite, Quantum (Meta), Radar-Score und Upside je Titel.")
        import precompute as _pcs
        _strat = st.selectbox("Strategie", list(_pcs.STRATEGIEN),
                              key="live_strat")
        _sinfo = _pcs.STRATEGIEN[_strat]
        st.caption(f"**Sucht:** {_sinfo['was']}")
        st.warning(f"**Schwäche dieser Strategie:** {_sinfo['risiko']}")

        _lc1, _lc2 = st.columns(2)
        try:
            import roic as _rq
            _roic_da = _rq.enabled()
        except Exception:
            _roic_da = False
        _groessen = [90, 200, 400, 600] if _roic_da else [40, 90, 150]
        _uni = _lc1.selectbox("Universumsgr\u00f6\u00dfe",
                              _groessen,
                              index=1,
                              format_func=lambda n: f"{n} Titel",
                              key="live_uni",
                              help="Gro\u00dfe Titel aus US, DE, FR, GB, NL ab 5 Mrd. "
                                   "Marktkapitalisierung. Mehr Titel = "
                                   "gr\u00fcndlicher, aber l\u00e4nger.")
        _topn = _lc2.selectbox("Davon tief nachrechnen",
                               [10, 20, 30, 40] if _roic_da else [5, 10, 15, 20],
                               index=1, format_func=lambda n: f"Top {n}",
                               key="live_top",
                               help="Nur f\u00fcr diese werden Radar-Score und "
                                    "volle Bewertung berechnet \u2013 das kostet "
                                    "mehrere Zusatzabrufe je Titel.")
        if _roic_da:
            # Parallel (8 gleichzeitig in der Vorauswahl, 6 beim Tief-Rechnen).
            # Massgeblich ist jetzt das roic-Limit von 240/min, nicht mehr die
            # Summe der Wartezeiten. 3 Abrufe je Titel breit, ~13 je Top-Titel.
            _abrufe = _uni * 3 + _topn * 13
            _sek = int(_abrufe / 240 * 60 * 1.15)      # kleiner Puffer
            _sek = max(20, _sek)
            st.caption(f"Gesch\u00e4tzte Laufzeit: **rund {max(1, _sek//60)}\u2013"
                       f"{_sek//60 + 1} Minuten** ({_abrufe} Abrufe \u00fcber "
                       "roic.ai, parallel). Bitte den Tab offen lassen.")
        else:
            _dauer = int(_uni * 0.25 + _topn * 1.2)    # parallel, grob
            st.caption(f"Gesch\u00e4tzte Laufzeit: **rund {max(1, _dauer//60)}\u2013"
                       f"{_dauer//60 + 1} Minuten**. Ohne roic.ai-Anbindung "
                       "greifen die Limits der Gratisquellen \u2013 gr\u00f6\u00dfere "
                       "Universen sind deshalb gesperrt.")

        if st.button("\u25b6 Scan jetzt starten", key="live_go",
                     use_container_width=True):
            import precompute as _pcx
            _bar = st.progress(0.0, text="Universum wird geladen \u2026")

            def _fortschritt(fertig, gesamt, phase):
                if phase == "breit":
                    anteil = 0.8 * fertig / max(gesamt, 1)
                    _bar.progress(anteil,
                                  text=f"Breite Bewertung \u2026 {fertig}/{gesamt}")
                else:
                    anteil = 0.8 + 0.2 * fertig / max(gesamt, 1)
                    _bar.progress(min(anteil, 1.0),
                                  text=f"Top-Titel tief nachrechnen \u2026 "
                                       f"{fertig}/{gesamt}")

            try:
                _erg = _pcx.live_scan(universum=_uni, top_n=_topn, tief=True,
                                      fortschritt=_fortschritt,
                                      strategie=_strat)
                _bar.progress(1.0, text="fertig")
                st.session_state["live_ergebnis"] = _erg
                st.session_state["live_zeit"] = datetime.now().strftime(
                    "%d.%m.%Y %H:%M")
                st.session_state["live_strat_used"] = _strat
                st.session_state["live_spalten"] = _sinfo.get("spalten", [])
            except Exception as _e:
                _bar.empty()
                st.error(f"Scan fehlgeschlagen: {_e}")

        _erg = st.session_state.get("live_ergebnis")
        if _erg:
            st.caption(f"Stand: {st.session_state.get('live_zeit', '\u2014')} \u00b7 "
                       f"Strategie: **{st.session_state.get('live_strat_used', '\u2014')}** "
                       f"\u00b7 {len(_erg)} Titel")
            # Branchenfilter: die im Scan gefundenen Sektoren als Auswahl.
            # Filtert nur die ANZEIGE - der Scan selbst bleibt marktweit.
            _rd_br = radar.BRANCHES
            _vorhandene = sorted({(r.get("sector") or "") for r in _erg
                                  if r.get("sector")})
            # Auf die deutschen Branchen-Labels abbilden, wo moeglich
            _sek_zu_label = {}
            for _lbl, (_sek, _kw) in _rd_br.items():
                if _kw is None:               # nur die eindeutigen Haupt-Sektoren
                    _sek_zu_label.setdefault(_sek, _lbl)
            _optionen = ["Alle Branchen"] + [
                _sek_zu_label.get(s, s) for s in _vorhandene]
            _wahl_br = st.selectbox("Branche filtern", _optionen,
                                    key="live_branche")
            if _wahl_br != "Alle Branchen":
                # gewaehltes Label zurueck auf den Sektor mappen
                _ziel_sek = None
                for _lbl, (_sek, _kw) in _rd_br.items():
                    if _lbl == _wahl_br:
                        _ziel_sek = _sek
                        break
                if _ziel_sek is None:
                    _ziel_sek = _wahl_br      # war schon ein roher Sektorname
                _erg_gefiltert = [r for r in _erg
                                  if (r.get("sector") or "") == _ziel_sek]
            else:
                _erg_gefiltert = _erg
            if _wahl_br != "Alle Branchen":
                st.caption(f"{len(_erg_gefiltert)} von {len(_erg)} Titeln "
                           f"in **{_wahl_br}**")
            # Strategiespezifische Spalten hinter den Standardspalten
            _extra = st.session_state.get("live_spalten", [])
            _zeilen = []
            for r in _erg_gefiltert:
                _vt = "\u26a0\ufe0f " if r.get("vt_warnung") else ""
                _z = {"Ticker": r.get("ticker"),
                      "Name": (_vt + (r.get("name") or ""))[:24],
                      "Comp": r.get("composite"),
                      "Quantum": r.get("quantum"),
                      "Radar": r.get("radar_score"),
                      "Ebenen": (f"{r.get('radar_ebenen')}/4"
                                 if r.get("radar_ebenen") is not None else "\u2014")}
                for _lbl, _key in _extra:
                    _z[_lbl] = r.get(_key)
                _z.update({"Upside %": r.get("upside"), "Kurs": r.get("price"),
                           "Fair Value": r.get("fair_value"),
                           "Einstieg": r.get("entry"),
                           "Sektor": (r.get("sector") or "\u2014")[:16]})
                _zeilen.append(_z)
            _signed = ["Upside %"] + [l for l, _k in _extra
                                      if "%" in l or "52W" in l]
            vr_table(_zeilen, signed_cols=tuple(_signed),
                     height=min(len(_zeilen) * 40 + 46, 520))
            st.caption(
                "**Comp** = Composite Score (Fundamentaldaten), **Quantum** = "
                "Meta-Score aus Composite, Bewertung, Analysten und Momentum, "
                "**Radar** = Fr\u00fchsignal-Score mit der Zahl feuernder Ebenen. "
                "Sortiert nach Composite plus gedeckelter Upside \u2013 dieselbe "
                "Reihenfolge wie im Nachtlauf. **Eine Momentaufnahme, kein "
                "Kaufsignal:** ein hoher Score hei\u00dft \u201epasst zu den Kriterien\u201c, "
                "nicht \u201ewird steigen\u201c. Diese Titel landen NICHT automatisch in "
                "der Trefferbilanz \u2013 dort wird nur der Nachtlauf protokolliert, "
                "damit die Messung sauber bleibt. Kein Anlagerat.")

    vorlage = st.selectbox("Vorlage", ["Eigene Filter"] + list(sp.PRESETS.keys()),
                           help="Fertige Screening-Strategien oder eigene Filter.")
    manual_mode = (vorlage == "Eigene Filter")
    go = False

    if manual_mode:
        with st.expander("\u2699  FILTER  (0 bzw. leer = Filter aus)", expanded=True):
            r1 = st.columns(4)
            f_mcap = r1[0].number_input("Min. Market Cap (Mrd. \u20ac)", value=2.0, step=0.5,
                                        help="Liquiditaet & Stabilitaet.")
            f_profit = r1[1].selectbox("Gewinn (2026e)", ["egal", "positiv", "negativ"], index=1,
                                       help="positiv = nur profitable Firmen (Forward-EPS > 0).")
            f_revg = r1[2].number_input("Min. Umsatzwachstum %", value=0.0, step=1.0)
            f_roe = r1[3].number_input("Min. ROE %", value=0.0, step=1.0)
            r2 = st.columns(4)
            f_pe = r2[0].number_input("Max. KGV (fwd)", value=0.0, step=1.0,
                                      help="0 = aus. ACHTUNG: bei Zyklikern/Growth irrefuehrend!")
            f_evebitda = r2[1].number_input("Max. EV/EBITDA", value=0.0, step=1.0, help="0 = aus.")
            f_pb = r2[2].number_input("Max. KBV (P/B)", value=0.0, step=0.5, help="0 = aus.")
            f_peg = r2[3].number_input("Max. PEG", value=0.0, step=0.5, help="0 = aus.")
            r3 = st.columns(4)
            f_fcf = r3[0].number_input("Min. FCF-Rendite %", value=0.0, step=1.0)
            f_nde = r3[1].number_input("Max. Net Debt/EBITDA", value=0.0, step=0.5, help="0 = aus.")
            f_curr = r3[2].number_input("Min. Current Ratio", value=0.0, step=0.1)
            screen_preset = r3[3].selectbox("Playbook", ["quality", "cyclical", "inflection"],
                                            index=2, key="screen_preset")
            r4 = st.columns([3, 1])
            regions = r4[0].multiselect("Regionen (freier Yahoo-Screener)", ms.REGION_CHOICES,
                                        default=ms.DEFAULT_REGIONS,
                                        help="Bestimmt das Markt-Universum (wird bei FMP-Key ignoriert).")
            max_load = r4[1].number_input("Max. Titel laden", value=60, step=10, min_value=10,
                                          max_value=300, help="Tempo vs. Abdeckung.")

        go = st.button("\u25b6 SCREENEN", use_container_width=True)
    else:
        info = sp.PRESETS[vorlage]
        st.caption("\U0001f4cb " + info["desc"])
        with st.expander("Welche Kriterien pr\u00fcft diese Vorlage?", expanded=False):
            for c in info["criteria"]:
                tag = "Pflicht" if c["type"] == "hard" else "Bonus"
                st.markdown(f"- **[{tag}]** {c['label']}")
            st.caption("N\u00e4herungen: 5-Jahres-Wachstum \u2248 TTM-Wachstum; "
                       "Eigenkapitalquote \u2248 Verschuldungsgrad (D/E); "
                       "Marktposition \u2248 Bruttomarge \u00d7 ROE.")
        pc = st.columns([3, 1])
        p_regions = pc[0].multiselect("Regionen", ms.REGION_CHOICES,
                                      default=ms.DEFAULT_REGIONS, key="p_regions")
        p_maxload = pc[1].number_input("Max. Titel laden", value=80, step=10,
                                       min_value=10, max_value=300, key="p_maxload")
        if st.button("\u25b6 VORLAGE SCREENEN", use_container_width=True):
            with st.spinner("Hole Markt-Universum ..."):
                universe, src = load_universe(tuple(p_regions or ms.DEFAULT_REGIONS),
                                              0.5, int(p_maxload) * 2)
            universe = universe[:int(p_maxload)]
            st.caption(f"Universum-Quelle: {src} \u00b7 {len(universe)} Kandidaten.")

            loaded = []
            prog = st.progress(0.0, text="Lade Fundamentaldaten ...")
            for i, t in enumerate(universe, 1):
                fd = load_fundamentals(t)
                if fd.get("price"):
                    fd["_fx"] = fx_to_eur(fd.get("currency", "USD")) or 1.0
                    loaded.append(fd)
                prog.progress(i / max(len(universe), 1), text=f"Lade {t} ...")
            loaded = radar.dedupe_by_name(loaded)

            playbook = info["playbook"]
            need_div = sp.needs_dividends(vorlage)
            rows = []
            for j, fd in enumerate(loaded, 1):
                t = fd["ticker"]
                ex = load_screen_extras(t)
                if need_div:
                    fd["dividend_years"] = load_div_years(t)
                fv = valuation.fair_value(fd, None, valuation.classify_playbook(fd))
                ev = sp.evaluate(vorlage, fd, ex, fv)
                prog.progress(j / max(len(loaded), 1),
                              text=f"Pr\u00fcfe {t} ... ({len(rows)} Treffer)")
                if not ev["passed"]:
                    continue
                fx = fd["_fx"]
                pe = fd.get("pe_forward") or fd.get("pe_trailing")
                rows.append({
                    "Name": (fd.get("name") or "")[:24], "Ticker": t,
                    "Preis \u20ac": round((fd.get("price") or 0) * fx, 2),
                    "Fair Value \u20ac": round((fv.get("fair_value") or 0) * fx, 2)
                    if fv.get("fair_value") else None,
                    "Upside %": display_upside(fv, fd.get("price")),
                    "KGV": round(pe, 1) if pe else None,
                    "12M %": ex.get("ch_1y"),
                    "Bonus-Fit": f"{ev['soft_pass']}/{ev['soft_total']}",
                    "_fit": ev["soft_pass"],
                    "Land": fd.get("country", "?"),
                    "Sektor": (fd.get("sector") or "")[:16],
                })
            prog.empty()

            if rows:
                df = pd.DataFrame(rows).sort_values(
                    ["_fit", "Upside %"], ascending=[False, False]).drop(columns=["_fit"])

                def cup(v):
                    try:
                        x = float(v)
                        return "color:#3FB950" if x > 0 else ("color:#F85149" if x < 0 else "")
                    except Exception:
                        return ""
                styled = (df.style.map(cup, subset=["Upside %"])
                          .format(precision=2, formatter={"Preis \u20ac": "{:.2f}", "Fair Value \u20ac": "{:.2f}",
                                   "Upside %": "{:+.2f}", "12M %": "{:+.2f}"}, na_rep="\u2014"))
                st.success(f"{len(df)} Titel erf\u00fcllen alle Pflicht-Kriterien der "
                           f"Vorlage \u201e{vorlage}\u201c.")
                vr_table(df.to_dict("records"),
                         signed_cols=("Upside %", "12M %"), height=560)
                st.caption("Alle Pflicht-Kriterien sind erf\u00fcllt; \u201eBonus-Fit\u201c zeigt die "
                           "zus\u00e4tzlich erf\u00fcllten weichen Kriterien. Kein Kaufsignal \u2013 "
                           "jeden Treffer einzeln pr\u00fcfen. \U0001f449 Orangenen Ticker anklicken "
                           "\u2192 Einzelanalyse.")
            else:
                st.info("Keine Aktie erf\u00fcllt alle Pflicht-Kriterien \u2013 mehr Titel laden "
                        "oder Regionen erweitern.")

    # ------------------------------------------------------------------
    # Ergebnis fuer die Dauer der Sitzung behalten. Streamlit baut die
    # Seite bei JEDEM Tabwechsel neu auf - ohne Zwischenspeicher waere ein
    # mehrminuetiger Scan danach verloren.
    # ------------------------------------------------------------------
    if go or st.session_state.get("scr_passed"):
        if go:
            with st.spinner("Hole Markt-Universum ..."):
                universe, src = load_universe(tuple(regions or ms.DEFAULT_REGIONS),
                                              f_mcap, int(max_load) * 2)
            st.caption(f"Universum-Quelle: {src} \u00b7 {len(universe)} Kandidaten "
                       f"\u2192 lade die ersten {int(max_load)}.")
            universe = universe[:int(max_load)]

            def ok(fd):
                if mcap_eur_bn(fd) < f_mcap:                 # gleiche Schwelle wie Radar
                    return False
                eps_fwd = fd.get("eps_forward")
                if f_profit == "positiv" and not (eps_fwd is not None and eps_fwd > 0):
                    if not ((fd.get("profit_margin") or -1) > 0):
                        return False
                if f_profit == "negativ" and (eps_fwd is not None and eps_fwd > 0):
                    return False
                if f_revg and (fd.get("revenue_growth") or -99) * 100 < f_revg:
                    return False
                if f_roe and (fd.get("roe") or -99) * 100 < f_roe:
                    return False
                if f_fcf and (fd.get("fcf_yield") or -99) * 100 < f_fcf:
                    return False
                if f_curr and (fd.get("current_ratio") or -99) < f_curr:
                    return False
                if f_pe and (fd.get("pe_forward") or 1e9) > f_pe:
                    return False
                if f_evebitda and (fd.get("ev_ebitda") or 1e9) > f_evebitda:
                    return False
                if f_pb and (fd.get("pb") or 1e9) > f_pb:
                    return False
                if f_peg and (fd.get("peg") or 1e9) > f_peg:
                    return False
                if f_nde and (fd.get("net_debt_ebitda") or -1e9) > f_nde:
                    return False
                return True

            passed = []
            prog = st.progress(0.0, text="Lade & filtere Titel ...")
            for i, t in enumerate(universe, 1):
                fd = load_fundamentals(t)
                if fd.get("price"):
                    fd["_fx"] = fx_to_eur(fd.get("currency", "USD")) or 1.0
                    if ok(fd):
                        passed.append(fd)
                prog.progress(i / max(len(universe), 1), text=f"Pr\u00fcfe {t} ... "
                              f"({len(passed)} Treffer)")
            prog.empty()
            passed = radar.dedupe_by_name(passed)      # Doppel-Listings entfernen
            st.caption(f"{len(passed)} Titel bestehen die Filter.")
            st.session_state["scr_passed"] = passed
            st.session_state["scr_zeit"] = datetime.now().strftime("%H:%M")
        else:
            passed = st.session_state["scr_passed"]
            _c1, _c2 = st.columns([3, 1])
            _c1.info(f"Ergebnis von **{st.session_state.get('scr_zeit', '\u2014')} "
                     f"Uhr** \u00b7 {len(passed)} Titel. Auf \u201eSCREENEN\u201c "
                     "klicken f\u00fcr einen neuen Lauf.")
            if _c2.button("\U0001f5d1\ufe0f Verwerfen", key="scr_clear",
                          use_container_width=True):
                st.session_state.pop("scr_passed", None)
                st.session_state.pop("scr_zeit", None)
                st.rerun()

        rows = []
        # Doppelnotierungen ueber den Firmennamen entfernen. Die symbol-
        # basierte Variante greift hier nicht: NVIDIA laeuft als NVDA,
        # NVD.DE, NVDG.F und NVDD.XC - kein gemeinsames Basissymbol.
        try:
            import precompute as _pcd
            _vorher = len(passed)
            _grp, _ohne = {}, []
            for _fd in passed:
                _k = _pcd._norm_name(_fd.get("name"))
                if not _k:
                    _ohne.append(_fd)
                else:
                    _grp.setdefault(_k, []).append(_fd)

            def _rang(fd):
                _t = fd.get("ticker") or ""
                _b, _p = _pcd._canon_base(_t)
                return (_p, len(_b), _t)
            passed = [sorted(g, key=_rang)[0] for g in _grp.values()] + _ohne
            if len(passed) < _vorher:
                st.caption(f"{_vorher - len(passed)} Doppelnotierung(en) "
                           "zusammengefasst (gleiche Firma, andere B\u00f6rse).")
        except Exception:
            pass

        for fd in passed:
            t = fd["ticker"]
            fx = fd["_fx"]
            peers = [p for p in passed if p.get("sector") == fd.get("sector") and p["ticker"] != t]
            sres = scoring.score_stock(fd, peers or None, preset=screen_preset)
            perf = load_perf(t)
            an = load_analyst(t)
            an_str = f"{an['buy']}/{an['hold']}/{an['sell']}" if an else "\u2014"
            rows.append({
                "Name": (fd.get("name") or "")[:26],
                "Ticker": t,
                "Preis \u20ac": round((fd.get("price") or 0) * fx, 2),
                "6M %": round(perf["ch_6m"], 1) if perf.get("ch_6m") is not None else None,
                "1J %": round(perf["ch_1y"], 1) if perf.get("ch_1y") is not None else None,
                "YTD %": round(perf["ch_ytd"], 1) if perf.get("ch_ytd") is not None else None,
                "Land": fd.get("country", "?"),
                "Sektor": (fd.get("sector") or "")[:16],
                "Analyst K/H/V": an_str,
                "Score": sres["composite"],
            })

        if rows:
            df = pd.DataFrame(rows).sort_values("Score", ascending=False)
            vr_table(df.to_dict("records"), score_cols=("Score",),
                     signed_cols=("6M %", "1J %", "YTD %"), height=560)
            st.caption(f"{len(df)} Titel \u00b7 Playbook: {screen_preset} \u00b7 nach Score "
                       "sortiert \u00b7 Analyst K/H/V = Kauf/Halten/Verkauf-Empfehlungen. "
                       "\U0001f449 Orangenen Ticker anklicken \u2192 Einzelanalyse.")
        else:
            st.info("Kein Titel besteht alle Filter \u2013 Schwellen lockern oder "
                    "mehr Titel laden.")


# ===========================================================================
# MOMENTUM
# ===========================================================================
if nav == "Momentum":
    st.markdown('<div class="sec-title">MOMENTUM</div>', unsafe_allow_html=True)
    st.caption("Sucht Titel mit starkem, aufmerksamkeitsstarkem Aufw\u00e4rtstrend: "
               "Trendst\u00e4rke (12\u20131-Momentum), relative St\u00e4rke zur Branche, "
               "N\u00e4he zum 52-Wochen-Hoch, K\u00e4ufer-\u00dcbergewicht (OBV) und "
               "Handelsvolumen.")
    st.warning("**Momentum ist der am besten belegte, aber auch der "
               "gef\u00e4hrlichste Faktor.** Er kehrt sich abrupt um \u2013 gerade in "
               "Wendephasen des Marktes. Ein hoher Score hei\u00dft \u201estarker "
               "Trend jetzt\u201c, nicht \u201ewird weiter steigen\u201c. Kein Anlagerat.")

    try:
        import roic as _rqm
        _roic_da_m = _rqm.enabled()
    except Exception:
        _roic_da_m = False

    _mc1, _mc2 = st.columns(2)
    _uni_m = _mc1.selectbox("Universumsgr\u00f6\u00dfe",
                            [90, 200, 400, 600] if _roic_da_m else [40, 90, 150],
                            index=1, format_func=lambda n: f"{n} Titel",
                            key="mom_uni",
                            help="Gro\u00dfe Titel aus US, DE, FR, GB, NL ab 5 Mrd. "
                                 "Marktkapitalisierung.")
    _top_m = _mc2.selectbox("Wie viele anzeigen", [15, 25, 40, 60],
                            index=1, format_func=lambda n: f"Top {n}",
                            key="mom_top")
    _dauer_m = int(_uni_m * 0.25 + 15)
    st.caption(f"Gesch\u00e4tzte Laufzeit: **rund {max(1, _dauer_m//60)}\u2013"
               f"{_dauer_m//60 + 1} Minuten** (parallel). Bitte den Tab offen "
               "lassen.")

    if st.button("\U0001f680 Momentum scannen", key="mom_go",
                 use_container_width=True):
        import precompute as _pcm
        _barm = st.progress(0.0, text="Universum wird geladen \u2026")

        def _fm(fertig, gesamt, phase):
            _barm.progress(min(fertig / max(gesamt, 1), 1.0),
                           text=f"Bewerte \u2026 {fertig}/{gesamt}")

        try:
            _ergm = _pcm.momentum_scan(universum=_uni_m, top_n=_top_m,
                                       fortschritt=_fm)
            _barm.progress(1.0, text="fertig")
            st.session_state["mom_ergebnis"] = _ergm
            st.session_state["mom_zeit"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        except Exception as _em:
            st.error(f"Scan fehlgeschlagen: {_em}")
        _barm.empty()

    _ergm = st.session_state.get("mom_ergebnis")
    if _ergm:
        st.caption(f"Stand: {st.session_state.get('mom_zeit', '')} \u00b7 "
                   f"{len(_ergm)} Titel")
        _data_m = []
        for r in _ergm:
            _data_m.append({
                "Ticker": r["ticker"],
                "Name": (r.get("name") or "")[:20],
                "Score": r["score"],
                "12\u20131 %": round(r["mom_12_1"], 1) if r.get("mom_12_1") is not None else None,
                "6M %": round(r["ch_6m"], 1) if r.get("ch_6m") is not None else None,
                "vs Branche": round(r["rel_staerke"], 1) if r.get("rel_staerke") is not None else None,
                "z. 52W-Hoch %": round(r["zu_hoch"], 1) if r.get("zu_hoch") is not None else None,
                "RSI": round(r["rsi"]) if r.get("rsi") is not None else None,
                "OBV": {"up": "\u2191 Kauf", "down": "\u2193 Verkauf",
                        "flat": "\u2192"}.get(r.get("obv"), "\u2014"),
                "\u2013\u2013": r["ticker"],
            })
        vr_table(_data_m, score_cols=("Score",),
                 signed_cols=("12\u20131 %", "6M %", "vs Branche", "z. 52W-Hoch %"),
                 height=min(len(_data_m) * 40 + 46, 640))
        st.caption("**12\u20131 %** = Jahresrendite ohne den letzten Monat "
                   "(Forschungsstandard, da der j\u00fcngste Monat zur Umkehr "
                   "neigt). **vs Branche** = 6M-Vorsprung zum Median der "
                   "Branche \u2013 nur positive Werte sind echte relative St\u00e4rke. "
                   "**OBV** = kaufen oder verkaufen die Anleger per Saldo "
                   "aggressiver.")

        # Warnungen des Top-Titels als Beispiel zeigen
        _mit_warn = [r for r in _ergm if r.get("warnungen")]
        if _mit_warn:
            with st.expander(f"\u26a0\ufe0f Warnhinweise ({len(_mit_warn)} Titel)"):
                for r in _mit_warn[:20]:
                    st.markdown(f"**{r['ticker']}** ({r['score']}): "
                                + " \u00b7 ".join(r["warnungen"]))
    else:
        st.info("Noch kein Scan. Oben Parameter w\u00e4hlen und "
                "\u201eMomentum scannen\u201c klicken.")


# ===========================================================================
# WATCHLIST
# ===========================================================================
if nav == "Watchlist":
    st.markdown('<div class="sec-title">WATCHLIST</div>', unsafe_allow_html=True)
    wl = store.get_watchlist()
    ac = st.columns([2, 1])
    new_tk = ac[0].text_input("Ticker/Unternehmen hinzuf\u00fcgen", key="wl_add_input",
                              placeholder="z.B. NVDA, SAP.DE, Palantir",
                              label_visibility="collapsed")
    if ac[1].button("\u2795 Hinzuf\u00fcgen", use_container_width=True):
        raw = (new_tk or "").strip()
        if raw:
            tk = raw.upper()
            f0 = load_fundamentals(tk)
            if not f0.get("price"):              # Name -> Ticker aufloesen
                mm = search_symbols(raw)
                if mm:
                    tk = mm[0]["symbol"].upper()
            try:
                _ok = store.watchlist_add(tk)
            except Exception as _e:
                _ok = False
                st.error(f"Speichern fehlgeschlagen: {_e}")
            if _ok is False:
                st.error("\u26a0\ufe0f Konnte nicht speichern \u2013 siehe Diagnose unten.")
            else:
                st.session_state.pop("wl_add_input", None)
                st.rerun()

    if not wl:
        st.info("Noch keine Titel auf der Watchlist. Oben hinzuf\u00fcgen \u2013 oder in der "
                "Einzelanalyse den Button \u201e\u2606 Zur Watchlist\u201c nutzen.")
    else:
        with st.spinner("Watchlist wird berechnet (Mehrquellen-Abgleich) ..."):
            wrows, _winv, _wres = build_portfolio_rows(
                [{"ticker": t} for t in wl], inc_radar=False, inc_pl=False, live=True,
                require_size=False)
        buyzone = [r for r in wrows
                   if r.get("entry_eur") and r.get("price_eur")
                   and r["price_eur"] <= r["entry_eur"]]
        if buyzone:
            st.success("\U0001f3af In Kaufzone: "
                       + ", ".join(f"{r['ticker']} ({sym_eur(r['price_eur'])} "
                                   f"\u2264 {sym_eur(r['entry_eur'])})" for r in buyzone))
        data = [{"Ticker": r["ticker"], "Name": (r["name"] or "")[:20],
                 "Kurs \u20ac": round(r.get("price_eur") or 0, 2),
                 "Comp.": round(r["composite"]) if r.get("composite") is not None else None,
                 "Fair \u20ac": round(r["fair_value_eur"], 2) if r.get("fair_value_eur") else None,
                 "Einstieg \u20ac": round(r["entry_eur"], 2) if r.get("entry_eur") else None,
                 "Upside %": round(r["upside"], 2) if r.get("upside") is not None else None,
                 "Zone": ("\U0001f7e2 Kauf" if (r.get("entry_eur") and r.get("price_eur")
                          and r["price_eur"] <= r["entry_eur"]) else "\u2013")}
                for r in wrows]
        vr_table(data, score_cols=("Comp.",), signed_cols=("Upside %",),
                 height=min(len(data) * 40 + 46, 520))
        st.caption("\u201eEinstieg \u20ac\u201c = modellierter Kaufkurs mit Sicherheitsmarge. "
                   "\U0001f7e2 = Kurs hat die Kaufzone erreicht. Kein Anlagerat.")

        rc = st.columns([2, 1])
        rem = rc[0].selectbox("Titel entfernen", ["\u2014"] + wl, key="wl_rem_sel",
                              label_visibility="collapsed")
        if rc[1].button("\U0001f5d1\ufe0f Entfernen", use_container_width=True):
            if rem and rem != "\u2014":
                store.watchlist_remove(rem)
                st.rerun()


# ===========================================================================
# LONG / SHORT-RADAR (experimentell)
# ===========================================================================
if nav == "Long/Short":
    # st.tabs verliert die Auswahl bei jedem Rerun (Filter/Buttons springen zurueck
    # auf den ersten Tab). Deshalb eine zustandsfeste Auswahl per Radio.
    _ls_view = st.radio("Ansicht", ["\U0001f3db\ufe0f Strategien", "\U0001f4d3 Logbuch"],
                        horizontal=True, label_visibility="collapsed", key="ls_view")
    if _ls_view.endswith("Logbuch"):
        st.markdown('<div class="sec-title">\U0001f4d3 TRADE-LOGBUCH \u00b7 alle '
                    'Strategien</div>', unsafe_allow_html=True)
        render_hf_logbook()
    if _ls_view.endswith("Strategien"):
        st.markdown('<div class="sec-title">\U0001f3db\ufe0f LAUFENDE STRATEGIE-PORTFOLIOS '
                    '(Papier)</div>', unsafe_allow_html=True)
        try:
            _hf = store.get_hf()
        except Exception:
            _hf = {}
        if not _hf:
            st.info("Noch keine laufenden Portfolios. Sie werden vom Nacht-Job (2\u00d7 t\u00e4glich) "
                    "automatisch angelegt und gef\u00fchrt \u2013 oder hier per Knopf gestartet.")
        _sn = {"marktneutral": "Marktneutral (L100/S100)", "130/30": "130/30",
               "quality_long": "Qualit\u00e4ts-Long",
               "core_ko": "Aktien + KO-Hebel 3x (8\u201315 % Beimischung)",
               "screener_long": "Screener-Test (nur Long/Short-Screener)"}
        for _k, _s in (_hf or {}).items():
            _v, _c0 = _s.get("value_eur", 0), _s.get("start_capital", 10000)
            _ret = (_v / _c0 - 1) * 100 if _c0 else 0
            _col = "#3FB950" if _ret >= 0 else "#F85149"
            with st.expander(f"{_sn.get(_k, _k)} \u00b7 {sym_eur(_v)} "
                             f"({_ret:+.1f} %) \u00b7 {len(_s.get('positions', []))} Pos.",
                             expanded=False):
                # Neustart-Vermerk: ohne ihn laesst sich eine Rendite nicht
                # einordnen - ein zwei Wochen altes Depot ist mit einem seit
                # Monaten laufenden nicht vergleichbar.
                _na = _s.get("neustart_am") or _s.get("created")
                if _na:
                    try:
                        _tage = int((time.time() - float(_na)) / 86400)
                        _dat = datetime.fromtimestamp(float(_na)).strftime("%d.%m.%Y")
                        _gr = (_s.get("neustart_grund") or "").strip()
                        st.caption(f"L\u00e4uft seit **{_dat}** ({_tage} Tage)"
                                   + (f" \u00b7 Neustart: {esc(_gr)}" if _gr else "")
                                   + (" \u00b7 \u26a0\ufe0f zu kurz f\u00fcr eine Beurteilung"
                                      if _tage < 30 else ""))
                    except Exception:
                        pass

                _rows = [{"Ticker": p["ticker"], "Richtung": (f'\U0001f680 KO-{p["ko_dir"]} 3x' if p.get("type") == "ko"
                           else ("\U0001f7e2 Long" if p["dir"] == "long" else "\U0001f534 Short")), "Einstieg \u20ac": p["entry_eur"],
                          "Kurs \u20ac": p.get("last_eur"), "G/V %": p.get("pl_pct"),
                          "Gewinn-Stop": (f"+{p['trail_stop']:.0f} %"
                                          if p.get("trail_stop") is not None else "\u2013"),
                          "St\u00fcck": p["qty"]} for p in _s.get("positions", [])]
                if _rows:
                    vr_table(_rows, signed_cols=("G/V %",),
                             height=min(len(_rows) * 40 + 46, 420))
                _rules = ("Regeln: Long TP +20/SL \u221210, Short TP +15/SL \u221210 \u00b7 "
                          "Gewinn-Stop: ab +15 % zieht der Stop auf +10 % nach und steigt "
                          "in 5er-Schritten mit (+20 \u2192 +15, +25 \u2192 +20 \u2026) \u00b7 "
                          "danach Slots neu bef\u00fcllt.")
                if _k == "core_ko":
                    _rules = ("Regeln: Aktien-Kern (6 Titel) TP +20/SL \u221210 \u00b7 "
                              "Gewinn-Stop ab +15 % (dann +10 %, in 5er-Schritten mit) \u00b7 "
                              "KO-Scheine 3\u00d7 Hebel, ~12 % des Depots, TP +45/SL \u221230, "
                              "Knock-out bei \u00b133 % \u00b7 KO-Basiswerte sind bewusst ANDERE "
                              "Unternehmen als der Kern, immer Call UND Put beigemischt.")
                    st.info("\u2139\ufe0f Die KO-Scheine sind **simuliert**, keine echten "
                            "Zertifikate: kein Emittent/ISIN, konstanter Hebel 3\u00d7, "
                            "Barriere \u00b133 %, ohne Aufgeld, Spread und Finanzierungskosten. "
                            "Reale Knock-outs haben einen **dynamischen** Hebel (er steigt, "
                            "je n\u00e4her der Kurs der Barriere kommt) und k\u00f6nnen "
                            "**intraday** ausknocken \u2013 die Simulation ist also g\u00fctiger "
                            "als die Realit\u00e4t.")
                _px_ts = _s.get("last_price")
                _px_txt = (f" \u00b7 Kurse: {fmt_ts(_px_ts)}"
                           if _px_ts and _px_ts != _s.get("last_check") else "")
                st.caption(f"Cash: {sym_eur(_s.get('cash', 0))} \u00b7 "
                           f"letzte Regel-Pr\u00fcfung: "
                           f"{fmt_ts(_s.get('last_check'))}{_px_txt} \u00b7 {_rules}")
                _tr = _s.get("trades", [])[:5]
                if _tr:
                    st.caption("Letzte Trades: " + " \u00b7 ".join(
                        f"{t['action']} {t['ticker']} ({t['dir']}"
                        + (f", {t['pl_pct']:+.0f}%" if t.get("pl_pct") is not None else "")
                        + f", {t['why']})" for t in _tr))

                # --- Zuruecksetzen (mit Bestaetigung) ---
                if st.button("\u21ba Portfolio zur\u00fccksetzen", key=f"hf_reset_{_k}",
                             use_container_width=True):
                    st.session_state["hf_confirm_reset"] = _k
                    st.rerun()
                if st.session_state.get("hf_confirm_reset") == _k:
                    st.warning(f"\u26a0\ufe0f \u201e{_sn.get(_k, _k)}\u201c wirklich zur\u00fccksetzen? "
                               "Alle Positionen und die Trade-Historie dieser Strategie "
                               "werden verworfen und das Depot startet neu mit "
                               f"{sym_eur(_s.get('start_capital', 10000))} Papiergeld.")
                    _rc = st.columns(2)
                    if _rc[0].button("\u21ba Ja, neu aufsetzen", key=f"hf_reset_yes_{_k}",
                                     use_container_width=True):
                        with st.spinner("Setze zur\u00fcck und baue nach aktuellen Regeln neu auf ..."):
                            try:
                                import hedgefund
                                hedgefund.reset(_k, refill=True, scan_size=50)
                                st.session_state.pop("hf_confirm_reset", None)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Zur\u00fccksetzen fehlgeschlagen: {e}")
                    if _rc[1].button("Abbrechen", key=f"hf_reset_no_{_k}",
                                     use_container_width=True):
                        st.session_state.pop("hf_confirm_reset", None)
                        st.rerun()
        # --- ALLE Strategien gemeinsam neu starten ---
        with st.expander("\u21ba ALLE STRATEGIEN NEU STARTEN", expanded=False):
            st.caption("Setzt **alle vier** Depots gleichzeitig zur\u00fcck und "
                       "baut sie aus einem gemeinsamen Kandidaten-Scan neu auf. "
                       "Sinnvoll, wenn sich die Datengrundlage ge\u00e4ndert hat \u2013 "
                       "dann sind alte und neue Ergebnisse ohnehin nicht "
                       "vergleichbar.")
            _grund = st.text_input(
                "Grund (wird gespeichert)",
                value="Umstellung auf roic.ai-Daten",
                key="hf_reset_grund",
                help="Erscheint sp\u00e4ter neben jedem Depot. Ohne Vermerk "
                     "l\u00e4sst sich in einigen Monaten nicht mehr sagen, "
                     "warum die Historie dort beginnt.")
            try:
                import roic as _rhf
                if not _rhf.enabled():
                    st.warning("\u26a0\ufe0f **roic.ai ist in dieser App nicht "
                               "aktiv** (ROIC_API_KEY fehlt in den Secrets). "
                               "Ein Neustart w\u00fcrde jetzt wieder auf die "
                               "Gratisquellen zur\u00fcckfallen \u2013 also genau auf "
                               "die Datenlage, die du hinter dir lassen "
                               "wolltest. Erst den Schl\u00fcssel setzen.")
            except Exception:
                pass
            st.warning("**Das verwirft die gesamte bisherige Historie** aller "
                       "vier Strategien: Positionen, Trades, Wertentwicklung. "
                       "Das ist nicht r\u00fcckg\u00e4ngig zu machen.")
            _ok = st.checkbox("Ja, ich m\u00f6chte alle vier Depots verwerfen",
                              key="hf_reset_all_ok")
            if st.button("\u21ba ALLE NEU AUFSETZEN", key="hf_reset_all_go",
                         disabled=not _ok, use_container_width=True):
                with st.spinner("Setze alle Depots zur\u00fcck und baue neu auf \u2026"):
                    try:
                        import hedgefund as _hfm
                        _hfm.reset_all(refill=True, scan_size=60,
                                       grund=_grund.strip())
                        st.session_state.pop("hf_reset_all_ok", None)
                        st.success("Alle Strategien neu aufgesetzt.")
                        st.rerun()
                    except Exception as _e:
                        st.error(f"Neustart fehlgeschlagen: {_e}")

        _hb = st.columns(2)
        if _hb[0].button("\U0001f4b6 Werte aktualisieren (nur Kurse)",
                         use_container_width=True):
            with st.spinner("Hole aktuelle Kurse ..."):
                try:
                    import hedgefund
                    hedgefund.refresh_prices()
                    st.rerun()
                except Exception as e:
                    st.error(f"Kurs-Update fehlgeschlagen: {e}")
        if _hb[1].button("\U0001f504 Jetzt pr\u00fcfen & anpassen (handelt!)",
                         use_container_width=True):
            with st.spinner("Pr\u00fcfe Positionen und f\u00fclle Slots ..."):
                try:
                    import hedgefund
                    hedgefund.run_all(scan_size=50)
                    st.rerun()
                except Exception as e:
                    st.error(f"Update fehlgeschlagen: {e}")
        st.caption("\U0001f4b6 **Nur Kurse**: bewertet die Depots neu, handelt aber "
                   "**nicht** \u2013 schnell und ohne Nebenwirkungen. \u00b7 "
                   "\U0001f504 **Pr\u00fcfen & anpassen**: wendet die Regeln an "
                   "(Take-Profit, Stop-Loss, Gewinn-Stop, Signal erloschen) und "
                   "besetzt freie Slots neu \u2013 kann also Positionen \u00f6ffnen und "
                   "schlie\u00dfen.")
        st.markdown("---")

        st.markdown('<div class="sec-title">\u2696\ufe0f LONG / SHORT-RADAR</div>',
                    unsafe_allow_html=True)
        st.caption("Einheitlicher Screen nach beiden Richtungen. LONG = Qualit\u00e4t + "
                   "Bewertungs-Upside. SHORT = deutlich \u00fcberbewertet + schw\u00e4chere "
                   "Qualit\u00e4t + KEIN starker Aufw\u00e4rtstrend. Volatilit\u00e4t = nur Kontext. "
                   "\U0001f449 Orangenen Ticker anklicken \u2192 Einzelanalyse.")

        lc = st.columns([1.4, 1, 1])
        region_choice = lc[0].selectbox(
            "Markt", ["USA + Europa", "Nur USA", "Nur Europa", "Breit (inkl. Asien)"],
            key="ls_region")
        depth = lc[1].select_slider("Tiefe", ["schnell", "mittel", "gr\u00fcndlich"],
                                    value="gr\u00fcndlich", key="ls_depth")
        _REG = {"USA + Europa": ["us", "de", "fr", "gb", "nl", "ch"],
                "Nur USA": ["us"], "Nur Europa": ["de", "fr", "gb", "nl", "ch", "it", "es"],
                "Breit (inkl. Asien)": ["us", "de", "fr", "gb", "nl", "ch", "jp", "hk"]}
        _SIZE = {"schnell": 60, "mittel": 100, "gr\u00fcndlich": 160}

        if lc[2].button("\U0001f50d Scan starten", use_container_width=True):
            st.session_state["ls_run"] = True

        if st.session_state.get("ls_run"):
            with st.spinner("Scanne Universum (Kennzahlen + Trend) \u2013 der erste Lauf "
                            "dauert etwas ..."):
                longs, shorts = longshort_candidates(
                    tuple(_REG[region_choice]), 5.0, _SIZE[depth])

            st.markdown('<div class="sec-title" style="color:#3FB950">\U0001f7e2 LONG-KANDIDATEN'
                        '</div>', unsafe_allow_html=True)
            if longs:
                vr_table([{k: v for k, v in r.items() if k != "Vola %"} for r in longs],
                         score_cols=("Comp.", "Chance"), signed_cols=("Upside %",),
                         height=min(len(longs) * 40 + 46, 520))
                st.caption("Sortiert nach \u201eChance\u201c (Qualit\u00e4t + Bewertungs-Upside "
                           "+ Piotroski-Bonus). **F** = Piotroski F-Score (0\u20139, "
                           "fundamentale St\u00e4rke; \u2265 7 filtert Value-Fallen). "
                           "\u2191 \u00fcber 200T = Aufw\u00e4rtstrend best\u00e4tigt die Idee.")
            else:
                st.info("Keine \u00fcberzeugenden Long-Kandidaten in diesem Universum "
                        "(verlangt Composite \u2265 58 und Upside \u2265 +10 %).")

            st.markdown('<div class="sec-title" style="color:#F85149;margin-top:14px">'
                        '\U0001f534 SHORT-KANDIDATEN \u00b7 mit Vorsicht</div>',
                        unsafe_allow_html=True)
            if shorts:
                vr_table(shorts, score_cols=("Comp.", "Risiko-Fit"),
                         signed_cols=("Upside %",),
                         height=min(len(shorts) * 40 + 46, 520))
                st.caption("**Z** = Altman Z (< 1,8 = Pleiterisiko), **M** = "
                           "Beneish M (> \u22122,22 = m\u00f6gliche Bilanzmanipulation). Nur "
                           "Titel, die \u00fcberbewertet UND fundamental problematisch "
                           "sind, nicht in starkem Aufw\u00e4rtstrend, ohne Squeeze-"
                           "Gefahr. Die \u201eWarnung\u201c nennt das forensische Signal. "
                           "Shorten ist f\u00fcr Privatanleger riskant \u2013 sieh das eher "
                           "als \u201ediese meiden\u201c denn als Aufforderung.")
            else:
                st.info("Aktuell keine vertretbaren Short-Kandidaten \u2013 entweder nichts stark "
                        "genug \u00fcberbewertet, oder die \u00dcberbewerteten laufen noch im "
                        "Aufw\u00e4rtstrend (bewusst ausgeblendet).")
            st.caption("Flache Datentiefe (API-schonend) \u2013 jeden Treffer vor einer "
                       "Entscheidung in der Einzelanalyse mit tiefen Daten gegenpr\u00fcfen.")

            # ---------- HEDGEFONDS-MODUS: konkreter Portfolio-Vorschlag ----------
            st.markdown('<div class="sec-title" style="margin-top:16px">\U0001f3db\ufe0f '
                        'HEDGEFONDS-MODUS \u00b7 Portfolio-Vorschlag</div>',
                        unsafe_allow_html=True)
            hc = st.columns([1.4, 1, 1])
            strat_label = hc[0].selectbox("Strategie", [
                "Marktneutral (Long 100 / Short 100)",
                "130/30 (Long 130 / Short 30)",
                "Qualit\u00e4ts-Long (nur Long)"], key="hf_strat")
            capital = parse_eur(hc[1].text_input("Kapital \u20ac", value="10000",
                                                 key="hf_capital")) or 10000.0
            _SMAP = {"Marktneutral (Long 100 / Short 100)": "marktneutral",
                     "130/30 (Long 130 / Short 30)": "130/30",
                     "Qualit\u00e4ts-Long (nur Long)": "quality_long"}
            if hc[2].button("\U0001f3db\ufe0f Portfolio vorschlagen", use_container_width=True):
                st.session_state["hf_show"] = True
            if st.session_state.get("hf_show"):
                hp = hedgefund_proposal(longs, shorts, _SMAP[strat_label], capital)
                mc = st.columns(4)
                card(mc[0], "Brutto-Exposure", f"{hp['gross_pct']} %")
                card(mc[1], "Netto-Exposure", f"{hp['net_pct']} %",
                     sub="~0 = marktneutral" if _SMAP[strat_label] == "marktneutral" else "")
                card(mc[2], "\u00d8 Composite (Long)",
                     f"{hp['l_comp']:.0f}" if hp["l_comp"] is not None else "\u2014")
                card(mc[3], "Gew. Upside (Long)",
                     f"{hp['l_up']:+.1f} %" if hp["l_up"] is not None else "\u2014",
                     color="var(--green)")
                if hp["long"]:
                    st.markdown('<div class="sec-title" style="color:#3FB950">LONG-BUCH</div>',
                                unsafe_allow_html=True)
                    vr_table(hp["long"], score_cols=("Comp.",),
                             signed_cols=("Upside %",),
                             height=min(len(hp["long"]) * 40 + 46, 420))
                if hp["short"]:
                    st.markdown('<div class="sec-title" style="color:#F85149">SHORT-BUCH</div>',
                                unsafe_allow_html=True)
                    vr_table(hp["short"], score_cols=("Comp.",),
                             signed_cols=("Upside %",),
                             height=min(len(hp["short"]) * 40 + 46, 420))
                    st.caption("Gew. Upside Short-Buch: "
                               + (f"{hp['s_up']:+.1f} % (negativ = These intakt)"
                                  if hp["s_up"] is not None else "\u2014"))
                st.caption("Regelbasierte Konstruktion: Gewicht ~ Signalst\u00e4rke, max. 12 % je "
                           "Position, St\u00fcckzahlen auf dein Kapital gerechnet. F\u00fcr dein "
                           "externes Testdepot \u2013 kein Anlagerat. 130/30 & Marktneutral "
                           "erfordern real Margin/Leerverkauf beim Broker; Vorschlag hier ist "
                           "eine Simulation zum Lernen.")
        else:
            pass


# ===========================================================================
# BACKTEST - ehrliche historische Pruefung: trifft der Fair Value, bringt
# hoher Upside Rendite? Mit Look-ahead-Schutz.
# ===========================================================================
if nav == "Backtest":
    st.markdown('<div class="sec-title">BACKTEST \u2013 FUNKTIONIEREN UNSERE '
                'SIGNALE?</div>', unsafe_allow_html=True)
    st.caption("Ehrliche R\u00fcckschau: Wir rekonstruieren f\u00fcr vergangene "
               "Stichtage, welche Daten damals WIRKLICH bekannt waren (mit "
               "Puffer f\u00fcr die Berichtsverz\u00f6gerung \u2013 kein Blick in die "
               "Zukunft), berechnen den damaligen Fair Value mit unserer "
               "echten Logik und pr\u00fcfen zwei Fragen getrennt: Kam der Kurs "
               "dem Fair Value n\u00e4her? Und brachte hoher Upside mehr Rendite? "
               "Kein Anlagerat.")

    try:
        import backtest as _bt
    except Exception as _e:
        st.error(f"backtest.py fehlt oder ist veraltet: {_e}")
        _bt = None
    try:
        import roic as _btroic
    except Exception:
        _btroic = None

    if _bt is not None:
        # Bewusst GEMISCHTES Feld statt nur teurer Tech-Giganten: Zykliker,
        # Banken, Energie, Substanzwerte - auch Titel, die mal wirklich billig
        # waren. Nur so ist Frage 2 (bringt hoher Upside Rendite?) beantwortbar.
        # Breites, quer gestreutes Feld (~40 Titel) fuer mehr Datenpunkte -
        # besonders wichtig fuer Frage 3, die zuletzt an nur 3 Titeln haing.
        # Bewusst ueber alle Bewertungslagen: Zykliker, Banken, Energie,
        # Industrie, Konsum, Pharma, Tech, Telekom, Handel.
        _std_titel = (
            "F, GM, DAL, UAL, DOW, DD, CAT, DE, "        # Zykliker/Industrie
            "C, WFC, BAC, JPM, GS, MET, PRU, AIG, "      # Banken/Versicherung
            "XOM, CVX, COP, OXY, "                        # Energie
            "PFE, MRK, BMY, CVS, "                        # Pharma/Gesundheit
            "VZ, T, TMUS, "                               # Telekom
            "TGT, WMT, KR, "                              # Handel
            "INTC, CSCO, IBM, HPQ, "                      # Tech (reifer)
            "KO, PEP, MO, KHC"                            # Konsum
        )
        _eingabe = st.text_input(
            "Titel (Komma-getrennt, am besten langlebige US-Titel)",
            value=_std_titel, key="bt_ticker")
        st.caption("Voreingestellt ist ein **bewusst gemischtes Feld**: Zykliker "
                   "(F, GM, DAL, DOW), Banken (C, WFC, BAC), Versicherung (MET), "
                   "Energie (XOM, CVX), Substanz (PFE, VZ, T, TGT, INTC) \u2013 also "
                   "auch Titel, die zwischenzeitlich wirklich g\u00fcnstig waren. "
                   "Nur so l\u00e4sst sich Frage 2 beantworten, denn ein Feld aus "
                   "lauter teuren Tech-Giganten hat gar keine 'hoher Upside'-"
                   "Gruppe. Du kannst die Titel frei \u00e4ndern.")
        _c1, _c2, _c3 = st.columns(3)
        import datetime as _dtn
        _jn = _dtn.date.today().year
        _von = _c1.number_input("Von Jahr", min_value=_jn - 5, max_value=_jn - 1,
                                value=_jn - 4, key="bt_von")
        _bis = _c2.number_input("Bis Jahr", min_value=_jn - 4, max_value=_jn,
                                value=_jn - 1, key="bt_bis")
        _halte = _c3.selectbox("Haltedauer", [12, 24, 36],
                               format_func=lambda x: f"{x} Monate", key="bt_halte")

        st.caption("\u26a0\ufe0f **Dein roic-Tarif (Individual) liefert 5 Jahre "
                   "Historie.** Ein Backtest reicht also nur ~5 Jahre zur\u00fcck, "
                   "nicht weiter. Mehr Titel = mehr Datenpunkte (besser f\u00fcr die "
                   "Statistik), aber jeder Titel kostet mehrere roic-Abrufe \u2013 "
                   "das breite Feld dauert **1-2 Minuten** und kann ans "
                   "Rate-Limit sto\u00dfen. Zwei Stichtage pro Jahr verdoppeln die "
                   "Punkte. Bleibt ein Anhaltspunkt, keine Gewissheit.")

        if st.button("\U0001f9ea Backtest starten", key="bt_start"):
            _ticker = [t.strip().upper() for t in _eingabe.split(",") if t.strip()]
            if not _ticker:
                st.warning("Bitte mindestens einen Titel eingeben.")
            elif _btroic is None or not _btroic.enabled():
                st.error("roic ist nicht aktiv \u2013 der Backtest braucht die "
                         "historischen roic-Daten.")
            else:
                _stichtage = _bt.jahres_stichtage(int(_von), int(_bis), pro_jahr=2)
                _alle = []
                _pro_titel = {}
                _prog = st.progress(0.0)
                for _i, _tk in enumerate(_ticker):
                    try:
                        _z = _bt.einzeltest(_btroic, valuation, _tk, _stichtage,
                                            haltedauer=int(_halte),
                                            scoring_mod=scoring)
                        _alle.extend(_z)
                        _pro_titel[_tk] = len(_z)
                    except Exception as _e:
                        _pro_titel[_tk] = f"Fehler: {_e}"
                    _prog.progress((_i + 1) / len(_ticker))
                _prog.empty()

                if not _alle:
                    st.warning("Keine auswertbaren Datenpunkte. M\u00f6glich: roic "
                               "liefert f\u00fcr diese Titel keine tiefe Historie, "
                               "oder der Zeitraum ist zu kurz.")
                    with st.expander("\U0001f527 Diagnose: woran liegt es?"):
                        for _tk in _ticker[:3]:
                            st.markdown(f"**{_tk}**")
                            try:
                                import datetime as _dtd
                                _diag_st = _dtd.date(int(_von), 6, 15)
                                for _zeile in _bt.diagnose(_btroic, _tk, _diag_st):
                                    st.text(_zeile)
                            except Exception as _de:
                                st.text(f"Diagnose-Fehler: {_de}")
                else:
                    _a = _bt.auswertung(_alle)
                    st.markdown("### Ergebnis")
                    # Kurzuebersicht: wie viele Titel lieferten Daten, welche nicht
                    _ok = sum(1 for v in _pro_titel.values()
                              if isinstance(v, int) and v > 0)
                    _leer = [k for k, v in _pro_titel.items()
                             if isinstance(v, int) and v == 0]
                    _fehler = [k for k, v in _pro_titel.items()
                               if not isinstance(v, int)]
                    _info = f"{_ok} von {len(_ticker)} Titeln lieferten Daten"
                    if _leer:
                        _info += f" \u00b7 ohne Historie: {', '.join(_leer)}"
                    if _fehler:
                        _info += f" \u00b7 Fehler: {', '.join(_fehler)}"
                    st.caption(_info)
                    _m1, _m2, _m3 = st.columns(3)
                    card(_m1, "Datenpunkte", str(_a["n"]),
                         "Titel \u00d7 Stichtage")
                    card(_m2, "Fair-Value-Treffer",
                         f"{_a['fv_treffer_pct']:.0f}%",
                         "Kurs n\u00e4herte sich dem FV",
                         score_color(_a['fv_treffer_pct']))
                    _rg = _a.get("rendite_gesamt")
                    card(_m3, "\u00d8 Rendite gesamt",
                         f"{_rg:+.1f}%" if _rg is not None else "\u2014",
                         f"nach {_halte} Monaten",
                         "var(--green)" if (_rg or 0) >= 0 else "var(--red)")

                    st.markdown("#### Frage 1: Trifft der Fair Value?")
                    st.write(f"In **{_a['fv_treffer_pct']:.0f}%** der F\u00e4lle "
                             f"({_a['fv_treffer_abs']} von {_a['n']}) bewegte sich "
                             f"der Kurs nach {_halte} Monaten in Richtung des "
                             f"damals berechneten Fair Value. Ein Wert deutlich "
                             f"\u00fcber 50% spricht daf\u00fcr, dass der Fair Value "
                             f"Information tr\u00e4gt; nahe 50% w\u00e4re er so gut wie "
                             f"ein M\u00fcnzwurf.")

                    st.markdown("#### Frage 2: Bringt hoher Upside mehr Rendite?")
                    _mo = _a.get("median_obere_haelfte")
                    _mu = _a.get("median_untere_haelfte")
                    _ro = _a.get("rendite_obere_haelfte")
                    _ru = _a.get("rendite_untere_haelfte")
                    _tab = [
                        {"Gruppe": f"Obere H\u00e4lfte (Upside \u2265 "
                                   f"{_a.get('upside_obere_min','?')}%)",
                         "Median Rendite": f"{_mo:+.1f}%" if _mo is not None else "\u2014",
                         "\u00d8 Rendite": f"{_ro:+.1f}%" if _ro is not None else "\u2014",
                         "Anzahl": _a.get("n_haelfte", 0)},
                        {"Gruppe": f"Untere H\u00e4lfte (Upside \u2264 "
                                   f"{_a.get('upside_untere_max','?')}%)",
                         "Median Rendite": f"{_mu:+.1f}%" if _mu is not None else "\u2014",
                         "\u00d8 Rendite": f"{_ru:+.1f}%" if _ru is not None else "\u2014",
                         "Anzahl": _a.get("n_haelfte", 0)},
                    ]
                    vr_table(_tab)
                    st.caption("**Median ist der belastbare Wert** \u2013 er ist immun "
                               "gegen einzelne Ausrei\u00dfer (ein +600%-Titel verzerrt "
                               "den Durchschnitt, nicht aber den Median). Relativer "
                               "Vergleich: obere gegen untere H\u00e4lfte nach Upside.")
                    # Urteil auf Basis des MEDIAN (robust)
                    if _mo is not None and _mu is not None:
                        if _mo > _mu:
                            st.success(f"\u2705 Nach Median brachte die H\u00e4lfte mit "
                                       f"h\u00f6herem Upside {_mo - _mu:+.1f} Prozentpunkte "
                                       f"mehr Rendite ({_mo:+.1f}% vs. {_mu:+.1f}%) \u2013 "
                                       f"das Signal trug Information (robust gegen "
                                       f"Ausrei\u00dfer gemessen).")
                        elif abs(_mo - _mu) < 3:
                            st.info(f"\u2696\ufe0f Nach Median lagen beide H\u00e4lften "
                                    f"praktisch gleichauf ({_mo:+.1f}% vs. "
                                    f"{_mu:+.1f}%) \u2013 das Upside-Signal trug in "
                                    f"diesem Zeitraum wenig Information.")
                        else:
                            st.warning(f"\u26a0\ufe0f Nach Median brachte die H\u00e4lfte "
                                       f"mit h\u00f6herem Upside NICHT mehr Rendite "
                                       f"({_mo:+.1f}% vs. {_mu:+.1f}%) \u2013 ehrlich "
                                       f"festzuhalten.")
                    # Rang-Korrelation (robust) als Hauptmass, normale daneben
                    _korr = _a.get("korrelation_rang")
                    _kornorm = _a.get("korrelation")
                    if _korr is not None:
                        _kortext = ("deutlich positiv" if _korr > 0.3 else
                                    "leicht positiv" if _korr > 0.1 else
                                    "praktisch kein Zusammenhang" if _korr > -0.1 else
                                    "leicht negativ" if _korr > -0.3 else
                                    "deutlich negativ")
                        st.caption(f"Rang-Korrelation Upside \u2194 Rendite (robust): "
                                   f"**{_korr:+.2f}** ({_kortext})"
                                   + (f" \u00b7 klassische Korrelation {_kornorm:+.2f}"
                                      if _kornorm is not None else "")
                                   + ". Die Rang-Korrelation z\u00e4hlt nur die "
                                   "Reihenfolge und ist daher ausrei\u00dfer-fest. "
                                   "Bei ~30 Punkten bleibt alles ein Anhaltspunkt, "
                                   "keine Gewissheit.")

                    # Frage 3: die VORAB festgelegte Hypothese
                    st.markdown("#### Frage 3: Trifft die feste Hypothese "
                                "(g\u00fcnstig UND stark)?")
                    if not _a.get("hyp_verfuegbar"):
                        st.info("Der Composite Score konnte historisch nicht "
                                "berechnet werden \u2013 die Hypothese ist f\u00fcr "
                                "diese Titel nicht auswertbar.")
                    else:
                        _hmt = _a.get("hyp_median_treffer")
                        _hmr = _a.get("hyp_median_rest")
                        st.caption(f"**Vorab festgelegt, nicht optimiert:** Titel mit "
                                   f"Upside > {_a.get('hyp_upside_min',0):.0f}% UND "
                                   f"Composite \u2265 {_a.get('hyp_composite_min',55):.0f} "
                                   f"gegen den Rest. Diese Schwellen wurden vor dem "
                                   f"Test festgelegt und werden nicht nachjustiert \u2013 "
                                   f"nur so ist es ehrliche Statistik statt "
                                   f"Kurvenanpassung.")
                        _htab = [
                            {"Gruppe": "G\u00fcnstig UND stark (Hypothese)",
                             "Median Rendite": f"{_hmt:+.1f}%" if _hmt is not None else "\u2014",
                             "\u00d8 Rendite": (f"{_a.get('hyp_schnitt_treffer'):+.1f}%"
                                            if _a.get('hyp_schnitt_treffer') is not None else "\u2014"),
                             "FV-Treffer": (f"{_a.get('hyp_treffer_fv_quote'):.0f}%"
                                            if _a.get('hyp_treffer_fv_quote') is not None else "\u2014"),
                             "Anzahl": _a.get("hyp_n_treffer", 0)},
                            {"Gruppe": "Rest",
                             "Median Rendite": f"{_hmr:+.1f}%" if _hmr is not None else "\u2014",
                             "\u00d8 Rendite": (f"{_a.get('hyp_schnitt_rest'):+.1f}%"
                                            if _a.get('hyp_schnitt_rest') is not None else "\u2014"),
                             "FV-Treffer": "\u2014",
                             "Anzahl": _a.get("hyp_n_rest", 0)},
                        ]
                        vr_table(_htab)
                        if _a.get("hyp_n_treffer", 0) == 0:
                            st.warning("\u26a0\ufe0f Kein einziger Titel erf\u00fcllte die "
                                       "Hypothese (g\u00fcnstig UND stark zugleich) in "
                                       "diesem Zeitraum \u2013 die Engine h\u00e4tte hier "
                                       "nichts gekauft. Aussage: nicht testbar mit "
                                       "diesen Titeln.")
                        elif _hmt is not None and _hmr is not None:
                            if _hmt > _hmr + 3:
                                st.success(f"\u2705 Die Hypothese h\u00e4lt (in diesem "
                                           f"kurzen Zeitraum): g\u00fcnstige UND starke "
                                           f"Titel brachten im Median {_hmt - _hmr:+.1f} "
                                           f"Prozentpunkte mehr ({_hmt:+.1f}% vs. "
                                           f"{_hmr:+.1f}%). Ein ehrliches, weil vorab "
                                           f"festgelegtes Signal \u2013 aber nur {_a.get('hyp_n_treffer')} "
                                           f"Treffer, also mit Vorsicht.")
                            elif abs(_hmt - _hmr) <= 3:
                                st.info(f"\u2696\ufe0f Die Hypothese-Gruppe lag praktisch "
                                        f"gleichauf mit dem Rest ({_hmt:+.1f}% vs. "
                                        f"{_hmr:+.1f}%). Kein klarer Vorteil \u2013 die "
                                        f"Kombination trug hier wenig.")
                            else:
                                st.warning(f"\u26a0\ufe0f Die Hypothese f\u00e4llt durch: "
                                           f"g\u00fcnstige UND starke Titel brachten NICHT "
                                           f"mehr ({_hmt:+.1f}% vs. {_hmr:+.1f}%). Ehrlich "
                                           f"festzuhalten \u2013 und wir justieren die "
                                           f"Schwelle bewusst NICHT nach.")

                    # Frage 4: die STRENGERE feste Hypothese (guenstig + stark + solide)
                    if _a.get("hyp_verfuegbar"):
                        st.markdown("#### Frage 4: Strengere Hypothese "
                                    "(g\u00fcnstig + stark + solide Bilanz)?")
                        _h2t = _a.get("hyp2_median_treffer")
                        _h2r = _a.get("hyp2_median_rest")
                        _h2n = _a.get("hyp2_n_treffer", 0)
                        st.caption(f"**Vorab festgelegt, nicht optimiert:** Upside > "
                                   f"{_a.get('hyp2_upside_min',15):.0f}% UND Composite "
                                   f"\u2265 {_a.get('hyp2_composite_min',60):.0f} UND "
                                   f"Netto-Verschuldung/EBITDA < "
                                   f"{_a.get('hyp2_netdebt_max',3):.0f} (solide Bilanz). "
                                   f"Katalysator bewusst ausgelassen \u2013 historisch "
                                   f"nicht sauber rekonstruierbar. Drei Bedingungen "
                                   f"sind streng; erwartungsgem\u00e4\u00df erf\u00fcllen sie nur "
                                   f"wenige Titel.")
                        if _h2n == 0:
                            st.warning("\u26a0\ufe0f **Kein einziger Titel** erf\u00fcllte alle "
                                       "drei Bedingungen in diesem Zeitraum. Die "
                                       "Hypothese ist damit **nicht testbar** \u2013 das "
                                       "ist das ehrliche Ergebnis, kein Beleg f\u00fcr "
                                       "oder gegen die Strategie. Genau die "
                                       "Overfitting-Falle, die wir vermeiden wollten: "
                                       "zu enge Filter treffen fast nie.")
                        elif _h2n < 4:
                            st.info(f"\u2696\ufe0f Nur **{_h2n} Titel** erf\u00fcllten alle drei "
                                    f"Bedingungen ({', '.join(_a.get('hyp2_treffer_titel', []))}). "
                                    f"Median-Rendite {_h2t:+.1f}% gegen den Rest "
                                    f"{_h2r:+.1f}%. **Zu wenige F\u00e4lle f\u00fcr eine "
                                    f"belastbare Aussage** \u2013 bei 1\u20133 Titeln ist "
                                    f"jedes Ergebnis Zufall. Ehrlich: nicht "
                                    f"aussagekr\u00e4ftig.")
                        else:
                            _h2tab = [
                                {"Gruppe": "G\u00fcnstig+stark+solide",
                                 "Median": f"{_h2t:+.1f}%" if _h2t is not None else "\u2014",
                                 "\u00d8": (f"{_a.get('hyp2_schnitt_treffer'):+.1f}%"
                                        if _a.get('hyp2_schnitt_treffer') is not None else "\u2014"),
                                 "FV-Treffer": (f"{_a.get('hyp2_treffer_fv_quote'):.0f}%"
                                                if _a.get('hyp2_treffer_fv_quote') is not None else "\u2014"),
                                 "Anzahl": _h2n},
                                {"Gruppe": "Rest",
                                 "Median": f"{_h2r:+.1f}%" if _h2r is not None else "\u2014",
                                 "\u00d8": "\u2014", "FV-Treffer": "\u2014",
                                 "Anzahl": _a.get("hyp2_n_rest", 0)},
                            ]
                            vr_table(_h2tab)
                            st.caption(f"Erf\u00fcllt von: "
                                       f"{', '.join(_a.get('hyp2_treffer_titel', []))}")
                            if _h2t is not None and _h2r is not None:
                                if _h2t > _h2r + 3:
                                    st.success(f"\u2705 Die strenge Kombination h\u00e4lt "
                                               f"(in diesem Zeitraum, {_h2n} Titel): "
                                               f"{_h2t - _h2r:+.1f} Prozentpunkte mehr "
                                               f"im Median. Ein ehrliches, weil vorab "
                                               f"festgelegtes Signal \u2013 mit der "
                                               f"n\u00f6tigen Vorsicht bei {_h2n} F\u00e4llen.")
                                elif abs(_h2t - _h2r) <= 3:
                                    st.info(f"\u2696\ufe0f Gleichauf mit dem Rest "
                                            f"({_h2t:+.1f}% vs. {_h2r:+.1f}%) \u2013 die "
                                            f"strenge Kombination trug hier keinen "
                                            f"klaren Vorteil.")
                                else:
                                    st.warning(f"\u26a0\ufe0f F\u00e4llt durch: {_h2t:+.1f}% vs. "
                                               f"{_h2r:+.1f}%. Wir justieren die "
                                               f"Schwellen bewusst NICHT nach.")

                    with st.expander("Alle Datenpunkte ansehen"):
                        vr_table([{
                            "Ticker": z["ticker"], "Stichtag": z["stichtag"],
                            "Kurs": z["kurs_damals"], "Fair Value": z["fair_value"],
                            "Upside %": z["upside_pct"],
                            "Composite": (round(z["composite"]) if z.get("composite")
                                          is not None else "\u2014"),
                            "Kurs sp\u00e4ter": z["kurs_spaeter"],
                            "Rendite %": z["rendite_pct"],
                            "FV genaehert": "\u2713" if z["fv_angenaehert"] else "\u2717",
                        } for z in _alle], signed_cols=("Upside %", "Rendite %"))

                    st.caption("**Ehrliche Grenzen:** Nur Titel, die roic historisch "
                               "abdeckt (\u00fcberlebende Firmen \u2013 Pleiten fehlen, "
                               "Survivorship-Bias). Fair Value nutzt die "
                               "Jahreszahlen mit Berichtspuffer, aber der "
                               "Analystenteil fehlt r\u00fcckwirkend. Ein erster "
                               "Anhaltspunkt, kein endg\u00fcltiges Urteil.")


# ===========================================================================
# FRAG CLAUDE - Denk- und Recherchepartner (aendert KEINE Modellzahlen)
# ===========================================================================
# ===========================================================================
# THESEN-BILANZ - dein ehrlicher Spiegel: gehen DEINE eigenen Thesen auf?
# ===========================================================================
if nav == "ThesenTrack":
    st.markdown('<div class="sec-title">THESEN-BILANZ \u2013 TRIFFT DEIN '
                'URTEIL?</div>', unsafe_allow_html=True)
    st.caption("Kein Modell-Lernen \u2013 dein eigener Spiegel. Das Tool schaut "
               "nach, was aus deinen gespeicherten Thesen wurde: Gingen sie "
               "auf? Triffst du besser, wenn du \u00fcberzeugt warst? Wie der "
               "Backtest, aber angewandt auf DEIN Urteil. So lernst nicht das "
               "Tool aus dir \u2013 sondern du aus dir selbst. Kein Anlagerat.")

    _alle_thesen = store.get_alle_thesen()
    if not _alle_thesen:
        st.info("Noch keine Thesen gespeichert. Die Eingabemasken in der "
                "Einzelanalyse wurden entfernt \u2013 bereits gespeicherte Thesen "
                "werden hier weiterhin ausgewertet.")
    else:
        st.caption(f"{len(_alle_thesen)} Thesen gespeichert. Aktuelle Kurse "
                   "werden geladen \u2013 das kann einen Moment dauern.")
        if st.button("\U0001f504 Bilanz berechnen", key="tt_calc"):
            _bewertungen = []
            _zeilen = []
            _prog = st.progress(0.0)
            _items = list(_alle_thesen.items())
            for _i, (_tk, _th) in enumerate(_items):
                if _th.get("start_kurs"):
                    try:
                        _f = load_fundamentals_deep(_tk)
                        _akt = _f.get("price") if _f else None
                    except Exception:
                        _akt = None
                    _b = these_mod.these_bewerten(_th, _akt)
                    if _b:
                        _bewertungen.append(_b)
                        _zeilen.append({
                            "Ticker": _tk,
                            "Name": (_th.get("name") or _tk)[:20],
                            "Endmarkt": (_th.get("endmarkt") or "\u2014")[:18],
                            "Angelegt": _th.get("angelegt", "\u2014"),
                            "Start": _th.get("start_kurs"),
                            "Aktuell": round(_akt, 2) if _akt else "\u2014",
                            "Rendite %": _b["rendite_pct"],
                            "\u00dcberzeugung": _b.get("ueberzeugung") or "\u2014",
                            "Ziel erreicht": ("\u2713" if _b["ziel_erreicht"]
                                              else "\u2717" if _b["ziel_erreicht"] is False
                                              else "\u2014"),
                        })
                _prog.progress((_i + 1) / len(_items))
            _prog.empty()

            if not _bewertungen:
                st.warning("Keine auswertbaren Thesen \u2013 es fehlen Startkurse. "
                           "Thesen, die vor diesem Update angelegt wurden, haben "
                           "noch keinen Startkurs. Speichere sie einmal neu, "
                           "dann z\u00e4hlen sie ab jetzt.")
            else:
                _tr = these_mod.trackrecord_auswerten(_bewertungen)
                _m1, _m2, _m3 = st.columns(3)
                card(_m1, "Thesen gemessen", str(_tr["n"]), "mit Startkurs")
                _mr = _tr.get("median_rendite")
                card(_m2, "Median-Rendite",
                     f"{_mr:+.1f}%" if _mr is not None else "\u2014",
                     "seit Anlage",
                     "var(--green)" if (_mr or 0) >= 0 else "var(--red)")
                _zt = _tr.get("ziel_treffer_pct")
                card(_m3, "Ziel-Trefferquote",
                     f"{_zt:.0f}%" if _zt is not None else "\u2014",
                     f"{_tr.get('ziel_treffer',0)} von {_tr.get('n_mit_ziel',0)}",
                     score_color(_zt) if _zt is not None else "var(--amber)")

                # Der eigentliche Erkenntnis-Moment: Ueberzeugung vs. Treffer
                _mh = _tr.get("median_hohe_ueberzeugung")
                _mn = _tr.get("median_niedrige_ueberzeugung")
                if _mh is not None and _mn is not None:
                    st.markdown("#### Triffst du besser, wenn du \u00fcberzeugt bist?")
                    vr_table([
                        {"Gruppe": "Hohe \u00dcberzeugung (4\u20135)",
                         "Median-Rendite": f"{_mh:+.1f}%",
                         "Anzahl": _tr.get("n_hohe_ueberzeugung", 0)},
                        {"Gruppe": "Vage Idee (1\u20132)",
                         "Median-Rendite": f"{_mn:+.1f}%",
                         "Anzahl": _tr.get("n_niedrige_ueberzeugung", 0)},
                    ])
                    if _mh > _mn + 3:
                        st.success("\u2705 Deine \u00fcberzeugten Thesen liefen besser als "
                                   "deine vagen Ideen \u2013 ein Zeichen, dass deine "
                                   "\u00dcberzeugung echte Information tr\u00e4gt. Vertrau "
                                   "ihr, aber bleib demütig.")
                    elif _mh < _mn - 3:
                        st.warning("\u26a0\ufe0f Deine vagen Ideen liefen besser als deine "
                                   "\u00fcberzeugten Thesen. Das ist unbequem, aber "
                                   "lehrreich: Vielleicht \u00fcbersch\u00e4tzt du dich "
                                   "gerade dort, wo du dir am sichersten bist. "
                                   "Ein klassischer Denkfehler \u2013 gut, ihn zu sehen.")
                    else:
                        st.info("\u2696\ufe0f \u00dcberzeugung und Trefferquote h\u00e4ngen bei "
                                "dir bisher kaum zusammen. Bei wenigen Thesen "
                                "normal \u2013 beobachte es weiter.")

                st.markdown("#### Deine Thesen im Einzelnen")
                vr_table(_zeilen, signed_cols=("Rendite %",))
                st.caption(f"Beste These {_tr.get('beste'):+.1f}%, schlechteste "
                           f"{_tr.get('schlechteste'):+.1f}%. **Wenige Thesen = "
                           "noch kein Urteil \u00fcber dein K\u00f6nnen.** Der Wert "
                           "entsteht \u00fcber Monate und Jahre, wenn du siehst, wo "
                           "du echte St\u00e4rken hast und wo du dich t\u00e4uschst.")


# ===========================================================================
# PORTFOLIOCHECK
# ===========================================================================
if nav == "Portfoliocheck":
    st.markdown('<div class="sec-title">PORTFOLIOCHECK</div>', unsafe_allow_html=True)
    st.caption("Pro Position: Ticker ODER Firmenname, Anzahl und \u00d8 Buy-in-Kurs (\u20ac). "
               "Wert = Anzahl \u00d7 aktueller Intraday-Kurs. Gewinn/Verlust & Live-Kurse "
               "immer aktiv.")

    _pt_view = st.radio("Ansicht", ["\U0001f4ca Analyse", "\U0001f4d3 Logbuch"],
                        horizontal=True, label_visibility="collapsed",
                        key="pt_view")
    if _pt_view.endswith("Logbuch"):
        st.markdown('<div class="sec-title">\U0001f4d3 PORTFOLIO-LOGBUCH</div>',
                    unsafe_allow_html=True)
        st.caption("Verk\u00e4ufe \u00fcber den \u2715-Button landen automatisch hier. "
                   "Zus\u00e4tzlich kannst du Transaktionen manuell eintragen.")
        render_pf_logbook()
    if _pt_view.endswith("Analyse"):

        # --- Aktuelles Portfolio als Liste von dicts in session_state["pf_records"] ---
        def _pf_load(name):
            recs = store.load_all().get(name, [])
            st.session_state["pf_records"] = [
                {"ticker": str(r.get("ticker") or ""),
                 "shares": r.get("shares"),
                 "avg_buyin": r.get("avg_buyin")} for r in recs]
            st.session_state["pf_cur_name"] = name
            st.session_state["pf_edit_open"] = False
            st.session_state.pop("pf_editor", None)

        def _pf_new():
            st.session_state["pf_records"] = []
            st.session_state["pf_cur_name"] = ""
            st.session_state["pf_edit_open"] = True        # Editor gleich aufklappen
            st.session_state.pop("pf_editor", None)

        def _editor_to_records(df):
            out = []
            try:
                recs = df.to_dict("records")
            except Exception:
                recs = []
            for r in recs:
                tk = str(r.get("Ticker/Unternehmen") or "").strip()
                if not tk:
                    continue
                out.append({"ticker": tk, "shares": r.get("Anzahl"),
                            "avg_buyin": r.get("\u00d8 Buy-in (\u20ac)")})
            return out

        def _render_pf_editor():
            st.markdown("---")
            # Anker direkt vor dem Editor: st.data_editor loest bei jeder
            # Eingabe einen Rerun aus, und auf Mobil springt die Seite dabei
            # nach oben. Ist der Editor offen, scrollen wir nach dem Rerun
            # zu diesem Anker zurueck - die Position bleibt beim Tippen erhalten.
            st.markdown('<div id="pf-editor-anchor"></div>', unsafe_allow_html=True)
            if st.session_state.get("pf_edit_open"):
                components.html(
                    "<script>setTimeout(function(){try{"
                    "var d=window.parent.document;"
                    "var a=d.getElementById('pf-editor-anchor');"
                    "if(a){a.scrollIntoView({block:'start',behavior:'auto'});}"
                    "}catch(e){}},80);</script>", height=0)
            with st.expander("\u270f\ufe0f Portfolio bearbeiten / anlegen",
                             expanded=st.session_state.get("pf_edit_open", False)):
                st.caption("Kompakte Tabelle: Ticker/Unternehmen, Anzahl, \u00d8 Buy-in (\u20ac). "
                           "Unterste leere Zeile = neue Position; Zeile markieren + Entf = "
                           "l\u00f6schen. Danach \u00fcbernehmen bzw. speichern.")
                # WICHTIG: alle Spalten als reine Strings. Gemischte Typen (leere
                # Strings + Zahlen) belasten die Arrow-Konvertierung von
                # st.data_editor - auf Python 3.14 eine Absturzquelle.
                _seed = pd.DataFrame(
                    [{"Ticker/Unternehmen": str(r.get("ticker") or ""),
                      "Anzahl": ("" if r.get("shares") in (None, "")
                                 else str(r.get("shares"))),
                      "\u00d8 Buy-in (\u20ac)": ("" if r.get("avg_buyin") in (None, "")
                                                 else str(r.get("avg_buyin")))}
                     for r in st.session_state.get("pf_records", [])]
                    or [{"Ticker/Unternehmen": "", "Anzahl": "",
                         "\u00d8 Buy-in (\u20ac)": ""}]).astype(str)
                _edited = st.data_editor(_seed, num_rows="dynamic", use_container_width=True,
                                         hide_index=True, key="pf_editor")
                _name = st.text_input("Speichern als",
                                      value=st.session_state.get("pf_cur_name", ""),
                                      placeholder="Name des Portfolios", key="pf_save_name")
                _ec = st.columns(2)
                if _ec[0].button("\u2714\ufe0f \u00dcbernehmen (nur anzeigen)",
                                 use_container_width=True):
                    st.session_state["pf_records"] = _editor_to_records(_edited)
                    st.session_state["pf_edit_open"] = True
                    st.session_state.pop("pf_editor", None)
                    st.rerun()
                if _ec[1].button("\U0001f4be \u00dcbernehmen & speichern",
                                 use_container_width=True):
                    _recs = _editor_to_records(_edited)
                    st.session_state["pf_records"] = _recs
                    _clean = [{"ticker": r["ticker"], "value": None, "date": None,
                               "shares": parse_eur(r.get("shares")),
                               "avg_buyin": parse_eur(r.get("avg_buyin"))}
                              for r in _recs if r["ticker"]]
                    if _name.strip() and store.save(_name.strip(), _clean):
                        st.session_state["pf_cur_name"] = _name.strip()
                        st.session_state["pf_edit_open"] = False
                        st.session_state.pop("pf_editor", None)
                        st.success(f"Gespeichert als \u201e{_name.strip()}\u201c "
                                   f"({len(_clean)} Positionen).")
                        st.rerun()
                    else:
                        st.warning("Bitte einen Namen f\u00fcr das Portfolio angeben.")

        # KEIN Auto-Laden mehr: beim Öffnen des Tabs wird nichts berechnet.
        # Ein Portfolio wird erst geladen, wenn man es explizit anklickt.
        _pending = st.session_state.pop("pf_pending_load", None)
        if _pending:
            _pf_load(_pending)
        st.session_state.setdefault("pf_records", [])
        st.session_state.setdefault("pf_cur_name", "")

        saved = store.names()

        # --- Gespeichertes Portfolio laden (direkt bei Auswahl im Dropdown) ---
        if saved:
            st.markdown('<div class="vr-th">Gespeichertes Portfolio laden</div>',
                        unsafe_allow_html=True)
            _cur = st.session_state.get("pf_cur_name")
            _idx = saved.index(_cur) if _cur in saved else 0

            def _pf_on_select():
                # Direkt laden, sobald im Dropdown etwas Neues gewaehlt wird -
                # kein zusaetzlicher Button noetig. Nur laden, wenn sich die
                # Auswahl tatsaechlich vom aktuell geladenen Portfolio
                # unterscheidet (sonst unnoetiges Neuladen).
                _sel = st.session_state.get("pf_select")
                if _sel and _sel != st.session_state.get("pf_cur_name"):
                    _pf_load(_sel)

            _wahl = st.selectbox(
                "Portfolio", saved, index=_idx, key="pf_select",
                on_change=_pf_on_select,
                format_func=lambda n: (("\u2705 " if n == _cur else "") + n),
                label_visibility="collapsed")
            # Nur noch der Loesch-Button daneben (Laden passiert automatisch)
            _pc = st.columns([3, 1])
            _aktiv = (_wahl == _cur)
            _pc[0].caption("\u2705 Geladen" if _aktiv
                           else "Wird beim Ausw\u00e4hlen geladen \u2026")
            if _pc[1].button("\U0001f5d1\ufe0f", key="pf_del_sel",
                             use_container_width=True,
                             help=f"{_wahl} l\u00f6schen"):
                st.session_state["pf_confirm_delete"] = _wahl
                st.rerun()
            if st.session_state.get("pf_confirm_delete"):
                _dn = st.session_state["pf_confirm_delete"]
                st.warning(f"\u26a0\ufe0f Portfolio \u201e{_dn}\u201c wirklich l\u00f6schen? "
                           "Kann nicht r\u00fcckg\u00e4ngig gemacht werden.")
                dcc = st.columns(2)
                if dcc[0].button("\U0001f5d1\ufe0f Ja, endg\u00fcltig l\u00f6schen",
                                 use_container_width=True, key="pf_del_yes"):
                    store.delete(_dn)
                    st.session_state.pop("pf_confirm_delete", None)
                    if _dn == st.session_state.get("pf_cur_name"):
                        _pf_new()
                        st.session_state["pf_edit_open"] = False
                    st.rerun()
                if dcc[1].button("Abbrechen", use_container_width=True, key="pf_del_no"):
                    st.session_state.pop("pf_confirm_delete", None)
                    st.rerun()
        else:
            st.caption("Noch keine gespeicherten Portfolios \u2013 unten \u201e\u2795 Portfolio "
                       "hinzuf\u00fcgen\u201c und im Editor anlegen.")
        if st.button("\u2795 Portfolio hinzuf\u00fcgen", use_container_width=True):
            _pf_new()
            st.rerun()

        # --- Backup / Wiederherstellung (reboot-fest, weil auf DEINEM Geraet) ---
        # records aus dem aktuell geladenen Portfolio (pf_records) bauen
        records = []
        for r in st.session_state.get("pf_records", []):
            tkv = str(r.get("ticker") or "").strip()
            if not tkv:
                continue
            records.append({"ticker": tkv, "value": None,
                            "shares": parse_eur(r.get("shares")),
                            "date": None,
                            "avg_buyin": parse_eur(r.get("avg_buyin"))})

        inc_radar, inc_pl, live_px = False, True, True      # G/V & Intraday immer an
        if not records:
            st.info("Kein Portfolio geladen. Oben ein gespeichertes anklicken (\u201eLaden\u201c) "
                    "\u2013 oder \u201e\u2795 Portfolio hinzuf\u00fcgen\u201c und im Editor Positionen "
                    "eintragen.")
            _render_pf_editor()
        else:
            if st.button("\U0001f504 Kurse aktualisieren", use_container_width=True):
                load_intraday_price.clear()
                load_intraday_quote.clear()
                fx_to_eur.clear()                 # frischer Wechselkurs (sonst bis 30 Min alt)
                load_fundamentals.clear()
                _DEEP_CACHE.clear()               # manueller Cache von load_fundamentals_deep
                st.session_state.pop("pf_rows_cache", None)
                st.rerun()
            # Ergebnis fuer die Sitzung behalten: Bei vielen Positionen dauert
            # der Aufbau spuerbar, und Streamlit rechnet ihn sonst nach jedem
            # Tabwechsel neu. Schluessel enthaelt die Einstellungen, damit ein
            # Wechsel von z.B. "mit Radar" auch wirklich neu rechnet.
            _pf_key = (tuple(sorted(str(r.get("ticker") or "") for r in records)),
                       bool(inc_radar), bool(inc_pl), bool(live_px))
            _pf_cache = st.session_state.get("pf_rows_cache")
            if _pf_cache and _pf_cache.get("key") == _pf_key:
                rows = _pf_cache["rows"]
                invalid = _pf_cache["invalid"]
                resolved = _pf_cache["resolved"]
                _pc1, _pc2 = st.columns([3, 1])
                _pc1.caption(f"Stand {_pf_cache.get('zeit', '\u2014')} Uhr \u00b7 "
                             "aus dem Sitzungsspeicher")
                if _pc2.button("\U0001f504 Neu berechnen", key="pf_recalc",
                               use_container_width=True):
                    st.session_state.pop("pf_rows_cache", None)
                    st.rerun()
            else:
                with st.spinner("Analysiere Positionen (Intraday-Kurse) ..."):
                    rows, invalid, resolved = build_portfolio_rows(
                        records, inc_radar, inc_pl, live=live_px)
                st.session_state["pf_rows_cache"] = {
                    "key": _pf_key, "rows": rows, "invalid": invalid,
                    "resolved": resolved,
                    "zeit": _berlin_now().strftime("%H:%M"),
                }
            if live_px:
                n_live = sum(1 for r in rows if r.get("live"))
                st.caption(f"\u23f1 Intraday-Kurse aktiv f\u00fcr {n_live}/{len(rows)} Positionen \u00b7 "
                           f"Stand {_berlin_now().strftime('%H:%M:%S')} (dt. Zeit) \u00b7 "
                           "\u201eKurse aktualisieren\u201c f\u00fcr neuen Abruf.")

            if resolved:
                st.caption("Erkannt: " + "  \u00b7  ".join(f"{esc(a0)} \u2192 {esc(b0)}"
                                                           for a0, b0 in resolved))
            if invalid:
                # Diese Eintraege blieben auch nach der Symbolsuche ohne Kurs.
                st.warning("Keine Kursdaten (fehlen in allen Auswertungen "
                           "unten): " + ", ".join(esc(str(x)) for x in invalid))

            if not rows:
                st.info("Mindestens eine g\u00fcltige Position (Ticker/Name + Wert > 0) eintragen.")
            else:
                a = pf.analyze(rows)

                vcol = {"buy": "var(--green)", "watch": "var(--amber)", "drop": "var(--red)"}[a["vkey"]]
                _n_non_stock = a["n"] - a.get("n_stocks", a["n"])
                _score_note = (f' \u00b7 <span style="color:var(--muted)">Score \u00fcber '
                               f'{a.get("n_stocks", a["n"])} Einzelaktien '
                               f'(ETFs/Gold ausgeklammert)</span>' if _n_non_stock else "")
                st.markdown(
                    f'<div style="border:1px solid {vcol};border-radius:10px;padding:16px;margin:8px 0 14px">'
                    f'<div style="color:{vcol};font-size:26px;font-weight:800">Portfolio: {a["label"]} '
                    f'\u00b7 {a["score"]:.2f}/100</div>'
                    f'<div class="meta" style="margin-top:4px">Gesamtwert {sym_eur(a["total_eur"])} \u00b7 '
                    f'{a["n"]} Positionen \u00b7 effektiv {a["eff_positions"]:.2f} \u00b7 '
                    f'gr\u00f6\u00dfte Position {a["max_pos"]*100:.2f} % \u00b7 '
                    f'Top-Sektor {esc(a["max_sector_name"])} {a["max_sector"]*100:.2f} %'
                    f'{_score_note}</div></div>',
                    unsafe_allow_html=True)

                # Score-Erklaerung: warum dieser Score, was verbessern?
                _erk = pf.erklaere_score(a)
                with st.expander("\u2139\ufe0f Warum dieser Score \u2013 und was verbessern?",
                                 expanded=False):
                    st.markdown(f"**{_erk['fazit']}**")
                    if _erk["plus"]:
                        st.markdown("**Das spricht f\u00fcr das Depot:**")
                        for _p in _erk["plus"]:
                            st.markdown(f"- \u2705 {_p}")
                    if _erk["minus"]:
                        st.markdown("**Das bremst den Score:**")
                        for _m in _erk["minus"]:
                            st.markdown(f"- \u26a0\ufe0f {_m}")
                    if _erk["tipps"]:
                        st.markdown("**Verbessern:**")
                        for _t in _erk["tipps"]:
                            st.markdown(f"- \U0001f4a1 {_t}")
                    st.caption("Orientierung aus deinen Depotdaten \u2013 kein "
                               "Anlagerat.")

                ncards = 5 if a["have_pl"] else 4
                mc = st.columns(ncards)
                card(mc[0], "\u00d8 Composite (gew.)",
                     f"{a['w_composite']:.2f}" if a["w_composite"] is not None else "\u2014",
                     color=score_color(a["w_composite"] or 0))
                cov_sub = (f"{a.get('pf_cov', 0)}/{a['n']} Pos. bewertet"
                           if a.get("pf_cov") is not None else "")
                card(mc[1], "Erwartetes Upside",
                     f"{a['pf_upside']:+.2f} %" if a["pf_upside"] is not None else "\u2014",
                     sub=cov_sub,
                     color="var(--green)" if (a["pf_upside"] or 0) >= 0 else "var(--red)")
                card(mc[2], "Portfolio-Fair-Value", sym_eur(a["pf_fair_eur"]), sub=cov_sub)
                if a["have_pl"]:
                    g = a["pl_gain"]
                    gcol = "var(--green)" if g >= 0 else "var(--red)"
                    gtxt = f'{"+" if g >= 0 else "\u2212"}{sym_eur(abs(g))}'
                    card(mc[3], "Gewinn/Verlust ges.", gtxt,
                         sub=f"{a['pl_return']:+.2f} %" if a["pl_return"] is not None else "",
                         color=gcol)
                card(mc[ncards - 1], "\u00d8 Radar (gew.)",
                     f"{a['w_radar']:.2f}" if a["w_radar"] is not None else "\u2013")

                # Detailzeile Gewinn/Verlust seit Kauf
                if a["have_pl"]:
                    g = a["pl_gain"]
                    gcol = "var(--green)" if g >= 0 else "var(--red)"
                    st.markdown(
                        f'<div style="padding:8px 0 2px">Seit Kauf ({a["pl_count"]} von {a["n"]} '
                        f'Positionen mit Kauf-Info): '
                        f'<b style="color:{gcol}">{a["pl_return"]:+.2f} %  \u00b7  '
                        f'{"+" if g >= 0 else "\u2212"}{sym_eur(abs(g))}</b>'
                        f'  <span class="na">(Einsatz {sym_eur(a["pl_cost"])} \u2192 Wert '
                        f'{sym_eur(a["pl_value"])})</span></div>', unsafe_allow_html=True)

                # Positionsliste (orangenen Ticker anklicken -> Einzelanalyse)
                prows = sorted(rows, key=lambda r: -r["weight"])
                _pf_name_tbl = st.session_state.get("pf_cur_name", "")
                _komm_tbl = store.get_pos_kommentare(_pf_name_tbl) if _pf_name_tbl else {}
                data = [{"Ticker": r["ticker"], "Name": (r["name"] or "")[:18],
                         "Kurs \u20ac": round(r.get("price_eur") or 0, 2),
                         "Comp.": (round(r["composite"])
                                   if r.get("composite") is not None else None),
                         "Upside %": round(r["upside"], 2) if r.get("upside") is not None else None,
                         **({"Kauf %": round(r["ret_pct"], 2) if r.get("ret_pct") is not None else None}
                            if a["have_pl"] else {}),
                         **({"G/V \u20ac": round(r["gain_eur"], 2) if r.get("gain_eur") is not None else None}
                            if a["have_pl"] else {}),
                         "Wert \u20ac": round(r["value_eur"], 2),
                         "Status": positions_status(
                             r.get("upside"),
                             r.get("ret_pct") if a["have_pl"] else None)[0],
                         "Kommentar": (_komm_tbl.get(str(r["ticker"]).upper(), "") or "")[:40],
                         "\u2013\u2013": r["ticker"]} for r in prows]     # Verkaufs-Button
                vr_table(data, score_cols=("Comp.",),
                         signed_cols=("Upside %", "Kauf %", "G/V \u20ac"),
                         height=min(len(data) * 40 + 46, 460))
                st.caption("\U0001f449 Orangenen Ticker anklicken \u2192 Einzelanalyse \u00b7 "
                           "\u2715 rechts = Position verkaufen (mit Best\u00e4tigung, wird ins "
                           "Logbuch \u00fcbernommen).")
                st.caption(
                    "**Status** (Leitfrage: *W\u00fcrde ich zum heutigen Kurs neu "
                    "kaufen?*) \u2013 \U0001f7e2 Upside + / im Plus: l\u00e4uft \u00b7 "
                    "\U0001f535 Upside + / im Minus: These pr\u00fcfen \u00b7 "
                    "\U0001f7e1 Upside \u2212 / im Plus: nicht nachkaufen \u00b7 "
                    "\U0001f534 Upside \u2212 / im Minus: genau pr\u00fcfen "
                    "(Value-Trap-Gefahr). Kein Anlagerat \u2013 nur eine Sortierhilfe "
                    "f\u00fcr deine eigene Pr\u00fcfung.")

                # --- Kommentar-Spalte je Position (editierbar, dauerhaft) ------
                _pf_name_akt = st.session_state.get("pf_cur_name", "")
                if _pf_name_akt:
                    with st.expander("\U0001f4dd Kommentare je Position", expanded=True):
                        _pk_state = f"pf_poskomm_{_pf_name_akt}"
                        if _pk_state not in st.session_state:
                            st.session_state[_pk_state] = store.get_pos_kommentare(_pf_name_akt)
                        _gespeichert = st.session_state[_pk_state]
                        st.caption("Eine Notiz je Position \u2013 z.B. warum du sie "
                                   "h\u00e4ltst, Ziel/Stop, Beobachtungspunkte. "
                                   "\u00c4nderungen mit \u201eKommentare speichern\u201c sichern.")
                        _neu = {}
                        for r in prows:
                            _tk = str(r["ticker"]).upper()
                            _c1, _c2 = st.columns([1, 3], gap="small")
                            with _c1:
                                st.markdown(
                                    f'<div style="padding-top:6px;font-weight:700">'
                                    f'{esc(r["ticker"])}</div>'
                                    f'<div class="na" style="font-size:11px">'
                                    f'{esc((r.get("name") or "")[:22])}</div>',
                                    unsafe_allow_html=True)
                            with _c2:
                                _neu[_tk] = st.text_input(
                                    f"Kommentar {_tk}",
                                    value=_gespeichert.get(_tk, ""),
                                    key=f"poskomm_{_pf_name_akt}_{_tk}",
                                    label_visibility="collapsed",
                                    placeholder="Notiz \u2026")
                        if st.button("\U0001f4be Kommentare speichern",
                                     key=f"poskomm_save_{_pf_name_akt}"):
                            if store.set_pos_kommentare(_pf_name_akt, _neu):
                                st.session_state[_pk_state] = {
                                    k: v for k, v in _neu.items() if str(v).strip()}
                                st.success("Kommentare gespeichert.")
                            else:
                                st.error("Konnte nicht gespeichert werden.")

                # --- Verkauf bestaetigen (ausgeloest vom X-Button in der Tabelle) ---
                _sell = st.session_state.get("pf_confirm_sell")
                if _sell:
                    _pos = next((r for r in prows if r["ticker"] == _sell), None)
                    if _pos:
                        _amt = _pos.get("value_eur") or 0
                        _gv = _pos.get("gain_eur")
                        st.warning(
                            f"\u26a0\ufe0f **{_sell}** verkaufen? "
                            f"Position: {sym_eur(_amt)}"
                            + (f" \u00b7 G/V {'+' if (_gv or 0) >= 0 else '\u2212'}"
                               f"{sym_eur(abs(_gv))}" if _gv is not None else "")
                            + ". Die Position wird aus dem Portfolio entfernt und im "
                              "Logbuch eingetragen.")
                        _sc = st.columns(2)
                        if _sc[0].button("\u2714\ufe0f Ja, verkaufen & protokollieren",
                                         use_container_width=True, key="pf_sell_yes"):
                            _entry = {
                                "ts": time.time(),
                                "datum": _berlin_now().strftime("%d.%m.%Y %H:%M"),
                                "portfolio": st.session_state.get("pf_cur_name", ""),
                                "typ": "Verkauf", "ticker": _sell,
                                "anzahl": next((rec.get("shares") for rec in records
                                                if str(rec.get("ticker")).upper() == _sell), None),
                                "kurs_eur": round(_pos.get("price_eur") or 0, 2),
                                "betrag_eur": round(_amt, 2),
                                "gv_eur": round(_gv, 2) if _gv is not None else None,
                                "notiz": "\u00fcber Verkaufs-Button", "quelle": "auto"}
                            try:
                                store.pf_log_add(_entry)
                            except Exception as e:
                                st.error(f"Logbuch-Eintrag fehlgeschlagen: {e}")
                            # Position aus dem Portfolio entfernen (und speichern).
                            # Robust matchen: der angezeigte Ticker (_sell) kann
                            # ein aufgeloester Ticker sein (z.B. "AAPL"), waehrend
                            # in pf_records noch der Roheingabewert steht (z.B.
                            # "Apple"). Deshalb ueber BEIDES matchen: den
                            # Roheingabewert der verkauften Zeile UND den Ticker.
                            _sell_raw = (_pos.get("raw") or "").strip().upper()
                            _sell_tk = _sell.strip().upper()

                            def _ist_verkauft(rec):
                                _rt = str(rec.get("ticker", "")).strip().upper()
                                return _rt == _sell_tk or (_sell_raw and _rt == _sell_raw)

                            st.session_state["pf_records"] = [
                                r for r in st.session_state.get("pf_records", [])
                                if not _ist_verkauft(r)]
                            _nm = st.session_state.get("pf_cur_name", "")
                            if _nm:
                                store.save(_nm, [
                                    {"ticker": r["ticker"], "value": None, "date": None,
                                     "shares": parse_eur(r.get("shares")),
                                     "avg_buyin": parse_eur(r.get("avg_buyin"))}
                                    for r in st.session_state["pf_records"] if r.get("ticker")])
                            st.session_state.pop("pf_confirm_sell", None)
                            st.rerun()
                        if _sc[1].button("Abbrechen", use_container_width=True,
                                         key="pf_sell_no"):
                            st.session_state.pop("pf_confirm_sell", None)
                            st.rerun()
                    else:
                        st.session_state.pop("pf_confirm_sell", None)

                # Offene Kennzahlen fuer die Statistik im Logbuch hinterlegen
                _sc = [r for r in rows if r.get("ret_pct") is not None]
                st.session_state["pf_stats_open"] = {
                    "scored": len(_sc),
                    "wins": sum(1 for r in _sc if (r.get("ret_pct") or 0) > 0),
                    "gain": a.get("pl_gain") if a.get("have_pl") else None,
                    "cost": a.get("pl_cost") or 0}

                # Status je Position (wie frueher "Im Plus - halten" etc.) - inkl. konkreter
                # Gewinnabsicherungs-Marke, wo sie zutrifft.
                st.markdown('<div class="sec-title" style="margin-top:8px">STATUS JE POSITION</div>',
                            unsafe_allow_html=True)
                _scol = {"gr\u00fcn": "#3FB950", "gruen": "#3FB950", "gelb": "#FFB000",
                         "rot": "#F85149", "neutral": "#6B7686"}
                for r in prows:
                    lab, col, note = r.get("status", ("\u2014", "neutral", ""))
                    dot = _scol.get(col, "#6B7686")
                    line = (f'<span style="color:{dot};font-size:15px">\u25cf</span> '
                            f'<b class="tick">{esc(r["ticker"])}</b> '
                            f'<span style="color:{dot};font-weight:700">{esc(lab)}</span>')
                    if note:
                        line += f'<div class="sum" style="margin:1px 0 0 20px">{esc(note)}</div>'
                    st.markdown(f'<div class="rowline" style="padding:6px 0">{line}</div>',
                                unsafe_allow_html=True)

                # Thesen-Check: konkrete Aktionen aus dem Kauf-Status
                if a["have_pl"] and a["actions"]:
                    st.markdown('<div class="sec-title">THESEN-CHECK \u00b7 Aktionen aus Gewinn/Verlust</div>',
                                unsafe_allow_html=True)
                    cmap = {"rot": "var(--red)", "gelb": "var(--amber)", "gr\u00fcn": "var(--green)",
                            "neutral": "var(--muted)"}
                    for x in a["actions"]:
                        rp = f" ({x['ret_pct']:+.2f} %)" if x.get("ret_pct") is not None else ""
                        st.markdown(
                            f'<div class="news-box"><a>{esc(x["ticker"])} \u2014 {esc(x["name"] or "")}'
                            f'</a> <b style="color:{cmap[x["color"]]}">{esc(x["label"])}{rp}</b>'
                            f'<div class="meta">{esc(x["note"])}</div></div>', unsafe_allow_html=True)


                # Sektor-Allokation
                ac = st.columns(2)
                with ac[0]:
                    st.markdown('<div class="sec-title">SEKTOR-ALLOKATION</div>', unsafe_allow_html=True)
                    sdf = [(k, round(v * 100, 1)) for k, v in a["sector_alloc"].items()]
                    sdf.sort(key=lambda kv: -kv[1])
                    st.markdown(svg_hbars(sdf), unsafe_allow_html=True)
                with ac[1]:
                    st.markdown('<div class="sec-title">KLUMPEN & \u00dcBERSCHNEIDUNGEN</div>',
                                unsafe_allow_html=True)
                    cmap = {"rot": "var(--red)", "gelb": "var(--amber)", "gr\u00fcn": "var(--green)"}
                    for col, txt in a["flags"]:
                        st.markdown(f'<div style="padding:6px 10px;border-bottom:1px solid #1F2733">'
                                    f'<b style="color:{cmap[col]}">\u25cf</b>&nbsp; {esc(txt)}</div>',
                                    unsafe_allow_html=True)

                # Schwaechste Positionen
                if a["weak"]:
                    st.markdown('<div class="sec-title">SCHW\u00c4CHSTE POSITIONEN \u00b7 reduzieren/ersetzen pr\u00fcfen</div>',
                                unsafe_allow_html=True)
                    for w in a["weak"]:
                        st.markdown(f'<div class="news-box"><a>{esc(w["ticker"])} \u2014 {esc(w["name"] or "")}</a>'
                                    f'<div class="meta">{esc(" \u00b7 ".join(w["reasons"]))}</div></div>',
                                    unsafe_allow_html=True)

                # --- Wertentwicklung gegen die grossen Indizes
                st.markdown('<div class="sec-title">WERTENTWICKLUNG \u00b7 '
                            'PORTFOLIO GEGEN DIE INDIZES</div>',
                            unsafe_allow_html=True)

                @st.cache_data(ttl=900, show_spinner=False)
                def _pf_perf(_key, _rows):
                    return pf.performance(_rows)

                try:
                    _perf = _pf_perf(tuple(sorted(r["ticker"] for r in rows)),
                                     [{"ticker": r["ticker"],
                                       "value_eur": r["value_eur"]} for r in rows])
                except Exception as _e:
                    _perf = None
                    st.caption(f"(nicht berechenbar: {_e})")

                if not _perf:
                    st.caption("Wertentwicklung derzeit nicht berechenbar.")
                else:
                    _pc = st.columns(2)
                    card(_pc[0], "Portfolio heute",
                         (f"{de(_perf['pf_heute'], 2)} %"
                          if _perf["pf_heute"] is not None else "\u2014"),
                         f"{_perf['n']} Positionen",
                         "var(--green)" if (_perf["pf_heute"] or 0) >= 0
                         else "var(--red)")
                    card(_pc[1], "Portfolio 1 Monat",
                         (f"{de(_perf['pf_monat'], 2)} %"
                          if _perf["pf_monat"] is not None else "\u2014"),
                         "gewichtet nach Positionswert",
                         "var(--green)" if (_perf["pf_monat"] or 0) >= 0
                         else "var(--red)")

                    vr_table([{
                        "Portfolio vs.": i["name"],
                        "Heute": i["diff_heute"],
                        "1 Monat": i["diff_monat"],
                    } for i in _perf["indizes"]],
                        signed_cols=("Heute", "1 Monat"),
                        height=226)
                    if _perf["abdeckung"] < 95:
                        st.caption(f"\u26a0\ufe0f Nur {_perf['abdeckung']} % des "
                                   "Portfoliowerts konnten einbezogen werden"
                                   + (f" \u2013 ohne Kursdaten: "
                                      f"{', '.join(_perf['fehlend'][:6])}"
                                      if _perf["fehlend"] else "") + ".")

                # Portfolio bearbeiten: direkt unter dem Portfolio, VOR den Ideen.
                _render_pf_editor()

                # Vorschlaege zum Erg\u00e4nzen (aus Screener-Hot-Picks, Sektor-Luecken bevorzugt)
                st.markdown('<div class="sec-title">IDEEN ZUM ERG\u00c4NZEN \u00b7 Qualit\u00e4t mit Bewertungsabstand</div>',
                            unsafe_allow_html=True)
                if a["gaps"]:
                    st.caption("Unterrepr\u00e4sentierte Sektoren: " + ", ".join(a["gaps"][:6])
                               + "  \u00b7  Kandidaten aus US, DE, FR, GB, NL, CH, CA, JP, HK.")
                with st.spinner("Suche passende Kandidaten (mehrere L\u00e4nder) ..."):
                    held_t = {r["ticker"] for r in rows}
                    held_n = {(r["name"] or "").lower() for r in rows}
                    gaps = set(a["gaps"])
                    cands = portfolio_candidates(a, held_t, held_n)
                if cands:
                    cdf = pd.DataFrame([{"Ticker": c["ticker"], "Name": (c["name"] or "")[:22],
                                         "Chance": round(c.get("opportunity") or 0),
                                         "Score": c["score"],
                                         "Upside %": round(c["upside"], 2) if c.get("upside") is not None else None,
                                         "Sektor": (c["sector"] or "")[:16],
                                         "Land": (c.get("country") or "")[:14],
                                         "Preis \u20ac": c["price_eur"],
                                         "F\u00fcllt L\u00fccke": "ja" if c.get("sector") in gaps else ""}
                                        for c in cands])
                    vr_table(cdf.to_dict("records"),
                             score_cols=("Chance", "Score"), signed_cols=("Upside %",),
                             height=min(len(cdf) * 40 + 46, 460))
                    st.caption("\U0001f449 Orangenen Ticker anklicken \u2192 Einzelanalyse. "
                               "\u201eChance\u201c = Qualit\u00e4t + Bewertungs-Upside. Kein Anlagerat "
                               "\u2013 selbst pr\u00fcfen.")
                else:
                    st.info("Aktuell keine \u00fcberzeugenden Erg\u00e4nzungen gefunden (verlangt Qualit\u00e4t "
                            "Score \u2265 55, belastbarer Fair Value und glaubhaftes Upside +8 bis +80 %). "
                            "Bewusst lieber nichts vorschlagen als \u00fcberteuerte Titel.")

        # (Der Editor "Portfolio bearbeiten" wird jetzt direkt unter dem Portfolio
        #  bzw. beim Anlegen gerendert - siehe _render_pf_editor().)


# ===========================================================================
# TAB — UMFELD (Saisonalitaet, Sektorfuehrung, Reaktion auf Quartalszahlen)
# ===========================================================================
if nav == "Umfeld":
    import regime as rg

    @st.cache_data(ttl=21600, show_spinner=False)
    def _rg_state():
        return rg.market_state()

    @st.cache_data(ttl=21600, show_spinner=False)
    def _rg_lead():
        return rg.leadership()

    @st.cache_data(ttl=21600, show_spinner=False)
    def _rg_themen():
        return rg.themen_momentum()

    @st.cache_data(ttl=86400, show_spinner=False)
    def _rg_season(sektor, jahre):
        return rg.sector_seasonality(sektor, jahre)

    @st.cache_data(ttl=3600, show_spinner=False)
    def _rg_profile(t):
        return rg.reaction_profile(t)

    st.markdown('<div class="sec-title">\U0001f30d MARKTUMFELD</div>',
                unsafe_allow_html=True)
    st.caption("Beschreibende Statistik \u2013 **was war**, nicht was kommt. Alle "
               "Auswertungen nennen ihre Fallzahl. Kein Anlagerat.")

    _uv = st.radio("Ansicht",
                   ["\U0001f4c5 Anstehende Zahlen", "\U0001f4ca Sektorf\u00fchrung",
                    "\U0001f680 Themen", "\U0001f5d3\ufe0f Saisonalit\u00e4t",
                    "\U0001f4e2 Reaktion auf Zahlen"],
                   horizontal=True, label_visibility="collapsed", key="uv_view")

    # ---------------------------------------------------------- Sektorfuehrung
    if _uv.endswith("Sektorf\u00fchrung"):
        _ms = _rg_state()
        if _ms:
            _c = st.columns(2)
            card(_c[0], "Marktlage (S&P 500)", _ms["lage"],
                 f"{_ms['drawdown']:+.1f} % unter dem 12-Monats-Hoch",
                 "var(--green)" if _ms["drawdown"] > -5 else
                 ("var(--amber)" if _ms["drawdown"] > -20 else "var(--red)"))
            card(_c[1], "Historischer Hinweis", "\u2014", _ms["hinweis"],
                 "var(--amber)")
        _ld = _rg_lead()
        if not _ld:
            st.info("Sektordaten aktuell nicht abrufbar \u2013 sp\u00e4ter erneut versuchen.")
        else:
            st.markdown('<div class="sec-title" style="margin-top:14px">'
                        'RELATIVE ST\u00c4RKE (gegen S&P 500, Prozentpunkte)</div>',
                        unsafe_allow_html=True)
            vr_table([{"Sektor": r["sektor"], "ETF": r["etf"],
                       "3M": r["rel_3m"], "6M": r["rel_6m"], "12M": r["rel_12m"],
                       "Schnitt": r["schnitt"],
                       "Trend": ("\u2197\ufe0f anziehend"
                                 if (r["rel_3m"] is not None and r["rel_12m"] is not None
                                     and r["rel_3m"] > r["rel_12m"])
                                 else "\u2198\ufe0f abflauend"
                                 if (r["rel_3m"] is not None and r["rel_12m"] is not None)
                                 else "\u2014"),
                       "Anhaltend": "\u2713" if r["anhaltend"] else ""}
                      for r in _ld],
                     signed_cols=("3M", "6M", "12M", "Schnitt"),
                     height=min(len(_ld) * 40 + 46, 520))
            # Sektoren die anhaltend UND anziehend sind = die interessantesten
            _hot = [r["sektor"] for r in _ld if r["anhaltend"]
                    and r["rel_3m"] is not None and r["rel_12m"] is not None
                    and r["rel_3m"] > r["rel_12m"]]
            if _hot:
                st.success("**Anhaltend vorn UND anziehend** (3M-St\u00e4rke gr\u00f6\u00dfer "
                           "als 12M \u2013 der Trend beschleunigt sich): "
                           + ", ".join(_hot))
            _an = [r["sektor"] for r in _ld if r["anhaltend"]]
            if _an:
                st.success("**Anhaltend vorn** (\u00fcber 3, 6 **und** 12 Monate): "
                           + ", ".join(_an))
            st.caption("Ein Boom braucht hier keinen Namen: Er zeigt sich als "
                       "Sektor, der \u00fcber alle drei Zeitr\u00e4ume vor dem Index liegt. "
                       "Das findet auch den n\u00e4chsten Boom \u2013 eine Stichwortliste "
                       "m\u00fcsste man st\u00e4ndig pflegen. **Aber:** Relative St\u00e4rke sagt, "
                       "was gelaufen IST. Sie kann kurz vor dem Wendepunkt am "
                       "st\u00e4rksten aussehen.")

    # ----------------------------------------------------------------- Themen
    if _uv.endswith("Themen"):
        st.markdown('<div class="vr-th">\U0001f680 Themen im Aufschwung</div>',
                    unsafe_allow_html=True)
        st.caption("Kuratierte Themen-K\u00f6rbe quer durch Branchen \u2013 gemessen "
                   "wie die Sektorf\u00fchrung (relative St\u00e4rke ggü. Markt \u00fcber "
                   "3/6/12 Monate). **Wichtig:** Diese Themen sind **von Hand "
                   "gepflegt**, nicht automatisch entdeckt \u2013 das System misst "
                   "nur die hier definierten K\u00f6rbe, es findet keine neuen "
                   "Trends von selbst. Beschreibend (was war), kein Anlagerat.")
        _th = _rg_themen()
        if not _th:
            st.info("Themen-Daten noch nicht verf\u00fcgbar (Kursreihen laden).")
        else:
            for _t in _th:
                _pfeil = ("\u2197\ufe0f beschleunigt" if _t.get("beschleunigt")
                          else "\u2198\ufe0f flaut ab" if _t.get("beschleunigt") is False
                          else "")
                _stark = "\U0001f7e2" if _t.get("anhaltend") else "\u26aa"
                with st.container():
                    _c = st.columns([3, 1, 1, 1])
                    _c[0].markdown(
                        f"**{_stark} {_t['label']}**  \n"
                        f"<span style='color:var(--muted);font-size:0.85em'>"
                        f"{_t['beschreibung']} \u00b7 {_t['n_titel']}/"
                        f"{_t['n_gesamt']} Titel mit Daten</span>",
                        unsafe_allow_html=True)
                    _c[1].metric("3M", f"{_t['rel_3m']:+.0f}%"
                                 if _t['rel_3m'] is not None else "\u2014")
                    _c[2].metric("6M", f"{_t['rel_6m']:+.0f}%"
                                 if _t['rel_6m'] is not None else "\u2014")
                    _c[3].metric("12M", f"{_t['rel_12m']:+.0f}%"
                                 if _t['rel_12m'] is not None else "\u2014")
                    if _pfeil:
                        st.caption(f"{_pfeil} \u00b7 Titel: {', '.join(_t['ticker'])}")
                    else:
                        st.caption(f"Titel: {', '.join(_t['ticker'])}")
                    st.markdown("<hr style='margin:0.3em 0;border-color:"
                                "rgba(255,255,255,0.06)'>", unsafe_allow_html=True)
            st.caption("\U0001f7e2 = \u00fcber alle drei Zeitr\u00e4ume vorn (anhaltend) \u00b7 "
                       "\u26aa = gemischt. Relative St\u00e4rke zeigt, was gelaufen IST \u2013 "
                       "ein hei\u00dfes Thema kann kurz vor dem Wendepunkt am st\u00e4rksten "
                       "aussehen. Die K\u00f6rbe sind gleichgewichtet und handgepflegt.")

    # ---------------------------------------------------------- Saisonalitaet
    if _uv.endswith("Saisonalit\u00e4t"):
        _sc1, _sc2 = st.columns([2, 1])
        _sek = _sc1.selectbox("Sektor", list(rg.SECTOR_ETFS),
                              format_func=lambda k: rg.SECTOR_ETFS[k][1],
                              key="uv_sek")
        _jahre = _sc2.selectbox("Zeitraum", [10, 15, 20], index=2, key="uv_jahre")
        _se = _rg_season(_sek, _jahre)
        if not _se:
            st.info("Keine ausreichende Historie abrufbar.")
        else:
            st.markdown(f'<div class="sec-title" style="margin-top:8px">'
                        f'{_se["sektor"]} \u00b7 {_se["etf"]}</div>',
                        unsafe_allow_html=True)
            vr_table([{"Monat": m["monat"], "n": m["n"],
                       "\u00d8 %": m["avg"], "Median %": m["median"],
                       "Positiv %": m["trefferquote"]} for m in _se["monate"]],
                     signed_cols=("\u00d8 %", "Median %"), height=560)
            _nmin = min(m["n"] for m in _se["monate"])
            st.warning(f"**Vorsicht bei der Auslegung.** Je Monat liegen nur "
                       f"etwa {_nmin} Werte vor. Bei so kleinen Stichproben "
                       "sehen auch reine Zufallsmuster \u00fcberzeugend aus \u2013 ein "
                       "Unterschied von ein bis zwei Prozentpunkten zwischen "
                       "Monaten ist meist Rauschen. Bekannte Muster wie "
                       "\u201eSell in May\u201c sind zudem seit Jahrzehnten publiziert "
                       "und damit weitgehend eingepreist.")

    # -------------------------------------------- Reaktion auf Quartalszahlen
    if _uv.endswith("Reaktion auf Zahlen"):
        st.caption("Wie hat eine Aktie auf vergangene Quartalszahlen reagiert? "
                   "Zwei getrennte Fragen: Liegen die **Analysten** daneben, "
                   "und **belohnt der Markt** das \u00fcberhaupt?")
        _t = st.text_input("Ticker", value="", placeholder="z. B. NVDA, SAP.DE",
                           key="uv_tick").strip().upper()
        if _t:
            _p = _rg_profile(_t)
            if not _p:
                st.info(f"Keine Quartalshistorie f\u00fcr **{_t}** abrufbar. "
                        "yfinance liefert diese Daten nicht f\u00fcr alle Titel, "
                        "besonders selten f\u00fcr europ\u00e4ische Notierungen.")
            else:
                _k = st.columns(3)
                card(_k[0], "Beat-Quote", f"{_p['beat_quote']} %",
                     f"Analysten {_p['analysten']}",
                     "var(--green)" if _p["beat_quote"] >= 75 else "var(--amber)")
                card(_k[1], "davon belohnt",
                     (f"{_p['beat_belohnt_pct']} %"
                      if _p["beat_belohnt_pct"] is not None else "\u2014"),
                     f"Markt {_p['markt']}",
                     "var(--green)" if (_p["beat_belohnt_pct"] or 0) >= 70
                     else "var(--red)")
                card(_k[2], "\u00d8 Kursreaktion", f"{_p['avg_reaktion']:+.1f} %",
                     f"{_p['n']} Termine erfasst",
                     "var(--green)" if _p["avg_reaktion"] >= 0 else "var(--red)")
                st.info(f"**Einordnung:** {_p['urteil']}")

                st.markdown('<div class="sec-title" style="margin-top:14px">'
                            'DIE VIER F\u00c4LLE</div>', unsafe_allow_html=True)
                vr_table([{"Fall": k, "Anzahl": v,
                           "Anteil %": round(v / _p["n"] * 100)}
                          for k, v in _p["faelle"].items()], height=220)

                st.markdown('<div class="sec-title" style="margin-top:14px">'
                            'EINZELNE TERMINE</div>', unsafe_allow_html=True)
                vr_table([{"Datum": r["datum"], "Erwartet": r["erwartet"],
                           "Gemeldet": r["gemeldet"],
                           "\u00dcberraschung %": r.get("ueberraschung_pct"),
                           "Kursreaktion %": r["reaktion_pct"],
                           "Fall": r["fall"]} for r in _p["zeilen"]],
                         signed_cols=("\u00dcberraschung %", "Kursreaktion %"),
                         height=min(len(_p["zeilen"]) * 40 + 46, 400))
                # --- Langfristige Kursreaktion aus roic (viel mehr Termine)
                try:
                    import roic as _rr
                    _lang = (_rr.call_reaktionsprofil(_t)
                             if _rr.enabled() and _rr.covers(_t) else {})
                except Exception:
                    _lang = {}
                if _lang.get("n"):
                    st.markdown('<div class="sec-title" style="margin-top:14px">'
                                'KURSREAKTION \u00dcBER VIELE JAHRE</div>',
                                unsafe_allow_html=True)
                    _lk = st.columns(3)
                    card(_lk[0], "Termine", str(_lang["n"]),
                         "aus der Call-Historie", "var(--amber)")
                    card(_lk[1], "\u00d8 Ausschlag",
                         f"{_lang['median_ausschlag']:.1f} %",
                         "Median, ohne Vorzeichen", "var(--amber)")
                    card(_lk[2], "Reaktion gedreht",
                         f"{_lang['gedreht_pct']} %",
                         "binnen f\u00fcnf Handelstagen",
                         "var(--red)" if _lang["gedreht_pct"] >= 40
                         else "var(--green)")
                    st.caption(
                        f"An Zahlentagen bewegte sich der Titel im Mittel um "
                        f"**{_lang['median_ausschlag']:.1f} %**, in "
                        f"{_lang['positiv_pct']} % der F\u00e4lle nach oben. "
                        f"Gr\u00f6\u00dfte Ausschl\u00e4ge: {_lang['groesster_plus']:+.1f} % "
                        f"und {_lang['groesster_minus']:+.1f} %. "
                        "**\u201eReaktion gedreht\u201c** hei\u00dft: Die Richtung des "
                        "ersten Tages hielt f\u00fcnf Handelstage sp\u00e4ter nicht mehr. "
                        "Ein hoher Wert spricht daf\u00fcr, dass die erste Bewegung "
                        "eher Aufregung als Neubewertung war.")
                    vr_table([{
                        "Datum": z["datum"],
                        "Quartal": (f"Q{z['quartal']} {z['jahr']}"
                                    if z.get("quartal") else "\u2014"),
                        "Tag %": z["reaktion_pct"],
                        "nach 5 Tagen %": z["nach5t_pct"],
                    } for z in _lang["zeilen"][:20]],
                        signed_cols=("Tag %", "nach 5 Tagen %"),
                        height=min(len(_lang["zeilen"][:20]) * 40 + 46, 420))
                    st.caption("Diese Reihe stammt aus der Earnings-Call-"
                               "Historie und reicht deutlich weiter zur\u00fcck als "
                               "die acht Quartale oben. Sie sagt allerdings "
                               "NICHTS \u00fcber geschlagen oder verfehlt \u2013 dafuer "
                               "braucht es die damaligen Sch\u00e4tzungen, und die "
                               "hat der Anbieter nicht.")

                st.caption("**Nur bis zu 8 Quartale verf\u00fcgbar** \u2013 das ist ein "
                           "Stimmungsbild, keine Statistik. Bei acht Terminen "
                           "kann eine \u201eQuote von 75 %\u201c auch reiner Zufall sein. "
                           "Verwende es als Frage an dich selbst, nicht als "
                           "Antwort. Kein Anlagerat.")

    # ------------------------------------------------- Anstehende Quartalszahlen
    if _uv.endswith("Anstehende Zahlen"):
        st.caption("Welche S&P-500-Titel melden demn\u00e4chst \u2013 und was sagt die "
                   "Historie \u00fcber ihre Reaktion auf gute und schlechte Zahlen?")
        _res = []
        try:
            _res = store.get_earnings() or []
        except Exception as _e:
            st.caption(f"(nicht ladbar: {_e})")
        if not _res:
            st.info("Noch keine Termine gespeichert. Der Scan l\u00e4uft im "
                    "n\u00e4chtlichen Job \u00fcber den **S&P 500** \u2013 rund 500 Abrufe "
                    "allein f\u00fcr die Termine, danach die tiefe Analyse nur f\u00fcr "
                    "die tats\u00e4chlich meldenden Titel. Im Browser w\u00e4re das "
                    "nicht zumutbar. Starte den Workflow in GitHub oder warte "
                    "den n\u00e4chsten Lauf ab.")
        else:
            _amp = {"gruen": "\U0001f7e2", "gelb": "\U0001f7e1",
                    "rot": "\U0001f534", "grau": "\u26aa"}
            _f1, _f2 = st.columns([1, 1])
            _nur = _f1.selectbox("Anzeigen",
                                 ["alle", "nur \U0001f7e2 gr\u00fcn",
                                  "nur \U0001f534 rot", "gr\u00fcn + rot"],
                                 key="uv_filter")
            _maxt = _f2.selectbox("bis in", [7, 14, 28, 56], index=2,
                                  format_func=lambda d: f"{d} Tagen",
                                  key="uv_maxt")
            _sicht = [r for r in _res if (r.get("tage") or 0) <= _maxt]
            if _nur.endswith("gr\u00fcn"):
                _sicht = [r for r in _sicht if r.get("ampel") == "gruen"]
            elif _nur.endswith("rot"):
                _sicht = [r for r in _sicht if r.get("ampel") == "rot"]
            elif "+" in _nur:
                _sicht = [r for r in _sicht if r.get("ampel") in ("gruen", "rot")]
            st.caption(f"{len(_sicht)} von {len(_res)} gespeicherten Terminen")
            if not _sicht:
                st.info("Keine Termine im gew\u00e4hlten Filter.")
            else:
                vr_table([{
                    "": _amp.get(r.get("ampel"), "\u26aa"),
                    "Ticker": r["ticker"],
                    "Name": (r.get("name") or "")[:20],
                    "in Tagen": r["tage"],
                    "Datum": r["datum"], "Beat-Quote %": r.get("beat_quote"),
                    "belohnt %": r.get("belohnt_pct"), "n": r.get("n_termine"),
                    "Umsatz +%": r.get("revenue_growth"),
                } for r in _sicht],
                    signed_cols=("Umsatz +%",),
                    height=min(len(_sicht) * 40 + 46, 460))
                st.markdown('<div class="sec-title" style="margin-top:14px">'
                            'EINORDNUNG JE TITEL</div>', unsafe_allow_html=True)
                for r in _sicht[:25]:
                    with st.expander(
                            f"{_amp.get(r.get('ampel'), '')} **{r['ticker']}** "
                            f"\u00b7 in {r['tage']} Tagen \u00b7 {r.get('name', '')}"):
                        st.write(f"**Einordnung:** {r.get('urteil', '')}")
                        _e1, _e2 = st.columns(2)
                        with _e1:
                            st.caption("**Historie**")
                            st.write(f"\u2022 Termine erfasst: {r.get('n_termine') or 0}")
                            if r.get("beat_quote") is not None:
                                st.write(f"\u2022 Sch\u00e4tzung \u00fcbertroffen: {r['beat_quote']} %")
                            if r.get("belohnt_pct") is not None:
                                st.write(f"\u2022 davon belohnt: {r['belohnt_pct']} %")
                            if r.get("avg_reaktion_beat") is not None:
                                st.write(f"\u2022 \u00d8 Reaktion auf Beat: "
                                         f"{r['avg_reaktion_beat']:+.1f} %")
                        with _e2:
                            st.caption("**Erwartung**")
                            if r.get("eps_estimate") is not None:
                                st.write(f"\u2022 erwarteter Gewinn/Aktie: {r['eps_estimate']}")
                            if r.get("revenue_growth") is not None:
                                st.write(f"\u2022 Umsatzwachstum: {r['revenue_growth']:+.1f} %")
                        # Erwartungsluecke: laeuft das Geschaeft der
                        # Schaetzung davon? Nutzt die Quartalshistorie aus
                        # roic - deutlich mehr Quartale als yfinance.
                        try:
                            import regime as _rgl
                            _el = _rgl.erwartungsluecke(r["ticker"])
                        except Exception:
                            _el = None
                        if _el and (_el.get("spannungen") or _el.get("gegen")):
                            _sy = {"gruen": "\U0001f7e2", "gelb": "\U0001f7e1",
                                   "rot": "\U0001f534"}.get(_el["ampel"], "\u26aa")
                            st.markdown(f"**{_sy} Erwartungsl\u00fccke "
                                        f"({_el['punkte']:+d} Punkte):** "
                                        f"{_el['urteil']}")
                            if _el.get("beschleunigung_pp") is not None:
                                st.caption("Umsatzdynamik gegen\u00fcber den drei "
                                           "Quartalen davor: "
                                           f"**{_el['beschleunigung_pp']:+.1f} "
                                           "Prozentpunkte** (aus "
                                           f"{_el['n_quartale']} Quartalen)")
                            for _x in (_el.get("spannungen") or [])[:4]:
                                st.write(f"\u2022 {_x}")
                            for _x in (_el.get("gegen") or [])[:3]:
                                st.write(f"\u2022 \u26a0\ufe0f {_x}")

                        if r.get("pro"):
                            st.success("**Spricht gegen die Erwartung:**\n"
                                       + "\n".join(f"\u2022 {x}" for x in r["pro"]))
                        if r.get("contra"):
                            st.warning("**St\u00fctzt die Erwartung:**\n"
                                       + "\n".join(f"\u2022 {x}" for x in r["contra"]))
            st.caption("**Wichtig:** Der Scanner sagt NICHT, ob eine Sch\u00e4tzung "
                       "falsch ist \u2013 das kann vorab niemand wissen. Er sammelt "
                       "Spannungen zwischen Erwartung und beobachtbaren Trends. "
                       "Gr\u00fcne und rote F\u00e4lle werden in der **Trefferbilanz** "
                       "mitprotokolliert \u2013 dort siehst du in einigen Wochen, ob "
                       "die Logik trug. Vor Quartalszahlen einzusteigen bleibt "
                       "eine Wette auf eine einzelne Nachricht. Kein Anlagerat.")

    # -----------------------------------------------------------------
    # BRANCHEN-ZUORDNUNG: welche Aktie steckt in welchem Sektor?
    # -----------------------------------------------------------------
    st.markdown("---")
    st.markdown('<div class="sec-title">\U0001f5c2\ufe0f BRANCHEN-ZUORDNUNG</div>',
                unsafe_allow_html=True)
    st.caption("Zeigt, welchem Sektor das Tool jede Aktie zuordnet \u2013 dieselbe "
               "Einteilung, die Screener, Radar und der Branchenvergleich im "
               "Momentum nutzen. Die Sektor-Angabe stammt aus den Fundamental"
               "daten (roic/yfinance), nicht aus einer eigenen Liste.")

    _bz1, _bz2 = st.columns(2)
    _bz_uni = _bz1.selectbox("Universumsgr\u00f6\u00dfe",
                             [90, 200, 400], index=1,
                             format_func=lambda n: f"{n} Titel", key="bz_uni")
    _bz_go = _bz2.button("\U0001f5c2\ufe0f Branchen laden", key="bz_go",
                         use_container_width=True)

    if _bz_go:
        import precompute as _pcb
        _bzbar = st.progress(0.0, text="Lade Universum \u2026")

        def _bzf(fertig, gesamt, phase):
            _bzbar.progress(min(fertig / max(gesamt, 1), 1.0),
                            text=f"Lade \u2026 {fertig}/{gesamt}")
        try:
            _rows = _pcb.branchen_uebersicht(universum=_bz_uni, fortschritt=_bzf)
            st.session_state["bz_rows"] = _rows
            st.session_state["bz_zeit"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        except Exception as _ebz:
            st.error(f"Laden fehlgeschlagen: {_ebz}")
        _bzbar.empty()

    _bz_rows = st.session_state.get("bz_rows")
    if _bz_rows:
        from collections import defaultdict
        _nach_sektor = defaultdict(list)
        for r in _bz_rows:
            _nach_sektor[r.get("sector") or "Unbekannt"].append(r)
        st.caption(f"Stand: {st.session_state.get('bz_zeit', '')} \u00b7 "
                   f"{len(_bz_rows)} Titel in {len(_nach_sektor)} Sektoren")
        # Sektoren nach Anzahl absteigend
        for _sek in sorted(_nach_sektor, key=lambda s: -len(_nach_sektor[s])):
            _titel = sorted(_nach_sektor[_sek],
                            key=lambda r: (r.get("name") or r.get("ticker") or ""))
            with st.expander(f"{_sek}  ({len(_titel)})"):
                _bzdata = [{"Ticker": r.get("ticker"),
                            "Name": (r.get("name") or "")[:32],
                            "Industrie": (r.get("industry") or "\u2014")[:28]}
                           for r in _titel]
                vr_table(_bzdata, height=min(len(_bzdata) * 38 + 44, 460))
    else:
        st.info("Noch nicht geladen. Oben Gr\u00f6\u00dfe w\u00e4hlen und "
                "\u201eBranchen laden\u201c klicken.")



# ===========================================================================
# TAB — EARNINGS CALLS (S&P 500 · NASDAQ-100 · DAX)
# ===========================================================================
if nav == "Earnings Calls":
    st.markdown('<div class="sec-title">\U0001f399\ufe0f EARNINGS CALLS \u00b7 '
                'NEU ERSCHIENEN</div>', unsafe_allow_html=True)
    st.caption("Wortprotokolle der Telefonkonferenzen aus S&P 500, NASDAQ-100 "
               "und DAX. Der n\u00e4chtliche Job sucht, wer neu ver\u00f6ffentlicht "
               "hat; der Volltext wird erst beim \u00d6ffnen geladen.")

    try:
        import roic as _rt
        import kennzahlen as _kt
        _rt_ok = _rt.enabled()
    except Exception:
        _rt = _kt = None
        _rt_ok = False

    if not _rt_ok:
        st.info("Ben\u00f6tigt die roic.ai-Anbindung \u2013 ROIC_API_KEY ist nicht "
                "gesetzt.")
    else:
        # Robust gegen einen veralteten Upload: Fehlt die Funktion, liegt
        # eine alte store.py auf dem Server - dann sagen wir genau das,
        # statt eine kryptische Meldung zu zeigen.
        _liste = []
        if not hasattr(store, "get_transkripte"):
            st.error(
                "\u26a0\ufe0f **Die hochgeladene `store.py` ist veraltet.** "
                "Ihr fehlen die Funktionen `get_transkripte` / "
                "`set_transkripte`, die dieser Tab braucht. Bitte "
                "**`store.py`** neu hochladen (am besten das komplette ZIP, "
                "damit die Dateien zueinander passen) und die App neu "
                "starten.")
        else:
            try:
                _liste = store.get_transkripte() or []
            except Exception as _e:
                st.caption(f"(nicht ladbar: {_e})")

        if not _liste:
            st.info("Noch keine Calls erfasst. Der Nachtlauf pr\u00fcft rund 560 "
                    "Titel (etwa 2 Minuten) und h\u00e4lt fest, wer in den letzten "
                    "drei Wochen ver\u00f6ffentlicht hat. Starte den Workflow in "
                    "GitHub oder warte den n\u00e4chsten Lauf ab.")

            # Diagnose: was hat der letzte Nachtlauf beim Transkript-Scan getan?
            try:
                _st = store.get_transkript_status() if hasattr(
                    store, "get_transkript_status") else {}
            except Exception:
                _st = {}
            if _st.get("stand"):
                if not _st.get("roic_aktiv"):
                    st.error("\u26a0\ufe0f Letzter Nachtlauf: " + _st["stand"])
                else:
                    st.warning("Letzter Nachtlauf-Status: " + _st["stand"])

            # --- Live-Selbsttest: prueft die Earnings-Call-Kette sofort,
            #     ohne auf den Nachtlauf zu warten. Zeigt genau, wo es hakt.
            with st.expander("\U0001f527 Verbindung jetzt testen "
                             "(ohne Nachtlauf)", expanded=False):
                st.caption("Pr\u00fcft direkt bei roic.ai, ob Earnings Calls "
                           "abrufbar sind \u2013 mit Apple als Beispiel.")
                if st.button("\U0001f50d Test starten", key="ec_selftest"):
                    with st.spinner("Frage roic.ai ab \u2026"):
                        try:
                            _tl = _rt.transcript_liste("AAPL", limit=5)
                        except Exception as _e:
                            _tl = None
                            st.error(f"transcript_liste warf einen Fehler: {_e}")
                        if _tl:
                            st.success(f"\u2705 Verbindung ok \u2013 "
                                       f"{len(_tl)} Calls f\u00fcr AAPL gefunden.")
                            st.write("Neueste Eintr\u00e4ge:")
                            for _z in _tl[:3]:
                                st.write(f"\u2022 {_z.get('jahr')} Q{_z.get('quartal')} "
                                         f"\u00b7 {_z.get('datum')}")
                            # Zusatz: erkennt neue_transkripte aktuelle Calls?
                            st.write("---")
                            st.write("**Test: werden aktuelle Calls erkannt?**")
                            try:
                                _testtitel = ["META", "GOOGL", "MSFT", "V", "MA",
                                              "AMZN", "AAPL"]
                                _nt = _rt.neue_transkripte(_testtitel, tage=21,
                                                           deckel=10)
                                _akt = [x for x in _nt if x.get("ist_neu")]
                                if _akt:
                                    st.success(f"\u2705 {len(_akt)} aktuelle Calls "
                                               f"(\u2264 21 Tage) erkannt:")
                                    for _x in _akt[:6]:
                                        st.write(f"\u2022 {_x['ticker']} \u00b7 "
                                                 f"{_x['datum']} "
                                                 f"({_x['tage_her']} Tage her)")
                                    st.caption("Die Erkennung funktioniert. Wenn "
                                               "der Tab leer bleibt, l\u00e4uft der "
                                               "Nachtlauf mit ALTER Version \u2013 "
                                               "neuen Code ins Repo + Workflow "
                                               "starten.")
                                else:
                                    st.warning(f"\u26a0\ufe0f {len(_nt)} Calls gefunden, "
                                               "aber KEINER als aktuell markiert. "
                                               "Zeigt die Datums-Logik. Neueste "
                                               "gefundene:")
                                    for _x in _nt[:5]:
                                        st.write(f"\u2022 {_x['ticker']} \u00b7 "
                                                 f"{_x.get('datum')} "
                                                 f"({_x.get('tage_her')} Tage)")
                            except Exception as _e2:
                                st.error(f"neue_transkripte-Fehler: {_e2}")
                        elif _tl is not None:
                            st.warning("\u26a0\ufe0f Verbindung steht, aber roic "
                                       "liefert keine Calls f\u00fcr AAPL zur\u00fcck. "
                                       "M\u00f6glich: Der API-Key hat kein "
                                       "Earnings-Call-Paket, oder der Endpunkt "
                                       "hat sich erneut ge\u00e4ndert. Bitte das "
                                       "Diagnose-Skript roic_ec_diagnose.py "
                                       "ausf\u00fchren und die Ausgabe schicken.")
        else:
            _f1, _f2 = st.columns(2)
            _zeit = _f1.selectbox("Zeitraum", [7, 14, 21],
                                  format_func=lambda d: f"letzte {d} Tage",
                                  key="ec_zeit")
            _nur_pf = _f2.checkbox("Nur meine Titel (Portfolio + Watchlist)",
                                   key="ec_nur_pf")

            _meine = set()
            if _nur_pf:
                try:
                    for _n, _rs in (store.load_all() or {}).items():
                        for _r in _rs or []:
                            _x = str(_r.get("ticker") or "").strip().upper()
                            if _x:
                                _meine.add(_x)
                    for _r in (store.get_watchlist() or []):
                        _x = str(_r.get("ticker") if isinstance(_r, dict)
                                 else _r or "").strip().upper()
                        if _x:
                            _meine.add(_x)
                except Exception:
                    pass

            # Zwei Gruppen: aktuelle Saison (im Zeitfenster) zuerst, aeltere
            # darunter. So bleibt der Tab auch zwischen den Earnings-Saisons
            # nuetzlich, statt leer zu sein.
            _basis = _liste
            if _nur_pf:
                _basis = [r for r in _basis if r["ticker"] in _meine]

            # AUDIT-BEFUND E1: 'tage_her' wurde beim SCHREIBEN berechnet und
            # mitgespeichert. Ein Eintrag vom 7. August stand damit fuer immer
            # als "vor 2 Tagen" in der Liste - und galt als aktueller Call,
            # obwohl er einen Monat alt war. Die Zahl altert nicht mit.
            #
            # Deshalb hier aus dem DATUM rechnen. Das gespeicherte Feld bleibt
            # nur noch Rueckfall, falls kein Datum vorliegt.
            from datetime import datetime as _dtm

            def _alter_tage(r):
                d = str(r.get("datum") or r.get("date") or "")[:10]
                for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                    try:
                        return (_dtm.now() - _dtm.strptime(d, fmt)).days
                    except ValueError:
                        continue
                return r.get("tage_her")

            for _r in _basis:
                _r["tage_her"] = _alter_tage(_r)

            _aktuell = [r for r in _basis if (r.get("tage_her") or 99) <= _zeit]
            _aktuell.sort(key=lambda r: r.get("tage_her") or 999)
            _aelter = [r for r in _basis if (r.get("tage_her") or 99) > _zeit]
            _aelter.sort(key=lambda r: r.get("tage_her") or 999)
            _sicht = _aktuell + _aelter          # fuer Dropdown/Protokoll

            if _aktuell:
                st.caption(f"{len(_aktuell)} aktuelle Calls (\u2264 {_zeit} Tage)"
                           + (f" \u00b7 {len(_aelter)} \u00e4ltere darunter"
                              if _aelter else ""))
            else:
                st.info(f"Aktuell keine Calls in den letzten {_zeit} Tagen \u2013 "
                        "zwischen den Earnings-Saisons ist das normal. Unten "
                        "siehst du die zuletzt erschienenen Calls."
                        + (" (Nur deine Titel.)" if _nur_pf else ""))

            if not _sicht:
                st.info("Keine Calls im gew\u00e4hlten Filter."
                        + (" Deine Titel wurden noch nicht erfasst."
                           if _nur_pf else ""))
            else:
                # AUDIT-BEFUND D1: Das Budget lag bei 40. Beim ersten Aufruf
                # nach einem Neustart sind das 40 Netzabrufe nacheinander,
                # waehrend die Seite steht. Jetzt: 12 je Durchlauf, und die
                # aufgeloesten Namen landen dauerhaft im Speicher - nach ein
                # paar Aufrufen sind alle da und es faellt gar kein Abruf mehr
                # an. Lieber ein paar Ticker mehr in der ersten Ansicht als
                # eine Seite, die zu haengen scheint.
                _name_budget = [12]

                def _tabellenzeile(r, gruppe):
                    _nm = r.get("name")
                    if (not _nm or _nm == r["ticker"]) and _name_budget[0] > 0:
                        _name_budget[0] -= 1
                        _nm = load_firmenname(r["ticker"])
                    return {
                        "": gruppe,
                        "Firma": _nm or r["ticker"],
                        "Datum": r["datum"],
                        "vor Tagen": r.get("tage_her"),
                        "Quartal": (f"{r.get('quartal') or ''} "
                                    f"{r.get('jahr') or ''}").strip() or "\u2014",
                    }
                with st.spinner("Firmennamen werden aufgel\u00f6st \u2026"):
                    _tabelle = ([_tabellenzeile(r, "\U0001f195") for r in _aktuell]
                                + [_tabellenzeile(r, "") for r in _aelter[:30]])
                # Noch nicht aufgeloest heisst: In der Spalte steht der Ticker.
                _ticker_im_satz = {r["ticker"] for r in _aktuell} | \
                                  {r["ticker"] for r in _aelter[:30]}
                _offen = sum(1 for z in _tabelle if z["Firma"] in _ticker_im_satz)
                if _offen:
                    st.caption(f"{_offen} Namen noch nicht aufgel\u00f6st \u2013 "
                               f"sie erscheinen beim n\u00e4chsten Aufruf. "
                               f"Aufgel\u00f6ste Namen bleiben dauerhaft gespeichert.")
                vr_table(_tabelle,
                         height=min(len(_tabelle) * 40 + 46, 420))

                st.markdown('<div class="sec-title" style="margin-top:16px">'
                            'PROTOKOLL \u00d6FFNEN</div>', unsafe_allow_html=True)
                _wahl = st.selectbox(
                    "Firma",
                    _sicht,
                    format_func=lambda r: (f"{r.get('name') or r['ticker']} \u00b7 "
                                           f"{r['datum']} \u00b7 "
                                           f"{r.get('quartal') or ''} "
                                           f"{r.get('jahr') or ''}").strip(),
                    key="ec_wahl")

                # Direkt zur Einzelanalyse springen (Ticker uebergeben)
                if st.button(f"\U0001f50e Analyse zu "
                             f"{_wahl.get('name') or _wahl['ticker']} \u00f6ffnen",
                             key="ec_analyse"):
                    st.session_state["pending_search"] = _wahl["ticker"]
                    st.session_state["pending_nav"] = "Einzelanalyse"
                    st.rerun()

                @st.cache_data(ttl=86400, show_spinner=False)
                def _ec_text(t, jahr, quartal):
                    return _rt.transcript(t, jahr, quartal)

                if st.button("\u25b6 Protokoll laden", key="ec_go",
                             use_container_width=True):
                    with st.spinner("Wortprotokoll wird geladen \u2026"):
                        st.session_state["ec_geladen"] = _ec_text(
                            _wahl["ticker"], _wahl.get("jahr"),
                            _wahl.get("quartal"))
                        st.session_state["ec_ticker"] = _wahl["ticker"]

                _tr = st.session_state.get("ec_geladen") or {}
                if _tr.get("text"):
                    _tk = st.session_state.get("ec_ticker", "")
                    _txt = _tr["text"]
                    # AUDIT-BEFUND K1: Hier wurde ungeprueft aufgerufen,
                    # waehrend zusammenfassung_call() weiter unten mit hasattr()
                    # abgesichert ist. Fehlte die Funktion, brach die ganze
                    # Ansicht mit AttributeError ab statt nur ein Teil davon.
                    if hasattr(_kt, "transkript_kennzahlen"):
                        _mz = _kt.transkript_kennzahlen(_txt)
                    else:
                        st.warning("Die hochgeladene `kennzahlen.py` ist "
                                   "veraltet \u2013 ihr fehlt "
                                   "`transkript_kennzahlen`. Der Umfang wird "
                                   "ersatzweise direkt gez\u00e4hlt.")
                        _w = len(_txt.split())
                        _mz = {"zeichen": len(_txt), "woerter": _w,
                               "lesedauer_min": max(1, round(_w / 200.0)) if _w else 0,
                               "frageanteil_pct": None}

                    _mc = st.columns(3)
                    card(_mc[0], "Umfang", f"{_mz['lesedauer_min']} min",
                         f"{_mz['zeichen']:,}".replace(",", ".") + " Zeichen",
                         "var(--amber)")
                    card(_mc[1], "Frageteil",
                         (f"{_mz['frageanteil_pct']} %"
                          if _mz.get("frageanteil_pct") is not None else "\u2014"),
                         "Anteil am Protokoll", "var(--amber)")
                    card(_mc[2], "Quartal",
                         f"{_tr.get('quartal') or ''} {_tr.get('jahr') or ''}".strip()
                         or "\u2014", _tr.get("datum") or "", "var(--amber)")

                    _av = st.radio("Ansicht",
                                   ["\U0001f4dd Zusammenfassung",
                                    "\U0001f4cc Kernstellen", "\U0001f4c4 Volltext"],
                                   horizontal=True, label_visibility="collapsed",
                                   key="ec_ansicht")

                    if _av.endswith("Zusammenfassung"):
                        if not hasattr(_kt, "zusammenfassung_call"):
                            st.error(
                                "\u26a0\ufe0f **Die hochgeladene `kennzahlen.py` ist "
                                "veraltet.** Ihr fehlt die Funktion "
                                "`zusammenfassung_call`, die diese Ansicht "
                                "braucht. Bitte **`kennzahlen.py`** neu hochladen "
                                "(am besten das komplette ZIP, damit die Dateien "
                                "zueinander passen) und die App neu starten. "
                                "Solange kannst du die Kernstellen oder den "
                                "Volltext nutzen.")
                            _zf = None
                        else:
                            _zf = _kt.zusammenfassung_call(_txt)
                        if _zf is not None:
                            st.caption("**Faktenorientierte \u00dcbersicht \u2013 keine "
                                       "Stimmungsdeutung.** W\u00f6rtliche Fundstellen "
                                       "aus dem Protokoll, nach Art geordnet. "
                                       "Kein Anlagerat.")
                            if _zf.get("themen"):
                                _tt = " \u00b7 ".join(f"{t['thema']} ({t['nennungen']})"
                                                     for t in _zf["themen"][:5])
                                st.markdown(f"**Worum es ging:** {_tt}")
                            if _zf.get("fakten"):
                                st.markdown('<div class="sec-title" '
                                            'style="margin-top:12px">\U0001f4ca '
                                            'GENANNTE ZAHLEN</div>',
                                            unsafe_allow_html=True)
                                for _f in _zf["fakten"]:
                                    st.markdown(f"> {esc(_f)}")
                            if _zf.get("ausblick"):
                                st.markdown('<div class="sec-title" '
                                            'style="margin-top:12px">\U0001f52d '
                                            'AUSBLICK (Management)</div>',
                                            unsafe_allow_html=True)
                                st.caption("Was die Leitung f\u00fcr die Zukunft sagt "
                                           "\u2013 erfahrungsgem\u00e4\u00df optimistisch, mit "
                                           "Vorsicht zu lesen.")
                                for _a in _zf["ausblick"]:
                                    st.markdown(f"> {esc(_a)}")
                            if _zf.get("nachfragen"):
                                st.markdown('<div class="sec-title" '
                                            'style="margin-top:12px">\U0001f5e3\ufe0f '
                                            'WORAN ANALYSTEN NACHHAKTEN</div>',
                                            unsafe_allow_html=True)
                                st.caption("Das Aufschlussreichste am Call: Hier "
                                           "wird kritisch nachgefragt, oft zu "
                                           "wunden Punkten.")
                                for _n in _zf["nachfragen"]:
                                    st.markdown(f"> {esc(_n)}")
                            if not any([_zf.get("fakten"), _zf.get("ausblick"),
                                        _zf.get("nachfragen")]):
                                st.info("Keine strukturierten Fundstellen "
                                        "gefunden \u2013 sieh dir die Kernstellen "
                                        "oder den Volltext an.")
                    elif _av.endswith("Kernstellen"):
                        _bl = (_kt.kernstellen(_txt, max_je_thema=4)
                               if hasattr(_kt, "kernstellen") else [])
                        if not _bl:
                            st.info("Keine Kernstellen gefunden \u2013 das "
                                    "Protokoll ist eventuell sehr kurz.")
                        else:
                            st.caption("**W\u00f6rtliche Fundstellen, keine "
                                       "Zusammenfassung.** Sortiert nach Thema; "
                                       "Stellen aus dem **Frageteil** stehen "
                                       "oben, weil dort nachgehakt wird.")
                            for _b in _bl:
                                st.markdown(f'<div class="sec-title" '
                                            f'style="margin-top:12px">'
                                            f'{esc(_b["thema"].upper())}</div>',
                                            unsafe_allow_html=True)
                                for _s in _b["stellen"]:
                                    _tag = ("\U0001f5e3\ufe0f **Frageteil**"
                                            if _s["teil"] == "Frageteil"
                                            else "\U0001f4d6 Vortrag")
                                    st.markdown(f"{_tag}  \n> {esc(_s['satz'])}")
                            st.caption("Nennungen je Thema: "
                                       + " \u00b7 ".join(f"{k} {v}" for k, v
                                                          in _mz["nennungen"].items()))
                    else:
                        _such = st.text_input(
                            "Im Protokoll suchen",
                            placeholder="z. B. guidance, margin, demand",
                            key="ec_such").strip()
                        if _such:
                            _low, _pos, _tref = _txt.lower(), 0, []
                            _p = _low.find(_such.lower())
                            while _p >= 0 and len(_tref) < 15:
                                _tref.append(_txt[max(0, _p - 220):_p + 320])
                                _p = _low.find(_such.lower(), _p + 1)
                            st.caption(f"{len(_tref)} Fundstelle(n)")
                            for _s in _tref:
                                st.markdown(f"> \u2026{esc(_s)}\u2026")
                                st.divider()
                        else:
                            st.text_area("Wortprotokoll", _txt, height=460,
                                         key="ec_volltext")

                    st.warning(
                        "**Warum hier keine automatische Einsch\u00e4tzung steht:** "
                        "In diesen Konferenzen spricht die Unternehmensleitung "
                        "\u00fcber das eigene Unternehmen \u2013 sie klingt fast immer "
                        "zuversichtlich, auch unmittelbar vor schlechten "
                        "Quartalen. Eine automatische Stimmungsauswertung w\u00fcrde "
                        "vor allem messen, wie gut die Kommunikationsabteilung "
                        "arbeitet, und das mit dem Anschein von Objektivit\u00e4t. "
                        "Aufschlussreich ist der **Frageteil**: Woran haken "
                        "Analysten mehrfach nach, und wo weicht die Antwort aus? "
                        "Kein Anlagerat.")
