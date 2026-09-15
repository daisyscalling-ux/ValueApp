"""
verlauf.py - Was hat sich bei diesem Titel geaendert, und warum?

Fuehrt je Titel eine kurze Liste der Aenderungen an Composite, Quantum-Score
und Fair Value - mit dem Grund, soweit er sich benennen laesst.

WARUM NICHT EINFACH ALLES SPEICHERN

    Der Zusatzspeicher liegt in einem Google Sheet und fasst rund 1,35 Mio
    Zeichen (30 Zeilen a 45.000). Darin liegen bereits Transkripte,
    Anreicherungen, Firmennamen und Sektormediane.

    Ein Eintrag braucht knapp 90 Zeichen. Gerechnet:

        600 Titel x  8 Eintraege =   432.000 Zeichen   passt
        600 Titel x 20 Eintraege = 1.080.000 Zeichen   zu gross
       2000 Titel x  8 Eintraege = 1.440.000 Zeichen   zu gross

    Deshalb drei Grenzen, die zusammen dafuer sorgen, dass der Verlauf nicht
    ueber den Speicher hinauswaechst:
      1. hoechstens MAX_EINTRAEGE je Titel
      2. hoechstens MAX_TITEL Titel insgesamt - der am laengsten unberuehrte
         faellt heraus
      3. nur bei SPUERBARER Aenderung wird ueberhaupt geschrieben

    Die dritte Grenze ist die wichtigste: Ein Fair Value, der von 100,00 auf
    100,40 wandert, ist keine Aenderung, sondern ein anderer Kursstand. Ihn
    zu notieren wuerde die Liste mit Rauschen fuellen und die echten
    Aenderungen darin begraben.
"""

from __future__ import annotations

__version__ = "2026.09.27"

from datetime import datetime
from typing import Dict, List, Optional

#: Je Titel. Gemessen, nicht geschaetzt: 500 Titel x 6 Eintraege belegten
#: 45,5 % des Zusatzspeichers - zu viel neben Transkripten, Anreicherungen und
#: Sektormedianen. 300 x 5 liegt bei rund 20 %.
MAX_EINTRAEGE = 5

#: Insgesamt. Deutlich mehr als Watchlist und Portfolio, aber weniger als das
#: volle Scan-Universum. Wer haeufiger Aenderungen hat, bleibt drin - wer
#: monatelang unveraendert ist, faellt heraus.
MAX_TITEL = 300

#: Ab wann gilt eine Aenderung als spuerbar?
SCHWELLE = {
    "fair_value": 0.03,     # 3 % - darunter ist es Kursbewegung, keine Neubewertung
    "composite": 3.0,       # Punkte
    "quantum": 3.0,
}


#: Kurze Schluessel im Speicher, sprechende nach aussen.
#:
#: Gemessen bei 500 Titeln x 6 Eintraegen: 246 Zeichen je Eintrag, davon
#: entfallen allein auf die Feldnamen ("composite", "fair_value", "grund" ...)
#: rund 60. Sie wiederholen sich in JEDEM Eintrag - bei 3.000 Eintraegen sind
#: das 180.000 Zeichen nur fuer Bezeichner.
#:
#: Die Uebersetzung passiert an der Schnittstelle: Wer notieren() oder lesen()
#: benutzt, sieht weiterhin die langen Namen.
_KURZ = {"d": "d", "composite": "c", "quantum": "q", "fair_value": "f",
         "was": "w", "grund": "g", "basis": "b"}
_LANG = {v: k for k, v in _KURZ.items()}


def _ein(e: dict) -> dict:
    """nach innen: lange Namen -> kurze"""
    return {_KURZ.get(k, k): v for k, v in e.items()}


def _aus(e: dict) -> dict:
    """nach aussen: kurze Namen -> lange"""
    return {_LANG.get(k, k): v for k, v in (e or {}).items()}


