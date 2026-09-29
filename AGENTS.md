# RB PLUS: Instructions for coding agents

## Start here

Read `HANDOFF.md` first, then `compatibility/README.md`. This private repository
contains our source code. Rekordbox binaries, music, databases, dumps and local
measurements must stay out of Git. Build using the scripts under `native/`;
the solution is for navigation.

## Product and boundaries

- Windows x64, additional page **Preferences → Extensions → RB PLUS**.
- Default, 0.1 BPM and 1 BPM apply only to the live base tempo request of
  Performance decks. Verify the audio rate, not just displayed text.
- Do not change track BPM, metadata, beatgrids or databases.
- Vendor licenses/subscriptions and their checks are outside this project's scope.
- The user explicitly abandoned the waveform/120 Hz idea. Do not resume it unless
  the user requests it again.
- Preserve known limitations and untested hardware honestly in README and version
  reports. A known EXE hash is not a complete runtime test.

## When the user names a new Rekordbox version

An instruction such as “I installed a new version at <path>; make sure it works
with our patch” activates the complete workflow in `compatibility/README.md`.
The user does not need to repeat previous findings or list individual checks.

1. First perform a read-only check of the supplied path using
   `Test-RekordboxCompatibility.ps1` and identify the exact build. Do not inject
   or patch unknown builds using existing addresses.
2. Investigate the new version's tempo/playback path before implementation.
   Existing signatures are clues; ABI, object offsets, VTables, threading,
   grid access and reapplication must be supported by evidence.
3. Add support **additively**. Do not replace old `compatibility/builds.json`
   entries or working backends with new offsets. Before supporting a second build,
   make the currently fixed native/Python backends separately selectable using
   exact hash matching, with no fallback to the “latest” version. Keep packages
   separate per build. Never rewrite a global `EXPECTED` to exclude old builds.
4. Test the new and all previously supported versions against the matrix.
   Separate historical results from tests actually repeated now. If an old local
   EXE or hardware is unavailable, continue independent work and report the
   specific missing check. Do not invent successful regressions.
5. Perform runtime tests/installation only after matching static checks. Check
   playback before restarting; do not interrupt a running set. Close normally,
   never blindly terminate processes. Preserve backups and the INI.
6. Update the profile, report, matrix, HANDOFF and README. Mark a build supported
   only after meeting the specified criteria; name remaining limitations and
   preserve prior support.

Routine analysis, local builds, fixes and tests are part of this task. Do not
request repeated confirmation for work already authorized in the session.
Missing test data/hardware calls for a specific question, not a general approval
stage. GitHub pushes must stay within the authorized scope.

## Runtime and UI rules

- No global input hooks. The dropdown fix is limited to its own popup and GUI thread.
- Keep UI Automation on the MTA worker and GUI work on the GUI thread.
- Check COM success **and** a non-null interface. JUCE may return `S_OK` with null
  for disappeared controls; a previous crash dump established this.
- No long-lived UIA button caches: category changes create new controls.
- Test UI with real mouse clicks. `CB_SETCURSEL` plus `WM_COMMAND` masked the
  original popup bug. Also test keyboard input, Escape, outside clicks and
  closing/reopening. Restore the cursor position afterwards.
- Do not use Frida instrumentation again: an earlier probe crashed Rekordbox.
  Prefer static analysis and a read-only observer.
- The native DLL stays loaded for the process lifetime. Never unload a hook
  that another thread may still reach.

## Checks and handoff

For build/compatibility tooling changes run `python -m unittest discover -s tests -v`,
`native\build.cmd` and `native\build-extension.cmd rb_bpm_patch`. For host/engine/UI
changes also run the affected integration checks from the matrix. Do not alter
playing decks indiscriminately with diagnostic helpers.

Before committing, inspect `git diff --cached` and the file list for generated
binaries, private data, credentials and large artifacts. Never use `git add -f`
for vendor files. Never overwrite the existing vendor backup.
