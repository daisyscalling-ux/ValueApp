# Bewertungserweiterung für Value Radar

Sechs Bausteine aus dem AlphaSpread-Abgleich, gebaut gegen den tatsächlichen
Code — nicht mehr gegen eine angenommene Schnittstelle.

## Was sich gegenüber meinem ersten Entwurf geändert hat

Zwei Annahmen von mir waren falsch, und beide hätten den Einbau gesprengt:

**1. Das DCF-Modell.** Ich hatte Umsatz × Marge × Exit-Multiple angenommen (so
rechnet AlphaSpread). `dcf_two_stage` rechnet aber FCF-basiert mit linear
abklingendem Wachstum und Gordon-Terminal. Damit gibt es kein sichtbares
Exit-Multiple — es steckt versteckt in `(1+g)/(r−g)`. Genau das rechnet
`bewertung_x.dcf_diagnose()` jetzt aus und stellt es dem heutigen FCF-Multiple
gegenüber. Die zweite Achse im Reverse DCF ist entsprechend nicht die
Netto-Marge, sondern der **Faktor auf den heutigen Free Cashflow**.

**2. Die Optik.** `dashboard.py` ist ein dunkles Terminal-Layout
(`#0A0E14`, JetBrains Mono, Bernstein-Akzent) — und definiert bereits `.vr-card`
und `.row` global. Meine weißen AlphaSpread-Karten hätten die bestehenden Karten
überschrieben und wären mitten in einer dunklen App als Fehler gelesen worden.
Übernommen ist deshalb der **Aufbau** (Großzahl mit Vergleichsbalken,
Treiberliste, Urteilskasten, Korridorleiste, Referenztabelle, Szenario-
Umschalter), nicht die Farbwelt. Alle Klassen sind `va-` präfixiert.

Wer trotzdem hell will: `ui_bewertung.inject_css("hell")`. Die Vorschau hat
einen Umschalter in der Sidebar, damit du beides nebeneinander siehst.
Meine Empfehlung ist dunkel — ein Stilbruch auf einer von vierzig Seiten sieht
nicht nach AlphaSpread aus, sondern nach halbfertigem Redesign.

---

## Dateien

**Drei bestehende Dateien überschreiben** (Namen unverändert):

| Datei | vorher → nachher | Was dazugekommen ist |
|---|---|---|
| `valuation.py` | 984 → 1.877 Zeilen | Diagnostik, Herkunft, Szenarien, Cash-Conversion, Reverse-DCF-Korridor |
| `relval.py` | 122 → 325 Zeilen | echtes Perzentil; `historical_band()` nutzt es, wenn Jahreswerte da sind |
| `providers.py` | +30 Zeilen | `get_eps_history()` — volle EPS-Reihe statt nur letzter Überraschung |

**Drei neue Dateien:**

| Datei | Zweck |
|---|---|
| `schaetzguete.py` | Trefferquote des Konsens → Gewicht für Forward-EPS |
| `ui_bewertung.py` | Darstellung (`va-` präfixiert, kollidiert nicht mit `dashboard.py`) |
| `bewertung_seite.py` | Einbau-Funktion + eigenständige Vorschau |

Plus `test_bewertung_diagnose.py` (dein `test_bewertung.py` bleibt unberührt).

Alles läuft ohne neue Abhängigkeiten. `bewertung_x.py`, `reverse_dcf.py` und
`bewertungshistorie.py` aus der ersten Fassung gibt es nicht mehr — der Code
sitzt jetzt dort, wo die verwandte Logik schon lag.

```bash
python3 test_bewertung_diagnose.py          # Logik prüfen, kein Netzwerk nötig
streamlit run bewertung_seite.py            # Vorschau mit ETN-Zahlen
```

### Neue Namen in `valuation.py`

`herkunft` · `dcf_diagnose` · `conversion_aus_historie` · `szenario_matrix` ·
`rd_korridor` · `impliziertes_wachstum` · `implizierte_cash_basis` ·
`wachstums_anker` · `anker_aus_fund` · `reverse_dcf_analyse` · `cagr`

Die bestehende `reverse_dcf_implied_growth()` bleibt unverändert. Die neue
Analyse heißt bewusst `reverse_dcf_analyse()`, damit beide nicht verwechselt
werden — sie beantworten verschiedene Fragen (siehe unten).

### Neue Namen in `relval.py`

`perzentil` · `kgv_historie` · `ev_ebitda_historie` · `urteil` ·
`multiple_band` · `bericht`

`historical_band(f, pe_hist_werte=None)` hat einen zweiten Parameter bekommen
und gibt neu `pctile_quelle` zurück: `"gemessen (10 Jahre)"` oder
`"geschaetzt (nur Median bekannt)"`. Ohne den Parameter verhält sie sich exakt
wie vorher — alle bestehenden Aufrufe in `dashboard.py` laufen weiter.

