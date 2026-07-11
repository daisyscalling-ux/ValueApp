# Standard-Theme & Port fuer das Value-Radar-Dashboard.
# Port hier aenderbar, oder beim Start ueberschreiben:
#   streamlit run dashboard.py --server.port 8765

[server]
port = 8501
headless = true

[browser]
gatherUsageStats = false

[theme]
base = "dark"
primaryColor = "#FFB000"
backgroundColor = "#0A0E14"
secondaryBackgroundColor = "#121821"
textColor = "#E6E1D3"
font = "monospace"

[client]
# Viewer-Modus: deaktiviert Entwickler-Hotkeys (z.B. "C" = Cache leeren),
# damit Markieren/Kopieren und STRG+F nicht versehentlich Dialoge oeffnen.
toolbarMode = "viewer"
