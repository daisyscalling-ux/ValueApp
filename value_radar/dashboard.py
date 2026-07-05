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
/* ---- Mobile Top-Tab-Navigation (nur auf Handys/schmalen Touch-Screens) ---- */
.st-key-mobilenav{display:none;}
@media (max-width: 820px){
  /* Seitenleiste + Hamburger-Icon (oben links) auf dem Handy ausblenden -
     die Top-Leiste ersetzt die Navigation komplett. */
  section[data-testid="stSidebar"]{display:none !important;}
  [data-testid="stSidebarCollapsedControl"],
  [data-testid="collapsedControl"],
  [data-testid="stSidebarCollapseButton"]{display:none !important;}
  /* Streamlit-Kopfleiste schrumpfen, damit die Tab-Leiste ganz oben sitzt */
  header[data-testid="stHeader"]{height:0 !important; min-height:0 !important;}

  .st-key-mobilenav{
    display:block; position:sticky; top:0; z-index:99990;
    margin:0 -1rem 8px -1rem;                 /* volle Breite bis zum Rand */
    background:rgba(10,14,20,.98); backdrop-filter:blur(8px);
    border-bottom:2px solid var(--amber);
    padding:4px 4px;}
  /* Spalten NEBENEINANDER erzwingen (Streamlit stapelt sie sonst untereinander) */
  .st-key-mobilenav [data-testid="stHorizontalBlock"]{
    flex-direction:row !important; flex-wrap:nowrap !important;
    gap:2px !important; width:100%;}
  .st-key-mobilenav [data-testid="column"]{
    flex:1 1 0 !important; width:auto !important; min-width:0 !important;}
  .st-key-mobilenav .stButton{width:100%;}
  .st-key-mobilenav .stButton>button{
    width:100%; min-height:0; padding:6px 0; border:1px solid var(--line);
    border-radius:5px; box-shadow:none; background:rgba(255,255,255,.03);
    color:var(--muted); overflow:hidden;
    font-size:10px; letter-spacing:0; line-height:1.2; white-space:nowrap;}
  .st-key-mobilenav .stButton>button p{font-size:10px; margin:0;}
  .st-key-mobilenav .stButton>button:hover{color:var(--amber); border-color:var(--amber);}
  .st-key-mobilenav .stButton>button[kind="primary"]{
    color:#0A0E14; background:var(--amber); border-color:var(--amber); font-weight:800;}
  /* etwas Luft oben, kein Overlay-Abstand unten mehr noetig */
  section[data-testid="stMain"] .block-container,
  section.main .block-container{padding-top:6px !important;}
}
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


@st.cache_data(ttl=1800, show_spinner=False)
def load_fundamentals(t): return providers.get_fundamentals(t)
@st.cache_data(ttl=1800, show_spinner=False)
def load_fundamentals_deep(t): return providers.get_fundamentals(t, deep=True)
@st.cache_data(ttl=1800, show_spinner=False)
def load_intel(t, name=None): return intel_mod.gather(t, name=name)
@st.cache_data(ttl=900, show_spinner=False)
def load_history(t, p, i): 
    h = providers.get_price_history(t, period=p, interval=i)
    return h[["Close"]].reset_index() if (h is not None and not h.empty) else None
@st.cache_data(ttl=1800, show_spinner=False)
def fx_to_eur(c): return providers.get_fx_to_eur(c)


@st.cache_data(ttl=1800, show_spinner=False)
def load_universe(regions, min_mcap_eur_bn, size):
    """Gecachtes Universum mit STABILEM Schluessel (EUR-Schwelle, kein Live-FX).

    Gleiche Eingaben -> garantiert dieselbe Titelmenge bei jedem Lauf
    (innerhalb der Cache-Dauer). Die EUR->USD-Umrechnung passiert intern und
    wird im Cache eingefroren, statt den Schluessel zu verwackeln."""
    usd = providers.get_fx_to_eur("USD") or 0.92
    return ms.get_universe(list(regions), (min_mcap_eur_bn * 1e9) / usd, int(size))


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
def load_marketnews(section): return mn.get_section(section)
@st.cache_data(ttl=86400, show_spinner=False)
def tr_de(text): return tr.translate_text(text, "de")


def fmt_ts(ts):
    if not ts:
        return ""
    try:
        import datetime as dt
        return dt.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return ""


def esc(s):
    return html.escape(s or "")


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
        f'<svg viewBox="0 0 {W} {H}" width="100%" height="{H}" '
        f'preserveAspectRatio="none" style="display:block">'
        f'<polygon points="{area_pts}" fill="{color}" opacity="0.12"/>'
        f'<line x1="0" y1="{zy:.1f}" x2="{W}" y2="{zy:.1f}" stroke="#6B7686" '
        f'stroke-width="1" stroke-dasharray="4 4"/>'
        f'<polyline points="{line_pts}" fill="none" stroke="{color}" '
        f'stroke-width="1.8" vector-effect="non-scaling-stroke"/>'
        f'<text x="6" y="14" fill="#6B7686" font-size="11" font-family="monospace">'
        f'+{hi:.1f}%</text>'
        f'<text x="6" y="{H-6}" fill="#6B7686" font-size="11" font-family="monospace">'
        f'{lo:.1f}%</text></svg>')


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
    return h[["Close"]].reset_index(drop=True)


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