---

## Einbau in die Einzelanalyse — erledigt

`dashboard.py` ist eingebaut: **ein Hunk, +62 Zeilen, nichts gelöscht.** Der Block
sitzt direkt vor `left, right = st.columns([1, 1])` in der Einzelanalyse.

Er rendert **inline, nicht in einem Expander**. Terminalwert-Anteil, Herkunft des
Fair Value und das Reverse-DCF-Urteil sind genau die Warnungen, die man nicht
wegklicken können soll. Nur das Wachstum-×-Cash-Gitter bleibt eingeklappt.

### So prüfst du, ob die neue Version läuft

```bash
grep -c bewertung_seite dashboard.py     # muss 2 ergeben
```

In der App erscheinen in der Einzelanalyse unterhalb der Kennzahlen-Expander
fünf neue Abschnittsüberschriften in Bernstein:

```
1  INNERER WERT
2  WOHER DER WERT KOMMT
3  REVERSE DCF  was der Kurs verlangt
4  SZENARIEN  je Methode
5  BEWERTUNGSHISTORIE  eigenes Perzentil
```

Ohne jede Historienreihe (roic aus, yfinance leer) bleiben 1, 2, 4 und ein
verkürztes 5 übrig — es ist also nie komplett leer. Darunter steht dann eine
Zeile, welche Reihen gefehlt haben und welche Abschnitte deshalb entfallen sind.

Falls du nichts siehst: App neu starten bzw. neu deployen. Streamlit lädt
geänderte Module erst beim Neustart.

### Warum die Optik trotzdem nicht in `dashboard.py` liegt

Das ist eine bewusste Abweichung von deinem bisherigen Muster — im Rest der App
steht die Darstellung direkt in `dashboard.py`. Gründe für den Schnitt:

- `dashboard.py` hat 8.673 Zeilen. Weitere 600 machen es schlechter, nicht besser.
- `ui_bewertung.py` lässt sich ohne Streamlit-Server rendern (genau so sind die
  Vorschau-HTMLs entstanden). Innerhalb von `dashboard.py` wäre das unmöglich.
- Rückbau ist eine Dateilöschung plus ein Hunk, kein Diff durch 8.700 Zeilen.

Der Preis: CSS liegt jetzt an zwei Stellen. Deshalb ist **jede Regel unter `.va`
gekapselt** — geprüft, kein einziger globaler Selektor. Insbesondere gibt es
keine `stRadio`-Regel, die sonst jeden Radio-Button der App mitgestaltet hätte.
Der Szenario-Umschalter sieht damit aus wie deine übrigen `st.radio`-Leisten
(z. B. die Zeitraumwahl im Chart).

**Achtung Sortierung:** `roic.kennzahl_historie` und `providers.get_financials`
liefern *recent first*. `reverse_dcf.wachstums_anker()` erwartet *ältester Wert
zuerst*. `reverse_dcf.anker_aus_fund()` dreht selbst.

---

## Punkt 1 — Reverse DCF mit Urteil

`valuation.reverse_dcf_implied_growth()` liefert bereits eine Zahl, aber ohne
Maßstab. Neu ist der Korridor, gegen den sie gemessen wird:

```python
anker = valuation.anker_aus_fund(fund, historie=roic.kennzahl_historie(t))
rd = valuation.reverse_dcf_analyse(fund, anker, preset)

rd["impliziertes_wachstum"]     # was der Kurs verlangt
rd["implizierte_cash_basis"]    # zweite Achse: Faktor auf den heutigen FCF
rd["korridor"]                  # tief / mitte / hoch, regime-gewichtet
rd["urteil"]                    # konservativ | fair | anspruchsvoll | zu_optimistisch
rd["zeilen"]                    # Referenztabelle
rd["gitter"]                    # Wachstum × Cash-Basis inkl. Iso-Linie
rd["beide_gestreckt"]           # True, wenn beide Treiber über der Mitte liegen
```

Der Korridor gewichtet 3J/5J/10J/Konsens nach Playbook
(`PLAYBOOK_GEWICHTE`). Bei `cyclical` und `financial` dominiert die lange
Historie, weil sie einen vollen Zyklus abdeckt; bei `inflection` der Konsens,
weil die Vergangenheit dort per Definition nicht die These ist.

Konsistenzhinweis: Mein Löser bildet die **Abkling-Struktur** von
`dcf_two_stage` ab, die bestehende Funktion rechnet mit **konstantem** g. Für
ETN: 28,2 % (Abkling) vs. 16,1 % (konstant). Beide stimmen — sie beantworten
verschiedene Fragen. Vergleichbar mit dem DCF ist nur die Abkling-Variante;
die alte bleibt als grobe Zweitmeinung nutzbar.

