"""
screener2_lauf.py - den neuen Screener von der Kommandozeile ausprobieren.

    python3 screener2_lauf.py                          # Standardlauf
    python3 screener2_lauf.py --tief 40                # mehr Titel tief pruefen
    python3 screener2_lauf.py --profil momentum
    python3 screener2_lauf.py --regionen us de
    python3 screener2_lauf.py --parallel 1             # nacheinander (langsam)
    python3 screener2_lauf.py --kontrolle              # Gates aus: was waere oben?
    python3 screener2_lauf.py --vergleich              # gegen den alten Filter
    python3 screener2_lauf.py --ticker AAPL MSFT NVDA  # feste Liste statt Scan

WARUM DAS DAUERT
    Stufe 3 laedt jeden ueberlebenden Titel mit deep=True - also roic-Bundle,
    Jahresabschluesse fuer die Forensik, Kurshistorie. Das sind mehrere Abrufe
    je Titel. Rechne mit rund 2-5 Sekunden pro Titel; --tief 20 dauert also
    etwa eine Minute, --tief 80 gut fuenf.

    Genau das ist der Preis dafuer, dass im Screener dieselben Zahlen stehen
    wie in der Einzelanalyse. Bisher standen dort andere, und das ist der
    Fehler, den wir abstellen.

VOR DEM ERSTEN LAUF
    Aus dem Projektordner starten, damit .streamlit/secrets.toml gefunden wird:
        cd C:\\Users\\Patrick\\Desktop\\value_radar
        python screener2_lauf.py --tief 15
"""

from __future__ import annotations

import sys
import time

import kandidat as kd
import providers
import screener2 as s2


def flach_laden(t: str) -> dict:
    """Stufe 2: billiger Abruf. Bewusst deep=False."""
    fd = providers.get_fundamentals(t, deep=False) or {}
    if fd.get("price"):
        try:
            fd["_fx"] = providers.get_fx_to_eur(fd.get("currency") or "USD") or 1.0
        except Exception:
            fd["_fx"] = 1.0
    return fd


def _schluessel_pruefen() -> None:
    """Warum ist roic aus? Die Antwort ist fast immer der Pfad zu secrets.toml.

    Ohne roic gibt es keine Jahresabschluesse - also keine Forensik, keine
    Bewertungshistorie, keine Cash-Conversion. Der Screener laeuft dann zwar,
    misst aber etwas anderes als die Einzelanalyse.
    """
    import os

    import config

    quelle = (config.schluessel_quelle("ROIC_API_KEY")
              if hasattr(config, "schluessel_quelle") else "?")
    aktiv = bool(getattr(config, "ROIC_API_KEY", ""))
    print(f"  ROIC-Schluessel: {'gesetzt' if aktiv else 'FEHLT'} "
          f"(Quelle: {quelle})")
    if aktiv:
        return

    print("\n  Ohne roic fehlen Forensik, Bewertungshistorie und")
    print("  Cash-Conversion. Wo gesucht wurde:")
    hier = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(hier, ".streamlit", "secrets.toml"),
              os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
              os.path.expanduser("~/.streamlit/secrets.toml")):
        print(f"     {'gefunden' if os.path.exists(p) else 'nicht da'}  {p}")
    print(f"  Arbeitsverzeichnis: {os.getcwd()}")
    print("  Liegt die Datei woanders, hilft eine Umgebungsvariable:")
    print('     $env:ROIC_API_KEY="..."   (PowerShell, gilt fuer die Sitzung)')
    print()


def universum_holen(regionen, max_titel: int):
    import market_screener as ms
    print(f"  Hole Universum fuer {regionen} ...")
    uni, quelle = ms.get_universe(list(regionen), 0.5, max_titel * 3)
    uni = ms.collapse_listings(uni)[:max_titel * 3]
    print(f"  Quelle: {quelle} \u00b7 {len(uni)} Ticker")
    return uni


def alter_filter(universum, vorlage: str = "value_quality") -> list:
    """Was haette der bisherige Screener geliefert?

    Nachbau des Dashboard-Ablaufs: flache Daten, fair_value darauf, Vorlage
    pruefen. Nicht schoener gemacht als er ist - genau das ist der Punkt des
    Vergleichs.
    """
    import screener_presets as sp
    import valuation

    if vorlage not in sp.PRESETS:
        vorlage = list(sp.PRESETS)[0]
    treffer = []
    for t in universum:
        fd = flach_laden(t)
        if not fd.get("price"):
            continue
        try:
            ex = providers.get_screen_extras(t) or {}
            fv = valuation.fair_value(fd, None, valuation.classify_playbook(fd))
            if sp.evaluate(vorlage, fd, ex, fv).get("passed"):
                treffer.append(t)
        except Exception:
            continue
    return treffer


