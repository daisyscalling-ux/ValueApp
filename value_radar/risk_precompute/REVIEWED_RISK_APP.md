# Geprüfte Ereignisse und Bankkontext in der Einzelanalyse

Der App-Export läuft nun nach der Ereignisprüfung. Er übernimmt deren Ergebnisse nur, wenn beide Prüfdateien ausdrücklich dieselbe `coverageGeneratedAt` wie die Abdeckungsdatei nennen. Veraltete oder fremde Läufe werden nicht kombiniert. Unternehmensidentität, Gültigkeitszeitraum und bei Bankvergleichen Holding, Berichtsperiode und Quellenprüfsumme müssen passen. Die unveränderten Abdeckungswerte erhalten einen Zusatz `domains.reviewedRisk`; die bestehende Größe und SHA256-Prüfung der App-Teilpakete bleiben bestehen.

Im lokalen Ordner `C:/Users/Patrick/Desktop/cf` sind Worker und Einzelanalyse angepasst: belegte Ereignisse mit Gegenkontext, Quellen und Ablaufdatum; korrigierte Unternehmenszuordnungen; gebündelte Kanzleihinweise; erklärte Kreditquote mit Vergleichsmedian. Meldungen werden als Text gerendert, nicht als HTML. Abgelaufene Ereignisse werden auch beim Anzeigen nochmals verworfen. Keine Änderung der Risikopunkte. Vorherige App-Versionen können die erweiterten Teilpakete weiterhin lesen.

## Neue Originaldaten

JPMorgan Chase & Co., Konzern, Quartalsdurchschnitt zum 30.06.2026: HQLA 975.412 Mio. USD, Nettoabflüsse 885.521 Mio. USD, gemeldete LCR 110 %. Die ebenfalls berichteten 118 % gehören zur Banktochter und werden nicht auf den börsennotierten Konzern übertragen. Originalquelle: [Form 10-Q, Seite 52](https://www.sec.gov/Archives/edgar/data/19617/000162828026054343/jpm-20260630.htm), Abschnitt Liquidity Risk Management. Die Werte wurden aus der zugänglichen Originaltabelle gelesen und mit der bestehenden Holdingzuordnung und Berechnungsprüfung getestet.

Diese Juni-Angabe passt zur aktuell importierten Juni-Konzernmeldung; sie wird nicht als neuester verfügbarer Quartalsabschluss bezeichnet. Die Identitäts-, Perioden- und Altersprüfung bleibt aktiv. Neue September-Kapitaldaten erfordern auch eine passende neue Liquiditätsangabe. Weitere offene Branchenanforderungen bleiben offen. Bei Bank of America enthält der ebenfalls geprüfte Juni-Bericht HQLA und Quote, aber die benötigten Nettoabflüsse waren im betrachteten Abschnitt nicht ausgewiesen; es wurde kein Nenner rückwärts aus der gerundeten Quote erfunden.

## Veröffentlichung

1. PR zusammenführen und `daily-risk` starten. Der Lauf erzeugt die erweiterten App-Teilpakete.
2. Den aktualisierten lokalen `cf`-Ordner mit dem bisherigen Cloudflare-Verfahren veröffentlichen. Worker und Frontend gehören zu dieser Änderung; ein reiner Austausch der statischen Dateien reicht nicht.
3. In der Einzelanalyse zum Beispiel J&J und JPMorgan prüfen. Bei J&J erscheint die korrigierte Nachrichtenzuordnung, solange die datierte Meldung und ihre Prüfung gültig sind. Bei JPMorgan erscheinen Kreditvergleich und neue Konzern-LCR, sofern die Datenbedingungen weiterhin erfüllt sind.

Tests: Python-Prüfungen einschließlich falscher Laufzuordnung und Holding/Periode, App-Prüfungen einschließlich Ablaufdatum und sicherer Textdarstellung sowie lokaler Durchlauf Export → Worker-Auswahl → Darstellungsmodell mit den verfügbaren 1.331-Aktien-Daten. Keine automatische Cloudflare-Veröffentlichung.