---

## Punkt 2 — Terminalwert-Anteil und implizites Terminal-Multiple

```python
d = v["dcf_diagnose"]
d["terminal_anteil"]        # 0.543 bei ETN
d["multiple_genutzt"]       # 15.4x — steckt in (1+g)/(r-g)
d["multiple_impliziert"]    # 58.1x — was der Kurs verlangt
d["multiple_heute"]         # 40.8x — was heute bezahlt wird
d["hinweise"]               # fertige Warntexte für die Ampel
```

`d["hinweise"]` gehört in die Zeile „Auf einen Blick", nicht in eine
aufklappbare Kachel — ab `TERMINAL_ANTEIL_WARN = 0.75` steht dort, dass das
Modell im Kern eine Multiple-Wette ist.

---

## Punkt 3 — Bear / Base / Bull je Methode

```python
m = valuation.szenario_matrix(fund, peer_funds, preset)
m["methoden"]["justified_pe"]["bull"]
m["blend"]                  # Bear/Base/Bull des geblendeten Fair Value
m["blend_konsistent"]       # nur Methoden, die in ALLEN Szenarien tragen
m["warnungen"]
```

Statt die Methoden nachzubauen, werden die **primitiven Treiber** im
`fund`-Dict verschoben (`revenue_growth`, `eps_forward`, `ebitda`,
`free_cashflow` primär; `hist_pe_median`, `ev_ebitda`, `beta` sekundär und auf
50 % gedämpft) und `valuation.fair_value()` dreimal aufgerufen. Damit bleibt die
Rechenlogik an genau einer Stelle und kann nicht abdriften.

Das Analystenziel bleibt in allen Szenarien unverändert — es ist eine externe
Konsensaussage, kein Modelltreiber. Dass es die Spanne dämpft, ist gewollt.

**Ein Fund, den der Test gehoben hat und den du kennen musst:** Bei ETN fällt
der DCF im Bear Case weg (negatives Eigenkapital), `fair_value()` renormiert die
Gewichte auf die verbliebenen Methoden — und der Bear-Wert (252,57) landet
**über** dem Base-Wert (247,02). Das ist kein Rechenfehler, sondern ein Artefakt
des Methodenausfalls. Deshalb gibt es `blend_konsistent`, das nur die in allen
drei Szenarien vorhandenen Methoden verwendet: 193,52 / 238,66 / 284,39 — monoton
und interpretierbar. Beide Zeilen werden angezeigt, samt Warnung. Das zu
verstecken wäre schlimmer gewesen, als es zu zeigen.

---

## Punkt 4 — Echtes Bewertungs-Perzentil

`relval._pctile_from_median()` schätzte das Perzentil aus dem Median und einer
**angenommenen** Streuung von 35 %. Die Funktion bleibt als Rückfall drin, aber
`historical_band()` nimmt jetzt die echten Jahreswerte, sobald sie vorliegen —
und schreibt in `pctile_quelle`, welcher Weg genutzt wurde:

```python
b = relval.bericht(fund, roic.pe_history(ticker, 10), ev_hist)
b["kgv"]["perzentil"]["teuer_pct"]    # 100.0 bei ETN
b["kgv"]["rueckkehrwert"]             # Median-KGV × EPS = 213,31
b["urteil"]                           # Attraktiv / Neutral / Unattraktiv
b["band"]                             # P25/Median/P75 für die Szenarien
```

Bei ETN liegen alte Schätzung (98.) und echtes Perzentil (100.) nah beieinander
— das ist kein Beleg für die Schätzung, sondern der Fall, in dem sie zufällig
passt. Interessant wird der Unterschied bei Titeln mit sehr enger oder sehr
weiter Bewertungsspanne, wo die 35-%-Annahme systematisch danebenliegt.

Unter vier Jahreswerten gibt das Modul bewusst **kein** Perzentil zurück,
sondern nur den Rückkehrwert. Lieber keine Zahl als eine erfundene.

**Kopplung zu Punkt 3:** `b["band"]` (bei ETN 18,5 / 21,7 / 27,7) gehört als
Bewertungsniveau in die Szenarien — dann wird es aus der eigenen Historie
abgeleitet statt gesetzt. Das war im ursprünglichen Plan nicht vorgesehen und
ist die sauberere Kopplung.

---

## Punkt 5 — Schätzgüte des Konsens

`providers.get_last_earnings_surprise()` liest bereits `earnings_dates`, wirft
aber alles außer der letzten Überraschung weg. `providers.get_eps_history()`
gibt die volle Reihe zurück; `get_last_earnings_surprise()` bleibt unverändert:

