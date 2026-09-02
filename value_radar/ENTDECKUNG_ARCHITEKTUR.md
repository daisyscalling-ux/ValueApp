# Entdeckungsschicht: Bestandsaufnahme, Architektur, Plan

Screener · Momentum · Radar — was da ist, was daran nicht trägt, und wie es
aussehen sollte, damit es verlässlich Kandidaten findet.

---

# TEIL 1 — Was heute da ist

| Modul | Zeilen | Aufgabe |
|---|---|---|
| `market_screener.py` | 181 | Universum beschaffen (Yahoo → FMP → eingebaute Liste) |
| `screener_presets.py` | 127 | 2 Vorlagen mit Pflicht-/Bonus-Kriterien |
| `momentum.py` | 201 | additiver 0–100-Score aus 6 Bausteinen |
| `radar.py` | 413 | 5 Signalebenen + Kombinationsformel, Themen-/Branchenlisten |
| `scoring.py` | 326 | perzentilbasierter Composite über 6 Kategorien |
| `scores.py` | 414 | Piotroski F, Altman Z, Beneish M |
| `backtest.py` | 635 | historischer Bewertungstest mit Look-ahead-Schutz |
| `trackrecord.py` | 622 | Signalaufzeichnung + Trefferbilanz |

## Der zentrale Befund

**Die Entdeckungsschicht nutzt die Bewertungsarbeit der letzten Monate nicht.**

Der Screener filtert auf `load_fundamentals(t)` — das ist der **flache** Pfad,
`deep=False`. Damit fehlen genau die Dinge, an denen wir gearbeitet haben:

| gebaut | im Screener verfügbar |
|---|---|
| roic als Primärquelle (55 Felder) | nein — `bundle_light`, 30 Felder |
| `cash_conversion` / normalisierter DCF | nein |
| Schätzgüte-korrigiertes `eps_forward` | nein |
| `datenqualitaet` (Playbook-Warnung, Methodenausfall) | nein |
| `herkunft` (Multiple- vs. Cashflow-Anteil) | nein |
| `verworfene_methoden` | nein |
| Reverse-DCF-Urteil + Korridor | nein |
| Piotroski F / Altman Z / Beneish M | nein — nur Einzelanalyse |
| Schmidlin-Kennzahlen (`kennzahlen.py`) | nein — nur Einzelanalyse |

Der Screener filtert auf `pe_forward`, `pb`, `peg` aus yfinance — also auf
genau den Feldern, deren Unzuverlässigkeit uns die letzten Tage gekostet hat.
Der Vorlagen-Screener ruft zwar `fair_value()` auf, aber auf flachen Daten:
dieselbe Wackelkonstruktion, die bei NVDA zwischen −65 % und +88 % gesprungen
ist — nur diesmal über 80 Titel gleichzeitig und ohne dass es jemand merkt.

**Das ist die Hauptbaustelle.** Alles Weitere ist nachrangig.

## Drei Module, drei unverbundene Score-Welten

- **Screener**: boolesche Tests, Ergebnis „6 von 9 Bonuskriterien"
- **Momentum**: additiver Score, 6 Bausteine, Abzüge bei RSI
- **Radar**: 5 Ebenen, Kombinationsformel mit Maximum, Teilzuschlag und
  Koinzidenz-Multiplikator
- **`scoring.py`**: Perzentilrang gegen Peers über 6 Kategorien

Vier Ranglisten, vier Definitionen von „gut", keine gemeinsame Grundlage.
Ein Titel kann im Screener durchfallen und im Radar auf Platz 3 stehen, ohne
dass sich sagen lässt, welche Aussage stimmt.

## Konkrete Schwächen, die ich beim Lesen gefunden habe

### Radar: der Ereignis-Score kann durch Abwesenheit steigen

```python
_aktiv = [(v, w) for v, w in _ev_ebenen if v > 0]
_wsum  = sum(w for _v, w in _aktiv)
ereignis_score = sum(v * w for v, w in _aktiv) / _wsum
```