def _jetzt() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _spuerbar(alt: Optional[dict], neu: dict) -> List[str]:
    """Welche Werte haben sich ueber die Schwelle hinaus bewegt?"""
    if not alt:
        return ["erste Erfassung"]
    raus = []
    for feld, schwelle in SCHWELLE.items():
        a, n = alt.get(feld), neu.get(feld)
        if a is None or n is None:
            if (a is None) != (n is None):
                raus.append(f"{feld} {'neu' if a is None else 'entfallen'}")
            continue
        if feld == "fair_value":
            if a and abs(n / a - 1.0) >= schwelle:
                raus.append(f"fair_value {a:.2f} \u2192 {n:.2f}")
        elif abs(n - a) >= schwelle:
            raus.append(f"{feld} {a:.0f} \u2192 {n:.0f}")
    return raus


def notieren(ticker: str, composite=None, quantum=None, fair_value=None,
             basis: Optional[dict] = None, grund: str = "") -> bool:
    """Einen Stand festhalten - aber nur, wenn er sich spuerbar unterscheidet.

    basis: valuation.basis_signatur() des aktuellen Laufs. Damit laesst sich
           beim naechsten Mal sagen, WARUM sich etwas geaendert hat: welche
           Felder fehlten, welche Methoden entfielen, ob das Playbook kippte.

    Rueckgabe: True, wenn geschrieben wurde.
    """
    import store

    tk = (ticker or "").upper().strip()
    if not tk:
        return False

    neu = {"d": _jetzt()}
    if composite is not None:
        neu["composite"] = round(float(composite), 1)
    if quantum is not None:
        neu["quantum"] = round(float(quantum), 1)
    if fair_value is not None:
        neu["fair_value"] = round(float(fair_value), 2)
    if len(neu) == 1:
        return False                      # nichts ausser dem Datum

    try:
        roh = store.get_anreicherung(tk, "verlauf", max_alter_tage=3650) or []
    except Exception:
        roh = []
    if not isinstance(roh, list):
        roh = []
    reihe = [_aus(e) for e in roh]

    letzter = reihe[-1] if reihe else None
    aenderungen = _spuerbar(letzter, neu)
    if not aenderungen:
        return False

    # Grund: erst der uebergebene, sonst aus dem Vergleich der Rechengrundlage
    if not grund and basis and letzter and letzter.get("basis"):
        try:
            import valuation as _v
            d = _v.basis_vergleich(basis, letzter["basis"])
            if d:
                grund = " \u00b7 ".join(d["texte"])[:110]
        except Exception:
            pass
    if not grund:
        # Ohne benennbare Ursache: Das ist selbst eine Aussage - die
        # Rechengrundlage war gleich, der Wert hat sich trotzdem bewegt.
        grund = ("gleiche Datengrundlage - die Bewegung kommt aus den Zahlen "
                 "selbst" if letzter else "")

    eintrag = dict(neu)
    eintrag["was"] = " \u00b7 ".join(aenderungen)[:90]
    if grund:
        eintrag["grund"] = grund
    if basis:
        eintrag["basis"] = basis

    # Eintrag desselben Tages ersetzen, nicht anhaengen
    reihe = [e for e in reihe if e.get("d") != neu["d"]]
    reihe.append(eintrag)
    reihe = reihe[-MAX_EINTRAEGE:]

    # 'basis' nur beim JUENGSTEN Eintrag behalten.
    #
    # Gemessen: Ein vollstaendiger Eintrag braucht 383 Zeichen, davon 182
    # allein fuer 'basis' - fast die Haelfte. Bei 500 Titeln mit sechs
    # Eintraegen waren das 53 % des gesamten Zusatzspeichers.
    #
    # Gebraucht wird die Signatur aber nur, um den NAECHSTEN Vergleich zu
    # bilden. Sobald ein neuerer Eintrag da ist, hat sie ihren Zweck erfuellt.
    # Der Grundtext bleibt - er ist das Ergebnis des Vergleichs und das, was
    # man spaeter lesen will.
    for e in reihe[:-1]:
        e.pop("basis", None)

    try:
        return bool(store.set_anreicherung(tk, "verlauf",
                                           [_ein(e) for e in reihe]))
    except Exception:
        return False


