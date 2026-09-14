# Audit-Plan Value Radar

Vollständige Prüfung aller Module: Werden die Daten benutzt, wofür sie gedacht
sind? Sind die Rechenwege richtig? Stimmt, was angezeigt wird?

---

# TEIL 1 — Was zu prüfen ist

**77 Module, 34.620 Zeilen.** Nicht alles davon verdient dieselbe Sorgfalt.

| Kategorie | Module | Zeilen | Prüftiefe |
|---|---:|---:|---|
| Kern-Bewertung | 7 | 4.700 | **vollständig, Zeile für Zeile** |
| Datenbeschaffung | 7 | 5.183 | **vollständig** |
| Entdeckung | 7 | 3.518 | vollständig |
| Portfolio/Betrieb | 8 | 4.258 | Rechenwege vollständig, Rest stichprobenartig |
| Messung | 4 | 1.963 | vollständig (sie ist der Schiedsrichter) |
| Konfiguration | 2 | 398 | vollständig |
| Oberfläche | 6 | 10.173 | **anders** — siehe unten |
| Einweg-Diagnose | 36 | 4.350 | **gar nicht** — siehe Teil 6 |

## Risikorangfolge nach Abhängigkeit

Ein Fehler wiegt so schwer, wie viele Module ihn erben:

```
providers    31 abhängige Module
valuation    30
roic         20
config       12
store        10
scoring       9
```

**Diese fünf zuerst.** Ein falsches Feld in `providers` verfälscht jede
Bewertung, jeden Screener-Lauf, jedes Portfolio — und war in dieser Sitzung
schon dreimal die Ursache.

## Sonderfall Oberfläche

`dashboard.py` hat 8.631 Zeilen und 148 Funktionen. Eine zeilenweise Prüfung
wäre wochenlange Arbeit mit geringem Ertrag: Anzeigefehler sind sichtbar,
Rechenfehler nicht. Für die Oberfläche gilt deshalb ein anderer Maßstab —
geprüft wird ausschließlich, **wo dashboard.py selbst rechnet oder Daten
umformt**, nicht wie es zeichnet.

Erster Schritt dort: alle Stellen finden, an denen im Anzeigecode gerechnet
wird. Jede davon gehört eigentlich in ein Rechenmodul.

---

# TEIL 2 — Wonach gesucht wird

Ein Audit ohne Fehlermodell wird zum Durchlesen. Die dreizehn Defekte dieser
Sitzung sind das beste verfügbare Modell dafür, welche Fehler dieser Code
tatsächlich hat. Nach genau diesen Mustern wird gesucht.

### M1 — Falsche Größe benutzt
`revenue_growth_next or earnings_growth`: Gewinnwachstum als Anker für
Umsatzwachstum. Zwei verschiedene Größen, eine Variable.

*Suchmuster:* Rückfallketten mit `or`, in denen die Alternativen nicht
dieselbe Einheit haben. Jede Zuweisung, bei der Name und Inhalt auseinander
gehen können.

### M2 — Versteckte Annahme im Rechenweg
Der Plausibilitätsfilter war am Kurs verankert (`0,25×–4×`) und unterstellte
damit, dass der Markt ungefähr recht hat — bei einem Zykliker am Gipfel genau
verkehrt.

*Suchmuster:* Konstanten in Vergleichen. Jede Zahl im Code, die eine Annahme
über die Welt enthält, muss benannt und begründet sein.

### M3 — Einzelindikator als hartes Ausschlusskriterium
Beneish und Altman haben bekannt hohe Fehlalarmquoten und schlossen trotzdem
allein aus. NVIDIA, Eli Lilly, Smucker, Occidental.

*Suchmuster:* Jedes `if kennzahl > schwelle: return None` oder
`raus.append(...)`. Frage: Trägt diese eine Zahl die Entscheidung?

### M4 — Systemausfall als Titeleigenschaft gewertet
Ohne roic fiel Piotroski bei 24 von 24 Titeln aus, und das Gate wertete das
als Mangel der Titel.

*Suchmuster:* Fehlerbehandlung, die `None` zurückgibt, wo der Aufrufer nicht
zwischen „kein Wert" und „keine Verbindung" unterscheiden kann.

### M5 — Stille Wirkungslosigkeit
Das Reverse-DCF-Gate durfte bei 30 von 30 Titeln nicht greifen. Von außen sah
das aus wie ein Gate ohne Beanstandung.

*Suchmuster:* Jede Bedingung, die in der Praxis nie oder immer zutrifft. Zähler
einbauen und einen echten Lauf messen.