Normalisiert wird auf die **aktiven** Ebenen. Ein Titel mit einer einzigen
gefeuerten Ebene — etwa ein 8-K mit Item 2.01 (45 Punkte) plus ein
News-Treffer — bekommt `events = 59`, und weil alle anderen Ebenen 0 sind,
`ereignis_score = 59 · 0,34 / 0,34 = 59`. Ein Titel mit vier soliden Ebenen
à 50 bekommt ebenfalls 50. **Ein einzelnes Signal wiegt so viel wie vier.**

Der Kommentar begründet das damit, dass fehlende Ebenen den Score nicht
„künstlich" drücken sollen. Das ist die falsche Schlussfolgerung: Beim Suchen
nach dem nächsten Micron ist die Abwesenheit von Bestätigung eine Information,
kein Datenfehler.

Darauf kommen dann noch `× 1,22` Koinzidenzbonus und `+ cat_pts`. Bei einem
Deckel von 100 laufen die guten Kandidaten alle oben zusammen — die
Trennschärfe geht genau dort verloren, wo sie gebraucht wird.

### Radar: „das nächste Micron" ist per Konstruktion unmöglich

`THEMES` ist eine handgepflegte Liste von rund 120 Tickern. Was nicht auf der
Liste steht, kann nicht gefunden werden. Die Liste enthält MU, NVDA, AVGO —
die Aktien, die man **nach** dem Lauf kennt. Der Branchen-Scan ist breiter,
filtert aber nur über `sector`/`industry` auf einem Universum von maximal
einigen Dutzend geladenen Titeln.

### Momentum: die 12-1-Näherung ist bei genau den Titeln falsch, um die es geht

```python
mom_12_1 = ch_1y - ch_1m       # additive Naeherung
```

Bei +150 % Jahres- und +20 % Monatsperformance ergibt das 130 %. Richtig wäre
`(1+1,50)/(1+0,20) − 1 = 108 %`. Der Fehler wächst mit der Bewegung — also
genau bei den Titeln, die eine Momentum-Rangliste anführen sollen.

### Momentum: keine Risikoadjustierung

Der Score misst Trendstärke, nicht Trendqualität. Momentum ohne
Volatilitätsskalierung ist genau die Variante, die 2009 kollabiert ist — und
der Modul-Docstring beschreibt diese Gefahr korrekt, ohne sie zu behandeln.
Ein Titel mit 60 % Rendite bei 25 % Vola und einer mit 60 % bei 70 % Vola
bekommen denselben Punktwert.

### Screener: „marktweit" ist es nicht

Universum bis 300 Ticker, geladen werden 60–80. Die Vorauswahl trifft damit
der Yahoo-Screener nach Marktkapitalisierung, nicht unsere Kriterien.

### Screener: zwei Vorlagen für vier Playbooks

`PRESETS` kennt „Value & Qualität" und „Turnaround / Comeback". Das
Bewertungsmodell kennt `quality`, `cyclical`, `inflection`, `financial` mit je
eigenen Gewichten und Sicherheitsmargen. Für Zykliker und Finanzwerte gibt es
keine passende Suchvorlage.

### Der Value-Trap-Filter im Screener ist drei Zeilen

`scoring._value_trap()` prüft fallenden Umsatz, fallende Marge, hohe
Verschuldung. Piotroski F, Altman Z und Beneish M — die eigentlichen
Werkzeuge dafür — laufen nur in der Einzelanalyse. Der Screener lässt also
genau die Titel durch, die das Forensik-Modul aussortieren würde.

---

# TEIL 2 — Architektur

## Leitgedanke

**Eine Pipeline, drei Suchprofile.** Nicht drei Programme mit je eigener
Vorstellung von „guter Kandidat". Screener, Momentum und Radar werden zu drei
Gewichtungen über denselben Bausteinen — so wie die vier Playbooks drei
Gewichtungen über denselben Bewertungsmethoden sind.

