"""
ai_briefing.py — EIN Claude-Aufruf pro Nacht: erklaert die News und fasst zusammen,
welche neuen Aktien in Screener/Radar einen Score erreicht haben, plus die
wichtigsten Portfolio-/Watchlist-Aenderungen.

WICHTIG:
- Claude ist hier nur die SPRACH-/EINORDNUNGS-Schicht. Alle Zahlen (Scores, Fair
  Value, Upside) kommen deterministisch aus dem Code und werden Claude nur als
  Fakten uebergeben. Claude rechnet nichts, sondern erklaert/priorisiert.
- Laeuft ueber die Anthropic-API (pro Token abgerechnet, NICHT vom Abo gedeckt).
  Standardmodell: Haiku (guenstig, passend). Ueber AI_BRIEFING_MODEL aenderbar.
- Vollstaendig defensiv: kein Key / Fehler / Timeout -> gibt None zurueck, der
  Nacht-Job laeuft normal weiter (regelbasierte Zusammenfassung als Rueckfall).
"""
from __future__ import annotations
import os
import json

try:
    import requests
except Exception:
    requests = None

# Guenstiges, passendes Modell als Standard (ausdruecklich KEIN Opus).
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") and requests is not None)


def _rows_brief(rows, keys=("ticker", "name", "composite", "upside", "quantum")):
    out = []
    for r in (rows or [])[:12]:
        out.append({k: r.get(k) for k in keys if r.get(k) is not None})
    return out


def _news_brief(news_items, limit=8):
    out = []
    for n in (news_items or [])[:limit]:
        out.append({"title": (n.get("headline") or "")[:160],
                    "source": n.get("source"),
                    "summary": (n.get("summary") or "")[:240]})
    return out


def generate(changes, news_items, holdings, watch, screener_rows, radar_rows,
             model=None, timeout=60):
    """Erzeugt den Briefing-Text (deutsch) oder None bei Fehler/kein Key."""
    if not available():
        print("[ai_briefing] Kein ANTHROPIC_API_KEY - Briefing uebersprungen.")
        return None
    model = model or os.getenv("AI_BRIEFING_MODEL") or DEFAULT_MODEL

    facts = {
        "aenderungen": [
            {"section": c.get("section"), "ticker": c.get("ticker"),
             "text": c.get("text"), "kind": c.get("kind")}
            for c in (changes or [])[:25]
        ],
        "portfolio": _rows_brief(list((holdings or {}).values())),
        "watchlist": _rows_brief(list((watch or {}).values())),
        "screener_top": _rows_brief(screener_rows),
        "radar_top": _rows_brief(radar_rows),
        "news": _news_brief(news_items),
    }

    system = (
        "Du bist ein nuechterner Finanz-Analyst-Assistent fuer ein privates "
        "Lern-Tool. Sprache: Deutsch. Du bekommst FAKTEN (bereits berechnete "
        "Kennzahlen, erkannte Aenderungen, aktuelle Schlagzeilen) und sollst sie "
        "erklaeren und priorisieren - NICHT neu berechnen, NICHTS erfinden. "
        "Nenne nur Titel/Zahlen, die in den Fakten stehen. Wenn etwas unklar ist, "
        "sage es. Gib ausdruecklich KEINE Kauf-/Verkaufsempfehlung; formuliere als "
        "Beobachtung und Denkanstoss. Halte dich kurz und konkret."
    )
    instruction = (
        "Erstelle ein kompaktes Morgen-Briefing mit diesen Abschnitten:\n"
        "1) WICHTIGSTES ZUERST: 2-4 Stichpunkte zu den relevantesten Aenderungen "
        "(Kaufzone erreicht, starke Score-Bewegung, neuer Titel in Screener/Radar).\n"
        "2) NEUE KANDIDATEN: Welche NEUEN Aktien haben in Screener bzw. Radar einen "
        "Score erreicht? Nenne Ticker + kurz warum interessant (aus den Fakten).\n"
        "3) NEWS-EINORDNUNG: Zu den 2-3 wichtigsten Schlagzeilen je 1 Satz, welcher "
        "Bereich/welche Titel betroffen sein KOENNTEN (Denkanstoss).\n"
        "4) PORTFOLIO-BLICK: 1-2 Saetze zum Zustand (z.B. auffaellige Position, "
        "Klumpenrisiko), nur wenn aus den Fakten ableitbar.\n"
        "Schliesse mit einem kurzen Hinweis, dass dies kein Anlagerat ist.\n\n"
        "FAKTEN (JSON):\n" + json.dumps(facts, ensure_ascii=False)
    )

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
                "max_tokens": 1400,
                "system": system,
                "messages": [{"role": "user", "content": instruction}],
            },
            timeout=timeout,
        )
        if r.status_code != 200:
            print(f"[ai_briefing] API {r.status_code}: {r.text[:200]}")
            return None
        data = r.json()
        parts = [b.get("text", "") for b in data.get("content", [])
                 if b.get("type") == "text"]
        text = "\n".join(p for p in parts if p).strip()
        return text or None
    except Exception as e:
        print(f"[ai_briefing] Fehler: {e}")
        return None
