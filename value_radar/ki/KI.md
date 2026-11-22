# KI im Tool

Stand 22.11.2026. Testmonat des Nutzers mit eigenem API-Schlüssel (Secret `ANTHROPIC_API_KEY`), Modell Claude Haiku 5.5. Ausgabegrenze 2 $ pro Monat in der Anthropic Console.

## Grundsätze
- KI liefert **keine Zahlen für Bewertung oder Score**. Sie ordnet ein, sortiert vor oder erklärt. Alles ist gekennzeichnet („nicht geprüft“) und trägt `scoreContribution: 0`.
- Eingaben aus fremden Quellen stehen als Daten im Prompt, mit der Anweisung, darin enthaltene Anweisungen nicht zu befolgen. Antworten sind an ein JSON-Schema gebunden.
- Jede Antwort wird gegen die Eingabe geprüft: nur vorhandene IDs, nur bekannte Kategorien. Der Rest wird verworfen und gezählt. Die App prüft beim Lesen erneut.
- **Kosten:** `count_tokens` vor jedem Aufruf. Abbruch, wenn der Anteil der Funktion oder die Summe in `daten/ki_kosten.json` mit der Höchstschätzung überschritten würde. Jeder Aufruf wird gebucht (`kosten.py`).
- **Feste Anteile (seit 22.11.2026, Entscheidung des Nutzers):**

  | Funktion | Anteil pro Monat |
  |---|---:|
  | Ereignis-Vorprüfung | 0,90 $ |
  | KI-Portfolio | 0,40 $ |
  | Themen des Tages | 0,20 $ |
  | Trends-Einordnung | 0,10 $ |
  | **Pipeline zusammen** | **1,60 $** |
  | Fair-Value-Erklärung (Cloudflare) | 0,30 $ |

  Zusammen 1,90 $, unter der Console-Grenze von 2 $. Eine unbekannte Funktion hat kein Budget.

## Funktionen

| Funktion | Methode | Takt | geschätzte Kosten pro Monat |
|---|---|---|---:|
| Trends-Einordnung | `news_trends_ki_v1` (`nachrichten_trends/ki_einordnung.py`) | montags | ~0,01 $ |
| Vorprüfung negativer Ereignisse | `risk_event_ki_v1` (`ki/ereignisse.py`) | täglich | ~0,6–0,9 $ (gemessen 22.11.) |
| Themen des Tages | `daily_topics_ki_v1` (`ki/themen_des_tages.py`) | täglich 05:47 UTC | ~0,15 $ |

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

## Erster echter Lauf (22.11.2026)

| | Trends-Einordnung | Ereignis-Vorprüfung |
|---|---|---|
| Aufrufe | 1 | 4 (von 8 erlaubten) |
| Tokens ein / aus | 27.317 / 4.010 | 95.560 / 26.245 |
| Kosten | 0,0047 $ | 0,0227 $ |
| Ergebnis | 8 Themen, 4 neue Themen, 4 Aussagen ohne Beleg verworfen | 1.050 Schlagzeilen geprüft: 24 negative Ereignisse, 36 Kanzleiaufrufe, 25 andere Firma; 0 verworfen |

**Abweichungen vom Probelauf:**
- **Tokens:** Die Eingabe hatte etwa doppelt so viele Tokens wie geschätzt (Schätzung 3,5 Zeichen je Token; tatsächlich rund 1,8). Ein Ereignis-Stapel kostet daher etwa 0,0057 $ statt 0,002 $.
- **Eigener Fehler:** Der vierte Ereignis-Stapel brach mit `max_tokens` (8.000) ab und wird im nächsten Lauf wiederholt. Behoben: 250 Schlagzeilen je Stapel, 16.000 Antwort-Tokens.

**Neue Kostenschätzung:**
- Ereignis-Vorprüfung etwa 0,6–0,9 $ pro Monat, bei 800–1.400 neuen Schlagzeilen pro Tag.
- Trends-Einordnung etwa 0,02 $ pro Monat.
- Das liegt nahe am Pipeline-Budget von 1 $. Eine Senkung (Antwort ohne Denken, kürzere Begründung) entscheidet der Nutzer.

