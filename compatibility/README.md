# Versionspflege ohne Verlust älterer Unterstützung

Der Auftrag „Neue Rekordbox-Version unter <Pfad>, bitte kompatibel machen“
umfasst Erkennung, Untersuchung, gegebenenfalls Anpassung, Tests und eine
aktualisierte Übergabe. **Neue Versionen werden zusätzlich unterstützt.**

## Aktuell geprüfte Builds

| Build | Plattform | Stand | Nachweis |
| --- | --- | --- | --- |
| 7.2.18.0311 | Windows x64 | Unterstützt mit dokumentierten Grenzen | [Bericht](reports/7.2.18.0311-windows-x64.md) |

`builds.json` ist das maschinenlesbare Register. Produktnamen wie „7.2.18“ reichen
nicht: exakter SHA-256, Architektur und geprüfte Code-Stellen gehören zur
Identität. Unbekannte Dateien werden abgelehnt, auch bei gleicher Versionsanzeige.

## 1. Nur lesende Erstprüfung

```powershell
.\Test-RekordboxCompatibility.ps1 -Path 'D:\Programs\rekordbox NEU'
# Alternativ:
python tools/check_compatibility.py --path 'D:\Programs\rekordbox NEU\rekordbox.exe'
```

Der Checker startet Rekordbox nicht und schreibt weder Dateien noch Prozessspeicher.
Exit 0 = bekannter Build mit passenden statischen Merkmalen; Exit 2 = unbekannt,
inkonsistent oder nicht lesbar. Bei einer gepatchten Installation werden Manifest,
Original-Sicherung und DLL-Integrität zusätzlich geprüft. Eine neu kompilierte DLL
kann zum Manifest passen, ohne eine historisch getestete DLL zu sein: das separate
Feld `extension_tested_release` beachten. `runtime_tested_this_run` ist immer false.

Ein erfolgreicher Check ist **keine** automatische Freigabe neuer Versionen und
kein Audio-/Hardwaretest. Wenn der Build unbekannt ist, Analyse mit
`tools/inspect_binary.py --exe <EXE>` durchführen; den alten Native-Hook nicht laden.

## 2. Baselines erhalten

- Vor Änderungen bisherige Profile und Quellstand sichern/taggen. Der erste
  Stand trägt `rb-plus-7.2.18.0311-baseline`.
- Legale lokale Original-EXEs/Testkopien je Build unter `fixtures/<build-id>/`
  aufbewahren; Hash prüfen. Dieses Verzeichnis wird nicht eingecheckt.
- Neue Offsets, ABI und Layouts als zusätzlichen Backend/Adapter aufnehmen.
  Gemeinsame Quantisierung und UI nur ändern, wenn die alten Backends weiterhin
  passen oder gezielt getrennte Implementierungen erhalten.
- Vor Aufnahme des zweiten Builds: Native- und Python-Backend-Auswahl sowie
  Installer auf exakte Build-Zuordnung erweitern. Heutige Hardcodierungen in
  `tempo_hook.cpp`, `tempo_extension.cpp`, `observe_tempo.py`, `tempo_control.py`
  und `patch_app.py` dabei nicht einfach auf den neuen Build umstellen.
- Pakete ab dann unter `build/packages/<build-id>/` isolieren und Installer mit
  passendem Profil/Paket aufrufen. Das aktuelle `build/permanent` ist ausschließlich
  der Legacy-Paketpfad für 7.2.18. Nie ein neues Paket als das alte ausgeben.
- Alte Profile, Backend-Quellen und Testfälle bleiben auf dem aktuellen Branch.
  Ein Git-Tag allein ersetzt keine weiterhin funktionierende Versionsauswahl.

## 3. Neue Pipeline vor Eingriffen belegen

Den zentralen Tempo-Sollwertpfad bis zur Audio-Rate nachvollziehen. Erneut prüfen:
Signaturen, VTable-Slot, Calling Convention, relative Pitch-Darstellung,
Track-/Grid-Zugriff, Grenzwerte, Threads und Request-Funktion für Neuanwendung.
Kein bloßes Verschieben alter RVAs um einen geratenen Offset.

