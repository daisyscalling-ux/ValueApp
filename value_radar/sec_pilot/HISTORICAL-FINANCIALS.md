# Historische Finanzberichte ausgeschiedener Unternehmen

Dieser Forschungsabruf ergaenzt zunaechst HES, MRO, PXD und ANSS. Die Identitaet
ist ueber eine konkrete SEC-10-K-Quelle hinterlegt und wird mit CIK,
Accession, Berichtsdatum und Dokumentnamen in den SEC-Metadaten abgeglichen.
Ein heute fehlendes Boersensymbol verhindert den Abruf nicht.

## Start und Ergebnis

Nach Zusammenfuehrung: Actions → historical-sec-financials → Run workflow → main.
Das bereits vorhandene Secret SEC_USER_AGENT wird verwendet. Kein neuer API-Key,
kein Cloudflare-Deployment und kein neuer grosser Precompute-Lauf erforderlich.
Der Abruf nutzt SEC, nicht das ROIC-Aufrufbudget.

Das Artifact historical-sec-<Laufnummer> enthaelt Rohdaten, SHA-256-Pruefsummen,
Abrufzeitpunkte, Quell-URLs und manifest.json. Artefakte werden 90 Tage aufbewahrt;
fuer ein dauerhaftes Forschungsarchiv herunterladen. Teilergebnisse werden nach
jeder Firma gespeichert und auch bei Fehlern hochgeladen; ein unvollstaendiger
Abruf beendet den Job mit Fehlerstatus.

## Aussagegrenzen

25 quartalsweise Stichtage vom 12.10.2020 bis 12.10.2026; nur vorher verfuegbare
Jahresdaten in USD. Am Stichtag selbst eingereichte Berichte bleiben ausgeschlossen.
Die letzte Auswahl wird nach 550 Tagen als veraltet markiert. Fehlende Capex oder
Schulden werden nicht mit null ersetzt. Standard-XBRL-Tags koennen unvollstaendig
sein; Aenderungsberichte ohne CFO werden noch nicht rekonstruiert.

`complete` bedeutet nur, dass alle vier Firmenarchive erfasst und deren Identitaet
bestaetigt wurden, nicht dass alle Kennzahlen vollstaendig sind. Die Stichprobe ist
nicht repraesentativ. Indexmitgliedschaften, Renditefenster, Abfindungen und diese
Finanzberichte muessen noch verbunden und geprueft werden. Keine neuen Scoregewichte
oder Ausfallwahrscheinlichkeiten werden dadurch in der App aktiviert.
