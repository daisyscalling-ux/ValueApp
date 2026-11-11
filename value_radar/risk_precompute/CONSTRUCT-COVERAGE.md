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

FCFF-Marge: Die App liest den berichteten FCFF und den Umsatz (TTM) aus der ROIC-Bewertungszeile. Die Messung nutzte bisher eine Näherung aus dem Ersatzabschluss (operativer Cashflow, Investitionen). Seit dem Exportfeld `fcff_margin` im Universum (aus derselben ROIC-Zeile) misst sie genau das, was die App sieht. Bis zum ersten Universumsexport mit diesem Feld gilt weiter die Näherung.

Bankdaten (10.11.2026): 21 Bank-ADRs übernehmen die geprüften Konzernquoten ihrer Stammaktie. Außerdem verwarf `auditUniverse` seit der Ersatzhistorie aus der Heimatnotierung 21 Notierungen als Identitätskonflikt, weil die Historie die Heimatwährung trägt; gleiche ISIN gilt jetzt als Identitätsnachweis. Probelauf: CET1-Puffer 90 → 68 fehlend, LCR 121 → 105, Kreditqualität 97 → 88; Banken im Mittel 51,8 → 54,6 gefüllte Gewichtspunkte.

Kurshistorien (10.11.2026): Von 76 Notierungen ohne verwertbare Historie sind 57 (52 ISINs) Kandidaten für eine Heimatnotierung außerhalb des Universums, vor allem rund 35 OTC-Linien australischer, chinesischer und anderer ausländischer Werte (ASX, HKEX, SSE …). `export-home-histories.ts` sucht diese über die ROIC-Ticker-Suche (exakt gleiche ISIN, Hauptnotierung, keine OTC-Linie, Aktie, eindeutig) und lädt ihre Historie nach `cf_risk.json/homeListings`; `risk_history_proxy.py` nutzt sie wie eine Heimatnotierung aus dem Universum. Nicht lösbar auf diesem Weg: 15 Notierungen mit weniger als zwei Handelsjahren (Börsengänge und Abspaltungen) und 21 Universumszeilen ohne geprüfte Notierung (u. a. Vorzugsaktien).

Notierungsidentität in der App (10.11.2026): `listingMatches` der App erkannte nordische Aktiengattungen (`STO:VOLV_B`) und LSE-Symbole mit Punkt (`LSE:RR.`) nicht. Dadurch fehlten 48 Notierungen in der ganzen App, auch als Peers. Korrektur in valueapp-cf; die Messung nutzt jetzt direkt `value_radar/listing_identity.py`, das mit der App identisch ist (1.411 Paare geprüft). Wirkung auf denselben Daten: gesamt 76,3 → 76,7, Peer-Stress-Lücken bei Unternehmen 144 → 102, Reverse-DCF-Lücke 90 → 56.

Vorzugsaktien (10.11.2026, Nutzerentscheidung): 14 Vorzugsaktien US-amerikanischer Banken (BAC-PB, JPM-PD, WFC-PC, GS-PA, MS-PA, USB-PH …) liegen bewusst außerhalb des Modells, weil es für Stammaktien gebaut ist. Die App zeigt einen Hinweis statt eines Scores. Die Messung führt ihre Kennzahlen als `by_design` (Grund „Vorzugsaktie: Risikomodell gilt für Stammaktien“) statt als Lücke. Die Erkennung (`preferred_instrument`) entspricht `preferredInstrument` der App.

EBITDA-Marge gegenüber Peers (10.11.2026): Die Messung zählte Firmen derselben Branche mit Marge. Die App (`competitionMetrics`) vergleicht dagegen mit den ausgewählten Peers, bis zu 8 und seit den Branchengruppen auch aus verwandten Branchen. Die Messung zählt jetzt genau diese Peers mit EBITDA-Marge, ohne die eigene Notierung. Wirkung auf denselben Daten: Lücken 90 → 29, Unternehmen 82,5 → 82,8.

## Profilkorrektur für falsch eingeordnete Versicherer (10.11.2026)

