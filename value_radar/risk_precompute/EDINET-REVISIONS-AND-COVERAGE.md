# EDINET: Korrekturberichte, Investitionen und universumsweite Kontrolle

Stand: 25.10.2026. Ergaenzt JAPAN-AND-FINANCIAL-SUPPLY.md.

## Gemeinsamer Arbeitsblock

1. Korrekturberichte (130) werden ueber parentDocID mit dem Originalbericht (120) verknuepft. Fehlende Periodenmetadaten duerfen ausschliesslich aus dieser geprueften Kette stammen. Finanzwerte werden niemals vom alten Bericht uebernommen. Ungeklaerte, zurueckgezogene und widerspruechliche Revisionen bleiben gesperrt bzw. werden verworfen. Original- und Korrekturtage werden vor dem Abruf erneut geprueft.
2. Die offiziellen JGAAP-/IFRS-Summen fuer Sachanlagen und immaterielle Investitionen werden unterstuetzt. Eine gemeldete Gesamtsumme wird nicht nochmals mit Einzelkomponenten addiert. Vorzeichen, Vollstaendigkeit, doppelte Fakten und Widersprueche zwischen Summe und Bestandteilen werden geprueft. Rundungstoleranzen stammen aus XBRL decimals, nicht aus einer pauschalen Prozentfreigabe.
3. Explizit gemeldete IFRS InterestBearingLiabilities werden als verzinsliche Schulden erfasst. Es braucht entweder die Gesamtsumme oder beide vollstaendigen Laufzeitbestaende. Fehlend ist niemals null. Der Leasingumfang ist nicht separat abgeglichen; diese Einschraenkung reist mit der Kennzahl. JGAAP-Gesamtverbindlichkeiten und einzelne Kredite werden nicht als Finanzschulden umgedeutet.
4. OCF, FCF und Schuldenquote werden einzeln mit Quelle, Periode und Berichtskennung gefuehrt. Eine fehlende CapEx-Zahl entfernt nicht mehr eine unabhaengig gueltige OCF-Beobachtung. Bestehende Kennzahlen werden nicht ueberschrieben. Zur Ergaenzung einer offenen Bilanz muessen Periode, Waehrung, Bilanzsumme und Kassenbestand uebereinstimmen. Abweichungen werden als reconcile_sources im Nachversorgungsplan ausgewiesen.
5. cf_risk_coverage_changes.json vergleicht nach jedem Lauf die neue Abdeckung mit dem VOR dem ersten Audit gesicherten, zuletzt veroeffentlichten Stand. Alle Maerkte und Datenbereiche werden beruecksichtigt. Neue/entfernte Notierungen sind separat; context_only gilt nicht als vollstaendig verfuegbar. Fehlende, doppelte, zukuenftige oder zu alte Vergleichsstaende erzeugen keinen erfundenen Fortschritt. Der GitHub-Lauf zeigt die Zusammenfassung automatisch an.

Die Parser-Version erzwingt beim naechsten Lauf eine erneute Auswertung der bisherigen EDINET-Ziele. Ein erfolgreicher Download allein bestaetigt keine Vollstaendigkeit. Begrenzte numerische Originalfakten und ein SHA256 der Quelldatei erleichtern die weitere Pruefung; Unternehmens-Erweiterungstags werden ausschliesslich als Diagnose gespeichert, nicht automatisch als Finanzwerte akzeptiert. Keine Rohtexte, Zugangsdaten oder API-URLs mit Schluesseln werden exportiert.

## Nachweis und Grenzen

- Produktionsbasis: daily-risk vom 25.10.2026, 1.330 Notierungen. 64 offene Bilanzfaelle in Hauptmaerkten (53 primaer, 11 Europa). context_only ist separat und kein abgeschlossener branchenspezifischer Risikoscore.
- Gespeicherte offizielle Verzeichnisse: die fuenf bisher blockierten Korrekturen fuer TSE:7012, TSE:4689, TSE:8267, TSE:2503 und TSE:4324 werden eindeutig aufgeloest. Ob die heruntergeladenen Korrekturen alle benoetigten Fakten enthalten, muss der naechste produktive Lauf zeigen.
- Lokaler Durchlauf mit den bestehenden Produktionsdaten: 2.440 zuvor verfuegbare Bilanzkennzahlen unveraendert; keine kuenstliche Verbesserung der Abdeckungszahlen.
- 159 Python-Tests; 9 EDINET-Integrationstests; 33 Universumschecks; Kontextpruefungen; 24 Branchen-/Kalenderchecks und 6 Checks fuer breiten Branchenkontext bestanden.
- Die neuen Finanzfelder werden nur fuer Risikokontext verwendet. Fair Value, Kursziele und Gewichtungen werden nicht geaendert. Keine kalibrierte Verlustwahrscheinlichkeit.

## Offizielle Quellen

- FSA 2026 EDINET Taxonomy: https://www.fsa.go.jp/search/20251111.html
- Schema-Archiv: https://www.fsa.go.jp/search/20251111/1c_Taxonomy.zip
- API-Spezifikation: https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140206.pdf
- Offizielle Beispielberichte: https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140116.zip

## Einmaliger naechster Schritt

Nach Zusammenfuehrung daily-risk auf main einmal ausfuehren. EDINET_API_KEY ist bereits als Repository-Secret vorgesehen. Kein gesonderter Lauf pro Unternehmen und kein Cloudflare-Upload fuer diesen Datenblock. Danach cf_risk_coverage_changes.json, cf_financial_supply_plan.json und den EDINET-Bericht gemeinsam pruefen; nicht nur den gruenen Jobstatus.
