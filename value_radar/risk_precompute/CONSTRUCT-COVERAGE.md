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

Ausgewertet wird das durchschnittlich belegte Gewicht (von 100) je Profil und Block. Dazu kommt eine Rangliste der größten Lücken nach Gewicht × fehlenden Notierungen. Das ist keine Neuberechnung des Scores: Peer-Stress nutzt den vorberechneten Sektorvergleich als Näherung, und der freie Cashflow der Unternehmen ist operativer Cashflow minus Investitionen aus dem Jahresabschluss.

## Erste Messung (Daten vom 10.11.2026, 1.332 Notierungen)

Durchschnittlich belegtes Gewicht: **69,6** befüllt, 13,6 fehlend, 13,9 nur in der App prüfbar, 2,8 bewusst offen.

| Profil | Notierungen | befüllt | fehlend | nur App | bewusst offen |
|---|---:|---:|---:|---:|---:|
| Unternehmen | 1.051 | 74,5 | 10,5 | 15,0 | 0 |
| Banken (inkl. GS, Schwab) | 144 | 46,9 | 33,1 | 10,0 | 10,0 |
| Versicherer | 54 | 50,2 | 19,8 | 10,0 | 20,0 |
| Spezialfinanzierer | 83 | 59,8 | 15,3 | 10,0 | 14,9 |

Größte Lücken (Gewicht × fehlende Notierungen):

| Profil | Kennzahl | fehlend | Hauptgründe |
|---|---|---:|---|
| Unternehmen | Erwartungslücke Reverse DCF (10) | 411 | 218 Währungskonflikt, 98 Cashflow fehlt, 95 freier Cashflow ≤ 0 |
| Unternehmen | Peer-Stress (5) | 736 | Vergleichsgruppe zu klein (meist weniger als fünf Firmen in derselben Währung) |
| Unternehmen | FCFF-Marge (10) | 107 | Cashflow, Investitionen oder Umsatz fehlen |
| Banken | LCR (7,5) | 118 | keine geprüfte LCR (EU-Daten enthalten keine LCR) |
| Banken | CET1-Puffer (10) | 84 | keine geprüfte Anforderung |
| Unternehmen | Expected Shortfall (15) | 55 | 33 ohne Kurshistorie, 22 fehlerhaft |
| Banken | Erwartungslücke Eigenkapitalrendite (10) | 76 | 63 Währungskonflikt |

## Folgerungen

1. **Währungskonflikt:** Bei 218 Unternehmen und 63 Banken unterscheiden sich Berichts- und Handelswährung. Das sind meist ADRs und OTC-Notierungen. Eine geprüfte Umrechnung, wie sie die App für einzelne Notierungen schon kann, würde den Bewertungsblock breit füllen.
2. **Peer-Stress:** Der Sektorvergleich verlangt fünf Firmen derselben Währung. Eine währungsbereinigte Vergleichsgruppe liegt für viele bereits vor (`currencyAdjustedContext`), wird aber nicht als Score genutzt.
3. **Bank-LCR:** Für EU-Banken fehlt eine Quelle. Die Säule-3-Berichte enthalten die LCR, ein KM1-Import wie bei den internationalen Banken wäre möglich.
4. **Kurshistorie:** 55 Unternehmen und 41 Banken ohne verwertbare Historie, meist OTC-Notierungen.