```python
q = schaetzguete.fuer_ticker(ticker)
q["sterne"]              # 1..5
q["konsens_gewicht"]     # 0.35..1.0
q["bias"]                # optimistisch | konservativ | neutral

bl = schaetzguete.geblendetes_eps(fund["eps_forward"], eps_reihe, q)
schaetzguete.anwenden_auf_fund(fund, q, eps_reihe)   # setzt eps_forward
```

Der Konsens geht bisher ungewichtet in `justified_pe`, `fwd_pe` und `hist_pe`
ein. `konsens_gewicht` stutzt ihn gegen eine log-lineare Trendfortschreibung;
bei systematisch optimistischem Konsens wird zusätzlich um die mittlere
Verfehlung korrigiert, statt nur abzuwerten — eine Schätzung, die immer 5 % zu
hoch liegt, ist nach der Korrektur brauchbar.

Untergrenze 0,35: Auch ein schwacher Konsens kennt die Guidance.

---

## Punkt 6 — Cash-Conversion sichtbar

```python
cc = valuation.conversion_aus_historie(fcf_reihe, ni_reihe)
cc["median"]      # Treiber
cc["streuung"]    # Warnsignal
cc["warnung"]
```

Die Streuung ist die quantitative Fassung von Dorseys
Cashflow-vs-Gewinn-Divergenz: eine stark schwankende Conversion ist das
Warnsignal, nicht der Mittelwert.

---

## Die Selbstkritik, jetzt gemessen

`v["herkunft"]` zerlegt den Fair Value nach Herkunft der Annahme. Für ETN im
Quality-Playbook:

| Herkunft | Anteil |
|---|---|
| Multiple-Annahmen | 53,1 % |
| **Analystenkonsens** | **28,5 %** |
| Cashflow-Prognose | 18,4 % |

Der Analystenanker ist mit 15 % vorgesehen und wiegt effektiv **28,5 %** — weil
`fair_value()` Methoden herausfiltert und die Gewichte danach renormiert. Das
stand bisher nirgends. `herkunft()["gewichtsverschiebung"]` weist jede Methode
aus, deren effektives Gewicht um mehr als das 1,5-fache vom nominellen abweicht.

Das ist der unbequeme Teil: Ein Fair Value, der zu 28 % aus dem Analystenkonsens
besteht, kann nicht mehr unabhängig gegen den Markt gemessen werden — und genau
das ist laut Kommentar in `_WEIGHTS` das erklärte Ziel des reduzierten
Analystengewichts. Die Renormierung unterläuft die eigene Absicht. Ob du die
Schwelle senkst, den Filter änderst oder das Analystengewicht bei Ausfall
anderer Methoden deckelst, ist eine Entscheidung — aber sie war bisher nicht
sichtbar.

---

## Offene Punkte

- **`revenue_growth_next`** existiert im `fund`-Dict nicht. `anker_aus_fund()`
  fällt deshalb auf `earnings_growth` zurück. Wenn `providers` einen echten
  Forward-Umsatzkonsens liefern kann, wird der Korridor besser.
- **EV/EBITDA-Historie** gibt es noch nicht als Jahresreihe;
  `bewertungshistorie.ev_ebitda_historie()` ist vorbereitet, braucht aber eine
  Quelle (roic `multiples` mit `period_type=annual` liefert sie vermutlich).
- **`test_bewertung.py`** existiert bereits im Repo und ist unberührt; meine
  Tests liegen in `test_bewertung_diagnose.py`.
- **`valuation.py` hat jetzt 1.877 Zeilen.** Das ist der Preis der
  Zusammenführung. Wenn es unübersichtlich wird, ist der Reverse-DCF-Abschnitt
  am Dateiende der natürliche Schnitt für eine spätere Auslagerung — er hat
  keine Abhängigkeit zum Rest ausser `wacc()` und `V`.

---

## Was beim Hochladen passiert

Nichts bricht durch die neuen Dateinamen. Der Grund ist mechanisch:

- **`dashboard.py` bekommt genau einen Hunk** (+62 Zeilen, nichts gelöscht).
  Alles darin steckt in `try/except`.
- **Kein bestehendes Modul importiert die neuen Dateien.** Geprüft mit
  `grep`: `schaetzguete.py`, `ui_bewertung.py` und `bewertung_seite.py` werden
  nur untereinander importiert. Für den Rest der App sind sie unsichtbar.
- **Die drei überschriebenen Dateien behalten ihre öffentliche API.**
  `historical_band()` hat einen optionalen zweiten Parameter bekommen,
  `get_last_earnings_surprise()` und `reverse_dcf_implied_growth()` sind
  unverändert. Alle 27 lokalen Importe von `dashboard.py` lösen weiter auf.

Sichtbar wird der neue Block in der Einzelanalyse unter
„🧮 BEWERTUNG IM DETAIL" (zugeklappt). Alles andere sieht aus wie vorher.