### M6 — Unbelegte Datenannahme
Der Korridor war für 3J/5J/10J entworfen. Beide Quellen liefern fünf Jahre.

*Suchmuster:* Jeder `limit=`-Parameter, jede Annahme über Reihenlänge. Gegen
die tatsächliche Antwort prüfen, nicht gegen die Dokumentation.

### M7 — Optimiert ohne zu messen
Zweimal an der falschen Stelle. 87 % der Laufzeit lagen woanders.

*Suchmuster:* Caches, Nebenläufigkeit, Sparfassungen — jede davon braucht eine
Messung, die ihren Nutzen belegt.

### M8 — Identitätsverwechslung
`BAC-PB` (Vorzugsaktie) als Bank of America bewertet.

*Suchmuster:* Überall dort, wo Ticker oder Namen zusammengeführt, verglichen
oder aufgelöst werden.

### M9 — Näherung statt Rechnung
`ch_1y - ch_1m` statt `(1+r₁)/(1+r₂)-1`. Fehler 21,7 Prozentpunkte bei
starken Bewegungen.

*Suchmuster:* Kommentare mit „Näherung", „reicht für", „grob". Jede
Subtraktion von Prozentwerten.

### M10 — Normalisierung, die Abwesenheit belohnt
Der Radar-Ereignisscore normalisierte auf die aktiven Ebenen — ein Signal wog
mehr als vier.

*Suchmuster:* Jede Division durch eine Summe, die von der Datenlage abhängt.

### M11 — Nicht monotone Kombination
`max(a, b + 0.45·a) × 1.22 + c`. Man kann nicht sagen, was ein Punkt bedeutet.

*Suchmuster:* Multiplikatoren auf gedeckelte Werte, `max()` über
unterschiedlich skalierte Größen, Zuschläge nach der Deckelung.

### M12 — Zwischenspeicher liefert Überholtes
Lückenhafte Daten galten als vollständig und wurden eine Stunde festgeschrieben;
Anreicherungen überlebten Quartalsberichte.

*Suchmuster:* Jeder Cache. Frage: Was macht den Eintrag ungültig — und wird
das geprüft?

### M13 — Anzeige weicht von der Rechnung ab
Das Diagnoseskript zählte nach alten Ankernamen weiter und meldete „2 Anker",
während der Korridor auf fünf stand.

*Suchmuster:* Jede Stelle, an der die Anzeige eine eigene Kopie der Logik hat,
statt das Ergebnis zu lesen.

---

# TEIL 3 — Wie geprüft wird

Für jedes Modul dieselben sieben Fragen, in dieser Reihenfolge:

**1. Was soll es tun?** Docstring gegen tatsächliches Verhalten. Wo beides
auseinandergeht, ist mindestens eines falsch — oft die Absicht, nicht der Code.

**2. Welche Daten kommen herein?** Für jedes gelesene Feld: Einheit, Quelle,
Wertebereich, Verhalten bei `None`, bei `0`, bei negativ. Die
`_MUSS_POSITIV`-Lücke in `valuation` war genau hier.

**3. Ist jede Konstante begründet?** Jede Zahl im Rechenweg wird aufgelistet
und muss eine Herkunft haben: Fachliteratur, Messung oder ausdrückliche
Setzung. „Fühlt sich richtig an" ist keine.

**4. Was passiert an den Rändern?** Null, negativ, fehlend, extrem groß,
Finanzwerte, Verlustjahre, Währungswechsel, Zweitnotierungen. Für jeden Rand
ein Testfall.

**5. Wo wird still gescheitert?** Jedes `except: pass`, jedes `or 0`, jedes
`.get(x, standard)`. Frage: Merkt der Aufrufer, dass etwas fehlte?

**6. Stimmt das Ergebnis?** Gegen eine unabhängige Quelle — Handrechnung,
Geschäftsbericht, ein zweites Werkzeug. Nicht gegen den eigenen Code.

**7. Wirkt es überhaupt?** Zähler auf jede Verzweigung, echter Lauf über 100+
Titel. Zweige, die nie oder immer greifen, sind verdächtig.

## Werkzeug zuerst

Vor dem ersten Modul entstehen drei Hilfsmittel, sonst wird das Audit zum
Lesen:

**`audit_harness.py`** — lädt einen festen Satz von 40 Titeln (breit gestreut:
Qualität, Zykliker, Finanzwerte, Verlustfälle, ADRs, Nebenwerte, ein
Delisting) einmal aus dem Netz und legt die Rohdaten als Datei ab. Danach läuft
jede Prüfung offline, reproduzierbar und ohne API-Verbrauch. **Ohne diese
Grundlage ist kein Ergebnis wiederholbar.**

