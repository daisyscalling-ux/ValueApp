# Aeltere ANSYS-Finanzberichte: Datenfortschritt

Stand 18.10.2026. Geprueft wurden die SEC-Jahresberichte 2022 und 2023
(Einreichungen vom 22.02.2023 und 21.02.2024). Quellen stehen unmittelbar in
capex_evidence.py und balance_evidence.py.

Die jeweiligen Kapitalflussrechnungen bestaetigen die alternativen Capex-Tags.
Die Schuldennoten bestaetigen, dass der gesamte Kreditbuchwert langfristig ist
und keine Revolver-Ziehungen ausstehen. Berichtsspezifische Werte werden nicht
auf andere Einreichungen oder fruehere Zeitpunkte uebertragen.

Erneute Auswertung derselben archivierten SEC-Rohdaten und derselben zuvor
geprueften ANSYS-Kursreihe mit review_historical_financials.py:

| Verfuegbarkeit innerhalb historischer Mitgliedschaft | Vorher | Jetzt |
|---|---:|---:|
| Stichtage mit FCF/Aktiva | 2 | 10 |
| Stichtage mit Nettoschulden/Aktiva | 2 | 10 |
| Alle drei Finanzmerkmale plus 21-Tage-Kurspfad | 1 | 9 |
| Alle drei Finanzmerkmale plus 63-Tage-Kurspfad | 0 | 8 |
| Alle drei Finanzmerkmale plus 126-Tage-Kurspfad | 0 | 7 |

Das sind Datenabdeckungen, keine unabhaengigen Beobachtungen und keine
Vorhersageguete. ANSYS allein erlaubt keine robuste Risikokalibrierung.
Historische Mitgliedschaften und Kursanpassungen bleiben provisorisch.
Fehlende Uebernahmeabwicklungen werden nicht durch Nullrenditen ersetzt.

Die Rohdaten wurden lokal erneut ausgewertet. Kein weiterer SEC-Abruf oder
Cloudflare-Upload erforderlich. Produktionsscores bleiben unveraendert.