Generali und Tryg führt der Datenanbieter als „Insurance brokers/Services“. Eine geprüfte Korrektur je ISIN (`reviewed-profile-overrides.json`, mit Beleg, SHA-256 und Ablauf) ordnet sie dem Profil `insurer` zu. Sie gilt nur, solange der Anbieter dieselbe Branche meldet und die Prüfung gültig ist. Probelauf: Versicherer 54 → 57, Solvenzquote vorhanden 17 → 19, offen 37 → 38 (Tryg ohne zugelassenes System), Unternehmen 1.053 → 1.050, Gesamtabdeckung 78,3 → 78,2 % (Tryg-Lücke jetzt sichtbar). Details in `INSURER-SOURCES.md`.

## Universum = Indexmitglieder (10.11.2026)

Durch einen still fehlgeschlagenen Wikipedia-Abruf (HTTP 403) fehlten 274 S&P-500-Mitglieder; ein Screener-Rückfall füllte das Universum mit 215 OTC-Linien und rund 60 ausländischen ADRs. Zusätzlich verdrängten gleichnamige US-Ticker europäische Indexwerte (DTE.DE, MRK.DE, AIR.PA). Neu: S&P 500 mit beschreibendem User-Agent oder datierter fester Liste, Zusammenfassung nur im selben Land, `index_membership` je Zeile. Universum 1.330 → 1.345: 310 Indexwerte hinzu, 295 Nicht-Mitglieder entfernt. Vor der Korrektur war im Segment der OTC-Linien 9,8 % des Gewichts offen, bei den US-Hauptnotierungen 2,8 %. Bis die neuen Titel Daten haben, sinkt die Abdeckung vorübergehend. Details in `value_radar/UNIVERSUM.md`.

## US-Banken im S&P 500 (11.11.2026)

13 weitere US-Bankholdings sind dem FR-Y-9C-Bestand und den Fed-Anforderungen zugeordnet; nun 22 statt 9. Probelauf: S&P 500 gefüllt 80,69 → 80,95 %, offen 3,24 → 3,01 %. Offen bleiben je Bank LCR und Kreditqualität. Details in `regulatory_export/BHCF.md`.

## Peers: Auffüllung aus derselben Branche (11.11.2026)

Mit dem Index-Universum wurden kuratierte Familien zu dünn: Micron stand allein in „Speicherchips“, Meta und Alphabet hatten nur sich gegenseitig, und Monster fand keine Getränke-Peers. Neue Regel (identisch in `valueapp-cf/src/lib/peer-selection.ts`): Unter drei Peers füllen zuerst Firmen derselben Branche aus anderen Familien bis fünf auf (nicht für Unterbranchen), danach wie bisher die geprüfte Gruppe. Die Gruppen sind um Elektronikmärkte, Dienste für das Gesundheitswesen, Rundfunk, Zeitungsverlage und Pipelines ergänzt. Messung: Peer-Stress offen 26 → 9, EBITDA-Vergleich 35 → 22, S&P 500 offen 2,16 → 1,86 %. App und Pipeline wählen bei 1.335 von 1.339 Titeln identische Peers. Bei 4 Titeln (AJG, AON, C, WFC) weicht nur die Reihenfolge ab; das bestand schon vorher, die ersten fünf Peers sind gleich.

## Folgerungen

1. **Währungskonflikt:** Bei 218 Unternehmen und 63 Banken unterscheiden sich Berichts- und Handelswährung. Das sind meist ADRs und OTC-Notierungen. Eine geprüfte Umrechnung, wie sie die App für einzelne Notierungen schon kann, würde den Bewertungsblock breit füllen.
2. **Peer-Stress:** Er fehlt nur noch bei rund 180 Notierungen, weil keine Geschäftsfamilie oder Unterbranche zugeordnet ist oder weniger als drei Peers existieren. Abhilfe wären Unterbranchen in den Stammdaten; der Hebel ist mit 5 % Gewicht klein.
3. **Bank-LCR:** Für EU-Banken fehlt eine Quelle. Die Säule-3-Berichte enthalten die LCR, ein KM1-Import wie bei den internationalen Banken wäre möglich.
4. **Kurshistorie:** 55 Unternehmen und 41 Banken ohne verwertbare Historie, meist OTC-Notierungen.

