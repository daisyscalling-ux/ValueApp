# Insurer capital disclosures

The reviewed registry supplies original Solvency II group disclosures independently
of the US bank source. The daily regulatory-context job checks identity, review
expiry, report age, scope and same-basis arithmetic; it does **not** fetch or approve
new financial reports automatically. Updating `generatedAt` never changes a report
period. New reports require a reviewed registry update.

Initial coverage is XETR:ALV and XETR:MUV2 only. The registry binds exact input
identity, not ticker similarity, to the consolidated group. ADRs and OTC listings
are not silently included. EUR amounts are currency units, not millions. Jurisdiction
support is presently German Solvency II groups supervised by BaFin.

Allianz: H1 2026 report pages 4 and 15: EUR97.0bn eligible own funds, EUR43.1bn
capital requirement and 225% on quarterly dividend accrual. The separately reported
218% uses full annual dividend accrual. Its numerator and denominator are not
back-calculated. Volatility adjustment and yield-curve extension are disclosed;
the interim report does not separately quantify transitional effects. SFCR2025
page7 supplies group supervisory scope, not the interim amounts.

Munich Re: SFCR2025 pages67 and69: EUR54,660m eligible own funds for the **total
group** SCR of EUR18,230m, ratio300% with transitional measures. The 298% without
transitional measures is kept as ratio-only supplementary evidence. Proposed
dividend and pending buybacks are already deducted. Neither the consolidated-part
numerator nor minimum consolidated group SCR can substitute for these total-group
figures. SFCR page4 identifies BaFin. The official English translation states that
the German original is binding.

Annual records expire after550days, interim records after210days; the earlier
registry review expiry also applies. These are operational freshness ceilings,
not assertions that no newer report exists. The UI labels annual evidence and
its actual reporting period. Invalid or ambiguous primary evidence remains open.

Amounts/ratio agreement allows1.5percentage points for rounded published amounts.
Ratio-only variants cannot fulfill missing amounts. Both Python and TypeScript
validate before displaying coverage. These capital inputs close only the three
capital-data requirements, not underwriting, reserves, investment or liquidity
risk. No score contribution or historical point-in-time eligibility is assigned.

## Erweiterung auf vergleichbare europäische Systeme (10. November 2026)

Zugelassen sind jetzt Gruppen-Solvenzquoten aus Systemen mit derselben Definition (anrechenbare Eigenmittel / Solvenzkapitalanforderung, 100 % = Mindestanforderung):

| Rahmen | Land | Aufsicht |
|---|---|---|
| Solvency II | DE, FR, NL, FI, IT, NO, ES, BE, PL | BaFin, ACPR, DNB, FIN-FSA, IVASS, Finanstilsynet, DGSFP, NBB, KNF |
| Solvency UK | GB | PRA |

Währungen: EUR, GBP, NOK, PLN. Nicht vergleichbar und deshalb ausgeschlossen: Schweizer SST, japanische Solvenzmargen-Quote und ESR, US-RBC, chinesisches C-ROSS, kanadisches LICAT, Bermuda-BSCR, Hongkonger GWS.

**Reine Quote:** Viele Zwischenberichte nennen nur die Quote, nicht beide Beträge. Eine solche Beobachtung zählt jetzt als Hauptwert, wenn für die neueste Periode keine Beobachtung mit Beträgen vorliegt. Sie erfüllt dann nur `jurisdiction_and_regulatory_scope`. Eigenmittel und Anforderung bleiben als Nachweis offen. Mehrere gleichrangige Varianten derselben Periode bleiben mehrdeutig und werden abgelehnt.

**Neu im Register:** Sampo (30.09.2026, 175 %), NN Group (224 %), AXA (218 %, nur Quote), Talanx (246 %, nur Quote), Aviva (176 %, Shareholder View), Gjensidige (30.09.2026, 190 %), Unipol (259 %, nur Quote), Legal & General (201 %) und SCOR (30.09.2026, 221 %, geschätzt, nur Quote). Ohne Angabe gilt der Stichtag 30.06.2026. Dazu kommen die OTC-Stammaktien von Allianz, Munich Re und AXA mit den Gruppenwerten.