### Vollständige Änderungsliste

```
geändert:  config.py  dashboard.py  providers.py  relval.py  valuation.py
neu:       schaetzguete.py  ui_bewertung.py  bewertung_seite.py
           test_bewertung_diagnose.py  BEWERTUNG_ERWEITERUNG.md
unberührt: die übrigen 55 Dateien
```

## API-Keys

Die Fallback-Schlüssel für Finnhub und FMP stehen wieder in `config.py`, da das
Repo privat ist. `config.fehlende_keys()` ist neu dazugekommen und meldet, welche
Schlüssel nicht gesetzt sind — nützlich für eine Hinweiszeile im Dashboard.

Wenn das Repo jemals öffentlich geschaltet oder geforkt wird: beide Schlüssel
vorher entfernen **und neu ausstellen**. Ein späterer Commit entfernt sie nicht
aus der Git-Historie. Der Kommentar bei `ROIC_API_KEY` deutet darauf hin, dass
das schon einmal passiert ist.

## Laufzeit

`dcf_diagnose()` und `herkunft()` laufen jetzt bei jedem `fair_value()`-Aufruf
mit. Gemessen: 0,153 → 0,181 ms je Aufruf (+18 %). Bei einem Screener-Lauf
über 500 Titel sind das 0,01 Sekunden zusätzlich — irrelevant gegenüber der
Netzwerkzeit.

`szenario_matrix()` ruft `fair_value()` dreimal auf und wird deshalb **nur in
der Einzelanalyse** verwendet, nicht im Screener.

## Was noch nicht mit echten Daten lief

Getestet ist alles gegen ein synthetisches `fund`-Dict. Ohne Netzwerk nicht
prüfbar und daher offen:

- `providers.get_eps_history()` — braucht yfinance
- `schaetzguete.fuer_ticker()` — hängt daran
- `relval.historical_band()` mit echtem `roic.pe_history()`-Output
- der `dashboard.py`-Block als Ganzes: kompiliert und die Renderfunktionen sind
  headless geprüft, aber im laufenden Streamlit mit echten roic-Daten war er nie

---

## Bugreport: „NVDA, MU, Citi zeigen plötzlich 50 % Downside"

**Nicht die Bewertung ist falsch, es fehlen Daten.** Nachgestellt:

| NVDA | Playbook | Fair Value | Upside |
|---|---|---|---|
| mit allen Quellen | inflection | 186,53 | +3,6 % |
| ohne `revenue_growth`/`earnings_growth` | **quality** | 146,03 | −18,9 % |
| ohne FMP **und** Finnhub | quality | 88,43 | **−50,9 %** |

Der Mechanismus läuft in zwei Stufen:

1. `revenue_growth` und `earnings_growth` kommen aus FMPs `financial-growth`.
   Fehlen sie, stuft `classify_playbook()` einen Wachstumstitel als
   **Qualitätstitel** ein. Damit gelten andere Gewichte: statt
   `fwd_pe`/`fwd_composite`/`analyst` zählen `dcf` und `justified_pe`.
2. Weitere Felder fallen weg, die Methoden werden aussortiert, die Gewichte
   renormieren auf den Rest. Bei hoch bewerteten Titeln liegt dieser Rest weit
   unter dem Kurs.

Deshalb trifft es genau NVDA und MU (Wachstum, hohe Multiples) und Citi
(`financial` lebt von `pb`/`book_value_ps`), nicht aber ruhige Standardwerte.

### Ursache

Mit hoher Wahrscheinlichkeit die `config.py` aus dem Paket, in dem ich die
API-Keys auf `""` gesetzt hatte. Prüfen:

```bash
grep -n "FINNHUB_API_KEY\|FMP_API_KEY" config.py
```

Steht dort `os.getenv("FINNHUB_API_KEY", "")`, ist es die leere Fassung — dann
die `config.py` aus dem aktuellen Paket nehmen oder die Keys als
Umgebungsvariable setzen.

### Gegenprüfung

```bash
python3 diagnose_quellen.py NVDA MU C
```

Zeigt pro Titel, welche Schlüssel gesetzt sind, welche kritischen Felder
ankommen, welches Playbook daraus folgt und wie stark der Fair Value ohne die
Zusatzquellen abweichen würde.

### Damit das nie wieder still passiert

`valuation.datenqualitaet(fund, preset)` ist neu und hängt als
`v["datenqualitaet"]` im Rückgabe-Dict. Es meldet:

- welche Felder fehlen und welche Methode das lahmlegt
- wie viel Methodengewicht dadurch ausfällt
- **ob die Playbook-Einstufung auf wackligen Daten steht** — das ist die
  gefährlichste Lücke, weil sie sich nicht als Fehler zeigt, sondern als
  plausibel aussehender falscher Fair Value

