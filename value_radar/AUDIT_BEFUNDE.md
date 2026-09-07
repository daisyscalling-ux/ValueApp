# Befundregister

Sortiert nach Auswirkung, nicht nach Modul. Muster M1–M13 aus `AUDIT_PLAN.md`.

| Nr | Modul | Muster | Schwere | Status |
|---|---|---|---|---|
| S3 | store | M5 | **hoch** | behoben |
| C2 | config/providers | M4 | mittel | behoben |
| C1 | config | — | mittel | offen |
| S1 | store | M4 | niedrig | behoben |
| S2 | store | — | niedrig | behoben |

---

## S3 — `store._write()` meldete Erfolg bei unsichtbaren Daten
**Muster M5 (stille Wirkungslosigkeit) · hoch · behoben**

Ist das Google Sheet aktiv, wird von dort **gelesen** (`load_all`). Schlug das
Schreiben ins Sheet fehl, sicherte `_write()` lokal und gab **`True`** zurück.
Der Aufrufer hielt den Vorgang für geglückt, beim nächsten Laden war der
Eintrag weg.

Genau dieser Fehler war in `_save_aux()` bereits behoben — im Hauptpfad aber
nicht. Über `_write` laufen `save()` und damit Watchlist, Portfolio **und die
Signalaufzeichnung des Trackrecords**.

**Das erklärt vermutlich die leere Trackrecord-Bilanz.** `precompute.py`
schrieb Signale, bekam `True` zurück, und die Daten landeten in einer Datei,
aus der nie gelesen wird. Die Vermutung „precompute lief nie" war womöglich
falsch — es lief, aber die Daten verschwanden.

*Behoben:* `_write` schreibt erst lokal, versucht dann das Sheet und gibt
`False` plus Warnung zurück, wenn das Sheet nicht angenommen hat.

*Nachzuprüfen:* `precompute.py` einmal laufen lassen und auf die Zeile
`[store] Google-Sheet-Speichern FEHLGESCHLAGEN` achten. Erscheint sie, ist die
Ursache bestätigt und die Sheet-Anbindung das eigentliche Problem.

## C2 — Toter FMP-Schlüssel wurde bei jedem Aufruf neu probiert
**Muster M4 (Systemausfall als Einzelfall) · mittel · behoben**

`_fmp_get` behandelte nur HTTP 429. Bei 401/403 — Schlüssel ungültig — wurde
kein Merker gesetzt, also lief bei jedem Titel ein neuer Versuch mit
Zeitablauf. Im 150-Titel-Lauf waren das rund 300 vergebliche Anfragen.

Verschärfend: `config.FMP_API_KEY` ist gesetzt (fest im Code), also hielten
alle Prüfungen `if config.FMP_API_KEY:` die Quelle für verfügbar. „Kein
Schlüssel", „toter Schlüssel" und „Anbieter gerade weg" waren nicht
unterscheidbar.

*Behoben:* 401/403 lösen den Circuit-Breaker aus und setzen einen Grund.
Neu: `providers.fmp_status()` benennt den Zustand im Klartext.

## C1 — Zwei echte API-Schlüssel im Klartext im Code
**mittel · offen — Entscheidung liegt bei dir**

```
FINNHUB_API_KEY   40 Zeichen, fest in config.py
FMP_API_KEY       32 Zeichen, fest in config.py
```

Der Kommentar daneben benennt das Risiko bereits richtig: Wird das Repo
jemals öffentlich oder geforkt, sind beide Schlüssel kompromittiert, und ein
späterer Commit entfernt sie **nicht aus der Historie**.

Besonderheit: Der FMP-Schlüssel funktioniert nachweislich nicht mehr (beide
Endpunkte antworten nicht). Er ist also ein Risiko ohne jeden Nutzen.

*Empfehlung:* FMP-Schlüssel ersatzlos entfernen. Finnhub-Schlüssel neu
ausstellen und nur noch über Umgebungsvariable oder `secrets.toml` setzen.

## S1 — Gespeichertes `None` von „nicht gefunden" nicht unterscheidbar
**Muster M4 · niedrig · behoben**

`set_anreicherung(t, art, None)` schrieb erfolgreich, `get_anreicherung`
lieferte `None` — genau wie bei einem fehlenden Eintrag. Ein Aufrufer mit
`if ... is None: neu_berechnen()` hätte bei jedem Lauf neu gerechnet.

*Behoben:* `None` wird gar nicht erst gespeichert.

## S2 — Leerer Ticker erzeugt Mülleintrag
**niedrig · behoben**

