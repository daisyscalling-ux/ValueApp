# -*- coding: utf-8 -*-
"""these.py - Claude als Denk- und Recherchepartner fuer eigene Thesen.

WICHTIG - die Trennung, die den Wert des Tools schuetzt:
  Claude hilft hier beim DENKEN - Thesen schaerfen, Gegenargumente finden,
  Themen einordnen, Informationen bewerten. Claude veraendert NIEMALS den
  Fundamentalwert, den Composite Score oder das Upside des Tools. Die kalte
  Modellzahl bleibt unabhaengig und ehrlich; die eigene These steht daneben.

  Der Grund: Ein Bewertungswerkzeug ist nur wertvoll, wenn es der eigenen
  Begeisterung WIDERSPRECHEN kann. Sobald subjektiver Optimismus die Zahlen
  faerbt, wird das Tool zum Spiegel der eigenen Meinung - und damit nutzlos
  als Korrektiv. Darum: Claude als Sparringspartner, nicht als Orakel.
"""
from __future__ import annotations
import os
import json

try:
    import requests
except Exception:
    requests = None

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def verfuegbar() -> bool:
    """True, wenn ein API-Key gesetzt und requests da ist."""
    return bool(os.getenv("ANTHROPIC_API_KEY") and requests is not None)


def _frag_claude(system: str, nachricht: str, verlauf=None,
                 model: str = DEFAULT_MODEL, max_tokens: int = 1200,
                 timeout: int = 40) -> str | None:
    """Ein Aufruf an Claude. Gibt den Text zurueck oder None bei Fehler.
    verlauf = Liste von {role, content} fuer Mehrfach-Dialog."""
    if not verfuegbar():
        return None
    messages = list(verlauf or [])
    messages.append({"role": "user", "content": nachricht})
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": os.getenv("ANTHROPIC_API_KEY"),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": messages,
            },
            timeout=timeout,
        )
        if r.status_code != 200:
            return f"[Fehler {r.status_code}] {r.text[:200]}"
        data = r.json()
        parts = [b.get("text", "") for b in data.get("content", [])
                 if b.get("type") == "text"]
        text = "\n".join(p for p in parts if p).strip()
        return text or None
    except Exception as e:
        return f"[Fehler] {e}"


# System-Prompt: Claude ist hier ehrlicher Sparringspartner, KEIN Cheerleader.
_SYSTEM_SPARRING = (
    "Du bist ein erfahrener, skeptischer Investment-Sparringspartner. Der "
    "Nutzer teilt eine eigene These zu einer Aktie. Deine Aufgabe ist NICHT, "
    "ihm zuzustimmen oder ihn zu begeistern, sondern seine These zu SCHAERFEN "
    "und ehrlich zu pruefen. Konkret:\n"
    "1) Fasse den Kern der These in 1-2 Saetzen zusammen.\n"
    "2) Nenne die 2-3 STAERKSTEN Gegenargumente oder Risiken - das ist dein "
    "wichtigster Beitrag. Was koennte die These kippen?\n"
    "3) Nenne, welche konkreten Fakten/Kennzahlen man pruefen sollte, um die "
    "These zu bestaetigen oder zu widerlegen.\n"
    "4) Frage dich: Was weiss der Markt schon, das den Kurs erklaert? Warum "
    "sollte der Nutzer hier einen Vorteil haben?\n"
    "Sei konkret, nuechtern und knapp. Kein Hype, keine Kurszielprognose. "
    "Du gibst KEINEN Anlagerat und sagst NICHT, ob die Aktie steigt - du "
    "hilfst nur, klarer und ehrlicher zu denken. Antworte auf Deutsch."
)

_SYSTEM_FRAGE = (
    "Du bist ein sachkundiger, nuechterner Gespraechspartner fuer einen "
    "Privatanleger, der verstehen und lernen will. Beantworte seine Fragen zu "
    "Unternehmen, Branchen, Endmaerkten, Geschaeftsmodellen und "
    "Zusammenhaengen fundiert und ausgewogen. Nenne Chancen UND Risiken. "
    "Wenn du etwas nicht sicher weisst (z.B. tagesaktuelle Kurse oder Zahlen "
    "nach deinem Wissensstand), sage das offen, statt zu raten. Gib KEINE "
    "Kaufempfehlung und keine Kursprognose - hilf beim Einordnen und Verstehen. "
    "Sei konkret und knapp. Antworte auf Deutsch."
)


def these_pruefen(ticker: str, name: str, these_text: str,
                  endmarkt: str = "", katalysator: str = "",
                  fundamental_kontext: dict | None = None) -> str | None:
    """Claude prueft die eigene These als Sparringspartner - sucht die
    Schwachstellen, statt zuzustimmen. fundamental_kontext = optionale
    Modellzahlen (Score, Upside), damit Claude die Spannung benennen kann."""
    teile = [f"Aktie: {name} ({ticker})"]
    if these_text:
        teile.append(f"Meine These: {these_text}")
    if endmarkt:
        teile.append(f"Endmarkt/Treiber: {endmarkt}")
    if katalysator:
        teile.append(f"Katalysator: {katalysator}")
    if fundamental_kontext:
        teile.append("Was das Fundamentalmodell sagt (unabhaengig von meiner "
                     "These): " + json.dumps(fundamental_kontext,
                                              ensure_ascii=False))
    nachricht = "\n".join(teile) + (
        "\n\nBitte pruefe meine These ehrlich und schaerfe sie. Wo koennte ich "
        "falsch liegen?")
    return _frag_claude(_SYSTEM_SPARRING, nachricht)