**Stichprobe der Treffer:** überwiegend plausibel, z. B. Nissan-Hackerangriff, Intuit senkt die Umsatzprognose, Nike erwartet erneut sinkende Umsätze. Bekannte Fehleinstufungen:
- „HALO Faces Legal Setback … Over MRK's Keytruda“ als negatives Ereignis für Merck, obwohl es Halozyme betrifft;
- spekulative Fragen wie „JPMorgan Faces Data Leak …: Risks Mount?“ gelten als Ereignis.

Deshalb bleibt die Kennzeichnung „nicht geprüft“.

## Themen des Tages (`daily_topics_ki_v1`, seit 22.11.2026)
- **Abschnitte:**
  - **Markt:** `cf_news.json`, letzte 24 h.
  - **Aktien:** `cf_company_news.json`, letzte 48 h, ohne Routine-Meldungen, höchstens 2 je Titel. Am Wochenende kommen kaum Unternehmensnachrichten (21.11.: 41 gegen 1.042 am 20.11.).
  - **Welt:** `cf_world_news.json`, letzte 24 h. Neue Welt-Rubriken: BBC World, FT World, WSJ World, Bloomberg Politics. Stündlich im Workflow `market-news`, nur Titel, Datum und Link. Am 22.11. waren alle vier öffentlich erreichbar.
- **Ausgabe je Abschnitt:** ein Lagesatz und bis zu 5 Punkte, jeder mit 1–6 Belegen nur aus dem eigenen Abschnitt. Aktien-Symbole werden nur übernommen, wenn eine zitierte Schlagzeile sie betrifft. Abschnitte mit weniger als 5 Schlagzeilen bleiben offen, mit Grund.
- **Probelauf der Eingabe** (22.11., Sonntag, ohne API): Markt 117, Aktien 72, Welt 54 Schlagzeilen, rund 14.300 Tokens, also etwa 0,004 $ je Lauf.
- **Tests:** 3 (API simuliert).

## KI-Papierdepot (`ki_paper_portfolio_v1`, seit 22.11.2026)
**Simulation mit 50.000 € virtuell.** Kein echter Broker, keine echten Orders, kein Anlagerat. Code: `ki/portfolio.py`, Workflow `ki-portfolio` (Dienstag bis Samstag 04:31 UTC und manuell).

**Entscheidungen des Nutzers (22.11.2026):**
- **Auswahl:** Die KI wählt frei aus dem ganzen Universum.
- **Takt:** täglich prüfen und handeln, wenn der Kaufgrund nicht mehr gilt (z. B. schwache Zahlen, schlechte Nachrichten, gekippter Trend).
- **Regeln:** „ausgewogen“, dazu Nachkaufen erlaubt, wenn der Kurs gefallen ist, die Daten aber gut sind.
- **Vergleich:** S&P 500 und FTSE All-World.

| Regel | Umsetzung (Code, nicht KI) |
|---|---|
| Ausführung | am **nächsten** geprüften Schlusskurs (`exchange_close_v1`), der neuer ist als der bei der Entscheidung. Am Wochenende wird also nicht zum bekannten Freitagskurs ausgeführt. Nicht ausführbare Aufträge verfallen nach 3 Läufen. |
| Gebühren, Stückelung | 0,1 % je Kauf und Verkauf; nur ganze Stück (japanische Handelseinheiten von 100 Stück sind nicht abgebildet) |
| Währung | Depot in EUR, Umrechnung mit dem EZB-Referenzkurs (höchstens 5 Tage alt); ohne Kurs kein Handel |
| Grenzen | höchstens 10 Positionen, 12 % je Titel, 30 % je Branche, mindestens 5 % Cash. Größere Aufträge werden gekürzt, der Grund steht im Journal. |
| Stop-Loss | −15 % auf den durchschnittlichen Einstand (Notierungswährung), täglich zum Schlusskurs |
| Take-Profit | +35 %: die Hälfte wird verkauft, für den Rest gilt ein Stop beim Einstand |
| Nachkauf | nur unter dem Einstand; neuer Einstand als Durchschnitt |
| KI | Claude Haiku 5.5, `effort: medium`, Antwort als JSON-Schema. Eingabe: Regeln, Depot mit These je Position, Schlagzeilen und KI-Ereignisse der Positionen, Universum kompakt (1.339 Titel, rund 68.000 Tokens). Geprüft: Aktion, Symbol mit geprüftem Kurs, Anteil 0,5–12 %, Teilverkauf 10–90 %, Verkauf nur aus dem Depot, je Symbol eine Entscheidung. Verworfenes steht mit Grund im Journal. |
| Ohne KI | Aufträge, Stops und Bewertung laufen immer, auch ohne Schlüssel, bei leerem Budget oder unlesbarer Antwort. Dann gibt es an diesem Tag keine neuen Aufträge. |
| Vergleich | Schlusskurse von SXR8 (iShares Core S&P 500, Xetra, EUR) und VWCE (Vanguard FTSE All-World, Xetra, EUR). Geprüft: Währung EUR, Börse Xetra, höchstens 5 Tage alt. ETFs statt Index, deshalb mit Kosten und Wiederanlage. |
| Ablage | `daten/ki_portfolio/depot.json` (Stand, Positionen, Aufträge, Tagesverlauf); Journal je Monat `journal/JJJJ-MM.jsonl`, nur anhängen, nie löschen |