Der Grund ist nicht Eleganz, sondern Messbarkeit: Solange jedes Modul eigene
Zahlen erzeugt, lässt sich nicht feststellen, welches funktioniert.

## Vier Stufen

```
┌─ 1 UNIVERSUM ────────────── billig, breit ──────────────────────┐
│  Yahoo/FMP + eingebaute Liste + Watchlist + bisherige Treffer   │
│  Ziel: 500–2000 Ticker, keine Bewertung, nur Existenz           │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌─ 2 VORFILTER ───────────── flach, ~0 Kosten ────────────────────┐
│  NUR Ausschlüsse: Liquidität, Marktkap, handelbar, Kurs da      │
│  KEINE Bewertungskennzahlen — die sind hier zu unzuverlässig    │
│  Ziel: 100–300 Ticker                                            │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌─ 3 TIEFE PRÜFUNG ───────── deep=True, teuer ────────────────────┐
│  roic-Bundle · Forensik · fair_value inkl. Diagnose ·           │
│  Reverse-DCF-Urteil · Datenqualität · Momentum-Rohwerte         │
│  → ein einheitliches Kandidat-Objekt                             │
│  Ziel: 40–120 vollständig geprüfte Titel                        │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌─ 4 RANGBILDUNG ─────────── je Suchprofil ───────────────────────┐
│  Value · Momentum · Frühphase — gleiche Bausteine, andere        │
│  Gewichte, je Profil eigene Ausschlussregeln                     │
└──────────────────────────────────────────────────────────────────┘
                              ↓
                    trackrecord.record()
```

Der Bruch zwischen Stufe 2 und 3 ist die wichtigste Entscheidung: **Vorfilter
darf niemals auf Bewertungskennzahlen filtern.** Ein KGV aus dem flachen Pfad
ist keine belastbare Größe — daran zu filtern verwirft gute Titel aus
Datengründen und behält schlechte aus demselben Grund.

## Der gemeinsame Datenvertrag

Neues Modul `kandidat.py`, eine Funktion:

```python
def pruefe(ticker: str, tiefe: str = "voll") -> Kandidat
```

`Kandidat` bündelt, was es schon gibt — nichts wird neu gerechnet:

```
ticker, name, sektor, playbook
bewertung   fair_value, upside, einstieg, methoden, herkunft,
            dcf_diagnose, verworfene_methoden
kurs        reverse_dcf_analyse: impliziertes Wachstum, Korridor, Urteil
forensik    piotroski_f, altman_z, beneish_m
historie    relval.bericht: Perzentil, Rückkehrwert, Urteil
momentum    12-1 (multiplikativ), Vola-adjustiert, relative Stärke, RSI, OBV
signale     8-K-Events, EPS-Revisionen, Insider, Volumen-Spike
qualitaet   datenqualitaet, _offene_luecken, _feldquellen, basis_signatur
```

Alle vier Tabs lesen dasselbe Objekt. Ein Titel hat dann **eine** Einschätzung,
die je nach Profil anders gewichtet, aber nicht anders berechnet wird.

## Gates statt Punktabzüge

Heute wird Schlechtes durch Punktabzug bestraft (`VALUE_TRAP_PENALTY = 20`).
Ein Titel mit exzellenten Zahlen und einem Bilanz-Warnsignal steht damit
weiterhin oben. Vorschlag: **harte Ausschlüsse vor der Rangbildung**, je Profil
verschieden streng.

| Gate | Value | Momentum | Frühphase |
|---|---|---|---|
| Datenbasis nicht `kritisch` | ✓ | ✓ | ✓ |
| Piotroski F ≥ 5 | ✓ | – | – |
| Beneish M unauffällig | ✓ | ✓ | ✓ |
| Altman Z nicht Distress | ✓ | – | Warnung |
| Reverse-DCF-Urteil ≠ „über dem Lieferbaren" | ✓ | – | – |
| Multiple-Anteil am Fair Value < 75 % | ✓ | – | – |
| Mindestliquidität | ✓ | ✓ | ✓ |

