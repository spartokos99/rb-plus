# RB PLUS — Live tempo steps and deck layouts for Rekordbox

**RB PLUS v1.0.0** adds **Preferences → Extensions → RB PLUS** to
**Rekordbox 7.2.18.0311 on Windows x64**. The extension loads automatically on
normal startup. No external helper needs to stay open during playback.

- **BPM / Tempo Step:** Default / 0.01 BPM (native resolution), 0.1 BPM, or 1 BPM.
- **Waveforms (top to bottom):** any of the 24 waveform orders in Performance →
  4Deck Horizontal.
- **Decks (top / bottom):** independently choose the top left/right and bottom
  left/right decks. All 24 orders are available.

Selections take effect immediately and are saved in `rb-bpm.ini`. Previously
detected, loaded decks reapply their last tempo request when the step changes;
new decks are detected on their first valid tempo call. Layout choices are
reapplied after restarting or returning to 4Deck Horizontal. **Default (Rekordbox)**
restores the native arrangement for each list. Other layouts keep their native
arrangement. Deck numbers, controls and drop targets follow their deck; logical
deck IDs, audio routing and MIDI deck assignments remain unchanged.

This experimental patch quantizes the **live base tempo request before audio
processing**. It does not change track BPM, beatgrids, metadata or database values.

## Install the release