Die Warnung steht im Bewertungsblock **über** der Fair-Value-Zahl, nicht
darunter. Bei NVDA ohne Zusatzquellen erscheint:

> **Datenbasis kritisch** · 55 % Gewicht fehlt
> Playbook-Einstufung unsicher: revenue_growth, earnings_growth fehlt …

Das ist unabhängig von meinen sechs Bausteinen nützlich: die Schwäche steckt in
`classify_playbook()` und war vorher genauso da, nur unsichtbar.

---

## Quellenpriorität: roic zuerst

### Korrektur meiner vorherigen Aussage

Ich hatte behauptet, roic liefere elf kritische Felder nicht. **Das war falsch.**
Ich hatte nur das Dict-Literal in `bundle()` ausgewertet und den zweiten Teil der
Funktion übersehen, in dem weitere Felder per `out["…"] = …` gesetzt werden.

Tatsächlich liefert `bundle()` **55 Felder**, darunter alle, die ich als fehlend
bezeichnet hatte: `pb`, `ev_ebitda`, `ps`, `pe_trailing`, `book_value_ps`,
`eps_trailing`, `revenue_growth`, `hist_pe_median`.

Wirklich nicht bei roic — und das bleibt so:

| Feld | Warum |
|---|---|
| `eps_forward` | Schätzung, keine Historie |
| `target_mean` | Analystenkonsens |
| `analyst_count` | Analystenkonsens |
| `beta` | Marktstatistik, keine Fundamentalkennzahl |

### Was tatsächlich fehlte — und jetzt drin ist

**1. `earnings_growth`** war als einziges der beiden Wachstumsfelder nicht
gesetzt, obwohl `income_annual(limit=2)` in `bundle()` bereits abgerufen wird.
Jetzt aus EPS zweier Abschlüsse berechnet, mit Nettogewinn als Rückfall.
Kostet keinen zusätzlichen Abruf.

**2. `bundle_light()` hatte gar kein Wachstum.** Der breite Scan läuft mit
`deep=False`, also mit dem Light-Bundle — dort fehlten `revenue_growth` und
`earnings_growth` vollständig, die Playbook-Einstufung hing damit an
yfinance/Finnhub/FMP. Genau der Pfad, der NVDA und MU auf −50 % geschickt hat.
Jetzt ein vierter Abruf (`income_annual`) und beide Felder gesetzt. Ein
400-Titel-Scan kostet 1.600 statt 1.200 Abrufe, rund 7 statt 5 Minuten.

**3. Echte Multiple-Jahresreihen.** `hist_pe_median` war bisher das
Durchschnitts-KGV des *letzten* Geschäftsjahres — als Median-Ersatz brauchbar,
aber kein Verlauf. `multiples_historie()` existierte bereits ungenutzt und
liefert zehn Jahre je KGV, EV/EBITDA, KUV und KBV. `bundle()` mappt jetzt
`hist_pe_werte`, `hist_ev_ebitda_werte` und `hist_pb_werte`.

Damit rechnet `relval.perzentil()` ein **gemessenes** Perzentil statt der
Schätzung mit angenommener 35-%-Streuung — und der offene Punkt „EV/EBITDA-
Historie fehlt noch" aus dem Abschnitt zu Punkt 4 ist erledigt.

**4. FMP nur noch für echte Lücken.** Vorher: `if deep and not R` — deckte roic
den Titel ab, lief FMP nie, auch nicht für Felder, die roic nicht führt. Jetzt
wird FMP gezielt für die vier oben genannten Felder nachgeladen, wenn sie nach
roic + yfinance + Finnhub immer noch fehlen.

### Kette

```
1. roic.bundle()        55 Felder, gewinnen feldweise gegen alles andere
2. roic.wachstum()      füllt Lücken und liefert die Mehrjahresreihen
                        (überschreibt bundle() NICHT)
3. yfinance/Finnhub     nur was roic gar nicht führt
4. FMP                  nur die danach noch fehlenden kritischen Felder
5. _offene_luecken      was auch dann fehlt, wird ausgewiesen
```

### Neue Diagnosefelder im `fund`-Dict

| Feld | Inhalt |
|---|---|
| `_feldquellen` | `{feld: "roic" \| "fmp (Luecke)" \| "yfinance/finnhub"}` |
| `_fmp_luecken` | welche Felder FMP nachgeliefert hat |
| `_offene_luecken` | was auch danach fehlt |

```bash
python3 diagnose_quellen.py NVDA MU C
```

### Offen

Der `analyst`-Anker (15 % nominal, effektiv 28,5 %) und `eps_forward` bleiben
dauerhaft von yfinance/FMP abhängig. Das lässt sich nicht über roic lösen.

### Ungetestet

