# Arbeitsstandard ValueApp

Diese Datei gilt für jede Arbeit an ValueApp (Pipeline, Repo `ValueApp`) und an der App (Repo `valueapp-cf`). Maßstab ist das Risikoscore-Modul: tief, nachvollziehbar, geprüft. Jedes neue Modul und jede Erweiterung wird in derselben Gründlichkeit gebaut. Im Zweifel lieber kleiner und belastbar als breit und ungeprüft.

## Grundsätze

1. **Offen statt falsch.** Fehlen Daten, sind sie mehrdeutig oder nicht prüfbar, bleibt die Kennzahl offen und nennt einen konkreten Grund („Geprüfte LCR fehlt“, „Währungskonflikt: ADR oder unklare Aktienbasis“). Keine stillen Schätzungen, keine Nullen als Platzhalter, kein Auffüllen aus ähnlichen Firmen.
2. **Ersatz nur gekennzeichnet.** Jeder Ersatz oder jede Ableitung trägt eine maschinenlesbare Markierung und einen Hinweistext, den die App zeigt. Beispiele: `historySource`, `depositaryOf`, `shortHistory`, die Methode `share_count_and_price_ratio_v1`. Ein Ersatz überschreibt nie echte eigene Daten.
3. **Identität vor Inhalt.** Daten werden an eine eindeutige Notierung gebunden: `listing_symbol`, `isin`, `currency`, `security_type`, `share_class`, abgelegt als `inputIdentity`. Gleiche ISIN ist ein Nachweis; ein ähnlicher Name nie. Weicht ein Feld ab, wird der Datensatz verworfen, nicht angepasst.
4. **Herkunft immer mitführen.** Zu jeder Quelle gehören Quell-URL, Prüfsumme (`sha256`), Berichtsperiode, Importzeitpunkt und bei kuratierten Zuordnungen ein Prüfdatum mit Ablauf (`reviewed_on`, `review_expires`). Abgelaufene Prüfungen gelten nicht mehr.
5. **Frische explizit.** Jede Quelle hat ein festes Höchstalter (z. B. Abruf ≤ 36 h, letzter Kurs ≤ 7 Tage, Bankquartal ≤ 270 Tage, EBA ≤ 730 Tage). Ältere Daten bleiben datiert sichtbar, zählen aber nicht.
6. **Doppelte Prüfung.** Die Pipeline erzeugt und prüft. Die App prüft beim Lesen erneut: Schema, Methode, Identität, Frische, Wertebereiche, Konsistenz (z. B. CET1 ≤ Tier 1 ≤ Gesamtkapital). Vorberechnete Flags werden nie ungeprüft übernommen.
7. **Methode vor Zahl.** Schwellen, Gewichte und Skalen stehen im Code als Konstanten und in der Doku mit Begründung. Keine Kalibrierung behaupten, die nicht gemessen wurde. Kein Score ist eine Verlustwahrscheinlichkeit oder ein Kauf-/Verkaufssignal. Kontextdaten tragen `scoreContribution: 0`, bis ihr Modell festgelegt und geprüft ist.
8. **Verzerrungen bedenken.** Vor jeder neuen Regel fragen: Lässt sie bestimmte Firmen systematisch zu gut aussehen? Beispiel: Der größte Rückgang bleibt bei verkürzter Historie offen, weil er sonst junge Börsengänge beschönigt. Diese Abwägung gehört in die Doku.
9. **Quellen fair nutzen.** Keine Umgehung von Bot-Schutz, Captchas oder TLS-Fehlern. Abgelehnte Hosts nicht erneut anfragen. Behördenquellen mit dem dafür vorgesehenen User-Agent-Secret (`SEC_USER_AGENT`). Keine Schlüssel oder persönlichen Daten im Code, in Logs oder in Anfragen an Dritte.

## Vorgehen bei jedem Modul

