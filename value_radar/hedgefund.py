# Value Radar online stellen — privat, nur für dich, mit Passwort + Biometrie

Ziel: Die App läuft in der Streamlit Cloud, **nur du** kommst rein (privat
freigegeben **und** Passwort-Gate), und du meldest dich bequem per
**Fingerabdruck/FaceID** über deinen Passwortmanager an.

---

## Schritt 0 — einmal vorbereiten (am PC)

1. Kostenloses Konto auf https://github.com anlegen.
2. **Neues, PRIVATES Repository** erstellen (z. B. `value-radar`). Wichtig:
   „Private" wählen, nicht „Public".
3. Den kompletten Ordner `value_radar` hochladen (**ohne** die Datei
   `.streamlit/secrets.toml` — die bleibt lokal! Die `.gitignore` sorgt schon
   dafür, dass sie nicht mitgeht).

> Prüfen: Im Repo darf **keine** `secrets.toml` liegen. `secrets.toml.example`
> darf dabei sein — die enthält keine echten Keys.

---

## Schritt 1 — App deployen

1. Auf https://share.streamlit.io mit GitHub anmelden.
2. **Create app → Deploy a public app from GitHub** → dein privates Repo wählen.
3. Main file: `dashboard.py` → **Deploy**.

---

## Schritt 2 — Secrets setzen (Passwort + API-Keys)

In Streamlit Cloud: **Manage app → Settings → Secrets** und diesen Inhalt
eintragen (deine echten Werte einsetzen):

```toml
APP_PASSWORD = "ein-langes-einzigartiges-passwort"
FINNHUB_API_KEY = "dein_finnhub_key"
FMP_API_KEY     = "dein_fmp_key"
```

Speichern → die App startet neu. Beim Öffnen erscheint jetzt das **Login**.
Ohne korrektes Passwort kommt niemand ins Dashboard.

---

## Schritt 3 — Zugriff auf DICH beschränken (privat)

In Streamlit Cloud: **Manage app → Settings → Sharing**:

- Auf **„Only specific people can view this app"** stellen.
- **Nur deine eigene E-Mail-Adresse** freigeben (die, mit der du dich bei
  Google/GitHub anmeldest).

Damit gilt: Fremde sehen nicht mal die App (Zugriff gesperrt), UND selbst wenn
jemand den Link hätte, bräuchte er zusätzlich das Passwort. Doppelter Schutz.

---

## Schritt 4 — Anmeldung per Fingerabdruck/FaceID (Biometrie)

Die App kann Biometrie nicht selbst abfragen (das darf keine Web-App). Der
saubere Weg läuft über deinen **Passwortmanager**:

1. App-Link im Handy-Browser öffnen, Passwort einmal eingeben.
2. Der Passwortmanager (iCloud-Schlüsselbund / Google Passwortmanager /
   Bitwarden …) fragt „Passwort speichern?" → **Ja**.
3. Ab dann füllt er das Passwortfeld automatisch aus und entsperrt sich dabei
   per **Fingerabdruck/FaceID**. Fühlt sich an wie ein biometrischer Login,
   ist aber sicher (deine Biometrie verlässt nie das Gerät).

Optional noch bequemer: bei **Google/GitHub einen Passkey** einrichten — dann
läuft schon der Login beim Identity-Provider biometrisch.

---

## Schritt 5 — wie eine App aufs Handy

Im Handy-Chrome die App-URL öffnen → Menü → **„Zum Startbildschirm hinzufügen"**.
Liegt als Icon, öffnet im Vollbild.

---

## Wichtige Hinweise

- **Keys niemals im Code / im Repo.** Sie gehören ausschließlich in die Secrets.
  Wenn ein Key je öffentlich war: bei Finnhub/FMP neu generieren.
- **Gespeicherte Portfolios**: liegen lokal als Datei auf dem jeweiligen Rechner.
  In der Cloud sind sie an die App-Instanz gebunden und nicht privat pro Nutzer —
  für dich als Einzelnutzer aber unproblematisch.
- Kostenlose Cloud „schläft" bei Nichtnutzung; der erste Aufruf danach braucht
  ein paar Sekunden zum Aufwachen.
