# Untersuchung vom 21.–22.09.2026

**Aktueller Stand:** Dauerhafter Dateipatch mit automatisch geladener nativer
Erweiterung und gespeichertem Einstellungsfeld in Preferences installiert.
Zwei reguläre Starts der gepatchten EXE und die Übernahme von 0.1 BPM sind
bestätigt. GUI-Tempo und interne Audio-Rate wurden live geprüft; Hardware und
weitere Betriebsarten bleiben offen. Die Abschnitte bis zum letzten Nachtrag
dokumentieren den historischen Stand; Aussagen über unveränderte Programmdateien
oder fehlende dauerhafte Settings gelten für diese früheren Untersuchungen.

## Exakte untersuchte Installation

- Datei: `D:\Programs\rekordbox 7.2.18\rekordbox.exe`
- FileVersion: `7.2.18.0`
- ProductVersion: `7.2.18.0311`
- Größe: 100561840 Bytes
- SHA-256: `a99896cf26d5998e6ad4177796a467b83df14bf8ae7207df21ed01251e402493`
- Architektur: Windows x64; bevorzugte ImageBase `0x140000000`.
- Alle folgenden Adressen sind **RVAs**, zu denen die aktuelle ASLR-Modulbasis
  addiert werden muss. Keine Versionsfreigabe für andere Builds mit gleichem Namen.
- MSVC-RTTI ist erhalten. Der eingebettete PDB-Pfad verweist auf einen
  Hersteller-Buildserver; lokale Quellzeilen/Debugsymbole standen nicht bereit.

Die EXE-Prüfsumme war nach der Untersuchung unverändert. Es wurden keine
Rekordbox-Programmdateien, Datenbanken, Beatgrids oder Metadaten gepatcht.

## Statisch belegter Kandidat und Datenweg

Die Namen werden aus MSVC-RTTI von Task-Klassen und deren VTables abgeleitet.
Dies sind rekonstruierte Zuordnungen, keine vom Hersteller veröffentlichte API.

| RVA | Zuordnung / beobachteter Code |
| --- | --- |
| `0x555c620` | VTable `rbxfrm::StretchBehavior`, Slot 9 führt zu `0x2c07bd0` |
| `0x555c748` | VTable `doSetBaseTempoRatioTask` aus `StretchBehavior::reqSetBaseTempoRatio` |
| `0x2c07e80` | Task-Ausführung: Owner aus `task+0x20`, float aus `task+0x28`; Sprung auf Owner-VTable `+0x48` |
| `0x2c07ef0` | Request-Funktion: begrenzt Wert auf `owner+0x11c/0x120`; reiht Task ein oder ruft VTable `+0x48` direkt auf |
| `0x2c07bd0` | Rekonstruierter `StretchBehavior::doSetBaseTempoRatio`-Setter; konsumiert `this` in RCX und float in XMM1. Ein früher vermutetes bool-Argument wird nicht gelesen. |
| `0x2c07de5` | Schreibt float aus XMM6 nach `[RBX+0xec]` |
| `0x2d94af0` | Ausführung von `DjSyncSlaveBehaveDispatcher::reqSetBaseTempoRatio`-Task |
| `0x2d949d0` | Dispatcher-Pfad, ruft bei erfüllten Bedingungen `0x2c07ef0` |
| `0x2e4a610` | Ausführung von `DjSyncMasterBehavior::reqSetBaseTempoRatio`-Task |
| `0x2e4a270` | Master-Pfad mit zusätzlichen Sync-/Beatgrid-Berechnungen; noch nicht bis zum Ende zur Laufzeit verifiziert |

Wichtig: Nur den Queue-Task zu hooken wäre unvollständig. Der Request-Code
enthält einen direkten Aufruf derselben virtuellen Funktion. Die Funktion
`0x2c07bd0` ist deshalb ein besserer **Kandidat** als die Task-Ausführung.

### Verbindung zur Rate-Verarbeitung

- `0x2c04b90` liest `StretchBehavior+0xec`, addiert `1.0f` und berücksichtigt
  die Wiedergaberichtung. Die Konstante bei RVA `0x5582880` ist `0000803f`.
- `0x2c050e0` kombiniert `1 + [owner+0xec]` mit einem separaten Wert aus
  `[owner+0xf0]`, unter Berücksichtigung der Richtung.
- Der Pfad um `0x2c04f67..0x2c05057` enthält zusätzliche Play-/Scratch-
  Bedingungen und ruft bei `0x2c0500e` die Funktion `0x2d80e60` auf.
- `0x2d80e60` erhält den Core über RCX und die Rate über XMM1, iteriert die
  Audioteile aus `core+0x2c0`, Liste `+0x68`, Anzahl `+0x74`, und übergibt die
  Rate an drei Unterobjekte pro Teil über deren VTable `+0x88`.
- Bei `0x2d80f6f` wird der übergebene Rate-Wert als double nach `part+0x30`
  geschrieben. Diesen Zustand kann der externe Beobachter lesen.

Damit ist der Kandidat statisch mit der Audio-Rate-Verarbeitung verbunden.
Eine ausschließlich visuelle BPM-Rundung wäre etwas anderes. Noch **nicht**
belegt sind die vollständige Coverage aller Eingabequellen und die tatsächlich
ausgegebene Audio-Geschwindigkeit bei einem quantisierten Wert.

### Korrekte numerische Interpretation

Der gespeicherte float ist eine relative Abweichung, kein Faktor mit Neutralwert 1:

