# Breiter Branchenkontext

Wenn die enge Vergleichsgruppe weniger als fünf geeignete andere Emittenten in derselben Handelswährung enthält, kann ein zusätzlicher breiter Sektorkontext angezeigt werden.

Die Sektorzuordnung stammt aus höchstens 30 Tage alten, anhand der aktuellen Notierung geprüften Yahoo-Unternehmensprofilen. Widersprüchliche Zuordnungen innerhalb eines Emittenten werden ausgeschlossen. Es gibt keine unscharfe Namenssuche und keine Vermischung von Handelswährungen.

Der zusätzliche Vergleich benötigt mindestens zehn andere Emittenten. Er verwendet dieselben zeitgleichen Kursfenster, mindestens 200 gemeinsame Kurstage und 53 Wochenstände wie der bestehende Vergleich. Jeder Emittent zählt einmal; die eigene Gesellschaft wird ausgeschlossen. Die Auswahl erfolgt nach Datenabdeckung, nicht nach Rendite.

Der enge Vergleich behält seinen ursprünglichen Status. Die zusätzliche Ebene steht unter broaderContext und wird in summary.broaderContext separat gezählt. Sie erhält quality=broad_sector_context und score=null. Sie verändert weder Fair Value noch Gewichtungen noch die als verfügbar gezählten engen Vergleiche. Fehlende oder veraltete Zielhistorien werden durch die neue Ebene nicht umgangen.

Aktivierung: PR zusammenführen, daily-risk auf main starten und den aktualisierten Desktop/cf/dist-Ordner zu Cloudflare hochladen. Der Worker reicht die zusätzlichen Felder im bestehenden Datenbericht durch; keine neuen Secrets oder Endpunkte sind erforderlich.

Validierung: sechs neue Berechnungstests, 24 bestehende Sektor-/Kalenderprüfungen und vier Tests der Cloudflare-Anzeige. Die tatsächliche zusätzliche Abdeckung muss nach dem produktiven Lauf geprüft werden.

