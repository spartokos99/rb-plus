# Feasibility: waveforms at 120 Hz

**Archived: the user abandoned this idea on 2026-09-22.**
This is historical research, not an active task or planned feature.

Investigation dated 2026-09-22 for Rekordbox 7.2.18.0311, Windows x64.
Scope: investigation only, no implementation or activation.

## Result

Technically plausible, but no verified patch delivering 120 distinct waveform
frames per second. The settings path and parts of the OpenGL drawing path were
identified. Setting `RenderDelay=120` alone proves nothing: that value was already
saved. The actual waveform frame rate and limiting path still need measurement.

Rekordbox was not running during this investigation. It was not started, injected,
patched or reconfigured. Only existing files and Windows system information were
read; this document records the findings.

## Local findings

- Windows reported AMD Radeon RX 6900 XT, 3440 × 1440, 240 Hz. This was the reported
  display configuration, not a measurement of Rekordbox's frame rate.
- `%APPDATA%\Pioneer\rekordbox6\rekordbox3.settings` contained `RenderDelay=120`,
  `BasicOpenGL=0` and `DisableOpenGL=0`.
- Installed EXE and extension remained identical to the previous BPM/dropdown patch:
  - EXE: `297ab491ae745191b09ee72612be6d4c61075788740fb62140f93b0628337a4f`
  - DLL: `5175314bf0b0f9dc0c07637577bca080625c660f60ac8fd2cf5809f1c812de0d`

## Static clues in this exact binary

Addresses are RVAs, not absolute runtime addresses. Mappings come from disassembly
and retained MSVC RTTI, not vendor symbols.

| RVA | Finding |
| --- | --- |
| `0x5bcf678` | RTTI `ViewWaveformDrawRateComponent` |
| `0x39ec008` | Listener VTable; callback at `0x1c966b0` |
| `0x1c966b0` | Selection handler sets 120 or 40 through `0x1cda120`, depending on branch; also toggles a Boolean option |
| `0x1cda090` / `0x1cda120` | Read/write setting with string ID `0x5e35640` |
| `0xb2f650` | Initializes this string ID with `RenderDelay` |
| `0x39ff478` | Default value 120 |
| `0x1746e50` | Reads `RenderDelay`, caps at 60 and computes integer `1000 / rate`; alternative branch uses 30 |
| `0x1915f40` | Another consumer capped at 60, with `1000 / rate` |
| `0x1d578a0` | OpenGL drawing path of RTTI class `djplay::OpenGLRenderComponentImpl` |
| `0xfca970` / `0xfca980` | Setter/getter of a delay field in `rb::OpenGLCachedImageDelay` |
| `0xfbe3d0` / `0xfc9940` | Reference `wglSwapIntervalEXT` |

`0x1746e50` is called through `0x24ec3b0` and MainComponent accessor `0x173e0e0`.
The first path belongs to the main UI; the second is in the VideoPanel code area.
**These caps do not establish a 60 FPS limit for waveforms.** The OpenGL waveform
output must be traced separately.

Integer milliseconds are also not a precise 120 Hz clock: `1000 / 120` yields
8 ms, or 125 Hz before other limits. True 120 Hz averages 8.333 ms and needs
appropriate presentation through VSync/frame pacing.

## External sources considered during the investigation

- The [Rekordbox 7 manual, page 226](https://cdn.rekordbox.com/files/20260409151936/rekordbox7.214_manual_EN.pdf)
  describes Waveform Drawing Rate and the higher computing cost at higher rates,
  but does not guarantee 120 FPS there.
- The [Smooth Mixer Patcher](https://github.com/SebitosMixx/rekordbox-smooth-mixer-patcher)
  describes adjustable UI limits and a 120 FPS preset for 7.2.18. It targets mixer/UI
  updates; its author notes that OpenGL waveforms may already run more smoothly
  independently. This suggests separate paths but does not prove 120 Hz waveforms
  on this machine. It was not executed.
- The [JUCE OpenGL interface](https://github.com/juce-framework/JUCE/blob/master/modules/juce_opengl/opengl/juce_OpenGLContext.h)
  distinguishes continuous drawing, requested repaints and swap interval. That
  distinction matters for investigation, but the current library's behavior cannot
  be assumed to match Rekordbox's embedded fork.

## Unresolved at the time of abandonment

1. Capture actual frame times with moving waveforms, distinguishing new content
   from repeated presentation of the same frame.
2. Map the active waveform render thread, scheduler and swap interval to the exact
   call path before choosing any modification.
3. Determine whether 120 FPS is already achievable or which limit prevents it.
4. If the user ever requests implementation again and a change is necessary,
   integrate a version-specific option under RB PLUS and verify frame pacing and
   audio stability with multiple decks.

No waveform frame-rate hook was implemented and no 120 Hz success was claimed.
