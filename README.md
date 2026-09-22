# RB PLUS — Live-Tempo-Schritte für Rekordbox

**Der dauerhafte Windows-x64-Patch ist implementiert und lokal installiert.**
Rekordbox lädt die Erweiterung bei jedem normalen Start selbst. Unter
**Preferences / Einstellungen → Extensions → RB PLUS** steht
**BPM / Tempo Step** zur Auswahl:

- **Default / 0.01 BPM:** unveränderte native Tempoauflösung.
- **0.1 BPM:** Zehntel-BPM.
- **1 BPM (integer):** ganze BPM.

Die Auswahl wird gespeichert und beim nächsten Start übernommen. Bei bereits
erfassten, geladenen Decks wird der letzte Tempo-Sollwert beim Umschalten sofort
neu angewendet. Neue Decks werden beim ersten gültigen Tempoaufruf erfasst.
**Kein externes Tool muss beim Spielen laufen.** Python und die PowerShell-
Werkzeuge werden nur für Installation, Rückbau und optionale Diagnosen gebraucht.

Der experimentelle Patch quantisiert den **Basis-Tempo-Sollwert vor der
Audioverarbeitung**. Er schreibt keine Track-BPM, Beatgrids, Metadaten oder
Rekordbox-Datenbankwerte.

## Neue Rekordbox-Versionen

Künftig genügt als Auftrag an den Coding-Agent:

> Ich habe eine neue Version von Rekordbox unter `<Pfad>` installiert.
> Stelle sicher, dass sie mit unserem Tool/Patch kompatibel ist und alle
> bisher unterstützten Versionen weiterhin funktionieren.

[AGENTS.md](AGENTS.md) und [HANDOFF.md](HANDOFF.md) legen den Ablauf fest.
Das [Build-Register und die Prüfmatrix](compatibility/README.md) erhalten alte
Versionen und dokumentieren Ergebnisse pro Build. Aktuell ist ausschließlich
**7.2.18.0311 / Windows x64** unterstützt; neue Versionen werden untersucht und
additiv aufgenommen, nicht ungeprüft über einen Versionsnamen freigeschaltet.

Für die erste, ausschließlich lesende Prüfung:

~~~powershell
.\Test-RekordboxCompatibility.ps1 -Path 'D:\Programs\rekordbox NEU'
~~~

Der Check ersetzt keine Live-/Hardwaretests. Unbekannte Builds werden abgelehnt.
Die Native-/Diagnose-Backends sind derzeit an 7.2.18 gebunden; vor Freigabe eines
zweiten Builds muss die versionsabhängige Auswahl zusätzlich implementiert werden.

## Aus einem frischen Checkout bauen

Benötigt: Windows x64, Python x64 (lokal mit 3.13 getestet), Visual Studio C++-
Buildtools einschließlich Windows SDK sowie eine eigene passende Rekordbox-Installation.
Keine Hersteller-Binaries, Musik, Datenbanken, Dumps oder lokalen Pakete liegen im Git.
Die Solution gruppiert die Quelldateien; die Build-Skripte erzeugen die DLLs.

~~~powershell
python -m pip install --target .tools/python -r requirements-analysis.txt
python -m unittest discover -s tests -v
.\native\build.cmd
.\native\build-extension.cmd rb_bpm_patch
python tools/patch_app.py prepare --exe '<ungepatchte Arbeitskopie>\rekordbox.exe'
~~~

Die Analyse-Abhängigkeiten sind nur für PE-Inspektion/Disassembly nötig. Der
Kompatibilitätscheck und Installer verwenden die Python-Standardbibliothek.
MSVC wird über `vswhere` erkannt; alternativ eine x64 Developer Shell verwenden
oder `RBQ_VCVARS` auf die passende `vcvars64.bat` setzen. Ergebnisse liegen in
`build/`, lokale Nachweise in `artifacts/`; beides bleibt außerhalb von Git.

Zusätzlicher Dateipaket-Test mit einer eigenen Originaldatei (nur temporäre Kopien):

~~~powershell
$env:RBQ_TEST_ORIGINAL='<Original oder geprüftes Backup>'
python -m unittest discover -s tests -v
Remove-Item Env:RBQ_TEST_ORIGINAL
~~~

