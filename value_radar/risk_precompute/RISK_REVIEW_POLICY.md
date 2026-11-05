# Inhaltliche Risikoprüfung und Bankkreditvergleich

## Nachrichten

`risk_review.py` ergänzt die bestehenden Ereignisprüfdateien. Hinweise auf Mandantenwerbung und Klägerfristen werden als `legal_solicitation` markiert und je Notierung in einen Prüfkorb gelegt. Die Originalmeldungen bleiben erhalten. Weder die Zahl dieser Meldungen noch ihre Verteilung über Presseportale beweist mehrere Verfahren, unabhängige Bestätigungen oder einen neuen Schaden. Vergleiche und regulatorische Entscheidungen werden nicht allein wegen des juristischen Themas als Werbung behandelt.

`reviewed-risk-events.json` enthält explizit überprüfte Entscheidungen. Sie sind an Kandidaten-ID, Notierung und Identitätsfingerabdruck gebunden. Bestätigungen benötigen eine Unternehmensquelle, Fundstelle, Ereignisdatum, Prüfzeitpunkt, Gegenkontext und Ablaufdatum. Unvollständige, widersprüchliche, zukünftige, abgelaufene oder zur Unternehmensidentität nicht passende Entscheidungen werden zurückgewiesen. Die Software prüft die Vollständigkeit und Zuordnung der kuratierten Belege; sie verifiziert deren Inhalt nicht selbst durch einen erneuten Webseitenabruf. Neue Ereignisse bleiben bis zur inhaltlichen Prüfung offen. Der aktuelle Nachrichtenausschnitt umfasst sieben Tage; Entscheidungen können ohne passenden aktuellen Kandidaten keine Bestätigung erzeugen.

Die Entscheidung `not_subject_of_tagged_event` verwirft nur die konkrete Ereigniszuordnung, nicht jede denkbare indirekte Betroffenheit. Eine Bestätigung gilt nur für `verifiedSymbols`, niemals automatisch für andere Firmen, die im gleichen Artikel vorkommen. Bestätigung bezeichnet ein dokumentiertes Ereignis, keine quantifizierte Kurswirkung. Alle Scorebeiträge bleiben null, bis das Ereignismodell festgelegt und geprüft ist.

### Erste belegte Fälle

- Rheinmetall, 05.11.2026: Die [offizielle Quartalsmeldung](https://www.rheinmetall.com/en/media/news-watch/news/2026/11/2026-11-05-rheinmetall-news-quarterly-statement-q3), Abschnitt „Outlook: Annual guidance adjusted“, nennt die Senkung der Umsatzprognose auf rund 13,2 Mrd. EUR und der operativen Margenprognose auf rund 18,5 %. Grundlage der Prüfung war der im Webindex zugängliche Text der offiziellen Meldung; der direkte Abruf war nicht erreichbar. Dies wird mit `sourceAccess: indexed_official_release` offengelegt. Die gleiche Quelle beschreibt Wachstum und projektbedingte Verschiebungen; eine dauerhaft sinkende Nachfrage oder ein bestimmter künftiger Kursverlust wird daraus nicht behauptet.
- J&J: Die gelieferte Reuters-Überschrift ordnet die Prognosesenkung Smith+Nephew zu und erwähnt J&J im Zusammenhang mit Gesprächen. Das ist kein Nachweis einer J&J-Prognosesenkung. Nur die Überschriftenzuordnung wurde geprüft; der Artikelvolltext war nicht erreichbar.

## Vergleich der bereits geprüften US-Bankkreditdaten

`cf_sector_review_packets.json.bankCreditComparison` enthält eine separat benannte Vergleichskennzahl: Kredite ohne Zinsvereinnahmung plus mindestens 90 Tage überfällige, weiterhin verzinste Kredite, geteilt durch die vorhandenen Gesamtkredite. Die bestehenden FR-Y9C-Felder und deren bereits überprüfte Definitionen bleiben maßgeblich. [Federal-Reserve-Definition als fachlicher Kontext](https://www.federalreserve.gov/releases/e15/current/pdf/afdr_b6.pdf). Dies ist keine Gleichsetzung mit sämtlichen internationalen NPL-Definitionen.

Zugelassen werden nur geprüfte Bankprofile mit eindeutiger Identität, konsolidierter Holding, übereinstimmender Periode und Quellenprüfsumme, höchstens 180 Tage altem Berichtsdatum sowie rechnerisch passenden Komponenten. Investmentbanken/Finanzdienstleister mit anderem Profil werden nicht in diesen Bankvergleich gezwungen. Andere Notierungen derselben Holding zählen nicht als weitere Wettbewerber; widersprüchliche Meldungen derselben Holding werden ausgeschlossen. Der Median verwendet nur die anderen Holdings derselben Periode und benötigt mindestens fünf davon.

Ein höherer Anteil bedeutet mehr bereits auffällige Kredite. Ein Wert über dem Median ist kein automatisches Urteil „schlechte Bank“: Kreditarten, Sicherheiten, Garantien, Reserven und Trends fehlen in diesem Vergleich. Er ersetzt weder Liquiditätskennzahlen noch Kapitalanforderungen und schließt keine offenen allgemeinen Branchenanforderungen. Die neue Erklärung und der Vergleich werden zunächst als Daten exportiert; die bestehende Cloudflare-Oberfläche wird in diesem PR nicht geändert.

## Betrieb und Tests

Die Verarbeitung läuft automatisch innerhalb von `risk_evidence.py` im bestehenden Tagesjob. Ergebnisse und konkrete Prüfentscheidungen werden in den bereits archivierten Nachrichten- und Branchendateien gesichert. Keine zusätzlichen API-Schlüssel oder Anbieterabrufe. Der Workflow führt jetzt explizit auch `test_risk_evidence.py` aus; dieser Test fehlte bisher in der einzeln aufgezählten CI-Liste. Hinzu kommen Tests für die Inhaltsprüfung, Identitäts- und Zeitgrenzen, Doppelprüfungen, Quelldifferenzen, vergleichbare Bankperioden, mehrfach notierte Holdings, widersprüchliche Werte und zu kleine Vergleichsgruppen.