**Die erste Zeile ist die wichtigste.** Ein Titel, dessen Fair Value auf halber
Datenbasis steht, gehört in keine Rangliste — egal wie gut die Zahl aussieht.
Das ist die direkte Lehre aus dem NVDA-Fall: Dort war nicht der Wert falsch,
sondern seine Grundlage unvollständig, und niemand hat es gesehen.

## Die drei Suchprofile

### Value — „unterbewertet und solide"

Was heute fehlt und der eigentliche Gewinn wäre:

- **Reverse-DCF als Kernkriterium.** Nicht „Kurs unter Fair Value", sondern
  „was der Kurs verlangt, liegt im realistischen Korridor". Das ist die
  falsifizierbare Variante derselben Frage und deutlich robuster gegen
  Modellfehler.
- **Bewertungs-Perzentil.** Titel im unteren Drittel der eigenen 10-Jahres-
  Verteilung — annahmefrei, kein Wachstumsmodell nötig.
- **Herkunft als Filter.** Ein Fair Value zu 80 % aus Multiple-Annahmen ist
  kein Value-Signal, sondern eine Multiple-Wette.
- **Forensik als Gate** statt als Fußnote.

### Momentum — „läuft und hat Substanz"

- 12-1 **multiplikativ**, nicht additiv
- **Vola-adjustiert**: Rendite ÷ annualisierte Volatilität (Information Ratio)
- **Sektor-neutralisiert**: Rang innerhalb des Sektors, nicht absolut —
  sonst ist die Liste in Boomphasen zu 80 % eine Branche
- **Fundamentaler Boden**: kein Momentum-Titel ohne positiven operativen
  Cashflow oder mit Beneish-Auffälligkeit
- **Überhitzungs-Gate statt Punktabzug**: RSI > 85 schließt aus, statt 10
  Punkte zu kosten

### Frühphase (Radar) — „bevor der Markt reagiert"

- **Score additiv und normalisiert über ALLE Ebenen**, nicht nur die aktiven.
  Fehlende Bestätigung ist ein Malus, keine Nicht-Information.
- **Keine Multiplikatoren.** Der Koinzidenzeffekt entsteht bei additiver
  Rechnung von selbst; `× 1,22` auf einen gedeckelten Score staucht nur oben
  zusammen.
- **Dynamisches Universum statt Themenliste.** Kandidaten aus messbaren
  Merkmalen: Umsatzbeschleunigung, EPS-Revisionsschub, ungewöhnliches Volumen,
  Insiderkäufe, Marktkap unter Schwelle. Die Themenliste bleibt als
  zusätzlicher Einstieg, ist aber nicht mehr die Quelle.
- **Frische zählt.** Ein 8-K von vor drei Monaten ist kein Vorbeben. Signale
  bekommen ein Alter und einen Abschlag.

---

# TEIL 3 — Plan

## Etappe 0 — Messlatte zuerst *(halber Tag)*

**Bevor irgendetwas geändert wird.** `backtest.py` und `trackrecord.py`
existieren und werden kaum genutzt. Ohne Ausgangsmessung ist jede spätere
Verbesserung Behauptung.

- Aktuelle Trefferquote je Quelle (Screener/Momentum/Radar) aus `trackrecord`
- 30 Titel je Modul einfrieren als Vergleichsbasis
- Ergebnis: eine Zahl, gegen die alles Weitere antritt

Das ist die unbequeme Etappe, weil sie nichts verbessert. Sie ist trotzdem die
wichtigste — sonst bauen wir weiter nach Gefühl.

## Etappe 1 — `kandidat.py` *(1–2 Tage)*