Die roic-Aufrufe laufen hier nicht (kein Schlüssel, kein Netzwerk). Die neuen
Feld-Mappings sind gegen die Struktur der bestehenden `_g()`-Aufrufe gebaut und
kompilieren, aber die tatsächlichen Antwortfelder von `multiples_historie()`
habe ich nicht gegen die Live-API geprüft.


---

## „NVDA liegt immer noch bei −65 %"

### Der Wert selbst ist nicht kaputt

Mit vollständigen Daten und realistischen NVDA-Zahlen (Kurs 180, Umsatz 200 Mrd,
FCF 75 Mrd, EPS fwd 6,50) rechnet der Code:

```
Playbook inflection · Fair Value 202,09 · Upside +12,3 % · Datenbasis vollständig
   fwd_pe          225,23   (+25,1 %)   Gewicht 30 %
   fwd_composite   166,58    (−7,5 %)   Gewicht 25 %
   dcf                  --              Gewicht 30 %   <-- fällt aus
   analyst         215,00   (+19,4 %)   Gewicht 15 %
```

−65 % entsteht nur, wenn Felder fehlen: ohne `revenue_growth`/`earnings_growth`
fällt die Einstufung von `inflection` auf `quality`, und damit greifen
`dcf` (30 %) und `justified_pe` (30 %) statt der Forward-Multiples.

### Drei Pfade, drei Datenstände

Wo du die Zahl siehst, entscheidet, welcher Code überhaupt läuft:

| Ansicht | Datenquelle | betroffen von meinen Fixes? |
|---|---|---|
| Einzelanalyse | `get_fundamentals(t, deep=True)`, Cache 1 h | ja, nach App-Neustart |
| Screener / Radar / Watchlist | `store.get_snapshot()` aus `precompute.py` | **nein**, bis precompute neu läuft |
| Vergleichstabellen | `get_fundamentals(t, deep=False)` | ja, aber über `bundle_light` |

**Das ist der wahrscheinlichste Grund.** `precompute.py` läuft mit
`SCAN_DEEP = False` und schreibt Fair Value und Upside in den Store. Das
Dashboard liest sie von dort. Wurde der Snapshot erzeugt, während die Keys leer
waren oder `bundle_light` noch kein Wachstum lieferte, steht dort weiterhin
−65 % — unabhängig davon, was ich in `valuation.py` ändere.

Abhilfe: `precompute.py` einmal neu laufen lassen. Vorher `dashboard.py`
neu starten (der 1-Stunden-Cache in `load_fundamentals` und `_DEEP_CACHE`
überleben ein Browser-Reload).

### Das Werkzeug für die Antwort

```bash
python3 warum_fair_value.py NVDA            # Einzelanalyse-Pfad
python3 warum_fair_value.py NVDA --flach    # Scan-Pfad
```

Zeigt in einer Ausgabe: Schlüssel → Quellen je Feld → offene Lücken →
Einstufung samt Eingangsgrößen → **jede Methode einzeln mit ihrem Gewicht**
→ Fair Value und Herkunft. Fällt eine gewichtete Methode aus, steht dort
`<-- fällt aus!`.

Damit ist in einem Durchlauf entschieden, ob das Modell so rechnet oder ob
Daten fehlen — und welche.

### Nebenbefund

Bei NVDA fällt der **DCF mit 30 % Gewicht aus**, obwohl alle Daten da sind.
Grund: negative Nettoverschuldung und ein FCF, der gegen die Marktkapitalisierung
winzig ist. Der Fair Value stützt sich damit auf `fwd_pe` und `analyst` —
Herkunft: 77 % Multiple, 23 % Markt, 0 % Cashflow. Das ist bei einem Titel
dieser Größe eine Aussage, die man kennen sollte; sie steht jetzt in der
Herkunftszeile.


---

## Warum App und Kommandozeile verschiedene Werte lieferten

Der ROIC-Schlüssel liegt in `.streamlit/secrets.toml`. `config.py` las Schlüssel
aber nur über `os.getenv()`. Streamlit stellt `secrets.toml` **nur innerhalb einer
laufenden Streamlit-App** bereit — Skripte wie `precompute.py`, `main.py` oder
`warum_fair_value.py` laufen außerhalb und sahen dort gar nichts.

Folge: **Die App rechnete mit roic-Daten, jedes Skript ohne.** Zwei verschiedene
Fair Values für denselben Titel, ohne dass die Ursache irgendwo sichtbar war. Das
erklärt auch den Widerspruch NVDA App −64,5 % gegen Skript +88,7 % — es waren nie
dieselben Daten.

Besonders unangenehm: **`precompute.py` ist so ein Skript.** Der Snapshot, den das
Dashboard für Screener, Radar und Watchlist liest, wurde also ohne roic erzeugt.

### Behoben

