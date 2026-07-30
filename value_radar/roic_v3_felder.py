#!/usr/bin/env python3
"""
roic_v3_felder.py - Zeigt die ECHTEN v3-Feldnamen der Fundamental-Endpunkte.

Problem: Nach dem v3-Umbau kommen Kurs und ISIN an, aber der Composite ist
None - die Bewertung scheitert, weil erwartete Felder (revenue, eps, margin,
market_cap ...) unter v3 offenbar anders heissen.

Dieses Skript ruft die Endpunkte fuer AAPL ab und druckt ALLE Feldnamen +
Beispielwerte. Damit ordne ich die v3-Namen den vom Score erwarteten Feldern
zu und korrigiere roic.py gezielt - ohne zu raten.

AUFRUF (PowerShell):  $env:ROIC_API_KEY="dein_key"; python roic_v3_felder.py
"""
import json
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


def zeig(titel, daten):
    print("\n" + "=" * 60)
    print(titel)
    print("=" * 60)
    obj = daten
    if isinstance(daten, list):
        obj = daten[0] if daten else {}
    elif isinstance(daten, dict):
        for k in ("data", "results", "rows"):
            v = daten.get(k)
            if isinstance(v, list) and v:
                obj = v[0]
                break
    if not isinstance(obj, dict):
        print("  (kein Objekt)")
        return
    # Alle Felder mit Werten, alphabetisch, kompakt
    for k in sorted(obj.keys()):
        v = obj[k]
        if isinstance(v, (int, float, str)) and str(v)[:40]:
            print(f"  {k:42} = {str(v)[:32]}")


ex = "NASDAQ:AAPL"
print(f"v3-Feldnamen fuer {ex}")

# Genau die Endpunkte, aus denen das Bundle seine Score-Felder zieht
zeig("PROFIL (Name/ISIN/Sektor/currency)",
     roic._get(f"company/profile/{ex}"))
zeig("ENTERPRISE-VALUE (market_cap, ttm_ebitda, revenue ...)",
     roic._get(f"fundamental/enterprise-value/{ex}"))
zeig("RATIOS/PROFITABILITY (margins, roe, roic ...)",
     roic._get(f"fundamental/ratios/profitability/{ex}"))
zeig("MULTIPLES (KGV, KUV, KBV, EV/EBITDA ...)",
     roic._get(f"fundamental/multiples/{ex}"))
zeig("PER-SHARE (eps, book value ...)",
     roic._get(f"fundamental/per-share/{ex}"))
zeig("INCOME-STATEMENT (revenue, ebit, eps ...)",
     roic._get(f"fundamental/income-statement/{ex}",
               {"period": "annual", "limit": 1}))

print("\n" + "=" * 60)
print("Schick mir diese komplette Ausgabe. Daraus lese ich die echten")
print("v3-Feldnamen ab und korrigiere die Zuordnung in roic.py - dann")
print("kommt der Composite (und damit die Kaufkandidaten) zurueck.")