Download the ZIP and its SHA-256 file from [Release v1.0.0](https://github.com/spartokos99/rb-plus/releases/tag/v1.0.0).
The package includes the tested DLL, installer, uninstaller and an isolated
Python runtime. The destination laptop needs no Python installation, development
tools or additional downloads.

1. Extract the entire `RB-PLUS-v1.0.0-Rekordbox-7.2.18.0311-Windows-x64.zip`.
2. Close Rekordbox normally.
3. Right-click `Install.cmd` and choose **Run as administrator**.
4. Select the `rekordbox.exe` in your own 7.2.18 installation.
5. Start Rekordbox normally and open **Preferences → Extensions → RB PLUS**.

`Check-Compatibility.cmd` performs read-only checks. To remove the patch, close
Rekordbox and run `Uninstall.cmd` as administrator, selecting the same EXE.
Full instructions are included in `README.txt`.

The ZIP contains no Rekordbox EXE, music or database. The installer prepares the
patched EXE from the exact, verified local installation. Other builds are rejected,
even if their displayed version matches. The original is preserved as
`rekordbox.exe.rb-bpm-original`. Existing settings are retained; new installations
start with Default. Local Windows users receive write access only to `rb-bpm.ini`
so settings can be saved under Program Files without running Rekordbox as
administrator. Executable and backup permissions are not broadened.

Uninstalling restores the original EXE byte for byte and removes the matching
DLL. The backup and INI remain. An EXE changed by another update is not overwritten.
**Do not delete the DLL separately while the EXE is patched:** Windows needs it
to start Rekordbox. Keep the ZIP for future uninstallation.

The file patch invalidates the original vendor signature and removes its PE
directory reference. Vendor licenses and subscriptions remain required.
Rekordbox updates may replace the patch; other builds need a separate investigation.
The package has not been tested on the destination laptop.

## Validation and limitations

Measured internal audio state with a track whose original BPM is 174:

| Mode | Requested BPM | BPM from the audio-part rate |
| --- | ---: | ---: |
| Default | 175.37 | 175.369995 |
| 1 BPM | 175.37 | 174.999992 |
| 0.1 BPM | 175.37 | 175.400009 |

The differences reflect native floating-point representation. Historical tests
confirmed that changing from 1 to 0.1 BPM reapplies the audio-part rate without
another fader movement; the beatgrid stayed at 174 BPM. These are internal engine
measurements, not recordings of the audio output.

The tested layout build passed all 50 selections (24 + Default per list), actual
mouse and keyboard input, waveform dragging and Play/Pause mapping for four loaded
decks, layout switching, saved startup and dialog lifecycle checks. The tempo
dropdown's popup handling is corrected and tested with actual clicks, Escape and
outside clicks. Unit tests, native builds, PE checks and the extracted release's
install/reinstall/update/rollback/uninstall lifecycle are covered separately.
See the [version report](compatibility/reports/7.2.18.0311-windows-x64.md) for exact
DLL hashes, dates, repeated checks and historical coverage.

- **DDJ-1000 hardware input is untested:** no controller was connected. The hook
  sits at a shared setter, but this does not establish hardware coverage.
- Sync, DVS/CDJ-800, multiple loaded decks, track changes and Export/Performance
  transitions are not fully validated across the tempo matrix. The UiPlayer type
  check does not completely identify global Performance mode. **Select Default
  before leaving Performance.**
- Jog bend, scratch, reverse and start/stop ramps use additional rate paths.
  Quantization applies to the base request, not every transient rate.
- Hysteresis is half a step plus 10% of the step width. With 1 BPM, 175 persists
  until about 175.60; in reverse, 176 persists until about 175.40. Small relative
  increments may round back to the same step.
- Dynamic beatgrid BPM is read on tempo calls; a position change alone does not
  trigger quantization.
- At most eight player addresses are tracked per session. Invalid, unknown or
  concurrent contexts pass through unchanged and are counted diagnostically.
  Long-session validation remains open.
- The tab bar and panel are native Windows controls inside Rekordbox, not an
  official vendor extension. Existing Extensions tabs open their original pages.
  UI tests used English Preferences at 96 DPI. Other languages and high DPI are
  untested. UI Automation runs on a separate thread only while Preferences is visible.

Implementation evidence: [tempo investigation](docs/investigation-7.2.18.md) and
[layout investigation](docs/layout-7.2.18.md). The abandoned 120 Hz investigation
is archived and is not an implemented or planned feature.

## Build from a fresh checkout

Requirements: Windows x64, x64 Python (locally tested with 3.13), Visual Studio C++
Build Tools with the Windows SDK, and your own matching Rekordbox installation.
The solution groups sources for navigation; CMD scripts build the binaries.
Vendor binaries, music, databases, dumps and local packages are excluded from Git.

```powershell
python -m pip install --target .tools/python -r requirements-analysis.txt
python -m unittest discover -s tests -v
.\native\build.cmd
.\native\build-extension.cmd rb_bpm_patch
python tools/patch_app.py prepare --exe '<unpatched working copy>\rekordbox.exe'
```

Analysis dependencies are needed only for PE inspection/disassembly. Compatibility
checks and installation use the Python standard library. MSVC is detected using
`vswhere`; alternatively use an x64 Developer Shell or point `RBQ_VCVARS` to
`vcvars64.bat`. Outputs go to `build/`, local evidence to `artifacts/`; neither is
committed. `prepare` requires a verified **unpatched** file named `rekordbox.exe`.
If already patched, copy the verified backup to a working directory under that
name. The current development package is created in `build/permanent`.

Install or restore that development package with Rekordbox closed:

```powershell
.\Patch-Rekordbox.ps1 -Action Install -Exe '<installation>\rekordbox.exe'
.\Patch-Rekordbox.ps1 -Action Restore -Exe '<installation>\rekordbox.exe'
```

Repeated installation preserves the INI and verified backup. For an updated DLL
with the same patched EXE, only the DLL and manifest are updated after validation.

Build and test a release from a DLL recorded as runtime-tested in the registry:

```powershell
python tools/build_release.py --dll build/permanent/rb_bpm_patch.dll
$env:RBQ_TEST_ORIGINAL='<verified original or backup>'
$env:RBQ_TEST_RELEASE='packages/RB-PLUS-v1.0.0-Rekordbox-7.2.18.0311-Windows-x64.zip'
python -m unittest discover -s tests -v
```

The package builder uses a local Windows x64 CPython installation with `Lib`,
`DLLs` and `LICENSE.txt` (currently 3.13.14). An unrecorded DLL is rejected even
if it compiles successfully. Optional package tests use temporary copies only;
without the two environment variables, their corresponding tests are skipped.

## Supporting another Rekordbox version

A future request to a coding agent can simply state:

> I installed a new Rekordbox version at `<path>`. Make it compatible with our
> patch and keep all previously supported versions working.

[AGENTS.md](AGENTS.md), [HANDOFF.md](HANDOFF.md) and the
[compatibility workflow and matrix](compatibility/README.md) define the complete
process. Support is additive and tied to exact builds. Only **7.2.18.0311 / Windows
x64** is currently supported. The native and diagnostic backends are bound to
7.2.18; explicit backend selection must be implemented before adding a second build.

Start with a read-only check:

```powershell
.\Test-RekordboxCompatibility.ps1 -Path 'D:\Programs\rekordbox NEW'
```

A successful static check is not a live or hardware test. Unknown builds are rejected.

## Settings and diagnostics

The INI beside the EXE contains, for example:

```ini
[Tempo]
Step=0.1
[Layout]
WaveOrder=3124
DeckOrder=3214
```

Tempo accepts `default`, `0.1` or `1`; layout accepts `default` or any permutation
of `1234`. Missing/invalid layout values use Default. Manual file changes are
read at the next startup; use the panel while Rekordbox is running.

```powershell
.\Set-TempoStep.ps1 -Step Status
.\Observe-Tempo.ps1 -Seconds 30
```

The observer injects nothing and writes no process memory. Logs go to `artifacts/`.
`owner` is an address, not a deck number; `grid_bpm` is the local beatgrid BPM.
Snapshots are not atomic. `Start-Control.cmd` and `Set-TempoStep.ps1` are optional
diagnostic controls. With the permanent patch, mode changes are saved and Stop is
blocked: use Default to disable quantization or uninstall to remove the patch.
Close Preferences before changing modes externally: Rekordbox does not reliably
expose its Performance display to UI Automation while the modal dialog is open.
The embedded panel works directly in the open dialog.

Core sources: `native/tempo_hook.cpp` (setter), `native/tempo_extension.cpp`
(startup, settings, persistence and reapplication), `native/preferences_tabs.h`
(Extensions navigation), `native/layout_extension.h` (layout),
`tools/pe_startup_patch.py` (PE patch), `tools/patch_app.py` (installation/restoration).
The older `tools/verify_live.py` requires the diagnostic runtime hook and actively
changes deck tempo; it is not a passive monitor.