**Offen:**
- Hannover Rück, Admiral, Ageas, Mapfre: Die Websites sperren automatisierte Abrufe.
- ASR: Das Dokument verweist auf einen Download, der 404 liefert.
- Beazley, St. James's Place, Standard Life: Quote im Halbjahresbericht nicht gefunden.
- PZU: Die jüngste veröffentlichte Gruppenquote ist vom 31.03.2026 und damit älter als 210 Tage.
- Schweizer Versicherer: Die Freigabe ihrer Websites wurde abgelehnt; SST ist ohnehin ein eigenes System.

## Depositary Receipts (10. November 2026)

Die Solvenzquote gilt für den Versicherungskonzern. Ein Depositary Receipt mit derselben ISIN übernimmt den Eintrag einer im selben Lauf geprüften Stammaktie (`depositaryOf`) und behält dabei seine eigene Identität. Das entspricht dem Vorgehen bei Banken. Zeilen mit eigenem Registry-Eintrag, auch abgelehnte, werden nie über diesen Weg übernommen.

Ergebnis: OTC:ALIZY (Allianz), OTC:AXAHY (AXA) und OTC:MURGY (Munich Re) haben jetzt eine Solvenzquote. Damit sind 17 statt 14 Versicherer-Notierungen abgedeckt.

Weiter offen: ASR Nederland und PZU haben öffentliche Berichte ohne Bot-Schutz, aber ohne direkte PDF-Links. Sie kommen in die Quartalsaufgabe.

## Generali und Profilkorrektur (10. November 2026)

**Generali (MIL:G, OTC:ARZGY):** Neu im Register mit zwei Beobachtungen.
- Halbjahresbericht 2026 (PDF-Seiten 8 und 16, Fußnote 3; SHA-256 `047cf4e5…2556`): vorläufige Gruppenquote 216 % zum 30.06.2026, netto nach anteiliger Dividendenabgrenzung. Beträge werden nicht genannt. Diese Beobachtung ist der Hauptwert und erfüllt nur `jurisdiction_and_regulatory_scope`.
- SFCR 2025 (Seite 113; SHA-256 `8432c16f…ffd5e`): 52.551 Mio. € Gruppeneigenmittel, 24.004 Mio. € SCR, 218,9 %. Sie gilt, sobald der Halbjahreswert älter als 210 Tage ist.

Aufsicht IVASS und Register der Versicherungsgruppen Nr. 026: SFCR Seite 35. OTC:ARZGY übernimmt den Eintrag als Depositary Receipt (`depositaryOf`).

**Profilkorrektur:** Der Datenanbieter führt Generali und Tryg als „Insurance brokers/Services“, deshalb liefen beide bisher im Profil `corporate`. `reviewed-profile-overrides.json` setzt für genau diese ISINs das Profil `insurer`, mit Beleg-URL, Seite, SHA-256 und Prüfdatum. Die Korrektur gilt nur unter drei Bedingungen:
- Der Anbieter meldet weiterhin dieselbe Branche.
- Die Prüfung ist nicht abgelaufen (`review_expires` 10.05.2027).
- Das Ziel ist ein Finanzprofil.

Die Ausgabe trägt `profileSource`. Die App prüft die Angaben erneut und zeigt einen Hinweis; bei ungültiger Korrektur bleibt das Profil offen. Echte Makler (Aon, Marsh, Gallagher) bleiben `corporate`.

**Verzerrung:** Als `corporate` wurden Versicherer mit FCFF-Marge und Nettoschulden gemessen. Diese Kennzahlen sind für Versicherer nicht aussagekräftig und können in beide Richtungen täuschen. Die Korrektur kann ein Unternehmen nur in ein Finanzprofil mit eigenen, strengeren Nachweisen verschieben, nie hinaus.

