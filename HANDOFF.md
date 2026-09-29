# RB PLUS — Handoff

Updated: 2026-09-29. Repository: https://github.com/spartokos99/rb-plus (private).

## Current release work

The user requested English throughout the UI, installer and documentation, and
publication as GitHub release **v1.0.0**. The package name is
`packages/RB-PLUS-v1.0.0-Rekordbox-7.2.18.0311-Windows-x64.zip`.
The runtime build for English UI has SHA-256
`2ae31532ce79c1423c5a7cf0f921a71fa2b4ee97fa20224b03644b0dfb811c27`.
Release-specific results are recorded separately in the version report.

## Layout settings

For Performance / 4Deck Horizontal, RB PLUS offers two independent lists with
all 24 permutations plus Default: waveform rows from top to bottom, and decks
at top left/right then bottom left/right. Stored as `[Layout] WaveOrder` and
`DeckOrder` (e.g. 3124 / 3214) in the same INI. Other layouts remain native.
`native/layout_extension.h` uses the original panel resize, native deck layout
helpers and the locked waveform source assignment. Number images are drawn in
the existing native paint context. ABI/offsets/threading: `docs/layout-7.2.18.md`.

The 2026-09-28 layout DLL passed 50 choices with actual input and read-only position
checks, all four waveform drags and Play/Pause mappings with loaded tracks,
2H/4V/4H switching, 1920×1080, saved startup, three dialog cycles, Tab/Shift-Tab
and native categories. Tempo dropdown and internal Default/1/0.1 audio rates were
rechecked. No new hardware, extended-session or high-DPI test. See the version report.
User selections are WaveOrder=3124, DeckOrder=3214, Tempo=0.1. Always read current
playback/process state again before testing or restarting.

## Portable release package

The ZIP contains the recorded, runtime-tested DLL, isolated CPython 3.13.14,
installation, restoration and read-only checks. No Rekordbox EXE is included:
`tools/release_patch.py` reuses the existing installer to prepare it from the exact
verified destination installation in a temporary directory. Users select their own
`rekordbox.exe`. `release/Setup.ps1` blocks changes while Rekordbox is running.
Only `rb-bpm.ini` receives local-user write permission so choices can be saved
under Program Files. Executable/backup permissions remain unchanged.

Build: `python tools/build_release.py --dll build/permanent/rb_bpm_patch.dll`.
The builder accepts only hashes in `tested_extension_sha256`; never distribute
a freshly compiled untested DLL as a tested historical binary. Package tests need
`RBQ_TEST_RELEASE` and `RBQ_TEST_ORIGINAL`; they exercise the actual isolated runtime
and temporary original copies. English entry points: `Install.cmd`, `Uninstall.cmd`,
`Check-Compatibility.cmd`, instructions in `release/README.txt`.

Preserved local baselines:

- Tempo-only ZIP: `packages/tempo-2026-09-26/`; development package:
  `build/tempo-baseline-20260922/`.
- German layout DLL/package: `build/layout-baseline-20260928/`; unversioned ZIP:
  `packages/RB-PLUS-7.2.18.0311-Windows-x64.zip`.
- Old tested DLL hashes remain in the registry. Historical evidence stays distinct
  from current release validation.

## Working behavior

Permanent Windows x64 patch for **Rekordbox 7.2.18.0311**. The patched EXE loads
`rb_bpm_patch.dll` on normal startup. No PowerShell window/external process must
stay open while playing. **Preferences → Extensions → RB PLUS → BPM / Tempo Step**
offers Default / 0.1 / 1; selections are stored beside the installation.

The shared `StretchBehavior` setter quantizes relative base pitch. The engine
receives the resulting rate; analyzed BPM, grids and databases are unchanged.
Hysteresis is half a step plus 10% of its width. Values are native floats, not
exact decimal representations. Already detected decks reapply on setting changes.

JUCE previously cancelled mouse clicks on the separate native combo popup. A
GUI-thread hook limited to our own popup forwards those messages. Actual mouse,
keyboard, Escape/outside clicks and repeated dialog lifecycle checks established
the correction; the same scoped path supports all three selectors.

