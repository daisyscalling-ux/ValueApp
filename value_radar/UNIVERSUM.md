# Export-Universum (Cloudflare)

Stand: 10. November 2026.

## Definition

Das Universum für App und Risikoscore besteht aus den Mitgliedern von S&P 500, NASDAQ-100, STOXX Europe 600, Nikkei 225 und DAX, entdoppelt (`roic.export_universum`). Andere Titel gehören nicht dazu. So hat es der Nutzer am 10.11.2026 entschieden.

| Index | Quelle | Rückfall |
|---|---|---|
| S&P 500 | Wikipedia, Tabelle `constituents`, beschreibender User-Agent `value-radar/1.0 (index membership list)` | `sp500_liste.txt` (Stand im Kopf, höchstens 120 Tage alt) |
| NASDAQ-100 | slickcharts.com, sonst Wikipedia | keiner |
| STOXX Europe 600 | `stoxx600_liste.txt` (iShares-Bestand) | – |
| Nikkei 225 | `nikkei225_liste.txt` (offizielle Komponentenliste) | – |
| DAX | Konstante `DAX40` in `roic.py` | – |

Jede Exportzeile trägt `index_membership`, die Datei trägt `index_scope`: Methode `index-members-v1`, Quellen, Anzahl je Index, Vollständigkeit und Mitglieder.

## Befund und Korrektur (10.11.2026)

1. **S&P 500 unvollständig.** Wikipedia lehnt Abrufe ohne erkennbaren User-Agent ab (HTTP 403). `regime.sp500_tickers()` fiel deshalb still auf den Yahoo-Screener zurück, der die 500 größten US-gehandelten Titel liefert. Folge:
   - 274 von 503 S&P-500-Mitgliedern fehlten.
   - Stattdessen standen 215 OTC-Linien und rund 60 ausländische ADRs an NYSE/NASDAQ im Universum, z. B. chinesische Banken, kanadische Banken, NVS und SHEL.
   - Diese Zeilen verursachten überproportional viele offene Kennzahlen: Bei den OTC-Linien waren 9,8 % des Gewichts offen, bei den US-Hauptnotierungen 2,8 %.

   **Korrektur:** `index_membership.sp500_members` verwendet Wikipedia mit beschreibendem User-Agent. Gibt es dort keine plausible Tabelle (480–520 Symbole), gilt die datierte feste Liste. Ein Screener wird nie verwendet.
2. **Indexwerte durch gleichnamige US-Ticker verdrängt.** `precompute.collapse_listings` fasste nach Basissymbol über alle Börsen zusammen. Ein US-Ticker ohne Suffix verdrängte so andere Firmen: DTE.DE durch DTE, MRK.DE durch MRK, AIR.PA durch AIR, SAN.MC durch SAN, PRU.L durch PRU. Mit dem vollständigen S&P 500 wären es 24 europäische Indexwerte gewesen.

   **Korrektur:** Der Export fasst nur noch Notierungen desselben Landes zusammen (`collapse_same_market`, z. B. AMZ.DE/AMZ.F, BHP.L/BHPL.XC). Notierungen derselben Firma in zwei Indizes (ASML und ASML.AS, FER und FER.MC) bleiben beide erhalten; ihre Identität bindet wie bisher die ISIN.
3. **Veröffentlichungsschutz.** `export_continuity.guard` verweigert das Entfernen von mehr als 10 % der Zeilen. Bei vollständiger Indexbeschreibung (`scope_complete`: Methode stimmt, Mindestgrößen S&P 500 ≥ 480, NDX ≥ 95, STOXX ≥ 590, Nikkei ≥ 220, DAX ≥ 40) zählen nur noch entfernte Indexmitglieder. Zeilen ohne Indexzugehörigkeit dürfen gezielt wegfallen. Fehlt eine Liste, ist die Beschreibung unvollständig und die alte Regel greift.

## Messung (Probe ohne ROIC, Aufbereitung wie im Export)

| | bisher | neu |
|---|---|---|
| Titel | 1.330 | 1.345 |
| S&P-500-Mitglieder im Universum | 229 | 503 |
| hinzu | – | 310 (S&P 500: 287, STOXX 600: 22, DAX: 3) |
| entfernt | – | 295, davon kein Indexmitglied (215 OTC, 59 NYSE, 3 NASDAQ, 18 ohne Notierung) |

Neu hinzu kommen in Europa unter anderem SAP.DE, TTE.PA, AIR.PA, SAN.MC, BBVA.MC, MRK.DE, ASML.AS, SU.PA und RACE.MI.

## Folgen und Grenzen

- Die 310 neuen Titel brauchen Fundamentaldaten und Kurshistorien. Der Export und die Risikokette ziehen fehlende Titel vor, die Abdeckung erholt sich also über die nächsten Tagesläufe. In dieser Zeit sinkt die Risikoabdeckung vorübergehend; das ist erwartet und kein Rückschritt der Methode.
- Für die entfernten Zeilen gemachte Sonderprüfungen werden nicht mehr gebraucht: H-Aktien-ISIN in `reviewed_listing_reference.json`, Heimatkurse für ADRs, Versicherer- und Bank-DRs. Sie bleiben vorerst als Daten liegen.
- Die Indexlisten sind nicht zeitpunktgenau: Für historische Auswertungen gilt das heutige Universum nicht rückwirkend (Survivorship).
- Offen: Der NASDAQ-100-Abruf (`roic._html_tabellen`) gibt sich als Chrome-Browser aus. Das widerspricht dem Arbeitsstandard und sollte auf einen beschreibenden User-Agent umgestellt werden. Die STOXX-Liste enthält einzelne veraltete Kürzel (z. B. DPW.DE statt DHL.DE, BT.A); sie wird bei der nächsten Listenpflege geprüft.

## Kurshistorien der Indexwerte (11.11.2026)

19 Notierungen hatten keine verwertbare Kurshistorie. Nach Ursache getrennt:

| Ursache | Titel | Behandlung |
|---|---|---|
| echte Neulinge (unter einem Handelsjahr oder noch ohne Historie) | Sydbank-Fusion, CSG, Magnum Ice Cream, Helvetia Baloise, Honeywell Aerospace, SpaceX, FedEx Freight, Vivmark, Vylor | bleiben offen; ab 253 Handelstagen greift die verkürzte Historie |
| übernommen und von der Börse genommen | Beazley (Zurich, 02.10.2026), Schroders (Nuveen, 02.10.2026) | aus `stoxx600_liste.txt` entfernt, mit Quelle im Kommentar |
| Übernahme ohne belegtes Wirksamkeitsdatum | Covestro (Squeeze-out durch XRG beschlossen) | bleibt, bis das Ende der Notierung belegt ist |
| ROIC-Reihe fehlerhaft, Yahoo-Reihe vollständig (nur Diagnose) | Rosebank, ARCHION, Zegona | Ursache wird geklärt; der Nutzer hat am 11.11.2026 gegen Yahoo als Ersatz entschieden |
| echte Handelsaussetzung | Nebius (2022–2024) | bleibt offen |
| keine eindeutige Notierung bei ROIC | Cboe Global Markets, Nordea, Octave | Diagnose im Export-Log |

Diagnose ab dem nächsten Lauf:
- `retryState` in `cf_risk.json` speichert den Klartextgrund. Gespeichert wird nur bei bekannten, unbedenklichen Meldungen, ohne URLs.
- Findet `roic.py` keine eindeutige Notierung, schreibt es die angebotenen Kandidaten ins Export-Log: Symbol, Art, Hauptnotierung, ISIN-Land. Daraus wird nichts übernommen.