Natives Setting und Eingabewege separat prüfen. UIA-Namen, Kategorien, Handles,
COM-Verhalten und Popup-Eingaben können sich unabhängig von der Audio-Engine ändern.
Profile erst nach Belegen und Tests freigeben; reine Kandidaten bleiben im Bericht.

## 4. Verbindliche Prüfmatrix

Für jeden neuen Build und als Regression für **jeden** schon unterstützten Build:

| Bereich | Prüfung / Erfolgskriterium |
| --- | --- |
| Identität | Unverändertes Original, exakter Hash/Architektur; fremde Builds abgelehnt |
| Offline | Python-Tests, Quantisierung/Hysterese, `/W4 /WX` Native-Builds |
| PE/Paket | Probe an lokaler Kopie: vorbereiten, installieren, wiederholen, DLL-Update, Rückbau mit Original-SHA; INI/Backup erhalten |
| Autostart | Regulärer Start lädt genau eine passende Erweiterung, kein Hilfsprozess nötig |
| Engine | Default bleibt unverändert; Integer und Zehntel mit Original-BPM 174 oder dokumentiertem anderem Track; Audio-Part-Rate messen |
| Grenzen/Hysterese | Langsamer Sweep, Schwellenrauschen, Sprünge, Min/Max; keine unerwarteten Zwischenwerte |
| Live-Umschalten | Bereits erfasstes Deck übernimmt neuen Modus ohne nächste Faderbewegung |
| Metadaten | Original-/Grid-BPM unverändert; keine Schreibpfade zu Analyse/Datenbank hinzufügen |
| Eingaben | GUI-Fader, manuelle BPM, DDJ-1000 und sonstige verfügbare Hardware; jeweils Beleg oder explizit ungetestet |
| UI | Extensions → RB PLUS, alle Modi mit echten Mausklicks und Tastatur, Escape/Außenklick, ursprüngliche Tabs, Kategorie-Wechsel |
| Lebensdauer | Mehrfach Preferences schließen/öffnen, Neustart mit gespeichertem Modus, keine zusätzlichen Hooks/Crashes |
| Weitere Pfade | Mehrere Decks, Track-/Moduswechsel, Sync/DVS, Bend/Scratch/Reverse; offene Grenzen separat führen |
| Last | CPU/GUI-Reaktion und Audio-Stabilität während eines dokumentierten längeren Tests |

Nur wirklich durchgeführte Prüfungen als bestanden melden. Fehlen historische
Installationen/Hardware, die unabhängigen Arbeiten erledigen und die fehlende
Regression konkret ausweisen. Nicht die bisherige Unterstützung löschen, um eine
Prüflücke zu umgehen. Keinen laufenden Auftritt für einen Test unterbrechen.

`tools/verify_live.py` steuert den alten Diagnose-Hook und benötigt spezielle
Vorbedingungen (HANDOFF). Für einen neuen permanenten Backend muss dieser Testweg
angepasst oder ein entsprechender Integrationstest ergänzt werden; nicht beide
Hooks gleichzeitig installieren. Die Mausprüfer bewegen den echten Cursor und
ändern das Setting; nur im geeigneten Testzustand einsetzen.

## 5. Abschluss

- Pro Build `compatibility/reports/<build-id>.md` mit Datum, Original-/Patch-/DLL-
  Hashes, Belegen, Prüfergebnissen und weiterhin offenen Punkten führen.
- `builds.json`, diese Matrix, README und HANDOFF additiv aktualisieren.
- Neue und alte Pakete unterscheidbar, reproduzierbar und gemeinsam nutzbar halten.
- Ergebnis an den Benutzer: neue Version, alte erhaltene Versionen, tatsächlich
  wiederholte Tests, konkrete Grenzen. Hardware-Coverage nicht pauschal zusagen.
- Quellcode/Prüfberichte einchecken; keine Rekordbox-EXEs, Datenbanken oder Dumps
  in Git oder GitHub-Releases hochladen. Eigene Release-DLLs nur gesondert, wenn
  tatsächlich als Release beauftragt und pro Build geprüft.
