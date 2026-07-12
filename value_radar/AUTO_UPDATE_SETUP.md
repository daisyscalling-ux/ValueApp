# Automatische Neuberechnung – 2× täglich

Damit werden **ohne dein Zutun** neu berechnet:

| Bereich | Was genau |
|---|---|
| **Portfolio** (alle gespeicherten) | Composite, Fair Value, Upside, **Quantum-Score**, Einstiegskurs, Kurs – mit **tiefen** Daten |
| **Watchlist** | dieselben Kennzahlen + Kaufzonen-Prüfung (Startseiten-Alarm) |
| **Screener** | Qualitäts-Scan, neue Treffer werden als „Änderung" gemeldet |
| **Radar** | Radar-Score, Ebenen, frische Katalysatoren |
| **Hedgefonds** | alle 4 Strategie-Depots: TP/SL, **Gewinn-Stop**, Slots neu befüllen |

Ergebnisse landen im Google Sheet → die App zeigt sie sofort beim Öffnen (ohne Ladezeit),
u. a. auf der Startseite unter „Was hat sich geändert" und „Watchlist-Alarm".

---

## Schritt 1 – Google Sheet als Speicher einrichten

Ohne Speicher gehen die Ergebnisse nach jedem Lauf verloren. Falls schon erledigt: weiter zu Schritt 2.
Anleitung dazu: **GOOGLE_SHEETS_SETUP.md**. Du brauchst am Ende zwei Dinge:

- die **Sheet-ID** (steht in der URL des Sheets zwischen `/d/` und `/edit`)
- die **Service-Account-JSON-Datei** (der komplette Inhalt, inkl. `{` und `}`)

Wichtig: Das Sheet muss für die E-Mail-Adresse des Service-Accounts als **Bearbeiter** freigegeben sein.

---

## Schritt 2 – Secrets in GitHub hinterlegen

Im Repo: **Settings → Secrets and variables → Actions → New repository secret**.
Für jedes Secret: Name exakt so schreiben, Wert einfügen, speichern.

**Pflicht:**

| Name | Wert |
|---|---|
| `GSHEET_ID` | die Sheet-ID aus Schritt 1 |
| `GCP_SERVICE_ACCOUNT` | **kompletter Inhalt** der JSON-Datei (roher Text, nicht Base64, nicht der Dateipfad) |
| `FINNHUB_API_KEY` | dein Finnhub-Key |
| `FMP_API_KEY` | dein FMP-Key |

**Optional:**

| Name | Wert |
|---|---|
| `TIINGO_API_KEY` | sauberere Kurse/Währung |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `EMAIL_TO` | für die Zusammenfassungs-Mail (Gmail: **App-Passwort**, nicht dein normales Passwort; Host `smtp.gmail.com`, Port `587`) |
| `ANTHROPIC_API_KEY` / `AI_BRIEFING_MODEL` | nur falls du das KI-Briefing aktivieren willst (kostet pro Aufruf) |

Fehlt ein optionaler Wert, läuft der Job trotzdem – der jeweilige Teil wird einfach übersprungen.

---

## Schritt 3 – Workflow-Datei ins Repo

Die Datei liegt im ZIP unter:

```
.github/workflows/precompute.yml
```

Sie gehört **ins Repo-Wurzelverzeichnis** (also `.github/workflows/precompute.yml`),
**nicht** in den Ordner `value_radar/`. Hochladen und committen.

---

## Schritt 4 – Actions aktivieren und einmal manuell testen

1. Reiter **Actions** öffnen. Falls GitHub fragt: Workflows **aktivieren**.
2. Links **„value-radar-update"** anklicken.
3. Rechts **„Run workflow"** → grünen Knopf drücken (das ist der manuelle Start).
4. Den Lauf anklicken und das Log ansehen. Achte auf diese Zeilen:
   - `Speicher: gsheet` (steht dort `lokal (JSON)`, greift Schritt 2 nicht!)
   - `Portfolio: N Ticker` / `Watchlist: N Ticker`
   - `[hedgefund] Kandidaten: X Long, Y Short, Z KO-Put`
   - `[hedgefund] marktneutral: Wert … EUR, … Positionen`
   - `=== precompute fertig ===`