`set_anreicherung("", "conversion", ...)` legte einen Eintrag unter dem
Schlüssel `conversion:` an. Ein Fehler weiter oben hätte still Datenmüll
erzeugt.

*Behoben:* leerer Ticker wird abgewiesen.

---

## Geprüft und in Ordnung

**`config.py`** — 0 begründungspflichtige Zahlen. Die Schlüsselauflösung
(Umgebungsvariable → `secrets.toml` an drei Orten → Rückfall) ist korrekt und
meldet über `schluessel_quelle()` selbst, woher ein Wert kam.

**`store.py`** — alle geprüften Randfälle korrekt: leeres Dict, Marker-Logik
in allen drei Varianten (passend, abweichend, keiner), Altersgrenze exakt an
der Schwelle.

---

## M-1 — Zwei widersprechende Gate-Systeme
**Muster M5 · mittel · behoben**

`scorecard.evaluate()` prüfte sechs eigene Pflicht-Gates,
`kandidat.gate_pruefen()` acht andere. Derselbe Titel konnte in der
Einzelanalyse „Kaufkandidat" sein und im Screener ausgeschlossen werden.

Zwei Stellen im alten Code gestanden die Abnutzung selbst ein:

> „Gelockert wurde nur die Bonus-Schwelle, damit überhaupt genug Fälle für
> eine Auswertung zusammenkommen"

> „wodurch das Kriterium ohnehin fast immer 'bestanden' war – es filterte also
> praktisch nichts"

*Behoben:* Neues Modul `pruefung.py` ruft dieselben Gates auf wie der
Screener. Matrix 1 entfällt (Inhalte stehen in Finanzlage, Forensik und
Momentum), aus Matrix 2 bleibt das fundamentale Momentum als Bonuskriterium.
`BONUS_FUER_KAUFKANDIDAT = 2` wird bewusst nicht gesenkt, wenn zu wenige
Kandidaten entstehen — das war der Fehler im Vorgänger.

*Offen:* `precompute.py` und `hedgefund.py` rufen `matrices` und `scorecard`
weiterhin auf. Sie gehören in denselben Umbau, aber nicht in denselben
Schritt — der Trackrecord hängt daran.

## D1 — Earnings-Call-Liste blieb nach dem Zähler stehen
**Muster M12 (Cache) + M7 (ohne Messung gebaut) · mittel · behoben**

Symptom: „85 aktuelle Calls · 115 ältere darunter" erschien, danach nichts.
Kein Fehler, keine Meldung — die Seite schien einzufrieren.

Ursache: Die gespeicherten Call-Einträge tragen nur Ticker, Datum und Quartal
— **keinen Firmennamen**. Die Tabelle löste deshalb bis zu **40 Namen
nacheinander** über `providers.get_fundamentals()` auf, jeder mit Netzabruf.

`load_firmenname` trug zwar `@st.cache_data(ttl=86400)` und der Docstring
sagte „24h gecacht" — aber dieser Cache ist **prozessgebunden und nach jedem
App-Neustart leer**. Genau nach einem Neustart trat der Fehler auf.

*Behoben:*
- Namen liegen jetzt im dauerhaften Speicher (`store`, 365 Tage). Einmal
  aufgelöst, überleben sie jeden Neustart.
- Budget von 40 auf 12 je Durchlauf gesenkt.
- Spinner während der Auflösung, plus Hinweis, wie viele Namen noch fehlen.

Wirkung: 40 blockierende Abrufe je Neustart → 12 beim ersten Mal, danach
keine.

*Grundproblem bleibt:* Der Nachtlauf sollte die Namen gleich mitspeichern.
Dann fällt die Auflösung in der Anzeige ganz weg. Das gehört zu `precompute`
und damit in Stufe 6 des Audits.

## K1 — Aufruf einer Funktion, die es nicht gibt
**Muster M13 (Anzeige mit eigener Logik) · hoch · behoben**

`dashboard.py` rief beim Öffnen eines Earnings Calls
`kennzahlen.transkript_kennzahlen()` auf. **Die Funktion existierte nicht.**
Ergebnis: AttributeError, die gesamte Ansicht brach ab.

Verschärfend: Wenige Zeilen darunter wird `zusammenfassung_call()` sauber mit
`hasattr()` abgesichert und im Fehlerfall eine verständliche Meldung gezeigt.
Beim Nachbarn fehlte dieselbe Absicherung — also fiel nicht ein Teil aus,
sondern alles.