Der gemeinsame Datenvertrag. Reine Bündelung, keine neue Rechnung. Danach
existiert eine Stelle, an der „was wissen wir über diesen Titel" beantwortet
wird.

## Etappe 2 — Zweistufiger Screener *(1–2 Tage)*

Vorfilter flach, tiefe Prüfung nur für Überlebende. Damit wird `deep=True` im
Screener bezahlbar: 800 Titel grob, 80 tief.

Risiko: Laufzeit. Gegenmaßnahme — Vorfilter ohne Netzabruf wo möglich, tiefe
Prüfung parallelisiert, Zwischenergebnis persistent, damit ein Abbruch nicht
alles verwirft.

## Etappe 3 — Gates *(1 Tag)*

Datenqualität, Forensik, Reverse-DCF-Urteil als Ausschluss. **Hier wird die
Trefferliste kürzer** — das ist beabsichtigt und der Punkt, an dem sich zeigt,
ob Etappe 0 gemacht wurde.

## Etappe 4 — Momentum reparieren *(1 Tag)*

Multiplikative 12-1, Vola-Adjustierung, Sektor-Neutralisierung,
Überhitzungs-Gate. Kleiner Eingriff, klar begründbar, sofort messbar.

## Etappe 5 — Radar neu *(2–3 Tage)*

Score-Formel additiv und normalisiert, Multiplikatoren raus,
Signalalter berücksichtigen, dynamisches Universum. Der größte Eingriff und
der mit dem höchsten Risiko, deshalb bewusst nach den anderen.

## Etappe 6 — Vorlagen je Playbook *(1 Tag)*

Vier Vorlagen statt zwei, abgestimmt auf `quality` / `cyclical` /
`inflection` / `financial`, mit den jeweils passenden Kennzahlen — Zykliker
über mid-cycle-Gewinn und KBV, Finanzwerte über KBV und ROE.

## Etappe 7 — Rückmessung *(halber Tag)*

Gegen Etappe 0. Wenn die Trefferquote nicht besser ist, war es keine
Verbesserung, sondern nur eine Veränderung.

---

# TEIL 4 — Was ich dabei unbequem finde

**Das Werkzeug wird strenger, die Listen werden kürzer.** Wer heute 25 Treffer
gewohnt ist, sieht danach vielleicht 6. Das ist richtig so, fühlt sich aber
nach Rückschritt an. Die Alternative — viele Treffer, von denen die Hälfte auf
lückenhaften Daten steht — ist genau das Problem der letzten Tage, nur eine
Ebene höher.

**Die tiefe Prüfung kostet Zeit.** 80 Titel mit `deep=True` sind nicht in zehn
Sekunden geladen. Ein Screener-Lauf wird Minuten dauern statt Sekunden. Der
Gegenwert ist, dass die Zahlen dann dieselben sind wie in der Einzelanalyse —
heute sind sie es nicht, und das ist der eigentliche Fehler.

**Radar bleibt der schwierigste Teil.** „Das nächste Micron finden" ist eine
Anforderung, die kein Screening zuverlässig erfüllt — sonst täte es jeder. Was
realistisch geht: früher als der Konsens auf messbare Beschleunigung
aufmerksam werden. Was nicht geht: die Aktie finden, bevor es etwas zu messen
gibt. Ich würde die Erwartung an Radar entsprechend formulieren, sonst misst
man ihn an einem unerfüllbaren Maßstab.

**Reihenfolge-Empfehlung:** Etappe 0 → 1 → 2 → 3 zusammenhängend, dann
messen, dann entscheiden, ob 4 und 5 überhaupt noch nötig sind. Es kann gut
sein, dass allein die Umstellung auf vollständige Daten plus Gates den größten
Teil des Nutzens bringt und der Rest Feinschliff ist.

---

# TEIL 5 — Stand nach Etappe 2 und 3

## Gebaut

