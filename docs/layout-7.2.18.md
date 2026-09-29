# Configurable order in 4Deck Horizontal

This backend is restricted to the original SHA in `compatibility/builds.json`,
Rekordbox 7.2.18.0311 x64. Both settings apply only to Performance and layout
`0x14` (4Deck Horizontal). Other layouts use the original function.

`[Layout] WaveOrder=3124` describes rows from top to bottom; `DeckOrder=3214`
describes top left/right, then bottom left/right. `default`, missing or invalid
values leave the arrangement to Rekordbox. The UI offers all 24 permutations
and a separate **Default (Rekordbox)** option.

## Static and read-only runtime evidence

Addresses are EXE RVAs, not absolute process addresses:

| Element | Established path |
| --- | --- |
| Main window | Singleton `0x5d1f260`, MainComponent VTable `0x3818028` |
| Performance | MainComponent `+0x428` → ApplicationMode (`0x3690870`), flags `+0x98`, mask 2 |
| PlayerPanelL | MainComponent `+0x490` → UiManager `+0xe0` → PlayerComponent (`0x384ec68`), child with VTable `0x384f080` |
| Layout event | PlayerPanelL `resized`, VTable slot 35 → `0x180ed40`; layout state `+0x5b8` |
| Geometry | JUCE Component: parent `+0x30`, Rectangle<int> `+0x38`, children `+0x58/+0x64` |
| Deck rectangles | PlayerPanelL `+0x5c8`, `+0x5d8`, `+0x5e8`, `+0x5f8`, indexed by logical deck ID |
| Deck layout | Helpers `+0x4f8..+0x510`, panel backlink `+0`, deck ID `+8`; `0x181c820(helper, layout, rect, visible)` |
| Highlights | Active/drop arrays `+0x640/+0x650`, bounds through `0x2aeac60(component, rect)` |
| Waveform sources | Unchanged logical array of four `+0x5a8/+0x5b4`; WidgetWaveView component at source `+0x648`, VTable `0x38b4668` |
| Waveform pairs | PlayerPanelL `+0x3b8/+0x3c0`, VTable `0x38b7aa0` |
| Assigning sources | `0x194e340(pair, slot, source)` → `0x19485b0`, using the native renderer CriticalSection; slots 0/1 per pair |
| Waveform layout | Pair `resized` at `0x194bea0` positions and reparents the actual components according to their sources |
| Numbers | Pair `paint`, slot 26 → `0x194b710`; four native number images `+0x1b0..+0x1c8` |

The original resize runs first and supplies the four current slot rectangles.
RB PLUS then assigns existing deck helpers to these slots and updates the
per-deck rectangles and both highlights. Audio players, tracks and IDs are not
swapped. Waveforms use existing sources and native locks; the owner fields
`PlayerWaveView+0x158/+0x160` are unchanged. Runtime observation confirms changed
parent/bounds values of actual waveform components, not just altered text.

The original horizontal drawing path supports numbers only in Rekordbox's built-in
orders. For a custom order, RB PLUS draws the same background and four number
images in the selected order. Native Graphics calls: color `0x29ea970`, rectangle
`0x29e8270`, ImageAt `0x29e67d0`; background color `0x5d54f08`, native positions
x=0/w−12, y=19/67. This runs in the host's paint context on its render thread;
it does not change controls, parents, bounds or UIA there. Selections are published
atomically. Layout and INI changes run on the GUI thread. Other modes/layouts
retain the original paint function.

All used function entries and both original VTable slots are checked before
installation. Object types, backlinks and array sizes are checked before layout
changes; invalid/incomplete contexts are skipped. Like the tempo hook, the DLL
stays loaded until the process exits.

## Reproducible checks

- `native/build.cmd`: quantizer/hysteresis tests, all 24 permutations,
  serialization round trips and invalid INI values.
- `tools/observe_layout.py --pid ...`: read-only snapshot of sources, actual
  waveform components, deck rectangles and highlights.
- `tools/verify_layout_input.py --pid ... --preferences ...`: in a paused 4Deck
  test session, exercise all selections with actual input, verify positions,
  Escape/outside clicks and keyboard input. Restores the original selections.
- `tools/verify_preferences_input.py`: regression of the existing tempo dropdown.

Private screenshots, disassembly and component snapshots are under `artifacts/layout-*`;
vendor data stays out of Git. Actual coverage and open limits are in the version report.
