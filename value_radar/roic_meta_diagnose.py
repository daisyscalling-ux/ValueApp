#!/usr/bin/env python3
"""
roic_meta_diagnose.py - Warum findet der Nachtlauf Metas Call vom 29.07 nicht?

Testet gezielt fuer META (und weitere Titel, die diese Woche gemeldet haben)
die komplette Kette und zeigt, was WIRKLICH zurueckkommt.

AUFRUF (PowerShell im value_radar-Ordner):
    $env:ROIC_API_KEY="dein_key"; python roic_meta_diagnose.py
"""
import datetime as dt

TITEL = ["META", "GOOGL", "MSFT", "V", "MA"]


def main():
    try:
        import roic
    except Exception as e:
        print(f"Import fehlgeschlagen: {e}")
        return

    heute = dt.date.today()
    print(f"Heute: {heute}\n" + "=" * 66)

    for t in TITEL:
        print(f"\n### {t}")
        # 1) Was liefert transcript_liste roh?
        try:
            liste = roic.transcript_liste(t, limit=5)
        except Exception as e:
            print(f"  transcript_liste FEHLER: {e}")
            continue
        if not liste:
            print("  transcript_liste: LEER (kein Call gefunden!)")
            continue
        print(f"  transcript_liste liefert {len(liste)} Eintraege:")
        for z in liste[:5]:
            d = z.get("datum")
            tage_her = None
            if d:
                try:
                    tage_her = (heute - dt.date.fromisoformat(d[:10])).days
                except Exception:
                    pass
            print(f"    {z.get('jahr')} Q{z.get('quartal')} - {d} "
                  f"({tage_her} Tage her)")

        # 2) Ist der neueste 'neu' (<=21 Tage)?
        neuester = liste[0]
        d = str(neuester.get("datum") or "")[:10]
        if d:
            try:
                tag = dt.date.fromisoformat(d)
                grenze = heute - dt.timedelta(days=21)
                ist_neu = tag >= grenze
                print(f"  -> neuester Call {d}: ist_neu (<=21 Tage)? {ist_neu}")
                if not ist_neu:
                    print(f"     ({(heute-tag).days} Tage her - AUSSERHALB 21-Tage-Fenster)")
            except Exception as e:
                print(f"     Datum nicht parsbar: {e}")

    # 3) Was macht neue_transkripte fuer genau diese Titel?
    print("\n" + "=" * 66)
    print("neue_transkripte fuer genau diese 5 Titel (tage=21):")
    try:
        neu = roic.neue_transkripte(TITEL, tage=21, deckel=10)
        print(f"Ergebnis: {len(neu)} Calls")
        for r in neu:
            print(f"  {r['ticker']}: {r['datum']} ({r['tage_her']} Tage), "
                  f"neu={r.get('ist_neu')}")
        aktuell = [r for r in neu if r.get("ist_neu")]
        print(f"\nDavon 'aktuell' (ist_neu=True): {len(aktuell)}")
        if not aktuell:
            print("-> PROBLEM: keiner als aktuell markiert, obwohl META am 29.07 war!")
    except Exception as e:
        import traceback
        print(f"FEHLER: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
