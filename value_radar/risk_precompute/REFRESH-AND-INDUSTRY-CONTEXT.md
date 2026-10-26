# Vorbeugende Nachversorgung und gestufter Branchenkontext

Stand: 26.10.2026. Datenpipeline, keine neue Verlustwahrscheinlichkeit oder Fair-Value-Formel.

## Konkrete Ursache der beiden Rueckschritte

Im Archiv vom 25.10.2026 hatten TSE:3697 und TSE:7453 vollstaendige ROIC-Abschluesse per 31.08.2025, abgerufen am 24.10.2026. Der Lauf vom 26.10.2026 ersetzte sie durch ROIC-Periodenzeilen per 31.08.2026, deren sieben normalisierte Finanzfelder ausnahmslos null waren. Der neue Periodenkopf wurde faelschlich als erfolgreicher Abschlussabruf gespeichert. Yahoo lieferte gleichzeitig keinen nutzbaren Ersatz (bei TSE:3697 nur einen unveraendert datierten Altstand).

Die Korrektur gilt fuer alle Notierungen: Eine vollstaendig leere Periode wird uebersprungen. Ein aelterer Abschluss wird nur dann frisch datiert, wenn dessen Werte im selben aktuellen API-Abruf tatsaechlich enthalten sind. Ohne solche Werte gilt der Abruf als empty_statement_values; ein vorhandener Archivstand bleibt mit seinem urspruenglichen Abrufdatum erhalten. Echte, teilweise befuellte neue Abschluesse werden nicht zugunsten schoenerer alter Zahlen versteckt. Explizit gemeldete Nullen bleiben Werte, fehlende Werte bleiben null. Es werden keine Perioden vermischt. Uebersprungene Leerperioden werden protokolliert.

## Vor Ablauf statt erst nach Ausfall

Die Bilanzpruefung exportiert expiresAt und refreshDue. Massgeblich ist die frueheste bestehende Grenze aus Abschlussabruf, einzelnen Feldabrufen, Periodenalter und Publikationsalter. Zwei Tage vor Ablauf entstehen bereits Aufgaben fuer fundamentals-daily und vorbeugende ROIC-/EDINET-Ersatzabrufe. Identitaetspruefung, Marktprioritaet, Tages-Cooldown, Zeitbudget und vorhandene Gueltigkeitsgrenzen bleiben bestehen. Diese Vorsorge garantiert nicht, dass ein Anbieter Daten liefern kann; sie schafft Zeit fuer Ersatzquellen und verlaengert keine alten Daten kuenstlich.

fundamentals/index.json erhaelt je versuchter Notierung annualSupply. Ein erfolgreicher Kursabruf bedeutet damit nicht mehr automatisch einen frischen Jahresabschluss. Rueckbehaltene Felder und ihr Alter bleiben sichtbar. Dieser Status ist eine Datumspruefung, keine umfassende Rechnungslegungspruefung; die strengeren Kennzahlenpruefungen bleiben entscheidend.

## Drei getrennte Vergleichsebenen

1. Bestehende engere Anbieter-Unterbranche bzw. gepruefte Geschaeftsmodellgruppe.
2. Neu: gleicher gemeldeter Branchenzweig als eigenstaendiger industryContext, falls die engere Gruppe weniger als fuenf geeignete Vergleichsemittenten hat. Mindestens fuenf andere Emittenten, gleiche Handelswaehrung, frische und widerspruchsfreie Branchenzuordnung, passende Identitaet und gemeinsame Handelstage sind Pflicht. Bestehende erfolgreiche enge Vergleiche und individuell gepruefte Geschaeftsmodellgruppen werden nicht ersetzt.
3. Bestehender breiter Sektorkontext mit mindestens zehn anderen Emittenten.

Die neue Ebene bestaetigt keine direkten Konkurrenten und verbessert nicht kuenstlich die enge Peer-Abdeckungszahl. Sie verwendet vorhandene Kursreihen ohne zusaetzliche API-Abrufe. Der Arbeitsplan zaehlt enge Vergleiche, Branchenkontext, breiten Sektorkontext sowie mindestens einen/nicht vorhandenen Kontext getrennt, ohne die Notierungen mehrfach in any_context zu zaehlen. Die neue Ebene wird zunaechst im Datenexport bereitgestellt; eine neue App-Oberflaeche ist nicht Bestandteil dieses Blocks.

## Validierung und Grenzen

- 176 Python-Risikotests und 36 Fundamentalexport-Tests bestanden.
- 12 feldweise Bilanztests, 33 Universumschecks, 10 EDINET-Integrationstests, 24 Branchen-/Kalenderchecks, 6 breite Sektortests und 6 Tests fuer den neuen Branchenkontext bestanden.
- Replay des aktuellen Produktionsbestands zum selben Auswertungszeitpunkt: 2.441 bereits verfuegbare Bilanzkennzahlen unveraendert, keine Umklassifizierung. Die Nachversorgung veraendert deren Werte nicht.
- Leere Folgeperiode, echter neuer Teilabschluss, Altstand ohne Neudatierung, vorbeugender Abruf, Cooldown, Waehrung, Identitaet, doppelte Notierungen und ungueltige Kontextdaten sind abgedeckt.
- Die komplette produktive Kursreihen-Datei liegt im GitHub-Cache, nicht im Repository. Die Zahl neu verfuegbarer Branchenvergleiche wird deshalb erst nach dem produktiven Lauf berichtet; keine synthetischen Tests werden als reale Abdeckung ausgegeben.

Nach Merge einmal daily-risk auf main starten. fundamentals-daily uebernimmt die neue Abrufdiagnose beim regulaeren naechsten Lauf. Keine neuen Secrets, kein Cloudflare-Upload fuer diesen Datenblock. Anschliessend die beiden ROIC-Faelle und die gestufte Peer-Abdeckung im gemeinsamen Laufbericht pruefen.
