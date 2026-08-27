"""
ui_bewertung.py - Darstellungsschicht fuer den Bewertungsteil.

Uebernimmt den AUFBAU von AlphaSpread (Grosszahl mit Vergleichsbalken,
Treiberliste, Urteilskasten, Korridorleiste, Referenztabelle, Szenario-
Umschalter) - aber im BESTEHENDEN Terminal-Look des Dashboards. Ein weisses
Kartenlayout mitten in einer dunklen App sieht nicht nach AlphaSpread aus,
sondern nach Fehler. Wer trotzdem umstellen will: inject_css(theme="hell").

Alle Klassen sind mit `va-` praefixiert. Wichtig, weil dashboard.py bereits
`.vr-card` und `.row` global definiert - ohne eigenes Praefix wuerden sich
beide Stylesheets gegenseitig ueberschreiben.

Reine Praesentation: jede Funktion nimmt fertige Werte aus valuation,
relval und schaetzguete entgegen und rendert sie.
"""

from __future__ import annotations

import html as _html
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import streamlit as st

# ---------------------------------------------------------------------------
# Farbtoken
# ---------------------------------------------------------------------------

DUNKEL = {
    "bg": "#0A0E14", "panel": "#121821", "panel2": "#0D1219", "line": "#1F2733",
    "fg": "#E6E1D3", "muted": "#6B7686", "amber": "#FFB000", "green": "#3FB950",
    "red": "#F85149", "cyan": "#58C4DD", "violet": "#A78BFA",
    "rot_weich": "#331A19", "gruen_weich": "#16301C", "gelb_weich": "#332708",
    "track": "#0D1219",
    # Eigene, kraeftigere Toene NUR fuer die Luecke im Balkenpaar. Die weichen
    # Toene oben sind fuer Kastenhintergruende gedacht und gehen auf dunklem
    # Grund praktisch unter - als Flaeche, die eine Differenz zeigen soll,
    # taugen sie nicht.
    "luecke_rot": "#7A2620", "luecke_gruen": "#1F6B39",
}

HELL = {
    "bg": "#F3F5F9", "panel": "#FFFFFF", "panel2": "#F7F9FC", "line": "#E6EAF1",
    "fg": "#0F172A", "muted": "#6B7280", "amber": "#B77400", "green": "#12A150",
    "red": "#E0342C", "cyan": "#1B8FD1", "violet": "#7C5CD6",
    "rot_weich": "#FBDDD5", "gruen_weich": "#D8F0E2", "gelb_weich": "#FBEBD2",
    "track": "#F1F3F7",
    "luecke_rot": "#F2B4A6", "luecke_gruen": "#8FD9AC",
}

C = dict(DUNKEL)

TON = {"gruen": "green", "gelb": "amber", "rot": "red", "grau": "muted"}

#: Waehrungszeichen fuer die Grosszahl. Ohne Eintrag wird der Code gezeigt -
#: besser ein sperriges "CHF" als ein falsches "$".
WAEHRUNGSZEICHEN = {"EUR": "\u20ac", "USD": "$", "GBP": "\u00a3",
                    "JPY": "\u00a5", "CHF": "CHF"}


def _farbe(ton: str) -> str:
    return C.get(TON.get(ton, "muted"), C["muted"])


def _weich(ton: str) -> str:
    return {"gruen": C["gruen_weich"], "gelb": C["gelb_weich"],
            "rot": C["rot_weich"]}.get(ton, C["panel2"])


