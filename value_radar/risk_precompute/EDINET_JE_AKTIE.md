# Kennzahlen je Aktie aus EDINET (Japan)

Stand 27.11.2026. Entscheidung des Nutzers: Ältere Geschäftsjahre für Gewinn je Aktie, Gewinn, KGV, KBV, Graham-Zahl und Dividende japanischer Titel aus den amtlichen Jahresberichten (有価証券報告書) laden.

## Ausgangslage (gemessen)

- 225 Titel im Universum mit japanischer ISIN. Yahoo liefert 4 Geschäftsjahre, meist ab 2022.
- Der Dokumentenindex von `edinet_supply.py` (`cf_edinet_cashflow.json`, 494 Tage, 460 Tage Fenster) enthält für **218 von 225** Titeln den neuesten Jahresbericht.
  - 6 Titel: ungeklärte Korrektur (`unavailable_correction`).
  - 1 Titel: kein Bericht.
- Stichtage: 174 × 31.03., 29 × 31.12., 7 × 28.02., übrige einzeln. Eingereicht: 165 im Juni 2026.

## Quelle

Jeder Jahresbericht enthält unter 主要な経営指標等の推移 fünf Geschäftsjahre. Gelesen werden je Titel zwei Berichte:

1. der neueste aus dem vorhandenen Index, also ohne zusätzlichen Indexabruf;
2. der von vor 4 Jahren (`ALT_JAHRE`), gesucht im Index ±10 Tage um den Einreichungstag minus 4 Jahre.

Zusammen ergibt das bis zu 9 Geschäftsjahre. Mehr geht nicht: EDINET stellt Jahresberichte nur innerhalb der gesetzlichen Einsichtsfrist von 5 Jahren bereit.

## Elemente

Geprüft gegen die FSA-Taxonomie 2025-11-01 (`1c_Taxonomy.zip`, sha256 `8d57f84802b20a8dc6a517ad6d4768270c294aa6991621d66cb5adb562df5de2`), mit Elementtyp und amtlicher japanischer Bezeichnung.

| Feld | J-GAAP | IFRS | US-GAAP |
|---|---|---|---|
| Gewinn je Aktie verwässert | `DilutedEarningsPerShare…` | `DilutedEarningsLossPerShareIFRS…` | `DilutedEarningsLossPerShareUSGAAP…` |
| Gewinn je Aktie unverwässert | `BasicEarningsLossPerShare…` | `BasicEarningsLossPerShareIFRS…` | `BasicEarningsLossPerShareUSGAAP…` |
| Gewinn (Eigentümer) | `ProfitLossAttributableToOwnersOfParent…` | `…IFRS…` | `NetIncomeLossAttributableToOwnersOfParentUSGAAP…` |
| Buchwert je Aktie | `NetAssetsPerShare…` | **`EquityToAssetRatioIFRS…`** | `EquityAttributableToOwnersOfParentPerShareUSGAAP…` |
| KGV | `PriceEarningsRatio…` | `…IFRS…` | `…USGAAP…` |
| Dividende je Aktie (Einzelabschluss) | `DividendPaidPerShare…` | gleich | gleich |
| Ausgegebene Aktien (Einzelabschluss) | `TotalNumberOfIssuedShares…` | gleich | gleich |

Alle Namen enden auf `SummaryOfBusinessResults`.

**Falle in der Taxonomie:** Der IFRS-Buchwert je Aktie heißt `EquityToAssetRatioIFRSSummaryOfBusinessResults`. Laut Typ (`perShareItemType`) und Bezeichnung (１株当たり親会社所有者帰属持分) ist es der Buchwert je Aktie, keine Quote. Die Quote heißt `RatioOfOwnersEquityToGrossAssetsIFRS…`.

## Regeln (`edinet_je_aktie.py`, Methode `edinet_summary_per_share_v1`)

- **Sicherheit wie `edinet_cashflow.py`:** kein DTD und keine Entities, nur UTF-8, eindeutige Kontexte und Einheiten. Die EDINET-Nummer muss passen, ein Konzernabschluss muss vorliegen, das ZIP muss genau eine öffentliche Instanz enthalten, Größengrenzen gelten.
- **Konzern- und Einzelwerte:** Konzernwerte stammen aus Kontexten ohne Dimension. Dividende und Aktienzahl kommen aus dem Einzelabschluss (`NonConsolidatedMember`), sonst aus dem Konzern. Andere Dimensionen werden übergangen.
- **Jahre und Einheiten:** Jahre werden über die Periodendaten zugeordnet (330–400 Tage), nicht über Kontextnamen. Je-Aktie-Werte zählen nur in der Einheit JPY/Aktie.
- **Leere und widersprüchliche Werte:** `nil` bleibt offen. Widersprüchliche Werte machen das Feld offen und werden gemeldet.
- **Rechnungslegung:** Der Standard wird je Geschäftsjahr nur aus Konzernwerten bestimmt (seit 27.11.2026, Korrektur nach dem ersten Lauf). Das jüngste Jahr braucht genau einen Standard, sonst wird der Bericht verworfen. Ältere Jahre mit zwei Standards im Konzern bleiben offen und werden als Konflikt gemeldet. Jedes Jahr trägt `standard`.
- **Älterer Bericht:** nur ein Original (Typ 120) mit derselben EDINET-Nummer und einem Stichtag 4 Jahre vor dem neuesten (±40 Tage). Gibt es eine Korrektur (Typ 130) dazu, bleibt der Bericht offen; unter Korrekturen wird nicht ausgewählt. Außerhalb der Einsichtsfrist bleibt er ebenfalls offen.
- **Identität:** Ändert sich die Identität der Notierung (ISIN, Währung, Wertpapierart), wird der gespeicherte Eintrag verworfen.
- **Abruf:** Neu gelesen wird nur, wenn sich der neueste Bericht oder die Parser-Version ändert. Anfragen kommen im Abstand von mindestens 2 Sekunden. Das Budget liegt bei 900 s je Lauf (`EDINET_JE_AKTIE_BUDGET_S`), Schlüssel ist `EDINET_API_KEY`.

