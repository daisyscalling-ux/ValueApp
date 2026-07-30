#!/usr/bin/env python3
"""
roic_v3_bp.py - Zeigt die ROHEN Suchtreffer fuer BP und RR, damit wir sehen,
warum die Aufloesung LSE:BP / LSE:RR verwirft.

Vermutung: Der LSE-Treffer meldet ein anderes 'listing_country_code' als GB,
oder die Symbol-Basis weicht ab (z.B. 'BP.' oder 'BP/'), oder die Boerse
heisst nicht exakt 'LSE'. Die Ausgabe klaert das.

AUFRUF (PowerShell):  $env:ROIC_API_KEY="dein_key"; python roic_v3_bp.py
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

for basis in ("BP", "RR", "SHEL", "HSBA"):
    print("=" * 60)
    print(f"Suche: {basis}")
    print("=" * 60)
    treffer = roic._such_roh(basis)
    if not treffer:
        print("  (keine Treffer)")
        continue
    # Alle Treffer zeigen, deren Symbol-Basis dem gesuchten entspricht
    # oder die an einer UK-Boerse liegen
    for tr in treffer[:25]:
        sym = tr.get("symbol") or ""
        ex = sym.split(":")[0] if ":" in sym else tr.get("exchange")
        sym_basis = sym.split(":")[-1] if ":" in sym else ""
        land = tr.get("listing_country_code")
        prim = tr.get("is_primary")
        isin = tr.get("isin")
        # nur relevante zeigen: Basis passt oder UK-Boerse
        if sym_basis.upper() == basis or (ex or "").upper() in ("LSE", "IOB"):
            print(f"  symbol={sym:16} exch={str(ex):8} land={str(land):5} "
                  f"primary={str(prim):5} isin={isin}")
    print(f"  ({len(treffer)} Treffer gesamt)")

print("\n" + "=" * 60)
print("Schick mir die Ausgabe. Ich sehe dann, unter welchem Symbol/")
print("Land/Boersennamen BP und RR an der LSE stehen - und passe die")
print("Aufloesung so an, dass sie die UK-Notierung findet.")