def build_portfolio_rows(records, inc_radar=False, inc_pl=True, live=False):
    """records: Liste von {ticker, value, date}. Baut die angereicherten Zeilen
    fuer portfolio.analyze (Composite, Upside, Fair Value, Sektor, Land, optional
    Radar und Gewinn/Verlust seit Kauf). Loest Firmennamen automatisch zu Tickern auf.
    Rueckgabe: (rows, invalid, resolved-mapping)."""
    import pandas as _pd
    rows, invalid, resolved = [], [], []
    for rec in records:
        raw = str(rec.get("ticker") or "").strip()
        val = parse_eur(rec.get("value"))
        shares = parse_eur(rec.get("shares"))
        has_val = val is not None and val > 0
        has_shares = shares is not None and shares > 0
        if not raw or (not has_val and not has_shares):
            continue
        tk = raw.upper()
        f = load_fundamentals(tk)
        if not f.get("price"):
            mm = search_symbols(raw)
            if mm:
                tk = mm[0]["symbol"].upper()
                f = load_fundamentals(tk)
                if tk != raw.upper():
                    resolved.append((raw, tk))
        if not f.get("price"):
            invalid.append(raw)
            continue
        fx = fx_to_eur(f.get("currency", "USD")) or 1.0
        p_now = f.get("price")
        live_used = False
        if live:                                    # minutengenauer Kurs fuer Wert & G/V
            p_live = load_intraday_price(tk)
            if p_live and p_live > 0:
                p_now = p_live
                live_used = True
        # Wert bestimmen: Stueckzahl x Kurs (exakt) hat Vorrang, sonst manueller Wert
        if has_shares and p_now:
            value_eur = shares * p_now * fx
        elif has_val:
            value_eur = val
        else:
            invalid.append(raw)
            continue
        ep = valuation.classify_playbook(f)
        comp = scoring.score_stock(f, None, preset=ep)["composite"]
        v = valuation.fair_value(f, None, ep)
        # Upside: Modell-Upside, wenn nicht gekappt. Sonst als Rueckfall das
        # Analysten-Kursziel (deckt Titel wie NetEase ab, wo das Modell kappt
        # oder Daten fehlen). So bleibt fast immer ein sinnvoller Wert stehen.
        capped = v.get("fair_value_capped")
        up_model = v.get("upside_pct")
        atgt = v.get("analyst_target")
        base_price = f.get("price")
        if up_model is not None and not capped:
            up_reliable = up_model
        elif atgt and base_price:
            up_reliable = round((atgt / base_price - 1) * 100, 1)
        else:
            up_reliable = up_model            # ggf. gekappt, aber besser als leer
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
        rows.append({
            "ticker": tk, "name": f.get("name"), "value_eur": float(value_eur),
            "shares": shares if has_shares else None,
            "sector": f.get("sector"), "country": f.get("country"),
            "composite": comp, "upside": up_reliable,
            "price_eur": (p_now or 0) * fx, "live": live_used,
            "fair_value_eur": fv_reliable * fx if fv_reliable else None,
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


PAGES = ["Start", "Einzelanalyse", "Radar", "Screener", "Portfoliocheck", "News"]
ICONS = {"Start": "\U0001f3e0", "Einzelanalyse": "\U0001f4c8", "Radar": "\U0001f3af",
         "Screener": "\U0001f50d", "Portfoliocheck": "\U0001f4bc", "News": "\U0001f4f0"}
if "pending_nav" in st.session_state:
    st.session_state["nav"] = st.session_state.pop("pending_nav")
st.session_state.setdefault("nav", "Start")
nav = st.session_state["nav"]

# Mobile Top-Tab-Navigation: erscheint via CSS nur auf Handys, ganz oben ueber
# dem Titel. Echte Streamlit-Buttons (kein Reload) -> Login/Status bleiben erhalten.
MOBILE_NAV = {"Start": "\U0001f3e0 Start", "Einzelanalyse": "\U0001f4c8 Analyse",
              "Radar": "\U0001f3af Radar", "Screener": "\U0001f50d Screen",
              "Portfoliocheck": "\U0001f4bc Depot", "News": "\U0001f4f0 News"}
_mnav = st.container(key="mobilenav")
with _mnav:
    _mc = st.columns(len(MOBILE_NAV))
    for _i, (_pg, _lab) in enumerate(MOBILE_NAV.items()):
        if _mc[_i].button(_lab, key=f"mnav_{_pg}", use_container_width=True,
                          type=("primary" if _pg == nav else "secondary")):
            if _pg != nav:
                st.session_state["nav"] = _pg
                st.rerun()

st.markdown(
    '<div class="vr-head"><div class="brand">VALUE RADAR <span class="caret">\u25ae</span></div>'
    '<div class="status">// vor die welle kommen &nbsp;\u00b7&nbsp; lokales terminal '
    '&nbsp;\u00b7&nbsp; anzeige in EUR &nbsp;\u00b7&nbsp; daten: yfinance'
    + ('  +finnhub' if config.FINNHUB_API_KEY else '') + '</div></div>',
    unsafe_allow_html=True)

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
                   load_history, load_history_full, load_intraday_price):
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
    st.markdown('<div class="sec-title">M\u00c4RKTE HEUTE</div>', unsafe_allow_html=True)
    icols = st.columns(len(INDICES))
    for col, (nm, tk) in zip(icols, INDICES):
        h = load_index(tk)
        with col:
            if h is None or h.empty:
                st.markdown(f'<div style="font-weight:700">{nm}</div>'
                            '<span class="na">n/a</span>', unsafe_allow_html=True)
                continue
            b, last = float(h["Close"].iloc[0]), float(h["Close"].iloc[-1])
            pct = (last / b - 1) * 100 if b else 0
            hexc = "#3FB950" if pct >= 0 else "#F85149"
            st.markdown(f'<div style="font-weight:700">{nm}</div>'
                        f'<div style="color:{hexc};font-size:17px;font-weight:700">'
                        f'{pct:+.2f} %</div>'
                        + svg_sparkline(list(h["Close"]), hexc, height=44),
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
        df = pd.DataFrame(data)

        def csc(v):
            return f"color:{score_hex(v)};font-weight:700"
        styled = df.style.map(csc, subset=cstyle).format(precision=2, formatter={"Preis \u20ac": "{:.2f}"})
        st.dataframe(styled, hide_index=True, use_container_width=True, height=340)
        ticker_open_bar(list(df["Ticker"]), key)

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
    if saved_all:
        st.markdown('<div class="sec-title">MEINE PORTFOLIOS</div>', unsafe_allow_html=True)
        st.caption("Beim Start neu berechnet. \u201e\u00d6ffnen\u201c l\u00e4dt das Portfolio in den Check.")
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
                pdf = pd.DataFrame(pdata)
                st.dataframe(
                    pdf.style.map(lambda v: f"color:{score_hex(v)};font-weight:700", subset=["Comp."])
                    .format(precision=2, formatter={"Wert \u20ac": "{:.2f}", "Gew. %": "{:.2f}"}),
                    hide_index=True, use_container_width=True,
                    height=min(len(pdf) * 36 + 40, 360))
            if st.button("\u00d6ffnen", key=f"open_pf_{pname}", use_container_width=True):
                st.session_state["pf_data"] = pf_records_to_df(precs)
                st.session_state["pf_editor_key"] = st.session_state.get("pf_editor_key", 0) + 1
                st.session_state["pf_cur_name"] = pname
                st.session_state["pending_nav"] = "Portfoliocheck"
                st.rerun()

        items = list(saved_all.items())
        for i in range(0, len(items), 2):       # zwei Portfolios pro Zeile nebeneinander
            cols = st.columns(2)
            for j, (pname, precs) in enumerate(items[i:i + 2]):
                with cols[j]:
                    render_saved_portfolio(pname, precs)

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
        url = esc(nitem.get("url") or "#")
        src = esc(nitem.get("source") or "")
        date = fmt_ts(nitem.get("ts"))
        st.markdown(f'<div class="news-box">{chip_html}'
                    f'<a href="{url}" target="_blank">{esc(head_raw)}</a>{pt_html}'
                    f'<div class="meta">{src}{" \u00b7 " + date if date else ""}</div></div>',
                    unsafe_allow_html=True)
    st.caption("Chips = Thema, Punkt = Kernaussage. Mehr (auf Deutsch, mit Briefing-Modus) "
               "im Men\u00fcpunkt \u201eNews\u201c.")


# ===========================================================================
# EINZELANALYSE (Tabs: Analyse, Scorecard, Matrix 1, Matrix 2)
# ===========================================================================
if nav == "Einzelanalyse":
    # Eingabefeld direkt im Tab (Name ODER Ticker) - Playbook laeuft im Hintergrund
    if "ea_search" not in st.session_state:
        st.session_state["ea_search"] = "MU"
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
                up = v["upside_pct"]
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
                        df = pd.DataFrame([{"Methode": valuation.METHOD_LABELS.get(k, k),
                                            f"Wert/Aktie ({sym})": round(val * mult, 2)}
                                           for k, val in meth.items()])
                        st.dataframe(df, hide_index=True, use_container_width=True)
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
                    st.markdown('<div class="sec-title">KURSVERLAUF</div>', unsafe_allow_html=True)
                    tf = st.radio("Zeitraum", list(TIMEFRAMES.keys()), index=0,
                                  horizontal=True, label_visibility="collapsed")
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
                                    pf_ = load_fundamentals(ptk)
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
                            pdf_ = pd.DataFrame(prowz)
                            evp = st.dataframe(
                                pdf_.style.map(lambda x: f"color:{score_hex(x)};font-weight:700",
                                               subset=["Score"])
                                .format(precision=2),
                                hide_index=True, use_container_width=True,
                                on_select="rerun", selection_mode="single-row", key="peer_tbl")
                            st.caption("\U0001f449 Zeile antippen \u2192 \u00f6ffnet den Wettbewerber. "
                                       "Kurse/Werte in Handelsw\u00e4hrung des jeweiligen Titels.")
                            selp = []
                            try:
                                selp = list(evp.selection.rows)
                            except Exception:
                                if isinstance(evp, dict):
                                    selp = evp.get("selection", {}).get("rows", [])
                            if selp:
                                pk = str(pdf_.iloc[selp[0]]["Ticker"])
                                if st.session_state.get("peer_pick") != pk:
                                    st.session_state["peer_pick"] = pk
                                    st.session_state["pending_search"] = pk
                                    st.session_state["pending_nav"] = "Einzelanalyse"
                                    st.rerun()
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
                    if news:
                        for n in news[:10]:
                            head = clean_headline(n.get("headline"))
                            url = n.get("url") or "#"
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
            extras = load_screen_extras(ticker)
            rkey = f"radar_one_{ticker}"
            res = sc.evaluate(f, valu, comp, m1t, m2t, extras,
                              intel.get("insider"), intel.get("analyst"),
                              radar_score=st.session_state.get(rkey))

            st.markdown(f"### Kauf-Scorecard \u2014 {f.get('name','')} `{ticker}`")
            st.caption(f"Playbook: {ep}{' (automatisch)' if preset.startswith('Auto') else ''}  \u00b7  "
                       "automatische Pr\u00fcfung aller Gates (Schwellen: KAUFAUSWAHL_ANLEITUNG.md)")

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
                st.dataframe(pd.DataFrame([
                    {"Modell": "Forward-Multiple (KGV)", "Wert": e(vs["forward_multiple_pe"])},
                    {"Modell": "EV/EBITDA-Modell", "Wert": e(vs["ev_ebitda_model"])},
                    {"Modell": "DCF-Modell", "Wert": e(vs["dcf_model"])},
                    {"Modell": "Fair Value (Blend)", "Wert": e(vs["fair_value"])},
                ]), hide_index=True, use_container_width=True)
            st.dataframe(pd.DataFrame([
                {"Entry-Preis": "ohne DCF", "Basis": e(vs["entry_no_dcf"]),
                 "MOS 10%": e(vs["entry_no_dcf_mos"][0.10]),
                 "MOS 15%": e(vs["entry_no_dcf_mos"][0.15]),
                 "MOS 20%": e(vs["entry_no_dcf_mos"][0.20])},
                {"Entry-Preis": "mit DCF", "Basis": e(vs["entry_dcf"]),
                 "MOS 10%": e(vs["entry_dcf_mos"][0.10]),
                 "MOS 15%": e(vs["entry_dcf_mos"][0.15]),
                 "MOS 20%": e(vs["entry_dcf_mos"][0.20])},
            ]), hide_index=True, use_container_width=True)
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
    nc = st.columns([1.3, 1, 1, 1.4])
    if nc[0].button("\U0001f4e1 News laden / aktualisieren", use_container_width=True):
        st.session_state["news_loaded"] = True
        load_marketnews.clear()
    de_on = nc[1].checkbox("\U0001f1e9\U0001f1ea Deutsch", value=tr.available(),
                           disabled=not tr.available(),
                           help="\u00dcbersetzt englische Quellen ins Deutsche. "
                                "Erster Aufruf langsamer.")
    brief_on = nc[2].checkbox("\u26a1 Briefing", value=True,
                              help="Schnell-Briefing: nur Themen-Chips + die 1\u20132 "
                                   "wichtigsten Kernpunkte je Meldung. F\u00fcr Details "
                                   "abschalten oder Headline anklicken.")
    nc[3].caption("Briefing-Modus: informiert in Sekunden \u2013 Chips zeigen das Thema, "
                  "Punkte die Kernaussage. Headline \u00f6ffnet den Artikel.")
    if not tr.available():
        nc[3].caption("F\u00fcr die \u00dcbersetzung: `pip install deep-translator`")

    if not st.session_state.get("news_loaded"):
        st.info("Auf \u201eNews laden\u201c klicken, um die aktuellen Markt-News zu holen.")
    else:
        sections = ["US-Markt", "Yahoo US", "DAX", "Asien", "Aktien-News"]
        nsub = st.tabs([f"  {s}  " for s in sections])
        for tabobj, section in zip(nsub, sections):
            with tabobj:
                with st.spinner(f"Lade {section} ..."
                                + (" + \u00fcbersetze ..." if (de_on and section != 'DAX') else "")):
                    items = load_marketnews(section)
                    translate_here = de_on and section != "DAX"
                if not items:
                    st.markdown('<span class="na">Aktuell keine Meldungen abrufbar '
                                '(Feeds evtl. kurz nicht erreichbar \u2013 erneut '
                                'aktualisieren).</span>', unsafe_allow_html=True)
                total_secs = 0
                for n in items[:10]:
                    head_raw = n.get("headline") or ""
                    summ_raw = n.get("summary") or ""
                    url = esc(n.get("url") or "#")
                    src = esc(n.get("source") or "")
                    date = fmt_ts(n.get("ts"))
                    flag = " \U0001f1e9\U0001f1ea" if translate_here else ""
                    if brief_on:
                        # Chips + 1-2 Kernpunkte (erst extrahieren, dann uebersetzen:
                        # spart Uebersetzungsaufrufe und haelt es schnell)
                        chips = bfg.tags_for(head_raw, summ_raw)
                        points = bfg.key_points(head_raw, summ_raw, max_points=2)
                        total_secs += bfg.reading_secs(head_raw, summ_raw)
                        head = tr_de(head_raw) if translate_here else head_raw
                        if translate_here:
                            points = [tr_de(p) for p in points]
                        chip_html = "".join(
                            f'<span class="pill">{e} {esc(l)}</span>' for e, l in chips)
                        pts_html = "".join(
                            f'<div class="sum">\u2022 {esc(p)}</div>' for p in points)
                        meta = src + (f" \u00b7 {date}" if date else "") + flag
                        st.markdown(
                            f'<div class="news-box">{chip_html}'
                            f'<a href="{url}" target="_blank">{esc(head)}</a>'
                            f'{pts_html}<div class="meta">{meta}</div></div>',
                            unsafe_allow_html=True)
                    else:
                        head = tr_de(head_raw) if translate_here else head_raw
                        summ = tr_de(summ_raw) if translate_here else summ_raw
                        sum_html = f'<div class="sum">{esc(summ)}</div>' if summ else ""
                        meta = src + (f" \u00b7 {date}" if date else "") + flag
                        st.markdown(
                            f'<div class="news-box"><a href="{url}" target="_blank">'
                            f'{esc(head)}</a>{sum_html}<div class="meta">{meta}</div></div>',
                            unsafe_allow_html=True)
                if brief_on and items:
                    st.caption(f"\u23f1 Briefing-Lesezeit gesamt: ~{max(total_secs // 60, 1)} Min. "
                               f"f\u00fcr {min(len(items), 10)} Meldungen.")


# ===========================================================================
# TAB — RADAR (Das Micron von morgen)
# ===========================================================================
if nav == "Radar":
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
        rc = st.columns(2)
        rg = rc[0].multiselect("L\u00e4nder/Regionen", ms.REGION_CHOICES,
                               default=ms.DEFAULT_REGIONS)
        rmcap = rc[1].number_input("Min. Market Cap (Mrd. \u20ac)", value=1.0, step=0.5)
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
                                          rmcap_bn, int(rmax) * 2)

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
        rows = [{"Ticker": r["ticker"], "Name": (r["name"] or "")[:22],
                 "Radar-Score": r["score"], "Ereignisse": r["layers"]["events"],
                 "Fundamental": r["layers"]["fundamental"],
                 "Sch\u00e4tzungen": r["layers"]["estimates"],
                 "Akkumulation": r["layers"]["accumulation"],
                 "Aktive Ebenen": r["firing"],
                 "Preis \u20ac": round((r["_price"] or 0) * r["_fx"], 2),
                 "Sektor": (r["sector"] or "")[:14]} for r in results]
        df = pd.DataFrame(rows)

        def csc(v):
            return f"color:{score_hex(v)};font-weight:700"
        styled = (df.style.map(csc, subset=["Radar-Score", "Ereignisse", "Fundamental",
                                            "Sch\u00e4tzungen", "Akkumulation"])
                  .format(precision=2, formatter={"Preis \u20ac": "{:.2f}"}))
        st.caption("Werte 0\u2013100; \u00fcber die Spalten\u00fcberschrift fahren f\u00fcr Erkl\u00e4rungen.")
        colcfg = {
            "Radar-Score": st.column_config.NumberColumn(
                "Radar-Score", help="Gesamt-Fr\u00fchsignal 0\u2013100 (gewichtete Summe der vier Ebenen)"),
            "Ereignisse": st.column_config.NumberColumn(
                "Ereignisse", help="SEC-8-K & News: \u00dcbernahmen, Fusionen, Kooperationen, Gro\u00dfauftr\u00e4ge"),
            "Fundamental": st.column_config.NumberColumn(
                "Fundamental", help="Wachstumsniveau und Auftragseingang/Backlog-Hinweise"),
            "Sch\u00e4tzungen": st.column_config.NumberColumn(
                "Sch\u00e4tzungen", help="Schätzungs-Momentum: Analysten heben Gewinnsch\u00e4tzungen an"),
            "Akkumulation": st.column_config.NumberColumn(
                "Akkumulation", help="Stille Akkumulation: Insiderk\u00e4ufe, Volumen-Spikes, Chart-Setup"),
            "Aktive Ebenen": st.column_config.NumberColumn(
                "Aktive Ebenen", help="Wie viele der 4 Ebenen gleichzeitig stark sind (Koinzidenz)"),
        }
        st.dataframe(styled, hide_index=True, use_container_width=True, height=460,
                     column_config=colcfg)
        ticker_open_bar(list(df["Ticker"]), "radar")

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
                st.dataframe(styled, hide_index=True, use_container_width=True, height=560,
                             column_config={
                                 "Upside %": st.column_config.NumberColumn(
                                     "Upside %", help="Fairer Wert vs. aktueller Kurs"),
                                 "Bonus-Fit": st.column_config.TextColumn(
                                     "Bonus-Fit", help="Erf\u00fcllte Bonus-Kriterien (weich)")})
                st.caption("Alle Pflicht-Kriterien sind erf\u00fcllt; \u201eBonus-Fit\u201c zeigt die "
                           "zus\u00e4tzlich erf\u00fcllten weichen Kriterien. Kein Kaufsignal \u2013 "
                           "jeden Treffer einzeln pr\u00fcfen.")
                if "Ticker" in df.columns:
                    ticker_open_bar(list(df["Ticker"]), "scr_preset")
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

            def csc(v):
                try:
                    return f"color:{score_hex(float(v))};font-weight:700"
                except Exception:
                    return ""

            def cpm(v):
                try:
                    x = float(v)
                    return "color:#3FB950" if x > 0 else ("color:#F85149" if x < 0 else "")
                except Exception:
                    return ""
            styled = (df.style
                      .map(csc, subset=["Score"])
                      .map(cpm, subset=["6M %", "1J %", "YTD %"])
                      .format(precision=2, formatter={"Preis \u20ac": "{:.2f}", "6M %": "{:+.2f}",
                               "1J %": "{:+.2f}", "YTD %": "{:+.2f}"}, na_rep="\u2014"))
            scolcfg = {
                "Preis \u20ac": st.column_config.NumberColumn("Preis \u20ac", help="Aktueller Kurs in Euro"),
                "6M %": st.column_config.NumberColumn("6 Mon. %", help="Kursentwicklung der letzten 6 Monate"),
                "1J %": st.column_config.NumberColumn("1 Jahr %", help="Kursentwicklung der letzten 12 Monate"),
                "YTD %": st.column_config.NumberColumn("Seit Jahresanfang %", help="Year-to-date"),
                "Analyst K/H/V": st.column_config.TextColumn(
                    "Analyst K/H/V", help="Analystenempfehlungen: Kauf / Halten / Verkauf"),
                "Score": st.column_config.NumberColumn(
                    "Gesamt-Score", help="Sektor-relativer Qualit\u00e4ts-/Bewertungs-Score 0\u2013100"),
            }
            st.dataframe(styled, hide_index=True, use_container_width=True, height=560,
                         column_config=scolcfg)
            st.caption(f"{len(df)} Titel \u00b7 Playbook: {screen_preset} \u00b7 "
                       "nach Score sortiert (Spalten anklickbar zum Umsortieren).")
            if "Ticker" in df.columns:
                ticker_open_bar(list(df["Ticker"]), "scr_custom")
        else:
            st.info("Kein Titel besteht alle Filter \u2013 Schwellen lockern oder "
                    "mehr Titel laden.")


# ===========================================================================
# PORTFOLIOCHECK
# ===========================================================================
if nav == "Portfoliocheck":
    st.markdown('<div class="sec-title">PORTFOLIOCHECK</div>', unsafe_allow_html=True)
    st.caption("Ticker ODER Firmenname eintragen (wird automatisch erkannt), dann "
               "Anzahl und \u00d8 Buy-in-Kurs. Der Wert wird automatisch aus Anzahl \u00d7 "
               "aktuellem Intraday-Kurs berechnet. Gewinn/Verlust und Live-Kurse sind "
               "immer aktiv.")

    # --- Speicher-Verwaltung (Laden/Loeschen buendig mit dem Auswahlfeld) ---
    saved = store.names()
    sccol = st.columns([2, 1, 1], vertical_alignment="bottom")
    pick = sccol[0].selectbox("Gespeichertes Portfolio laden", ["\u2013"] + saved)
    if sccol[1].button("Laden", use_container_width=True) and pick != "\u2013":
        st.session_state["pf_data"] = pf_records_to_df(store.load_all().get(pick, []))
        st.session_state["pf_editor_key"] = st.session_state.get("pf_editor_key", 0) + 1
        st.session_state["pf_cur_name"] = pick
        st.rerun()
    if sccol[2].button("L\u00f6schen", use_container_width=True) and pick != "\u2013":
        store.delete(pick)
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

    if "pf_data" not in st.session_state or st.session_state["pf_data"] is None:
        st.session_state["pf_data"] = pd.DataFrame([
            {"Ticker": "AAPL", "Anzahl": "10", "\u00d8 Buy-in": "", "Kaufdatum": None},
            {"Ticker": "MSFT", "Anzahl": "5", "\u00d8 Buy-in": "", "Kaufdatum": None},
            {"Ticker": "NVDA", "Anzahl": "8", "\u00d8 Buy-in": "", "Kaufdatum": None}])
    ekey = f"pf_editor_{st.session_state.get('pf_editor_key', 0)}"
    edited = st.data_editor(
        st.session_state["pf_data"], num_rows="dynamic", use_container_width=True, key=ekey,
        column_config={
            "Ticker": st.column_config.TextColumn("Ticker / Name",
                                                  help="Ticker (AAPL, SAP.DE) ODER Firmenname \u2013 "
                                                       "wird automatisch aufgel\u00f6st."),
            "Anzahl": st.column_config.TextColumn(
                "Anzahl", help="St\u00fcckzahl der Aktien. Wert = Anzahl \u00d7 aktueller Kurs."),
            "\u00d8 Buy-in": st.column_config.TextColumn(
                "\u00d8 Buy-in (\u20ac)",
                help="Dein durchschnittlicher Kaufkurs je Aktie IN EURO (so wie im "
                     "Depot angezeigt). Mit Anzahl ergibt das den exakten Gewinn/Verlust. "
                     "Alternativ das Kaufdatum nutzen."),
            "Kaufdatum": st.column_config.DateColumn(
                "Kaufdatum (optional)", format="YYYY-MM-DD",
                help="Alternative zum \u00d8 Buy-in. Leer lassen bei Sparplan/unbekannt.")})

    # Speichern (Name + Button buendig) + Kurse aktualisieren
    inc_radar, inc_pl, live_px = False, True, True      # G/V & Intraday immer an
    sc2 = st.columns([2, 1, 1], vertical_alignment="bottom")
    save_name = sc2[0].text_input("Speichern als", value=st.session_state.get("pf_cur_name", ""),
                                  placeholder="Name des Portfolios")
    if sc2[1].button("\U0001f4be Speichern", use_container_width=True):
        recs = []
        for _, rr in edited.iterrows():
            tkv = str(rr.get("Ticker") or "").strip()
            shv = parse_eur(rr.get("Anzahl"))
            if not tkv or shv is None:
                continue
            kd = rr.get("Kaufdatum")
            recs.append({"ticker": tkv, "value": None, "shares": shv,
                         "date": pd.to_datetime(kd).date().isoformat()
                         if (kd is not None and pd.notna(kd)) else None,
                         "avg_buyin": parse_eur(rr.get("\u00d8 Buy-in"))})
        if save_name.strip() and store.save(save_name.strip(), recs):
            st.session_state["pf_cur_name"] = save_name.strip()
            st.success(f"Gespeichert als \u201e{save_name.strip()}\u201c.")
        else:
            st.warning("Bitte einen Namen angeben.")
    if sc2[2].button("\U0001f504 Kurse aktualisieren", use_container_width=True):
        load_intraday_price.clear()
        st.rerun()

    records = [{"ticker": rr.get("Ticker"), "value": None,
                "shares": rr.get("Anzahl"),
                "date": rr.get("Kaufdatum"), "avg_buyin": rr.get("\u00d8 Buy-in")}
               for _, rr in edited.iterrows()]
    with st.spinner("Analysiere Positionen (Intraday-Kurse) ..."):
        rows, invalid, resolved = build_portfolio_rows(records, inc_radar, inc_pl, live=live_px)
    if live_px:
        n_live = sum(1 for r in rows if r.get("live"))
        st.caption(f"\u23f1 Intraday-Kurse aktiv f\u00fcr {n_live}/{len(rows)} Positionen \u00b7 "
                   f"Stand {datetime.now().strftime('%H:%M:%S')} \u00b7 "
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
        st.markdown(
            f'<div style="border:1px solid {vcol};border-radius:10px;padding:16px;margin:8px 0 14px">'
            f'<div style="color:{vcol};font-size:26px;font-weight:800">Portfolio: {a["label"]} '
            f'\u00b7 {a["score"]:.2f}/100</div>'
            f'<div class="meta" style="margin-top:4px">Gesamtwert {sym_eur(a["total_eur"])} \u00b7 '
            f'{a["n"]} Positionen \u00b7 effektiv {a["eff_positions"]:.2f} \u00b7 '
            f'gr\u00f6\u00dfte Position {a["max_pos"]*100:.2f} % \u00b7 '
            f'Top-Sektor {esc(a["max_sector_name"])} {a["max_sector"]*100:.2f} %</div></div>',
            unsafe_allow_html=True)

        ncards = 5 if a["have_pl"] else 4
        mc = st.columns(ncards)
        card(mc[0], "\u00d8 Composite (gew.)",
             f"{a['w_composite']:.2f}" if a["w_composite"] is not None else "\u2014",
             color=score_color(a["w_composite"] or 0))
        card(mc[1], "Erwartetes Upside",
             f"{a['pf_upside']:+.2f} %" if a["pf_upside"] is not None else "\u2014",
             color="var(--green)" if (a["pf_upside"] or 0) >= 0 else "var(--red)")
        card(mc[2], "Portfolio-Fair-Value", sym_eur(a["pf_fair_eur"]))
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

        # Positionstabelle (Zeile antippen -> Einzelanalyse; Gewicht % entfernt)
        prows = sorted(rows, key=lambda r: -r["weight"])
        any_shares = any(r.get("shares") for r in prows)
        data = [{"Ticker": r["ticker"], "Name": (r["name"] or "")[:22],
                 **({"Anzahl": r["shares"]} if any_shares else {}),
                 "Kurs \u20ac": round(r.get("price_eur") or 0, 2),
                 "Sektor": (r["sector"] or "")[:16], "Composite": round(r["composite"] or 0),
                 "Upside %": round(r["upside"], 2) if r.get("upside") is not None else None,
                 **({"Kauf %": round(r["ret_pct"], 2) if r.get("ret_pct") is not None else None}
                    if a["have_pl"] else {}),
                 **({"G/V \u20ac": round(r["gain_eur"], 2) if r.get("gain_eur") is not None else None}
                    if a["have_pl"] else {}),
                 **({"Status": r["status"][0]} if a["have_pl"] else {}),
                 **({"Radar": round(r["radar"] or 0)} if inc_radar else {}),
                 "Playbook": r["playbook"],
                 "Wert \u20ac": round(r["value_eur"], 2)} for r in prows]   # ganz rechts
        dfp = pd.DataFrame(data)

        def csc(v):
            return f"color:{score_hex(v)};font-weight:700"

        def gvcol(v):                                   # gruen bei Plus, rot bei Minus
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return ""
            return ("color:#3ddc84;font-weight:700" if v >= 0
                    else "color:#ff5c5c;font-weight:700")

        def sgn_eur(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "\u2014"
            return f"{'+' if v >= 0 else '\u2212'}{de(abs(v), 2)}"

        def sgn_pct(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "\u2014"
            return f"{'+' if v >= 0 else '\u2212'}{de(abs(v), 2)} %"

        subset = ["Composite"] + (["Radar"] if inc_radar else [])
        pl_cols = [c for c in ("Kauf %", "G/V \u20ac") if c in dfp.columns]
        fmt = {"Kurs \u20ac": "{:.2f}", "Wert \u20ac": "{:.2f}"}
        if "Kauf %" in dfp.columns:
            fmt["Kauf %"] = sgn_pct
        if "G/V \u20ac" in dfp.columns:
            fmt["G/V \u20ac"] = sgn_eur
        styled = (dfp.style.map(csc, subset=subset).format(fmt, precision=2))
        if pl_cols:
            styled = styled.map(gvcol, subset=pl_cols)
        ev = st.dataframe(styled, hide_index=True, use_container_width=True,
                          on_select="rerun", selection_mode="single-row", key="pf_holdings")
        sel = []
        try:
            sel = list(ev.selection.rows)
        except Exception:
            if isinstance(ev, dict):
                sel = ev.get("selection", {}).get("rows", [])
        if sel:
            picked = str(dfp.iloc[sel[0]]["Ticker"])
            if st.session_state.get("pf_hold_pick") != picked:
                st.session_state["pf_hold_pick"] = picked
                st.session_state["pending_search"] = picked
                st.session_state["nav"] = "Einzelanalyse"
                st.rerun()
        st.caption("\U0001f449 Zeile antippen \u2192 \u00f6ffnet die Aktie in der Einzelanalyse.")

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
            evc = st.dataframe(cdf.style.map(csc, subset=["Chance", "Score"])
                               .format(precision=2, formatter={"Preis \u20ac": "{:.2f}"}),
                               hide_index=True, use_container_width=True,
                               on_select="rerun", selection_mode="single-row", key="pf_cand2")
            selc = []
            try:
                selc = list(evc.selection.rows)
            except Exception:
                if isinstance(evc, dict):
                    selc = evc.get("selection", {}).get("rows", [])
            if selc:
                pk = str(cdf.iloc[selc[0]]["Ticker"])
                if st.session_state.get("pf_cand_pick") != pk:
                    st.session_state["pf_cand_pick"] = pk
                    st.session_state["pending_search"] = pk
                    st.session_state["nav"] = "Einzelanalyse"
                    st.rerun()
            st.caption("\U0001f449 Zeile antippen \u2192 Einzelanalyse. \u201eChance\u201c = Qualit\u00e4t "
                       "kombiniert mit Bewertungs-Upside. Kein Anlagerat \u2013 selbst pr\u00fcfen.")
        else:
            st.info("Aktuell keine \u00fcberzeugenden Erg\u00e4nzungen gefunden (verlangt Qualit\u00e4t "
                    "Score \u2265 55, belastbarer Fair Value und glaubhaftes Upside +8 bis +80 %). "
                    "Bewusst lieber nichts vorschlagen als \u00fcberteuerte Titel.")