_CSS = """
<style>
.va, .va *{box-sizing:border-box;}
.va-num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1;}

.va-sec{display:flex;align-items:baseline;gap:10px;margin:26px 0 12px;
  border-bottom:1px solid %(line)s;padding-bottom:6px;}
.va-sec .n{font-size:13px;font-weight:700;color:%(muted)s;}
.va-sec .t{font-size:13px;font-weight:700;letter-spacing:2px;color:%(amber)s;
  text-transform:uppercase;}
.va-sec .t i{font-style:normal;color:%(muted)s;font-weight:400;}

.va-card{border:1px solid %(line)s;background:%(panel)s;padding:14px 16px;
  margin-bottom:10px;}
.va-card h4{margin:0 0 2px;font-size:13px;font-weight:700;color:%(fg)s;
  letter-spacing:1px;text-transform:uppercase;}
.va-card .sub{font-size:11.5px;color:%(muted)s;margin-bottom:12px;line-height:1.5;}
.va-split{display:grid;grid-template-columns:1.1fr .9fr;gap:22px;}
@media (max-width:900px){.va-split{grid-template-columns:1fr;gap:14px;}}

.va-big{font-size:44px;line-height:1;font-weight:800;letter-spacing:-1px;}
.va-big .cur{font-size:22px;color:%(muted)s;font-weight:600;vertical-align:6px;}
.va-kick{font-size:13px;font-weight:700;color:%(fg)s;letter-spacing:1px;
  text-transform:uppercase;}
.va-kick span{display:block;font-size:11px;font-weight:400;color:%(muted)s;
  letter-spacing:0;text-transform:none;margin-top:1px;}
.va-lead{font-size:13.5px;line-height:1.7;color:%(fg)s;opacity:.9;}
.va-lead b{opacity:1;font-weight:700;}

.va-bars{margin-top:14px;}
.va-bar{position:relative;height:28px;background:%(track)s;border:1px solid %(line)s;
  margin-bottom:5px;overflow:hidden;}
.va-bar .fill{position:absolute;top:0;bottom:0;left:0;display:flex;align-items:center;
  padding:0 9px;font-size:11.5px;font-weight:700;letter-spacing:.5px;}
.va-bar .rest{position:absolute;top:0;bottom:0;display:flex;align-items:center;
  justify-content:center;font-size:11px;font-weight:700;color:#F2F5F9;
  letter-spacing:.5px;}
.va-bar .val{position:absolute;right:9px;top:50%%;transform:translateY(-50%%);
  font-size:11.5px;font-weight:700;}
.va-badge{display:inline-block;padding:3px 8px;font-size:10.5px;font-weight:700;
  letter-spacing:1px;text-transform:uppercase;}

.va-list{border:1px solid %(line)s;}
.va-list .va-r{display:flex;justify-content:space-between;align-items:center;
  padding:8px 10px;border-bottom:1px solid %(line)s;font-size:12.5px;}
.va-list .va-r:last-child{border-bottom:none;}
.va-list .k{color:%(muted)s;}
.va-list .v{font-weight:700;color:%(fg)s;}
.va-list .v em{font-style:normal;color:%(muted)s;font-weight:400;}
.va-lbl{font-size:10.5px;font-weight:700;letter-spacing:1.5px;color:%(muted)s;
  text-transform:uppercase;margin:12px 0 5px;}
.va-lbl:first-child{margin-top:0;}

.va-verdict{border:1px solid;padding:12px 14px;}
.va-verdict .h{font-size:16px;font-weight:800;line-height:1.25;}
.va-verdict .s{font-size:12.5px;color:%(fg)s;opacity:.75;margin-top:5px;line-height:1.5;}
.va-verdict .m{font-size:12px;color:%(muted)s;margin-top:9px;}
.va-chip{float:right;padding:2px 7px;font-size:10.5px;font-weight:700;
  border:1px solid;}

.va-tbl{width:100%%;border-collapse:collapse;font-size:12.5px;}
.va-tbl th{text-align:left;font-size:10.5px;letter-spacing:1.2px;text-transform:uppercase;
  color:%(muted)s;font-weight:700;padding:7px 9px;border-bottom:1px solid %(line)s;}
.va-tbl th.r,.va-tbl td.r{text-align:right;}
.va-tbl td{padding:8px 9px;border-bottom:1px solid %(line)s;color:%(fg)s;}
.va-tbl tr:last-child td{border-bottom:none;}
.va-tbl .name{font-weight:600;}
.va-tbl .note{display:block;font-size:10.5px;font-weight:400;margin-top:2px;}
.va-pill{display:inline-block;padding:2px 7px;font-size:11px;font-weight:700;}
.va-hl td{background:%(panel2)s;}

.va-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:9px;}
.va-tile{border:1px solid %(line)s;background:%(panel)s;padding:12px 13px;}
.va-tile .big{font-size:26px;font-weight:800;letter-spacing:-.5px;}
.va-tile .cap{font-size:10.5px;font-weight:700;letter-spacing:1.2px;
  text-transform:uppercase;color:%(muted)s;margin-top:2px;}
.va-tile .chips{display:flex;gap:5px;margin-top:10px;flex-wrap:wrap;}
.va-tile .chips span{border:1px solid %(line)s;padding:2px 5px;font-size:10.5px;
  color:%(muted)s;}
.va-tile .scale{margin-top:10px;height:6px;background:%(track)s;position:relative;
  border:1px solid %(line)s;}
.va-tile .scale i{position:absolute;top:-3px;width:3px;height:10px;}

.va-stack{display:flex;height:24px;border:1px solid %(line)s;overflow:hidden;}
.va-stack div{display:flex;align-items:center;justify-content:center;font-size:10.5px;
  font-weight:700;color:#0A0E14;}
.va-legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;font-size:11.5px;
  color:%(muted)s;}
.va-legend i{display:inline-block;width:9px;height:9px;margin-right:5px;}

.va-note{font-size:12px;color:%(muted)s;line-height:1.55;padding:3px 0 3px 9px;
  border-left:2px solid %(amber)s;margin:5px 0;}
.va-stars{letter-spacing:3px;font-size:17px;color:%(amber)s;}
.va-stars i{font-style:normal;color:%(line)s;}
</style>
"""


