# Value Radar aufs Handy bringen (Android) — realistische Wege

**Wichtig:** Value Radar ist eine *Streamlit*-App (ein Python-Webserver mit Browser-Oberfläche).
Daraus lässt sich **kein natives `.apk` kompilieren**. Der saubere Weg ist: die App **einmal
online stellen** und sie dann als **installierbare App / als echtes APK** aufs Handy holen.
Beides geht ohne Programmierkenntnisse.

---

## Überblick der Wege

| Weg | Ergebnis | Aufwand | Nur Handy möglich? |
|---|---|---|---|
| **A. Web-App + „Zum Startbildschirm"** | Icon wie eine App, öffnet die Web-App | sehr gering | ja (nach dem Deploy) |
| **B. PWABuilder → echtes .apk** | installierbares `.apk` (Play-Store-fähig) | gering | ja (im Browser) |
| **C. WebView-Wrapper selbst bauen** | eigenes `.apk` | hoch (Android Studio) | nein (PC nötig) |

Gemeinsame Voraussetzung für **alle** Wege: Die App muss **einmal deployt** (online gestellt)
werden. Das ist eine Einmal-Sache und am bequemsten an einem Computer (ca. 10 Minuten).

---

## Schritt 1 — App kostenlos online stellen (einmalig)

**Empfehlung: Streamlit Community Cloud** (kostenlos).

1. Kostenloses Konto auf https://github.com anlegen.
2. Den kompletten Projektordner `value_radar` als neues GitHub-Repository hochladen
   (am PC per „Add file → Upload files"; alle Dateien inkl. `dashboard.py`, `requirements.txt`,
   `.streamlit/` usw.).
3. Auf https://share.streamlit.io mit GitHub anmelden → **New app** → das Repo wählen →
   Hauptdatei `dashboard.py` → **Deploy**.
4. Nach 1–2 Minuten bekommst du eine feste URL wie
   `https://dein-name-value-radar.streamlit.app`.

Alternative: **Hugging Face Spaces** (https://huggingface.co/spaces, „Streamlit" als SDK).

> **Sicherheit zuerst (wichtig!):** Aktuell steht dein **Finnhub-API-Key im Klartext** in
> `config.py`. Wenn die App öffentlich erreichbar ist, ist auch der Key in den Dateien sichtbar,
> und Fremde könnten deine App nutzen. Vor dem Deploy:
> - Den Key aus `config.py` entfernen und stattdessen in **Streamlit → Settings → Secrets**
>   hinterlegen (`FINNHUB_API_KEY = "..."`). Die App liest ihn schon per Umgebungsvariable.
> - Überlege, die App **privat** zu halten (Hugging Face Spaces kann „private"; Streamlit Cloud
>   erlaubt Zugriffsbeschränkung über erlaubte E-Mail-Adressen).
> - Den im Chat geteilten Key kannst du bei Finnhub jederzeit neu generieren.

---

## Weg A — Als App-Icon (am schnellsten, reine Handy-Lösung)

Sobald die App online ist:

1. Die `.streamlit.app`-URL in **Chrome auf dem Android-Handy** öffnen.
2. Menü (⋮ oben rechts) → **„Zum Startbildschirm hinzufügen"** / „App installieren".
3. Fertig: Es liegt ein Icon auf dem Homescreen, das die App im Vollbild öffnet —
   fühlt sich an wie eine native App.

Das ist für die meisten der praktischste Weg und braucht **keinen** APK-Build.

---

## Weg B — Echtes `.apk` aus der URL (im Browser, ohne PC)

Wenn du wirklich eine installierbare `.apk`-Datei willst:

1. https://www.pwabuilder.com öffnen.
2. Deine `.streamlit.app`-URL einfügen → **Start**.
3. Reiter **Android** → **Generate Package** → es wird ein **signiertes `.apk`/`.aab`** erzeugt.
4. Die `.apk` herunterladen und auf dem Handy installieren
   (dafür „Installation aus unbekannten Quellen" für den Browser erlauben).

PWABuilder verpackt die Web-App in einen schlanken Android-Container — das ist genau das,
was ein „App aus einer Web-App"-APK ausmacht, und funktioniert komplett im Browser.

---

## Weg C — Eigener WebView-Wrapper (nur mit PC/Android Studio)

Für Bastler: ein winziges Android-Projekt, das nichts tut, außer deine URL in einer WebView
zu laden. Kernstück (Kotlin):

```kotlin
// MainActivity.kt
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val web = WebView(this)
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.loadUrl("https://DEINE-URL.streamlit.app")
        setContentView(web)
    }
}
```

```xml
<!-- AndroidManifest.xml: Internet-Berechtigung nicht vergessen -->
<uses-permission android:name="android.permission.INTERNET"/>
```

In Android Studio als „Empty Activity" anlegen, obiges einsetzen, **Build → Build APK**.
Das braucht aber einen Rechner mit Android Studio — für unterwegs ist **Weg A oder B** besser.

---

## Ehrliche Einordnung

- Eine **dauerhaft offline laufende** native App wäre ein komplettes Neuschreiben in einer
  mobilen Technologie (z. B. Flutter/Kotlin) inklusive Nachbau aller Module — ein eigenes,
  großes Projekt. Die Web-App-Wege oben geben dir denselben Funktionsumfang sofort.
- Die App **braucht Internet** (Kurse, News) — auch ein APK-Wrapper lädt die Online-Version.
- Kosten: Streamlit Community Cloud und PWABuilder sind kostenlos; bei kostenlosen Hostern
  „schläft" die App bei Nichtnutzung und braucht beim ersten Aufruf ein paar Sekunden zum Aufwachen.