def main() -> int:
    args = sys.argv[1:]

    def opt(name, standard=None, mehrere=False):
        if name not in args:
            return standard
        i = args.index(name)
        werte = []
        for a in args[i + 1:]:
            if a.startswith("--"):
                break
            werte.append(a)
        if not werte:
            return standard
        return werte if mehrere else werte[0]

    profil = opt("--profil", "value")
    parallel = int(opt("--parallel", "4"))
    tief = int(opt("--tief", "20"))
    regionen = opt("--regionen", ["us", "de"], mehrere=True)
    feste = opt("--ticker", None, mehrere=True)

    print(f"\n{'=' * 72}\nSCREENER 2 \u00b7 Profil '{profil}' \u00b7 max. {tief} tief"
          f" \u00b7 {parallel} parallel\n{'=' * 72}")

    if not kd.__dict__.get("pruefe"):
        print("  kandidat.py nicht geladen.")
        return 1
    _schluessel_pruefen()

    universum = [t.upper() for t in feste] if feste else \
        universum_holen(regionen, tief)
    if not universum:
        print("  Kein Universum erhalten.")
        return 1

    start = time.time()
    zuletzt = [0.0]

    def fortschritt(anteil, text):
        # Nicht bei jedem Titel schreiben - das Protokoll wird sonst unlesbar.
        if anteil - zuletzt[0] >= 0.05 or anteil >= 1.0:
            zuletzt[0] = anteil
            print(f"    {anteil * 100:5.0f} %  {text}")

    print("\n  Lauf startet ...")
    kontrolle = "--kontrolle" in args
    erg = s2.lauf(universum, flach_laden, profil=profil, max_tief=tief,
                  fortschritt=fortschritt, parallel=parallel,
                  gates_aus=kontrolle)
    dauer = time.time() - start

    print(f"\n{'=' * 72}")
    for zeile in s2.bericht(erg):
        print("  " + zeile)
    print(f"  Dauer: {dauer:.0f} s ({dauer / max(erg.trichter.tief_geprueft, 1):.1f} s je tief geprueftem Titel)")

    if kontrolle:
        print(f"\n{'=' * 72}\nKONTROLLLAUF \u2013 Gates protokolliert, nicht "
              f"angewendet\n{'=' * 72}")
        print("  Alle Titel nach Score. Die letzte Spalte zeigt, woran der "
              "Titel im\n  Normalbetrieb gescheitert waere.\n")
        print(f"    {'Ticker':9s} {'Score':>6s} {'Upside':>8s} {'Sektor':22s} "
              f"Waere ausgeschieden an")
        for z in erg.treffer[:20]:
            gruende = z.get("waere_raus") or []
            kurz = "; ".join(g.split("(")[0].strip() for g in gruende)[:44] or "-"
            print(f"    {z['ticker']:9s} {z['score']:6.1f} "
                  f"{(z['upside'] or 0):+7.1f} % {(z['sektor'] or '?')[:22]:22s} "
                  f"{kurz}")
        _sektoren = {}
        for z in erg.treffer[:10]:
            _s = z.get("sektor") or "?"
            _sektoren[_s] = _sektoren.get(_s, 0) + 1
        print(f"\n  Sektoren der besten zehn: "
              + ", ".join(f"{k} ({v})" for k, v in
                          sorted(_sektoren.items(), key=lambda x: -x[1])))
        print("  Fuehren hier dieselben Zykliker und Banken, liegt die "
              "Konzentration am Markt.\n  Stehen Qualitaetstitel oben, liegt "
              "sie am Profil.")
        return 0

    if erg.treffer:
        print(f"\n  TREFFER ({len(erg.treffer)}):")
        print(f"    {'Ticker':8s} {'Score':>6s} {'Upside':>8s} {'Datenbasis':>14s} "
              f"{'Basis':>6s}  Name")
        for z in erg.treffer[:25]:
            print(f"    {z['ticker']:8s} {z['score']:6.1f} "
                  f"{(z['upside'] or 0):+7.1f} % {z['datenstufe']:>14s} "
                  f"{(z.get('score_basis') or 0) * 100:5.0f} %  {z['name'][:28]}")
        print("\n  Aufschluesselung des besten Treffers:")
        b = erg.treffer[0]
        for n, v in (b.get("teile") or {}).items():
            print(f"    {n:20s} {v:5.1f}")
        if b.get("score_fehlend"):
            print(f"    nicht belegt: {', '.join(b['score_fehlend'])}")
    else:
        print("\n  KEIN TREFFER. Das ist eine Aussage, kein Fehler - der")
        print("  Trichter oben zeigt, woran es lag.")

    if erg.ausgeschlossen:
        print(f"\n  KNAPP GESCHEITERT (erste 10 von {len(erg.ausgeschlossen)}):")
        for z in erg.ausgeschlossen[:10]:
            print(f"    {z['ticker']:8s} {'; '.join(z['gruende'])[:70]}")

    if "--vergleich" in args:
        print(f"\n{'=' * 72}\nGEGENPROBE gegen den bisherigen Filter\n{'=' * 72}")
        print("  Laeuft den alten Weg auf demselben Universum ...")
        alt = alter_filter(universum[:tief])
        v = s2.vergleich(erg, alt)
        print(f"  alt {v['alt_n']} Treffer  \u00b7  neu {v['neu_n']} Treffer")
        print(f"  in beiden: {', '.join(v['in_beiden']) or '-'}")
        print(f"  nur neu  : {', '.join(v['nur_neu']) or '-'}")
        print(f"  nur alt  : {', '.join(v['nur_alt']) or '-'}")
        if v["warum_weg"]:
            print("  Warum die alten Treffer wegfallen:")
            for t, g in v["warum_weg"].items():
                print(f"    {t:8s} {'; '.join(g)[:70]}")
        print("\n  Das ist die Messung: Fallen sinnvolle Titel weg oder Schrott?")

    return 0


if __name__ == "__main__":
    sys.exit(main())