def inject_css(theme: str = "dunkel") -> None:
    """Einmal pro Seite aufrufen, nach dem globalen CSS des Dashboards."""
    global C
    C = dict(HELL if theme in ("hell", "light") else DUNKEL)
    st.markdown(_CSS % C, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Formatierung
# ---------------------------------------------------------------------------

def _e(x) -> str:
    return _html.escape("" if x is None else str(x))


def de(x: Optional[float], dez: int = 2) -> str:
    """Deutsche Schreibweise: schmales Leerzeichen als Tausender, Komma dezimal."""
    if x is None:
        return "n/a"
    return f"{x:,.{dez}f}".replace(",", "\u2009").replace(".", ",")


def geld(x: Optional[float], waehrung: str = "USD", dez: int = 2) -> str:
    return "n/a" if x is None else f"{de(x, dez)}\u202f{waehrung}"


def pct(x: Optional[float], dez: int = 1, vz: bool = False, schon_pct: bool = False) -> str:
    if x is None:
        return "n/a"
    v = x if schon_pct else x * 100
    s = f"{v:+.{dez}f}" if vz else f"{v:.{dez}f}"
    return s.replace(".", ",") + "\u202f%"


def mult(x: Optional[float], dez: int = 1) -> str:
    return "n/a" if x is None else de(x, dez) + "x"


def _md(html_str: str) -> None:
    st.markdown(f'<div class="va">{html_str}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------

def abschnitt(nummer: int, titel: str, zusatz: str = "") -> None:
    z = f"<i> {_e(zusatz)}</i>" if zusatz else ""
    _md(f'<div class="va-sec"><span class="n">{nummer}</span>'
        f'<span class="t">{_e(titel)}{z}</span></div>')


def szenario_umschalter(key: str, index: int = 1) -> str:
    """Gibt 'bear' | 'base' | 'bull' zurueck."""
    labels = ["Bear Case", "Base Case", "Bull Case"]
    wahl = st.radio("Szenario", labels, index=index, key=key,
                    horizontal=True, label_visibility="collapsed")
    return {"Bear Case": "bear", "Base Case": "base", "Bull Case": "bull"}[wahl]


def wert_kopf(*, titel: str, fall: str, wert: Optional[float], preis: Optional[float],
              text_html: str, waehrung: str = "USD", akzent: str = "amber",
              balken_label: str = "Innerer Wert") -> None:
    """Grosszahl mit Vergleichsbalken - der Kopfbereich jedes Bewertungsblocks."""
    farbe = C.get(akzent, akzent)
    w = wert or 0.0
    p = preis or 0.0

    if not wert or not preis:
        badge = ""
    else:
        ab = (p - w) / w
        f = C["red"] if ab >= 0 else C["green"]
        txt = ("ueberbewertet" if ab >= 0 else "unterbewertet") + f" {abs(ab) * 100:.0f} %"
        badge = (f'<div style="text-align:right;margin-bottom:5px;">'
                 f'<span class="va-badge" style="background:{f};color:{C["bg"]};">'
                 f'{_e(txt)}</span></div>')

    top = max(w, p) or 1.0
    bw, bp = 100.0 * w / top, 100.0 * p / top
    luecke = C["luecke_rot"] if p >= w else C["luecke_gruen"]
    # Beschriftung in die Luecke: eine Farbflaeche allein sagt nicht, wie gross
    # der Abstand ist.
    if wert and preis:
        _d = (p - w) / w * 100
        luecke_txt = f"{abs(_d):.0f} %"
    else:
        luecke_txt = ""

    _md(
        f'<div class="va-card"><div class="va-split">'
        f'  <div class="va-lead">{text_html}</div>'
        f'  <div>'
        f'    <div class="va-kick">{_e(titel)}<span>{_e(fall)}</span></div>'
        f'    <div class="va-big va-num" style="color:{farbe};margin:8px 0 2px;">'
        f'<span class="cur">{_e(WAEHRUNGSZEICHEN.get(waehrung, waehrung))}</span>'
        f'{de(wert, 2)}</div>'
        f'    {badge}'
        f'    <div class="va-bars">'
        f'      <div class="va-bar">'
        f'        <div class="rest va-num" style="left:{bw:.1f}%;'
        f'width:{max(0.0, bp - bw):.1f}%;background:{luecke};">'
        f'{luecke_txt if bp > bw else ""}</div>'
        f'        <div class="fill va-num" style="width:{bw:.1f}%;background:{farbe};'
        f'color:{C["bg"]};">{_e(balken_label)}</div></div>'
        f'      <div class="va-bar">'
        f'        <div class="rest va-num" style="left:{bp:.1f}%;'
        f'width:{max(0.0, bw - bp):.1f}%;background:{luecke};">'
        f'{luecke_txt if bw > bp else ""}</div>'
        f'        <div class="fill va-num" style="width:{bp:.1f}%;background:{C["line"]};'
        f'color:{C["fg"]};">Kurs<span class="val">{_e(geld(preis, waehrung))}</span>'
        f'</div></div>'
        f'    </div></div>'
        f'</div></div>'
    )


def treiber_panel(bloecke: Sequence[Tuple[str, Sequence[Tuple[str, str]]]]) -> None:
    """bloecke: [(Ueberschrift, [(Schluessel, Wert-als-HTML), ...]), ...]"""
    teile = []
    for titel, zeilen in bloecke:
        rows = "".join(f'<div class="va-r"><span class="k">{_e(k)}</span>'
                       f'<span class="v va-num">{v}</span></div>' for k, v in zeilen)
        teile.append(f'<div class="va-lbl">{_e(titel)}</div>'
                     f'<div class="va-list">{rows}</div>')
    _md(f'<div class="va-card">{"".join(teile)}</div>')


def urteil_box(*, titel: str, text: str, ton: str, chip: str = "",
               kennzahlen: str = "") -> None:
    f, w = _farbe(ton), _weich(ton)
    chip_html = (f'<span class="va-chip" style="border-color:{f};color:{f};">'
                 f'{_e(chip)}</span>') if chip else ""
    kz = f'<div class="m">{kennzahlen}</div>' if kennzahlen else ""
    _md(f'<div class="va-verdict" style="border-color:{f};background:{w};">'
        f'{chip_html}<div class="h" style="color:{f};">{_e(titel)}</div>'
        f'<div class="s">{_e(text)}</div>{kz}</div>')


def korridor_balken(*, tief: float, mitte: float, hoch: float,
                    impliziert: Optional[float],
                    marker: Sequence[Tuple[str, float]] = ()) -> None:
    """SVG-Leiste: realistischer Korridor, Anker, vom Kurs verlangter Wert."""
    pts = [tief, mitte, hoch] + [m[1] for m in marker]
    if impliziert is not None:
        pts.append(impliziert)
    lo, hi = min(pts), max(pts)
    pad = max((hi - lo) * 0.22, 0.004)
    lo, hi = lo - pad, hi + pad
    spanne = hi - lo or 1.0

    W, H = 720, 104

    def x(v):
        return 26 + (v - lo) / spanne * (W - 52)

    def lbl(v):
        return f"{v * 100:.1f}".replace(".", ",") + " %"

    x_lo, x_hi, x_mi = x(tief), x(hoch), x(mitte)
    ok = impliziert is None or tief <= impliziert <= hoch
    imp_f = C["green"] if ok else C["red"]

    p = [f'<svg viewBox="0 0 {W} {H}" width="100%" height="{H}" role="img" '
         f'aria-label="Realistischer Korridor">',
         f'<rect x="26" y="42" width="{W - 52}" height="14" fill="{C["track"]}" '
         f'stroke="{C["line"]}"/>',
         f'<rect x="{x_lo:.1f}" y="42" width="{max(2.0, x_hi - x_lo):.1f}" height="14" '
         f'fill="{C["line"]}"/>',
         f'<line x1="{x_mi:.1f}" y1="38" x2="{x_mi:.1f}" y2="60" stroke="{C["muted"]}" '
         f'stroke-width="1.5" stroke-dasharray="3 3"/>',
         f'<text x="{(x_lo + x_hi) / 2:.1f}" y="32" text-anchor="middle" font-size="10" '
         f'font-weight="700" fill="{C["muted"]}" letter-spacing="1.2">'
         f'REALISTISCHER KORRIDOR</text>',
         f'<text x="{x_lo:.1f}" y="70" text-anchor="middle" font-size="10" '
         f'fill="{C["muted"]}">{lbl(tief)}</text>',
         f'<text x="{x_hi:.1f}" y="70" text-anchor="middle" font-size="10" '
         f'fill="{C["muted"]}">{lbl(hoch)}</text>']

    for i, (name, val) in enumerate(marker):
        xv, y = x(val), (86 if i % 2 else 70)
        p.append(f'<circle cx="{xv:.1f}" cy="49" r="3.5" fill="{C["panel"]}" '
                 f'stroke="{C["muted"]}" stroke-width="1.5"/>')
        p.append(f'<text x="{xv:.1f}" y="{y + 12}" text-anchor="middle" font-size="9.5" '
                 f'fill="{C["muted"]}">{_e(name)}</text>')

    if impliziert is not None:
        xi = x(impliziert)
        p.append(f'<line x1="{xi:.1f}" y1="36" x2="{xi:.1f}" y2="62" stroke="{imp_f}" '
                 f'stroke-width="2"/>')
        p.append(f'<circle cx="{xi:.1f}" cy="49" r="5" fill="{imp_f}"/>')
        p.append(f'<text x="{xi:.1f}" y="20" text-anchor="middle" font-size="10.5" '
                 f'font-weight="700" fill="{imp_f}">Kurs verlangt {lbl(impliziert)}</text>')
    p.append("</svg>")
    _md(f'<div class="va-card">{"".join(p)}</div>')


def benchmark_tabelle(zeilen: Iterable[dict], *, treiber_kopf: str = "Startwachstum",
                      wert_kopf_txt: str = "DCF-Wert", waehrung: str = "USD") -> None:
    body = []
    for z in zeilen:
        up = z.get("upside")
        if up is None:
            pill = f'<span class="va-pill" style="color:{C["muted"]};">n/a</span>'
        elif abs(up) < 0.5:
            pill = (f'<span class="va-pill" style="border:1px solid {C["line"]};'
                    f'color:{C["muted"]};">= heutiger Kurs</span>')
        elif up < 0:
            pill = (f'<span class="va-pill" style="background:{C["rot_weich"]};'
                    f'color:{C["red"]};">{abs(up):.0f} % ueberbewertet</span>')
        else:
            pill = (f'<span class="va-pill" style="background:{C["gruen_weich"]};'
                    f'color:{C["green"]};">{up:.0f} % unterbewertet</span>')
        rng = (f'<span class="note" style="color:{C["green"]};">im Korridor</span>'
               if z.get("im_korridor")
               else f'<span class="note" style="color:{C["red"]};">ausserhalb</span>')
        hl = ' class="va-hl"' if z.get("key") == "impliziert" else ""
        body.append(
            f'<tr{hl}><td><span class="name">{_e(z["label"])}</span>{rng}</td>'
            f'<td class="r va-num"><b>{z["treiber"] * 100:.1f} %</b></td>'
            f'<td class="r va-num">{_e(geld(z.get("wert"), waehrung))}</td>'
            f'<td class="r">{pill}</td></tr>')
    _md(f'<div class="va-card"><table class="va-tbl"><thead><tr><th>Referenz</th>'
        f'<th class="r">{_e(treiber_kopf)}</th><th class="r">{_e(wert_kopf_txt)}</th>'
        f'<th class="r">Abweichung</th></tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>')


def diagnose_karte(diagnose: Optional[dict], herkunft: Optional[dict]) -> None:
    """Die Ergaenzung gegenueber dem Vorbild: woher der Wert tatsaechlich kommt."""
    from valuation import HERKUNFT_FARBE, HERKUNFT_LABEL, TERMINAL_ANTEIL_WARN

    links = '<div class="sub">Kein DCF fuer diesen Titel.</div>'
    if diagnose:
        ta = diagnose.get("terminal_anteil") or 0.0
        f = C["red"] if ta > TERMINAL_ANTEIL_WARN else C["cyan"]
        rows = []
        if diagnose.get("multiple_impliziert") is not None:
            gap = diagnose["multiple_impliziert"] > (diagnose["multiple_genutzt"] or 0) * 1.25
            rows.append(
                f'<div class="va-r"><span class="k">Terminal-Multiple vom Kurs verlangt</span>'
                f'<span class="v va-num" style="color:{C["red"] if gap else C["fg"]};">'
                f'{mult(diagnose["multiple_impliziert"])}'
                f'<em> statt {mult(diagnose["multiple_genutzt"])}</em></span></div>')
        if diagnose.get("multiple_heute"):
            rows.append(f'<div class="va-r"><span class="k">Heutiges FCF-Multiple</span>'
                        f'<span class="v va-num">{mult(diagnose["multiple_heute"])}'
                        f'</span></div>')
        rows.append(f'<div class="va-r"><span class="k">WACC / Terminalwachstum</span>'
                    f'<span class="v va-num">{pct(diagnose.get("wacc"))} / '
                    f'{pct(diagnose.get("terminal_growth"))}</span></div>')
        links = (
            f'<div class="va-lbl">Terminalwert-Anteil</div>'
            f'<div class="va-bar" style="height:22px;">'
            f'<div class="fill va-num" style="width:{ta * 100:.1f}%;background:{f};'
            f'color:{C["bg"]};">{ta * 100:.0f} %</div></div>'
            f'<div class="va-list" style="margin-top:10px;">{"".join(rows)}</div>')

    rechts = '<div class="sub">Keine Herkunftszerlegung verfuegbar.</div>'
    if herkunft and herkunft.get("nach_herkunft"):
        seg, leg = [], []
        for k, v in herkunft["nach_herkunft"].items():
            if v < 0.005:
                continue
            fb = HERKUNFT_FARBE.get(k, C["muted"])
            seg.append(f'<div style="width:{v * 100:.1f}%;background:{fb};">'
                       f'{v * 100:.0f}%</div>')
            leg.append(f'<span><i style="background:{fb};"></i>'
                       f'{_e(HERKUNFT_LABEL.get(k, k))}</span>')
        rechts = (f'<div class="va-lbl">Woraus der Fair Value besteht</div>'
                  f'<div class="va-stack">{"".join(seg)}</div>'
                  f'<div class="va-legend">{"".join(leg)}</div>')

    hinweise = list((diagnose or {}).get("hinweise") or []) + \
               list((herkunft or {}).get("hinweise") or [])
    notes = "".join(f'<div class="va-note">{_e(h)}</div>' for h in hinweise)

    _md(f'<div class="va-card"><h4>Woher der Wert kommt</h4>'
        f'<div class="sub">Zwei Anteile, die jedes Bewertungsmodell verschweigt - '
        f'und die bestimmen, worauf man eigentlich wettet.</div>'
        f'<div class="va-split">{f"<div>{links}</div>"}{f"<div>{rechts}</div>"}</div>'
        f'{notes}</div>')


def gitter_tabelle(gitter: Optional[dict], waehrung: str = "USD") -> None:
    """Wachstum x Cash-Basis mit Farbcodierung gegen den Kurs."""
    if not gitter:
        return
    gs, cs, werte, preis = (gitter["wachstum"], gitter["cash_basis"],
                            gitter["werte"], gitter["preis"])
    kopf = "".join(f'<th class="r">{g * 100:.0f} %</th>' for g in gs)
    rows = []
    for i in range(len(cs) - 1, -1, -1):
        zellen = []
        for j in range(len(gs)):
            v = werte[i][j]
            if not v:
                zellen.append(f'<td class="r" style="color:{C["muted"]};">-</td>')
                continue
            r = v / preis - 1.0
            if r >= 0.15:
                bg, fg = C["gruen_weich"], C["green"]
            elif r >= 0:
                bg, fg = C["panel2"], C["green"]
            elif r >= -0.15:
                bg, fg = C["gelb_weich"], C["amber"]
            else:
                bg, fg = C["rot_weich"], C["red"]
            zellen.append(f'<td class="r va-num" style="background:{bg};color:{fg};'
                          f'font-weight:600;">{de(v, 0)}</td>')
        rows.append(f'<tr><td class="name va-num">{de(cs[i], 2)}x</td>'
                    f'{"".join(zellen)}</tr>')
    _md(f'<div class="va-card"><h4>Wachstum x Cash-Basis</h4>'
        f'<div class="sub">Wert je Aktie in {_e(waehrung)}. Gruen = ueber dem Kurs '
        f'({_e(geld(preis, waehrung))}), rot = darunter. Die Zeile ist der Faktor auf '
        f'den heutigen Free Cashflow. Einzelne Treiber zu testen unterschaetzt, was '
        f'der Kurs verlangt, wenn beide gestreckt sind.</div>'
        f'<table class="va-tbl"><thead><tr><th>Cash-Basis \\ Wachstum</th>{kopf}</tr>'
        f'</thead><tbody>{"".join(rows)}</tbody></table></div>')


def szenario_tabelle(matrix: Optional[dict], labels: Optional[Dict[str, str]] = None,
                     waehrung: str = "USD") -> None:
    if not matrix:
        return
    labels = labels or {}
    body = []
    eintraege = list(matrix["methoden"].items()) + [("__blend__", matrix["blend"])]
    if matrix.get("blend_konsistent"):
        eintraege.append(("__konsistent__", matrix["blend_konsistent"]))
    preis = matrix["preis"]
    for k, zeile in eintraege:
        blend = k in ("__blend__", "__konsistent__")
        if k == "__blend__":
            name = "Geblendeter Fair Value"
        elif k == "__konsistent__":
            gem = ", ".join(labels.get(x, x) for x in matrix.get("gemeinsame_methoden", []))
            name = f"... nur gemeinsame Methoden ({gem})"
        else:
            name = labels.get(k, k)
        zellen = []
        for sz in ("bear", "base", "bull"):
            v = zeile.get(sz)
            if not v:
                zellen.append(f'<td class="r" style="color:{C["muted"]};">n/a</td>')
                continue
            up = (v - preis) / preis * 100 if preis else 0.0
            f = C["green"] if up >= 0 else C["red"]
            zellen.append(f'<td class="r va-num"><b>{de(v, 2)}</b>'
                          f'<span class="note" style="color:{f};">{up:+.0f} %</span></td>')
        style = f' style="background:{C["panel2"]};font-weight:700;"' if blend else ""
        body.append(f'<tr{style}><td class="name">{_e(name)}</td>'
                    f'{"".join(zellen)}</tr>')

    t = matrix.get("treiber") or {}
    fuss = (f'Treiber: Wachstum \u00b1{t.get("wachstum_pp", "?")} Pp., operative '
            f'Ausfuehrung \u00b1{t.get("operativ_pct", "?")} %, Bewertungsniveau '
            f'\u00b1{t.get("bewertung_pct", "?")} % und Beta \u00b1{t.get("beta_pp", "?")} '
            f'(sekundaer, auf {t.get("daempfung", 0.5):.0%} gedaempft). Das Analystenziel '
            f'bleibt in allen Szenarien unveraendert.')

    warn = "".join(f'<div class="va-note">{_e(w)}</div>'
                   for w in (matrix.get("warnungen") or []))
    pos = ""
    if matrix.get("kurs_ausserhalb"):
        pos = (f'<div class="va-note">Der Kurs liegt '
               f'{_e(matrix["kurs_ausserhalb"])} - selbst der guenstigste Fall '
               f'erklaert ihn nicht.</div>')

    _md(f'<div class="va-card"><table class="va-tbl"><thead><tr><th>Methode</th>'
        f'<th class="r">Bear</th><th class="r">Base</th><th class="r">Bull</th></tr>'
        f'</thead><tbody>{"".join(body)}</tbody></table>'
        f'{pos}{warn}'
        f'<div class="sub" style="margin:10px 0 0;">{_e(fuss)}</div></div>')


def perzentil_kacheln(bericht: dict) -> None:
    kacheln = []
    for key, titel in (("kgv", "KGV"), ("ev_ebitda", "EV/EBITDA")):
        b = bericht.get(key)
        if not b or not b.get("perzentil"):
            continue
        p = b["perzentil"]
        tp = p["teuer_pct"]
        f = C["red"] if tp >= 70 else (C["green"] if tp <= 30 else C["amber"])
        chips = [f'<span>Median {de(p["median"], 1)}</span>',
                 f'<span>P25/P75 {de(p["p25"], 1)} / {de(p["p75"], 1)}</span>',
                 f'<span>{p["n"]} Jahre</span>']
        if b.get("rueckkehrwert"):
            chips.insert(0, f'<span>Rueckkehrwert {de(b["rueckkehrwert"], 0)}</span>')
        kacheln.append(
            f'<div class="va-tile"><div class="big va-num" style="color:{f};">'
            f'{tp:.0f}.</div><div class="cap">Perzentil \u00b7 {_e(titel)}</div>'
            f'<div class="scale"><i style="left:{max(0, min(100, tp)):.1f}%;'
            f'background:{f};"></i></div>'
            f'<div class="chips">{"".join(chips)}</div></div>')
    if kacheln:
        _md(f'<div class="va-tiles">{"".join(kacheln)}</div>')

    u = bericht.get("urteil") or {}
    urteil_box(titel=f'Historien-Urteil: {u.get("label", "?")}',
               text=u.get("text", ""), ton=u.get("ton", "grau"),
               chip=(f'{u["teuer_pct"]:.0f}. Perzentil'
                     if u.get("teuer_pct") is not None else ""))


def sterne_karte(guete: dict, blend: Optional[dict] = None) -> None:
    an = "\u2605" * guete["sterne"]
    aus = f'<i>{"\u2605" * (5 - guete["sterne"])}</i>'
    f = _farbe(guete.get("ton", "grau"))
    bias = {"optimistisch": "Konsens liegt im Schnitt zu hoch",
            "konservativ": "Konsens wird regelmaessig uebertroffen",
            "neutral": "kein systematischer Verzerrungseffekt"}.get(
        guete.get("bias"), "keine Daten")

    rows = [
        ("Trefferquote (Beats)", pct(guete.get("trefferquote"), 0)),
        ("Mittlere Abweichung", pct(guete.get("mittlere_abweichung"), 1, vz=True)),
        ("Median |Abweichung|", pct(guete.get("median_abweichung"), 1)),
        ("Daraus abgeleitetes Konsensgewicht", pct(guete.get("konsens_gewicht"), 0)),
    ]
    if blend and blend.get("trend"):
        rows.append(("Konsens / Trend / geblendet",
                     f'{de(blend.get("konsens"), 2)} \u00b7 {de(blend["trend"], 2)} '
                     f'\u00b7 <b>{de(blend["eps"], 2)}</b>'))
    liste = "".join(f'<div class="va-r"><span class="k">{_e(k)}</span>'
                    f'<span class="v va-num">{v}</span></div>' for k, v in rows)

    _md(f'<div class="va-card"><div class="va-split">'
        f'  <div><h4>Schaetzguete des Konsens</h4>'
        f'    <div class="sub">{guete.get("n", 0)} Quartale ausgewertet \u00b7 '
        f'{_e(bias)}</div>'
        f'    <div class="va-stars">{an}{aus}</div>'
        f'    <div style="font-size:13px;color:{f};font-weight:700;margin-top:6px;">'
        f'{_e(guete.get("label", ""))}</div></div>'
        f'  <div><div class="va-list">{liste}</div></div>'
        f'</div></div>')


def sparkline(werte: Sequence[float], farbe: Optional[str] = None,
              breite: int = 150, hoehe: int = 30) -> str:
    """Winziger Verlauf als SVG. Gibt HTML zurueck, rendert nicht selbst.

    Eine Prozentangabe sagt, DASS sich etwas geaendert hat. Der Verlauf sagt,
    ob es eine Wende oder eine Fortsetzung ist - bei Eaton war genau das der
    Punkt: Umsatz weiter steigend, Nettoergebnis bereits drehend. In einer
    Tabelle nebeneinander uebersieht man das.
    """
    xs = [float(v) for v in (werte or [])
          if v is not None and isinstance(v, (int, float))]
    if len(xs) < 3:
        return ""
    lo, hi = min(xs), max(xs)
    spanne = (hi - lo) or (abs(hi) or 1.0)
    n = len(xs)
    farbe = farbe or (C["green"] if xs[-1] >= xs[0] else C["red"])

    pkt = []
    for i, v in enumerate(xs):
        x = i / (n - 1) * (breite - 2) + 1
        y = hoehe - 2 - (v - lo) / spanne * (hoehe - 6)
        pkt.append(f"{x:.1f},{y:.1f}")
    linie = " ".join(pkt)
    flaeche = f"1,{hoehe - 1} {linie} {breite - 1},{hoehe - 1}"
    lx, ly = pkt[-1].split(",")

    return (
        f'<svg viewBox="0 0 {breite} {hoehe}" width="100%" height="{hoehe}" '
        f'preserveAspectRatio="none" style="display:block;margin-top:8px;">'
        f'<polygon points="{flaeche}" fill="{farbe}" opacity="0.13"/>'
        f'<polyline points="{linie}" fill="none" stroke="{farbe}" '
        f'stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{lx}" cy="{ly}" r="2.2" fill="{farbe}"/>'
        f'</svg>')


def kennzahl_kacheln(items: Sequence[Dict]) -> None:
    """Kennzahlen-Kacheln mit Verlauf, Vorjahresdelta und 3J/5J/10J-Chips.

    items: {label, value, delta, chips:[(text, wert)], reihe:[...],
            negative:bool}
      value    fertig formatierte Grosszahl (String)
      delta    Veraenderung zum Vorjahr als Dezimalzahl, optional
      reihe    Jahreswerte aeltester zuerst, fuer die Sparkline
    """
    tiles = []
    for it in items:
        d = it.get("delta")
        if d is None:
            dl = ""
        else:
            col, soft = ((C["green"], C["gruen_weich"]) if d >= 0
                         else (C["red"], C["rot_weich"]))
            dl = (f'<span class="va-delta" style="background:{soft};color:{col};">'
                  f'{d * 100:+.0f} %</span>')
        chips = "".join(
            f'<span>{_e(c)} <b style="color:{C["green"] if v >= 0 else C["red"]};">'
            f'{v * 100:+.0f} %</b></span>' for c, v in (it.get("chips") or []))
        neg = it.get("negative")
        spark = sparkline(it.get("reihe") or [], C["red"] if neg else None)
        farbe = C["red"] if neg else C["cyan"]
        tiles.append(
            f'<div class="va-tile">{dl}'
            f'<div class="big va-num" style="color:{farbe};">{_e(it["value"])}</div>'
            f'<div class="cap">{_e(it["label"])}</div>'
            f'{spark}<div class="chips">{chips}</div></div>')
    _md(f'<div class="va-tiles">{"".join(tiles)}</div>')


def news_karte(eintraege: Sequence[Dict], kopfzeile: str = "",
               sichtbar: int = 5) -> None:
    """Meldungen als zweispaltige Karte statt als Liste im Aufklapper.

    eintraege: {titel, quelle, datum, url}
    Die Kopfzeile fasst das Gesamtbild - zwoelf Schlagzeilen beantworten
    nicht, ob gerade etwas los ist.
    """
    if not eintraege:
        return
    zeilen = []
    for n in eintraege[:sichtbar]:
        titel = _e(str(n.get("titel") or "").strip())
        if not titel:
            continue
        quelle = _e(str(n.get("quelle") or "").strip())
        datum = _e(str(n.get("datum") or "")[:10])
        url = n.get("url")
        inhalt = (f'<a href="{_e(str(url))}" target="_blank" rel="noopener" '
                  f'style="color:{C["fg"]};text-decoration:none;">{titel}</a>'
                  if url else titel)
        zeilen.append(
            f'<div style="display:grid;grid-template-columns:92px 1fr;gap:12px;'
            f'padding:10px 0;border-bottom:1px solid {C["line"]};">'
            f'<div style="font-size:11px;color:{C["muted"]};line-height:1.5;">'
            f'{datum}<br><span style="color:{C["muted"]};">{quelle}</span></div>'
            f'<div style="font-size:13px;line-height:1.5;color:{C["fg"]};">'
            f'{inhalt}</div></div>')
    if not zeilen:
        return
    zeilen[-1] = zeilen[-1].replace(f'border-bottom:1px solid {C["line"]};', "")
    kopf = (f'<div class="sub" style="margin-bottom:2px;">{_e(kopfzeile)}</div>'
            if kopfzeile else "")
    _md(f'<div class="va-card"><h4>Nachrichten</h4>{kopf}{"".join(zeilen)}</div>')


def hinweise(texte: Sequence[str]) -> None:
    if not texte:
        return
    _md("".join(f'<div class="va-note">{_e(t)}</div>' for t in texte))
