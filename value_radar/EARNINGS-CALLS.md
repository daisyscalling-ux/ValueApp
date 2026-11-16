# Earnings Calls (earnings-daily)

`earnings_only.py` sammelt täglich den jüngsten Call je Firma des Universums von ROIC und schreibt `daten/cf_earnings.json` (`stand`, `anzahl`, `calls`). Die App liest die Datei direkt von `main`.

## Ausfall 20.10.–16.11.2026 (Befund 16.11.2026)

- Der Export lief jeden Tag (zuletzt 1.091 Calls, davon 819 ≤ 90 Tage, aus 1.319 von 1.344 Tickern, 25 min).
- Der Push wurde seit 20.10. täglich abgelehnt (einmal schon am 16.10.): Andere Läufe pushen während der 25 min nach `main`, und der Schritt rebaset nicht. `git push || echo "push uebersprungen"` meldete trotzdem Erfolg.
- Auf `main` blieb `stand: 2026-10-19 13:19 UTC`.
- **Behebung:** Commit nur bei Änderung, danach bis zu 4 Versuche `git pull --rebase` und `git push` mit steigender Pause (10/20/30/40 s), wie in `market-news` und `regulatory-daily`. Scheitern alle, endet der Lauf rot (`::error::`), statt still grün zu bleiben. Eine leere oder fehlende Datei bricht ebenfalls ab.
- Die App kennzeichnet eine Liste über 36 h Alter als veraltet (valueapp-cf, `src/lib/earnings-freshness.ts`).

**Offen:** `backtest-fundamental.yml` und `backtest-langfrist.yml` nutzen dasselbe Muster `git push || echo "push uebersprungen"` und können still scheitern. Der Aufwand dafür ist klein, als eigene PR.