1. **Bestand messen.** Zuerst die Abdeckung je Kennzahl und Profil feststellen (`filled` / `missing` / `app_only` / `by_design`), mit Gründen und Anzahl. Ohne Messung keine Priorisierung.
2. **Ursachen trennen.** Eine fehlende Quelle ist etwas anderes als ein Zuordnungs- oder Identitätsproblem oder ein Fehler im eigenen Code. Fehler im eigenen Code zuerst beheben und offen benennen.
3. **Methode festlegen und dokumentieren.** Die Methodenentscheidung gehört dem Nutzer, wenn es mehrere vertretbare Wege gibt. Dann fragen, mit Empfehlung.
4. **Tests für jede Regel.** Positiv- und Negativfälle: falsche ISIN, falsche Wertpapierart, abgelaufene Prüfung, zu alte Periode, Werte außerhalb des Bereichs, fehlende Kennzeichnung. Neue Testdateien in den passenden Workflow aufnehmen (`daily-risk.yml`, `fundamentals-daily.yml`, `npm test`).
5. **Probelauf auf einer Kopie von main.** Die betroffene Kette auf einer Datenkopie laufen lassen, Ergebnis gegen main **ohne** die Änderung vergleichen und nur die eigene Wirkung berichten.
6. **Dokumentieren.** Deutsche Markdown-Datei des Moduls mit Datum, Begründung, Grenzen und Messergebnis ergänzen (z. B. `RISIKOSCORE.md`, `CONSTRUCT-COVERAGE.md`, `EU_BANKS.md`).
7. **Nach dem Lauf prüfen.** Nach Merge und Tageslauf die tatsächlichen Zahlen gegen den Probelauf abgleichen und Abweichungen erklären.

## Zusammenarbeit

- Berichte, Doku und Commit-Nachrichten auf Deutsch, knapp und mit Zahlen.
- Eine PR je Thema. Pull Requests werden nur vom Nutzer gemergt. Danach startet der Nutzer die Läufe (`daily-risk`, `fundamentals-daily`) und deployt die App.
- Methodenänderungen, die App und Pipeline betreffen, in beiden Repos gleichzeitig: Die Kopien unter `value_radar/risk_precompute/src/lib` und `worker` stammen aus `valueapp-cf` und müssen identisch bleiben.
- Kein Hinweis auf Vollständigkeit ohne Messung. Offene Punkte immer mit Anzahl und Aufwand nennen.

## Dieses Repo (Pipeline)

- Das Repo erlaubt nur „Rebase and merge“. Deshalb ein Commit je PR, sauber auf `origin/main` aufgesetzt. Hat ein PR Konflikte, wird er auf einem neuen Branch neu aufgesetzt und als neuer PR eingereicht, mit Verweis im alten. Kein Force-Push.
- Vor dem Commit nicht versionierte `__pycache__`-Ordner entfernen. Versionierte `.pyc` nicht löschen.
- Tests: `python -m unittest discover -s value_radar/risk_precompute -p 'test_*.py'` sowie `value_radar/regulatory_export`. Die TS-Tests werden mit `npx --yes esbuild@0.24.2 <test>.ts --bundle --platform=node --format=esm` gebaut und mit `node` ausgeführt; die Liste steht in `.github/workflows/daily-risk.yml`.
- Probelauf der Risikokette auf einer Kopie (`git archive origin/main value_radar | tar -x -C <kopie>`, im Kopie-Ordner ausführen):
  `run_integrity.py capture` → `regulatory_context.py` → `audit-universe` → `financial_supply_policy.py` → `coverage_delta.py` → `history-backfill.mjs` (Dateiname zwingend) → `financial_history.py` → `risk_workplan.py` → `risk_app_export.py` → `run_integrity.py seal` → `risk_evidence.py` → `risk_app_export.py` → `run_integrity.py seal` → `risk_construct_coverage.py`.
- Wirkung messen mit `value_radar/daten/cf_risk_construct_coverage.json` (Methode `offline-input-availability-v2`). Neue Kennzahlen dort und in `CONSTRUCT-COVERAGE.md` aufnehmen.
