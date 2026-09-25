# ValueApp → Quantum: geprüfte GitHub-Ergänzung

Diese Ergänzung fügt drei Dateien hinzu. Den vorhandenen precompute.yml und precompute.py NICHT ersetzen.

1. .github/workflows/quantum-peers.yml
2. value_radar/quantum_peers.py
3. value_radar/test_quantum_peers.py

Der Workflow läuft täglich um 03:17 UTC und kann über Actions → quantum-peer-universe → Run workflow manuell gestartet werden. Er benötigt keine Pakete außer Python. Es werden keine E-Mails, Depotaktionen oder KI-Aufrufe aus ValueApp gestartet.

GitHub: Settings → Secrets and variables → Actions → New repository secret:
- ROIC_API_KEY: bereits im vorhandenen Projekt verwendet.
- QUANTUM_SYNC_TOKEN: derselbe Wert wie das gleichnamige Cloudflare-Secret. Nicht als Datei ins Repository hochladen.

Der Zielserver ist https://quantum-equity-research.daisyscalling.workers.dev . Das Secret erlaubt nur das Lesen des Sync-Fortschritts und das Schreiben der Branchenkennzahlen, keinen Dashboard-Login. Der Cloudflare-Endpunkt ist /api/peer-sync. Ohne gesetztes Secret bleibt er gesperrt.

Pro Lauf: höchstens 250 Unternehmen, 30 Minuten Zeitbudget, 20 Sekunden je Netzwerkabruf, maximal etwa 230 ROIC-Abrufe pro Minute. Jeder erfolgreich gespeicherte Datensatz und die nächste Katalogposition werden gemeinsam abgelegt. Abbrüche führen beim nächsten Lauf zur Fortsetzung; ein abgeschlossener Katalog startet im nächsten Lauf erneut. Fehlerhafte Titel behalten ihre bisherigen Werte und werden im nächsten Durchlauf erneut versucht. Ein weltweites Universum benötigt bei 250 Titeln täglich mehrere Wochen; Aufrufzahl und Laufzeit müssen nach dem ersten realen Lauf abgestimmt werden.

Der Import verwendet ausschließlich ROIC-TTM mit passender Währung, Aktienkennung und Finanzstichtag. Margen bleiben Prozentwerte. FCFF wird nicht als Free Cash Flow übernommen; unvollständige Investitionsausgaben erzeugen keinen erfundenen FCF. Jahresdaten werden nicht als TTM ausgegeben. Veraltete/neue Datensätze überschreiben keine neueren Abschlussdaten.

Der bestehende Cloudflare-Sammler bleibt während der Inbetriebnahme aktiv. Erst nach einem nachgewiesenen erfolgreichen GitHub-Import sollte man entscheiden, ob dieser zusätzliche Sammler weiter benötigt wird. Beide zusammen plus interaktive Abfragen können das gemeinsame ROIC-Limit beanspruchen; HTTP 429 stoppt den GitHub-Lauf.

Befunde im gelieferten ZIP:
- _fuer_sektormessung behält nur Sektor/Branche und wenige Multiples; keine Margen, Finanzstichtage oder eindeutigen IDs.
- roic.bundle_light übernimmt ttm_free_cash_flow_firm als free_cashflow. Deshalb keine ungeprüfte Übernahme dieses Dictionarys.
- Die vorhandenen Zeitbudgets und Fortschrittsanzeigen sind sinnvoll, aber der Export benötigt eine eigene persistente Fortsetzungsposition.

Getestet: Perioden/Währungsabgleich, FCFF/FCF-Trennung, vollständige CapEx, Prozent-Einheiten, Import-Authentifizierung, Größenlimit und Ablehnung ungültiger Batches. Ein echter GitHub-Lauf erfordert das Einfügen der Dateien und des Repository-Secrets.
