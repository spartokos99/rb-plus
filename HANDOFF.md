# RB PLUS – Übergabe

Stand: 22.09.2026. Repository: https://github.com/spartokos99/rb-plus (privat).

## Was funktioniert

Permanenter Windows-x64-Patch für **Rekordbox 7.2.18.0311**. Die gepatchte EXE
lädt `rb_bpm_patch.dll` beim normalen Start. Kein PowerShell-Fenster oder externer
Prozess muss beim Spielen offen bleiben. Einstellung unter
**Preferences → Extensions → RB PLUS → BPM / Tempo Step**: Default / 0.1 / 1.
Gespeichert in `rb-bpm.ini` neben der Installation.

Quantisiert wird der relative Basis-Pitch im zentral untersuchten
`StretchBehavior`-Setter. Die Engine erhält die resultierende Rate; analysierte
BPM, Grid und Datenbank bleiben unverändert. Hysterese: halbe Stufe + 10 % der
Stufenbreite. Die tatsächlichen Zahlen sind native Floats, nicht exakt darstellbare
Dezimalzahlen. Bereits erfasste Decks werden bei einer Setting-Änderung neu angewendet.

Die letzte Fehlerkorrektur betrifft das native Dropdown: JUCE brach Mausklicks
auf dessen separates Popup ab. Ein nur auf dieses Popup begrenzter GUI-Thread-
Hook reicht die Mausnachrichten weiter. Alle drei Modi per echter Maus und
Keyboard, Escape/Außenklick sowie drei weitere Dialogzyklen wurden geprüft.

## Zuständigkeit der Dateien

| Datei | Zweck |
| --- | --- |
| `native/quantizer.h` | Quantisierung und Hysterese ohne Rekordbox-Abhängigkeit |
| `native/tempo_hook.cpp` | Aktuell exakt an 7.2.18 gebundener Native-Backend, ABI/Offsets/VTable-Hook |
| `native/tempo_extension.cpp` | Autostart, INI, Setting, Neuanwendung auf GUI-Thread |
| `native/preferences_tabs.h` | Extensions-Tab-Leiste, RB PLUS, UIA-MTA-Worker |
| `native/preferences_combo.h` | Echte Mausbedienung des eigenen Dropdown-Popups |
| `tools/pe_startup_patch.py` | PE-Import/Entry-Point-Ergänzung ohne Verschieben alter RVAs |
| `tools/patch_app.py` | Paketvorbereitung, Installation, DLL-Update, Rückbau |
| `tools/observe_tempo.py` | Nur lesender Prozess-/Audio-Rate-Beobachter; derzeit 7.2.18 gebunden |
| `tools/tempo_control.py` | Explizite Diagnose-Steuerung, Exporte und Telemetrie |
| `compatibility/builds.json` | Additives Register bekannter, exakt identifizierter Builds |
| `Test-RekordboxCompatibility.ps1` | Nur lesender Einstieg für einen neuen Installationspfad |

Die `.sln` ist eine navigierbare Quellcode-Solution; gebaut wird mit den CMD-Skripten.
`native/ui_input_probe.cpp` ist optionale Diagnose, kein Bestandteil der installierten
Erweiterung. Die alten Runtime-Controls und `verify_live.py` sind nicht der normale
Startweg des permanenten Patches; `verify_live.py` erwartet den Diagnose-Hook,
genau einen laufenden Deck-1-Track mit Original-BPM 174 und verändert dessen Tempo.

## Bekannter Host / lokaler Stand

- Build: 7.2.18.0311, x64; Original-SHA und gepatchter SHA im Register.
- Historischer lokaler Installationspfad: `D:\Programs\rekordbox 7.2.18`.
- Original-Sicherung: `rekordbox.exe.rb-bpm-original`, niemals ungeprüft ersetzen.
- Zuletzt installierte DLL-SHA:
  `5175314bf0b0f9dc0c07637577bca080625c660f60ac8fd2cf5809f1c812de0d`.
- Zuletzt bewusst wiederhergestelltes Setting: 0.1 BPM. Aktuellen Zustand immer
  neu lesen; PIDs, Fensterhandles und Player-Adressen aus alten Logs nicht wiederverwenden.
- Der Patch entfernt die Authenticode-Signatur des geänderten PE; keine Signatur-
  oder Lizenzprüfung wird umgangen. Rückbau stellt das geprüfte Original wieder her.

## Neue Rekordbox-Version

Der Benutzer möchte künftig nur den neuen Installationspfad nennen müssen.
Folge dann **`AGENTS.md` → `compatibility/README.md`** vollständig. Vorherige
getestete Versionen müssen weiter funktionieren. Der Checker ist bereits
registerbasiert; Installer und Native-/Diagnose-Backend unterstützen heute nur
7.2.18. Vor Freigabe einer zweiten Version ist deren additive Auswahl umzusetzen.
Ein neuer Registereintrag allein erweitert den Hook **nicht**.

Einfacher Einstieg:

```powershell
.\Test-RekordboxCompatibility.ps1 -Path 'D:\Programs\rekordbox NEU'
```

## Bekannte Grenzen / nicht als bestanden ausgeben

DDJ-1000 war nicht angeschlossen. DVS/CDJ-800, Sync, mehrere gleichzeitig geladene
Decks, Trackwechsel, Export-/Performance-Wechsel und Langzeitlast sind noch nicht
vollständig validiert. UiPlayer allein beweist den globalen Performance-Modus
nicht lückenlos; vor einem Wechsel aus Performance Default wählen.
Jog-Bend, Scratch, Reverse und Start-/Bremsrampen sind zusätzliche Ratenpfade.
Dynamische Beatgrids werden bei Tempoaufrufen ausgewertet, nicht bei jedem
Positionswechsel. Englischer Preferences-Dialog bei 96 DPI war die UI-Testbasis.

Die Waveform-/120-Hz-Untersuchung wurde **abgebrochen auf Wunsch des Benutzers**.
`docs/waveforms-120hz-feasibility.md` ist nur ein historischer Befund; kein Auftrag,
keine implementierte Funktion, kein nächster Arbeitsschritt.

Details: `compatibility/reports/7.2.18.0311-windows-x64.md` und
`docs/investigation-7.2.18.md`. Rohlogs/Screenshots/Dumps sind lokal in `artifacts/`
und absichtlich nicht Teil des Repositories. Fehlende Rohdaten nicht als neue
erfolgreiche Prüfung darstellen.
