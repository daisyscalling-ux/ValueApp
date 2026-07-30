#!/usr/bin/env python3
"""
etf_check.py — Liefern roic/Providers fuer 4GLD (Xetra-Gold) und VWRL
(FTSE All-World ETF) einen Upside und einen Composite Score?

Hintergrund: Diese beiden Titel flogen frueher aus dem Portfolio, weil die
Bewertung leer blieb. Die Frage ist, ob die roic-Daten das jetzt aendern.

Wichtig vorab - der konzeptionelle Haken:
    Beide sind KEINE Einzelunternehmen.
      - Xetra-Gold ist physisches Gold: kein Umsatz, keine Marge, kein
        Gewinn, kein KGV. Ein "Fair Value" ist der Goldpreis selbst.
      - VWRL ist ein Korb aus ~3.600 Aktien, kein einzelnes Income
        Statement, kein ROE, kein DCF.
    roic.ai liefert Fundamentaldaten VON FIRMEN. Fuer ein Gold-ETC oder
    einen breiten ETF gibt es diese nicht. Ein Composite Score und ein
    Upside sind fuer solche Instrumente also methodisch gar nicht definiert.

Dieses Skript BEHAUPTET das nicht nur, sondern PRUEFT es: Es geht die ganze
Kette durch (roic-Abdeckung -> Profil -> Fundamentaldaten -> Fair Value ->
Score -> Upside) und zeigt, wo und warum etwas fehlt.

AUFRUF (im Ordner value_radar, mit gesetztem Schluessel):
    $env:ROIC_API_KEY="dein_key"       # PowerShell
    python etf_check.py

Danach die Ausgabe an mich schicken - dann sehen wir schwarz auf weiss,
ob sich ein Score bauen laesst oder ob die Titel besser OHNE Bewertung
(nur als Position mit Wert) ins Portfolio gehoeren.
"""
import os
import sys


def _schluessel_finden():
    """ROIC-Schluessel aus denselben Quellen holen wie die App.

    Die App laeuft in Streamlit, das die Secrets als Umgebungsvariablen
    bereitstellt. Ein Konsolen-Skript sieht diese NICHT - deshalb wird der
    Schluessel hier aktiv gesucht:
      1) Umgebungsvariable ROIC_API_KEY (falls lokal gesetzt)
      2) .streamlit/secrets.toml  (der uebliche Ort, auch auf Streamlit Cloud)
      3) zur Not interaktive Eingabe
    Gefundener Schluessel wird als Umgebungsvariable gesetzt, BEVOR roic/config
    importiert werden - die lesen ihn dann ganz normal ueber os.getenv.
    """
    if os.getenv("ROIC_API_KEY"):
        return "Umgebungsvariable"

    # secrets.toml an den ueblichen Stellen suchen (Skriptordner + uebergeordnet)
    hier = os.path.dirname(os.path.abspath(__file__))
    kandidaten = [
        os.path.join(hier, ".streamlit", "secrets.toml"),
        os.path.join(hier, "..", ".streamlit", "secrets.toml"),
        os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
        os.path.expanduser("~/.streamlit/secrets.toml"),
    ]
    for pfad in kandidaten:
        if not os.path.isfile(pfad):
            continue
        try:
            # tomllib ab Python 3.11, sonst simple Zeilensuche
            try:
                import tomllib
                with open(pfad, "rb") as fh:
                    daten = tomllib.load(fh)
                key = daten.get("ROIC_API_KEY")
            except Exception:
                key = None
                with open(pfad, encoding="utf-8") as fh:
                    for zeile in fh:
                        z = zeile.strip()
                        if z.startswith("ROIC_API_KEY"):
                            key = z.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            if key:
                os.environ["ROIC_API_KEY"] = key
                return f"secrets.toml ({pfad})"
        except Exception:
            pass

    # Letzter Ausweg: interaktiv nachfragen (Eingabe wird nicht gespeichert)
    try:
        key = input("ROIC_API_KEY eingeben (oder Enter zum Abbrechen): ").strip()
    except (EOFError, KeyboardInterrupt):
        key = ""
    if key:
        os.environ["ROIC_API_KEY"] = key
        return "interaktive Eingabe"
    return None


_quelle = _schluessel_finden()
if _quelle:
    print(f"ROIC-Schluessel gefunden ueber: {_quelle}\n")
else:
    print("KEIN ROIC-Schluessel gefunden.\n"
          "  Entweder als Umgebungsvariable setzen:\n"
          "    PowerShell:  $env:ROIC_API_KEY=\"dein_key\"\n"
          "    WSL/Linux:   export ROIC_API_KEY=\"dein_key\"\n"
          "  oder das Skript aus dem Ordner starten, in dem\n"
          "  .streamlit/secrets.toml liegt.\n")


# Kandidaten je Titel - mehrere Boersenschreibweisen, weil nicht jede
# Notierung ueberall gefuehrt wird. Die erste, die Daten liefert, gewinnt.
TITEL = {
    "Xetra-Gold (physisches Gold)": ["4GLD.DE", "4GLD.F", "4GLD.SG"],
    "Vanguard FTSE All-World": ["VWRL.L", "VWRL.AS", "VWRL.DE", "VWCE.DE"],
}


def _num(x):
    try:
        return float(x)
    except Exception:
        return None