## Versicherer außerhalb von Solvency II/UK (11.11.2026)

Entscheidung des Nutzers: Die Solvenzquote wird nur für Gruppen unter Solvency II (EWR) oder Solvency UK verglichen. Maßgeblich ist das ISIN-Land; geprüfte Ausnahme ist Prudential plc (Gruppenaufsicht Hongkong). Andere Länder (USA, Japan, Schweiz, Bermuda) zählen als `by_design` mit Grund. Spiegel von `insurerSolvencyScope` (valueapp-cf). Messung: Solvenzquote fehlend 41 → 10, 31 bewusst außerhalb, 12 vorhanden; S&P 500 offen 2,16 → 1,62 %, Nikkei 225 1,60 → 1,20 %.

## Währungskonflikt bei Stammaktien (10.11.2026)

Der Abschluss-Export (`export_fundamentals.py`) setzt jetzt für Stammaktien mit abweichender Berichtswährung automatisch die Aktienbasis 1:1 (`share_basis_rule.py`, Methode `rule_ordinary_share_isin_v1`). Bedingungen: Wertpapiertyp „stock“ ohne Sonderaktienklasse und eine Nicht-US-ISIN, also die Heimat-ISIN der Stammaktie; Depositary Receipts tragen eigene US-ISINs. Die App rechnet damit den Abschluss zum EZB-Kurs in die Handelswährung um und gibt die Bewertung frei. Manuell geprüfte Einträge in `share_basis.json` haben Vorrang.

Betroffen sind 189 Notierungen: 134 Unternehmen, 32 Banken, 12 Versicherer, 10 Spezialfinanzierer (darunter 2 georgische Banken ohne EZB-Kurs für GEL, die offen bleiben). Die Einträge erscheinen, sobald der Export die jeweilige Datei neu schreibt (mindestens wöchentlich). Die Messung unterscheidet bis dahin „Stammaktie, Aktienbasis noch nicht in der Abschlussdatei“ von „ADR oder unklare Aktienbasis“. Echte ADRs (rund 120) brauchen weiterhin ein geprüftes Umtauschverhältnis. Wenn die App neuere Primärdaten als den Ersatzabschluss hat, nutzt sie den Ersatzabschluss nicht. Einzelne Notierungen können deshalb trotz Aktienbasis offen bleiben.

## Fehlende Kurshistorien (10.11.2026)

Ausgangslage: 109 Notierungen ohne verwertbare eigene Historie. 76 haben keinen Eintrag, 18 eine Historie mit längeren Lücken, 15 weniger als zwei Handelsjahre. Die meisten sind OTC-Notierungen (64), dazu Neuemissionen (CoreWeave, Nebius, Magnum Ice Cream, Metlen) und 23 Einträge ohne Börsenpräfix (Vorzugsaktien wie MS-PA, BML-PH und Ticker ohne Zuordnung).

`risk_history_proxy.py` läuft in `daily-risk` direkt nach dem Kursexport. Fehlt einer Notierung die eigene vollständige Historie, hat dieselbe Aktie (gleiche ISIN) aber eine Börsennotierung (keine OTC-Notierung) mit vollständiger, frischer Historie, legt das Skript deren Risikozusammenfassung unter dem Symbol der Notierung ab. Die Stammaktie hat dabei Vorrang vor einem ADR. Der Eintrag trägt `historySource` und einen Hinweistext, den die App unter „Berechnung und Datenqualität“ zeigt. Wechselkursschwankungen zur Handelswährung sind nicht enthalten. Eigene vollständige Historien werden nie überschrieben. `export-risk.ts` behandelt Ersatzeinträge nie als frisch und versucht die eigene Historie jedes Mal neu. Ist die Heimathistorie nicht mehr verwertbar, wird der Ersatz entfernt. Das Rohdaten-Archiv vermerkt die Quelle (`price.historySource`).

Probelauf: 30 Ersatzhistorien, z. B. OTC:MBFJF aus TSE:8306 (MUFG) und OTC:LLDTF aus LSE:LLOY. Expected Shortfall fehlt danach bei 35 statt 55 Unternehmen und bei 32 statt 41 Banken. Belegtes Gewicht gesamt 72,9 statt 72,3.