*Behoben:*
- `transkript_kennzahlen()` in `kennzahlen.py` ergänzt: Zeichen, Wörter,
  Lesedauer, Anteil des Frageteils. Bewusst rein beschreibend, ohne
  Stimmungsdeutung.
- Alle drei `_kt`-Aufrufe im Dashboard sind jetzt mit `hasattr()` abgesichert
  (`transkript_kennzahlen`, `zusammenfassung_call`, `kernstellen`).
- `kennzahlen.py` in `pruefe_dateistand.py` aufgenommen, damit eine fehlende
  Funktion künftig vor dem Start auffällt statt beim Klick.

*Beobachtung fürs Audit:* Dass eine Funktion aufgerufen wird, die nie
existierte, deutet auf einen abgebrochenen Umbau. In Stufe 8 gehört ein
systematischer Abgleich dazu: jeder Modulaufruf im Dashboard gegen die
tatsächlich vorhandenen Funktionen.

## V1 — `justified_pe` rechnete auf der Prognose statt auf dem Ergebnis
**Muster M1 (falsche Größe benutzt) · mittel · behoben**

`justified_pe` bezog sein EPS über `_eps()`, und das liefert
`eps_forward or eps_trailing` — also die Analystenschätzung, sobald eine
vorliegt. Bei Adobe (trailing 14,70 / forward 20,60) ergab das **+109 % statt
+49 %** zum Kurs. Der Wert wurde als unplausibel verworfen, und **30 %
Methodengewicht fielen weg** — der Fair Value stand danach auf drei statt
vier Verfahren.

Zwei Gründe, warum dort das laufende Ergebnis gehört:

1. Die Methode fragt „welches KGV verdient dieses Geschäft?" und wendet es auf
   den Gewinn an. Mit einer Prognose wird daraus ein Forward-Verfahren — und
   dupliziert `fwd_pe`.
2. `eps_forward` ist der Analystenkonsens. Nutzt `justified_pe` ihn, stammt
   ein Teil des Werts aus dem Markt, während die Herkunftszerlegung ihn als
   reine Multiple-Annahme ausweist. **Die Aufschlüsselung „47 % Multiple ·
   28 % Markt · 25 % Cashflow" war dadurch falsch.**

*Behoben:* Neue Funktion `_eps_ist()` liefert ausdrücklich `eps_trailing`.
`peg_ratio` bleibt bei `_eps()` — dort ist die Prognose sachlich richtig.

### Der Preis dieser Korrektur

Sie hilft nicht in jedem Fall. Gemessen an vier Konstellationen:

```
Fall                       alt (forward)      neu (trailing)
Adobe-artig (fwd >> ttm)   556  (+109 %)      397  ( +49 %)   besser
stetig      (fwd ~ ttm)    278  ( +55 %)      265  ( +47 %)   leicht besser
Erholung    (fwd << ttm)   216  ( +44 %)      324  (+116 %)   SCHLECHTER
Verlustjahr                       —                  —        unverändert
```

Bei einem Titel mit fallenden Gewinnen rechnet die Methode jetzt auf dem
höheren Altgewinn und wird optimistischer. Das ist die logische Folge und
kein Versehen: `justified_pe` sagt „auf Basis des Erwirtschafteten verdient
die Firma dieses KGV". Dass die Gewinne fallen, bilden `fwd_pe` und der DCF
ab — dafür gibt es mehrere Verfahren.

Ob die Korrektur netto hilft, hängt davon ab, wie viele Titel in welcher
Konstellation stehen. **Das ist mit dem eingefrorenen Datensatz aus
`audit_harness.py` messbar** und gehört in Stufe 3.

### Nicht behoben: die KGV-Leiter selbst

Sie addiert Sockel 7 + Stabilität max 3 + Burggraben max 14 + Wachstum max 9,
gedeckelt bei 42. Woher die 7 kommen und warum ein Burggraben genau 14 Punkte
wert ist, steht nirgends. `hist_pe_median` liegt im Datensatz vor und wird
**nicht benutzt** — das Modell sagt „27 wäre fair", während der Titel bei 12,9
handelt und historisch bei 38 stand. Keine der beiden Beobachtungen fließt ein.

Das ist Muster M2 und gehört in Stufe 3. Ich habe es bewusst nicht nebenbei
geändert: `justified_pe` trägt 30 % Gewicht in zwei von vier Playbooks, und
eine neue Ankerlogik verschiebt jeden Fair Value im Bestand.

## V2 — Folgefehler aus V1: `fwd_pe` brach mit TypeError ab
**Muster M4 · hoch · behoben**

