# Quantum: Screener und Branchenkennzahlen

Der Workflow quantum-peer-universe aktualisiert jetzt vollständige Screener-Analysen und die Branchenkennzahlen in Cloudflare. Der bestehende value-radar-update bleibt unverändert.

## Aktivierung

Diesen Pull Request in main übernehmen, anschließend unter Actions → quantum-peer-universe → Run workflow starten. ROIC_API_KEY und QUANTUM_SYNC_TOKEN bleiben dieselben vorhandenen Secrets. Keine weiteren Schlüssel erforderlich.

## Ablauf

Vier Starts täglich: 03:17, 09:17, 15:17 und 21:17 UTC. Pro Lauf sechs Minuten Datenbudget, maximal 150 Titel, 20 Sekunden je Abruf und etwa 214 ROIC-Anfragen pro Minute. Das Zeitbudget begrenzt den tatsächlichen Umfang; es wird kein weltweiter Tagesvollbestand versprochen. Die GitHub-Laufzeit fällt zusätzlich zum vorhandenen ValueApp-Job an.

ROIC-Seitentokens verfallen nach einer Stunde (https://www.roic.ai/api/docs/response-format). Jeder Lauf lädt deshalb den Katalog mit Seiten von 2.000 Einträgen neu und setzt die Finanzanalyse anhand einer dauerhaft gespeicherten Aktien-ID in stabiler Sortierung fort. Der erste Lauf beginnt am Kataloganfang. Ein kompletter Durchlauf beginnt anschließend wieder vorn. Fehlgeschlagene Aktien werden im nächsten Durchlauf erneut versucht; vorherige gute Daten bleiben erhalten.

## Berechnung und Speicherung

quantum_sync/sync.mjs ist aus dem ROIC-Adapter des Dashboards erzeugt. Node 24 und Python 3.12 sind ausreichend, pip-Abhängigkeiten sind nicht nötig. Die Python-Dateien unter quantum_sync/engine entsprechen der eingebundenen valuation.py des Dashboards; sie ersetzen ValueApps vorhandene Bewertungsdateien nicht.

Jeder Import speichert Finanzdaten, Python-Bewertung, serverseitig abgeleiteten Fundamental Score und die Fortsetzungsposition gemeinsam. Ältere Importe überschreiben keine neueren Analysen. Fehlende Eingaben und Bewertungs-Prüffälle bleiben gekennzeichnet. Der Screener-Score enthält kein Momentum; Kurshistorie und Nachrichten werden beim Öffnen der Einzelanalyse nachgeladen. FMP-Free-Ziele werden nicht vorausgesetzt.

Cloudflare nutzt /api/screener-sync mit dem vorhandenen Import-Token. Die zusätzliche Tabelle ist bereits durch worker/migrations/0002-screener.sql vorbereitet. Kein Token darf ins Repository.

## Prüfung

Lokal geprüft: Original-Python-Gleichheit, Import und Filter gegen SQLite, ungültige Importe, ältere Daten, Authentifizierung, Körpergrößenlimit sowie Wiederaufnahme nach abgelaufenem ROIC-Cursor. GitHub führt Kennzahlen- und Engine-Tests vor dem Abgleich aus. Ein echter Lauf dieses neuen Workflows steht vor dem Zusammenführen noch aus.