Offen und sachlich richtig offen: Neuemissionen mit weniger als zwei Handelsjahren. Offen ohne Ersatz: OTC-Notierungen ohne Börsennotierung im Universum (vor allem chinesische Banken) und Einträge ohne Börsenpräfix. Nebenbefund: STO:INVE_B trägt im Universum die ISIN der A-Aktie (SE0015811955).

## ADR-Umtauschverhältnisse (10.11.2026)

`fundamental_export/adr_basis.py` läuft nach jedem Abschluss-Export und leitet das Verhältnis eines Depositary Receipts zur Stammaktie doppelt ab:
1. **Aktienzahl:** Stammaktien der Heimatnotierung ÷ ADR-Einheiten. Sie muss ein Standardverhältnis (1, 2, 4, 10, 1/10 …) auf 2 % treffen.
2. **Kurs:** ADR-Kurs ÷ Heimatkurs zum EZB-Kurs. Er muss dasselbe Verhältnis auf 10 % treffen; OTC-Kurse können einige Tage alt sein.

Die Heimatnotierung ist die Stammaktie mit derselben ISIN im Universum. Manuelle Einträge in `share_basis.json` haben Vorrang. Ein Verhältnis, das nicht mehr bestätigt wird, wird sofort entfernt. Die App (`sharesPerUnit`) prüft Methode und Belege erneut, rechnet den Gewinn je Aktie auf die ADR-Einheit um und rechnet firmenweite Beträge nur in die Handelswährung um.

Probelauf: Verhältnis für 61 ADRs gesetzt. 67 ADRs haben keine Heimatnotierung im Universum, 7 scheitern an fehlenden Daten oder an nicht übereinstimmenden Werten. In der Abdeckung sinken die ADR-Konflikte bei Unternehmen von 82 auf 41, bei Banken von 31 auf 24.

## Ersatz für die Erwartungslücke ohne positiven Cashflow (10.11.2026)

Seit Konstrukt-Version 0.9 gilt für Unternehmen ohne positiven freien Cashflow statt des Reverse DCF der Aufschlag des EV/EBITDA auf den Median der Peers (mindestens drei Peers mit positivem EV/EBITDA, eigenes EV/EBITDA positiv). Die Messung bildet das nach. Ergebnis mit den Daten vom 10.11.2026: Die Erwartungslücke fehlt bei 90 statt 258 Unternehmen. Davon haben 51 weniger als drei Peers mit EV/EBITDA, 34 sind ADRs ohne Aktienbasis, 5 haben ein negatives EBITDA. Belegtes Gewicht gesamt 75,8, Unternehmen 80,9.

Verkürzte Historie (10.11.2026): Notierungen mit 253 bis 504 Kurspunkten (`shortHistory`) zählen bei Expected Shortfall und Volatilität als gefüllt; der größte Rückgang bleibt mit dem Grund „Verkürzte Historie“ offen (Methode in `RISIKOSCORE.md` der App). Betrifft vor allem die 15 jungen Notierungen aus der Kurshistorien-Analyse; unter 253 Kurspunkten bleibt alles offen.

Erster Lauf mit Heimatnotierungen (10.11.2026): 6 von 52 ISINs aufgelöst (ASX:CBA, ASX:ANZ, ASX:CSL, KRX:000660, AMEX:ET, LSE:MTLN), 4 Kurslücken geschlossen (Kursblock-Lücken Banken 32 → 30, Unternehmen 35 → 33; gesamt 76,1 → 76,3). Für die 46 ungelösten ISINs, überwiegend China/Hongkong, hält die Auflösung seit Methode `isin-primary-v2` den Grund fest (`no_search_results`, `no_same_isin`, `otc_only`, `no_active_stock`, `primary_in_universe`, `no_primary_listing`, `ambiguous_primary`), samt Kandidaten derselben ISIN und einer Stichprobe anderer Treffer (`cf_risk.json/homeResolution`, Zählung in `homeListingsReport.unresolvedReasons`). Daran entscheidet sich der nächste Schritt; eine Lockerung der Regel (z. B. Nebenbörse, andere Aktiengattung) wird erst nach dieser Diagnose und mit Begründung erwogen.