def lesen(ticker: str) -> List[dict]:
    """Verlauf eines Titels, neueste zuerst."""
    import store
    try:
        r = store.get_anreicherung((ticker or "").upper(), "verlauf",
                                   max_alter_tage=3650)
        return [_aus(e) for e in reversed(r)] if isinstance(r, list) else []
    except Exception:
        return []


#: Mehr als das darf der Verlauf vom Zusatzspeicher nicht belegen. Wird die
#: Grenze ueberschritten, faellt der aelteste Titel heraus - unabhaengig von
#: MAX_TITEL. Ist der Speicher voll, schlaegt das SCHREIBEN fehl: dann sind
#: auch Watchlist, Portfolio und Trackrecord betroffen, nicht nur der Verlauf.
MAX_ANTEIL_PCT = 25.0


def aufraeumen(max_titel: int = MAX_TITEL) -> int:
    """Aelteste Verlaeufe entfernen, wenn zu viele Titel gefuehrt werden.

    Ohne diese Grenze waechst der Verlauf mit jedem Nachtlauf weiter - bei
    600 gescannten Titeln taeglich waere der Speicher in einer Woche voll,
    und dann schlaegt das SCHREIBEN fehl, nicht nur der Verlauf. Deshalb
    laeuft das Aufraeumen am Ende jedes Laufs.

    Rueckgabe: Anzahl entfernter Titel.
    """
    import store

    try:
        d = store._load_aux()
    except Exception:
        return 0
    eintraege = d.get("anreicherung") or {}
    verlaeufe = {k: v for k, v in eintraege.items() if k.startswith("verlauf:")}
    import json as _j0
    _anteil_jetzt = (len(_j0.dumps(verlaeufe, ensure_ascii=False)) / 1_350_000 * 100
                     if verlaeufe else 0.0)
    if len(verlaeufe) <= max_titel and _anteil_jetzt <= MAX_ANTEIL_PCT:
        return 0

    # Aeltester Schreibzeitpunkt zuerst weg - nicht aeltester Eintrag:
    # Ein Titel, der seit Monaten unveraendert ist, wird seltener geschrieben
    # und ist damit weniger interessant als einer, der sich bewegt.
    nach_alter = sorted(verlaeufe.items(), key=lambda kv: (kv[1] or {}).get("_ts", 0))
    weg = max(0, len(verlaeufe) - max_titel)

    # Zusaetzlich am Platz ausrichten: Die Titelzahl allein sagt nichts ueber
    # die Groesse - ein Titel mit fuenf langen Gruenden belegt so viel wie
    # fuenf mit je einem.
    import json as _j
    while True:
        rest = dict(nach_alter[weg:])
        if not rest:
            break
        anteil = len(_j.dumps(rest, ensure_ascii=False)) / 1_350_000 * 100
        if anteil <= MAX_ANTEIL_PCT or weg >= len(nach_alter) - 50:
            break
        weg += 25

    for schluessel, _ in nach_alter[:weg]:
        eintraege.pop(schluessel, None)
    try:
        store._save_aux(d)
    except Exception:
        return 0
    return weg


def statistik() -> dict:
    """Wie viel Platz belegt der Verlauf? Fuer die Diagnose."""
    import json

    import store
    try:
        d = store._load_aux()
    except Exception:
        return {}
    eintraege = d.get("anreicherung") or {}
    verlaeufe = {k: v for k, v in eintraege.items() if k.startswith("verlauf:")}
    zeichen = len(json.dumps(verlaeufe, ensure_ascii=False)) if verlaeufe else 0
    n_eintraege = sum(len((v or {}).get("wert") or []) for v in verlaeufe.values())
    return {"titel": len(verlaeufe), "eintraege": n_eintraege,
            "zeichen": zeichen,
            "anteil_speicher": round(zeichen / 1_350_000 * 100, 1)}