def frage_stellen(frage: str, verlauf=None) -> str | None:
    """Allgemeine Frage an Claude zu Themen, Branchen, Einordnung von
    Informationen. verlauf ermoeglicht ein fortlaufendes Gespraech."""
    return _frag_claude(_SYSTEM_FRAGE, frage, verlauf=verlauf, max_tokens=1500)


# ===========================================================================
# PORTER FUENF KRAEFTE - gefuehrter Eigen-Input (Schmidlin, Kapitel 5/8.2)
# ===========================================================================
# Die Marktmacht laesst sich NICHT sauber automatisieren - sie braucht dein
# Urteil. Diese fuenf Fragen strukturieren es. Claude hilft beim Einschaetzen,
# entscheiden tust du. Jede Kraft wird 0-5 bewertet (5 = sehr guenstig fuer die
# Firma), Summe 0-25 = "Porter-Punkte" -> Marktstellungs-Aufschlag im fairen KGV.

PORTER_KRAEFTE = [
    {"key": "rivalitaet",
     "frage": "Wie stark ist die Rivalit\u00e4t unter den bestehenden Wettbewerbern?",
     "hilfe": "Wenige Wettbewerber und wenig Preiskampf = g\u00fcnstig (hoch). Viele "
              "austauschbare Anbieter, Preiskrieg = ung\u00fcnstig (niedrig).",
     "claude": "Wer sind die Hauptwettbewerber von {name} ({ticker}), und wie "
               "intensiv ist der Preiswettbewerb in dieser Branche? Nenne mir "
               "die 2-3 wichtigsten Punkte, die ich f\u00fcr eine Einsch\u00e4tzung der "
               "Wettbewerbsintensit\u00e4t (0=brutal, 5=entspannt) brauche."},
    {"key": "neue_anbieter",
     "frage": "Wie hoch sind die Markteintrittsbarrieren (Bedrohung durch neue Anbieter)?",
     "hilfe": "Hohe Barrieren (Kapital, Patente, Marke, Netzwerkeffekte) = "
              "g\u00fcnstig (hoch). Leichter Eintritt = ung\u00fcnstig (niedrig).",
     "claude": "Wie hoch sind die Markteintrittsbarrieren im Gesch\u00e4ft von {name} "
               "({ticker})? Was h\u00e4lt neue Konkurrenten fern (oder eben nicht)? "
               "Nenne mir die entscheidenden Faktoren."},
    {"key": "lieferanten",
     "frage": "Wie gro\u00df ist die Verhandlungsmacht der Lieferanten?",
     "hilfe": "Firma ist von wenigen Lieferanten abh\u00e4ngig = ung\u00fcnstig (niedrig). "
              "Viele austauschbare Lieferanten = g\u00fcnstig (hoch).",
     "claude": "Wie abh\u00e4ngig ist {name} ({ticker}) von seinen Lieferanten? Gibt "
               "es Kl\u00fcmpchenrisiken oder viele Alternativen? Was sollte ich "
               "wissen, um die Lieferantenmacht einzusch\u00e4tzen?"},
    {"key": "abnehmer",
     "frage": "Wie gro\u00df ist die Verhandlungsmacht der Abnehmer/Kunden?",
     "hilfe": "Wenige gro\u00dfe Kunden, die Druck machen k\u00f6nnen = ung\u00fcnstig (niedrig). "
              "Viele kleine Kunden, hohe Wechselkosten = g\u00fcnstig (hoch).",
     "claude": "Wie ist die Kundenstruktur von {name} ({ticker})? Gibt es "
               "Kl\u00fcmpchenrisiken (wenige Gro\u00dfkunden) oder Preismacht gegen\u00fcber "
               "den Kunden? Was ist f\u00fcr die Einsch\u00e4tzung wichtig?"},
    {"key": "substitute",
     "frage": "Wie gro\u00df ist die Bedrohung durch Ersatzprodukte (Substitute)?",
     "hilfe": "Kaum Alternativen zum Produkt = g\u00fcnstig (hoch). Leicht ersetzbar "
              "durch andere L\u00f6sungen/Technologien = ung\u00fcnstig (niedrig).",
     "claude": "Welche Substitute oder alternativen Technologien bedrohen das "
               "Kerngesch\u00e4ft von {name} ({ticker}) mittelfristig? Wie gro\u00df ist "
               "die Verdr\u00e4ngungsgefahr?"},
]


