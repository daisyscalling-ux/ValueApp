# Explorative finanzielle Risikoprüfung

Feste Stichprobe: 40 heutige US-Nichtfinanzunternehmen, je acht aus Technologie, Energie, Gesundheit, Industrie und Konsum. Keine Auswahl anhand späterer Renditen. Keine repräsentative Universumsstudie; historische Ausgeschiedene fehlen. Identität wird per SEC-CIK und Ticker sowie Yahoo-Symbol/Instrument/Währung geprüft.

## Definitionen und Datenlücken
Jährlicher CFO minus PP&E-Investitionen geteilt durch Bilanzsumme (mit umgekehrtem Vorzeichen), Verbindlichkeiten/Bilanzsumme sowie Nettoschulden/Bilanzsumme. Verbindlichkeiten sind nicht gleich Finanzschulden. Fehlen Verbindlichkeiten, werden nur explizite kurzfristige plus langfristige Verbindlichkeiten derselben Einreichung verwendet. Bilanzsumme minus Eigenkapital allein wird nicht mehr als Verbindlichkeiten angenommen: separat ausgewiesenes rückzahlbares Kapital könnte enthalten sein. Gemeldete rückzahlbare Minderheiten können eine Bilanzabweichung erklären, wenn die Überleitung innerhalb 0,1 % der Bilanzsumme schließt. Ein ungeklärter Widerspruch sperrt das Verbindlichkeitenmerkmal, nicht unabhängig belegte Cashflow- oder Schuldenmerkmale. Fehlende Finanzschulden werden nicht durch Verbindlichkeiten ersetzt. Kein fehlender Betrag wird null. CFO-Capex ist nicht ROIC-FCFF und jährliche Werte sind nicht TTM. Damit wird ein separates Forschungsmodell, nicht der bestehende Finanzscore, untersucht.

Je Kursstichtag wird die jüngste damals bekannte Jahresperiode aus dem SEC-Pilot gewählt, höchstens 550 Tage alt. Felder aus derselben Einreichung/Periode/Einheit, keine späteren oder taggleichen Einreichungen. Nicht rekonstruierte spätere Jahres-Amendments der Periode sperren die Beobachtung. Standardtags und vollständige Jahresberichte: Quartalsberichte, individuelle XBRL-Tags und frühere Earnings-Releases bleiben Grenzen des Verfahrens. Fehlende/konfliktbehaftete Angaben bleiben im Bericht sichtbar.

## Vergleich
Kursfenster stammen direkt aus der unveränderten risk_precompute/src/lib/risk-validation.ts: Quartalsstichtage mit mindestens 505 vergangenen Handelstagen, Einstieg zum nächsten Schlusskurs, 21/63/126 folgende Sitzungen. Ziel ist größter zwischenzeitlicher Verlust ab Einstieg, keine Ereigniswahrscheinlichkeit. Yahoo Adjusted Close ist eine Anbieter-Näherung für Total Return, keine archivierte damalige Preisversion.

Frühere Fenster enden vor 2025-01-01, spätere starten danach; übergreifende Fenster werden ausgeschlossen. Feste Ridge-Regression alpha=1, Skalierung ausschließlich auf früheren Daten. Je Finanzmerkmalsgruppe zwei Vergleiche: Jahresvolatilität allein gegen Volatilität plus Finanzen, Kursscore allein gegen Kursscore plus Finanzen. Je Vergleich exakt dieselben vollständigen Beobachtungen. Mindestens acht Unternehmen in beiden Perioden, 32 frühere und 16 spätere Fenster; darunter keine Aussage. Keine Anpassung der Risikogewichte. Die spätere Periode wurde bereits im ersten Versuch betrachtet und ist kein unangetasteter Bestätigungstest.

Ausgabe: mittlerer quadratischer Fehler im späteren Zeitraum, Differenz der Fehler und Sektoraufschlüsselung. Positive Verbesserung bedeutet nur geringeren Fehler in dieser Stichprobe. Mehrere Vergleiche, überlappende Horizonte, wiederkehrende Firmen und Marktschocks: keine Signifikanzbehauptung, keine Auswahl des besten Modells als vermeintlich bewiesener Gewinner. Zwölf Jahre Kurshistorie werden angefragt. Die Krisen 2020/2022 können damit im früheren Trainingszeitraum liegen; sie sind kein unabhängiger Krisentest.

## Betrieb
Workflow sec-financial-study. Erstlauf automatisch, wenn seine Workflow-Datei auf codex/sec-financial-study angelegt wird; später manuell. Bestehendes SEC_USER_AGENT-Secret. Nur Leserechte; keine Änderungen an App oder Risikoscores. PR-Ereignisse führen nur Offline-Tests aus. Der bisherige SEC-Pilot bleibt separat.

Artefakt enthält Original-SEC-Daten und Prüfsummen, Kurshistorien, Beobachtungsfenster, zugeordnete Jahresdaten, Abdeckungsfehler und study-report.json/md. 90 Tage Aufbewahrung; für ein dauerhaftes Archiv herunterladen. Ein abgebrochener Lauf kann Teilfortschritt liefern. Keine nutzbaren Vergleiche führt zu fehlgeschlagenem Job mit Bericht.

Lokal: 15 Offline-Tests bestanden; mit dem vorhandenen Zwei-Firmen-Archiv wurden 56 Kursfenster zugeordnet, alle Modellvergleiche wegen zu geringer Stichprobe gesperrt. Der erweiterte Lauf ist erfolgreich abgeschlossen: 19 geladene Unternehmen, 532 Kursfenster, 18 auswertbare Vergleiche und sechs wegen fehlender Nettoschuldendaten gesperrte Vergleiche. Ergebnisse und Einschränkungen: [STUDY-RESULTS.md](STUDY-RESULTS.md).


## Erweiterung nach dem Erstlauf

Die Jahresauswahl berücksichtigt auch CFO aus fortgeführten Aktivitäten. Ein Gesamt-CFO wird daraus ausschließlich mit separat gemeldetem CFO aufgegebener Aktivitäten derselben Einreichung und Periode rekonstruiert. Fehlend bedeutet nicht null. Neue Jahresberichte verdrängen damit ältere Auswahlstände auch dann, wenn kein vollständiger Gesamt-Cashflow verfügbar ist.

Die API liefert nur Standardtaxonomie-Fakten für das gesamte Unternehmen; individuelle Tags und dimensionale Details bleiben eine Datenlücke ([SEC-Dokumentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)). Definitionen der verwendeten Tags stammen außerdem aus den archivierten Companyfacts-Antworten.

Der erste Ergebnisbericht mit 19 geladenen Unternehmen bleibt unverändert als Vergleichsstand erhalten. Die Erweiterung ist ein neuer explorativer Lauf mit anderer Stichprobe, längerer Historie und korrigierter Datenzuordnung. Ein Unterschied zum Erstlauf isoliert deshalb keinen einzelnen Änderungseffekt.