**`audit_zweige.py`** — instrumentiert ein Modul und zählt, wie oft jede
Verzweigung genommen wurde. Findet M5 (stille Wirkungslosigkeit) und toten
Code.

**`audit_konstanten.py`** — zieht alle Zahlenliterale aus einem Modul und
listet sie mit Fundstelle auf. Grundlage für Frage 3. Bei `valuation.py` sind
das erfahrungsgemäß über hundert.

---

# TEIL 4 — Reihenfolge

Geprüft wird von unten nach oben: erst die Quellen, dann die Rechnung, dann
die Auswahl, zuletzt die Anzeige. Ein Fehler in `providers` würde sonst jede
höhere Prüfung verfälschen.

### Stufe 0 — Werkzeug und Datensatz *(1 Tag)*
Die drei Hilfsmittel oben, 40-Titel-Datensatz eingefroren.

### Stufe 1 — `config`, `store`, `gsheet` *(0,5 Tage)*
Klein, aber 12 bzw. 10 Module hängen daran. Schlüsselauflösung,
Cache-Invalidierung, Backend-Wechsel Datei/Sheet. Die Uneinigkeit zwischen
`precompute` (Sheet) und lokalen Skripten (Datei) ist hier zu klären.

### Stufe 2 — `roic`, `providers` *(3–4 Tage)*
Das Herzstück und die größte Fehlerquelle. 3.931 Zeilen.

- Feldabbildung: Für **jedes** der ~55 Felder aus `bundle()` prüfen, ob der
  roic-Feldname das enthält, was der Zielname behauptet. Stichprobe gegen
  einen echten Geschäftsbericht.
- Währungsumrechnung: `_ABSOLUT`-Liste vollständig? Welche Felder fehlen?
  Ein je-Aktie-Wert, der nicht umgerechnet wird, verfälscht das KGV.
- Quellenpriorität: Tut `_merge_sources` wirklich, was der Kommentar sagt?
- Alle `limit=`-Parameter gegen die tatsächliche Antwortlänge (M6).
- Cache-Invalidierung (M12).
- Zweitnotierungen, Vorzugsaktien, ADRs (M8).

### Stufe 3 — `valuation` *(3 Tage)*
2.441 Zeilen, 60 Funktionen, 30 abhängige Module.

- Jede der acht Bewertungsmethoden einzeln gegen eine Handrechnung.
- DCF: Diskontierungsformel, Terminalwert, Nettoschuldenabzug — an einem
  Beispiel mit Papier nachgerechnet.
- Alle Schwellen und Kappungen auflisten (M2). Warum 0,25×? Warum 16 %
  Wachstumsdeckel? Warum Exit-Multiple 20,8?
- `classify_playbook`: Wie viele Titel landen je Playbook? Ein Playbook, das
  nie greift, ist ein Fehler.
- WACC: Beta-Behandlung, Mindestabstand zum Terminalwachstum.
- Gewichtungen und Renormierung: Der Analystenanker wog effektiv 28,5 % statt
  15 % — gibt es weitere solche Verschiebungen?

### Stufe 4 — `scores`, `kennzahlen`, `relval`, `matrices`, `scoring`, `scorecard` *(2 Tage)*
Die Kennzahlenmodule. Jede Formel gegen ihre Quelle: Piotroski (2000),
Altman (1968), Beneish (1999), Schmidlin, Dorsey. **Formeln gegen die
Originalarbeit prüfen, nicht gegen die Erinnerung daran** — der
Schwellenwertfehler bei Beneish (−2,22 gegen −1,78) war genau das.

### Stufe 5 — Entdeckung *(2 Tage)*
`kandidat`, `screener2`, `momentum`, `radar`, `regime`, `market_screener`,
`screener_presets`. Frisch gebaut, aber `regime` (1.190 Zeilen) und
`market_screener` sind ungeprüft. Die Entdopplung, die 55 % des Universums
entfernt, gehört hierher.

### Stufe 6 — Portfolio und Betrieb *(2 Tage)*
`portfolio`, `autodepot`, `hedgefund`, `precompute`, `trackrecord`.
Hier geht es um echtes Geld — Positionsgrößen, Gewichte, Kaufsignale.
`precompute` ist zusätzlich die einzige Stelle, die den Trackrecord schreibt.

### Stufe 7 — Messung *(1 Tag)*
`backtest`, `trackrecord`, `messlatte`, `these`. Der Schiedsrichter muss selbst
stimmen. Besonders: Look-ahead-Schutz im Backtest — die Vier-Monats-Regel ist
zu prüfen, nicht zu glauben.

