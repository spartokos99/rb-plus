# Version maintenance without losing older support

A request to support a new Rekordbox version at a supplied path includes detection,
investigation, necessary changes, tests and an updated handoff.
**Support for new versions is additive.**

## Currently verified builds

| Build | Platform | Status | Evidence |
| --- | --- | --- | --- |
| 7.2.18.0311 | Windows x64 | Supported with documented limitations | [Report](reports/7.2.18.0311-windows-x64.md) |

`builds.json` is the machine-readable registry. A product name such as “7.2.18”
is insufficient: identity includes exact SHA-256, architecture and verified code
locations. Unknown files are rejected even if their displayed version matches.

## 1. Initial read-only check

```powershell
.\Test-RekordboxCompatibility.ps1 -Path 'D:\Programs\rekordbox NEW'
# Alternative:
python tools/check_compatibility.py --path 'D:\Programs\rekordbox NEW\rekordbox.exe'
```

The checker does not start Rekordbox or write files/process memory. Exit 0 means
a known build with matching static properties; exit 2 means unknown, inconsistent
or unreadable. For patched installations it also checks the manifest, original
backup and DLL integrity. A newly compiled DLL can match its manifest without
being a historically tested release: inspect `extension_tested_release` separately.
`runtime_tested_this_run` is always false.

A successful check does **not** automatically approve a new version and is not
an audio/hardware test. For an unknown build, investigate using
`tools/inspect_binary.py --exe <EXE>`; do not load the old native hook.

## 2. Preserve baselines

- Preserve/tag existing profiles and source before changing them. The initial
  baseline is `rb-plus-7.2.18.0311-baseline`.
- Keep legally available local original EXEs/test copies per build under
  `fixtures/<build-id>/`; verify their hashes. This directory is not committed.
- Add new offsets, ABI and layouts as another backend/adapter. Change shared
  quantization and UI only if old backends still work or get separate implementations.
- Before adding a second build, extend native/Python backend selection and the
  installer to use exact build identities. Do not simply retarget hardcoded values
  in `tempo_hook.cpp`, `tempo_extension.cpp`, `observe_tempo.py`, `tempo_control.py`
  and `patch_app.py` to the new build.
- From then on, isolate packages under `build/packages/<build-id>/` and invoke the
  installer with the matching profile/package. `build/permanent` is currently the
  legacy path for 7.2.18 only. Never present a new package as an old one.
- Keep old profiles, backend sources and test cases on the current branch.
  A Git tag alone does not replace working version selection.

## 3. Establish the new pipeline before modifying it

Trace the central tempo request through to the audio rate. Recheck signatures,
VTable slot, calling convention, relative pitch representation, track/grid access,
limits, threads and the request function used to reapply a setting. Do not shift
old RVAs by a guessed offset.

Verify native settings and input paths separately. UIA names, categories, handles,
COM behavior and popup input can change independently of the audio engine.
Approve profiles only with evidence and tests; record unconfirmed candidates as such.

## 4. Required test matrix

Run for every new build and as a regression for **every** previously supported build:

| Area | Check / success criterion |
| --- | --- |
| Identity | Unchanged original, exact hash/architecture; other builds rejected |
| Offline | Python tests, quantization/hysteresis, `/W4 /WX` native builds |
| PE/package | On a local copy: prepare, install, repeat, DLL update, restore original SHA; preserve INI/backup |
| Startup | Normal startup loads exactly one matching extension; no helper required |
| Engine | Default passes through; integer/tenth modes with original BPM 174 or another documented track; measure audio-part rate |
| Limits/hysteresis | Slow sweep, threshold noise, jumps, min/max; no unexpected intermediate values |
| Live switching | Previously detected deck applies a new mode without another fader movement |
| Metadata | Original/grid BPM unchanged; no new analysis/database write paths |
| Inputs | GUI fader, manual BPM, DDJ-1000 and other available hardware; evidence or explicitly untested |
| UI | Extensions → RB PLUS, all modes using actual mouse and keyboard, Escape/outside clicks, original tabs, category changes |
| Lifetime | Repeated Preferences close/reopen, restart with saved mode, no extra hooks/crashes |
| 4Deck Horizontal | Independent wave/deck orders: all 24 plus Default; real components/numbers, input and drop targets; other layouts unchanged, return/restart reapplies selections |
| Other paths | Multiple decks, track/mode changes, Sync/DVS, bend/scratch/reverse; retain open limitations separately |
| Load | CPU/GUI responsiveness and audio stability during a documented extended test |

Report only tests actually performed as passing. If historical installations or
hardware are unavailable, complete independent work and identify the missing
regression specifically. Do not remove existing support to conceal a gap. Never
interrupt a live performance for testing.

`tools/verify_live.py` controls the older diagnostic hook and requires specific
preconditions (see HANDOFF). Adapt that path or add an appropriate integration
test for a new permanent backend; never install both hooks together. Mouse testers
move the real cursor and change settings; use only in an appropriate test state.

## 5. Finish

- Maintain `compatibility/reports/<build-id>.md` with dates, original/patched/DLL
  hashes, evidence, results and remaining limitations.
- Update `builds.json`, this matrix, README and HANDOFF additively.
- Keep new and old packages distinguishable, reproducible and usable together.
- Report the new version, preserved old versions, tests actually repeated and
  specific limits. Do not claim blanket hardware coverage.
- Commit source and reports, never Rekordbox EXEs, databases or dumps to Git or
  GitHub releases. Our own DLLs may be released separately only when a release is
  requested and the exact build has been tested.
