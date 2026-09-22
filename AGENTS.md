# RB PLUS: Arbeitsanweisungen für Coding-Agents

## Einstieg

Lies zuerst `HANDOFF.md`, dann `compatibility/README.md`. Dieses private Repo
enthält unseren Quellcode; Rekordbox-Binaries, Musik, Datenbanken, Dumps und
lokale Messdaten gehören nicht ins Git. Der Build verwendet die Skripte unter
`native/`; die Solution dient der Navigation.

## Produkt und Grenzen

- Windows x64, Zusatzseite **Preferences → Extensions → RB PLUS**.
- Default, 0.1 BPM und 1 BPM quantisieren ausschließlich den Live-Basis-Tempo-
  Sollwert der Performance-Decks. Audio-Rate prüfen, nicht nur Displaytexte.
- Keine Änderungen an Track-BPM, Metadaten, Beatgrid oder Datenbank.
- Herstellerlizenzen/Abonnements und ihre Prüfungen sind nicht Teil dieses Projekts.
- Die Waveform-/120-Hz-Idee wurde vom Benutzer ausdrücklich verworfen. Nicht
  wieder aufnehmen, sofern der Benutzer sie nicht neu beauftragt.
- Bekannte Grenzen und ungetestete Hardware in README und Versionsbericht
  ehrlich erhalten. Ein bekannter EXE-Hash ist kein vollständiger Laufzeittest.

## Wenn der Benutzer eine neue Rekordbox-Version nennt

Eine Anweisung wie „Ich habe eine neue Version unter <Pfad> installiert,
stelle sicher, dass sie mit unserem Patch kompatibel ist“ aktiviert den
vollständigen Ablauf in `compatibility/README.md`. Der Benutzer muss weder alte
Erkenntnisse wiederholen noch die einzelnen Prüfungen aufzählen.

1. Zuerst den angegebenen Pfad mit `Test-RekordboxCompatibility.ps1` nur lesend
   prüfen und den exakten Build identifizieren. Unbekannte Builds nicht mit den
   bisherigen Adressen injizieren oder patchen.
2. Vor Implementierung den Tempo-/Playback-Pfad der neuen Version untersuchen.
   Vorhandene Signaturen sind Hinweise; ABI, Objektoffsets, VTables, Threading,
   Grid-Zugriff und Neuanwendung müssen belegt sein.
3. Unterstützung **additiv** ergänzen. Alte Einträge in `compatibility/builds.json`
   und alte funktionsfähige Backends nicht durch neue Offsets ersetzen. Vor dem
   zweiten unterstützten Build die heute noch fest gebundenen Native-/Python-
   Backends getrennt auswählbar machen (exakte Hash-Zuordnung, kein Fallback auf
   die „neueste“ Version). Getrennte Pakete je Build; niemals ein globales
   `EXPECTED` auf den neuen Build umschreiben und damit alte Builds ausschließen.
4. Neue und alle bisher unterstützten Versionen nach der Prüfmatrix testen.
   Historische Ergebnisse getrennt von aktuell wiederholten Tests ausweisen.
   Fehlt eine alte lokale EXE oder Hardware, Arbeit fortsetzen und die konkret
   fehlende Prüfung melden; keine Regression als bestanden erfinden.
5. Erst nach passender statischer Prüfung Runtime-Tests/Installation durchführen.
   Vor Neustarts Wiedergabezustand prüfen; laufende Sets nicht unterbrechen.
   Regulär schließen, nie blind Prozesse abschießen. Backups und INI erhalten.
6. Profil, Bericht, Matrix, HANDOFF und README aktualisieren. Den neuen Stand
   erst als unterstützt ausweisen, wenn die dort verlangten Kriterien erfüllt
   sind; offene Einschränkungen benennen. Frühere Unterstützung beibehalten.

Routineanalysen, lokale Builds, Korrekturen und Tests sind Teil dieses Auftrags.
Keine wiederholten Bestätigungen verlangen, wenn die Sitzung diese Arbeiten
bereits autorisiert. Fehlende Testdaten/Hardware sind konkrete Rückfragen, keine
pauschale neue Freigabestufe. GitHub-Pushs erfolgen nur im autorisierten Umfang.

## Laufzeit- und UI-Regeln

- Keine globalen Eingabe-Hooks. Die Dropdown-Korrektur ist ausschließlich auf
  das eigene Popup und den GUI-Thread begrenzt.
- UI-Automation auf dem MTA-Worker halten; GUI-Arbeit auf dem GUI-Thread.
- COM-Erfolg **und** nicht-null Interface prüfen. JUCE kann bei verschwundenen
  Controls `S_OK` mit null liefern (bereits durch Crash-Dump belegt).
- Keine langlebigen UIA-Button-Caches: Kategorien erzeugen neue Controls.
- UI mit echten Mausklicks testen. `CB_SETCURSEL` plus `WM_COMMAND` hat den
  ursprünglichen Popup-Fehler verdeckt. Auch Keyboard, Escape, Außenklick und
  Schließen/Öffnen testen. Cursorposition danach wiederherstellen.
- Keine Frida-Instrumentierung erneut einsetzen: frühere Probe verursachte
  einen Rekordbox-Absturz. Bevorzugt statische Analyse und lesender Beobachter.
- Native DLL bleibt während der Prozesslebensdauer geladen; kein unsicheres
  Entladen eines Hooks, der noch aus einem anderen Thread erreichbar ist.

## Prüfungen und Übergabe

Für Änderungen an Build-/Kompatibilitätswerkzeugen: `python -m unittest discover
-s tests -v`, `native\build.cmd`, `native\build-extension.cmd rb_bpm_patch`.
Für Host-/Engine-/UI-Änderungen zusätzlich die betroffenen Integrationstests aus
der Matrix. Nicht wahllos laufende Decks mit den Diagnosehelfern verändern.

Vor einem Commit `git diff --cached` und die Dateiliste auf generierte Binaries,
private Daten, Zugangsdaten und große Artefakte prüfen. Keine Herstellerdateien
mit `git add -f` aufnehmen. Die bestehende Hersteller-Sicherung nie überschreiben.
