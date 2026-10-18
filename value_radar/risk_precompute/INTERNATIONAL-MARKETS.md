# Internationaler Marktvergleich

Stand 18.10.2026. Die gemeinsame market-proxies.json wird vom ROIC-Abruf,
der TypeScript-Zuordnung und dem Yahoo-Ersatzabruf verwendet. Sie enthaelt
24 Laender und eindeutige englische Namensvarianten; keine unscharfe Suche.
Quellen zu den zusaetzlichen ETFs stehen direkt in der Datei.

Neu: Schweiz, Niederlande, Italien, Spanien, Daenemark, Belgien, Schweden,
Finnland, Oesterreich, Norwegen, Polen, Irland, Griechenland und Thailand.
Portugal bleibt ohne Ersatz. Fehlende oder fehlerhafte Historien bleiben offen.

Produktiver Lauf vor dieser Erweiterung (39115228928):
- 1330 aktive Notierungen, alle bearbeitet, kein Zeitbudgetabbruch.
- 1254 aktuelle Kursrisikohistorien und 1221 laengere Risikohistorien laut
  aktivem Universumsbericht (alte, nicht mehr aktive Archive nicht mitzaehlen).
- 1004 Notierungen mit Marktvergleich; 326 ohne Zuordnung.

Die neuen Zuordnungen betreffen 321 dieser 326 Notierungen. Die verbleibenden
fuenf haben Portugal als Land. Eine Zuordnung alleine ist keine Datenabdeckung.

Live-Test der Erweiterung am 18.10.2026: 24/24 ETF-Historien ueber yfinance
erfolgreich. Alle 24 bestehen validYahooBenchmark, historyStatistics und
compactHistory sowohl fuer aktuellen Drawdown als auch laengere
Verluststatistiken. Keine Ausweichannahme auf unbereinigte Schlusskurse.
Dies ist ein lokaler Live-Test, noch kein veroeffentlichtes Cloudflare-Ergebnis.

Der Yahoo-Helfer bearbeitet fehlende/aelteste Marktstaende zuerst und sichert
Teilergebnisse. Gesamtbudget 15 Minuten, einzelner Versuch maximal 40 Sekunden,
maximal zwei Versuche. Der Workflow erlaubt 17 Minuten fuer diesen Abschnitt.
So koennen neue Maerkte nicht dauerhaft hinter den alten zehn verhungern.

Alle Reihen sind US-gehandelte ETFs in USD. Bei auslaendischen Maerkten wirken
Wechselkurse, Fondsgebuehren und die jeweilige Indexzusammensetzung mit. Es sind
keine reinen lokalen Indizes, direkten Wettbewerber oder firmenspezifischen Betas.
Die Zuordnung nutzt das im Universum gespeicherte Land; fuer ADRs ist das nicht
zwangslaeufig das wirtschaftliche Heimatland des Unternehmens.

Nach Merge daily-risk starten. Die Erweiterung betrifft zunaechst Datenexport
und Abdeckungsbericht. Die separate Cloudflare-Oberflaeche wird durch diesen PR
nicht neu veroeffentlicht; eine dort eingebettete alte Laenderliste bleibt ein
separater Integrationspunkt. Kein neuer kalibrierter Gesamtscore.
