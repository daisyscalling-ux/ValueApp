# Feldweise Risikodaten und Arbeitsbloecke fuer das Universum

Stand: 26.10.2026. Dieser Block erweitert die Daten- und Pruefschicht. Er aendert keine Fair-Value-Berechnung und fuehrt keine neue Verlustwahrscheinlichkeit ein.

## Ausgangslage nach PR 68

Der veroeffentlichte Lauf vom 25.10.2026 um 19:45 UTC verarbeitet 1.330 Notierungen. Vier weitere Bilanzfaelle wurden geschlossen, 60 bleiben in den Hauptmaerkten offen. Alle 49 EDINET-Ziele wurden ohne Abruffehler geladen (26 vollstaendige Cashflows, 23 teilweise). Der Vergleich zeigt keine verlorene Verfuegbarkeit.

## Gemeinsame Aenderungen

- Finanzfelder werden einzeln auf Periode, Waehrung und Aktualitaet geprueft. Eine ungueltige CapEx-Angabe blockiert FCF, aber nicht eine unabhaengig belegte Schuldenquote. Eine ungueltige Bilanzsumme blockiert weiterhin alle davon abhaengigen Quoten. Keine gemischten Perioden und keine Uebernahme einzelner Werte zwischen Ersatzabschluessen.
- Quellen und Bezugsdaten werden pro Kennzahl als basis mitgefuehrt. Legacy-Daten ohne einzelne Feldquellen behalten die bisherige Abschlussquelle; dies ist keine neue Einzelverifikation.
- Zusaetzlicher Kontext fuer normale Unternehmen: operativer Cashflow, Kassenbestand, Eigenkapital und Ergebnis jeweils relativ zur Bilanzsumme am Jahresende. Diese supplementalen Beobachtungen schliessen fehlende FCF- oder Verschuldungsdaten NICHT und beeinflussen die Auswahl des primaeren Abschlusses nicht. Ergebnis / Schlussbilanz ist keine mit Durchschnittsvermoegen berechnete ROA.
- Investment managers / Asset management werden als specialist_financial behandelt. Anbietergruppen koennen gemischte Bank- und Vermoegensverwaltungsgeschaefte enthalten: Das Geschaeftsmodell und anwendbare Kapitalregeln bleiben daher explizite Pruefaufgaben. Verwaltete Kundenvermoegen, Nettozufluesse und Gebuehrenabhaengigkeit kommen als weitere Anforderungen hinzu. Vollstaendige Buchwerte ergeben nur context_only, keinen fertigen Branchenrisikoscore.
- Die offizielle JGAAP-Zahl PurchaseOfNoncurrentAssetsInvCF wird separat erfasst. Daraus kann der Cashflow nach gemeldeten Kaeufen langfristiger Vermoegenswerte gebildet werden. Diese breitere Abgrenzung ist NICHT FCF und ersetzt keine fehlende CapEx-Zahl. Aehnlich benannte unternehmenseigene IFRS-Tags bleiben Diagnosematerial.
- cf_risk_workplan.json gruppiert die offenen Aufgaben aller Notierungen nach Ursache, Bereich und Marktprioritaet. Finanzfelder, Quellenabgleich, Branchenanforderungen, Identitaet, Historien und Vergleichsgruppen bleiben unterscheidbar. Kleine Maerkte bleiben enthalten, werden aber nachgeordnet.
- Im Vorher-nachher-Bericht werden Aenderungen der Branchenpruefung gesondert als framework_changed ausgewiesen. Sie sind weder Datenverlust noch Datenbeschaffung. Der neue Arbeitsplan wird nach dem finalen Audit als Artefakt und Repository-Datei veroeffentlicht; die groessten Gruppen erscheinen im Laufbericht.

## Validierung

168 Python-Tests, 10 Tests zur feldweisen Bilanzpruefung, 10 EDINET-Integrationstests, 33 Universumschecks, Kontextpruefungen, 24 Branchen-/Kalenderchecks und 6 Checks zum breiten Branchenkontext bestanden.

Replay auf dem gespeicherten Produktionsstand, mit identischem Auswertungszeitpunkt: 2.399 bereits verfuegbare Kennzahlen in unveraenderten Branchenprofilen behalten exakt ihren Wert. 24 Notierungen wechseln sachgerecht in die gesonderte Finanzbranchenpruefung; diese werden nicht als neue Datengewinnung gezaehlt. 3.990 zusaetzliche Einzelbeobachtungen werden aus vorhandenen Abschluessen getrennt exportiert (976 operativer Cashflow, 1.006 Kasse, 1.005 Eigenkapital, 1.003 Ergebnis). Sie sind keine 3.990 neuen Unternehmen oder unabhaengigen Quellen.

Der Arbeitsplan enthaelt im Replay 75 Ursachengruppen, davon 47 in Hauptmaerkten. 1.030 Notierungen haben mindestens eine offene Aufgabe, beispielsweise die individuelle Branchenpruefung oder einen engeren Peer-Vergleich. Diese Zahl darf nicht mit den 60 offenen Bilanzfaellen verwechselt werden. Neue Originalfakten aus EDINET muessen im produktiven Lauf erneut heruntergeladen werden; der Parser ist auf v3 angehoben.

## Quellen zur Abgrenzung

- IAS 7: Investitionstaetigkeit umfasst langfristige Vermoegenswerte und andere Anlagen, nicht nur Sachanlagen und immaterielle Anlagen. https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows.html
- FSA Taxonomie 2026, jppfs_cor_2025-11-01.xsd, PurchaseOfNoncurrentAssetsInvCF (monetaerer Dauerwert): https://www.fsa.go.jp/search/20251111.html
- Beispiel fuer die geschaeftsspezifischen Groessen AUM, Nettozufluesse und Gebuehrenwachstum: BlackRock Jahresergebnisse 2025. https://www.blackrock.com/corporate/newsroom/media/press-releases/blackrock-reports-fourth-quarter-2025

## Naechster Lauf

Nach Merge einmal daily-risk auf main. Keine neuen Secrets, kein gesonderter Lauf pro Aktie. Fuer diesen Datenblock ist kein Cloudflare-Upload erforderlich; neue Zusatzfelder werden zunaechst in der Datenschicht und den Laufberichten bereitgestellt. Vor einer zusaetzlichen Anzeige in der App ist deren Verbrauch gesondert zu integrieren.
