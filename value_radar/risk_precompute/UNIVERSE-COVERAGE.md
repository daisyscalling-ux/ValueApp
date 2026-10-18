# Universumsweite Risiko-Datenversorgung

## Was dieser Block umsetzt

Der bestehende daily-risk-Lauf prueft jetzt vor und nach dem Abruf jede Notierung
aus cf_universum.json. Keine manuell gepflegte Vier-Aktien-Stichprobe. Neue
Universumseintraege werden beim naechsten Lauf automatisch aufgenommen.

- cf_risk_coverage.json: Datenstatus pro Notierung fuer Identitaet, aktuellen
  Kurs, Kurshistorie, historische Verluststatistik, Bilanz/Cashflow, Markt,
  Branchenkontext und Nachrichten.
- cf_risk_queue.json: priorisierte Aufgaben mit Besitzer, Grund, Versuch und
  Wiederholungszeit. Der Preisabruf verarbeitet seine Aufgaben; fundamentals-daily
  nutzt die gemeinsamen Prioritaeten fuer die bestehende Yahoo-/SEC-Ergaenzung.
- Ergebniszusammenfassung direkt im GitHub-Actions-Lauf, beide Dateien zusaetzlich
  als Artifact fuer 90 Tage. Die JSON-Dateien werden ins Repository geschrieben.

## Abruf und Wiederaufnahme

Preisabrufe sind auf hoechstens 240 Requests/Minute begrenzt. Das ist kein
reserviertes Kontingent: andere ROIC-Nutzer teilen das kontoweite 300er-Limit.
HTTP 429 reduziert das Tempo und beruecksichtigt Retry-After. Zeitbudget und
Zwischenspeicherung des bestehenden Exports bleiben erhalten. Eindeutige
Notierungsmetadaten werden sieben Tage wiederverwendet.

Fehlversuche werden gespeichert. Providerfehler erhalten zunehmende Wartezeiten,
Zugangs-/Tarifprobleme laengere Sperrzeiten. Erfolgreiche Abrufe loeschen den
Fehlerstatus. Im Fundamentallauf haben neue und seit mehr als sieben Tagen nicht
bearbeitete Notierungen Vorrang, damit bekannte Problemfaelle sie nicht verdraengen.
Ein expliziter manueller Fundamentaldatenabruf umgeht die automatische Wartezeit.

## Bedeutung der Bereiche

`available` heisst: die erforderlichen datierten Felder bestehen die hier
definierten Pruefungen. Kein kalibrierter Gesamtscore, keine Fallwahrscheinlichkeit.
Die vorhandenen Risikostatistiken werden weiterverwendet; keine Gewichte geaendert.

Bei Bilanzquoten werden ausschliesslich Werte derselben Jahresperiode und
Berichtswaehrung kombiniert. Fehlende Schulden sind nicht null. Negativer Capex
wird nur fuer explizit gekennzeichnete Yahoo-Jahresdaten als Cash-Auszahlung
normalisiert. GBP/GBp/GBX werden bei der Identitaetspruefung als dieselbe Waehrung
mit verschiedenen Einheiten erkannt; hier wird kein absoluter Preis verglichen.
Die Quoten sind Buchwertmerkmale und keine vollstaendige Leasing-/Kapitalanalyse.

Branchenzuordnung mit mindestens fuenf anderen Notierungen bedeutet nur
`context_only`: keine bestaetigten direkten Wettbewerber und kein Branchenrisiko.
Allgemeine News sind keine unternehmensbezogene Abdeckung. `not_assessed` bleibt
sichtbar, bis ein eigener datierter Unternehmensnews-Lauf vorhanden ist. Laender
ohne zugeordneten Markt-ETF bleiben `unsupported`, ohne erfundenen Ersatz.

## Grenzen und naechste Arbeit

Dieser Block liefert die gemeinsame Datenpruefung und Abrufsteuerung fuer das
gesamte Universum. Ein neuer App-Gesamtscore, Unternehmensnews-Klassifikation,
weitere internationale Marktproxies und historische Risikokalibrierung sind
separate Folgearbeiten. Review-Aufgaben werden nicht als automatisch erledigt
ausgegeben. Bestehende publizierte Daten sind kein historischer Point-in-time-Test.

Nach Merge einmal `daily-risk` auf main starten. Danach arbeitet der bestehende
taegliche Zeitplan. `fundamentals-daily` uebernimmt die neue Warteschlange beim
naechsten Lauf. Kein vierstuendiger Precompute und kein Cloudflare-Upload notwendig.
