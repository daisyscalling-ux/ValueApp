# KI im Tool

Stand 22.11.2026. Testmonat des Nutzers mit eigenem API-Schlüssel (Secret `ANTHROPIC_API_KEY`), Modell Claude Haiku 5.5. Ausgabegrenze 2 $ pro Monat in der Anthropic Console.

## Grundsätze
- KI liefert **keine Zahlen für Bewertung oder Score**. Sie ordnet ein, sortiert vor oder erklärt. Alles ist gekennzeichnet („nicht geprüft“) und trägt `scoreContribution: 0`.
- Eingaben aus fremden Quellen stehen als Daten im Prompt, mit der Anweisung, darin enthaltene Anweisungen nicht zu befolgen. Antworten sind an ein JSON-Schema gebunden.
- Jede Antwort wird gegen die Eingabe geprüft: nur vorhandene IDs, nur bekannte Kategorien. Der Rest wird verworfen und gezählt. Die App prüft beim Lesen erneut.
- **Kosten:** `count_tokens` vor jedem Aufruf. Abbruch, wenn der Monat in `daten/ki_kosten.json` mit der Höchstschätzung über 1 $ käme. Jeder Aufruf wird gebucht (`kosten.py`).

## Funktionen

| Funktion | Methode | Takt | geschätzte Kosten pro Monat |
|---|---|---|---:|
| Trends-Einordnung | `news_trends_ki_v1` (`nachrichten_trends/ki_einordnung.py`) | montags | ~0,01 $ |
| Vorprüfung negativer Ereignisse | `risk_event_ki_v1` (`ki/ereignisse.py`) | täglich | ~0,25 $ |

## Vorprüfung negativer Ereignisse (`risk_event_ki_v1`)
- **Anlass:** Die Suchmuster in `company_news.py` markierten am 21.11. nur 71 von 5.542 Unternehmensschlagzeilen, 67 davon Kanzleiaufrufe. Prognosesenkungen, Ermittlungen oder Rücktritte ohne die genauen Wörter fehlten.
- **Eingabe:** alle Unternehmensschlagzeilen der letzten 7 Tage zu Universumstiteln, die noch nicht geprüft sind, mit dem Firmennamen. Stapel zu 350, höchstens 8 Aufrufe je Lauf, Einstellung `effort: low`.
- **Ausgabe:** nur Treffer mit Einstufung (`negatives_ereignis`, `anwaltsaufruf`, `andere_firma`), Kategorie (7 feste) und einem Satz Begründung aus der Schlagzeile. Alle geprüften IDs werden gemerkt, damit nichts doppelt bezahlt wird.
- **Datei:** `daten/cf_risk_event_ki.json`, 7 Tage rollierend. Die versiegelte Ereignisprüfung (`cf_risk_event_review.json`) bleibt unverändert; eine Bestätigung braucht weiter die Originalquelle (`reviewed-risk-events.json`).
- **Probelauf der Eingabe (22.11., ohne API):** 5.672 offene Schlagzeilen, 17 Stapel zu je rund 12.000 Tokens, etwa 0,002 $ je Stapel. Der Rückstand ist nach etwa 3 Läufen abgearbeitet; danach etwa 3–4 Stapel pro Tag.
- **Grenzen und Verzerrungen:**
  - Das Modell sieht nur die Schlagzeile. Die Einstufung kann falsch sein, deshalb ist der Beleg immer verlinkt.
  - Fehlt eine Einstufung, heißt das nicht „kein Ereignis“.
  - Titel mit vielen Schlagzeilen werden häufiger getroffen; die Zahl der Treffer ist kein Risikomaß.
- **Tests:** `test_ki.py` (5, API simuliert).
