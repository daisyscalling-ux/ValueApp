# Datenbasis fuer Bewertung und Risikoforschung

## Gepruefte Capex-Ergaenzung (18.10.2026)

Die Cashflow-Tabellen in den in capex_evidence.py verlinkten SEC-Berichten bestaetigen:

- ANSYS 2024: 44,045 Mio. USD gesamte Investitionsausgaben.
- Hess 2024: 4.640 Mio. USD E&P plus 306 Mio. USD Midstream, zusammen 4.946 Mio. USD.
- Pioneer 2023: 4.571 Mio. USD Oel-/Gasvermoegen plus 177 Mio. USD sonstige Anlagen,
  zusammen 4.748 Mio. USD. Nicht mit dem engeren bereinigten Management-FCF gleichsetzen.

Die alternativen Datenpunkte werden nur fuer gepruefte CIK, Einreichung, Periode,
USD-Einheit und exakte Komponentenwerte verwendet. Keine Rueckuebertragung einer
spaeteren Einreichung auf fruehere Entscheidungszeitpunkte. Eine unvollstaendige
Komponentensumme oder ein widerspruechlicher Standardwert bleibt gesperrt.
Die Originalfelder bleiben unveraendert; capex_method und capex_review erklaeren
die Ergaenzung. Aeltere Berichte brauchen eigene Belege.

Lokaler Abgleich mit dem bestehenden Forschungsarchiv: zusaetzlich zwei
FCF-Stichtage bei Hess, zwei bei ANSYS und einer bei Pioneer. Noch keine
vollstaendige Dreierkombination aus FCF, Nettoschulden und Verbindlichkeiten
zusammen mit einem vollstaendigen Kursfenster. Kein neuer Produktionsscore.

## Wie daraus bessere Bewertungen entstehen koennen

Fair Value ist nicht direkt beobachtbar. Ein spaeterer Boersenkurs allein beweist
nicht, dass ein damaliger innerer Wert richtig oder falsch war. Daher trennen:

1. Datenqualitaet: Perioden, Waehrungen, Aktienzahl, Kapitalansprueche, Schulden und
   Cashflows vor Modellrechnung abgleichen. Minderheiten auch bei Hess beachten.
2. Operative Prognosen: Geschaetzte Umsaetze, Margen und Cashflows mit spaeteren
   berichteten Ergebnissen vergleichen, je Branche und Konjunkturphase.
3. 12-Monats-Kursziel: damaliges Kursziel separat mit dem spaeteren splitbereinigten
   Kurs vergleichen. Dividenden nur bei einem ausdruecklichen Gesamtrenditeziel
   hinzufuegen; Unternehmensuebernahmen und Delistings gesondert behandeln.
4. Prognosearchiv: pro Berechnung Zeitpunkt, Datenstichtage, Quellen, Modellversion,
   Annahmen und Bear/Base/Bull speichern. Historisch spaeter bekannte Analystenziele
   oder Guidance duerfen nicht als damaliges Wissen verwendet werden.
5. Testdesign: zeitlich fortlaufende Trainings-/Testfenster; zwischen beiden einen
   Abstand entsprechend dem Prognosehorizont lassen. Abhaengige ueberlappende
   Beobachtungen und Firmencluster beachten. Letzte Testperiode nicht optimieren.
6. Vergleich: heutige unveraenderte Modelle gegen einfache Ausgangsmodelle testen.
   Fehlerverteilung, systematische Ueber-/Unterschaetzung und tatsaechliche
   Abdeckung der Szenariobaender messen. Datenabdeckung separat zeigen.

Die vorhandene Studie hat 21/63/126 Handelstage; ein 12-Monats-Test benoetigt
zusaetzlich etwa 252 Handelstage und ausreichend lange Nachbeobachtung. Die
vier ausgeschiedenen Firmen sind keine repraesentative Kalibrierungsstichprobe.
Es fehlen noch historische Prognosen, weitere Berichte, Kursreihen und Teile
der Kapitalmassnahmen. Das Risikomodell darf nicht pauschal als Abschlag auf
Fair Value addiert werden, wenn WACC oder Cashflows das Risiko schon enthalten.

Ziel: robustere Annahmen und ehrlichere Bandbreiten, nicht automatisch ein
Fair Value naeher am aktuellen Kurs. Erst unabhaengige Tests entscheiden,
welche Modellanpassungen in die App uebernommen werden.
