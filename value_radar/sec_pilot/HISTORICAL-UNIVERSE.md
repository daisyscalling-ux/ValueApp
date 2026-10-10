# Historisches Universum und ausgeschiedene Wertpapiere

## Aktueller Stand

Die erste Zugangskontrolle am 10. Oktober 2026 (Actions-Lauf 38080413729) erhielt kein GitHub-Secret FMP_API_KEY. Damit wurde keine FMP-Endpunktfreigabe getestet. Die bestehende 39-Unternehmen-Studie ist weiterhin eine Auswahl heutiger Unternehmen. Dieser Baustein ersetzt sie noch nicht durch einen vollstÃ¤ndigen historischen S&P 500.

`historical_sources.py` prÃ¼ft drei dokumentierte FMP-Endpunkte mit dem vorhandenen Secret: aktuelle S&P-500-Mitglieder, historische VerÃ¤nderungen und die erste Seite ausgeschiedener Firmen. Es speichert nur Status, Anzahl und Feldnamen, keine SchlÃ¼ssel, Fehlerantworten oder vollstÃ¤ndigen ProviderdatensÃ¤tze. HTTP 402 wird nicht durch neue SchlÃ¼ssel oder Wiederholungen umgangen. Der Workflow-Erfolg bedeutet ausschlieÃŸlich, dass der PrÃ¼fbericht erstellt wurde. MaÃŸgeblich sind dessen Einzelstatus.

## Quellen und offene Grenze

- [FMP: Historical S&P 500](https://site.financialmodelingprep.com/developer/docs/stable/historical-sp-500): HinzufÃ¼gungen und Entfernungen. Eine erfolgreiche Antwort beweist weder VollstÃ¤ndigkeit noch eindeutige WertpapieridentitÃ¤t.
- [FMP: Delisted Companies](https://site.financialmodelingprep.com/developer/docs/stable/delisted-companies): Verzeichnis ausgeschiedener BÃ¶rsenwerte. Kein Ersatz fÃ¼r terminale ErlÃ¶se und lÃ¼ckenlose Gesamtrenditen.
- [CRSP US Stock Databases](https://www.crsp.org/research__trashed/crsp-us-stock-databases/): aktive/inaktive Wertpapiere, permanente Kennungen und KapitalmaÃŸnahmen. Zugang muss separat vorliegen.
- [Norgate Datenpakete](https://norgatedata.com/stockmarketpackages.php): historische Indexmitglieder und delistete Werte ab Platinum. Kein kostenloser Datenzugang; keine Bestellung erfolgt.

Aktuelle Wikipedia-/Yahoo-Listen oder die vorhandene cf_universum.json sind keine vollstÃ¤ndige historische Mitgliederliste. Indexentfernung ist kein Delisting; eine Insolvenz ist nicht automatisch eine sofortige Auszahlung von null. BÃ¶rsenkÃ¼rzel kÃ¶nnen neu vergeben werden. CIK identifiziert den Emittenten, nicht allein die Aktiengattung.

## Nutzbare ImportprÃ¼fung

`historical_universe.py input.json --output report.json` prÃ¼ft einen normalisierten Providerexport. Der Normalisierungsschritt eines realen Anbieters ist noch nicht implementiert, solange Zugriff und Originalformat fehlen. Tests verwenden ausschlieÃŸlich ausdrÃ¼cklich synthetische Daten.

Erforderliche JSON-Felder:

- `schema`: 1.
- `coverage`: `start` inklusive und `end` exklusive, `source` als HTTPS-Beleg, `membership_completeness: provider_attested`, `return_basis: total_return_including_delisting`. Die Attestierung ist eine zu prÃ¼fende ErklÃ¤rung des Datenlieferanten, kein Beweis des Programms.
- `securities`: Zuordnung dauerhafter wertpapierspezifischer IDs zu Stammdaten und `source`. Symbol nur als Anzeige. Bei Beendigung: `termination_date`, `terminal_source`, `terminal_adjustment: included_in_total_return` erst nach belegter Abwicklung bzw. Nachfolgerbehandlung.
- `memberships`: Intervalle mit `security_id`, `start` inklusive, `end` exklusive und `source`. Keine Ãœberschneidungen je Wertpapier. Offene Intervalle mÃ¼ssen explizit bis zum Ende der belegten Abdeckung reichen.
- `sessions`: vollstÃ¤ndiger, chronologischer BÃ¶rsenkalender. Keine Duplikate; auÃŸergewÃ¶hnliche LÃ¼cken von mehr als sieben Kalendertagen verlangen PrÃ¼fung.
- `decisions`: vorab festgelegte Beobachtungstage aus diesem Kalender innerhalb der Mitgliederabdeckung.
- `returns`: Tagesgesamtrenditen als Dezimalzahl mit `security_id`, `date`, `total_return`, `source`. Bereits inklusive Dividenden, KapitalmaÃŸnahmen und gegebenenfalls Delisting; keine doppelte ErgÃ¤nzung der Delistingrendite. Mindestens âˆ’1. Nach Ãœbernahme muss eine belegte Portfoliorendite die Nachfolgeraktien oder tatsÃ¤chlich ausgezahltes Cash abbilden. Keine automatische Nullfortschreibung.

FÃ¼r jeden damaligen Indexbestand entstehen erwartete Fenster Ã¼ber 21/63/126 Sitzungen nach dem Einstieg zum nÃ¤chsten Sitzungsschluss. Ein spÃ¤terer Indexausschluss beendet das Fenster nicht. Fehlende Kurse/Schlussrenditen bleiben im Nenner der erwarteten Fenster und erscheinen als LÃ¼cke. Sie werden nicht herausgefiltert, um die Abdeckung besser aussehen zu lassen. Die Rendite des Einstiegstages selbst zÃ¤hlt nicht zur Haltedauer.

Ausgabe enthÃ¤lt nutzbare Einzelbeobachtungen und jede LÃ¼cke. `incomplete` oder `invalid_input` liefern Exitcode 2, keine aggregierte Risikokalibrierung. `ready_for_feature_join` heiÃŸt nur: deklarierte Daten strukturell verwendbar. Das Programm setzt `complete_historical_universe_verified` absichtlich niemals automatisch auf true. Herkunft, korrekte Indexdefinition, Aktiengattungen, BÃ¶rsenwechsel und Providerabdeckung sind zusÃ¤tzlich zu prÃ¼fen.

Danach fehlen noch die Verbindung zu damaligen Finanzmerkmalen und ein festgelegter rollierender Vergleich. Die vorhandenen DatenlÃ¼cken erlauben derzeit keine Aussage, dass der Survivorship Bias beseitigt ist. Keine produktive ScoreÃ¤nderung.
