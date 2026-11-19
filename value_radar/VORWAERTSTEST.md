# Vorwärtstest Fair Value gegen 12M-Ziel

Stand 19.11.2026, Methode `fv_vs_target_forward_v1` (`value_radar/forward_test/forward_test.py`, Workflow `forward-test.yml`).

## Frage

Wenn Fair Value und 12-Monats-Ziel in entgegengesetzte Richtungen zeigen (Beispiel: Fair Value −14 %, Ziel +12 %), welches Modell hatte recht? Das ist ein Vorwärtstest: Es werden nur Prognosen gewertet, die vor der Kursbewegung gespeichert waren. Rückwirkend gerechnete Werte werden nicht gewertet.

## Regeln (Entscheidungen des Nutzers, 19.11.2026)

| Regel | Wert | Konstante |
|---|---|---|
| Auswahl | FV und Ziel gegenläufig, je mindestens 5 % vom Kurs | `MIN_ABSTAND = 0.05` |
| Zeiträume | 1, 3, 6, 12 Monate (30/91/182/365 Tage) | `HORIZONTE` |
| Späterer Stand | erster Stand ab dem Zieldatum, höchstens 10 Tage danach | `TOLERANZ_TAGE = 10` |
| Kurs | split-bereinigt mit den Splits der Ergänzungsdatei derselben Notierung (`splits`, Datum im Zeitraum) | `splitfaktor` |
| Marktabgleich | Rendite relativ zum Median aller Titel der Region (USA, Japan, Großbritannien, Europa ohne GB, sonstige), mindestens 20 Titel | `MIN_REGION = 20` |
| Wertung | marktbereinigt > +2 %: Recht hat das Modell, das nach oben zeigte; < −2 %: das andere; dazwischen unentschieden | `UNENTSCHIEDEN = 0.02` |
| Stände | ein Stand je Kalendertag, vorhandene werden nie überschrieben | `speichern` |

## Offen statt falsch

Ein Eintrag wird für einen Zeitraum nicht gewertet und mit Grund gezählt bei:

- **kein späterer Kurs**: Titel aus dem Universum gefallen (Übernahme, Delisting, Indexwechsel);
- **Währung verschieden** oder **ISIN verschieden**: Identitätsbruch der Notierung;
- **Kurssprung ohne Splitnachweis**: Kursänderung unter −50 % oder über +100 % ohne Split in der Ergänzungsdatei (möglicher fehlender Split; ein echter Absturz bleibt so ebenfalls offen und wird gezählt);
- **Region mit weniger als 20 Titeln**: kein belastbarer Marktabgleich.

Fehlt für einen fälligen Zeitraum ein Stand innerhalb von 10 Tagen nach dem Zieldatum, steht das unter `ohne_passenden_spaeteren_stand`.

## Kohorten und Methode

- `aktuell`: Stände ab 19.11.2026, laufend vom Workflow abgelegt (nach jedem precompute und täglich 09:41 UTC als Rückfall).
- `vorversion`: Stände vom 13. bis 18.11.2026, aus der Git-Historie von `cf_universum.json` rekonstruiert (je Kalendertag der letzte Commit, Commit und sha256 in `quelle`). Ein 12M-Ziel (`target_12m`) steht erst seit dem 13.11.2026 im Universum. Davor gab es nur `target_mean` (Analystenziel); das ist ein anderes Modell und wird nicht ersatzweise verwendet. Die 34 Stände vom 28.09. bis 12.11. haben deshalb keine Einträge und werden nicht gespeichert.
- Kohorten werden nie zusammengezählt. Zusätzlich trägt jeder Eintrag einen Methoden-Fingerabdruck (Scanner-Methode, `value_inputs`-Version, Vorhandensein von `eps_basis`, `terminal_growth`, `risk_free`, `roic_history_status`); die Auswertung zählt je Fingerabdruck (`nach_methode`). Der Fingerabdruck erkennt nur Regeln, die ein eigenes Feld schreiben; reine Rechenänderungen ohne neues Feld trennt er nicht.

## Dateien

