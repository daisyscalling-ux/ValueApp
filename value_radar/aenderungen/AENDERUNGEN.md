# Größere Änderungen im Universum (Startseite, seit 25.11.2026)

**Anlass:** Analog Devices zeigte in der Einzelanalyse einen Fair Value von 504 $, im Scanner noch 182 $. Der Grund war der neue Jahresabschluss vom 24.11. Der Nutzer wünscht eine Startseite, die solche größeren Änderungen mit Grund und Quelle listet.

**Ablauf:** Workflow `aenderungen` nach jedem `precompute-3tage`, Skript `aenderungen.py`, Methode `universe_changes_v1`.
- Es vergleicht die Universumszeilen mit dem zuletzt gespeicherten Stand (`daten/aenderungen/stand.json`). Daraus schreibt es `daten/cf_aenderungen.json` mit den Einträgen der letzten 7 Tage.
- Gleiche Notierung ist Pflicht (ISIN und Währung gleich), sonst gibt es keinen Vergleich.
- Ist der Universumsstand unverändert, passiert nichts.

**Schwellen (Entscheidung des Nutzers):** Ein Titel kommt auf die Liste bei

| Kennzahl | Schwelle |
|---|---|
| Fair Value | ±10 % |
| 12M-Ziel | ±10 % |
| Composite | ±10 Punkte |
| Quantum | ±10 Punkte |
| Fair Value oder Ziel | Wechsel zwischen Wert und offen |

Eine Kursbewegung allein löst keinen Eintrag aus.

**Grund (automatisch, Entscheidung des Nutzers; mehrere möglich, nie geraten):**

| Grund | Erkennung | Quelle |
|---|---|---|
| neuer_abschluss | Stichtag des Jahresabschlusses geändert | Bericht (SEC/Yahoo) mit Veröffentlichung und Accession, nur bei passendem Stichtag und https |
| neuer_konsens | Prognose-EPS ±5 %, Status/Methode geändert, oder Analystenziel ±5 % | Yahoo Analysten |
| phase / modell | Unternehmensphase oder Bewertungsmodell gewechselt | – |
| methode | Fingerabdruck der App-Kopien (Rechenweg) geändert | Vergleich der Commits auf GitHub |
| daten | Gewinn oder Buchwert je Aktie ±5 % ohne neuen Abschluss, oder Aktienbasis geändert | – |
| kernmethoden / methodenwert | andere Methoden im Kern des Fair Value (Plausibilitäts- und Median-Filter), sonst eine Methode ±10 % | – |
| ziel_teil | Teil des 12M-Ziels ±10 % (fundamental, Analysten, Momentum) | – |
| kategorie | Teilscores ±10 Punkte (bei Composite/Quantum) | – |
| kurs | Kurs ±10 % | – |
| unbekannt | keine Regel passt: „Grund nicht erkannt“ | – |

**Probelauf:** Stände von main nacheinander verglichen, 23. → 24. → 25.11.2026.
- 24.11.: 55 Titel, 2 ohne erkannten Grund. Diesen Tag prägten die Methodenänderungen (Phase, Leasing); im Probelauf war der Fingerabdruck gleich, im echten Lauf erscheint „methode“.
- 25.11.: 37 Titel, 1 ohne erkannten Grund.
- Häufigste Gründe: wechselnde Kernmethoden (14), Teil des 12M-Ziels (15), neuer Konsens (7).
- Dateigröße nach 2 Tagen 40 KB.
- In der ersten Fassung (nur Abschluss, Konsens, Phase, Methode, Kurs) blieben 24 von 37 Einträgen ohne Grund. Danach kamen Kernmethoden, Datenkorrektur, Teile des Ziels und Teilscores dazu.

**Grenzen:**
- Nur Kontext: `scoreContribution` 0, kein Kauf- oder Verkaufssignal.
- Der Grund beschreibt, welche Eingänge sich bewegt haben. Ob eine Änderung inhaltlich gerechtfertigt ist, prüft die Liste nicht.
- Der erste Lauf legt nur den Stand an.

**Tests:** `test_aenderungen.py` prüft:
- Schwellen genau an der Grenze und den Wechsel offen ↔ Wert;
- neuer Abschluss mit Quelle (ADI-Fall), dabei keine Datenkorrektur gemeldet;
- unveränderter Stand und das Fenster von 7 Tagen;
- andere ISIN;
- Methode mit Vergleichslink, Kernmethoden, Kurs, „unbekannt“;
- Datenkorrektur;
- Quelle nur bei passendem Stichtag und https;
- fehlendes Universum.
