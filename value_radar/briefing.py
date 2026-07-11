# Anleitung für Einsteiger (Windows) — Value Radar starten

Diese Anleitung setzt **keinerlei Vorwissen** voraus. Geh einfach Schritt für
Schritt durch. Wenn etwas klemmt, schau unten unter „Wenn etwas nicht klappt".

---

## Schritt 1 — Python installieren (nur beim ersten Mal)

Python ist die Sprache, in der das Programm geschrieben ist. Dein Windows hat es
noch nicht von Haus aus.

1. Gehe auf **https://www.python.org/downloads/**
2. Klicke auf den großen gelben Knopf **„Download Python 3.x"**.
3. Öffne die heruntergeladene Datei (unten im Browser oder im Ordner „Downloads").
4. **WICHTIG — der häufigste Anfängerfehler:** Setze unten im Fenster das Häkchen
   bei **„Add python.exe to PATH"**, *bevor* du auf Installieren klickst.
   Ohne dieses Häkchen findet Windows Python später nicht.
5. Klicke auf **„Install Now"** und warte, bis „Setup was successful" erscheint.
   Schließe das Fenster.

---

## Schritt 2 — Das Programm-Paket entpacken

1. Du hast die Datei **`value_radar.zip`** heruntergeladen (im Ordner „Downloads").
2. **Rechtsklick** auf die Datei → **„Alle extrahieren…"** → **„Extrahieren"**.
3. Es entsteht ein Ordner namens **`value_radar`**. Öffne ihn per Doppelklick.
   Du siehst darin Dateien wie `dashboard.py`, `main.py`, `README.md` usw.
4. Verschiebe diesen Ordner an einen Ort, den du wiederfindest — z. B. auf den
   **Desktop**. (Einfach den Ordner anklicken und auf den Desktop ziehen.)

---

## Schritt 3 — Das Terminal im richtigen Ordner öffnen

Das „Terminal" ist ein Fenster, in das man Befehle tippt. Der Trick: Es muss
**in deinem `value_radar`-Ordner** geöffnet werden.

1. Öffne den Ordner **`value_radar`** (sodass du `dashboard.py` siehst).
2. Klicke oben in die **Adressleiste** des Fensters (dort steht der Pfad, z. B.
   `Dieser PC > Desktop > value_radar`). Der Text wird blau markiert.
3. Tippe dort einfach **`cmd`** und drücke **Enter**.
4. Es öffnet sich ein schwarzes Fenster — das ist dein Terminal, und es startet
   bereits im richtigen Ordner. 👍

---

## Schritt 4 — Die benötigten Bausteine installieren (nur beim ersten Mal)

Tippe folgenden Befehl in das schwarze Fenster und drücke **Enter**:

```
py -m pip install -r requirements.txt
```

Jetzt lädt es einige Pakete herunter (yfinance, streamlit usw.). Das dauert
ein bis zwei Minuten. Warte, bis du wieder eine blinkende Eingabezeile siehst.

---

## Schritt 5 — Das Dashboard starten

Tippe diesen Befehl und drücke **Enter**:

```
py -m streamlit run dashboard.py
```

Beim allerersten Start fragt Streamlit eventuell nach einer E-Mail — du kannst
einfach **Enter** drücken (Feld leer lassen), das ist optional.

Nach ein paar Sekunden öffnet sich **automatisch dein Browser** mit dem
Dashboard. Falls nicht, öffne den Browser selbst und gib in die Adresszeile ein:

```
http://localhost:8501
```

🎉 Fertig. Links den Ticker eintippen (z. B. `MU`), Playbook wählen, auf
**ANALYSIEREN** klicken.

---

## Das Dashboard wieder beenden

- Gehe zurück zum schwarzen Terminal-Fenster und drücke **Strg + C**.
- Oder schließe das schwarze Fenster einfach. (Das Dashboard im Browser ist dann
  „tot" — beim nächsten Mal neu starten, siehe unten.)

---

## Beim nächsten Mal (Schritte 1, 2, 4 entfallen!)

1. `value_radar`-Ordner öffnen.
2. In die Adressleiste `cmd` tippen, Enter.
3. `py -m streamlit run dashboard.py` eingeben, Enter.

Das ist alles. Du musst Python und die Pakete **nicht** erneut installieren.

---

## Wenn etwas nicht klappt

**„'py' wird nicht erkannt" oder „'python' wird nicht erkannt"**
→ Das Häkchen „Add python.exe to PATH" (Schritt 1.4) hat gefehlt. Lösung:
Python deinstallieren (Windows-Einstellungen → Apps), neu installieren und das
Häkchen setzen. Danach Terminal **neu öffnen**.

**„'pip' wird nicht erkannt"**
→ Nutze immer die Variante mit `py -m` davor, also `py -m pip install ...`
(genau wie in dieser Anleitung).

**„streamlit: command not found / wird nicht erkannt"**
→ Starte mit `py -m streamlit run dashboard.py` (mit `py -m` davor).

**Windows-Firewall fragt nach Erlaubnis**
→ Auf **„Zugriff zulassen"** klicken. Das ist normal, es läuft nur lokal.

**„Port 8501 is already in use" (Port belegt)**
→ Anderen Port nehmen: `py -m streamlit run dashboard.py --server.port 8502`
und dann `http://localhost:8502` aufrufen.

**Falscher Ordner** (Fehler „can't find dashboard.py")
→ Das Terminal wurde nicht im `value_radar`-Ordner geöffnet. Schritt 3
wiederholen: in die Adressleiste des richtigen Ordners `cmd` tippen.

---

## Später, optional: mehr News & Daten freischalten

Das Dashboard läuft komplett kostenlos. Für News, Wettbewerber und Insider-Daten
braucht es einen kostenlosen Schlüssel von **finnhub.io**. Das ist ein Extra für
später — sag mir Bescheid, dann zeige ich dir das in einfachen Schritten.
