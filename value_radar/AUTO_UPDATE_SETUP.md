# Tägliche Vorberechnung + E-Mail-Benachrichtigung einrichten

Ein nächtlicher Job (`precompute.py`) rechnet **Portfolio, Watchlist, Screener und
Radar** einmal täglich durch, vergleicht mit dem Vortag, schreibt die Änderungen
ins Google Sheet (die App zeigt sie auf der Startseite unter „Was hat sich
geändert") und schickt dir eine **E-Mail-Zusammenfassung**. Ausgeführt wird er
kostenlos von **GitHub Actions** (kein KI-Token nötig).

> Ehrlich vorab: Screener/Radar laufen im Job **bewusst begrenzt** (Top-Ideen aus
> einem gedeckelten Universum, flache Datentiefe), um das FMP-Gratislimit und die
> Laufzeit zu schonen. Portfolio + Watchlist werden voll (deep) gerechnet.

---

## Voraussetzung
Google Sheets muss als Speicher laufen (siehe `GOOGLE_SHEETS_SETUP.md`). Der
Nacht-Job schreibt in dasselbe Sheet, aus dem die App liest.

---

## Schritt 1 — GitHub-Secrets anlegen
Im Repo: **Settings → Secrets and variables → Actions → New repository secret**.
Lege diese Secrets an:

| Secret | Wert |
|---|---|
| `GSHEET_ID` | die Sheet-ID (wie in Streamlit) |
| `GCP_SERVICE_ACCOUNT` | der **komplette Inhalt** der Service-Account-JSON-Datei (einfach reinkopieren) |
| `FINNHUB_API_KEY` | dein Finnhub-Key |
| `FMP_API_KEY` | dein FMP-Key |
| `SMTP_HOST` | z. B. `smtp.gmail.com` |
| `SMTP_PORT` | `587` (STARTTLS) oder `465` (SSL) |
| `SMTP_USER` | deine Absender-E-Mail |
| `SMTP_PASS` | **App-Passwort** (bei Gmail nötig, s. u.) |
| `EMAIL_TO` | Empfänger (darf = `SMTP_USER` sein) |

**Gmail:** Normales Passwort funktioniert nicht. Aktiviere 2-Faktor-Anmeldung und
erstelle ein **App-Passwort** (Google-Konto → Sicherheit → App-Passwörter). Dieses
16-stellige Passwort kommt in `SMTP_PASS`.

`GCP_SERVICE_ACCOUNT` unterscheidet sich vom Streamlit-Format: In Streamlit war es
ein `[gcp_service_account]`-TOML-Block — hier ist es der **rohe JSON-Inhalt** der
Datei (mit den `{ ... }`-Klammern), am einfachsten aus der heruntergeladenen
Service-Account-JSON kopiert.

---

## Schritt 2 — Workflow hochladen
Die Datei `value_radar/.github/workflows/precompute.yml` liegt im Paket. Lade den
Ordner `.github/workflows/` mit ins Repo (Struktur beibehalten). GitHub erkennt den
Workflow dann automatisch unter dem Reiter **Actions**.

---

## Schritt 3 — Testen
Unter **Actions → value-radar-nightly → Run workflow** kannst du ihn **sofort
manuell** starten (nicht auf die Nacht warten). Danach:
- Im Log siehst du, was berechnet wurde.
- Prüfe dein Postfach (E-Mail).
- Öffne die App-Startseite → „Was hat sich geändert".

Beim **ersten** Lauf gibt es noch keinen Vortagsvergleich → es kommen kaum
„Änderungen", aber Portfolio/Watchlist/Screener/Radar werden im Sheet und in der
E-Mail-Übersicht aufgeführt. Ab dem zweiten Lauf werden echte Änderungen erkannt.

---

## Zeitplan ändern
In `precompute.yml` die `cron`-Zeile anpassen (UTC!). `15 5 * * *` = 05:15 UTC
≈ 07:15 deutscher Zeit. Für z. B. 06:00 dt. Zeit im Winter → `0 5 * * *`.

## Watchlist füllen
In der App: Einzelanalyse öffnen → Button **„☆ Zur Watchlist"**. Diese Titel
werden nachts mitgerechnet und überwacht.

## Kosten
GitHub Actions ist für öffentliche und (in großzügigem Rahmen) private Repos
kostenlos. Der Job braucht nur wenige Minuten pro Tag. Es fallen **keine**
Anthropic-/API-Kosten an — das ist reine Datenverarbeitung, keine KI.