**Wirkung im Probelauf:** Versicherer-Notierungen 54 → 57. Solvenzquote vorhanden 17 → 19, offen 37 → 38: Tryg ist jetzt korrekt als Versicherer gezählt, aber Dänemark ist noch kein zugelassenes Solvenzsystem. Unternehmen 1.053 → 1.050. Gesamtabdeckung 78,3 → 78,2 %, weil die Lücke bei Tryg jetzt sichtbar ist.

Offen: Tryg (Solvency II, Finanstilsynet DK, DKK) bräuchte die Freigabe von DK/DKK in `INSURER_REGIMES`, in App und Pipeline gleichzeitig.

## Versicherer außerhalb von Solvency II/UK (11. November 2026)

Die Solvenzquote ist nur für Gruppen unter Solvency II (EWR) oder Solvency UK vergleichbar. Bei ISIN-Ländern außerhalb davon (USA, Japan, Schweiz, Bermuda) und bei Prudential plc (Gruppenaufsicht Hongkong GWS, Beleg Halbjahresbericht 2026) wird sie bewusst nicht geführt. App und Messung nennen den Grund; in der Messung zählt sie als `by_design`. Weiter zu füllen bleiben 10 Gruppen: Hannover Rück, Mapfre, Ageas, ASR, PZU, Tryg (DK fehlt noch in `INSURER_REGIMES`), Admiral, Beazley, Standard Life und St. James's Place.

## Nachtrag 12. November 2026: acht Versicherer, Dänemark freigegeben

Neu ist Dänemark in `REGIMES`/`INSURER_REGIMES` (Solvency II, Finanstilsynet, DKK), in Pipeline und App gleichzeitig. `reviewedOn` steht auf 12.11.2026.

| Versicherer | Stichtag | Quote | Beträge | Quelle |
|---|---|---:|---|---|
| Hannover Re | 30.06.2026 | 254 % | nein | EQS-Pflichtmitteilung 12.08.2026; hannover-re.com sperrt automatisierte Abrufe (HTTP 403) |
| Mapfre | 30.06.2026 | 208,8 % | 11.555 / 5.533 Mio. € | Mitteilung 04.09.2026, PDF 1–2 |
| Admiral | 30.06.2026 | 173 % | nein | Halbjahresbericht (RNS über Investegate), aufsichtsrechtliche Schätzung; die Schlagzeilenquote 190 % mit nicht genehmigtem Kapitalaufschlag wird nicht verwendet |
| Tryg | 30.09.2026 | 203 % | 14.080 / 6.940 Mio. DKK | Q1–Q3-Bericht, PDF 14 |
| St. James's Place | 31.12.2025 | 182 % | 4.569,0 / 2.508,9 Mio. £ | SFCR 2025, PDF 5, nach vorhersehbarer Dividende |
| a.s.r. | 31.12.2025 | 218 % | 13.007 / 5.966 Mio. € | SFCR 2025 der Gruppe, PDF 6 |
| PZU | 31.12.2025 | 239 % | 34,5 / 14,4 Mrd. PLN | Ergebnispräsentation H1 2026, PDF 26; Jahreswert laut Fußnote aus dem testierten SFCR |
| Munich Re | unverändert | 300 % | | Identität erneuert: Der Anbieter führt den Namen jetzt als „Munich Re AG“. ISIN DE0008430026 und Notierung sind unverändert. |

Bewusst nicht verwendet:
- Unternehmenseigene Sichten: Ageas „Pillar II“ (195 %), Standard Life „Shareholder Capital Coverage Ratio“ (169 %, ohne unsupported With-Profits).
- Admirals Schlagzeilenquote.

Offen:
- Ageas und Standard Life: Der Gruppen-SFCR 2025 war nicht als Originaldatei auffindbar.
- PZU: Die Quote zum 30.06.2026 erscheint mit dem Q3-Bericht (um den 20.11.2026).

Probelauf: Solvenzquote bei 8 Versicherern neu gefüllt. Versicherer offen 10 → 2.