- `daten/forward_test/staende/<Datum>T<Zeit>.json`: Einträge (Notierung, ISIN, Währung, Region, Kurs, FV, Ziel, beide Abstände, welches Modell nach oben zeigte, `fv_reliable`, `kauf_urteil`, `playbook`, Fingerabdruck) und kompakte Kurse aller Titel (`kurse_felder`: Kurs, Währung, ISIN, Region). Etwa 170 KB je Stand, gepackt rund 35 KB.
- `daten/forward_test/index.json`: Liste der Stände (Datei, Stand, Kohorte, Anzahl, sha256), die Regeln und die Splits seit dem ältesten Stand aus den Ergänzungsdateien. Die App liest ihn für den Tab „Vorwärtstest“.
- `daten/forward_test/ergebnis.json`: je Kohorte und Zeitraum Anzahl Wertungen, verschiedene Titel, FV recht, Ziel recht, unentschieden, Anteil FV unter den entschiedenen, Median marktbereinigt, Aufteilung danach, welches Modell nach oben zeigte, offene Gründe.

## Anzeige in der App (Tab „Vorwärtstest“)

Seit 19.11.2026 zeigt die App jeden gespeicherten Stand gegen den heutigen Kurs. Als „heute“ gilt der Kurs aus dem letzten Universum-Export, nicht ein Echtzeitkurs: Für 316 Titel gibt es keine Sammelquelle mit Echtzeitkursen, die fair nutzbar wäre.

Die App rechnet beim Lesen selbst nach (`src/lib/forward-test.ts`). Sie prüft:

- dass Regeln und Methode gleich sind wie in der Pipeline (sonst wird nicht gerechnet);
- die sha256 jedes Stands gegen den Index;
- die Gegenläufigkeit jedes Eintrags;
- Währung und ISIN;
- das Alter des heutigen Kurses (höchstens 7 Tage);
- Splits und Kurssprünge.

Das Ergebnis ist ausdrücklich ein Zwischenstand, keine Wertung. Gewertet wird nur nach den festen Zeiträumen.

Probe am 19.11. (Stände 13.–18.11. gegen die Kurse vom 19.11.): App und Pipeline zählen identisch. Beispiel Stand 13.11.: FV führt 127, Ziel führt 148, unentschieden 342, offen 1 (Keyence: Kurs 73.610 → 14.690 JPY ohne Splitnachweis in der Ergänzungsdatei).

## Grenzen und Verzerrungen

- **Keine unabhängigen Beobachtungen.** Derselbe Titel steht oft an vielen Tagen in der Auswahl, die Wertungen überlappen. Deshalb weist die Auswertung neben `n` die Zahl verschiedener Titel aus; Anteile sind keine Trefferquote mit Konfidenzintervall.
- **Einseitige Auswahl.** Am 19.11. zeigen 294 von 316 Einträgen FV nach unten und Ziel nach oben. Das Ergebnis sagt also vor allem, ob das Ziel bei Titeln über dem Fair Value recht behält. Für den umgekehrten Fall ist die Stichprobe klein (22). Die Aufteilung `nach_oben_zeigte` hält beide Fälle getrennt.
- **Momentum im Ziel.** Das 12M-Ziel enthält Analysten- und Trendanteile, der Fair Value nicht. Ein Ergebnis für das Ziel kann deshalb auch Momentum messen, nicht nur die Bewertung.
- **Ausscheider.** Übernahmen (meist Kursanstieg) und Delistings (meist Absturz) fallen als „kein späterer Kurs“ heraus. Ihre Zahl steht in `offen`.
- **Marktabgleich gleichgewichtet.** Der Median der Region ist kein Index; Sektor- und Größeneffekte sind nicht herausgerechnet.
- **Dividenden** sind nicht enthalten (Kursrendite). Bei Titeln mit hoher Ausschüttung benachteiligt das leicht das Modell, das nach oben zeigte.
- Kein Ergebnis ist eine Kauf- oder Verkaufsempfehlung.

## Messstand 19.11.2026

| Stand | Kohorte | Einträge | Ziel oben / FV oben |
|---|---|---:|---|
| 13.11. | vorversion | 618 | 553 / 65 |
| 14.11. | vorversion | 603 | 549 / 54 |
| 15.11. | vorversion | 605 | 551 / 54 |
| 16.11. | vorversion | 647 | 602 / 45 |
| 17.11. | vorversion | 310 | 288 / 22 |
| 18.11. | vorversion | 315 | 292 / 23 |
| 19.11. | aktuell | 316 | 294 / 22 |

Erste Wertung: Vorversion 1 Monat ab etwa 13.12.2026, aktuell ab etwa 19.12.2026. Die 12-Monats-Wertung beginnt im November 2027.
