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
section[data-testid="stSidebar"] .stButton>button{
  text-align:left; justify-content:flex-start; border-radius:8px;
  border:1px solid var(--line); padding:10px 12px; margin:2px 0;
  font-weight:600; letter-spacing:.3px;}
section[data-testid="stSidebar"] .stButton>button:hover{
  border-color:var(--amber); color:var(--amber);}
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
@st.cache_data(ttl=3600, show_spinner=False)
def load_fundamentals_deep(t): return providers.get_fundamentals(t, deep=True)
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
@st.cache_data(ttl=1800, show_spinner=False)
def load_perf(t): return providers.get_performance(t)
@st.cache_data(ttl=3600, show_spinner=False)
def load_screen_extras(t): return providers.get_screen_extras(t)
@st.cache_data(ttl=86400, show_spinner=False)
def load_div_years(t): return providers.get_dividend_years(t)
@st.cache_data(ttl=86400, show_spinner=False)
def load_price_on(t, date): return providers.get_price_on(t, date)
@st.cache_data(ttl=60, show_spinner=False)
def load_intraday_price(t): return providers.get_intraday_price(t)
@st.cache_data(ttl=60, show_spinner=False)
def load_intraday_quote(t, cur): return providers.get_intraday_quote(t, cur)
@st.cache_data(ttl=1800, show_spinner=False)
def load_analyst(t): return providers.get_analyst_ratings(t)
@st.cache_data(ttl=600, show_spinner=False)
def search_symbols(q): return providers.search_symbol(q)
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


