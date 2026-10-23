# Overrides of the game's files

Fixes the Switch needs in the game itself (the `chupathingyce` submodule),
each kept here as a whole copy of the fixed file until upstream has it. The
folder is laid out as the game is: `source/memory/data.c` here stands in for
the submodule's `source/memory/data.c`. The build (`port/switch/build.py`)
compiles an override in the game file's place, with the game file's flags,
so the submodule stays at upstream's commit and the workflows need nothing.

`python3 tools/switch_overrides.py` lists the overrides; `--diff` shows each
one's change against the submodule's file. The Port tests workflow runs it,
and it fails when an override no longer differs from upstream's file (upstream
has the fix: repin the submodule, delete the override and its entry here),
when its game file is gone, or when it is not listed below.

Every override is listed here, with what it fixes and where it is going.

## source/memory/data.c

`data_initialize` records the address of an array's elements translated
(`xbox_address`) under `HALO_ADDRESS_TRANSLATED`, not under `HALO_64BIT`
alone. In the 32-bit build with the window moved (the Switch) it held the raw
pointer, while the port's checks of an array (`game_state_data_array_good`
and the saved game's `game_state_image_data_valid` in `game_state.c`,
`lights_port_recover` in `object_lights.c`) compare the field with
`XBOX_ADDRESS(data + 1)`, so they never matched: every checkpoint and
cutscene skip was refused ("the saved game is not taken: cached object render
states is a data array whose elements are elsewhere") and the map started
over, and the lights array was taken for broken at every map start and
emptied ("the lights were out of order and all of them were let go"): no
flashlight, headlights or plasma glow.

- Base: upstream `d547dd7c` (the submodule's pin).
- Upstream: the commit `86735cd0` on branch `window-data-arrays` of
  `thelinkin3000/chupathingyce`; its pull request is still to be opened.