## Installation und Rückbau

Unterstützt wird exakt der untersuchte Windows-x64-Build **7.2.18.0311**.
Die Installation unter D:\Programs\rekordbox 7.2.18 ist bereits gepatcht.
Für eine erneute Installation des vorbereiteten Pakets Rekordbox beenden:

~~~powershell
.\Patch-Rekordbox.ps1 -Action Install
~~~

Danach Rekordbox normal starten. Neben der geänderten EXE liegen rb_bpm_patch.dll,
rb-bpm.ini und rb-bpm.patch.json. Die geprüfte Originaldatei wird als
**rekordbox.exe.rb-bpm-original** gesichert. Wiederholte Installation erkennt
den vorhandenen Patch; eine vorhandene INI bleibt erhalten. Bei einer neueren
Erweiterungs-DLL für dieselbe gepatchte EXE werden nur DLL und Manifest
aktualisiert; installierte DLL und Original-Backup werden zuvor geprüft.

Zum vollständigen Rückbau Rekordbox beenden:

~~~powershell
.\Patch-Rekordbox.ps1 -Action Restore
~~~

Der Rückbau stellt die Original-EXE bytegenau wieder her und entfernt die
passende DLL. Backup und Einstellung bleiben erhalten. Zwischenzeitlich
veränderte oder aktualisierte EXEs werden nicht überschrieben. Die DLL
nicht einzeln löschen, solange die EXE gepatcht ist: Windows benötigt sie
zum Start der Anwendung.

Der Dateipatch macht die ursprüngliche Herstellersignatur ungültig.
Rekordbox-Updates können ihn ersetzen; andere Builds benötigen eine neue
Untersuchung und werden von diesem Installer nicht akzeptiert.

## Prüfergebnisse

Deck 1, ursprüngliche BPM 174, laufender interner Audio-Rate-Zustand:

| Modus | Tempo-Eingabe | BPM aus der Audio-Part-Rate |
| --- | ---: | ---: |
| Default | 175.37 | 175.369995 |
| 1 BPM | 175.37 | 174.999992 |
| 0.1 BPM | 175.37 | 175.400009 |

Die Abweichungen entstehen durch die native Float-Repräsentation. Der Wechsel
von 1 auf 0.1 BPM im eingebetteten Einstellungsfeld änderte die Audio-Part-Rate
ohne neue Faderbewegung. Die Beatgrid-BPM blieb 174. Dies sind Messungen interner
Engine-Zustände, keine Aufnahme des Audioausgangs.

Bestanden: Quantisierungs-/Hysteresetests, zwölf Live-Testfälle, GUI-Fader-Sweep,
Windows-Start eines separat gepatchten Testprogramms, PE-Layout-Prüfungen und
Installation/Rückbau auf einer Dateikopie. Die installierte Rekordbox-EXE
wurde zweimal regulär gestartet: Hook und Einstellungsfeld erschienen
automatisch; die gespeicherte Auswahl **0.1 BPM** blieb erhalten.

Der Tab RB PLUS wurde anschließend ergänzt: Wechsel zu STEMS, Video, Lighting,
Audio und View, alle drei Einstellungswerte und fünfmaliges Schließen/Öffnen
bestanden. Eine dabei gefundene fehlende Nullprüfung bei der UI-Abfrage ist
in der installierten Fassung korrigiert; Details im Bericht.

Die Mausauswahl im Dropdown ist ebenfalls korrigiert. Alle drei Optionen wurden
mit echten Mausklicks gegen den aktiven Modus und die gespeicherte INI geprüft;
Tastaturbedienung sowie Abbruch mit Escape und Außenklick funktionieren ebenfalls.

Details und Evidenz: [Untersuchungsbericht](docs/investigation-7.2.18.md).

## Grenzen

- **DDJ-1000 noch nicht getestet:** Das Gerät war nicht angeschlossen. Der Hook
  sitzt am gemeinsamen Setter hinter den Tempo-Eingaben; tatsächliche
  Hardware-Abdeckung muss mit angeschlossenem Controller bestätigt werden.
