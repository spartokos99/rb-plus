# Investigation, 2026-09-21–22

**Status at the end of this investigation:** a permanent file patch with an
automatically loaded native extension and a saved Preferences setting was installed.
Two normal launches and persistence of 0.1 BPM were confirmed. GUI tempo and internal
audio rate were tested live; hardware and further modes remained open. Earlier
sections describe historical stages. Statements about unchanged program files or
missing persistent settings refer to those stages, not the completed extension.

## Exact installation investigated

- File: `D:\Programs\rekordbox 7.2.18\rekordbox.exe`
- FileVersion: `7.2.18.0`; ProductVersion: `7.2.18.0311`
- Size: 100561840 bytes
- Original SHA-256: `a99896cf26d5998e6ad4177796a467b83df14bf8ae7207df21ed01251e402493`
- Architecture: Windows x64; preferred ImageBase `0x140000000`.
- All following addresses are **RVAs**; add the current ASLR module base.
  This does not approve other builds with the same version name.
- MSVC RTTI remains present. The embedded PDB path points to a vendor build server;
  local source lines/debug symbols were unavailable.

The EXE checksum remained unchanged after the initial investigation. That stage
did not patch Rekordbox program files, databases, beatgrids or metadata.

## Statically established candidate and data path

Names are reconstructed from MSVC RTTI of task classes and their VTables, not a
vendor-published API.

| RVA | Mapping / observed code |
| --- | --- |
| `0x555c620` | `rbxfrm::StretchBehavior` VTable, slot 9 points to `0x2c07bd0` |
| `0x555c748` | `doSetBaseTempoRatioTask` VTable from `StretchBehavior::reqSetBaseTempoRatio` |
| `0x2c07e80` | Task execution: owner from `task+0x20`, float from `task+0x28`; jump to owner VTable `+0x48` |
| `0x2c07ef0` | Request function: clamps to `owner+0x11c/0x120`; queues a task or calls VTable `+0x48` directly |
| `0x2c07bd0` | Reconstructed `StretchBehavior::doSetBaseTempoRatio` setter; `this` in RCX, float in XMM1. A previously suspected Boolean argument is not read |
| `0x2c07de5` | Writes float from XMM6 to `[RBX+0xec]` |
| `0x2d94af0` | Executes `DjSyncSlaveBehaveDispatcher::reqSetBaseTempoRatio` task |
| `0x2d949d0` | Dispatcher path, conditionally calls `0x2c07ef0` |
| `0x2e4a610` | Executes `DjSyncMasterBehavior::reqSetBaseTempoRatio` task |
| `0x2e4a270` | Master path with additional Sync/beatgrid calculations; not fully verified at runtime |

Hooking only the queued task would miss the request function's direct call to the
same virtual function. `0x2c07bd0` was therefore the stronger candidate.

### Connection to rate processing

- `0x2c04b90` reads `StretchBehavior+0xec`, adds `1.0f` and accounts for playback
  direction. The constant at `0x5582880` is `0000803f`.
- `0x2c050e0` combines `1 + [owner+0xec]` with `[owner+0xf0]`, considering direction.
- `0x2c04f67..0x2c05057` includes additional play/scratch conditions and calls
  `0x2d80e60` at `0x2c0500e`.
- `0x2d80e60` receives the core in RCX and rate in XMM1, iterates audio parts from
  `core+0x2c0`, list `+0x68`, count `+0x74`, and passes the rate to three subobjects
  per part through their VTable `+0x88`.
- `0x2d80f6f` writes the supplied rate as a double to `part+0x30`, which the external
  observer can read.

This statically connects the candidate to audio-rate processing. At this stage,
coverage of every input source and actual audio output speed were **not** established.

### Correct numeric interpretation

The stored float is a relative deviation, not a factor whose neutral value is 1:

```text
pitchDelta = 0.0 corresponds to nominalRate = 1.0
targetBpm = originalBpm * (1.0 + pitchDelta)
quantizedBpm = round(targetBpm / step) * step
quantizedPitchDelta = quantizedBpm / originalBpm - 1.0
```

The addition and subsequent data path establish this interpretation. Original BPM
still needed a validated track/grid source. `core+0x218` was only a candidate:
120.0 in all five objects did **not** establish original BPM there.

## Runtime observations and limits