| Datei | Zweck |
|---|---|
| `kandidat.py` | gemeinsamer Datenvertrag, Vorfilter, Gates |
| `screener2.py` | vierstufige Pipeline, Rangbildung, Trichter, Kontrolllauf |
| `screener2_lauf.py` | Kommandozeile mit `--kontrolle`, `--vergleich`, `--parallel` |
| `messlatte.py` | Etappe 0 — **noch nicht gemessen**, Trackrecord ist leer |
| `pruefe_*.py` | Diagnose für Dateistand, Beneish, Korridor, Historie |

## Was die acht Fehlersuchrunden gefunden haben

Jede Runde hat einen echten Defekt aufgedeckt, der vorher unsichtbar
Ergebnisse verzerrt hat:

1. **Gewinnwachstum als Umsatzanker** — `revenue_growth_next` existierte nie,
   der Rückfall nahm `earnings_growth`. UnitedHealth bekam einen Korridor von
   −15,7 % bis 11,4 %, Eli Lilly einen bis 95 %.
2. **Kursverankerte Plausibilität bei Zyklikern** — mid-cycle-Verfahren sagen
   bewusst 70–85 % unter Kurs und wurden dafür aussortiert. Micron: 80 % des
   Methodengewichts weg, übrig blieb das Analystenziel.
3. **Beneish und Altman als Einzelkriterien überfordert** — beide mit bekannt
   hoher Fehlalarmquote. Jetzt Ausschluss nur mit zweitem, unabhängigem Beleg
   (TATA bzw. Zinsdeckung), sonst Abzug im Rang.
4. **Piotroski-Gate bei systemweitem Forensikausfall** — ohne roic fielen 24
   von 24 Titeln durch, was nichts über die Titel aussagt.
5. **Stumme Korridorprüfung** — das Gate durfte bei 30 von 30 nicht greifen,
   sah aber aus wie ein Gate ohne Beanstandung.
6. **Fünf Jahre Historie sind das Maximum** — roic und FMP liefern nicht mehr.
   Die Anker wurden auf 1J/2J/3J/4J umgestellt statt weiter zu suchen.
7. **87 % der Laufzeit an der falschen Stelle gesucht** — zweimal optimiert,
   bevor gemessen wurde.
8. **Vorzugsaktien als Treffer** — `BAC-PB` auf Platz eins, weil die
   namensbasierte Entdopplung sie für die Bank hielt.

## Offene Punkte

**Etappe 0 fehlt weiterhin.** `trackrecord` ist leer, weil `record()` nur von
`precompute.py` aufgerufen wird. Ohne Ausgangswert lässt sich nicht sagen, ob
der neue Screener besser trifft — nur, dass seine Begründungen nachprüfbar
sind. Das ist ein Unterschied.

**39 % des Universums sind nicht bewertbar.** 57 von 146 Titeln scheitern an
„Datenbasis unzureichend" oder „Modell trägt den Titel nicht" — überwiegend
ausländische ADRs und OTC-Notierungen (TSM, Toyota, MUFG, Softbank, Tencent).
Ob das an fehlenden roic-Daten liegt oder an der Bewertungslogik, ist offen.

**Sechs von zehn Treffern sind Banken oder Versicherer.** Bei 146 geprüften
Titeln ist das keine Zufälligkeit der Prüfmenge mehr. Der Kontrolllauf hat
gezeigt: Das Ranking selbst ist sektorbreit, die Gates erzeugen die
Konzentration. Wer mit der Liste arbeitet, trifft eine Sektorwette.

**Laufzeit ist die praktische Grenze.** 20 s je Titel, 49 Minuten für 150.
Parallelisierung bringt kaum noch etwas, weil roic drosselt (2274 s Stufenzeit
gegen 2926 s Uhrzeit). Ein marktweiter Lauf über 800 Titel wäre vier Stunden.

**Die Entdopplung entfernt 196 von 354 Titeln (55 %)** und ist nie
gegengeprüft worden. Wenn sie zu aggressiv ist, verschwinden echte Kandidaten
still.