def porter_punkte_zu_aufschlag(summe: int) -> float:
    """Wandelt die Porter-Summe (0-25) in Schmidlins KGV-Aufschlag (0-3)."""
    if summe <= 5:
        return 0.25
    if summe <= 10:
        return 1.0
    if summe <= 15:
        return 1.75
    if summe <= 20:
        return 2.25
    return 2.75


def porter_frage_an_claude(ticker: str, name: str, kraft_key: str) -> str | None:
    """Holt fuer EINE Porter-Kraft die passende Recherchehilfe von Claude,
    damit der Nutzer die Frage fundiert selbst beantworten kann."""
    kraft = next((k for k in PORTER_KRAEFTE if k["key"] == kraft_key), None)
    if not kraft:
        return None
    prompt = kraft["claude"].format(name=name, ticker=ticker)
    system = (_SYSTEM_FRAGE + " Halte dich kurz und konkret - der Nutzer will "
              "diese eine Wettbewerbskraft selbst auf einer Skala 0-5 bewerten "
              "und braucht daf\u00fcr die entscheidenden Fakten, keine Romane.")
    return _frag_claude(system, prompt, max_tokens=700)


# ===========================================================================
# THESEN-TRACKRECORD - dein ehrlicher Spiegel: gehen DEINE Thesen auf?
# ===========================================================================
# Kein Modell-Lernen. Das Tool wird durch deine Thesen NICHT "besser". Es
# zeigt dir stattdessen, wie gut DEIN eigenes Urteil ueber die Zeit trifft -
# genau wie der Backtest, aber angewandt auf deine persoenlichen Thesen.

def these_bewerten(these: dict, aktueller_kurs) -> dict | None:
    """Bewertet EINE These gegen den aktuellen Kurs. Braucht start_kurs und
    angelegt (Datum). Gibt Kennzahlen zurueck oder None, wenn nicht messbar."""
    start = these.get("start_kurs")
    if not start or not aktueller_kurs or start <= 0:
        return None
    rendite = (aktueller_kurs / start - 1) * 100
    # Dein Kursziel getroffen?
    ziel = these.get("eigenes_ziel")
    ziel_pct = None
    ziel_erreicht = None
    if ziel and ziel > 0:
        ziel_pct = (ziel / start - 1) * 100          # was du erwartet hast
        # "getroffen", wenn der Kurs die Richtung deines Ziels ging und
        # mindestens die Haelfte des erwarteten Wegs erreicht hat
        if ziel_pct > 0:
            ziel_erreicht = rendite >= ziel_pct * 0.5
        else:
            ziel_erreicht = rendite <= ziel_pct * 0.5
    return {
        "rendite_pct": round(rendite, 1),
        "ziel_pct": round(ziel_pct, 1) if ziel_pct is not None else None,
        "ziel_erreicht": ziel_erreicht,
        "ueberzeugung": these.get("ueberzeugung"),
        "endmarkt": these.get("endmarkt", ""),
        "angelegt": these.get("angelegt", ""),
        "start_kurs": start,
    }


def trackrecord_auswerten(bewertungen: list) -> dict:
    """Fasst mehrere bewertete Thesen zu einer ehrlichen Trefferbilanz
    zusammen. bewertungen = Liste von these_bewerten-Ergebnissen."""
    gueltig = [b for b in bewertungen if b]
    if not gueltig:
        return {"n": 0}
    n = len(gueltig)

    def _median(werte):
        w = sorted(werte)
        m = len(w)
        if not w:
            return None
        return round(w[m // 2] if m % 2 else (w[m // 2 - 1] + w[m // 2]) / 2, 1)

    renditen = [b["rendite_pct"] for b in gueltig]

    # Trefferquote gegen das eigene Ziel (nur wo ein Ziel gesetzt war)
    mit_ziel = [b for b in gueltig if b["ziel_erreicht"] is not None]
    treffer = sum(1 for b in mit_ziel if b["ziel_erreicht"])

    # Hohe vs. niedrige Ueberzeugung: triffst du besser, wenn du sicher warst?
    hoch = [b for b in gueltig if (b.get("ueberzeugung") or 0) >= 4]
    niedrig = [b for b in gueltig if (b.get("ueberzeugung") or 0) <= 2]

    return {
        "n": n,
        "median_rendite": _median(renditen),
        "schnitt_rendite": round(sum(renditen) / n, 1),
        "beste": round(max(renditen), 1),
        "schlechteste": round(min(renditen), 1),
        "n_mit_ziel": len(mit_ziel),
        "ziel_treffer": treffer,
        "ziel_treffer_pct": (round(treffer / len(mit_ziel) * 100, 1)
                             if mit_ziel else None),
        "median_hohe_ueberzeugung": _median([b["rendite_pct"] for b in hoch]) if hoch else None,
        "n_hohe_ueberzeugung": len(hoch),
        "median_niedrige_ueberzeugung": _median([b["rendite_pct"] for b in niedrig]) if niedrig else None,
        "n_niedrige_ueberzeugung": len(niedrig),
    }
