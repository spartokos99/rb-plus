RB PLUS v1.0.0 for Rekordbox 7.2.18.0311 / Windows x64

INSTALL
1. Extract the entire ZIP into a folder on the destination laptop.
2. Close Rekordbox normally.
3. Right-click Install.cmd and choose Run as administrator.
4. Select rekordbox.exe from your own 7.2.18 installation.
   Example: C:\Program Files\Pioneer\rekordbox 7.2.18\rekordbox.exe
5. Start Rekordbox normally after installation completes.
6. Open Preferences -> Extensions -> RB PLUS -> BPM / Tempo Step.
   Choose Default, 0.1 BPM or 1 BPM.

ARRANGE WAVEFORMS AND DECKS
In Performance -> 4Deck Horizontal, RB PLUS offers two independent selections:
  Waveforms (top to bottom): the order of the four waveform rows.
  Decks (top / bottom): top left - right / bottom left - right.
Each list supports all 24 orders. Selections apply immediately and are restored
on startup and when returning to this layout. Default (Rekordbox) restores the
native arrangement for that list. Other layouts keep their normal arrangement.
Logical deck IDs stay the same; track information, controls and drop targets
follow their deck.

Python, Visual Studio and an Internet connection are not required on the target
laptop. The bundled Python runtime is isolated and is not installed globally.
Setup does not start Rekordbox or terminate running processes. No external
helper needs to stay open during playback.
New installations use Default; existing settings are preserved. You may remove
the extracted folder after installation. Keep the ZIP for later uninstallation.
Setup grants local Windows users write access to rb-bpm.ini so selections
can be saved under Program Files without running Rekordbox as administrator.
Permissions on the EXE, DLL and original backup are not broadened.

COMPATIBILITY AND ORIGINAL BACKUP
Only the exact verified build 7.2.18.0311 is accepted. A different EXE is rejected
even if its displayed version matches. Check-Compatibility.cmd checks the selected
installation without changing it.
The package contains no Rekordbox EXE, music or database. The patched EXE is
prepared locally from your own installation. These files are created beside it:
  rekordbox.exe.rb-bpm-original  - verified original; never overwrite it
  rb_bpm_patch.dll              - RB PLUS extension
  rb-bpm.patch.json             - installation checksums
  rb-bpm.ini                    - saved tempo and layout selections
Track BPM, metadata, beatgrids and the database remain unchanged.
The file patch removes the now-invalid EXE vendor signature reference.
Vendor licenses and subscriptions remain required as before.

UNINSTALL
Close Rekordbox, run Uninstall.cmd as administrator and select the same EXE.
This restores the original byte for byte. The original backup and INI are kept.
An EXE changed by another update is not overwritten.
Never delete the DLL separately while the EXE is patched.

KNOWN LIMITATIONS
Experimental patch for the live base tempo request of Performance decks.
Select Default before leaving Performance mode.
DDJ-1000 was not connected during testing. DVS/CDJ-800, Sync, multiple loaded
decks, track/mode changes and long sessions are not fully validated across the
tempo matrix. Jog bend, scratch, reverse and start/stop ramps use additional
rate paths. Dynamic beatgrids are evaluated on tempo calls, not every position
change. At most eight player addresses are tracked per session; unknown or
concurrent contexts pass through unchanged.
UI tests used English Preferences at 96 DPI. High DPI and other host UI
languages are untested. Quantization uses native floats and hysteresis
(half a step plus 10% of the step width).
The layout implementation was tested locally on 2026-09-28: both orders, numbers,
mouse input for all four waveforms/decks, layout switching and internal audio
rates. Release-specific checks are listed in the included version report.
No test has been performed on the destination laptop; hardware limitations remain.
Details: compatibility\reports\7.2.18.0311-windows-x64.md.

PACKAGE VERIFICATION AND LICENSE
SHA256SUMS.txt lists checksums for the package files. A separate .zip.sha256
file is provided with the download to verify the whole archive.
The isolated Python runtime is bundled from local CPython files. Its license
and notices are in runtime\LICENSE.txt. No third-party Python packages from the
development environment are included.
Project and release: https://github.com/spartokos99/rb-plus/releases/tag/v1.0.0