ISIN der OTC-Linien chinesischer A/H-Konzerne (10.11.2026): Die Diagnose der Heimatnotierungen zeigte für 12 OTC-Stammaktien, dass das Universum die Unternehmens-ISIN der **A-Aktie** führt, die OTC-Linie aber die **H-Aktie** handelt (ROIC, exakte Notierung). Die H-ISINs sind durch die HKEX List of Securities belegt (sha256 `f872b4e3…`). Korrektur über den vorhandenen Prüfmechanismus `reviewed_listing_reference.json` (Prüfung bis 09.05.2027), angewendet beim Universumsexport und – damit die Korrektur nicht als Identitätswechsel gilt – auch auf ältere Snapshots (`export_continuity.baseline`). Bankdaten gelten für den Konzern: `reviewed-key-metrics.json` führt die H-ISIN als `shareClassIsins`, ADRs übernehmen die Quoten über den Konzern (LEI bzw. Emittenten-ISIN) statt über die gleiche ISIN. Probelauf: keine Änderung an Abdeckung, Bankdaten oder Identitätsstatus; der Gewinn (Hongkong-Heimatnotierung für die Kurshistorie) zeigt sich erst im Lauf mit ROIC. Neue tägliche Prüfung `listing_isin_audit.py` (nur Bericht, `cf_listing_isin_audit.json`) vergleicht alle OTC-Stammaktien mit der exakten Notierung und meldet neue Konflikte zur Prüfung, z. B. voraussichtlich Bank of Communications (OTC:BKFCF).

Peers aus verwandten Branchen (10.11.2026): Liefert die exakte Branche weniger als drei Peers, füllt eine geprüfte Gruppe verwandter Branchen bis fünf auf. Die Gruppen stehen in `src/lib/peer-industry-groups.json`, einer identischen Kopie aus valueapp-cf: 25 Gruppen, 92 Branchen, 26 bewusst ohne Gruppe, 9 Bezeichnungen angeglichen. Die Messung wendet dieselbe Regel an. Abgleich mit der App: gleiche Peers bei 1.305 von 1.310 Notierungen, bei 2 nur andere Reihenfolge, bei 3 britischen REITs ein anderer 8. Peer (die App-Sortierung ist nicht durchgängig widerspruchsfrei; Peer-Stress nutzt nur die ersten fünf). Wirkung: Peer-Stress-Lücken bei Unternehmen 102 → 14, Reverse-DCF-Lücke 56 → 41, gesamt 76,7 → 77,2.

Pariser Aktien als Peers (10.11.2026): Das Vorzugsaktien-Muster der App (und dieses Spiegels) traf die Börsenendung `.PA`, deshalb waren 62 Pariser Aktien nie Peers. Korrektur in valueapp-cf; die Endung wird nur abgetrennt, wenn die Notierungsprüfung sie bestätigt. Die Peer-Auswahl ändert sich bei 353 Notierungen, App und Spiegel stimmen bei allen 1.310 überein. Die Abdeckung ändert sich kaum (Peer-Stress Spezialfinanzierer 11 → 10), weil die betroffenen Firmen schon genug Peers hatten. Die Wirkung liegt in der Qualität der Vergleiche.

EU-Banken aus dem EBA Pillar 3 Data Hub (10.11.2026): LCR und vollständige CET1-Anforderung aus EU KM1 für alle 33 EU-Banken der Zuordnung (43 Notierungen inkl. ADRs). Bank-LCR-Lücken 93 → 50, CET1-Puffer-Lücken 56 → 47, Banken 55,2 → 58,0. Ablauf und Regeln in `regulatory_export/EU_BANKS.md`.

EU-Banken nur aus der Säule 3 (10.11.2026): 9 Banken ohne EBA-Transparenzdaten (Erste, mBank, Erste Polska, Crédit Agricole S.A., Eurobank, Piraeus, Sydbank, Ringkjøbing, Sparebanken Norge) bekommen Kapitalquoten, Anforderung und LCR ausschließlich aus EU KM1. Bank-LCR-Lücken 50 → 41, CET1-Puffer 47 → 40, Banken 58,0 → 59,0.