`config._key()` löst jetzt in dieser Reihenfolge auf:

```
1. Umgebungsvariable
2. .streamlit/secrets.toml   (Projektordner, CWD, ~/.streamlit)
3. Fallback im Code
```

Die Datei wird direkt mit `tomllib` gelesen, nicht über Streamlit — sonst würden
die Secrets zusätzlich nach `os.environ` exportiert und die Herkunftsanzeige
verfälscht.

`config.schluessel_quelle("ROIC_API_KEY")` gibt aus, woher der Schlüssel kam:
`Umgebungsvariable` / `secrets.toml` / `Fallback im Code` / `FEHLT`.
`warum_fair_value.py` zeigt das jetzt in Abschnitt 1.

### Zu prüfen bleibt

Damit rechnen App und Skripte erstmals mit denselben Daten. Was NVDA dann
tatsächlich ergibt, ist offen — die −64,5 % aus der App wurden **mit** roic
gerechnet, die +88,7 % ohne. Welcher Wert näher an der Wahrheit liegt, zeigt
erst ein Lauf mit gleicher Datenbasis.


---

## Was der Screenshot der laufenden App zeigt

Drei Befunde, zwei davon Fehler in meinem Code.

### 1. Die Ursache: 70 % Methodengewicht fehlen

Die rote Warnzeile sagt es selbst: `fwd_pe`, `fwd_composite` und `analyst`
fallen aus. Im `inflection`-Playbook sind das 30 + 25 + 15 = **70 % des
Gewichts**. Übrig bleiben DCF und Forward-Composite-Reste.

Grund: `eps_forward` und `target_mean` kommen in `_merge_sources()`
**ausschließlich von yfinance** (`A.get("target_mean")`). Ist yfinance nicht
erreichbar — auf gehosteten Umgebungen der Normalfall, Yahoo sperrt
Rechenzentrums-IPs — fällt beides weg und mit ihm der halbe Fair Value.

Auf deinem Rechner lief yfinance (der CLI-Lauf hatte `eps_forward 13,81` und
`target_mean 305,79`), in der App nicht. Daher die Differenz.

**Behoben:** Der Lückenfüller holt jetzt
- `target_mean`, `target_high`, `target_low` über Finnhub `stock/price-target`
- `analyst_count` über Finnhub `stock/recommendation`
- `eps_forward` über FMP `analyst-estimates`

Wirkung mit sonst identischen Daten:

| | Fair Value | Upside |
|---|---|---|
| ohne `eps_forward` / `target_mean` | 143,79 | −31,4 % |
| mit beiden | 395,64 | +88,7 % |

### 2. Mein Fehler: Korridor aus drei Boomjahren

Der Reverse-DCF-Block meldete **„Konservativ eingepreist"** bei einem Kurs, der
**87,7 % Umsatzwachstum pro Jahr über zehn Jahre** verlangt. Das ist so falsch,
wie eine Aussage sein kann.

Ursache: Die Anker kamen aus vier Jahren NVDA-Historie — 3J-CAGR 83 %. Damit lag
das eingepreiste Wachstum *unter* der Historie und wurde als konservativ
eingestuft. Zusätzlich wurde derselbe Wert unter dem Etikett **„10J+ Historie"**
geführt, obwohl keine zehn Jahre vorlagen. Das ist keine Näherung, das ist eine
Falschaussage.

**Behoben:**
- `cagr_3j` erst ab 4 Jahren, `cagr_5j` ab 6, `cagr_10j` ab 9 Jahren — sonst
  wird der Anker gar nicht gesetzt statt falsch beschriftet
- `rd_korridor()` gibt `None` zurück, wenn weniger als zwei Anker vorliegen —
  ein Anker ergibt keinen Korridor, sondern eine Zahl mit erfundener Streuung
- neue Grenze `IMPLIZIT_ABSURD = 0.40`: über 40 % p. a. über zehn Jahre lautet
  das Urteil immer „über dem realistisch Lieferbaren", egal wo die kurze
  Historie liegt
- die Einzelanalyse lässt den Abschnitt bei dünner Historie ganz weg und sagt
  warum

### 3. Offen: der DCF und das rohe Beta

`WACC 15,4 %` bei Beta 2,215 ergibt ein Terminal-Multiple von **8,0x**, während
der Kurs 40,8x verlangt. Der DCF liefert deshalb 71 USD. Das ist keine Panne,
sondern die Konsequenz aus rohem Beta. Ob das für ein Unternehmen mit
Nettoliquidität und 63 % Nettomarge angemessen ist, ist eine Modellfrage —
üblich wäre eine Schrumpfung Richtung 1 (Blume: 0,67·β + 0,33 → 1,81 →
WACC ≈ 13,2 %). Das ändere ich nicht ohne deine Entscheidung.
