# Regulatorische Datenversorgung: erste offizielle Quelle

FDIC BankFind financials wird taeglich um 06:11 UTC ueber regulatory-daily
abgerufen. Kein API-Key, keine neuen Secrets oder Drittanbieterpakete.
Der Abruf ermittelt den neuesten verfuegbaren Quartalsstichtag und paginiert
den kompletten Institutsbestand. Gleiche Periode, eindeutige CERT/RSSD-IDs,
vollstaendige Anzahl und numerische Werte werden geprueft. Fehler ersetzen
keinen erfolgreichen Bestand; status.json protokolliert den Fehlversuch.

Live-Test 19.10.2026: 4313 Institute, Stichtag 30.06.2026, 243 Finanznotierungen
im untersuchten Universum, 23 Namens-Zuordnungskandidaten. Keine bestaetigte
Konzernquote. Prozentwerte werden explizit in Dezimalquoten umgerechnet.

Offizielle Quellen:
- https://api.fdic.gov/banks/docs/
- https://api.fdic.gov/banks/docs/risview_properties.yaml
- https://api.fdic.gov/banks/financials

RBCT1CER: CET1, RBC1RWAJ: Tier-1, RBCRWAJ: Gesamtkapital.
NCLNLSR: nicht vertragsgemaess bediente Kredite/Leasingforderungen geteilt durch
Bruttokredite/Leasingforderungen laut FDIC-Definition. Keine harmonisierte
IFRS-NPL-Quote. Fehlende Werte bleiben null; Nullwerte werden nicht verworfen.

Die Daten gelten fuer das gemeldete FDIC-Institut, NICHT automatisch fuer
die boersennotierte Holding. NAMEHCR/RSSDHCR dokumentieren die im Datensatz
genannte Holding. Ein Namensvergleich erzeugt ausschliesslich einen Pruefauftrag,
keine verifizierte Wertpapieridentitaet. Quoten mehrerer Toechter werden weder
gemittelt noch addiert. LCR wird nicht aus Kredit-/Einlagenquoten geschaetzt.

Ausgaben in daten/regulatory/: fdic-latest.json, fdic-YYYY-MM-DD.json,
coverage.json und status.json. Abrufzeit ist kein Publikationsdatum. Aeltere
Quartalsdateien bleiben erhalten, Revisionen desselben Quartals ersetzen den
vorherigen Stand. Daher kein Point-in-Time-Backtestarchiv.

Weitere Quellen und Grenzen:
- EBA: https://www.eba.europa.eu/risk-and-data-analysis/pillar-3-data-hub
  Nachfolger der Transparency Exercise, seit Januar 2026 oeffentlich. Noch kein
  verifizierter automatischer Download-/LEI-Mappingpfad implementiert.
- Versicherer: individuelle SFCR-/Solvenzberichte des Konzerns; nationale
  Regime getrennt halten. https://www.eiopa.europa.eu/tools-and-data/insurance-statistics_en
  liefert aggregierte Statistiken, die keine individuellen Konzernquoten ersetzen.
- SEC: lokaler Probeabruf wurde mit HTTP 403 abgewiesen; kein Datenersatz aus
  Buchkapital. Bestehender SEC-Abruf in fundamentals-daily bleibt unveraendert.

Nach Merge regulatory-daily einmal ausfuehren. Keine Cloudflare-Aenderung und
kein Einfluss auf den Teilscore. Block 1 ist noch nicht vollstaendig: verifizierte
Holdingzuordnung, Konzern-/LCR-Daten und Versicherersolvabilitaet folgen.