- Sync, DVS/CDJ-800, mehrere geladene Decks, Trackwechsel und Export-/Performance-
  Wechsel sind noch nicht vollständig geprüft. Der UiPlayer-Typcheck erkennt
  den globalen Performance-Modus nicht lückenlos. **Vor einem Wechsel aus
  Performance Default auswählen.**
- Jog-Bend, Scratch, Reverse und Anlauf-/Bremsrampen bleiben zusätzliche Ratenpfade.
  Es wird der Basis-Sollwert quantisiert, nicht jede momentane Rate dieser Funktionen.
- Hysterese: halbe Stufe plus 10 % der Stufenbreite. Bei 1 BPM bleibt 175 bis
  ungefähr 175.60 erhalten; rückwärts bleibt 176 bis ungefähr 175.40 erhalten.
  Kleine relative Plus-/Minus-Eingaben können auf dieselbe Stufe zurückfallen.
- Bei dynamischen Beatgrids wird die lokale BPM bei Tempoaufrufen gelesen;
  Positionsänderungen allein lösen keine neue Quantisierung aus.
- Höchstens acht Player-Adressen pro Sitzung. Ungültige, unbekannte oder
  konkurrierende Kontexte passieren unverändert und werden diagnostisch gezählt.
  Langzeittests stehen aus.
- Tab-Leiste und RB-PLUS-Seite sind native Windows-Elemente innerhalb des
  Rekordbox-Dialogs, keine offizielle Herstellererweiterung. Die bisherigen
  Extensions-Tabs leiten an ihre bestehenden Seiten weiter. Getestet ist der
  lokale englische Dialog bei 96 DPI. UI-Abfragen erfolgen auf einem getrennten
  Thread innerhalb Rekordbox und nur bei sichtbaren Einstellungen.

## Diagnose und Quellcode

Die INI neben der EXE enthält:

~~~ini
[Tempo]
Step=0.1
~~~

Gültig sind default, 0.1 und 1. Manuelle Dateiänderungen werden beim nächsten
Start gelesen; während der Laufzeit das Einstellungsfeld verwenden.

~~~powershell
.\Set-TempoStep.ps1 -Step Status
.\Observe-Tempo.ps1 -Seconds 30
~~~

Der Beobachter injiziert nichts und schreibt keinen Prozessspeicher. Logs liegen
unter artifacts/. owner bezeichnet eine Adresse, keine Decknummer; grid_bpm
ist die lokale Beatgrid-BPM. Die Snapshots sind nicht atomar.

Start-Control.cmd und Set-TempoStep.ps1 bleiben optionale Diagnosebedienungen.
Beim permanenten Patch speichern Modusänderungen ebenfalls die Auswahl.
Stop ist dort gesperrt: zum Abschalten Default, zum Entfernen den Rückbau nutzen.
Für externe Modusänderungen den Preferences-Dialog schließen: Solange der
modale Dialog offen ist, stellt Rekordbox seine Performance-Anzeige nicht
zuverlässig für die UI-Automation bereit. Das eingebettete Feld funktioniert
direkt im geöffneten Dialog.

~~~powershell
.\native\build.cmd                          # Tests + älterer Runtime-Hook
.\native\build-extension.cmd rb_bpm_patch   # dauerhafte Erweiterung
python tools/patch_app.py prepare --exe 'D:\Programs\rekordbox 7.2.18\rekordbox.exe'
~~~

prepare benötigt eine **ungepatchte** Originaldatei namens rekordbox.exe.
Bei installiertem Patch eine Arbeitskopie des geprüften Backups unter diesem
Namen verwenden. Das aktuelle 7.2.18-Paket entsteht in build/permanent.
Die Build-Skripte erkennen MSVC automatisch; Details oben.

Implementierung: native/tempo_hook.cpp (Setter), native/tempo_extension.cpp
(Start, Einstellungsfeld, Speichern und Neuanwendung), native/preferences_tabs.h
(Extensions und RB PLUS), tools/pe_startup_patch.py
(PE-Patch), tools/patch_app.py (Installation/Rückbau).
Der ältere Test tools/verify_live.py benötigt den Runtime-Hook und verändert
ausdrücklich das Deck-Tempo; er ist kein passiver Monitor.