`fwd_pe` rechnete `eps1 * justified_pe_number(fund, preset)`. Nach der
Umstellung von `justified_pe_number` auf `eps_trailing` (Befund V1) gab diese
Funktion `None` zurück, sobald **kein positives laufendes Ergebnis** vorlag —
also genau bei Turnarounds mit Verlust im laufenden Jahr und positiver
Prognose. `eps1 * None` bricht mit TypeError ab.

Getroffen hat es den Long-Short-Suchlauf: Über viele Titel ist so einer schnell
dabei, und die ganze Seite fiel aus.

**Mein Fehler bei V1: Ich habe die Aufrufer nicht geprüft.** Die Änderung war
inhaltlich richtig, aber `justified_pe_number` hatte einen zweiten Nutzer, der
den Multiplikator ohne die EPS-Bedingung brauchte.

*Behoben:* Die KGV-Leiter steht jetzt als eigene Funktion `faires_kgv()` —
sie hängt nicht am EPS, sondern an Rentabilität, Marge, Verschuldung und
Wachstum. Jede Methode entscheidet selbst, worauf sie den Multiplikator
anwendet:

```
justified_pe -> laufendes Ergebnis (eps_trailing)
fwd_pe       -> erwartetes Ergebnis (eps_forward)
```

`justified_pe_number` bleibt als dünne Hülle bestehen, weil mehrere Stellen
diesen Namen benutzen.

*Gegenprobe:* 400 zufällig erzeugte Titel über alle vier Playbooks, mit
fehlenden, negativen und Null-Werten in jedem Feld — kein Abbruch. Zusätzlich
ein AST-Durchlauf über `valuation.py`: keine weitere Stelle, an der das
Ergebnis einer möglicherweise `None` liefernden Funktion ungesichert
weitergerechnet wird.

*Lehre fürs Audit:* Frage 5 des Prüfschemas („Wo wird still gescheitert?")
reicht nicht. Es braucht eine sechste: **Wer ruft diese Funktion sonst noch
auf, und verträgt der die neue Rückgabe?**

## W1 — `ROIC_API_KEY` fehlt im GitHub-Workflow
**Muster M4 · hoch · Änderung liegt bei dir (Workflow-Datei)**

Der `env:`-Block des Nachtlaufs übergibt `FINNHUB_API_KEY`, `FMP_API_KEY`,
`TIINGO_API_KEY` und `ANTHROPIC_API_KEY` — **aber nicht `ROIC_API_KEY`.**

`config._key()` liest Umgebungsvariable → `secrets.toml` → Rückfall. In der
GitHub-Umgebung gibt es keine `secrets.toml`, und für roic ist kein Rückfall
hinterlegt. Also läuft der gesamte Nachtlauf ohne roic:

- keine Jahresabschlüsse → keine Forensik (Piotroski, Altman, Beneish)
- keine Bewertungshistorie, keine Cash-Conversion
- keine Earnings-Call-Erkennung
- `providers.get_fundamentals(deep=True)` fällt auf yfinance + Finnhub zurück

**Folge:** Die im Sheet abgelegten Scores stammen aus anderen Daten als die
Einzelanalyse, die lokal mit roic rechnet. Derselbe Titel bekommt zwei
verschiedene Bewertungen, je nachdem wo man hinsieht — dieselbe Klasse Fehler
wie Befund M-1 (zwei Gate-Systeme), nur eine Ebene tiefer.

*Zu prüfen:* Ob das Secret in GitHub überhaupt hinterlegt ist. Falls nicht,
zuerst anlegen.

## W2 — Zeitplan-Kommentare beschreiben drei verschiedene Zustände
**Muster M13 · niedrig · Änderung liegt bei dir**

```
Kopfkommentar   "2x taeglich" (05:15 und 14:15 UTC)
Zweiter Block   "Alle 4 Stunden" (2,6,10,14,18,22 UTC)
cron            "0 6 * * *"  ->  EINMAL taeglich, 06:00 UTC
```

Beide Kommentare beschreiben Zustände, die es nicht gibt. Wer den Lauf ändern
will, orientiert sich an einer der beiden Beschreibungen und liegt falsch.

*Sachlich richtig ist der cron:* Einmal täglich reicht. Der Lauf berechnet
Jahresabschluss-Kennzahlen, Scores und Sektormediane — nichts davon ändert
sich innerhalb eines Tages. Die Sektormessung ersetzt zudem einen Eintrag
desselben Tages, statt ihn anzuhängen: Vier Läufe ergäben **einen**
gespeicherten Punkt bei vierfachem API-Verbrauch.
