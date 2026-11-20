# Fair-Value-Verlauf (täglich)

Stand 20.11.2026, Methode `fv_daily_log_v1` (`value_radar/fv_verlauf/fv_verlauf.py`, Workflow `fv-verlauf.yml`).

## Anlass
Bisher entstand der Verlauf in der Einzelanalyse nur, wenn ein Titel geöffnet wurde (KV-Speicher der App, Punkt nur bei spürbarer Änderung). Der Nutzer wünscht ein tägliches Protokoll für alle Titel.

## Regeln

| Regel | Umsetzung |
|---|---|
| Takt | Nach jedem `precompute-3tage` (`workflow_run`) und täglich um 09:47 UTC als Rückfall. |
| Ein Punkt je Tag | Tag des Universumsstands. Ein späterer Lauf am selben Tag ersetzt nichts. |
| Inhalt | `d`, `fv`, `kurs`, `m` (Methodenstand); dazu `verl` (FV verlässlich) und `modell`, wenn vorhanden. |
| Offener Fair Value | `fv: null` mit `grund` („Daten prüfen“ oder „Fair Value offen“), nie 0. |
| Identität | Jede Datei trägt `inputIdentity` (Notierung, ISIN, Währung). Weicht ein späterer Stand ab, wird der Punkt verworfen und gezählt. |
| Methodenstand | sha256 (12 Zeichen) von `risk_precompute/app-copies.json`, also des Rechenwegs, den der Scanner ausführt; vor dem 13.11. „python“. Die App markiert Wechsel. |
| Herkunft | `_quellen.json` je Tag: Universumsdatei, Commit (rekonstruiert), sha256, Methodenstand. |

Die App prüft beim Lesen erneut (`src/lib/fv-history.ts`):
- Schema und Methode;
- Notierung, ISIN, Währung;
- streng steigende Daten, keine in der Zukunft;
- FV > 0 oder offen, Kurs > 0.

Ein Verlauf, dessen letzter Punkt älter als 7 Tage ist, bleibt sichtbar und wird markiert.

## Rekonstruktion (einmalig, 20.11.2026)
- **Quelle:** alle 67 Commits von `cf_universum.json` seit dem 28.09.2026.
- **Reihenfolge:** neuester zuerst. So gilt die Identität des neuesten Stands, und je Kalendertag zählt der letzte Stand des Tages.
- **Ergebnis:** 46.936 Punkte aus 37 Ständen, 1.675 Titel (inklusive früherer Universumstitel). 181 ältere Punkte wurden wegen anderer ISIN oder Währung verworfen.
- **Grenze:** Stände vor Mitte Oktober haben kein `listing_symbol` und fehlen deshalb.

## Grenzen
- **Methodenwechsel:** Bis zum 20.11. hat sich der Rechenweg fast täglich geändert (bei SAP 6 Wechsel in 10 Tagen). Ein Sprung an einer gelben Linie kann aus der Methode kommen statt aus dem Unternehmen. Der Verlauf misst den Fair Value des Tools, nicht eine Eigenschaft der Firma.
- **Kurszeitpunkt:** Der Kurs im Verlauf ist der des Universums. Ob es ein Schluss- oder ein Handelskurs ist, steht dort (`price_kind`) und ist hier nicht zusätzlich gespeichert.
- **Größe:** etwa 2 KB je Titel und Monat, rund 1.341 Dateien, eine Datei je Notierung.