Temporary Frida probes targeted the three task functions, then `0x2c07bd0`.
Signatures and EXE hash matched, but no tempo change was logged in the observation
windows, so there was no fader call stack or before/after pair for a known track.
An additional internal scan found five `StretchBehavior` objects with
`DjPlayerCore` VTable `0x556fb28`, then timed out. Afterwards:

- Windows Application Error, Event 1000, 2026-09-21 20:24:03 local time.
- Process `rekordbox.exe`, PID 16088; faulting module `frida-agent.dll`.
- Exception `0xc0000409`, offset `0xfa2f9d`.
- Report ID `85c2d054-3006-4e14-9ffb-5833353456f8`.
- Local dump: `C:\Users\Nico\AppData\Local\CrashDumps\rekordbox.exe.16088.dmp`.
- The specific Frida failure was not investigated. These facts do not establish
  stack overflow or a particular race.

This instrumentation was insufficiently stable. Frida scripts were removed and
the original application restarted (PID 21800 at that time). The replacement
`tools/observe_tempo.py` uses only `OpenProcess` with
`PROCESS_QUERY_INFORMATION | PROCESS_VM_READ`, `VirtualQueryEx`, `ReadProcessMemory`
and module queries. No memory writes, injected DLL, remote thread or calls inside
Rekordbox.

Initial external observation found five validated player objects in about 4.2 s.
All had pitch/bend deltas 0 and nominal rate 1.0; four had audio-part rates `[0.0]`,
one `[1.0]`. All had unconfirmed `core+0x218=120.0`. Their deck/preview identities
were not yet known. Rekordbox remained responsive. Python syntax and PowerShell
parser checks passed. A subsequent 30-second observation found the same five
objects and exited normally; EXE hash remained unchanged. This was an idle
observation test, not audio or hardware validation.

The observer validates markers and VTables but does not read atomic snapshots.
Object lifetime, mode changes and short transitions remain limits. It can establish
GUI/hardware correlations, not prove that no intermediate value ever reaches the engine.

## Original checklist before the prototype

1. Correlate a known track/deck/original BPM with GUI and DDJ-1000 inputs separately.
2. Validate original/local grid BPM, track changes and unknown BPM; dynamic grids
   may require a position-dependent basis.
3. Distinguish Performance decks from Preview, Export, Sampler and other players.
4. Trace Sync master/slave and manual BPM input separately.
5. Establish whether CDJ-800 units provide audio or DVS/timecode control. Software
   can affect only software playback; DVS may have additional speed/scratch paths.
6. Define bend, scratch, reverse and ramp semantics. Base-request quantization alone
   does not eliminate intentional transient changes to the actual rate.
7. Choose a minimal stable native hook. No JavaScript logging, allocation, file I/O
   or blocking locks in a future audio callback.
8. Add per-deck/track hysteresis, reset on track/mode changes and respect rate bounds.
9. Account for float precision; validate audio with a tolerance separately from UI
   text and internal requests.
10. Test actual audio, both step modes, threshold noise, jumps, multiple decks, Sync,
    Master Tempo, track changes and restoration of Default behavior.

## Tools and sources

Primary evidence comes from the **local** EXE and observations. No third-party patch
or hardcoded offset was copied.