```text
pitchDelta = 0.0 entspricht nominalRate = 1.0
targetBpm = originalBpm * (1.0 + pitchDelta)
quantizedBpm = round(targetBpm / step) * step
quantizedPitchDelta = quantizedBpm / originalBpm - 1.0
```

Diese Interpretation ist statisch aus der Addition und dem folgenden Datenweg
belegt. Die Original-BPM muss noch aus einem validierten Track-/Beatgrid-Kontext
bezogen werden. `core+0x218` ist nur ein Kandidatenfeld: der beobachtete Wert
120.0 an allen fünf Objekten ist **kein Nachweis** einer dort gespeicherten
Original-BPM. Diesen Wert ungeprüft zu verwenden wäre falsch.

## Laufzeitbeobachtungen und ihre Grenzen

Die temporären Frida-Probes wurden an den drei Task-Funktionen und später
`0x2c07bd0` installiert. Byte-Signaturen und EXE-Hash stimmten überein. In den
Messfenstern gab es keine protokollierte Tempoänderung. Daher existieren noch
kein Fader-Aufrufstack und kein Vorher/Nachher-Paar eines bekannten Tracks.

Eine ergänzende interne Speichersuche fand fünf `StretchBehavior`-Objekte mit
`DjPlayerCore`-VTable `0x556fb28`, lief jedoch in einen Timeout. Danach:

- Windows Application Error, Event 1000, 21.09.2026 20:24:03 lokale Systemzeit.
- Prozess: `rekordbox.exe`, PID 16088.
- Fehlermodul: `frida-agent.dll`, Exception `0xc0000409`, Offset `0xfa2f9d`.
- Bericht-ID: `85c2d054-3006-4e14-9ffb-5833353456f8`.
- Lokaler Dump: `C:\Users\Nico\AppData\Local\CrashDumps\rekordbox.exe.16088.dmp`.
- Der genaue Fehler innerhalb Frida wurde nicht untersucht. Aus den Daten lässt
  sich keine präzisere Ursache wie Stack-Overflow oder eine konkrete Race ableiten.

Diese Instrumentierung ist für das aktuelle Setup nicht ausreichend stabil.
Die Frida-Skripte wurden aus dem Projekt entfernt. Die Originalanwendung wurde
neu gestartet (PID 21800 zum Testzeitpunkt).

Der Ersatz `tools/observe_tempo.py` verwendet nur `OpenProcess` mit
`PROCESS_QUERY_INFORMATION | PROCESS_VM_READ`, `VirtualQueryEx`,
`ReadProcessMemory` und Modulabfragen. Kein WriteProcessMemory, keine DLL,
keine Remote-Threads, keine Funktionsaufrufe in Rekordbox.

Ergebnis der ersten externen Beobachtung:

- Fünf validierte Player-Objekte gefunden, Scan in ungefähr 4.2 Sekunden.
- Alle fünf: `pitch_delta = 0`, `bend_delta = 0`, nominale Rate `1.0`.
- Vier: `audio_part_rates = [0.0]`; ein Objekt: `[1.0]`.
- Alle fünf: unbestätigtes Kandidatenfeld `core+0x218 = 120.0`.
- Kein Nachweis, welches Objekt Deck 1..4 oder beispielsweise Preview darstellt.
- Anwendung reagierte nach Ende der Beobachtung weiterhin.

Validierung der bereitgestellten Werkzeuge: Python-Syntaxprüfung beider Skripte
und PowerShell-Parserprüfung bestanden. `Observe-Tempo.ps1 -Seconds 30` wurde
anschließend erfolgreich ausgeführt; die fünf Objekte wurden erneut gefunden,
die Beobachtung endete regulär, Rekordbox blieb ansprechbar. Die EXE-Prüfsumme
wurde nochmals unverändert bestätigt. Dies ist ein Leerlauf-/Diagnosetest,
kein Audio- oder Hardware-Nachweis.

Der Beobachter validiert Marker und VTables, liest aber keine atomare Momentaufnahme.
Objekt-Lebensdauer, Moduswechsel und kurze Übergänge sind weitere Grenzen.
Er kann die GUI-/Hardware-Korrelation untersuchen, aber kein lückenloses
"kein Zwischenwert gelangt zur Engine" beweisen.

## Ursprüngliche Prüfliste (Stand vor dem Prototyp)

1. Bekannter Track, Decknummer, Original-BPM; GUI- und DDJ-1000-Fader getrennt
   beobachten und denselben Core-/Stretch-Zustand zuordnen.
2. Original-BPM-/lokale Beatgrid-Tempo-Quelle, Trackwechsel und unbekannte BPM
   validieren. Ein dynamischer Beatgrid kann eine positionsabhängige Basis benötigen.
3. Performance-Decks gegen Preview, Export, Sampler und andere Player abgrenzen.
4. Sync-Master/-Slave und manuelle BPM-Eingabe separat durch den Pfad verfolgen.
5. Klären, ob CDJ-800 normale Audioquellen sind oder per DVS/Timecode steuern.
   Ein Software-Patch kann nur die Software-Wiedergabe beeinflussen. DVS kann
   zusätzliche Geschwindigkeits-/Scratch-Pfade benötigen.
6. Semantik für Pitch-Bend, Scratch, Reverse und Anlauf-/Bremsrampen festlegen.
   Quantisierung eines dauerhaften Tempo-Sollwerts allein verhindert diese
   absichtlichen transienten Änderungen der tatsächlichen Rate nicht.
