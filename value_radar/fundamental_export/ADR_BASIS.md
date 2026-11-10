# ADR-Heimatnotierungen außerhalb des Universums (10. November 2026)

`adr_basis.py` braucht Kurs und Aktienzahl der Heimatnotierung. Bei 55 ADRs steht sie nicht im Universum, zum Beispiel ASML, Sanofi, GSK, Unilever, Santander, BBVA, HDFC und ICICI. Neuer Schritt `adr_home_quotes.py`, ausgeführt in `fundamentals-daily` vor dem ADR-Schritt:

1. Für ADRs mit Währungskonflikt, ohne Heimatnotierung im Universum und mit Nicht-US-ISIN sucht die ROIC-Ticker-Suche **genau eine Hauptnotierung mit exakt derselben ISIN** (keine OTC-Linie, Aktie, nicht delistet). Die Auflösung gilt 30 Tage.
2. Übersetzung in ein Yahoo-Symbol aus Börse und Land, zum Beispiel `EURONEXT:ASML` + NL → `ASML.AS` oder `HKEX:939` → `0939.HK`. Unklare Schreibweisen (`BMV:AMX/B`, Euronext ohne Land) bleiben offen.
3. Von Yahoo werden nur Kurs, Aktienzahl, Währung und Name übernommen. Der Name muss zum Emittenten passen; kurze Namen wie GSK müssen ohne Rechtsform exakt übereinstimmen.
4. `adr_basis.py` nutzt diese Heimatnotierung nur mit höchstens 7 Tage altem Kurs. Es gilt dieselbe doppelte Prüfung (Aktienzahl 2 %, Kurs 10 %, nur Standardverhältnisse). Die Belege tragen `homeOutsideUniverse`, `homeYahooSymbol` und `homeSource`.
5. Verschwindet die Heimatnotierung, wird ein abgeleitetes Verhältnis zurückgenommen und nicht weitergeführt. Das gilt jetzt auch ohne externe Heimatnotierung.

Ausgabe: `daten/fundamentals/adr_homes.json`.

**Live-Probe (Yahoo-Teil, Heimatnotierung von Hand gesetzt):** Alle 15 Verhältnisse entsprechen den bekannten Depositary-Verhältnissen: Santander, BBVA, Unilever, Itaú, CBA je 1; GSK 2; Sanofi 0,5; HDFC 3; ICICI 2; DBS 4; BAE 4; Vodafone 10; Schneider 0,2; Merck KGaA 0,2; NAB 0,5.

**Grenzen:**
- Für TWD veröffentlicht die EZB keinen Kurs, TSMC, ASE und Hon Hai bleiben deshalb offen.
- ADRs mit eigener US-ISIN im Universum bleiben offen: Alibaba, PDD, NetEase, Roche, Intesa.
