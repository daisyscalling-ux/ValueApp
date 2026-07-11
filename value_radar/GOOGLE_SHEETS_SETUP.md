# Portfolios dauerhaft speichern mit Google Sheets

Damit deine gespeicherten Portfolios **jeden Reboot der Streamlit-Cloud überleben**,
kann die App sie in ein Google Sheet schreiben. Einmal einrichten (ca. 10 Min),
danach läuft es automatisch. Ist es nicht eingerichtet, nutzt die App weiter den
lokalen Speicher + Backup-Datei – nichts geht kaputt.

---

## Schritt 1 — Google Cloud Projekt & Service-Account

1. Gehe zu https://console.cloud.google.com → oben ein **neues Projekt** anlegen
   (z. B. „value-radar").
2. Menü → **APIs & Services → Library** → suche **„Google Sheets API"** →
   **Enable**.
3. Menü → **APIs & Services → Credentials → Create Credentials →
   Service account**. Namen vergeben (z. B. „value-radar-bot"), erstellen.
4. Den erstellten Service-Account anklicken → Reiter **Keys → Add Key →
   Create new key → JSON**. Es lädt eine **JSON-Datei** herunter – die brauchen
   wir gleich. Darin steht u. a. eine E-Mail wie
   `value-radar-bot@...gserviceaccount.com`.

---

## Schritt 2 — Google Sheet anlegen und teilen

1. Lege ein leeres Google Sheet an (https://sheets.new). Name egal.
2. Kopiere die **Sheet-ID** aus der URL:
   `https://docs.google.com/spreadsheets/d/`**`DIESE_LANGE_ID`**`/edit`
3. Klicke im Sheet auf **Teilen** und teile es mit der **Service-Account-E-Mail**
   aus Schritt 1 (die `...gserviceaccount.com`-Adresse) als **Bearbeiter/Editor**.
   Das ist wichtig – sonst darf die App nicht schreiben.

---

## Schritt 3 — Secrets in Streamlit eintragen

In Streamlit Cloud: **Manage app → Settings → Secrets**. Füge Folgendes ein –
den Block `[gcp_service_account]` füllst du mit den Werten aus der JSON-Datei:

```toml
GSHEET_ID = "DIESE_LANGE_ID_AUS_DER_SHEET_URL"

[gcp_service_account]
type = "service_account"
project_id = "dein-projekt-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "value-radar-bot@...gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
```

Wichtig beim `private_key`: Er muss exakt so übernommen werden, mit den
`\n` als Zeilenumbrüche in Anführungszeichen (genau wie in der JSON-Datei).

Speichern → die App startet neu.

---

## Schritt 4 — fertig

Öffne den Portfoliocheck → Bereich **„🗄️ Backup / Wiederherstellen"**. Steht dort
grün **„☁️ Cloud-Speicher aktiv (Google Sheets)"**, funktioniert alles: Ab jetzt
werden Portfolios ins Google Sheet geschrieben und überstehen jeden Reboot.

Falls dort nichts Grünes steht, prüfe: Sheets-API aktiviert? Sheet mit der
Service-Account-E-Mail geteilt? `GSHEET_ID` korrekt? `private_key` vollständig?

---

## Hinweise

- **Sicherheit:** Der Service-Account hat nur Zugriff auf genau dieses eine Sheet
  (weil nur dieses mit ihm geteilt ist). Die Secrets liegen verschlüsselt in
  Streamlit, nicht im Code/Repo.
- **Format:** Die App legt alle Portfolios als ein JSON in Zelle **A1** ab. Du
  kannst da reinschauen, solltest die Zelle aber nicht von Hand bearbeiten.
- Die Backup-Datei-Funktion (Download/Import) bleibt zusätzlich verfügbar – als
  zweite Sicherung oder zum Umziehen.
