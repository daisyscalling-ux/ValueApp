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