### Stufe 8 — Oberfläche *(2 Tage)*
Nur die rechnenden Stellen in `dashboard.py`, plus `ui_bewertung`,
`bewertung_seite`, `kennzahl_kacheln`. Zusätzlich: Stimmt jede angezeigte
Einheit? Werden EUR und USD sauber getrennt? (M13)

### Stufe 9 — Aufräumen *(0,5 Tage)*
Siehe Teil 6.

**Summe: 17–18 Arbeitstage.** Das ist keine Nebenbeiarbeit.

---

# TEIL 5 — Was am Ende dasteht

Nicht ein Bericht, sondern vier Dinge:

**1. Ein Befundregister.** Je Fund: Modul, Zeile, Muster (M1–M13), Auswirkung,
Schweregrad, Korrekturvorschlag. Sortiert nach Auswirkung, nicht nach Modul.

**2. Charakterisierungstests.** Für jede geprüfte Funktion ein Test, der ihr
heutiges Verhalten festhält — auch das falsche. Erst danach wird korrigiert,
und der Test zeigt, was sich geändert hat. Ohne diesen Schritt ist jede
Korrektur ein Blindflug; genau das war der Grund für mehrere Rückschläge in
dieser Sitzung.

**3. Ein Konstantenverzeichnis.** Jede Zahl im Rechenweg mit Begründung. Das
ist mühsam und der wertvollste Teil: Es zwingt dazu, jede stille Annahme
auszusprechen.

**4. Eine Landkarte der Datenflüsse.** Welches Feld kommt woher, wird wo
umgerechnet, wo benutzt. Bei 31 Modulen, die an `providers` hängen, existiert
diese Karte heute nur in Fragmenten.

---

# TEIL 6 — Was nicht geprüft, sondern gelöscht wird

**36 Module, 4.350 Zeilen sind Einweg-Diagnoseskripte.** `roic_v3_sonde.py`,
`roic_v3_sonde2.py`, `roic_v3_felder.py`, `roic_v3_uk.py`, `roic_v3_bp.py`,
`roic_ec_diagnose.py`, `roic_meta_diagnose.py`, `test_eodhd.py`,
`test_tiingo.py` und zwei Dutzend weitere. Sie wurden geschrieben, um eine
Frage zu beantworten, die längst beantwortet ist.

Sie zu auditieren wäre verschwendete Zeit. Sie liegen zu lassen ist aber auch
nicht kostenlos: Sie erschweren die Suche, verwirren beim Lesen, und man weiß
bei keinem, ob er noch läuft.

**Vorschlag:** In einen Ordner `archiv/` verschieben, nicht löschen. Wenn nach
drei Monaten keiner gefehlt hat, weg damit. Das reduziert den zu prüfenden
Bestand von 34.620 auf 30.270 Zeilen — und die Zahl der Module von 77 auf 41.

Vorher zu klären: Ein paar davon sind womöglich noch eingebunden. Der
Abhängigkeitsgraph oben zeigt keine Nutzer für die meisten, aber
`dashboard.py` importiert 27 lokale Module — das ist einzeln zu prüfen.

---

# TEIL 7 — Was dieses Audit nicht leisten kann

**Ich kann die App nicht ausführen.** `intel.py` fehlt in beiden Uploads,
deshalb lässt sich `dashboard.py` nicht importieren — nur syntaktisch prüfen.
Alles, was ich dort ändere, bleibt ungetestet im Sinne von „nie ausgeführt".
Für Stufe 8 brauche ich die Datei.

**Ein Audit findet keine Fehler in der Absicht.** Ob der Fair Value das
richtige Konzept ist, ob die Playbook-Einteilung sinnvoll ist, ob Piotroski
für Wachstumstitel taugt — das sind fachliche Fragen, keine Prüffragen. Das
Audit sagt: „Der Code tut, was er soll." Ob er das Richtige soll, entscheidest
du.

**Ohne Trackrecord bleibt die wichtigste Frage offen.** Auch ein
fehlerfreies Werkzeug kann schlechte Aktien finden. Das Audit erhöht die
Verlässlichkeit, nicht die Trefferquote. Beides zu verwechseln wäre der
größte Fehler nach all dieser Arbeit.

**Die Reihenfolge ist wichtiger als die Vollständigkeit.** Wenn nach Stufe 3
die Zeit ausgeht, sind die 30 Module geprüft, die 90 % der Fehlerwirkung
tragen. Bei umgekehrter Reihenfolge wären es die Anzeigedetails.
