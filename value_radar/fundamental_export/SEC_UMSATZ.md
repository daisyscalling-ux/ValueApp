# Umsatz aus SEC companyfacts (11. November 2026)

## Befund

`export_fundamentals.sec_annual` las den Umsatz zuerst aus `RevenueFromContractWithCustomerExcludingAssessedTax` (ASC 606). Dieses Feld enthält keine Miet-, Leasing-, Zins- oder Prämienerträge. Bei Firmen mit solchen Erträgen war der Jahresumsatz deshalb deutlich zu niedrig, zum Beispiel (in Mio. USD):

| Titel | ASC-606-Feld | Gesamtfeld `Revenues` | Yahoo |
|---|---|---|---|
| United Rentals | 3.695 | 16.099 | 16.099 |
| Archer-Daniels-Midland | 24.956 | 80.269 | – |
| UDR (REIT) | 11 | 1.712 | – |
| General Motors | 167.971 | 185.019 | – |

**Folgen:**
- Margen und Umsatzkennzahlen dieser Titel waren verzerrt.
- Der Abgleich mit dem Yahoo-Abschluss (`enrich_matching_annual`, Umsatz auf 0,1 % gleich) scheiterte. Dadurch fehlten Schulden und Kasse, und bei Spezialfinanzierern blieben die Nettofinanzschulden offen (United Rentals, Ameriprise, Blackstone).

**Messung** (385 SEC-Abschlüsse auf main, gleicher Stichtag wie der Yahoo-Block):
- Umsatz auf 0,1 % gleich: 295
- Abweichung 0,1–1 %: 17
- Abweichung 1–5 %: 19
- Abweichung über 5 %: 29
- kein Vergleich möglich: 25

## Korrektur

Reihenfolge der Umsatzfelder: zuerst `Revenues` (Gesamtumsatz), dann `RevenueFromContractWithCustomerExcludingAssessedTax`, dann `SalesRevenueNet`. Das ASC-606-Feld zählt nur, wenn kein Gesamtumsatz gemeldet ist.

## Prüfung (companyfacts direkt abgerufen)

- **48 Titel mit über 1 % Abweichung:** 27 jetzt auf 0,1 % gleich, 14 unter 5 %, 6 weiter über 5 %, 1 ohne CIK. Keiner wird schlechter.
  - Weiter über 5 % liegen Banken und ein REIT ohne Gesamtfeld (Camden, M&T, Huntington, American Express), dazu Blackstone und Altria. Altria meldet nur das ASC-606-Feld; Yahoo zieht Verbrauchsteuern ab.
- **Stichprobe von 40 der 295 passenden Titel:** alle bleiben auf 0,1 % gleich.
- **Test:** `test_sec_total_revenue_before_contract_revenue`.

## Grenzen

- Banken: Umsatz ist ohnehin nicht die Kennzahl ihres Profils. Die Bankbewertung nutzt Kapital, Liquidität und Kreditqualität.
- Die Wirkung tritt mit dem nächsten `fundamentals-daily` ein, weil companyfacts dann neu abgerufen werden.
- Erst dieser Lauf zeigt, wie viele Abschlüsse zusätzlich Schulden und Kasse aus Yahoo übernehmen.
