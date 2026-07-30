#!/usr/bin/env python3
"""
roic_v3_uk.py - Klaert, ob UK-Firmen unter v3 sicher freigeschaltet werden
koennen. Prueft die WAEHRUNG von Kurs UND Kennzahlen fuer britische Titel.

Hintergrund: Die UK-Sperre gab es, weil roic frueher Pence-Kurse mit Pfund-
Gewinnen mischte -> KGV x100. v3 liefert jetzt pro Kennzahl ein Feld
'price_currency' und ein Flag 'fx_applied'. Damit koennen wir PRUEFEN statt
raten, ob Kurs und Kennzahl konsistent sind.

Wenn fuer BP.L / SHEL.L die Multiples in derselben Waehrung wie der Kurs
stehen (oder fx_applied=True sauber umrechnet), koennen wir UK freischalten.

AUFRUF (PowerShell):  $env:ROIC_API_KEY="dein_key"; python roic_v3_uk.py
"""
import os


def _key():
    if os.getenv("ROIC_API_KEY"):
        return
    for p in (".streamlit/secrets.toml", "../.streamlit/secrets.toml"):
        if os.path.isfile(p):
            for z in open(p, encoding="utf-8"):
                if z.strip().startswith("ROIC_API_KEY"):
                    os.environ["ROIC_API_KEY"] = \
                        z.split("=", 1)[1].strip().strip('"').strip("'")
                    return


_key()
import roic  # noqa: E402


def _feld(daten, *namen):
    obj = daten
    if isinstance(daten, list):
        obj = daten[0] if daten else {}
    elif isinstance(daten, dict):
        for k in ("data", "results"):
            v = daten.get(k)
            if isinstance(v, list) and v:
                obj = v[0]
                break
    if isinstance(obj, dict):
        for n in namen:
            if n in obj:
                return obj[n]
    return None


print("=" * 64)
print("UK-Freischaltung - Waehrungs-Check fuer britische Titel")
print("=" * 64)

for t in ("BP.L", "SHEL.L", "HSBA.L", "BARC.L", "RR.L"):
    sym = roic._v3(t)
    print(f"\n{t}  ->  {sym}")
    if not sym:
        print("   nicht aufloesbar")
        continue

    prof = roic._get(f"company/profile/{sym}")
    ev = roic._get(f"fundamental/enterprise-value/{sym}")
    mu = roic._get(f"fundamental/multiples/{sym}")
    px = roic._get(f"stock-prices/latest/{sym}")

    print(f"   fundamental_currency (Profil): {_feld(prof, 'fundamental_currency')}")
    print(f"   Kurs:                {_feld(px, 'close')} {_feld(px, 'currency')}")
    print(f"   EV price_currency:   {_feld(ev, 'price_currency')} "
          f"| fx_applied: {_feld(ev, 'fx_applied')}")
    print(f"   Multiples currency:  {_feld(mu, 'currency', 'price_currency')} "
          f"| fx_applied: {_feld(mu, 'fx_applied')}")
    print(f"   KGV (pe_ratio):      {_feld(mu, 'pe_ratio')}")
    print(f"   EV/EBITDA:           {_feld(mu, 'ev_to_ttm_ebitda')}")
    # Plausibilitaet: ein KGV ueber ~200 riecht nach Pence/Pfund-Mischung
    pe = _feld(mu, "pe_ratio")
    if isinstance(pe, (int, float)) and pe > 200:
        print("   -> VERDACHT: KGV > 200, moegliche Pence/Pfund-Mischung!")
    elif isinstance(pe, (int, float)):
        print("   -> KGV plausibel.")

print("\n" + "=" * 64)
print("Entscheidend: Steht 'Multiples currency' = GBP UND ist das KGV")
print("plausibel (nicht x100)? Dann koennen wir UK sauber freischalten.")
print("Schick mir die Ausgabe - dann baue ich die Freigabe passend ein.")
