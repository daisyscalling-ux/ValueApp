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
