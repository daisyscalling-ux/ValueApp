#!/usr/bin/env python3
"""
ticker_pruef.py - Welche Portfolio-Eintraege sind gar nicht abrufbar?

Hintergrund: In deinem Portfolio stehen teils FIRMENNAMEN statt Boersen-
symbolen ("GILEAD SCIENCES" statt "GILD") oder Symbole ohne Boersenkuerzel
("4GLD" statt "4GLD.DE"). Solche Positionen liefern keinen Kurs - sie
fehlen damit in Bewertung, Portfolioanalyse UND im Indexvergleich, ohne
dass es auffaellt.

Dieses Skript listet die kaputten Eintraege und schlaegt Symbole vor.

AUFRUF:
    python ticker_pruef.py
"""
import providers
import store

# Haeufige Faelle. Bewusst KEINE automatische Korrektur - ein falsch
# geratenes Symbol waere schlimmer als eine sichtbare Luecke.
VORSCHLAEGE = {
    "NETEASE (ADR)":    ["NTES"],
    "NETEASE":          ["NTES"],
    "SUZUKI MOTOR":     ["7269.T"],
    "GILEAD SCIENCES":  ["GILD"],
    "GILEAD":           ["GILD"],
    "BOOKING HOLDINGS": ["BKNG"],
    "BOOKING":          ["BKNG"],
    "ALLIANZ":          ["ALV.DE"],
    "SHA0":             ["SHA.DE", "SHA0.DE"],
    "VWRL":             ["VWRL.AS", "VWRL.L"],
    "4GLD":             ["4GLD.DE"],
    "SAP":              ["SAP.DE", "SAP"],
    "SIEMENS":          ["SIE.DE"],
    "BASF":             ["BAS.DE"],
    "BAYER":            ["BAYN.DE"],
    "MERCEDES":         ["MBG.DE"],
    "VOLKSWAGEN":       ["VOW3.DE"],
    "NESTLE":           ["NESN.SW"],
    "NOVARTIS":         ["NOVN.SW"],
    "ASML":             ["ASML.AS", "ASML"],
    "LVMH":             ["MC.PA"],
    "TOTALENERGIES":    ["TTE.PA"],
    "SHELL":            ["SHEL.L", "SHEL"],
}


def pruefe(t):
    """Liefert (ok, kurs)."""
    try:
        f = providers.get_fundamentals(t, deep=False)
        if f and f.get("price"):
            return True, f["price"]
    except Exception:
        pass
    return False, None


def main():
    tk = []
    try:
        for name, rows in (store.load_all() or {}).items():
            for r in rows or []:
                t = str(r.get("ticker") or "").strip()
                if t:
                    tk.append((t, name))
    except Exception as e:
        print(f"Portfolio nicht ladbar: {e}")
        return
    if not tk:
        print("Kein Portfolio gefunden.")
        return

    print("=" * 66)
    print(f"TICKER-PRUEFUNG  ({len(tk)} Positionen)")
    print("=" * 66)

    kaputt, ok = [], []
    for t, depot in tk:
        gut, kurs = pruefe(t)
        (ok if gut else kaputt).append((t, depot, kurs))

    print(f"\n  abrufbar:      {len(ok):3}")
    print(f"  NICHT abrufbar:{len(kaputt):3}")

    if kaputt:
        print(f"\n{'-'*66}")
        print("KAPUTTE EINTRAEGE - diese Positionen fehlen ueberall:")
        print(f"{'-'*66}")
        for t, depot, _ in kaputt:
            vors = VORSCHLAEGE.get(t.upper(), [])
            if not vors:
                # Symbol ohne Suffix? Deutsche Boerse ist der haeufigste Fall.
                if "." not in t and len(t) <= 5 and t.isalnum():
                    vors = [f"{t}.DE", f"{t}.AS", f"{t}.L"]
            zusatz = ""
            if vors:
                geprueft = [v for v in vors if pruefe(v)[0]]
                zusatz = ("  ->  " + ", ".join(geprueft) if geprueft
                          else "  ->  Vorschlaege gepruefte: keiner passt")
            print(f"  [{depot}] {t:20}{zusatz}")

    if ok:
        print(f"\n{'-'*66}")
        print("IN ORDNUNG:")
        print(f"{'-'*66}")
        for t, depot, kurs in ok:
            print(f"  [{depot}] {t:20} Kurs {kurs}")

    print(f"\n{'='*66}")
    print("WAS TUN:")
    print("Korrigiere die Symbole im Portfolio-Editor der App. Solange ein")
    print("Eintrag keinen Kurs liefert, fehlt er in der Bewertung, in der")
    print("Portfolioanalyse und im Indexvergleich - der Vergleich rechnet")
    print("dann nur mit einem Teil deines Depots.")


if __name__ == "__main__":
    main()
