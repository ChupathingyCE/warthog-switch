# Overrides of the game's files

Fixes the Switch needs in the game itself (the `chupathingyce` submodule),
each kept here as a whole copy of the fixed file until upstream has it. The
folder is laid out as the game is: `source/memory/data.c` here would stand in
for the submodule's `source/memory/data.c`. The build (`port/switch/build.py`)
compiles a `.c` override in the game file's place, with the game file's flags,
and finds a `.h` override before the game's header (the overrides' directories
come first on the include path), so the submodule stays at upstream's commit
and the workflows need nothing. The game's own sources (`source/`) and the
platform layer it shares with the desktop (`port/linux/src/`) can both be
overridden.

`python3 tools/switch_overrides.py` lists the overrides; `--diff` shows each
one's change against the submodule's file. The Port tests workflow runs it,
and it fails when an override no longer differs from upstream's file (upstream
has the fix: repin the submodule, delete the override and its entry here),
when its game file is gone, or when it is not listed below.

Every override is listed here, with what it fixes and where it is going.

None at present: the game is built from the submodule alone.

The first was `source/memory/data.c` (the data arrays' address under the
moved window, for checkpoints, cutscene skips and the dynamic lights), from
2026-10-23 until the submodule was repinned to a main that carries Milenko's
own fix of it, ChupathingyCE/chupathingyce 73958f4a (`DATA_ARRAY_OWN_ELEMENTS`).