def _zeige(label, wert, einheit=""):
    if wert is None:
        print(f"    {label:26} —")
    else:
        print(f"    {label:26} {wert}{einheit}")


def pruefe_roic(ticker):
    """Was sagt roic direkt zu diesem Ticker?"""
    import roic
    print(f"  roic.ai:")
    if not roic.enabled():
        print("    Kein Schluessel gesetzt (ROIC_API_KEY).")
        return False
    deckt = roic.covers(ticker)
    print(f"    covers()                 {deckt}")
    print(f"    multiples_ok()           {roic.multiples_ok(ticker)}")
    prof = None
    try:
        prof = roic.profile(ticker)
    except Exception as e:
        print(f"    profile() Fehler:        {e}")
    if prof:
        print(f"    profile() Felder:        {sorted(prof.keys())[:10]}")
        for k in ("price", "sector", "industry", "is_adr", "isin"):
            if k in prof:
                _zeige(f"profile.{k}", prof.get(k))
    else:
        print("    profile()                — (nichts zurueck)")
    # Der eigentliche Test: liefert das Fundamentalbuendel etwas?
    try:
        b = roic.bundle_light(ticker) or {}
        gefuellt = {k: v for k, v in b.items()
                    if v is not None and k not in ("price", "currency")}
        if gefuellt:
            print(f"    bundle_light() Felder:   {sorted(gefuellt)[:12]}")
            for k in ("revenue", "ebitda", "eps_trailing", "operating_margin",
                      "roe", "pe_trailing"):
                if k in gefuellt:
                    _zeige(f"  {k}", gefuellt.get(k))
        else:
            print("    bundle_light()           — keine Fundamentaldaten "
                  "(erwartbar bei ETF/ETC)")
        return bool(gefuellt)
    except Exception as e:
        print(f"    bundle_light() Fehler:   {e}")
        return False


def pruefe_kette(ticker):
    """Kommt die volle Pipeline zu Preis, Fair Value, Score, Upside?"""
    import providers
    import scoring
    import valuation
    print(f"  Volle Pipeline:")
    try:
        f = providers.get_fundamentals(ticker, deep=True) or {}
    except Exception as e:
        print(f"    get_fundamentals Fehler: {e}")
        return
    if not f:
        print("    get_fundamentals()       — leer")
        return

    preis = f.get("price")
    _zeige("Preis", preis, f" {f.get('currency', '')}")
    if f.get("_roic"):
        print(f"    Datenquelle              roic aktiv"
              + (f" (FX-Faktor {f.get('_roic_fx')})" if f.get("_roic_fx") else ""))
    # Fuer den Score noetige Bausteine einzeln zeigen
    for k in ("eps_trailing", "revenue", "operating_margin", "roe",
              "pe_trailing", "book_value_ps", "revenue_growth"):
        _zeige(k, f.get(k))

    # Fair Value + Score wie in der Einzelanalyse
    try:
        ep = valuation.classify_playbook(f)
        s = scoring.score_stock(f, None, preset=ep)
        v = valuation.fair_value(f, None, ep)
    except Exception as e:
        print(f"    Score/FairValue Fehler:  {e}")
        return

    comp = s.get("composite") if isinstance(s, dict) else None
    fair = v.get("fair_value") if isinstance(v, dict) else None
    _zeige("Composite Score", comp)
    _zeige("Fair Value", fair, f" {f.get('currency', '')}")
    if fair and preis and preis > 0:
        upside = round((fair / preis - 1) * 100, 1)
        _zeige("Upside", upside, " %")
    else:
        print("    Upside                   — (kein Fair Value oder Preis)")

    # Klartext-Urteil
    print("  Fazit:")
    if comp is None and fair is None:
        print("    Weder Score noch Fair Value - fuer dieses Instrument")
        print("    liefert die Bewertung nichts (kein Firmen-Fundament).")
    elif comp is not None and fair is not None:
        print("    Score UND Fair Value vorhanden - eine Bewertung ist")
        print("    technisch moeglich. ABER bei ETF/ETC kritisch pruefen,")
        print("    ob die Zahlen ueberhaupt sinnvoll sind (s. Kopf des Skripts).")
    else:
        print("    Nur teilweise Daten - Score oder Fair Value fehlt.")
        print("    Fuer eine belastbare Bewertung zu wenig.")


def main():
    for name, kandidaten in TITEL.items():
        print("=" * 66)
        print(name)
        print("=" * 66)
        for t in kandidaten:
            print(f"\n>>> {t}")
            hat_fund = pruefe_roic(t)
            pruefe_kette(t)
            # Wenn eine Schreibweise Fundamentaldaten lieferte, reicht das -
            # die anderen sind nur Ausweichnotierungen.
            if hat_fund:
                print(f"\n  ({t} lieferte Daten - weitere Schreibweisen "
                      "uebersprungen.)")
                break
        print()
    print("=" * 66)
    print("Bitte die komplette Ausgabe an mich schicken.")
    print("Kernfrage: Steht bei einem der Titel ein Composite Score UND")
    print("ein Fair Value? Wenn ja, bauen wir die Bewertung ein. Wenn nein,")
    print("kommen die Titel als reine Positionen (Wert ohne Score) zurueck -")
    print("das ist fuer Gold und einen All-World-ETF ohnehin der ehrlichere Weg.")


if __name__ == "__main__":
    main()
