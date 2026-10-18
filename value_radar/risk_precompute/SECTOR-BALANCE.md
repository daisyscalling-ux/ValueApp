# Branchenspezifische Finanzdatenpruefung

Diese Aenderung betrifft Export, Abdeckungsbericht und Nachladewarteschlange.
Sie aendert weder den Fair Value noch den sichtbaren Cloudflare-Risikoscore.
Kein automatischer kalibrierter Score wird erzeugt.

## Profile

Eine aktuelle Branchenklassifikation (maximal 90 Tage) ist erforderlich.
Exakte bekannte Bezeichnungen waehlen Bank, Versicherer oder spezialisierten
Finanzdienstleister. Versicherungsvermittler sind keine Versicherer.
Investmentbanken/Broker und Finanzkonglomerate bekommen ein separates Profil.
Fehlende/veraltete Klassifikation erzeugt unclassified mit Pruefauftrag.

Bei Unternehmen ausserhalb dieser Finanzprofile werden Nettoschulden/Bilanzsumme
und FCF/Bilanzsumme einzeln verfuegbar gehalten. Ein fehlender Capex-Wert darf
eine belegte Verschuldungskennzahl nicht verstecken. Der bisherige gemeinsame
ratios-Block bleibt bei unvollstaendigen oder ungeeigneten Daten null.

Finanzprofile verwenden Eigenkapital/Bilanzsumme und Jahresergebnis/
Stichtagsbilanzsumme nur als Buchwertkontext. Letzteres ist keine ROA auf Basis
durchschnittlicher Aktiva. Negatives Eigenkapital und Verluste bleiben sichtbar.
Industrielle FCF-/Nettoschuldenquoten sind hier not_applicable, nicht null Risiko.

Banken benoetigen zusaetzlich regulatorisches Kapital (CET1), Liquiditaet
(LCR bzw. lokales Aequivalent) und Kreditqualitaet. Versicherer benoetigen
anrechenbare Eigenmittel, Kapitalanforderung und den passenden regulatorischen
Geltungsbereich. Solvency II gilt nicht automatisch fuer jedes Land.
Diese Angaben sind noch NICHT automatisch befuellt. Die Warteschlange weist
sie als sector_financials / review_required aus, statt erfolglose Capex-Abrufe
als Ersatz fuer die regulatorische Pruefung zu priorisieren.

Quellen:
- https://www.bis.org/committees/bcbs/basel-framework
- https://www.bis.org/committees/bcbs/basel-framework/standard/lcr?allChapters=true
- https://www.eiopa.europa.eu/browse/regulation-and-policy/solvency-ii_en

## Zusaetzlicher Abruf

Yahoo-Jahrestabellen liefern nun auch Total Liabilities Net Minority Interest,
Interest Expense und Net Interest Income, sofern explizit berichtet.
Keine Ableitung regulatorischen Kapitals aus diesen Feldern. Die bestehende
Perioden-/Quellenpruefung bleibt bestehen. Die Zusatzfelder sind Vorbereitung
fuer weitere Finanzanalysen und beeinflussen aktuell keinen Risikoscore.

## Gegenpruefung

Snapshot 18.10.2026 18:48:49 UTC, 1330 aktive Notierungen, keine neuen Werte:
- vorher: 1123 verfuegbar, 207 fehlend nach einheitlicher Industrie-Pruefung
- jetzt: 934 vollstaendige Unternehmensquoten, 223 Finanz-/Branchenkontext,
  118 teilweise verfuegbar, 55 ohne nutzbaren Kennzahlenblock

Diese Kategorien sind methodisch verschieden. Der Rueckgang bei missing ist
KEIN Beleg fuer neu beschaffte Daten oder vollstaendige Bankrisikobewertungen.
Markt-/Kurs-/Historienabdeckung bleibt unveraendert.

Nach Merge fundamentals-daily ohne Symbolfilter, anschliessend daily-risk.
Kein Cloudflare-Deployment erforderlich; die Anzeigeintegration ist separat.
