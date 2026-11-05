# Ereignisprüfung, Branchenpakete und beobachtete Risikodaten

`daily-risk` führt `risk_evidence.py` nach der Integritätsprüfung aus. Es benötigt keine neuen Secrets und startet keine zusätzlichen Anbieterabrufe. Voraussetzung ist eine frische, zum verarbeiteten Universum passende Abdeckungsdatei.

## Nachrichten: Prüfaufträge, keine bestätigten Ereignisse

`cf_risk_event_review.json` gruppiert exakt gleiche, normalisierte Überschriften aus dem vorhandenen Nachrichtenarchiv. Nur zur aktuellen Unternehmensidentität passende und frische Datensätze werden zugelassen; zukünftige Artikel werden ausgeschlossen. Die bestehenden deutschen und englischen Schlagwortregeln liefern mögliche Themen, keine Tatsachenfeststellung.

Eine Meldung erhält ausdrücklich `verified: false` und keinen Scorebeitrag. Mehrere Links können dieselbe Agenturmeldung wiederholen. Die Anbieterzuordnung einer Aktie beweist nicht, dass diese Firma Gegenstand der Meldung ist. Verneinungen und hypothetische Formulierungen werden zur Prüfung markiert, nicht semantisch aufgelöst. Vor einer Verwendung im Score müssen Originalquelle, betroffene Geschäftstätigkeit, tatsächliches Ereignis, Datum und Gegenbelege geprüft werden.

`no_tagged_candidate_in_sample` bedeutet nur: im begrenzten gelieferten Ausschnitt kein Schlagworttreffer. Es bedeutet weder Nachrichtenfreiheit noch geringes Risiko. Fehlende, alte und nicht eindeutig zugeordnete Daten bleiben gesondert sichtbar. Keine automatische Bestätigung, neue Risikopunkte oder Oberfläche für die Ereignisfreigabe sind Teil dieses Schritts.

## Branchen: offene Anforderungen gemeinsam bearbeiten

`cf_sector_review_packets.json` bündelt Banken, Versicherer und spezialisierte Finanzunternehmen nach Marktpriorität, Finanzprofil und Notierungsland. Jedes Unternehmen behält seine eigenen offenen und erfüllten Anforderungen. Notierungsland ist eine Arbeitshilfe, kein Nachweis der regulatorischen Zuständigkeit. Kapital- oder Kreditqualitätskontext ersetzt keine fachlich passende Originalkennzahl. Diese Pakete beschaffen noch keine zusätzlichen Offenlegungen und schließen keine Anforderungen automatisch.

## Täglich nachvollziehbare Eingangsdaten

Die erste erfolgreiche Beobachtung je UTC-Tag erzeugt `daten/risk_observations/YYYY-MM-DD.json.gz`. Sie enthält Zeitpunkt, Codeversion und SHA256-Prüfsummen der sieben Eingabedateien. Weitere Läufe desselben Tages überschreiben sie nicht. Die großen JSON-Dateien werden ohnehin im gleichen Datencommit veröffentlicht; sie werden nicht täglich zusätzlich kopiert. `cf_risk_observation_status.json` beschreibt die Erzeugung beziehungsweise Beibehaltung der Beobachtung.

Für eine Wiederherstellung ist die vollständige Git-Historie erforderlich. `resolve_risk_observation.py REPOSITORY YYYY-MM-DD [AUSGABE.json]` liest alle Eingabedateien aus genau dem Commit, der das Tagesmanifest erstmals hinzugefügt hat, und prüft jede Prüfsumme. Aktuelle Dateien dürfen nicht als Ersatz verwendet werden. Fehlende Historie, ein anderer Dateisatz oder abweichende Prüfsummen führen zu einem Fehler. Die Historie darf daher nicht ohne gesondertes Archiv gekürzt oder umgeschrieben werden. Repository und Artefakte enthalten keine API-Schlüssel; Nachrichtenlinks mit Zugangsdaten werden verworfen.

Die Sicherung beginnt mit dem produktiven Einsatz. Berichtsperioden und Nachrichtenzeitpunkte werden nicht als rückwirkender Beobachtungszeitpunkt ausgegeben. Auch Anbieterrevisionen vor unserem Abruf können nicht ausgeschlossen werden.

## Was für die Gesamtmodellprüfung noch fehlt

Die Beobachtungen sind Eingabedaten, kein validierter Gesamtrisikoscore. Ein fehlender Gesamtscore wird nicht erfunden. Vor einer historischen Auswertung müssen Modellversion und Entscheidungsschwellen feststehen sowie später beobachtete, korrekt um Kapitalmaßnahmen und Delistings bereinigte Gesamtrenditen ergänzt werden. Vorgesehene Auswertungsfenster sind 21, 63 und 126 Handelstage mit Einstieg frühestens nach der Beobachtung. Zeitliche Trennung von Entwicklung und Prüfung, Datenabdeckung und Selektionsverzerrungen sind separat auszuweisen. Der bisherige Kurskomponenten-Test ist keine Validierung des Gesamtmodells.

Tests prüfen unter anderem Identitätswechsel, alte und zukünftige Meldungen, Dubletten, Verneinungen, unveränderte offene Branchenanforderungen, unveränderliche Tagesmanifeste, Prüfsummenfehler und eine Wiederherstellung aus einem echten lokalen Git-Repository nach späteren Datenänderungen.