**Verzerrungen und Grenzen:**
- **Nur Schlusskurse:** Ein Stop-Loss greift erst zum Tagesschluss. Kurslücken (z. B. nach Zahlen) können den Verlust über 15 % treiben. Das ist realistisch, aber gröber als ein echter Stop-Auftrag.
- **Überlebende im Universum:** Das Universum enthält nur heute gelistete Titel. Die KI kann also keine Firma kaufen, die gerade aus dem Universum fällt.
- **Nicht wiederholbar:** Die KI-Entscheidungen lassen sich nicht exakt wiederholen. Gewertet wird erst nach mehreren Monaten gegen beide Vergleichs-ETFs; einzelne Wochen sind Zufall.
- **Kosten:** Probelauf der Eingabe am 22.11.: rund 68.000 Tokens, also etwa 0,011 $ je Lauf und rund 0,25 $ im Monat. Anteil 0,40 $.

**Tests:** `test_portfolio.py` (8, API simuliert):
- Ausführung am Folgetag und nicht zum Wochenendkurs;
- Gebühr, ganze Stück, Yen;
- Stop-Loss, Take-Profit und Stop beim Einstand ohne KI;
- Nachkauf nur unter Einstand mit Durchschnittskurs;
- Grenzen für Titel, Branche, Cash und Anzahl;
- Prüfung der KI-Antwort;
- Budget, zu große Eingabe, unlesbare und unvollständige Antwort;
- fremdes Depotformat, fehlende Kurse.

### Erster Lauf (22.11.2026) und zwei eigene Fehler
- **Lauf:** 8 Kaufaufträge zu je 11 %, 0 verworfen, 85.348 Tokens Eingabe, 2.717 Ausgabe, 0,0099 $.
- **Fehler 1, Reihenfolge:** Das Universum lag alphabetisch vor der KI. Alle 8 Käufe kamen von Position 1–187 der 1.340 Titel (Athen, Madrid, Kopenhagen, Euronext). 27 Titel erfüllten das Profil, das die KI selbst als Begründung nannte, 8 davon in der hinteren Hälfte, darunter Industrivärden (Composite 88), Investor AB (84) und CF Industries (80).
- **Fehler 2, Zahlen:** `_f` kürzte bei ganzen Zahlen die Null weg: Composite 80 wurde zu „8“, Momentum 90 zu „9“. Betroffen waren 398 von 1.339 Titeln.
- **Entscheidung des Nutzers:**
  - Sortierung nach Composite absteigend, jede Zeile mit Region (USA, Europa, GB, Japan, übrige). Die KI wählt weiter frei.
  - Die 8 Aufträge werden storniert (`STORNO`, Journal-Art „storniert“) und neu entschieden.
- **Folge der Sortierung:** Die KI wird eher Titel wählen, die unsere Scores gut finden, und erbt deren Schwächen, etwa den Abstand der US-Werte im Fair Value. Unter den ersten 100 Zeilen stehen jetzt 45 aus den USA, 32 aus Europa, 15 aus Großbritannien und 8 aus Japan.
- **Eingabe:** etwa 72.000 Tokens (Regionsspalte), weiter unter der Preisgrenze von 100.000.
- **Tests:** 3 neu (Sortierung und Region, ganze Zahlen, Storno).