5. Danach die App öffnen → Startseite. Beim **ersten** Lauf gibt es noch keine
   „Änderungen" (es fehlt der Vergleichsstand von vorher) – das ist normal.
   Ab dem **zweiten** Lauf erscheinen sie.

Läuft der manuelle Test durch, läuft ab da auch der Zeitplan automatisch.

---

## Zeitplan (2× täglich)

In der Workflow-Datei steht:

```yaml
- cron: "15 5,14 * * *"
```

**GitHub rechnet in UTC.** Umgerechnet auf deutsche Zeit:

| UTC | Sommerzeit (MESZ) | Winterzeit (MEZ) | Warum dieser Zeitpunkt |
|---|---|---|---|
| 05:15 | **07:15** | 06:15 | vor der Europa-Eröffnung |
| 14:15 | **16:15** | 15:15 | kurz nach US-Eröffnung |

Bewusst 2×: Das schont die Gratis-API-Limits (häufige `429`-Fehler würden Datenpunkte
kosten und damit Scores und Fair Values verfälschen) und bleibt klar innerhalb der
GitHub-Freiminuten.

**Zeiten ändern:** Die Zahlen vor dem Komma sind die UTC-Stunden.
Beispiel 3× täglich: `"15 5,11,17 * * *"` · nur morgens: `"15 5 * * *"`.
Mehr als 3× würde ich mit den Gratis-Keys nicht empfehlen (siehe Hinweise unten).

---

## Wenn etwas nicht klappt

| Symptom im Log | Ursache | Lösung |
|---|---|---|
| `Speicher: lokal (JSON)` statt `gsheet` | Sheet-Secrets fehlen/falsch | `GSHEET_ID` und `GCP_SERVICE_ACCOUNT` prüfen (JSON **komplett**, mit Klammern) |
| `Portfolio: 0 Ticker` | Der Job sieht dein Portfolio nicht | Portfolio muss im **Google Sheet** liegen (nicht nur lokal gespeichert) |
| `429` / `rate limit` | Gratis-API-Limits | Läufe reduzieren (z. B. 2×/Tag) oder bezahlten FMP-Key nutzen |
| Keine E-Mail | SMTP-Secrets fehlen | Gmail: **App-Passwort** erzeugen, `SMTP_PORT=587` |
| Workflow startet nicht automatisch | Actions deaktiviert / Repo inaktiv | Reiter **Actions** → aktivieren. GitHub pausiert Cron-Jobs in Repos ohne Aktivität nach ~60 Tagen – ein manueller Lauf reaktiviert sie |

---

## Ehrliche Hinweise

- **Warum 2× und nicht öfter:** Die Gratis-Tarife (Finnhub/FMP) haben Anfrage-Limits.
  Häufigere Läufe mit tiefen Daten laufen in `429`-Fehler; dann fehlen Datenpunkte, und
  das drückt Composite **und** Fair Value (genau der Effekt, der dir die Scores schon
  einmal verhagelt hat). Mit einem bezahlten FMP-Flatrate-Key (~19 $/Monat) wären 4×+
  problemlos möglich.
- **GitHub-Minuten:** Private Repos haben 2.000 Gratis-Minuten/Monat. Ein Lauf dauert grob
  5–15 Minuten → 2×/Tag ≈ 300–900 Minuten/Monat. Das ist komfortabel im Rahmen.
  Verbrauch: **Settings → Billing**. Öffentliche Repos sind unbegrenzt.
- **Hedgefonds-Regeln greifen nur zu den Prüfzeiten.** Zwischen zwei Läufen kann ein
  Take-Profit, Stop-Loss oder Gewinn-Stop durchlaufen werden, ohne dass „verkauft" wird.
  Das ist bei einem Papier-Depot zum Lernen unkritisch, aber du solltest es wissen.
- **Der erste Lauf** legt nur den Vergleichsstand an. Änderungen und Watchlist-Alarme
  erscheinen erst ab dem zweiten Lauf.
