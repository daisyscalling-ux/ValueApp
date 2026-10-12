# Zehn historische Kursreihen: Pruefung vom 12.10.2026

Grundlage: erfolgreicher main-Lauf 38209892625, Datenzeitpunkt 2026-10-12T05:53:10.718380+00:00, letzter Handelstag 09.10.2026. Die Auswertung wurde lokal mit dem unveraenderten Roharchiv wiederholt. Kein neuer Vollabruf war erforderlich.

## Ergebnis und Korrekturen

| Fall | Befund und Behandlung |
| --- | --- |
| DOW | Dow Chemical vor 2017 und der 2019 abgespaltene heutige Dow sind getrennte Wertpapiere. Alte Mitgliedschaft bleibt unter DOW_CHEMICAL_PRE2017 erhalten, historische Preise fehlen. Heutiger DOW ist waehrend seiner Mitgliedschaft kalenderseitig vollstaendig. |
| FOX / FOXA | Alte 21st Century Fox und neue Fox Corporation getrennt, ebenso Aktienklassen A/B. Am 19.03.2019 unterscheiden die belegten Unternehmensnamen Eintritt und Austritt trotz identischer Ticker. Historische 21CF-Preise bleiben offen; moderne Fox-Reihen sind kalenderseitig vollstaendig. |
| SNDK | Alte SanDisk vor der Uebernahme 2016 getrennt von neuer Sandisk nach der Abspaltung 2025. Alte Mitgliedschaft und fehlende Preise bleiben erhalten. Neue Reihe ist waehrend ihrer Indexmitgliedschaft kalenderseitig vollstaendig. |
| Q | QuintilesIMS wurde 2017 IQVIA / IQV. Historisches Q wird nur vor diesem belegten Wechsel IQV zugeordnet. Qnity ab 2025 bleibt separat. Bereits vorhandene IQV-Preise decken die fruehere Mitgliedschaft ab. |
| FISV | Preis am 12.11.2025 fehlt. Gezielter Yahoo-Abruf 10.-14.11.2025 am 12.10.2026 liefert ebenfalls nur 10., 11., 13. und 14.11. Kein Auffuellen, keine gueltige Tagesrendite ueber die Luecke. |
| VLTO | Preise 02.-03.10.2023 fehlen. Gezielter Yahoo-Abruf 29.09.-05.10.2023 beginnt ebenfalls erst am 04.10. Der Emittent bestaetigt Handelsbeginn am 02.10.; somit keine Verschiebung des Anfangs auf den ersten verfuegbaren Yahoo-Kurs. |
| FTV | Fehlende Tagesrendite am 05.07.2016 betrifft ersten regulaeren Handelstag der Abspaltung. Als Notierungsgrenze gekennzeichnet, weiterhin unbestaetigt. |
| KHC | Fehlende Tagesrendite am 06.07.2015 betrifft Beginn der neuen Notierung nach Fusion. Keine erfundene Verbindung zu KRFT, keine Nullrendite. |
| VYLR | Fehlende Tagesrendite am 01.10.2026 betrifft Notierungsbeginn nach Abspaltung. Grenzfall separat gekennzeichnet; keine Rendite aus dem Mutterunternehmen uebernommen. |

Primaerquellen mit exakten Daten stehen in security_identity_evidence.json unter renames, identity_splits und listing_boundaries. Die Quellen belegen Unternehmens-/Tickerereignisse, nicht die Korrektheit aller Yahoo-Renditen.

## Nachpruefung

- 46 lokale Tests erfolgreich, einschliesslich Wiederverwendung von Tickern, Aktienklassen und Q/IQV/Qnity-Trennung.
- Keine verbleibenden Widersprueche in der Mitgliedschaftsrekonstruktion.
- 764 statt 760 getrennte Forschungsidentitaeten: vier frueher vermischte Wertpapiere werden jetzt separat gezaehlt.
- 599 kalenderseitig vollstaendige und 165 unvollstaendige Identitaeten (vorher 594 / 166).
- Erwartete Preistage unveraendert: 1.618.287. Fehlende Preistage: 173.884 (vorher 173.930).
- Gueltige Tagesrenditen: 1.444.022; fehlende/ungueltige: 173.765.

Die Verbesserung entsteht durch korrekte Zuordnung vorhandener Daten, nicht durch neue Yahoo-Kurse. Neue Fox-Kurse aus dem Vorhandel werden nicht mehr der alten Gesellschaft zugerechnet. Alte Gesellschaften bleiben im Nenner. Kalender-Vollstaendigkeit ist keine Freigabe fuer Produktionsscores oder ein bestaetigter Total-Return-Backtest. Abwicklungsrenditen, Kapitalmassnahmen, vollstaendige historische Identitaeten und Haltefenster nach Indexaustritten bleiben gesondert zu pruefen.