**Gespeichert** werden in `daten/cf_edinet_je_aktie.json` nur die berichteten Werte. Dazu kommen docID, EDINET-Nummer, Stichtag, Einreichung, Prüfsumme der Datei, Standard und Konflikte.

## Noch nicht enthalten (folgt nach daisyscalling-ux/ValueApp#299)

Umrechnung auf die heutige Aktienbasis, Abgleich und Übernahme in `per_share` (`export_fundamentals.py`). Geplante Regel:

- **Split-Faktor:** Je Jahr gilt f = (KGV × Gewinn je Aktie laut Bericht) ÷ Yahoo-Schlusskurs am Stichtag. f muss bis auf 3 % einem Produkt der Yahoo-Splits nach dem Stichtag entsprechen, einschließlich 1. Sonst ist das Jahr offen.
- **Hintergrund:** Japanische Berichte passen ältere Jahre nach einem Split nicht immer an. Der vom Unternehmen berichtete Kurs, ablesbar aus KGV × Gewinn je Aktie, zeigt, auf welcher Aktienbasis die Zahlen stehen.
- **Ohne KGV:** Bei Verlust oder fehlendem KGV lässt sich f nicht bestimmen. Dann bleiben die Werte je Aktie offen; der Gewinn bleibt.
- **Abgleich mit Yahoo:** wie bei SEC, Gewinn je Aktie höchstens 2 % Abweichung in mindestens einem gemeinsamen Jahr.
- **Rangfolge:** Yahoo- und Archivjahre haben Vorrang.

## Grenzen und Verzerrungen

- Höchstens 9 Jahre, durch die Einsichtsfrist bedingt.
- Titel ohne Konzernabschluss bleiben offen.
- Wie bei SEC enthält die Reihe nur heute notierte Titel.
- **Probelauf mit echten Daten:** hier nicht möglich, weil `EDINET_API_KEY` nur im Workflow liegt. Messung nach dem ersten `daily-risk`-Lauf: Zahl der gelesenen Berichte, Standards, `alt_status` und Fehler je Grund.

## Tests

`test_edinet_je_aktie.py` mit 8 Fällen, im Workflow `daily-risk`:

- J-GAAP über fünf Jahre mit Einzelwerten, nil und Segment;
- IFRS-Buchwert unter dem irreführenden Namen;
- Widerspruch, falsche Einheit, fremder Emittent, kein Konzernabschluss;
- unsichere oder mehrdeutige Instanz, aktuelles Jahr fehlt;
- ZIP mit genau einer Instanz;
- Auswahl des älteren Berichts mit Korrektur, Rückzug, Einsichtsfrist und Mehrdeutigkeit;
- Lauf mit zwei Berichten, ohne erneuten Abruf und mit Identitätswechsel.

## Erster Lauf (daily-risk, 27.11.2026 13:57 UTC)

- 89 Titel versucht, Budget von 900 s erreicht; 209 Indextage geladen.
- **42 Titel mit Werten**, alle J-GAAP: im Median 9 Geschäftsjahre (mindestens 5, höchstens 9), keine Widersprüche.
  - Neuestes Jahr gefüllt: Gewinn je Aktie unverwässert 42, Gewinn 42, Buchwert je Aktie 42, KGV 41, Dividende 42.
  - Verwässerter Gewinn je Aktie nur bei 16; bei den übrigen meldet der Bericht keine Verwässerung (nil).
  - Älterer Bericht: 37 gelesen, 3 mit Korrektur offen, 2 nicht gefunden.
- **45 Titel verworfen** (`ambiguous_or_unsupported_taxonomy`). Ursache war ein Fehler im eigenen Code: Der Standard wurde aus allen Werten bestimmt, auch aus dem Einzelabschluss. IFRS- und US-GAAP-Konzerne berichten die Muttergesellschaft aber nach J-GAAP. Korrigiert: Standard je Jahr nur aus Konzernwerten. Diese Titel werden im nächsten Lauf neu gelesen; an den J-GAAP-Ergebnissen ändert sich nichts.
- 1 Titel mit ungeklärter Korrektur, 1 ohne Jahresbericht im Index.
