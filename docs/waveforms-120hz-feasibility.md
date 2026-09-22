# Machbarkeit: Waveforms mit 120 Hz

**Archiviert: Der Benutzer hat diese Idee am 22.09.2026 verworfen.**
Kein aktiver Auftrag und keine geplante Funktion; nur historische Notizen.

Untersuchung am 22.09.2026 für Rekordbox 7.2.18.0311, Windows x64.
Auftrag: nur untersuchen, nichts implementieren oder aktivieren.

## Ergebnis

Technisch plausibel, aber noch kein verifizierter Patch für tatsächlich 120
unterschiedliche Waveform-Bilder pro Sekunde. Der Einstellungsweg und Teile der
OpenGL-Zeichenstrecke sind identifiziert. Ein bloßes Setzen von `RenderDelay=120`
reicht als Nachweis nicht aus: Dieser Wert ist bereits gespeichert. Die
tatsächliche Waveform-Bildrate und ihr begrenzender Pfad sind noch zu messen.

Rekordbox war während dieser Untersuchung nicht gestartet. Es wurde nicht
gestartet, injiziert, gepatcht oder umkonfiguriert. Es wurden ausschließlich
vorhandene Dateien und Windows-Systeminformationen gelesen; dieses Dokument
hält die Ergebnisse fest.

## Lokale Befunde

- Windows meldet AMD Radeon RX 6900 XT, 3440 × 1440, 240 Hz. Das ist die gemeldete
  aktuelle Anzeige-Konfiguration, keine Messung der Rekordbox-Bildrate.
- `%APPDATA%\Pioneer\rekordbox6\rekordbox3.settings` enthält `RenderDelay=120`,
  `BasicOpenGL=0` und `DisableOpenGL=0`.
- Die installierte EXE und Erweiterungs-DLL entsprechen unverändert dem
  zuvor installierten BPM-/Dropdown-Patch:
  - EXE: `297ab491ae745191b09ee72612be6d4c61075788740fb62140f93b0628337a4f`
  - DLL: `5175314bf0b0f9dc0c07637577bca080625c660f60ac8fd2cf5809f1c812de0d`

## Statische Anhaltspunkte im konkreten Binary

Adressen sind RVAs, keine absoluten Laufzeitadressen. Zuordnungen stammen aus
Disassembly und erhaltenem MSVC-RTTI, nicht aus Herstellersymbolen.

| RVA | Befund |
| --- | --- |
| `0x5bcf678` | RTTI `ViewWaveformDrawRateComponent` |
| `0x39ec008` | Listener-VTable; Callback bei `0x1c966b0` |
| `0x1c966b0` | Auswahlhandler setzt je nach Zweig 120 bzw. 40 über `0x1cda120`; schaltet zusätzlich eine boolesche Option |
| `0x1cda090` / `0x1cda120` | Lesen/Schreiben des Einstellungswerts mit String-ID `0x5e35640` |
| `0xb2f650` | Initialisiert diese String-ID mit `RenderDelay` |
| `0x39ff478` | Vorgabewert 120 |
| `0x1746e50` | Liest `RenderDelay`, begrenzt auf 60 und berechnet ganzzahlig `1000 / Rate`; alternativer Zweig verwendet 30 |
| `0x1915f40` | Weiterer Verbraucher mit Begrenzung auf 60 und `1000 / Rate` |
| `0x1d578a0` | OpenGL-Zeichenpfad der RTTI-Klasse `djplay::OpenGLRenderComponentImpl` |
| `0xfca970` / `0xfca980` | Setter/Getter eines Verzögerungsfeldes in `rb::OpenGLCachedImageDelay` |
| `0xfbe3d0` / `0xfc9940` | Referenzieren `wglSwapIntervalEXT` |

Der Aufruf von `0x1746e50` kommt über `0x24ec3b0` und den MainComponent-Zugriff
`0x173e0e0`. Der erste Pfad gehört zur Hauptoberfläche; der zweite liegt im
VideoPanel-Codebereich. **Diese 60er-Grenzen sind kein belegtes 60-FPS-Limit der
Waveforms.** Die OpenGL-Waveform-Ausgabe muss getrennt verfolgt werden.

Die beobachtete ganzzahlige Millisekundenrechnung ist außerdem kein präziser
120-Hz-Takt: `1000 / 120` ergibt dabei 8 ms, rechnerisch 125 Hz vor weiteren
Begrenzungen. Echte 120 Hz erfordern im Mittel 8,333 ms und passende Darstellung
über VSync/Frame-Pacing.

## Einordnung externer Quellen

- Das [Rekordbox-7-Handbuch, Seite 226](https://cdn.rekordbox.com/files/20260409151936/rekordbox7.214_manual_EN.pdf)
  dokumentiert Waveform Drawing Rate und den höheren Rechenaufwand bei höherer
  Zeichenrate, nennt dort aber keine garantierten 120 FPS.
- Der [Smooth Mixer Patcher](https://github.com/SebitosMixx/rekordbox-smooth-mixer-patcher)
  beschreibt veränderbare UI-Begrenzungen und einen 120-FPS-Preset für 7.2.18.
  Sein Ziel sind Mixer-/UI-Updates; laut Autor können OpenGL-Waveforms bereits
  unabhängig davon flüssiger laufen. Das ist ein Hinweis auf die getrennten
  Pfade, kein Nachweis für 120-Hz-Waveforms auf diesem Rechner. Nicht ausgeführt.
- Die [JUCE-OpenGL-Schnittstelle](https://github.com/juce-framework/JUCE/blob/master/modules/juce_opengl/opengl/juce_OpenGLContext.h)
  unterscheidet kontinuierliches Zeichnen, angeforderte Repaints und Swap-Intervall.
  Diese Unterscheidung ist für die weitere Untersuchung relevant; das Verhalten
  dieser aktuellen Bibliotheksquelle ist nicht automatisch das des eingebauten
  Rekordbox-Forks.

## Vor einer späteren Umsetzung offen

1. Tatsächliche Frame-Zeitpunkte mit laufenden Waveforms aufzeichnen; zwischen
   neuen Waveform-Inhalten und wiederholter Ausgabe desselben Bildes unterscheiden.
2. Den aktiven Waveform-Renderthread, seinen Scheduler und sein Swap-Intervall
   dem konkreten Call-Pfad zuordnen. Erst dann den passenden Eingriff auswählen.
3. Prüfen, ob 120 FPS bereits erreichbar sind oder welche Begrenzung sie verhindert.
4. Falls nötig, einen versionsgebundenen Eingriff in die vorhandene Erweiterung
   integrieren und eine Auswahl unter RB PLUS ergänzen; Frame-Pacing und
   Audio-Stabilität mit mehreren Decks überprüfen.

Es wurde noch kein Waveform-Hook implementiert und kein 120-Hz-Erfolg behauptet.