- [Vendor release notes](https://rekordbox.com/en/support/releasenote/): confirmed
  7.2.18 but did not provide an internal tempo API.
- [Frida JavaScript API](https://frida.re/docs/javascript-api/): consulted for the
  abandoned temporary instrumentation.
- [RekordBoxSongExporter](https://github.com/Unreal-Dan/RekordBoxSongExporter):
  researched as a related observation project; no playback hooks or implementation
  were taken from it.

`inspect_binary.py` uses exception unwind entries as function heuristics. Entries
may split a function into several ranges; relevant contiguous code was read fully.
Automatic boundaries can be inaccurate for leaf functions without entries.

## Runtime confirmation and prototype, 2026-09-22

These results concern PID 21800; its addresses must not be reused in later sessions.
The user prepared deck 1 with a 174 BPM track. No DDJ-1000 was connected.

### Live data path

1. Deck 1's `StretchBehavior` was `0x1a9cb799a50`; `owner+0x48` led to
   `DjPlayerCore` at `0x1a9cb71c830`.
2. `artifacts/deck1-174-gui.jsonl` recorded 129 changes around −0.06 to +0.06 pitch
   delta for this owner, while other owners stayed unchanged. The deck was paused.
3. `core+0x220` points to `DjPlayerState` (VTable `0x55716a8`): playback flag `+0x10`,
   position `+0x14` on a 44100 time base, BeatGridHolder `+0x28`, control client `+0x30`.
4. `BeatGridHolder+0x18` points to FormattedBeatGrid. Its `+0x18/+0x20` delimit a
   vector of 16-byte entries: BPM float at +0, position in milliseconds as double
   at +8. The loaded track had 909 entries of 174.0 BPM.
5. Native getters `0x1032900`, `0x1032830`, `0x1032930` confirm layout/conversion.
   The constant at `0x5b52288` is 1000/44100.
6. The control client belongs to UiPlayer's **secondary base**, VTable `0x3bb8068`,
   this-adjustment `0x410`. Primary VTable `0x3bb7e70` would be the wrong type check.
7. `core+0x218` remained 120.0 for the loaded 174 BPM track; it is not the track BPM source.
8. UI Automation Play/Pause changed audio-part rate 0.0 → 1.0 → 0.0; grid stayed 174.0.

### Implemented hook

`native/tempo_hook.cpp` atomically replaces only slot 9 of the StretchBehavior VTable
using `InterlockedCompareExchangePointer`. The slot briefly becomes writable and
then regains its prior protection. No trampolines, modified machine instructions,
Frida or custom audio thread.

The loader checks exact EXE SHA-256 and loaded setter bytes. The diagnostic hook
starts in Default; a separate selection enables quantization. The DLL remains
pinned so retained function pointers cannot reach unloaded code. After Stop, the
controller requires a Rekordbox restart before reinstalling the diagnostic hook.

The hook validates owners and their core/state/UiPlayer/grid types, reads local
beatgrid BPM, quantizes `bpm * (1 + pitchDelta)` and passes `quantizedBpm / bpm - 1`.
It respects native pitch bounds and keeps per-owner hysteresis. Grid, BPM or mode
changes reset hysteresis on the next setter call. The callback does not allocate,
open files or wait on locks. Invalid contexts and concurrent calls pass through
unchanged; diagnostic counters must be checked during tests. `changed`/`quantized`
counts successful quantizations even when the input already lies on the step.
Telemetry and external snapshots are not atomic whole-process states.

### Measured results

- C++ quantizer tests passed over 48000 sweep checks plus hysteresis, mode/track-BPM
  changes, bounds and NaN cases. MSVC 14.50 `/W4 /WX` build passed.
- Default: GUI request 175.37 reached the setter as `delta=0.00787353515625` and
  passed through bit-identically.
- Integer: the same request produced `delta=0.005747126415371895`, nominal
  174.999999996 BPM; audio-part rate 1.0057470798492432 = **174.999991894 BPM**.
- Tenth: audio-part rate 1.00804603099823 = **175.400009394 BPM**.
- Hysteresis: starting at 175, 175.59 stays 175 and 175.61 becomes 176; in reverse,
  175.41 stays 176 and 175.39 becomes 175.
- Twelve live cases passed: both steps, bidirectional hysteresis, ±6% jumps and
  Default restoration. Audio-part BPM tolerance 0.0001; all checked unchanged grid
  identity/BPM 174. Evidence: `artifacts/live-verification-20260922-020710.jsonl`.
- Actual GUI dragging produced 51 setter calls, then 46 in a separate run. The
  second run captured 218 external snapshots, with audio-part BPM only 174 through
  180 at integer steps within tolerance. Evidence: `artifacts/gui-drag-quantized.json`.
- After these tests: 117 hook calls, 112 quantizations, no context bypasses, rejected
  owners or concurrent calls. All logged calls came from thread 20972.
- Deck display also showed quantized tempo (e.g. 175.40); GUI percent may still show
  the raw request and is not authoritative for the audio rate.
- The external control window opened/connected; 0.1 / 1 / Default selections matched
  native telemetry. The Windows Store Python alias had to be resolved to the actual
  executable before entering the GUI loop.
- Final state: Default, deck 1 at 174 BPM and paused; original EXE hash unchanged.
  Diagnostic DLL SHA: `9cf1a63b2674ae6781aa58c2a5d0b6fcb990cf667464460451519094a81a7538`.

### Remaining limitations at that stage

Internal engine rate was established statically and live; independent output-audio
measurement was absent. No DDJ-1000 inputs were tested. A shared path suggests
coverage but does not prove it. The role of CDJ-800 units remained unresolved.
Multiple loaded decks, Sync master/slave, track changes, dynamic BPM and
Export/Performance changes needed separate tests. UiPlayer checks/owner lists are
conservative guards, not proof for every mode. The PowerShell UI checks PERFORMANCE
when activating, not continuously; the historical diagnostic workflow required
removing the hook before changing modes.

At this stage, selections, Default and Stop did not request recalculation; the next
regular tempo input applied changes. Bend, scratch, reverse, ramps and DVS remained
additional paths. Small relative increments could round back to the same step.
The prototype did not quantize every instantaneous playback rate in all situations.
Stop was implemented but a complete removal/restart cycle had not been run in the
prepared session. No Frida was used for these new tests. Responsiveness did not
establish long-term stability.

Additional primary references:

- [Microsoft InterlockedCompareExchangePointer](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-interlockedcompareexchangepointer)
- [Microsoft DLL Best Practices](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-best-practices)
- [Rekordbox 7.2.14 manual: Performance operation](https://cdn.rekordbox.com/files/20260409151936/rekordbox7.214_manual_EN.pdf)

## Control window may be closed

Closing the control window no longer removes the hook. Its state lives in the pinned
DLL; no external process is needed. Reconnecting reads `rbqTelemetry.mode` instead
of resetting Default. Default disables quantization; `Set-TempoStep.ps1 -Step Stop`
remains explicit removal for the diagnostic hook.

PowerShell parsing passed; no audio/quantization/DLL change was made for this UI
adjustment. Closing with an active hook was not retested because PID 21800 already
reported `installed=false`, 446 historical calls, 441 quantizations and no bypasses.
That old session needed a restart under the reinstall guard.

A permanent file patch was not yet implemented at this stage. Read-only inspection
found eight PE sections, a section table filling SizeOfHeaders (1024 bytes), entry
RVA `0x2711ccc`, 41 import descriptors and an Authenticode certificate table.
A startup loader would require PE-layout checks, original restoration and
initialization before decks exist. No program files were changed during this check.

## Permanent startup and embedded setting, 2026-09-22

### Installation and PE changes

After tests on local copies, the requested patch was installed under
`D:\Programs\rekordbox 7.2.18`. The original was retained as
`rekordbox.exe.rb-bpm-original` with the verified original hash.

- Patched EXE SHA: `297ab491ae745191b09ee72612be6d4c61075788740fb62140f93b0628337a4f`.
- Initial installed DLL SHA: `d4edc5ff31dbcdff25cd0dfc8809092dc0ca1fcd9c2c7f2ae3f9e5aeb2297010`.
- `tools/pe_startup_patch.py` adds a `rbqBootstrap` import and sections `.rbq`
  (RX, entry `0x6291000`) and `.rbqdat` (RW, import/unwind data `0x6292000`). No RWX section.
- New entry reserves 40 stack bytes, calls bootstrap, restores the stack and jumps
  to original entry `0x2711ccc`. Initialization is outside DllMain/loader lock.
- The full section table requires 512 additional header bytes. Raw offsets,
  including debug data, shift; original section RVAs and `.text` bytes are retained.
  The runtime-function table is copied and extended with x64 unwind information
  for the new entry; PE checksum is recalculated.
- The Authenticode directory reference is removed. The patched EXE has no valid
  vendor signature; it does not pretend otherwise.

The final layout first ran under the Windows loader in our own test host: exit 71
unpatched, 0 after bootstrap, including header expansion. An earlier design with
imports in RX failed on loader writes; separate RX/RW sections replaced it before
Rekordbox installation.

`tools/patch_app.py` verifies original/package hashes, creates a verified backup,
places extension files first and atomically replaces the EXE last. Install, repeat
and byte-exact restoration passed on a working copy. Restoration refuses an EXE
changed to an unknown state. `Patch-Rekordbox.ps1` requires Rekordbox to be closed.

### Automatic hook and setting

`native/tempo_extension.cpp` initializes existing quantization at startup. Valid
loaded UiPlayer contexts enter the bounded owner list on their first setter call;
no external scan/helper is needed. A GUI-thread `WH_CALLWNDPROC` hook recognizes
JUCE Preferences by its English title or the retained German title alias. Initially,
a native panel below the category list exposed BPM / Tempo Step by subclassing the
dialog, without changing JUCE class layout or track data. This placement was checked
at 800×800, 96 DPI and hidden if insufficient space; other DPI/languages were open.
It was subsequently replaced by the Extensions page described below.

`rb-bpm.ini` beside the EXE stores `Step=default|0.1|1` on the GUI/control path,
not inside the tempo callback. Setting changes re-request each known matching
grid's last raw input through native `0x2c07ef0`, using its existing lock/task path.
These decks update without another fader move; unknown contexts wait for a first call.

During temporary UI-test injection, Windows removed the window hook when its
installing helper thread exited. The diagnostic bootstrap now transfers ownership
synchronously to the GUI thread. The final EXE bootstrap already runs there and
needs no remote thread or persistent helper.

### Confirmed runtime results

- MSVC `/W4 /WX /MT` build passed; the DLL needs no separate runtime installation.
  Quantization matches the previously tested core.
- Before installation, PID 7152: original BPM 174, raw GUI request 175.37, integer
  audio-part BPM 174.999991894. Changing the embedded setting to 0.1 immediately
  yielded 175.400009394 without another fader move; grid stayed 174.
  Evidence: `artifacts/embedded-settings-live.json`.
- First normal installed launch: PID 4424 loaded the extension from the Rekordbox
  directory. Before the second launch: 1123 calls, 1098 quantizations, no rejected
  contexts, bypasses or concurrency. INI and panel showed 0.1; deck 1 was paused,
  grid 174, base request 173.5 BPM.
- Normal close/restart of the same patched EXE: PID 21556. Before any tempo input,
  hook installed, mode 1 (0.1), counters 0; panel also showed 0.1. No later injection
  or controller activation was used.
- New inputs then produced 81 calls/81 quantizations with no bypasses, rejected
  contexts or concurrency; grid remained 174, demonstrating automatic owner discovery.
- `tools/preferences_probe.ps1 -Action Status` reads the panel;
  `Set-TempoStep.ps1 -Step Status` reads the hook. Both are optional diagnostics.
- Final hash/INI/hook/deck snapshot: `artifacts/permanent-restart-verification.json`.
  Reapplying 0.1 through the optional controller increased the setter count to 82;
  the player thread processed the request. With modal Preferences open, Performance
  is absent from UI Automation and external activation is refused with guidance
  to use the embedded panel. The external call passed with Preferences closed.

Audio evidence remains internal engine measurement, without an independent output
recording. Hardware faders, Sync and DVS were untested. UiPlayer checks do not
completely separate Performance/Export; select Default before leaving Performance.

Primary references for PE layout and Windows lifetime:

- [Microsoft PE Format](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)
- [Microsoft SetWindowSubclass](https://learn.microsoft.com/en-us/windows/win32/api/commctrl/nf-commctrl-setwindowsubclass)
- [Microsoft Terminating a Thread](https://learn.microsoft.com/en-us/windows/win32/procthread/terminating-a-thread)

## Moving settings to Extensions → RB PLUS, 2026-09-22

The setting moved from below the category list to its own Extensions page.
`native/preferences_tabs.h` adds native Windows tabs STEMS, Video, Lighting and
RB PLUS. The first three use Accessibility to activate existing Rekordbox pages;
RB PLUS displays its own content. Other categories hide the added tabs/content.

UI Automation runs on a windowless COM MTA thread inside Rekordbox only while
Preferences is visible; messages marshal GUI changes to the GUI thread. No external
helper is needed. This follows [Microsoft's UI Automation threading guidance](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-threading).
Controls are repositioned only when the selection changes. Controls are discovered
fresh because JUCE replaces them during category changes without reliably invalidating
old references.

### Development failure and correction

Development DLL SHA `7c03cfc426bec8052a62fe99f984e41e001d9c017b855923c39fc72f7ba1a3e2`
crashed on a dialog/page change at 08:24:29. No matching Rider debug session, PDBs
or local WinDbg/CDB were available. Direct minidump inspection was compared against
disassembly of the loaded DLL:

- Exception `0xc0000005`, read at address 0, thread 22680.
- `rb_bpm_patch.dll+0x24a1`: `mov rax, [rcx]`, `RCX=0`.
- Previous call: `GetCurrentPatternAs`, pattern ID 10015 (TogglePattern), successful
  HRESULT but returned interface pointer 0.
- The following unchecked call would invoke `get_CurrentToggleState`.
- Fix: check HRESULT **and** interface pointer, including the related Invoke path.
  Missing/disappearing controls are skipped.

This was an extension UI bug. Local dump:
`f9eae4b1-53d9-4998-a855-8a965f1fd58d_7.2.18.0311_64.dmp` in the Rekordbox crash
directory. No external helper workaround was introduced.

### Installed and tested correction

- DLL SHA: `2b955d9d4ffe6b40fb6c02570498aec5c7fb096834d8a0bbc85bfefc2f2c7a55`.
- EXE/backup remained unchanged. The installer gained verified DLL updates preserving
  the INI; update, repeat and restore passed on a local file copy.
- `/W4 /WX` build passed; PID 8860 automatically loaded the corrected hook.
- Navigation Video → Lighting → STEMS → RB PLUS → Audio → RB PLUS → View → RB PLUS
  passed selection/visibility checks at every step.
- All three BPM modes matched hook telemetry/INI; final mode restored to 0.1.
- Five further close/reopen cycles passed and Rekordbox remained responsive. Six
  panels in total; no UI creation, COM or Invoke errors in final telemetry.
- Evidence: `artifacts/extensions-navigation.json`, `artifacts/extensions-verification.json`.

Tempo setter/quantization were unchanged; hardware/mode limitations remained.

## Actual mouse selection in the RB PLUS dropdown, 2026-09-22

The user reported that clicking opened the list but clicking an option closed it
without applying the choice; arrows and Enter worked. Previous tests used control
messages and missed this difference.

### Runtime evidence

No Rider debug session/run configuration existed for the native extension. Instead,
a bounded Windows message trace on the GUI thread used `native/ui_input_probe.cpp`,
a separate diagnostic tool excluded from the permanent installation.

In PID 8860, the `ComboLBox` popup was not a Preferences child (`IsChild=false`).
An actual click on option 2 left selection 1. `WM_LBUTTONDOWN` reached the popup,
then the combo lost focus to Preferences and emitted `CBN_SELENDCANCEL`. RB PLUS
stayed visible, locating the failure in popup input rather than saving/tab visibility.

An A/B experiment forwarded only this popup's mouse messages directly to its native
window procedure before the modal filter. The same click then selected option 2;
hook mode/INI also became 2 / 1 BPM. This established incompatibility with the host's
modal input path. Evidence: `artifacts/combo-mouse-before.json`,
`combo-messages-before.json`, `combo-mouse-bridge.json`, `combo-messages-bridge.json`.

### Permanent correction

`native/preferences_combo.h` registers a thread-local `WH_GETMESSAGE` hook for the
panel's lifetime. It handles only mouse messages for its own visible popup while
Preferences is active/enabled and the combo focused. Other windows/keyboard input
stay outside this path. Only `PM_REMOVE` messages are delivered once, then replaced
with `WM_NULL` before returning to the message loop. See [Microsoft GetMsgProc](https://learn.microsoft.com/en-us/windows/win32/winmsg/getmsgproc)
for the distinction between removed and inspected messages.

The native Windows combo still processes selection, outside clicks and closing.
The hook is removed when the panel is destroyed. The 400 ms setting synchronization
pauses while the list is open so it cannot reset an in-progress choice.

`/W4 /WX` build passed. Installed DLL SHA:
`5175314bf0b0f9dc0c07637577bca080625c660f60ac8fd2cf5809f1c812de0d`.
EXE patch and tempo engine were unchanged. Rekordbox was closed normally with empty,
stopped decks, the DLL updated and Rekordbox restarted. PID 23684 loaded only the
permanent extension, not the temporary diagnostic DLL.

### Verification using actual input

`tools/preferences_mouse.py` uses real Windows mouse/keyboard input, validates the
process under the click target and restores the cursor. `tools/verify_preferences_input.py`
compares selection, hook mode and INI.

- All three options selected with the mouse, hovering 700 ms (longer than the sync
  interval): passed.
- Escape and outside clicks cancelled without changing the selection and closed the list.
- All three options selected by keyboard after opening with the mouse: passed.
- Final selection restored to **0.1 BPM**.
- Evidence: `artifacts/combo-input-verification.json`.
- Three further close/reopen cycles followed by mouse selection passed. Four combo
  hooks installed, three removed, no installation errors; exactly one remained for
  the open panel. Rekordbox stayed responsive.
  Evidence: `artifacts/combo-lifecycle-verification.json`.

These checks concern settings input. The audio engine was unchanged for this fix;
all documented hardware limitations still applied.
