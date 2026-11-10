# Abdeckung des Risiko-Konstrukts

Stand 10.11.2026, Konstrukt Version 0.8. `risk_construct_coverage.py` läuft täglich in `daily-risk` (eigener Schritt mit `continue-on-error`) und schreibt `daten/cf_risk_construct_coverage.json`.

## Was gemessen wird

Für jede Notierung und jede Kennzahl prüft das Skript, ob die Eingangsdaten offline vorliegen. Der Status ist einer von vier Werten:

| Status | Bedeutung |
|---|---|
| filled | Eingangsdaten vorhanden; die App kann die Kennzahl rechnen |
| missing | Eingangsdaten fehlen; mit Grund |
| app_only | Nur mit Live-Daten der App prüfbar: Bear-Szenario, dreijähriger Margen- und Umsatzverlauf |
| by_design | Für das Profil bewusst offen: Bruttomarge und EBITDA-Vergleich bei Finanzwerten, Reserve- und Anlagerisiko bei Versicherern, Verschuldung bei Bilanzen mit Kundenvermögen |

Ausgewertet wird das durchschnittlich belegte Gewicht (von 100) je Profil und Block. Dazu kommt eine Rangliste der größten Lücken nach Gewicht × fehlenden Notierungen. Das ist keine Neuberechnung des Scores: Der freie Cashflow der Unternehmen ist operativer Cashflow minus Investitionen aus dem Jahresabschluss. Peer-Stress bildet die Peer-Auswahl der App nach (`selectPeers`, `listingMatches` aus valueapp-cf; Abgleich am 10.11.2026: bei allen 1.261 Notierungen dieselben fünf ersten Peers). Er zählt als befüllt, wenn mindestens drei der ersten fünf Peers einen vorberechneten aktuellen Abstand zum Jahreshoch haben.

## Messung (Methode v2, Daten vom 10.11.2026, 1.332 Notierungen)

Durchschnittlich belegtes Gewicht: **72,3** befüllt, 10,9 fehlend, 13,9 nur in der App prüfbar, 2,8 bewusst offen.

| Profil | Notierungen | befüllt | fehlend | nur App | bewusst offen |
|---|---:|---:|---:|---:|---:|
| Unternehmen | 1.051 | 77,4 | 7,6 | 15,0 | 0 |
| Banken (inkl. GS, Schwab) | 144 | 48,5 | 31,5 | 10,0 | 10,0 |
| Versicherer | 54 | 53,3 | 16,7 | 10,0 | 20,0 |
| Spezialfinanzierer | 83 | 61,8 | 13,3 | 10,0 | 14,9 |

Größte Lücken (Gewicht × fehlende Notierungen):

| Profil | Kennzahl | fehlend | Hauptgründe |
|---|---|---:|---|
| Unternehmen | Erwartungslücke Reverse DCF (10) | 411 | 218 Währungskonflikt, 98 Cashflow fehlt, 95 freier Cashflow ≤ 0 |
| Unternehmen | FCFF-Marge (10) | 107 | Cashflow, Investitionen oder Umsatz fehlen |
| Banken | LCR (7,5) | 118 | keine geprüfte LCR (EU-Daten enthalten keine LCR) |
| Banken | CET1-Puffer (10) | 84 | keine geprüfte Anforderung |
| Unternehmen | Expected Shortfall (15) | 55 | 33 ohne Kurshistorie, 22 fehlerhaft |
| Banken | Erwartungslücke Eigenkapitalrendite (10) | 76 | 63 Währungskonflikt |
| Unternehmen | Peer-Stress (5) | 141 | 72 mit weniger als drei Peers, 69 ohne Geschäftsfamilie oder Unterbranche |

Korrektur gegenüber Methode v1: Dort galt Peer-Stress bei 736 Unternehmen als fehlend, weil der strengere vorberechnete Sektorvergleich (fünf Firmen derselben Währung) als Näherung diente. Die App rechnet den Peer-Stress aber aus den eigenen Kurshistorien der Peers ohne Währungsbeschränkung. Tatsächlich fehlt er nur bei 141 Unternehmen.

## Folgerungen

