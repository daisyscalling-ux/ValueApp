# Datierte Ersatzversorgung

## Ablauf

`fundamentals-daily` ergänzt täglich die bekannte Universumsliste. Jeder Titel wird getrennt mit maximal 45 Sekunden abgefragt. Ein Lauf hat 120 Minuten Budget und speichert nach jedem Titel. Der nächste Lauf beginnt bei den am längsten nicht versuchten Titeln. Eine vollständige tägliche Aktualisierung ist damit kein garantierter Zustand; die Abdeckung steht im Index.

Die Cloudflare-Einzelanalyse liest automatisch die Datei ihrer exakten Notierung. Bei fehlendem oder über 24 Stunden altem Snapshot kann sie einen GitHub-Einzelabruf starten. Dafür muss das bereits vorgesehene Secret `QUANTUM_GITHUB_TOKEN` im Worker vorhanden sein (ValueApp, Actions read/write). Ohne Token funktioniert die tägliche Versorgung, der Einzelabruf wird als nicht eingerichtet angezeigt. Nach Abschluss des Jobs erneut laden. Es ist keine manuelle Aktivierung einer Datenquelle notwendig.

## Quellen und Auswahl

- Yahoo: getrennte datierte Jahresabschluss-Tabellen, Kursdaten und Analystenbeobachtungen; keine Übernahme des undatierten Profil-EPS als Jahresabschluss-EPS.
- SEC: für bekannte CIKs und US-GAAP aus derselben 10-K/10-K-A-Einreichung. `SEC_USER_AGENT` wird ausschließlich aus dem vorhandenen GitHub-Secret gelesen. Keine erfundene Kontaktadresse. IFRS/unternehmensspezifische XBRL-Tags werden nicht geraten.
- Geprüfte Unternehmensberichte in `reviewed/` können die Lücke bis zum strukturierten Bericht schließen. Das sind explizit manuell geprüfte Daten mit Quelle/Veröffentlichungsdatum. Neuere strukturierte Berichte ersetzen sie. Initial ist Microns Bericht vom 30.09.2026 enthalten.

Primärdaten werden nur durch einen mindestens gleich neuen, passenden Jahresblock ersetzt. Währung, exakte Notierung und Zeitraum müssen passen. Abgeleitete historische Aktienzahlen aus altem Börsenwert/heutigem Kurs werden nicht als neue Anbieterbeobachtung verkauft. Unpassende Währungen (beispielsweise ADR gegenüber Heimatabschluss) bleiben offen; keine geratene ADR-Ratio oder Wechselkurskorrektur.

## Verbindliche Lückenregeln

- Eine neue Abrufzeit macht alte Berichtsperioden nicht neu.
- Fehlgeschlagene/ältere Antworten löschen keine neueren gespeicherten Jahresblöcke. Das ursprüngliche Abrufdatum des zurückbehaltenen Blocks bleibt erhalten.
- Annual: maximal 460 Tage alt, letzte erfolgreiche Bestätigung maximal sieben Tage. Meldet der Anbieter bereits ein neueres Geschäftsjahr, wird das alte nicht als aktuell akzeptiert.
- Kursblock: Snapshot maximal 36 Stunden, Kursbeobachtung maximal vier Kalendertage (Wochenendpuffer), Datum sichtbar.
- EPS-Prognosen ohne expliziten Zeitraum bleiben als Rohbeobachtung erhalten, werden aber nicht als gesicherte Forward-EPS importiert.
- CFO minus Brutto-Capex bleibt separat. Es ist kein bestätigter FCFF für den vorhandenen Unternehmenswert-DCF. Fehlende Nettoverschuldung wird in DCF/EV/EPV nicht mehr als null angenommen.
- Werden neue Jahresdaten gewählt, werden nicht passende alte Finanzkennzahlen, forensische Paare und Diagrammreihen entfernt. Sie werden nicht aus anderen Perioden aufgefüllt.

## Installation

Repository: Collector/Tests/Reviewed-Daten nach `value_radar/fundamental_export/`, Workflow nach `.github/workflows/fundamentals-daily.yml`. Ergebnisse: `value_radar/daten/fundamentals/`.

Nach Merge zuerst `fundamentals-daily` starten, anschließend den aktualisierten lokalen `cf`-Ordner wie bisher deployen. `SEC_USER_AGENT` ist bereits für das Risikoprojekt vorgesehen. Es sind keine kostenpflichtigen neuen Datenzugänge erforderlich.

## Was damit nicht behauptet wird

Keine Quelle garantiert alle Felder für jede Aktie. Vollständige Methodeneingaben müssen je Titel geprüft werden. Insbesondere FCFF, explizit datierter Analysten-EPS-Konsens, ADR-Umrechnungen und nicht standardisierte SEC-Tags können offen bleiben. Fehlende Werte sind sichtbar offen und kein Kauf-/Verkaufssignal. Diese Versorgung ersetzt noch nicht den Python-Bewertungskern des alten Screener-Exports; dessen verdächtige Werte werden durch die lokale Konsistenzprüfung unterdrückt.

## Tests

Python: Datums-/Währungsbasis, veraltete Yahoo-Tabellen, exakte Notierungen, SEC-Zeiträume und gleiche Einreichung, Erhalt älterer Bestätigungsdaten.
TypeScript: echte Blockübernahme, Nichtvermischung mit altem FCFF, falsche Währung/Identität, veraltete/future Snapshots, Primärdaten neuer als Ersatzdaten, begrenzte GitHub-Abrufe und Fehlerbehandlung.

## Dauerhafte Aufnahme neuer Aktien

Neue Zeilen in cf_universum.json werden im nächsten täglichen Lauf automatisch berücksichtigt. Explizit angefragte EXCHANGE:SYMBOL-Notierungen werden vor dem ersten Netzabruf in index.json unter registered gespeichert. Auch ein fehlgeschlagener erster Versuch oder ein erschöpftes Laufbudget entfernt diese Registrierung nicht. Erfolgreiche ältere Einzelabrufe werden ebenfalls in die tägliche Auswahl aufgenommen. Unbekannte unqualifizierte Namen werden abgewiesen; keine erfundene Börsenzuordnung.

Der Cloudflare-Worker benötigt zusätzlich sein aktualisiertes Deployment: Einzelanfragen werden dauerhaft in UNIVERSE unter fundamental-pending: gespeichert. Der vorhandene Viertelstunden-Cron prüft maximal fünf Einträge pro Durchgang mit fortgesetztem Seitencursor. Er bündelt Wiederholungen und wartet nach einem akzeptierten erneuten Start mindestens sechs Stunden. Ein Eintrag wird erst gelöscht, wenn ein neuerer, zur Notierung passender Datensatz veröffentlicht ist, nicht bereits nach HTTP 204. Das fängt ersetzte wartende GitHub-Läufe ab. Voraussetzung bleiben QUANTUM_GITHUB_TOKEN mit Actions-Zugriff und die bestehende UNIVERSE-Bindung.

Diese Mechanik garantiert Aufnahme und erneute Versuche, nicht die Verfügbarkeit beliebiger Daten beim Anbieter. Währungs-/ADR-Konflikte und unbekannte Börsen bleiben offen statt mit Ersatzwerten kaschiert zu werden. Der globale Coverage-Bericht beschreibt weiterhin den jeweils angefragten Lauf; ein Einzelabruf ist kein vollständiger Universumsnachweis.