## File responsibilities

| File | Purpose |
| --- | --- |
| `native/quantizer.h` | Quantization/hysteresis independent of Rekordbox |
| `native/tempo_hook.cpp` | Exact 7.2.18 native backend: ABI, offsets and VTable hook |
| `native/tempo_extension.cpp` | Startup, INI, settings and GUI-thread reapplication |
| `native/preferences_tabs.h` | Extensions tabs, RB PLUS, UIA MTA worker |
| `native/preferences_combo.h` | Actual mouse input for our own combo popups |
| `native/layout_extension.h` | Version-specific waveform/deck arrangement |
| `native/layout_order.h` | Permutation parsing and serialization |
| `tools/pe_startup_patch.py` | PE import/entry additions without shifting old RVAs |
| `tools/patch_app.py` | Package preparation, installation, DLL update, restoration |
| `tools/observe_tempo.py` | Read-only process/audio-rate observer, currently bound to 7.2.18 |
| `tools/tempo_control.py` | Explicit diagnostic controls, exports and telemetry |
| `compatibility/builds.json` | Additive registry of exactly identified builds |
| `Test-RekordboxCompatibility.ps1` | Read-only entry point for a new installation path |

The `.sln` is for source navigation; build through CMD scripts.
`native/ui_input_probe.cpp` is optional diagnostics, not part of the installed
extension. Old runtime controls and `verify_live.py` are not the normal startup
path. `verify_live.py` expects the diagnostic hook, exactly one playing deck-1
track with original BPM 174, and actively changes its tempo.

## Known host and local state

- Build 7.2.18.0311 x64; original/patched hashes in the registry.
- Historical local installation: `D:\Programs\rekordbox 7.2.18`.
- Original backup: `rekordbox.exe.rb-bpm-original`; never replace it unchecked.
- English DLL installed for release validation: SHA given above.
- Restore the user's Tempo=0.1, WaveOrder=3124, DeckOrder=3214 after tests.
  Never reuse old PIDs, HWNDs or player addresses from logs.
- The PE patch removes the invalidated Authenticode directory reference; no
  signature/license check is bypassed. Restoration returns the verified original.

## New Rekordbox versions

The user wants to provide only the new installation path. Follow **AGENTS.md →
compatibility/README.md** completely. Previously tested versions must keep working.
The checker already uses the registry; the installer and native/diagnostic backends
support only 7.2.18. Implement additive backend selection before approving a second
version. A registry entry alone does **not** extend the hook.

```powershell
.\Test-RekordboxCompatibility.ps1 -Path 'D:\Programs\rekordbox NEW'
```

## Known limits — never report these as passed

DDJ-1000 was not connected. DVS/CDJ-800, Sync, multiple loaded decks, track changes,
Export/Performance transitions and long sessions remain incompletely validated
across the tempo matrix. UiPlayer checks do not fully establish global Performance
mode; select Default before leaving Performance. Jog bend, scratch, reverse and
start/stop ramps use additional rate paths. Dynamic beatgrids are evaluated on
tempo calls, not every position change. UI tests used English Preferences at 96 DPI.

The user **abandoned** the waveform/120 Hz investigation.
`docs/waveforms-120hz-feasibility.md` is historical evidence only, not a task,
implemented feature or next step.

Details: `compatibility/reports/7.2.18.0311-windows-x64.md` and
`docs/investigation-7.2.18.md`. Raw logs/screenshots/dumps stay locally in
`artifacts/` and outside Git. Missing raw data must not be presented as a new
successful test.

Release validation completed on 2026-09-29: English UI, 50 layout selections,
eight tempo input/cancellation cases, original categories and three dialog cycles
passed on the exact DLL above. All 11 Python tests passed without skips against
the actual ZIP and temporary original copies. Rekordbox was closed normally after
confirming paused players; saved settings are 0.1 / 3124 / 3214. Recheck this state
before subsequent work. The release contains our DLL and isolated Python only,
with no manufacturer EXE or private test artifacts.
