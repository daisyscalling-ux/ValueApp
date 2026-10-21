# Vergleichsgruppen – Schritt 1

Dieses Modul erzeugt `daten/cf_peer_groups.json` aus dem aktuellen Universum. Es berechnet keine Risikowerte und verändert weder die bestehenden Branchen-Kursvergleiche noch Fair Values oder die Cloudflare-Oberfläche. Der tägliche Workflow erzeugt, archiviert und veröffentlicht die Gruppenzuordnung. Schritt 2 kann diesen Bericht später ausdrücklich übernehmen.

## Regeln

1. Nur eindeutig bezeichnete Aktien/ADRs mit gültiger ISIN und höchstens 90 Tage alten Metadaten. Fehlende Angaben, doppelte Listing-Schlüssel und abgelaufene Stammdatenkorrekturen werden mit Gründen ausgeschlossen.
2. Verknüpfung gleicher ISIN, CIK, LEI oder konservativ normalisierter vollständiger Unternehmensnamen. Unterschiedliche Aktienklassen und ADRs geben einem Emittenten keine zusätzlichen Stimmen. Widersprüchliche CIK/LEI oder Geschäftszuordnungen werden zur Prüfung zurückgestellt. Namensgleichheit ohne globale Emittenten-ID bleibt eine Datenannahme; eine vollständige wirtschaftliche Konzernstruktur wird nicht behauptet.
3. Pro Emittent eine repräsentative Notierung: primäre Notierung, dann Nicht-OTC, dann Stammaktie vor ADR; bei Gleichstand alphabetisch. Alle alternativen Notierungen bleiben im Bericht nachvollziehbar. Der Emittent selbst wird immer aus seinen Peers entfernt.
4. Belegte Geschäftsmodell-Zuordnungen stehen vor Anbieter-Unterbranchen. Sie sind durch ISIN und erwarteten Unternehmensnamen begrenzt und haben ein Ablaufdatum. Quellen stehen in `peer-group-rules.json`.
5. Fehlt die Unterbranche, bleibt eine ausdrücklich vorläufige Branchen-Kontextgruppe. Nur explizite Schreibweisen-/Klassifikationsentsprechungen werden vereinheitlicht. Es gibt keinen automatischen Rückfall auf den Gesamtsektor. Die Gruppen sind keine bestätigte Liste direkter Konkurrenten.
6. Kleine Gruppen werden nicht mit fachfremden Titeln aufgefüllt. `ready` bedeutet lediglich mindestens fünf andere Emittenten, keine Freigabe für einen Risikoscore. `level` und `reason` müssen Verbraucher stets beachten.
7. Die Geschäftszuordnung ist global und nicht auf eine Handelswährung begrenzt. In Schritt 2 sind Währung, Länder-/Marktrisiken, gemeinsame Beobachtungstage und verfügbare Kurshistorien separat zu prüfen. Aus diesen Gruppen dürfen noch keine gemischten Kursmediane abgeleitet werden.

## Datenstand und Grenzen

Test am 21.10.2026: 1.330 Eingaben; 1.259 klassifizierte Notierungen, 1.073 Emittenten, 186 zusätzliche Notierungen zusammengeführt; 71 ausgeschlossen. 125 Gruppen; 1.087 Notierungen haben mindestens fünf andere Emittenten in ihrer Gruppe. Alle 1.330 Eingaben hatten keine Anbieter-Unterbranche. 12 Emittenten wurden anhand ihrer Unternehmensseiten fachlich eingeordnet; die übrigen 1.061 bleiben Branchen-Kontextgruppen. Das ist kein Nachweis, dass für alle Unternehmen bereits genaue Wettbewerber bekannt sind.

Beispiele: Micron, SK hynix und Kioxia gehören zur Speichergruppe; ASML (Lithografie), KLA (Prozesskontrolle) und TSMC (Auftragsfertigung) bleiben separat. Cadence und Synopsys teilen die EDA-Gruppe; Equinix und Digital Realty die Rechenzentrengruppe. Prologis gehört zu Logistikimmobilien. Netflix wird nicht mit beliebigen Internetdienstleistern gleichgesetzt. Banken werden nicht mit Versicherern oder Vermögensverwaltern über einen gemeinsamen Finanzsektor vermischt.

Der methodische Ausgangspunkt ist Hauptgeschäftstätigkeit statt bloßer Sektorzugehörigkeit, wie auch in der [GICS-Methodik von MSCI](https://www.msci.com/indexes/index-resources/gics). Unsere Gruppen sind eigene, transparente Zuordnungen und keine lizenzierte oder vollständige GICS-Klassifikation.

## Prüfung

`python -m unittest discover -s value_radar/risk_precompute -p 'test_peer_groups.py'`

Tests decken Notierungs-/Emittentenduplikate, Aktienklassen, normalisierte CIK, widersprüchliche Identitäten, Selbstvergleiche, veraltete Daten, bevorzugte Notierung, Reihenfolgeunabhängigkeit, Branchen-/Unterbranchentrennung, Währungshinweis und ablaufende belegte Zuordnungen ab. Neue Aktien werden im nächsten Lauf automatisch mit denselben Regeln erfasst. Fehlende Geschäftsmodelldaten werden nicht erfunden.