1. **Währungskonflikt:** Bei 218 Unternehmen und 63 Banken unterscheiden sich Berichts- und Handelswährung. Das sind meist ADRs und OTC-Notierungen. Eine geprüfte Umrechnung, wie sie die App für einzelne Notierungen schon kann, würde den Bewertungsblock breit füllen.
2. **Peer-Stress:** Er fehlt nur noch bei rund 180 Notierungen, weil keine Geschäftsfamilie oder Unterbranche zugeordnet ist oder weniger als drei Peers existieren. Abhilfe wären Unterbranchen in den Stammdaten; der Hebel ist mit 5 % Gewicht klein.
3. **Bank-LCR:** Für EU-Banken fehlt eine Quelle. Die Säule-3-Berichte enthalten die LCR, ein KM1-Import wie bei den internationalen Banken wäre möglich.
4. **Kurshistorie:** 55 Unternehmen und 41 Banken ohne verwertbare Historie, meist OTC-Notierungen.

## Währungskonflikt bei Stammaktien (10.11.2026)

Der Abschluss-Export (`export_fundamentals.py`) setzt jetzt für Stammaktien mit abweichender Berichtswährung automatisch die Aktienbasis 1:1 (`share_basis_rule.py`, Methode `rule_ordinary_share_isin_v1`). Bedingungen: Wertpapiertyp „stock“ ohne Sonderaktienklasse und eine Nicht-US-ISIN, also die Heimat-ISIN der Stammaktie; Depositary Receipts tragen eigene US-ISINs. Die App rechnet damit den Abschluss zum EZB-Kurs in die Handelswährung um und gibt die Bewertung frei. Manuell geprüfte Einträge in `share_basis.json` haben Vorrang.

Betroffen sind 189 Notierungen: 134 Unternehmen, 32 Banken, 12 Versicherer, 10 Spezialfinanzierer (darunter 2 georgische Banken ohne EZB-Kurs für GEL, die offen bleiben). Die Einträge erscheinen, sobald der Export die jeweilige Datei neu schreibt (mindestens wöchentlich). Die Messung unterscheidet bis dahin „Stammaktie, Aktienbasis noch nicht in der Abschlussdatei“ von „ADR oder unklare Aktienbasis“. Echte ADRs (rund 120) brauchen weiterhin ein geprüftes Umtauschverhältnis. Wenn die App neuere Primärdaten als den Ersatzabschluss hat, nutzt sie den Ersatzabschluss nicht. Einzelne Notierungen können deshalb trotz Aktienbasis offen bleiben.

## Fehlende Kurshistorien (10.11.2026)

Ausgangslage: 109 Notierungen ohne verwertbare eigene Historie. 76 haben keinen Eintrag, 18 eine Historie mit längeren Lücken, 15 weniger als zwei Handelsjahre. Die meisten sind OTC-Notierungen (64), dazu Neuemissionen (CoreWeave, Nebius, Magnum Ice Cream, Metlen) und 23 Einträge ohne Börsenpräfix (Vorzugsaktien wie MS-PA, BML-PH und Ticker ohne Zuordnung).

`risk_history_proxy.py` läuft in `daily-risk` direkt nach dem Kursexport. Fehlt einer Notierung die eigene vollständige Historie, hat dieselbe Aktie (gleiche ISIN) aber eine Börsennotierung (keine OTC-Notierung) mit vollständiger, frischer Historie, legt das Skript deren Risikozusammenfassung unter dem Symbol der Notierung ab. Die Stammaktie hat dabei Vorrang vor einem ADR. Der Eintrag trägt `historySource` und einen Hinweistext, den die App unter „Berechnung und Datenqualität“ zeigt. Wechselkursschwankungen zur Handelswährung sind nicht enthalten. Eigene vollständige Historien werden nie überschrieben. `export-risk.ts` behandelt Ersatzeinträge nie als frisch und versucht die eigene Historie jedes Mal neu. Ist die Heimathistorie nicht mehr verwertbar, wird der Ersatz entfernt. Das Rohdaten-Archiv vermerkt die Quelle (`price.historySource`).

Probelauf: 30 Ersatzhistorien, z. B. OTC:MBFJF aus TSE:8306 (MUFG) und OTC:LLDTF aus LSE:LLOY. Expected Shortfall fehlt danach bei 35 statt 55 Unternehmen und bei 32 statt 41 Banken. Belegtes Gewicht gesamt 72,9 statt 72,3.

Offen und sachlich richtig offen: Neuemissionen mit weniger als zwei Handelsjahren. Offen ohne Ersatz: OTC-Notierungen ohne Börsennotierung im Universum (vor allem chinesische Banken) und Einträge ohne Börsenpräfix. Nebenbefund: STO:INVE_B trägt im Universum die ISIN der A-Aktie (SE0015811955).