7. Native Hook-Lösung mit minimalem Eingriff auswählen und stabil testen. Kein
   JavaScript-Logging, keine Allokationen, Dateizugriffe oder blockierende Locks
   im Audio-Callback eines späteren Produkts.
8. Hysterese pro Deck und pro Track, Reset bei Modus-/Trackwechsel sowie
   Quantisierung innerhalb erlaubter Rate-Grenzen implementieren. An einer
   Rundungsgrenze halten, bis die Grenze plus/minus Totband überschritten wird.
9. Float-Präzision berücksichtigen: ein mathematisch gewünschter BPM-Wert wird
   durch eine endliche Rate repräsentiert. Audio-Messung mit definierter Toleranz,
   GUI-Text und interner Sollwert müssen getrennt validiert werden.
10. Abschließender Test mit tatsächlichem Audio: Standardtempo, beide Schrittmodi,
    Grenzflattern, Fadersprünge, mehrere Decks, Sync, Master Tempo, Trackwechsel
    sowie Wiederherstellung des Default-Verhaltens.

## Hilfswerkzeuge und Quellen

Die primäre Evidenz stammt aus der **lokalen** EXE und den beschriebenen
Beobachtungen. Kein fremder Patch oder hartcodierter Offset wurde übernommen.

- [Hersteller-Release-Notes](https://rekordbox.com/en/support/releasenote/):
  bestätigen Version 7.2.18, enthalten aber keine interne Tempo-API.
- [Frida JavaScript API](https://frida.re/docs/javascript-api/): wurde für die
  verworfene temporäre Instrumentierung konsultiert.
- [RekordBoxSongExporter](https://github.com/Unreal-Dan/RekordBoxSongExporter):
  als verwandtes Beobachtungsprojekt recherchiert; daraus wurden keine
  Playback-Hook-Adressen oder Implementierungen übernommen.

`inspect_binary.py` nutzt Exception-Unwind-Einträge als Funktionsheuristik.
Diese können eine Funktion in mehrere Bereiche teilen; für die obigen Befunde
wurden zusammenhängende Codebereiche ausdrücklich vollständig gelesen.
Bei Leaf-Funktionen ohne Eintrag sind automatisch gewählte Grenzen ungenau.

## Laufzeitbestätigung und Prototyp vom 22.09.2026

Die folgenden Ergebnisse beziehen sich auf PID 21800 und sind nicht auf spätere
Speicheradressen übertragbar. Deck 1 war vom Nutzer mit einem 174-BPM-Track
vorbereitet; der DDJ-1000 war nicht angeschlossen.

### Live-Datenweg

1. `StretchBehavior` bei `0x1a9cb799a50` gehört zum vorbereiteten Deck 1;
   `owner+0x48` führt zu `DjPlayerCore` bei `0x1a9cb71c830`.
2. Das frühere GUI-Fader-Log `artifacts/deck1-174-gui.jsonl` enthält 129
   Zustandsänderungen dieses Owners zwischen ungefähr -0.06 und +0.06 Pitch-Delta.
   Andere beobachtete Owner blieben unverändert. Das Deck war dabei pausiert.
3. `core+0x220` führt zu `DjPlayerState` (VTable-RVA `0x55716a8`). Darin:
   `+0x10` Wiedergabe-Flag, `+0x14` Position in einer 44100er Zeitbasis,
   `+0x28` BeatGridHolder, `+0x30` Control-Client.
4. `BeatGridHolder+0x18` führt zum FormattedBeatGrid. Dessen `+0x18/+0x20`
   begrenzen einen Vektor mit 16-Byte-Einträgen: BPM als float bei +0,
   Position in Millisekunden als double bei +8. Der geladene Track enthielt
   909 Einträge mit 174.0 BPM.
5. Native Getter `0x1032900`, `0x1032830` und `0x1032930` bestätigen Layout
   und Zeitumrechnung. Die Konstante bei `0x5b52288` ist 1000/44100.
6. Der Control-Client gehört zu UiPlayer, aber zu einer **sekundären Basis**:
   VTable-RVA `0x3bb8068`, this-adjustment `0x410`. Die primäre UiPlayer-VTable
   `0x3bb7e70` wäre für diesen Pointer der falsche Typcheck.
7. `core+0x218` bleibt beim geladenen 174-BPM-Track 120.0. Dieses Feld ist
   ausdrücklich NICHT die Track-BPM-Quelle.
8. Play/Pause wurde über Rekordbox-UI-Automation ausgelöst: Die Audio-Part-Rate
   wechselte von 0.0 zu 1.0 und zurück; die Grid-BPM blieb 174.0.

### Implementierter Eingriff

`native/tempo_hook.cpp` ersetzt ausschließlich Slot 9 der StretchBehavior-VTable
atomar per `InterlockedCompareExchangePointer`. Der Slot wird kurz beschreibbar
und danach wieder mit seinem vorherigen Seitenschutz versehen. Keine Trampoline,
keine geänderten Maschinenbefehle, kein Frida und kein eigener Audio-Thread.

Der Loader prüft den exakten EXE-SHA-256 und geladene Setter-Codebytes. Installation
beginnt immer im Default-Modus. Erst eine separate Modusauswahl aktiviert die
Quantisierung. Die DLL bleibt gepinnt, damit bereits geladene Funktionspointer
beim Entfernen des Hooks nicht auf entladenen Code zeigen können. Der Controller
verlangt vor erneuter Installation nach Stop einen Rekordbox-Neustart.

Der Hook prüft zuvor erfasste Owner und ihre Core-/State-/UiPlayer-/Grid-Typen.
Er liest die lokale Beatgrid-BPM und quantisiert `bpm * (1 + pitchDelta)`;
weitergegeben wird `quantizedBpm / bpm - 1`. Er berücksichtigt die nativen
Pitch-Grenzen und hält pro Owner einen Hysteresezustand. Grid-, BPM- und
Modusänderungen verwerfen die bisherige Hysterese beim nächsten Setter-Aufruf.
Der Callback allokiert nicht, öffnet keine Dateien und wartet nicht auf Locks.
Ungültige Kontexte oder konkurrierende Aufrufe werden unverändert durchgereicht;
die entsprechenden Zähler müssen beim Test geprüft werden.

Das Feld `changed`/`quantized` zählt erfolgreich durchgeführte Quantisierungen,
auch wenn der Eingabewert bereits exakt auf der gewählten Stufe lag. Telemetrie
und externe Speicher-Snapshots sind keine atomaren Gesamtzustände.

### Gemessene Ergebnisse

- `native/quantizer_test.cpp`: über 48000 Fader-Sweep-Prüfungen sowie konkrete
  Hysterese-, Moduswechsel-, Track-BPM-Wechsel-, Grenzwert- und NaN-Fälle bestanden.
  Build mit MSVC 14.50, `/W4 /WX`, erfolgreich.
- Default-Diagnose: 175.37 BPM als GUI-Eingabe erreichte den Setter als
  `delta=0.00787353515625` und wurde bitgleich weitergegeben.
- 1-BPM-Modus: dieselbe Eingabe ergab `delta=0.005747126415371895`;
  nominal 174.999999996 BPM, Audio-Part-Rate 1.0057470798492432,
  entsprechend **174.999991894 BPM**.
- 0.1-BPM-Modus: Audio-Part-Rate 1.00804603099823,
  entsprechend **175.400009394 BPM**.
- Hysterese: von 175 aus bleibt 175.59 bei 175; 175.61 wechselt auf 176.
  Rückwärts bleibt 175.41 bei 176 und 175.39 wechselt auf 175.
- Zwölf Live-Testfälle bestanden: beide Schritte, Hysterese in beide Richtungen,
  Sprünge an die +/-6%-Grenzen, Default-Wiederherstellung. Toleranz für die
  Audio-Part-BPM: 0.0001 BPM. Alle Tests prüften unveränderte Grid-BPM 174 und
  dieselbe Grid-Identität. Evidenz:
  `artifacts/live-verification-20260922-020710.jsonl`.
- GUI-Ziehen statt Texteingabe: zuerst 51, dann in einem separat protokollierten
  Durchlauf 46 Setter-Aufrufe. Im zweiten Durchlauf 218 externe Snapshots;
  gelesene Audio-Part-BPM ausschließlich 174, 175, 176, 177, 178, 179, 180
  innerhalb der genannten Toleranz. Evidenz: `artifacts/gui-drag-quantized.json`.
- Nach diesen Tests insgesamt 117 Hook-Aufrufe, 112 Quantisierungen,
  keine Kontext-Bypässe, keine abgewiesenen Owner, keine konkurrierenden Aufrufe.
  Sämtliche protokollierten Aufrufe kamen von Thread 20972.
- Die Deck-Anzeige zeigte ebenfalls das quantisierte Tempo (z.B. 175.40).
  Der GUI-Prozentwert kann weiterhin die rohe Anforderung widerspiegeln;
  dessen Anzeige ist nicht die maßgebliche Audio-Rate.
- Das externe Control-Fenster wurde geöffnet, verbunden und die Auswahl
  0.1 / 1 / Default gegen die native Telemetrie bestätigt. Der generische
  Windows-Store-Python-Alias musste vor der GUI-Schleife auf den spezifischen
  Python-Pfad aufgelöst werden.
- Zuletzt wieder Default, Deck 1 auf 174 BPM und pausiert. Die installierte
  EXE hat weiterhin den oben angegebenen SHA-256. DLL-Build-SHA-256:
  `9cf1a63b2674ae6781aa58c2a5d0b6fcb990cf667464460451519094a81a7538`.

### Noch keine vollständige Freigabe

Die Engine-Rate ist durch statischen Datenweg und Live-Zustände bestätigt;
eine unabhängige Messung des ausgegebenen Audios steht aus. Hardware-Eingaben
wurden mangels DDJ-1000 nicht ausgeführt. Die gemeinsame Datenstrecke macht
Abdeckung plausibel, ersetzt aber diesen Test nicht. Die Rolle der CDJ-800
(eigene Audioquellen oder DVS/Timecode) ist weiterhin offen.

Mehrere geladene Decks, Sync-Master/-Slave, Trackwechsel, dynamische BPM und
Export-/Performance-Wechsel müssen separat getestet werden. Der UiPlayer-
Typcheck und die Owner-Liste sind konservative Einschränkungen, kein Beweis
für jeden Betriebsmodus. Die PowerShell-Oberfläche prüft PERFORMANCE bei der
Aktivierung, aber nicht fortlaufend. Vor einem Moduswechsel den Hook entfernen.

Neue Auswahl, Default und Stop lösen keine eigene Tempo-Neuberechnung aus;
dafür ist die nächste reguläre Tempo-Eingabe erforderlich. Bend, Scratch,
Reverse, Anlauf-/Bremsrampen und DVS bleiben zusätzliche Ratenpfade. Kleine
relative Plus-/Minus-Schritte können auf dieselbe Stufe zurückrunden. Für
diese Punkte ist der Prototyp keine vollständige Umsetzung des ursprünglichen
Anspruchs auf quantisierte momentane Playback-Rate in allen Situationen.

Der Stop-Export ist implementiert; ein kompletter Remove-/Neustart-Zyklus wurde
in dieser laufenden, vorbereiteten Sitzung noch nicht durchgeführt. Frida wurde
für keinen der neuen Tests verwendet. Rekordbox blieb ansprechbar; daraus folgt
noch keine Langzeit-Stabilitätsgarantie.

Zusätzliche Primärquellen für den nativen Eingriff:

- [Microsoft: InterlockedCompareExchangePointer](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-interlockedcompareexchangepointer)
- [Microsoft: DLL Best Practices](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-best-practices)
- [Rekordbox-Handbuch 7.2.14: Performance-Bedienung](https://cdn.rekordbox.com/files/20260409151936/rekordbox7.214_manual_EN.pdf)

## Bedienänderung: Control-Fenster darf geschlossen werden

Das Control-Fenster entfernt den Hook beim Schließen nicht mehr. Die Auswahl
und der Hook befinden sich bereits in der gepinnten DLL innerhalb Rekordbox;
kein externer Prozess muss dafür weiterlaufen. Erneutes Verbinden übernimmt
`rbqTelemetry.mode` und setzt den Modus nicht mehr auf Default zurück. Zum
Deaktivieren kann Default gewählt werden; `Set-TempoStep.ps1 -Step Stop` bleibt
als ausdrückliches Entfernen vorhanden.

PowerShell-Parserprüfung bestanden. Die Audio-/Quantisierungsimplementierung
und die DLL wurden bei dieser Bedienänderung nicht geändert. Ein erneuter
Live-Test des Schließens mit aktivem Hook wurde nicht durchgeführt: Der Hook
in PID 21800 war beim Beginn dieser Änderung bereits entfernt (`installed=false`,
446 historische Aufrufe, davon 441 quantisiert, keine gemeldeten Bypässe).
Diese alte Sitzung benötigt gemäß bisheriger Reinstall-Sperre einen Neustart.

Ein dauerhafter Dateipatch ist noch nicht implementiert. Eine rein lesende
Prüfung ergab: acht PE-Sektionen, Sektionstabelle bereits bis SizeOfHeaders
(1024 Bytes) belegt, EntryPoint-RVA 0x2711ccc, 41 Import-Deskriptoren und eine
vorhandene Authenticode-Zertifikatstabelle. Ein Start-Loader wäre ein zusätzlicher
Eingriff in den Programmstart, einschließlich Prüfung des geänderten PE-Layouts,
Wiederherstellung der Originaldatei und Initialisierung vor verfügbaren Decks.
Die aktuelle DLL benötigt hingegen eine nachträglich erfasste Owner-Liste.
Es wurden bei dieser Untersuchung keine Rekordbox-Programmdateien verändert.

## Dauerhafter Start und eingebettete Einstellung, 22.09.2026

### Installation und PE-Eingriff

Der ausdrücklich angeforderte Dateipatch wurde nach Prüfungen an lokalen Kopien
unter `D:\Programs\rekordbox 7.2.18` installiert. Die ursprüngliche EXE liegt
als `rekordbox.exe.rb-bpm-original` mit dem oben genannten Original-Hash daneben.

- Gepatchte EXE: SHA-256
  `297ab491ae745191b09ee72612be6d4c61075788740fb62140f93b0628337a4f`.
- Installierte `rb_bpm_patch.dll`: SHA-256
  `d4edc5ff31dbcdff25cd0dfc8809092dc0ca1fcd9c2c7f2ae3f9e5aeb2297010`.
- `tools/pe_startup_patch.py` ergänzt einen Import von `rbqBootstrap` und zwei
  Sektionen: `.rbq` (RX, Einstieg bei RVA `0x6291000`) und `.rbqdat` (RW,
  Import-/Unwind-Daten ab RVA `0x6292000`). Es gibt keine neue RWX-Sektion.
- Der neue Einstieg reserviert 40 Bytes Stack, ruft den importierten Bootstrap
  und springt mit wiederhergestelltem Stack zum ursprünglichen Einstieg
  `0x2711ccc`. Die Initialisierung erfolgt außerhalb von DllMain/Loader-Lock.
- Die vollständig belegte Sektionstabelle erfordert 512 zusätzliche Headerbytes.
  Raw-Dateioffsets einschließlich der Debug-Daten werden verschoben. Alle
  ursprünglichen Sektions-RVAs und die ursprünglichen `.text`-Bytes bleiben
  erhalten. Die Runtime-Function-Tabelle wird kopiert und um den neuen Einstieg
  samt x64-Unwind-Information ergänzt. Der PE-Checksum wird neu berechnet.
- Die Authenticode-Verzeichnisreferenz wird entfernt. Die gepatchte EXE besitzt
  keine gültige Herstellersignatur; es wird keine gültige Signatur vorgetäuscht.

Die endgültige Konstruktion wurde zuerst mit einem eigenen Hostprogramm unter
dem Windows-Loader ausgeführt. Ungepatcht gab es Exitcode 71, nach Bootstrap 0;
auch die Headererweiterung war dabei enthalten. Eine frühere Testkonstruktion
mit Importdaten in einer RX-Sektion scheiterte beim Loader-Schreibzugriff und
wurde vor der Rekordbox-Installation durch getrennte RX-/RW-Sektionen ersetzt.

`tools/patch_app.py` prüft das Original und Paketdateien per SHA-256, schreibt ein
geprüftes Backup, legt zuerst die Erweiterungsdateien an und ersetzt die EXE
zuletzt atomar. Installation, wiederholte Installation und bytegenauer Rückbau
wurden an einer Arbeitskopie geprüft. Der Rückbau verweigert das Überschreiben
einer seitdem unbekannt veränderten EXE. `Patch-Rekordbox.ps1` verlangt dafür
eine beendete Rekordbox-Instanz.

### Automatischer Hook und Einstellung

`native/tempo_extension.cpp` enthält die bisherige Quantisierung und initialisiert
sie am Programmstart. Gültige, geladene UiPlayer-Kontexte werden nun beim ersten
Setter-Aufruf automatisch in die begrenzte Owner-Liste aufgenommen. Eine externe
Speichersuche oder ein offenes Hilfsprogramm ist nicht mehr erforderlich.

Ein auf den GUI-Thread begrenzter `WH_CALLWNDPROC`-Hook erkennt den JUCE-Dialog
mit Titel Preferences oder Einstellungen. Ein natives Windows-Panel ergänzt
links unter den vorhandenen Kategorien die Auswahl `BPM / Tempo Step`.
Der vorhandene Dialog wird dafür unterklassifiziert; keine JUCE-Klassenstruktur
oder Track-Daten werden geändert. Positionierung und freie Fläche wurden am
lokalen 800×800-Dialog bei 96 DPI visuell geprüft. Bei zu wenig Fläche wird das
Zusatzfeld ausgeblendet. Andere Sprachen oder DPI-Konfigurationen sind offen.

Der Modus wird in `rb-bpm.ini` neben der EXE gespeichert (`Step=default|0.1|1`).
Speichern geschieht auf dem GUI-/Steuerpfad, nicht im Tempo-Callback.
Bei Auswahländerung wird für bekannte, weiterhin passende Grid-Kontexte der
zuletzt empfangene rohe Sollwert über die native Request-Funktion `0x2c07ef0`
erneut angefordert. Diese nutzt den vorhandenen Lock-/Task-Pfad des Players.
Deshalb wirkt die Auswahl bei diesen Decks ohne zusätzliche Faderbewegung;
vorher unbekannte Kontexte warten auf ihren ersten regulären Tempoaufruf.

Bei der vorübergehenden Injektion zum UI-Test wurde festgestellt, dass Windows
den Fenster-Hook beim Ende des installierenden Hilfsthreads entfernte. Der
Diagnose-Bootstrap überträgt deshalb die Hook-Eigentümerschaft synchron auf den
GUI-Thread. Der endgültige EXE-Bootstrap läuft bereits auf diesem Thread und
benötigt weder Remote-Thread noch dauerhaft laufenden Helfer.

### Bestätigte Laufzeitergebnisse

- Build mit MSVC `/W4 /WX /MT` erfolgreich; DLL hat keine separate Runtime-
  Installation nötig. Quantisierungslogik entspricht dem vorher getesteten Kern.
- Test vor Installation, PID 7152: ursprüngliche BPM 174, roher GUI-Sollwert
  175.37, Integer-Modus mit Audio-Part-BPM 174.999991894. Der Wechsel im
  eingebetteten Einstellungsfeld auf 0.1 ergab sofort 175.400009394, ohne erneute
  Faderbewegung. Grid-BPM blieb 174. Evidenz: `artifacts/embedded-settings-live.json`.
- Erster regulärer Start der installierten EXE: PID 4424. Die Erweiterung wurde
  aus dem Rekordbox-Verzeichnis geladen. Vor dem zweiten Start: 1123 Aufrufe,
  1098 Quantisierungen, keine abgewiesenen Kontexte, Bypässe oder Konkurrenz.
  Der gewählte Modus 0.1 stand sowohl in der INI als auch im eingebetteten Feld.
  Deck 1 war pausiert, Grid 174, Basis-Sollwert 173.5 BPM.
- Normal beendet und direkt dieselbe gepatchte EXE neu gestartet: PID 21556.
  Vor jeder neuen Tempoeingabe war der Hook bereits installiert, Mode 1 (0.1),
  Zähler 0. Das eingebettete Feld zeigte ebenfalls 0.1. Es erfolgte keine
  nachträgliche DLL-Injektion oder Aktivierung durch einen Controller.
- Nach neuen Eingaben in dieser Sitzung: 81 Aufrufe und 81 Quantisierungen,
  keine Bypässe/abgewiesenen/konkurrierenden Kontexte; gelesene Grid-BPM weiterhin
  174. Das zeigt die automatische Owner-Erfassung nach dem Neustart.
- `tools/preferences_probe.ps1 -Action Status` liest Feld und Auswahl;
  `Set-TempoStep.ps1 -Step Status` liest den Hook. Beide sind Diagnosehilfen und
  werden für dessen Betrieb nicht benötigt.
- Abschließende Hash-, INI-, Hook- und Deck-Momentaufnahme nach Neustart:
  `artifacts/permanent-restart-verification.json`. Ein erneuter optionaler
  Steueraufruf mit unverändertem Modus 0.1 erhöhte den Setter-Zähler auf 82;
  der Neuberechnungsauftrag wurde vom Player-Thread verarbeitet. Beim offenen
  modalen Preferences-Dialog fehlt die Performance-Anzeige in UI-Automation;
  die externen Steuerhilfen verweigern dann die Aktivierung und verweisen auf
  das eingebettete Feld. Bei geschlossenem Dialog wurde der Aufruf geprüft.

Die Audio-Evidenz bleibt eine Messung des internen Engine-Zustands. Ein
unabhängig aufgezeichneter Audioausgang, Hardware-Fader, Sync und DVS wurden
nicht geprüft. Der UiPlayer-Typcheck ist keine lückenlose Performance-/Export-
Trennung. Der Prototyp ist daher noch keine Freigabe aller ursprünglich
gewünschten Betriebsarten; vor dem Verlassen von Performance Default auswählen.

Primärreferenzen für PE-Layout und Windows-Lebensdauer:

- [Microsoft PE Format](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)
- [Microsoft SetWindowSubclass](https://learn.microsoft.com/en-us/windows/win32/api/commctrl/nf-commctrl-setwindowsubclass)
- [Microsoft Terminating a Thread](https://learn.microsoft.com/en-us/windows/win32/procthread/terminating-a-thread)

## Verschiebung nach Extensions → RB PLUS, 22.09.2026

Die Einstellung befindet sich jetzt auf einer eigenen Seite unter Extensions.
Die Position unter der linken Kategorienliste wurde entfernt.
`native/preferences_tabs.h` ergänzt eine native Windows-Tab-Leiste mit STEMS,
Video, Lighting und RB PLUS. Die ersten drei Einträge aktivieren über die
Accessibility-Schnittstelle die vorhandenen Rekordbox-Seiten. RB PLUS zeigt
die Tempoauswahl in einem eigenen Inhaltsbereich. Bei anderen Kategorien
werden zusätzliche Tab-Leiste und Inhalt ausgeblendet.

UI-Automation läuft auf einem fensterlosen COM-MTA-Thread innerhalb Rekordbox,
nur bei sichtbaren Preferences. UI-Änderungen erfolgen per Nachricht auf dem
GUI-Thread. Kein externes Tool muss geöffnet bleiben. Das Thread-Modell folgt
der [Microsoft-Dokumentation zur eigenen UI als Automation-Ziel](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-threading).
Die Oberfläche wird nur bei geänderter Auswahl neu positioniert. GUI-Kontrollen
werden frisch ermittelt: JUCE ersetzt beim Kategorienwechsel Elemente, ohne
ältere Referenzen immer eindeutig als ungültig zu melden.

### Fehler während der Entwicklung und Korrektur

Die Entwicklungs-DLL mit SHA-256
`7c03cfc426bec8052a62fe99f984e41e001d9c017b855923c39fc72f7ba1a3e2`
verursachte beim Dialog-/Seitenwechsel einen Fehler und einen Crash-Dump um
08:24:29. Es war keine passende Rider-Debug-Sitzung aktiv; PDBs für diesen Build
und lokales WinDbg/CDB fehlten. Der Minidump wurde deshalb direkt ausgewertet
und mit dem Disassembly der tatsächlich geladenen DLL abgeglichen:

- Exception `0xc0000005`, lesender Zugriff auf Adresse 0, Thread 22680.
- `rb_bpm_patch.dll+0x24a1`: `mov rax, [rcx]`, mit `RCX=0`.
- Unmittelbar davor: `GetCurrentPatternAs`, Pattern-ID 10015 (TogglePattern),
  erfolgreicher HRESULT, aber zurückgegebener Interfacepointer 0.
- Danach sollte ungeprüft `get_CurrentToggleState` aufgerufen werden.
- Korrektur: HRESULT **und** Interfacepointer werden geprüft, auch im verwandten
  Invoke-Pfad. Fehlende oder verschwindende Controls werden übersprungen.

Der Fehler lag in der UI-Erweiterung. Der Dump heißt
`f9eae4b1-53d9-4998-a855-8a965f1fd58d_7.2.18.0311_64.dmp` im Rekordbox-Crash-
Verzeichnis. Es wurde kein externer Hilfsprozess als Umgehung eingeführt.

### Installierter und geprüfter Stand

- DLL-SHA-256: `2b955d9d4ffe6b40fb6c02570498aec5c7fb096834d8a0bbc85bfefc2f2c7a55`.
- EXE-SHA und Original-Backup bleiben gegenüber dem permanenten Patch unverändert.
  Der Installer unterstützt das geprüfte DLL-Update und erhält die INI.
  Update, Wiederholung und Rückbau wurden an einer lokalen Dateikopie geprüft.
- Build mit `/W4 /WX` bestanden; PID 8860 lud den korrigierten Hook automatisch.
- Navigation: Video → Lighting → STEMS → RB PLUS → Audio → RB PLUS → View →
  RB PLUS. Auswahl und Sichtbarkeit wurden für jeden Schritt geprüft.
- Alle drei BPM-Modi wurden über das verschobene Feld ausgewählt und gegen
  Hook-Telemetrie und INI geprüft; abschließend wieder 0.1.
- Fünf weitere Schließen-/Öffnen-Zyklen bestanden; Rekordbox blieb ansprechbar.
  Sechs erzeugte Panels insgesamt; keine gemeldeten UI-Erstellungs-, COM- oder
  Invoke-Fehler im Abschlussstatus.
- Evidenz: `artifacts/extensions-navigation.json` und
  `artifacts/extensions-verification.json`.

Tempo-Setter und Quantisierung wurden für die Verschiebung nicht geändert.
Die bestehenden Einschränkungen zu Hardware und Betriebsarten gelten weiterhin.

## Mausauswahl im RB-PLUS-Dropdown (22.09.2026)

Der Benutzer meldete: Die Liste öffnet sich per Maus, ein Klick auf eine Option
schließt sie ohne Übernahme; Pfeiltasten und Enter funktionieren. Die bisherigen
UI-Prüfungen setzten die Auswahl über Steuernachrichten und erfassten diesen
Unterschied nicht.

### Laufzeitbefund

Keine Rider-Debug-Sitzung oder Run-Konfiguration war für die native Erweiterung
vorhanden. Stattdessen wurde eine begrenzte Windows-Nachrichtenaufzeichnung auf
dem vorhandenen GUI-Thread verwendet (`native/ui_input_probe.cpp`). Sie ist ein
separates Diagnosewerkzeug und wird nicht mit dem permanenten Patch installiert.

In PID 8860 war die Popup-Liste `ComboLBox` kein Kindfenster der Preferences
(`IsChild=false`). Beim echten Klick auf Option 2 blieb die Auswahl 1. Die
Nachricht `WM_LBUTTONDOWN` ging an das Popup, anschließend verlor die Combobox
den Fokus an Preferences und meldete `CBN_SELENDCANCEL` statt der gewünschten
Auswahl. Der RB-PLUS-Inhalt blieb sichtbar. Der Fehler liegt damit im Eingabepfad
der Popup-Liste, nicht in der Speicherung oder im Ausblenden des Tabs.

Ein gezielter A/B-Versuch leitete ausschließlich Mausnachrichten dieses Popups
vor dem modalen Nachrichtenfilter direkt an dessen native Fensterprozedur.
Derselbe Klick wählte dann Option 2; Hook-Modus und INI wurden ebenfalls 2 / 1 BPM.
Das bestätigt die Unverträglichkeit des nativen Popups mit dem modalen
Eingabepfad des Hosts. Evidenz: `artifacts/combo-mouse-before.json`,
`combo-messages-before.json`, `combo-mouse-bridge.json`, `combo-messages-bridge.json`.

### Permanente Korrektur

`native/preferences_combo.h` registriert einen threadlokalen `WH_GETMESSAGE`-Hook
für die Lebensdauer des Panels. Er behandelt nur Mausnachrichten an die eigene
Popup-Liste, wenn Combo und Liste sichtbar, Preferences aktiv und aktiviert und
die Combo fokussiert sind. Andere Fenster und Tastatureingaben bleiben außerhalb
dieses Pfads. Nachrichten werden nur bei `PM_REMOVE` einmalig zugestellt und
anschließend als `WM_NULL` an die Nachrichtenschleife zurückgegeben. Die
[Microsoft-Dokumentation zu GetMsgProc](https://learn.microsoft.com/en-us/windows/win32/winmsg/getmsgproc)
beschreibt die Unterscheidung zwischen entnommenen und nur angesehenen Nachrichten.

Auswahl, Klick außerhalb der Liste und Schließen verarbeitet weiter die native
Windows-Combobox. Beim Zerstören des Panels wird der zusätzliche Hook entfernt.
Der 400-ms-Abgleich der Auswahl pausiert außerdem bei offener Liste, damit er
eine laufende Auswahl nicht auf den gespeicherten Modus zurücksetzt.

Build `/W4 /WX` bestanden. Installierte DLL-SHA-256:
`5175314bf0b0f9dc0c07637577bca080625c660f60ac8fd2cf5809f1c812de0d`.
EXE-Patch und Tempo-Engine blieben unverändert. Rekordbox wurde bei leeren,
gestoppten Decks regulär beendet, die DLL aktualisiert und normal neu gestartet.
PID 23684 lädt ausschließlich die permanente Erweiterung; die temporäre
Diagnose-DLL ist in diesem Prozess nicht geladen.

### Prüfung mit tatsächlicher Eingabe

`tools/preferences_mouse.py` verwendet echte Windows-Maus-/Tastatureingaben,
prüft den Prozess unter dem Klickziel und stellt die Cursorposition wieder her.
`tools/verify_preferences_input.py` vergleicht Auswahl, Hook-Modus und INI.

- Alle drei Optionen per Maus gewählt, mit 700 ms Verweildauer über dem Eintrag
  (länger als das Synchronisationsintervall): bestanden.
- Abbruch über Escape sowie Außenklick: Auswahl unverändert, Liste geschlossen.
- Alle drei Optionen über Tastatur nach Öffnen mit der Maus: bestanden.
- Abschlussauswahl wieder **0.1 BPM**.
- Evidenz: `artifacts/combo-input-verification.json`.
- Drei weitere Schließen-/Öffnen-Zyklen mit anschließender Mausauswahl bestanden.
  Telemetrie: vier installierte und drei entfernte Combo-Hooks, kein Installationsfehler;
  genau ein Hook bleibt für das aktuell offene Panel aktiv. Rekordbox ansprechbar.
  Evidenz: `artifacts/combo-lifecycle-verification.json`.

Diese Prüfung betrifft die Eingabe im Einstellungsfeld. Die Audio-Engine wurde
für diese Korrektur nicht verändert; die dokumentierten Hardware-Grenzen gelten weiter.