def render_trackrecord():
    """Trefferbilanz: was ist aus unseren Signalen geworden - gegen den Index."""
    st.markdown('<div class="sec-title">\U0001f4c8 TREFFERBILANZ \u00b7 Signal-Tagebuch'
                '</div>', unsafe_allow_html=True)
    st.caption("Kein Backtest, sondern ein **Vorw\u00e4rts-Test**: Jedes Screener-/"
               "Radar-Signal wird beim Auftauchen festgehalten \u2013 auch die sp\u00e4teren "
               "Fehlschl\u00e4ge \u2013 und danach gegen den S&P 500 gemessen. Erst so l\u00e4sst "
               "sich sagen, ob das Modell etwas kann oder nur der Markt lief.")
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
            f"({_n_reif} bereits reif). Details unten in der Diagnose.")
    elif not rows:
        st.info("Noch keine Signale erfasst. Der automatische Lauf (2\u00d7 t\u00e4glich) "
                "h\u00e4lt jedes Screener-/Radar-Signal fest. Aussagekr\u00e4ftig wird das "
                "erst nach einigen Wochen und vielen F\u00e4llen.")

    # --- Sofort erfassen (ohne auf den Cron-Job zu warten) ---
    _rr = st.session_state.get("radar_results") or []
    _cap = st.columns([2, 1])
    if _cap[0].button(f"\U0001f4cc Aktuelle Radar-Treffer erfassen ({len(_rr)})",
                      use_container_width=True, disabled=not _rr):
        try:
            new = tr.record([{"ticker": r["ticker"], "quelle": "Radar",
                              "score": r.get("score"),
                              "price": (r.get("_price") or 0) * (r.get("_fx") or 1.0)}
                             for r in _rr[:15]])
            st.success(f"{new} neue Signale erfasst.")
            st.rerun()
        except Exception as e:
            st.error(f"Erfassen fehlgeschlagen: {e}")
    if not _rr:
        _cap[0].caption("Erst im Radar scannen \u2013 dann lassen sich die Treffer "
                        "hier mit einem Klick ins Tagebuch \u00fcbernehmen.")

    # --- Selbsttest: erfasst JETZT ein Signal und zeigt jeden Schritt ---
    with st.expander("\U0001f527 Selbsttest \u2013 warum erscheinen keine Signale?"):
        st.caption("Pr\u00fcft die ganze Kette an einem Testticker (AAPL): Kurs abrufbar? "
                   "Benchmark? Speicher schreibbar? So l\u00e4sst sich eingrenzen, ob das "
                   "Problem beim Cron-Job, den Kursen oder dem Speicher liegt.")
        if st.button("Selbsttest starten", key="tr_selftest"):
            steps = []
            try:
                _p = tr._price("AAPL")
                steps.append(("Kurs AAPL abrufbar", bool(_p), str(_p)))
            except Exception as e:
                steps.append(("Kurs AAPL abrufbar", False, str(e)))
            try:
                _b = tr._bench_price()
                steps.append(("Benchmark (S&P) abrufbar", bool(_b), str(_b)))
            except Exception as e:
                steps.append(("Benchmark abrufbar", False, str(e)))
            _before = len(store.get_signals() or [])
            try:
                _n = tr.record([{"ticker": "AAPL", "quelle": "Selbsttest",
                                 "score": 60, "verdict": "Test"}])
                _after = len(store.get_signals() or [])
                steps.append(("Testsignal geschrieben",
                              _after > _before or _n == 0,
                              f"vorher {_before}, nachher {_after}, neu {_n}"))
            except Exception as e:
                steps.append(("Testsignal geschrieben", False, str(e)))
            for label, ok, detail in steps:
                st.write(("\u2705" if ok else "\u274c") + f" {label} \u2013 {detail}")

    # --- Diagnose: schreibt der Speicher ueberhaupt? ---
    with _cap[1].popover("\u2699\ufe0f Diagnose"):
        try:
            _sig = store.get_signals() or []
            st.write(f"Speicher: **{store.backend()}**")
            st.write(f"Signale gespeichert: **{len(_sig)}**")
            if store.backend() != "sheet":
                st.warning("Ohne Google-Sheet-Speicher gehen die Signale beim "
                           "Neustart verloren \u2013 und der Cron-Job schreibt in einen "
                           "anderen Speicher als die App.")
            if _sig:
                import time as _t
                _n_bench = sum(1 for e in _sig if e.get("bench_entry"))
                _n_verd = sum(1 for e in _sig if e.get("verdict"))
                _reif = sum(1 for e in _sig
                            if (_t.time() - (e.get("ts") or _t.time())) / 86400 >= 14)
                _auswert = len(rows)
                st.markdown(
                    f"- mit Einstiegskurs: **{sum(1 for e in _sig if e.get('entry_px'))}**\n"
                    f"- mit Benchmark-Kurs: **{_n_bench}**\n"
                    f"- mit Scorecard-Urteil: **{_n_verd}**\n"
                    f"- aktuell auswertbar (Kurs abrufbar): **{_auswert}**\n"
                    f"- davon reif (\u2265 14 Tage): **{_reif}**")
                if _auswert < len(_sig):
                    st.caption("Nicht auswertbare Signale = aktueller Kurs gerade nicht "
                               "abrufbar (API-Limit oder Ticker). Das ist meist "
                               "vor\u00fcbergehend \u2013 beim n\u00e4chsten Laden erneut pr\u00fcfen.")
                if _n_verd == 0:
                    st.caption("Kein Signal hat ein Scorecard-Urteil: L\u00e4uft der "
                               "Cron-Job schon mit der NEUEN precompute.py (die das "
                               "Urteil mitschreibt)? \u00c4ltere Signale bleiben ohne Urteil.")
                # Aelteste/juengste Signale zeigen
                _ts = [e.get("ts") for e in _sig if e.get("ts")]
                if _ts:
                    import datetime as _dt
                    _old = _dt.datetime.fromtimestamp(min(_ts)).strftime("%d.%m.%Y")
                    _new = _dt.datetime.fromtimestamp(max(_ts)).strftime("%d.%m.%Y")
                    st.caption(f"Signale von {_old} bis {_new}.")
        except Exception as e:
            st.error(f"Speicher nicht lesbar: {e}")

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
            row = {"Ticker": r["ticker"], "Tage": r["days"],
                   "Einstieg": round(r["entry_px"], 2)}
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
    _tab("\U0001f9ea GEGEN DEN STROM (experimentell)", "Contrarian",
         "Noch keine Kandidaten erfasst. Gesucht werden Titel mit niedrigen "
         "Erwartungen, bei denen harte Zahlen dagegen sprechen.",
         extra=[("Niedrige Erwartung", "merkmal", lambda v: str(v)),
                ("Spricht dagegen", "strategie", lambda v: str(v))])
    st.caption("**Experiment, kein Kaufsignal.** Gesucht sind Titel, bei denen "
               "Analysten negativ sind ODER Verluste erwartet werden \u2013 und wo "
               "gleichzeitig harte Zahlen widersprechen, etwa positiver Cashflow "
               "trotz Verlust oder steigende Umsätze. Die Idee: Wo alle skeptisch "
               "sind, wirkt eine positive \u00dcberraschung besonders stark. Ob das "
               "trägt, entscheidet diese Tabelle nach Monaten \u2013 nicht die Logik "
               "dahinter. Solche Firmen sind meist aus gutem Grund unbeliebt. "
               "Kein Anlagerat.")

    _tab("\u26a0\ufe0f KONTROLLGRUPPE (schwache Setups \u00b7 als Short gerechnet)", "Negativ",
         "Noch keine schwachen Setups erfasst \u2013 der n\u00e4chtliche Lauf "
         "sammelt sie ab jetzt automatisch.",
         extra=[("Score", "score", lambda v: round(v)),
                ("Upside %", "upside", lambda v: round(v, 1)),
                ("Merkmal", "merkmal", lambda v: str(v))],
         short=True)
    st.caption("Bei der Kontrollgruppe erwartet das Modell **fallende** Kurse. "
               "Deshalb steht neben der Kursentwicklung die **Short-Rendite** "
               "(umgekehrtes Vorzeichen): F\u00e4llt der Kurs, w\u00e4re die Position "
               "im Plus. Reine Modellrechnung \u2013 echte Leerverk\u00e4ufe kosten "
               "Leihgeb\u00fchr und Spread, erfordern Dividendenausgleich und haben "
               "theoretisch unbegrenztes Verlustrisiko. Kein Anlagerat.")

    st.caption("\u201evs. Index\u201c = Rendite minus S&P 500 im selben Zeitraum. Nur das "
               "z\u00e4hlt. Kein Anlagerat.")

    _rep = [r for r in _ok if r.get("repariert")]
    if _rep:
        st.caption(f"\u2139\ufe0f Bei {len(_rep)} Signalen wurde der Einstiegskurs von "
                   "Pence auf Pfund umgerechnet \u2013 sie stammen aus der Zeit vor "
                   "der Einheiten-Korrektur. Betroffen sind Londoner Titel "
                   "(.L / .XC). Die Rendite stimmt jetzt.")

    # Code-Version der Erfassung - haeufigste Fehlerquelle ist eine veraltete
    # precompute.py auf GitHub. Fehlt die Angabe, stammt das Signal aus einem
    # Lauf VOR der Versionskennung.
    _vers = sorted({(r.get("codever") or "unbekannt") for r in rows})
    if _vers:
        st.caption("Erfasst mit Code-Version: " + ", ".join(_vers)
                   + ("  \u2013 \u201eunbekannt\u201c bedeutet: der Lauf nutzte eine "
                      "\u00e4ltere precompute.py. Neue Spalten bleiben dann leer."
                      if "unbekannt" in _vers else ""))

    if _bad:
        with st.expander(f"\u26a0\ufe0f {len(_bad)} Signale mit fehlerhaften Kursdaten "
                         "(aus der Auswertung ausgeschlossen)"):
            st.caption("Diese Zeilen zeigen unrealistische Renditen \u2013 fast immer "
                       "ein Einheitenproblem (z. B. Pence gegen Pfund, Faktor 100). "
                       "Sie flie\u00dfen in KEINE Statistik ein. Nach dem n\u00e4chsten "
                       "n\u00e4chtlichen Lauf sollten sie verschwinden; bleiben sie, "
                       "l\u00f6sche die betroffenen Signale im Speicher.")
            vr_table([{"Ticker": r["ticker"], "Quelle": r.get("quelle", ""),
                       "Tage": r["days"], "Einstieg": round(r["entry_px"], 2),
                       "Rendite %": r["ret_pct"]} for r in _bad],
                     signed_cols=("Rendite %",),
                     height=min(len(_bad) * 40 + 46, 300))

    # === Signale verwalten (loeschen + neu aufbauen) ===
    with st.expander("\U0001f5d1\ufe0f Signale zur\u00fccksetzen"):
        st.caption("Bereits erfasste Signale werden vom n\u00e4chtlichen Lauf "
                   "**\u00fcbersprungen** \u2013 er f\u00fcgt nur neue Ticker hinzu. Nach "
                   "\u00c4nderungen an der Bewertung bleiben Alt-Eintr\u00e4ge daher mit "
                   "ihren veralteten Zahlen stehen. Hier kannst du eine Gruppe "
                   "l\u00f6schen, damit sie beim n\u00e4chsten Lauf frisch erfasst wird.")
        _zc1, _zc2 = st.columns([1, 1])
        _welche = _zc1.selectbox("Welche Gruppe?",
                                 ["Screener", "Radar", "Negativ", "ALLE"],
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
                    st.error("Nichts gel\u00f6scht. M\u00f6glich, wenn der Speicher gerade "
                             "nicht schreibbar ist \u2013 siehe Speicher-Diagnose "
                             "in der Watchlist.")
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
             "quality_long": "Qualit\u00e4ts-Long", "core_ko": "Aktien + KO 3x"}
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

    data = [{"Datum": e.get("datum", ""), "Typ": e.get("typ", ""),
             "Ticker": e.get("ticker", ""), "Anzahl": e.get("anzahl"),
             "Kurs \u20ac": e.get("kurs_eur"), "Betrag \u20ac": e.get("betrag_eur"),
             "G/V \u20ac": e.get("gv_eur"), "Portfolio": e.get("portfolio", ""),
             "Quelle": e.get("quelle", ""), "Notiz": (e.get("notiz") or "")[:30]}
            for e in log]
    vr_table(data, signed_cols=("G/V \u20ac",), height=min(len(data) * 40 + 46, 620))

    realized = sum(e.get("gv_eur") or 0 for e in log if e.get("typ") == "Verkauf")
    st.caption(f"Realisiertes Ergebnis aus protokollierten Verk\u00e4ufen: "
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


def read_url(url, access=""):
    """Leitet Artikel hinter einer Paywall ueber removepaywalls.com um.
    Format: https://removepaywalls.com/<vollstaendige Original-URL>.
    Frei lesbare Artikel bleiben unveraendert (kein Umweg noetig)."""
    u = (url or "").strip()
    if not u or not u.startswith("http"):
        return u or "#"
    if str(access).lower() in ("paywall", "metered"):
        return "https://removepaywalls.com/" + u
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
    try:
        import hedgefund as _hf
        _gate = _hf._quality_gate
    except Exception:
        _gate = None
    longs, shorts = [], []
    for t in tickers:
        f = load_fundamentals(t)
        price = f.get("price")
        if not price:
            continue
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
        base = {"Ticker": t, "Name": (f.get("name") or "")[:18],
                "Kurs \u20ac": round(price * fx, 2), "Comp.": round(comp),
                "Upside %": round(up, 1),
                "Vola %": round(vol) if vol else None, "Trend": trend}

        # LONG: Qualitaet + Bewertungsabstand, nicht im freien Fall
        if comp >= 58 and up >= 10 and (mom60 is None or mom60 > -0.20):
            lscore = comp * 0.6 + min(up, 60) * 0.5 + (6 if above else 0)
            longs.append({**base, "Chance": round(lscore)})

        # SHORT: ueberbewertet + schwaecher + kein starker Aufwaertstrend
        if up <= -20 and comp <= 52:
            strong_uptrend = bool(above and (mom60 or 0) > 0.15)
            rolling_over = (mom20 or 0) < 0
            if not strong_uptrend and (not above or rolling_over):
                sscore = (-up) * 0.5 + (60 - comp) * 0.4 \
                    + (10 if rolling_over else 0) - (15 if above else 0)
                shorts.append({**base, "Risiko-Fit": round(sscore)})

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
        up = v.get("upside_pct") if not capped else None    # nur gekappte Extremwerte raus
        reliable = v.get("reliable", False)
        rows.append({"ticker": f["ticker"], "name": f.get("name"), "sector": f.get("sector"),
                     "country": f.get("country"),
                     "price_eur": round((f.get("price") or 0) * f["_fx"], 2),
                     "score": comp, "upside": up, "reliable": reliable, "capped": bool(capped),
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
                p_now = p_live
                # Deutscher Vormittagskurs kommt in EUR -> mit EUR-FX (=1) rechnen,
                # US-Kurs in native Waehrung -> mit deren FX. Waehrung wandert mit.
                fx = fx_to_eur(cur_live) or 1.0
                live_used = True
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
        is_single_stock = not (is_fund or is_commodity)
        rows.append({
            "ticker": tk, "name": f.get("name"), "value_eur": float(value_eur),
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


PAGES = ["Start", "News", "Einzelanalyse", "Radar", "Screener", "Watchlist",
         "Long/Short", "Portfoliocheck", "Umfeld"]
ICONS = {"Start": "\U0001f3e0", "Einzelanalyse": "\U0001f4c8", "Radar": "\U0001f3af",
         "Screener": "\U0001f50d", "Watchlist": "\u2b50", "Long/Short": "\u2696\ufe0f",
         "Portfoliocheck": "\U0001f4bc", "News": "\U0001f4f0",
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
              "Einzelanalyse": "\U0001f4c8", "Radar": "\U0001f3af",
              "Screener": "\U0001f50d", "Watchlist": "\u2b50",
              "Long/Short": "\u2696\ufe0f", "Portfoliocheck": "\U0001f4bc",
              "Umfeld": "\U0001f30d"}
_mnav = st.container(key="mobilenav")
with _mnav:
    for _pg, _icon in MOBILE_NAV.items():
        if st.button(_icon, key=f"mnav_{_pg}", use_container_width=True,
                     help=_pg, type=("primary" if _pg == nav else "secondary")):
            if _pg != nav:
                st.session_state["nav"] = _pg
                st.rerun()

try:
    from assets_logo import LGI_LOGO_B64
    _logo_html = (f'<img src="data:image/png;base64,{LGI_LOGO_B64}" '
                  f'alt="Lohrer Global Investment">')
except Exception:
    _logo_html = ""

st.markdown(
    '<div class="vr-head"><div class="logorow">' + _logo_html +
    '<div class="brand">VALUE RADAR <span class="caret">\u25ae</span></div></div>'
    '<div class="status">// vor die welle kommen &nbsp;\u00b7&nbsp; lokales terminal '
    '&nbsp;\u00b7&nbsp; anzeige in EUR &nbsp;\u00b7&nbsp; daten: yfinance'
    + ('  +finnhub' if config.FINNHUB_API_KEY else '')
    + ' &nbsp;\u00b7&nbsp; <span style="opacity:.7">Build 2026-07-06c</span></div></div>',
    unsafe_allow_html=True)

if _scroll_top_now:
    # Nach Navigation/Ticker-Klick zuverlaessig an den Seitenanfang springen.
    components.html(
        "<script>setTimeout(function(){try{"
        "var d=window.parent.document;"
        "var m=d.querySelector('section.main')||d.querySelector('[data-testid=\"stMain\"]');"
        "if(m){m.scrollTo({top:0,left:0,behavior:'auto'});}"
        "window.parent.scrollTo({top:0,behavior:'auto'});"
        "}catch(e){}},60);</script>", height=0)

with st.sidebar:
    st.markdown('<div class="sec-title">NAVIGATION</div>', unsafe_allow_html=True)
    # Navigation als anklickbare Boxen (ganze Zeile klickbar, keine Radio-Punkte)
    for pg in PAGES:
        active = (pg == nav)
        btype = "primary" if active else "secondary"
        if st.button(f"{ICONS[pg]}  {pg}", key=f"navbtn_{pg}",
                     use_container_width=True, type=btype):
            if not active:
                st.session_state["nav"] = pg
                st.rerun()
    st.markdown("---")

    st.markdown("---")
    if st.button("\U0001f504 Marktdaten neu laden", use_container_width=True,
                 help="Leert den Datencache und holt frische Live-Daten. "
                      "Ohne Klick nutzen wiederholte L\u00e4ufe denselben Cache "
                      "(ca. 30 Min.) \u2013 dadurch sind die Ergebnisse reproduzierbar."):
        for fn in (load_universe, load_fundamentals, load_fundamentals_deep, load_perf,
                   load_analyst, load_screen_extras, load_div_years, load_intel, fx_to_eur,
                   load_history, load_history_full, load_intraday_price,
                   load_intraday_quote):
            try:
                fn.clear()
            except Exception:
                pass
        for k in ("radar_results", "radar_last_pick"):
            st.session_state.pop(k, None)
        st.success("Cache geleert \u2013 der n\u00e4chste Lauf holt frische Daten.")
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
              "quality_long": "Qualit\u00e4ts-Long", "core_ko": "Aktien + KO 3x"}
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
            st.session_state["pending_nav"] = "Radar"
            st.session_state["rv_view"] = "\U0001f4c8 Trefferbilanz"
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
                      "upside_flip": "\U0001f504", "new_idea": "\u2728"}
        for _c in _changes[:8]:
            _ic = _kind_icon.get(_c.get("kind"), "\u2022")
            _tk = esc(str(_c.get("ticker") or ""))
            _txt = esc(str(_c.get("text") or ""))
            _sec = esc(str(_c.get("section") or ""))
            _when = fmt_ts(_c.get("ts"))
            st.markdown(
                f'<div class="news-box" style="padding:8px 12px">'
                f'{_ic} <b class="tick">{_tk}</b> \u2013 {_txt}'
                f'<div class="meta">{_sec}{(" \u00b7 " + _when) if _when else ""}</div></div>',
                unsafe_allow_html=True)
        st.caption("Automatisch \u00fcber Nacht berechnet \u00b7 kein Anlagerat. "
                   "Ticker anklicken \u2013 oder in die Einzelanalyse eingeben.")
        st.markdown("---")

    st.markdown('<div class="sec-title">M\u00c4RKTE HEUTE</div>', unsafe_allow_html=True)
    st.caption("Tagesverlauf je Index \u00b7 gestrichelte Linie = Startwert (0 %). "
               "Rechts der Indexstand, unten die Uhrzeit.")
    for row_start in range(0, len(INDICES), 2):          # zwei Kacheln pro Zeile
        rcols = st.columns(2)
        for col, (nm, tk) in zip(rcols, INDICES[row_start:row_start + 2]):
            with col:
                h = load_index(tk)
                if h is None or h.empty:
                    st.markdown(f'<div style="font-weight:700">{nm}</div>'
                                '<span class="na">n/a</span>', unsafe_allow_html=True)
                    continue
                closes = list(h["Close"])
                times = list(h.index)
                b, last = float(closes[0]), float(closes[-1])
                pct = (last / b - 1) * 100 if b else 0
                hexc = "#3FB950" if pct >= 0 else "#F85149"
                st.markdown(
                    f'<div style="font-weight:700;font-size:14px">{nm}</div>'
                    f'<div style="color:{hexc};font-size:16px;font-weight:700">'
                    f'{pct:+.2f} %</div>'
                    + svg_index_chart(closes, times, b, hexc, height=132),
                    unsafe_allow_html=True)

    st.markdown("---")

    def hot_table(rows, kind, key):
        if not rows:
            if kind == "radar":
                st.info("Aktuell keine Radar-Daten abrufbar \u2013 sp\u00e4ter erneut versuchen "
                        "oder das Radar-Modul mit eigenem Universum nutzen.")
            else:
                st.info("Aktuell keine Titel mit Composite \u2265 55 gefunden \u2013 sp\u00e4ter "
                        "erneut versuchen.")
            return
        if kind == "radar":
            data = [{"Ticker": r["ticker"], "Name": (r["name"] or "")[:24],
                     "Radar-Score": r["score"], "Aktive Ebenen": r["firing"],
                     "Preis \u20ac": r["price_eur"], "Sektor": (r["sector"] or "")[:16]}
                    for r in rows]
            cstyle = ["Radar-Score"]
        else:
            data = [{"Ticker": r["ticker"], "Name": (r["name"] or "")[:22],
                     "Chance": round(r.get("opportunity") or 0),
                     "Score": r["score"],
                     "Upside %": (round(r["upside"], 2)
                                  if (r.get("upside") is not None and r.get("reliable")) else None),
                     "Preis \u20ac": r["price_eur"], "Sektor": (r["sector"] or "")[:16]}
                    for r in rows]
            cstyle = ["Chance", "Score"]
        vr_rows(data, key_prefix=f"hot_{key}",
                score_cols=("Radar-Score", "Chance", "Score"),
                signed_cols=("Upside %",))
        st.caption("\U0001f449 Orangenen Ticker anklicken \u2192 \u00f6ffnet die Einzelanalyse.")

    if not st.session_state.get("home_hot_loaded"):
        st.markdown('<div class="sec-title">HOT PICKS</div>', unsafe_allow_html=True)
        if st.button("\u25b6 Radar- & Screener-Hot-Picks laden", use_container_width=True):
            st.session_state["home_hot_loaded"] = True
            st.rerun()
        st.caption("Der Scan dauert beim ersten Mal etwas \u2013 wird separat geladen, "
                   "damit die Startseite sofort reagiert.")
    else:
        htabs = st.tabs(["  \U0001f3af RADAR \u00b7 HOT PICKS  ",
                         "  \U0001f50d SCREENER \u00b7 HOT PICKS  "])
        with htabs[0]:
            st.caption("Radar-Scan \u00fcber kuratierte Inflektions-/Breakout-Kandidaten "
                       "(Semis, AI, Power, Defense, Uran, Biotech) \u2013 nach Radar-Score sortiert.")
            with st.spinner("Lade Radar Hot Picks ... (erster Aufruf dauert l\u00e4nger)"):
                hot_table(home_radar_picks(10), "radar", "home_radar_tbl")
        with htabs[1]:
            st.caption("Qualit\u00e4ts-Scan (weltweit) \u2013 nach \u201eChance\u201c sortiert "
                       "(Qualit\u00e4t + verl\u00e4sslicher Bewertungs-Upside). Upside leer = Fair Value unsicher.")
            with st.spinner("Lade Screener Hot Picks ..."):
                hot_table(home_screener_picks(10), "screener", "home_screen_tbl")

    st.markdown("---")
    saved_all = store.load_all()
    st.markdown("---")
    st.markdown('<div class="sec-title">HOT NEWS \u00b7 SCHNELL-BRIEFING</div>',
                unsafe_allow_html=True)
    for nitem in (load_marketnews("US-Markt") or [])[:5]:
        head_raw = nitem.get("headline") or ""
        summ_raw = nitem.get("summary") or ""
        chips = bfg.tags_for(head_raw, summ_raw)
        points = bfg.key_points(head_raw, summ_raw, max_points=1)
        chip_html = "".join(f'<span class="pill">{e} {esc(l)}</span>' for e, l in chips)
        pt_html = (f'<div class="sum">\u2022 {esc(points[0])}</div>' if points else "")
        url = esc(read_url(nitem.get("url"), nitem.get("access", "")))
        src = esc(nitem.get("source") or "")
        date = fmt_ts(nitem.get("ts"))
        st.markdown(f'<div class="news-box">{chip_html}'
                    f'<a href="{url}" target="_blank">{esc(head_raw)}</a>{pt_html}'
                    f'<div class="meta">{src}{" \u00b7 " + date if date else ""}</div></div>',
                    unsafe_allow_html=True)
    st.caption("Chips = Thema, Punkt = Kernaussage. Mehr (auf Deutsch, mit Briefing-Modus) "
               "im Men\u00fcpunkt \u201eNews\u201c.")
    if saved_all:
        st.markdown('<div class="sec-title">MEINE PORTFOLIOS</div>', unsafe_allow_html=True)
        st.caption("Beim Start neu berechnet. \u201e\u00d6ffnen\u201c l\u00e4dt das Portfolio in den Check.")
        if True:
            def render_saved_portfolio(pname, precs):
                with st.spinner(f"Berechne {pname} ..."):
                    prows, _inv, _res = build_portfolio_rows(precs, inc_radar=False, inc_pl=True)
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
                              "Comp.": round(r["composite"] or 0),
                              "Upside %": round(r["upside"], 2) if r.get("upside") is not None else None,
                              **({"Kauf %": round(r["ret_pct"], 2) if r.get("ret_pct") is not None else None}
                                 if an["have_pl"] else {})}
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
# EINZELANALYSE (Tabs: Analyse, Scorecard, Matrix 1, Matrix 2)
# ===========================================================================
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
    if not qv:
        st.info("Aktie eingeben (Name oder Ticker) \u2013 oder in Radar, Screener, "
                "Watchlist bzw. Portfolio auf einen orangenen Ticker tippen. "
                "Die zuletzt analysierte Aktie bleibt bis zum n\u00e4chsten Start "
                "der App stehen.")
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
                    st.warning("\u26a0 Unvollst\u00e4ndige Kennzahlen von der Datenquelle "
                               f"({len(_missing)} Kernwerte fehlen \u2013 vermutlich Rate-Limit). "
                               "Der Score ist dadurch evtl. zu niedrig. Bitte in der Seitenleiste "
                               "\u201eMarktdaten neu laden\u201c klicken oder es gleich nochmal "
                               "versuchen.")

                # Quantum Score: Meta-Score ueber Qualitaet/Bewertung/Analysten/Momentum
                q = scoring.quantum_score(s["composite"], v, intel.get("analyst"),
                                          momentum=s["category_scores"].get("momentum"))

                c = st.columns(6)
                if q["score"] is not None:
                    card(c[0], "\u269b\ufe0f Quantum Score", f"{q['score']:.0f}",
                         "/ 100", score_color(q["score"]))
                else:
                    card(c[0], "\u269b\ufe0f Quantum Score", "\u2014")
                comp = s["composite"]
                card(c[1], "Composite Score", f"{comp:.0f}",
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

                dv = v.get("model_vs_analyst_pct")
                if dv is not None and abs(dv) >= 25:
                    acnt = v.get("analyst_count")
                    st.caption(f"\u2696\ufe0f Modell {m(v.get('model_fair_value'))} vs. "
                               f"Analysten-Konsens {m(v.get('analyst_target'))}"
                               + (f" ({acnt:.0f} Analysten)" if acnt else "")
                               + f": Analysten sehen {dv:+.0f}% ggü. Modell \u2013 unser Fair Value "
                                 "gewichtet beide. Gro\u00dfe Divergenz = Bewertung h\u00e4ngt an der "
                                 "Wachstumsstory, nicht an heutigen Zahlen.")

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

                st.markdown('<div style="height:26px"></div>', unsafe_allow_html=True)
                left, right = st.columns([1, 1])

                with left:
                    st.markdown('<div class="sec-title">SCORING-MATRIX</div>', unsafe_allow_html=True)
                    rows = ""
                    for k, val in s["category_scores"].items():
                        rows += (f'<div class="row"><span class="lbl">{k}</span>'
                                 f'<div class="track"><div class="fill" '
                                 f'style="width:{val}%;background:{score_color(val)}"></div></div>'
                                 f'<span class="val">{val:.0f}</span></div>')
                    st.markdown(rows, unsafe_allow_html=True)
                    st.markdown('<div class="sec-title" style="margin-top:18px">'
                                'BEWERTUNGSMETHODEN</div>', unsafe_allow_html=True)
                    meth = v.get("methods", {})
                    if meth:
                        vr_table([{"Methode": valuation.METHOD_LABELS.get(k, k),
                                   f"Wert/Aktie ({sym})": round(val * mult, 2)}
                                  for k, val in meth.items()])
                        if v.get("method_profile"):
                            st.caption(f"\U0001f9ed Methodenwahl f\u00fcr diese Aktie: "
                                       f"{esc(v['method_profile'])}")
                        if v.get("range_low") and v.get("range_high"):
                            st.caption(f"Bewertungsspanne: {m(v['range_low'])} \u2013 {m(v['range_high'])}"
                                       + (f"  \u00b7  Streuung {v['spread_pct']:.2f} %"
                                          if v.get('spread_pct') is not None else "")
                                       + ("  \u26a0 Methoden weichen stark ab \u2013 Fair Value mit "
                                          "Vorsicht lesen" if (v.get('spread_pct') or 0) > 60 else ""))
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
                    st.markdown('<div id="vr-chart-anchor"></div>'
                                '<div class="sec-title">KURSVERLAUF</div>',
                                unsafe_allow_html=True)
                    tf = st.radio("Zeitraum", list(TIMEFRAMES.keys()), index=0,
                                  horizontal=True, label_visibility="collapsed",
                                  key="ea_tf")
                    # Beim Zeitraum-Wechsel NICHT ans Seitenende springen, sondern
                    # sanft zum Chart zuruecksetzen.
                    if st.session_state.get("_ea_tf_seen") not in (None, tf):
                        components.html(
                            "<script>setTimeout(function(){try{"
                            "var d=window.parent.document;"
                            "var e=d.getElementById('vr-chart-anchor');"
                            "if(e){e.scrollIntoView({block:'start',behavior:'auto'});}"
                            "}catch(e){}},60);</script>", height=0)
                    st.session_state["_ea_tf_seen"] = tf
                    period, interval = TIMEFRAMES[tf]
                    hist = load_history(ticker, period, interval)
                    if hist is not None and not hist.empty:
                        datecol = hist.columns[0]
                        hist = hist.rename(columns={datecol: "Datum"}).reset_index(drop=True)
                        hist["_x"] = range(len(hist))
                        base = float(hist["Close"].iloc[0])
                        last = float(hist["Close"].iloc[-1])
                        hist["pct"] = (hist["Close"] / base - 1) * 100
                        hist["Preis"] = hist["Close"] * mult
                        p_pct = (last / base - 1) * 100
                        p_abs = (last - base) * mult
                        cc = "var(--green)" if p_pct >= 0 else "var(--red)"
                        arrow = "\u2197" if p_pct >= 0 else "\u2198"
                        sign = "+" if p_abs >= 0 else ""
                        st.markdown(
                            f'<div class="px-big">{m(last)}</div>'
                            f'<div class="px-chg" style="color:{cc}">{arrow} {sign}{sym}'
                            f'{de(abs(p_abs))} ({de(p_pct,2)} %)  <span class="na">\u00b7 {tf}</span></div>',
                            unsafe_allow_html=True)

                        hexcol = "#3FB950" if p_pct >= 0 else "#F85149"
                        st.markdown(svg_area_chart(list(hist["pct"]), hexcol, height=250),
                                    unsafe_allow_html=True)
                        st.caption(f"Zeitraum {tf} \u00b7 Achse: % seit Start "
                                   f"(0-Linie gestrichelt).")
                    else:
                        st.markdown(f'<span class="na">Kein Kursverlauf f\u00fcr "{tf}" '
                                    'verf\u00fcgbar (Intraday/1W nur an Handelstagen).</span>',
                                    unsafe_allow_html=True)
                    lo, hi, pr = f.get("52w_low"), f.get("52w_high"), f.get("price")
                    if lo and hi and pr:
                        pos = (pr - lo) / (hi - lo) * 100
                        st.caption(f"52W: {m(lo)} \u2500\u2500 [{pos:.2f}%] \u2500\u2500 {m(hi)}")

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

                ec1, ec2 = st.columns([1, 1])
                with ec1:
                    st.markdown("**Peers / Wettbewerber**")
                    peers = intel.get("peers") or []
                    if not peers:
                        st.markdown('<span class="na">n/a (Finnhub-Key n\u00f6tig)</span>',
                                    unsafe_allow_html=True)
                    else:
                        peer_key = f"peers_loaded_{ticker}"
                        if not st.session_state.get(peer_key):
                            st.caption("Spart Datenabrufe: Wettbewerber-Kennzahlen werden "
                                       "nur auf Wunsch geladen.")
                            if st.button("\U0001f4ca Wettbewerber-Kennzahlen laden",
                                         key=f"loadpeers_{ticker}"):
                                st.session_state[peer_key] = True
                                st.rerun()
                            st.markdown("".join(f'<span class="pill">{p}</span>'
                                                for p in peers), unsafe_allow_html=True)
                            prowz = []
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
                                        "Upside %": pv.get("upside_pct"),
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
                    scn = intel.get("supply_chain", {})
                    st.markdown("**Kunden**")
                    cust = scn.get("customers") or []
                    st.markdown("".join(f'<span class="pill">{c}</span>' for c in cust) if cust else
                                '<span class="na">n/a (Premium-Supply-Chain n\u00f6tig)</span>',
                                unsafe_allow_html=True)
                    st.markdown("**Lieferanten**")
                    supp = scn.get("suppliers") or []
                    st.markdown("".join(f'<span class="pill">{c}</span>' for c in supp) if supp else
                                '<span class="na">n/a (Premium-Supply-Chain n\u00f6tig)</span>',
                                unsafe_allow_html=True)
                with ec2:
                    st.markdown("**News \u00b7 Yahoo Finance / Investing.com / onvista / MarketScreener**")
                    news = intel.get("news") or []
                    # Nach Datum sortieren (neueste zuerst) - kam vorher ungeordnet
                    # aus verschiedenen Quellen.
                    news = sorted(news, key=news_sort_key, reverse=True)
                    if news:
                        for n in news[:10]:
                            head = clean_headline(n.get("headline"))
                            url = read_url(n.get("url"), n.get("access", ""))
                            src = n.get("source") or ""
                            dt = fmt_news_date(n.get("datetime"))
                            meta = src + (f" \u00b7 {dt}" if dt else "")
                            st.markdown(
                                f'<div class="news-box"><a href="{url}" target="_blank">{head}</a>'
                                f'<div class="meta">{meta}</div></div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="na">Keine aktuellen News aus diesen '
                                    'Quellen gefunden.</span>', unsafe_allow_html=True)

    # ===========================================================================
    # Gemeinsame Signal-Vorbereitung fuer beide Matrizen
    # ===========================================================================
    def _prep_for_matrix(t):
        f = load_fundamentals(t)
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
            m1t = mx.auto_m1_total(sig)
            m2t = mx.auto_m2_total(sig)
            _m1c = mx.auto_m1_coverage(sig)
            _m2c = mx.auto_m2_coverage(sig)
            extras = load_screen_extras(ticker)
            rkey = f"radar_one_{ticker}"
            res = sc.evaluate(f, valu, comp, m1t, m2t, extras,
                              intel.get("insider"), intel.get("analyst"),
                              radar_score=st.session_state.get(rkey))

            st.markdown(f"### Kauf-Scorecard \u2014 {f.get('name','')} `{ticker}`")
            st.caption(f"Playbook: {ep}{' (automatisch)' if preset.startswith('Auto') else ''}  \u00b7  "
                       f"Datenbasis: Matrix 1 {_m1c[0]}/{_m1c[1]} \u00b7 Matrix 2 "
                       f"{_m2c[0]}/{_m2c[1]} Kriterien mit echten Daten. "
                       "Fehlende Kriterien werden ausgeklammert (nicht als \u201eneutral\u201c "
                       "mitgez\u00e4hlt) \u2013 bei zu d\u00fcnner Basis gibt es bewusst keinen Wert.")

            def mm(v):
                return "\u2014" if v is None else f"{sym}{de(v*mlt)}"
            vcol = {"buy": "var(--green)", "watch": "var(--amber)", "drop": "var(--red)"}[res["vkey"]]
            warn = (f'<div class="meta" style="color:var(--amber);margin-top:4px">\u26a0 RSI '
                    f'{res["rsi"]:.2f} \u2013 kurzfristig \u00fcberkauft, Einstieg evtl. abwarten</div>'
                    if res["rsi_warn"] else "")
            st.markdown(
                f'<div style="border:1px solid {vcol};border-radius:10px;padding:16px;margin:6px 0 14px">'
                f'<div style="color:{vcol};font-size:26px;font-weight:800;letter-spacing:.5px">'
                f'{res["verdict"]}</div>'
                f'<div class="meta" style="margin-top:4px">Pflicht {res["mand_pass"]}/{res["mand_total"]}'
                f' erf\u00fcllt  \u00b7  Bonus {res["bonus_count"]}/{res["bonus_total"]}  \u00b7  '
                f'Fair Value {mm(res["fair_value"])}  \u00b7  Kaufzone \u2264 {mm(res["entry_price"])}</div>'
                f'{warn}</div>', unsafe_allow_html=True)

            def gaterow(x, mandatory):
                mark = "\u2713" if x["ok"] else "\u2715"
                col = "var(--green)" if x["ok"] else ("var(--red)" if mandatory else "var(--muted)")
                return (f'<div style="display:flex;justify-content:space-between;gap:10px;'
                        f'padding:7px 10px;border-bottom:1px solid #1F2733">'
                        f'<span><b style="color:{col}">{mark}</b>&nbsp;&nbsp;{esc(x["label"])}</span>'
                        f'<span class="meta" style="white-space:nowrap">{esc(x["detail"])}</span></div>')

            gc = st.columns(2)
            with gc[0]:
                st.markdown('<div class="sec-title">PFLICHT-GATES \u00b7 alle n\u00f6tig</div>',
                            unsafe_allow_html=True)
                st.markdown("".join(gaterow(x, True) for x in res["mandatory"]), unsafe_allow_html=True)
            with gc[1]:
                st.markdown('<div class="sec-title">BONUS \u00b7 Ziel \u2265 3</div>',
                            unsafe_allow_html=True)
                st.markdown("".join(gaterow(x, False) for x in res["bonus"]), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            if st.session_state.get(rkey) is None:
                if st.button("\u25b6 Radar-Score f\u00fcr diese Aktie berechnen (optional, langsamer)"):
                    with st.spinner("Radar-Ebenen werden geladen ..."):
                        rr = radar.compute(f, load_history_full(ticker), load_eps_rev(ticker),
                                           load_insider(ticker), load_8k(ticker),
                                           load_event_news(ticker, f.get("name")))
                        st.session_state[rkey] = rr["score"]
                    st.rerun()
            else:
                st.caption(f"Radar-Score: {st.session_state[rkey]:.2f}  "
                           "(flie\u00dft als Bonuspunkt ein)")

            st.caption("Hinweis: Die Scorecard ist ein Filter, kein Kaufsignal \u2013 Pflicht-Gates "
                       "m\u00fcssen alle erf\u00fcllt sein, Bonuspunkte zeigen zus\u00e4tzlichen R\u00fcckenwind.")
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
        sections = ["WSJ", "US-Markt", "Yahoo US", "DAX", "Asien", "Aktien-News"]
        _sec = st.radio("Bereich", sections, horizontal=True,
                        label_visibility="collapsed", key="news_section")
        for section in [_sec]:
            if True:
                # WSJ ist komplett hinter einer Paywall - der "nur frei lesbar"-Filter
                # wuerde den Bereich leer machen. Hier greift stattdessen die
                # Weiterleitung ueber removepaywalls.com (siehe read_url).
                _fo = False if section == "WSJ" else free_only
                if section == "WSJ":
                    st.caption("\U0001f512 Alle WSJ-Artikel liegen hinter der Paywall. "
                               "Jede Headline wird automatisch \u00fcber "
                               "**removepaywalls.com** ge\u00f6ffnet. Klappt nur, wenn "
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
                                             '\u2192 removepaywalls</span>',
                                  "paywall": '<span style="color:#F85149">\U0001f512 Paywall '
                                             '\u2192 removepaywalls</span>'}
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
if nav == "Radar":
    _rv = st.radio("Ansicht", ["\U0001f3af Radar", "\U0001f4c8 Trefferbilanz"],
                   horizontal=True, label_visibility="collapsed", key="rv_view")
    if _rv.endswith("Trefferbilanz"):
        render_trackrecord()
    if _rv.endswith("Radar"):
        st.markdown('<div class="sec-title">RADAR \u00b7 DAS MICRON VON MORGEN</div>',
                    unsafe_allow_html=True)
        st.caption("Scannt vier Frueh-Signal-Ebenen \u2014 Events (SEC-8-K + News), "
                   "Fundamental, Schaetzungs-Momentum, stille Akkumulation \u2014 und "
                   "vergibt einen Vor-der-Welle-Score. Leuchten mehrere Ebenen gleichzeitig, "
                   "gibt es einen Koinzidenz-Bonus.")

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

        rmax = st.number_input("Max. Titel scannen", value=40, min_value=10, max_value=150,
                               step=10, help="Mehr = mehr Treffer, aber langsamer "
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
            loaded = []
            prog = st.progress(0.0, text="Lade Universum ...")
            for i, t in enumerate(tickers, 1):
                f = load_fundamentals(t)
                if f.get("price"):
                    f["_fx"] = fx_to_eur(f.get("currency", "USD")) or 1.0
                    if theme or mcap_eur_bn(f) >= rmcap_bn:   # Themen ohne Mcap-Filter
                        loaded.append(f)
                prog.progress(i / max(len(tickers), 1), text=f"Lade {t} ...")
            if branch:                                  # nach Hauptbranche filtern
                sec, kw = radar.BRANCHES[branch]
                loaded = [f for f in loaded if radar.in_branch(f, sec, kw)]
            deduped = radar.dedupe_by_name(loaded)[:int(rmax)]

            # 2) Radar nur auf den bereinigten Titeln berechnen
            results = []
            for i, f in enumerate(deduped, 1):
                t = f["ticker"]
                r = radar.compute(f, load_history_full(t), load_eps_rev(t),
                                  load_insider(t), load_8k(t),
                                  load_event_news(t, f.get("name")))
                r["_fx"] = f.get("_fx") or 1.0
                r["_price"] = f.get("price")
                r["_mcap"] = f.get("market_cap")
                r["_analysts"] = f.get("analyst_count")
                results.append(r)
                prog.progress(i / max(len(deduped), 1),
                              text=f"Scanne {t} ... ({len(results)})")
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
                     "Radar-Score": r["score"], "Ereignisse": r["layers"]["events"],
                     "Fundamental": r["layers"]["fundamental"],
                     "Sch\u00e4tzungen": r["layers"]["estimates"],
                     "Akkumulation": r["layers"]["accumulation"],
                     "Aktive Ebenen": r["firing"],
                     "Gr\u00f6\u00dfe Mrd": _mc(r.get("_mcap")),
                     "Analysten": r.get("_analysts"),
                     "Preis \u20ac": round((r["_price"] or 0) * r["_fx"], 2),
                     "Sektor": (r["sector"] or "")[:14]} for r in _shown]
            df = pd.DataFrame(rows)
            vr_table(rows, score_cols=("Radar-Score", "Ereignisse", "Fundamental",
                                       "Sch\u00e4tzungen", "Akkumulation"), height=460)
            st.caption("Werte 0\u2013100. Ereignisse = 8-K/News (\u00dcbernahmen, Auftr\u00e4ge) \u00b7 "
                       "Fundamental = Wachstum/Backlog \u00b7 Sch\u00e4tzungen = Analysten heben "
                       "Gewinnsch\u00e4tzungen \u00b7 Akkumulation = Insiderk\u00e4ufe/Volumen/Chart \u00b7 "
                       "Aktive Ebenen = Koinzidenz der 4 Ebenen.")
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
            st.info("Noch kein Scan \u2013 oben Parameter w\u00e4hlen und "
                    "\u201eRADAR SCANNEN\u201c klicken.")


# ===========================================================================
# TAB 2 — SCREENER (marktweit)
# ===========================================================================
if nav == "Screener":
    st.markdown('<div class="sec-title">MARKTWEITER SCREENER</div>', unsafe_allow_html=True)
    st.caption("Screent gegen den breiten Markt (keine Tickerliste). W\u00e4hle eine "
               "fertige Vorlage oder eigene Filter. Geld in EUR.")

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
                    "Upside %": fv.get("upside_pct"),
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

        rows = []
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
# WATCHLIST
# ===========================================================================
if nav == "Watchlist":
    st.markdown('<div class="sec-title">WATCHLIST</div>', unsafe_allow_html=True)
    st.caption("Beobachtete Titel \u2013 t\u00e4glich vom Nacht-Job \u00fcberwacht. Erreicht ein "
               "Titel die Kaufzone (Kurs \u2264 Einstieg), erscheint das auf der Startseite. "
               "\U0001f449 Orangenen Ticker anklicken \u2192 Einzelanalyse.")

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

    # --- Speicher-Diagnose: haeufigste Ursache, wenn Eintraege "verschwinden" ---
    with st.expander("\u2699\ufe0f Speicher-Diagnose (wenn Eintr\u00e4ge nicht erscheinen)"):
        try:
            _be = store.backend()
            st.write(f"Speicher: **{_be}** \u00b7 Eintr\u00e4ge: **{len(store.get_watchlist())}**")
            if _be != "sheet":
                st.warning("Es wird **nicht** ins Google Sheet geschrieben. Auf Streamlit "
                           "Cloud ist der lokale Speicher fl\u00fcchtig \u2013 Eintr\u00e4ge sind "
                           "nach einem Neustart weg, und der Nacht-Job sieht sie nie.")
            if st.button("\U0001f9ea Schreibtest durchf\u00fchren", key="wl_wtest"):
                _probe = store.get_watchlist()
                _res = store.set_watchlist(_probe)      # unveraendert zurueckschreiben
                if _res:
                    st.success("Schreiben ins Google Sheet funktioniert.")
                else:
                    st.error("Schreiben FEHLGESCHLAGEN. H\u00e4ufigste Ursache: die "
                             "Zusatzdaten sprengen das Zellen-Limit von 50.000 Zeichen "
                             "(Hedgefonds-Historie, Snapshot, Logbuch). Die neue "
                             "gsheet.py verteilt die Daten auf mehrere Zellen \u2013 "
                             "bitte hochladen.")
        except Exception as e:
            st.error(f"Diagnose fehlgeschlagen: {e}")

        # Wiederherstellungs-Status: zeigt, ob Daten geladen werden konnten
        try:
            import gsheet as _gs
            _le = getattr(_gs, "_LOAD_ERROR", {})
            if _le.get("blocked") or _le.get("blocked_main"):
                st.error("\u26a0\ufe0f **Laden der gespeicherten Daten ist fehlgeschlagen.** "
                         "Das Schreiben wurde automatisch **gesperrt**, damit nichts "
                         "\u00fcberschrieben wird. Die Rohdaten wurden im Google Sheet "
                         "in Zelle **A33** (Zusatzdaten) bzw. **A34** (Portfolios) "
                         "gesichert \u2013 dort kannst du pr\u00fcfen, ob die Inhalte noch da "
                         "sind. Schick mir den Inhalt, dann stelle ich das Format wieder her.")
            _pf = store.names()
            _hf = (store.get_hf() or {})
            st.write(f"Gefundene Portfolios: **{len(_pf)}** \u00b7 "
                     f"Hedgefonds-Depots: **{len(_hf)}**")
            if _pf:
                st.caption("Portfolios: " + ", ".join(_pf))
        except Exception as e:
            st.caption(f"Wiederherstellungs-Status nicht lesbar: {e}")

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
               "core_ko": "Aktien + KO-Hebel 3x (8\u201315 % Beimischung)"}
        for _k, _s in (_hf or {}).items():
            _v, _c0 = _s.get("value_eur", 0), _s.get("start_capital", 10000)
            _ret = (_v / _c0 - 1) * 100 if _c0 else 0
            _col = "#3FB950" if _ret >= 0 else "#F85149"
            with st.expander(f"{_sn.get(_k, _k)} \u00b7 {sym_eur(_v)} "
                             f"({_ret:+.1f} %) \u00b7 {len(_s.get('positions', []))} Pos.",
                             expanded=(_k == "marktneutral")):
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
        st.warning("\u26a0\ufe0f Experimentell & ausdr\u00fccklich kein Anlagerat. Short-Positionen "
                   "haben theoretisch unbegrenztes Verlustrisiko (Squeeze). \u201eNur teuer\u201c "
                   "ist kein Short-Grund \u2013 der Trendfilter blendet laufende Aufw\u00e4rtstrends "
                   "bewusst aus, aber pr\u00fcfe jeden Fall selbst.")

        lc = st.columns([1.4, 1, 1])
        region_choice = lc[0].selectbox(
            "Markt", ["USA + Europa", "Nur USA", "Nur Europa", "Breit (inkl. Asien)"],
            key="ls_region")
        depth = lc[1].select_slider("Tiefe", ["schnell", "mittel", "gr\u00fcndlich"],
                                    value="mittel", key="ls_depth")
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
                st.caption("Sortiert nach \u201eChance\u201c (Qualit\u00e4t + Bewertungs-Upside). "
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
                st.caption("Nur Titel, die \u00fcberbewertet UND nicht in starkem Aufw\u00e4rtstrend "
                           "sind. \u2193 unter 200T oder abdrehendes Momentum st\u00fctzt die Short-These. "
                           "Hohe \u201eVola %\u201c = gr\u00f6\u00dferes Squeeze-Risiko.")
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
            st.info("\u201eScan starten\u201c dr\u00fccken. Der Scan pr\u00fcft je Titel Kennzahlen, "
                    "Bewertung und Kurstrend \u2013 er l\u00e4uft separat, damit der Tab sofort "
                    "reagiert.")


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

        # --- Gespeichertes Portfolio laden (explizit, ein Button je Portfolio) ---
        if saved:
            st.markdown('<div class="vr-th">Gespeichertes Portfolio laden</div>',
                        unsafe_allow_html=True)
            for pname in saved:
                active = (pname == st.session_state.get("pf_cur_name"))
                lc = st.columns([3, 1])
                if lc[0].button(("\u2705 " if active else "\U0001f4c2 ") + pname,
                                key=f"pfload_{pname}", use_container_width=True,
                                type="primary" if active else "secondary"):
                    _pf_load(pname)
                    st.rerun()
                if lc[1].button("\U0001f5d1\ufe0f", key=f"pfdel_{pname}",
                                use_container_width=True, help=f"{pname} l\u00f6schen"):
                    st.session_state["pf_confirm_delete"] = pname
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
        with st.expander("\U0001f5c4\ufe0f Backup / Wiederherstellen "
                         "(wichtig bei der Online-Version!)"):
            if store.backend() == "sheet":
                st.success("\u2601\ufe0f Cloud-Speicher aktiv (Google Sheets) \u2013 deine Portfolios "
                           "\u00fcberleben Reboots automatisch. Das Backup unten ist optional.")
            else:
                st.caption("In der Streamlit-Cloud wird der lokale Speicher bei jedem Reboot "
                           "geleert \u2013 gespeicherte Portfolios gehen dann verloren. L\u00f6sung: "
                           "entweder Google Sheets als Cloud-Speicher einrichten (siehe "
                           "GOOGLE_SHEETS_SETUP.md) ODER hier ein Backup herunterladen (liegt auf "
                           "deinem Ger\u00e4t) und nach einem Reboot wieder importieren.")
                if st.button("\U0001f50d Google-Sheets-Verbindung testen"):
                    try:
                        import gsheet
                        gsheet.reset_cache()
                        msg = gsheet.diagnose()
                    except Exception as e:
                        msg = f"Diagnose nicht m\u00f6glich: {e}"
                    if msg == "OK":
                        st.success("Verbindung steht! Bitte die App einmal neu laden \u2013 "
                                   "dann wird oben \u201eCloud-Speicher aktiv\u201c angezeigt.")
                    else:
                        st.error(msg)
            bc = st.columns([1, 1])
            bc[0].download_button(
                "\u2b07\ufe0f Backup herunterladen", data=store.export_json(),
                file_name="value_radar_portfolios.json", mime="application/json",
                use_container_width=True,
                disabled=not store.names())
            up = bc[1].file_uploader("\u2b06\ufe0f Backup importieren (.json)", type=["json"],
                                     key="pf_backup_upload", label_visibility="collapsed")
            if up is not None and not st.session_state.get("pf_backup_done"):
                try:
                    nimp = store.import_json(up.read().decode("utf-8"), merge=True)
                except Exception:
                    nimp = 0
                if nimp:
                    st.session_state["pf_backup_done"] = True
                    st.success(f"{nimp} Portfolio(s) importiert. Oben unter \u201eLaden\u201c ausw\u00e4hlen.")
                    st.rerun()
                else:
                    st.warning("Kein g\u00fcltiges Backup erkannt.")
            if up is None:
                st.session_state.pop("pf_backup_done", None)

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
                load_fundamentals_deep.clear()    # frischer Basis-Kurs (tiefe Quelle)
                st.rerun()
            with st.spinner("Analysiere Positionen (Intraday-Kurse) ..."):
                rows, invalid, resolved = build_portfolio_rows(records, inc_radar, inc_pl, live=live_px)
            if live_px:
                n_live = sum(1 for r in rows if r.get("live"))
                st.caption(f"\u23f1 Intraday-Kurse aktiv f\u00fcr {n_live}/{len(rows)} Positionen \u00b7 "
                           f"Stand {_berlin_now().strftime('%H:%M:%S')} (dt. Zeit) \u00b7 "
                           "\u201eKurse aktualisieren\u201c f\u00fcr neuen Abruf.")

            if resolved:
                st.caption("Erkannt: " + "  \u00b7  ".join(f"{esc(a0)} \u2192 {esc(b0)}"
                                                           for a0, b0 in resolved))
            if invalid:
                st.warning("Nicht gefunden / keine Daten: " + ", ".join(invalid))

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
                data = [{"Ticker": r["ticker"], "Name": (r["name"] or "")[:18],
                         "Kurs \u20ac": round(r.get("price_eur") or 0, 2),
                         "Comp.": round(r["composite"] or 0),
                         "Upside %": round(r["upside"], 2) if r.get("upside") is not None else None,
                         **({"Kauf %": round(r["ret_pct"], 2) if r.get("ret_pct") is not None else None}
                            if a["have_pl"] else {}),
                         **({"G/V \u20ac": round(r["gain_eur"], 2) if r.get("gain_eur") is not None else None}
                            if a["have_pl"] else {}),
                         "Wert \u20ac": round(r["value_eur"], 2),
                         "\u2013\u2013": r["ticker"]} for r in prows]     # Verkaufs-Button
                vr_table(data, score_cols=("Comp.",),
                         signed_cols=("Upside %", "Kauf %", "G/V \u20ac"),
                         height=min(len(data) * 40 + 46, 460))
                st.caption("\U0001f449 Orangenen Ticker anklicken \u2192 Einzelanalyse \u00b7 "
                           "\u2715 rechts = Position verkaufen (mit Best\u00e4tigung, wird ins "
                           "Logbuch \u00fcbernommen).")

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
                            # Position aus dem Portfolio entfernen (und speichern)
                            st.session_state["pf_records"] = [
                                r for r in st.session_state.get("pf_records", [])
                                if str(r.get("ticker", "")).upper() != _sell]
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
                st.caption("Absicherungs-Marken sind grobe Orientierung aus Kurs & Fair Value \u2013 "
                           "kein Anlagerat.")

                # Transparenter Rechenweg: jede Zahl gegen den Broker pruefbar machen.
                pl_rows = [r for r in rows if r.get("shares") and r.get("ret_pct") is not None
                           and r.get("cost_eur") is not None]
                if pl_rows:
                    with st.expander("\U0001f50d G/V-Rechenweg anzeigen (Zahlen pr\u00fcfen)"):
                        st.caption("Formel je Position: Kosten = Anzahl \u00d7 \u00d8 Buy-in \u20ac \u00b7 "
                                   "Wert = Anzahl \u00d7 aktueller Kurs \u20ac \u00b7 G/V = Wert \u2212 Kosten. "
                                   "Weicht dein Broker ab, liegt es fast immer am KURS "
                                   "(Verz\u00f6gerung der freien Daten / anderer Handelsplatz) \u2013 "
                                   "dann \u201eKurse aktualisieren\u201c dr\u00fccken und vergleichen.")
                        calc = []
                        for r in pl_rows:
                            sh = r["shares"]
                            cost = r["cost_eur"]
                            val = r["value_eur"]
                            buyin = cost / sh if sh else None
                            calc.append({
                                "Ticker": r["ticker"], "Anzahl": sh,
                                "\u00d8 Buy-in \u20ac": round(buyin, 2) if buyin else None,
                                "Kurs \u20ac": round(r.get("price_eur") or 0, 4),
                                "Kosten \u20ac": round(cost, 2), "Wert \u20ac": round(val, 2),
                                "G/V \u20ac": round(val - cost, 2),
                                "G/V %": round(r["ret_pct"], 2)})
                        vr_table(calc, signed_cols=("G/V \u20ac", "G/V %"))

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
                   ["\U0001f4ca Sektorf\u00fchrung", "\U0001f5d3\ufe0f Saisonalit\u00e4t",
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
                       "Anhaltend": "\u2713" if r["anhaltend"] else ""}
                      for r in _ld],
                     signed_cols=("3M", "6M", "12M", "Schnitt"),
                     height=min(len(_ld) * 40 + 46, 520))
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
                st.caption("**Nur bis zu 8 Quartale verf\u00fcgbar** \u2013 das ist ein "
                           "Stimmungsbild, keine Statistik. Bei acht Terminen "
                           "kann eine \u201eQuote von 75 %\u201c auch reiner Zufall sein. "
                           "Verwende es als Frage an dich selbst, nicht als "
                           "Antwort. Kein Anlagerat.")
