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
overridden, and a `.c` under `port/linux/game/` that the game has no file for
is an addition: a game unit of the port's own, compiled with the game's units
until upstream takes it.

`python3 tools/switch_overrides.py` lists the overrides; `--diff` shows each
one's change against the submodule's file. The Port tests workflow runs it,
and it fails when an override no longer differs from upstream's file (upstream
has the fix: repin the submodule, delete the override and its entry here),
when its game file is gone, or when it is not listed below.

Every override is listed here, with what it fixes and where it is going.

## port/linux/game/overlay_commands.c

An addition: commands from outside the game through a file, for an Ultrahand
overlay on the Switch. Once a second the game looks for `command.txt` in the
overlay package's folder (`/switch/.packages/halo/overlay`), takes it (the
file is deleted) and runs it: a console command as typed at the console
(cheats, `map_name`, `game_revert`), or `config <setting> <value>`, which sets
and saves a setting as the menus do. `result.txt` beside it says what came of
it. Each boolean the commands can set, a console global or a setting, has an
empty `flags/<name>.flag` while it is true (`show_hud`'s is `hud.flag`), and
`game/ChupaThingyCE.flag` names the game the package is talking to. Only when
the package's folder is there at the start; then the main menu says the
overlay is present, and the package's `game` and `flags` folders are emptied
or made for the run. `game.overlay_commands` turns the look off.

- From the Switch port's reference implementation (2026-10-24), with the
  game's flag named for ChupaThingyCE.
- Needs: `source/main/main.c` (the call), `port/linux/src/port_config.c` and
  `.h` (the setting, `config_set_text`, `config_boolean_setting`),
  `port/linux/src/msvc_crt.c` (the host-path file helpers), below; and in the
  host, a folder removed through `unlinkat` with `AT_REMOVEDIR`
  (`port/switch/host/host_syscall.c`, the port's own).
- Upstream: pull request to be opened, if wanted there.

## source/interface/terminal.c

Where the game's messages (the terminal's output lines, at the bottom left:
the notices, what the console's commands print) are drawn, as the setting
`game.terminal_output` says when `terminal_render` is 2, its default: upstream
draws them only while the console is open, and the Switch cannot open its
console, so no message ever showed there, the overlay's "Ultrahand Overlay
present and enabled" among them. "menus" draws them in the main menu too,
the default under `HALO_SWITCH_CONSOLE`; "console" is upstream's behaviour and
the default elsewhere; "none" and "always" as they say. The reference's rule,
on upstream's `terminal_render` values.

- Base: upstream `f5abeb99`.
- Upstream: pull request to be opened (the setting with its "console"
  default changes nothing on the desktop; a console build could turn
  "menus" on through a capability of `halo_console_features.h`).

## source/main/main.c

The call of `overlay_commands_update` after `telnet_console_process` in both
main loops (the pregame's and the game's), and its prototype. For
`port/linux/game/overlay_commands.c`.

## port/linux/src/port_config.h

The prototypes of `config_set_text` and `config_boolean_setting`, for
`port/linux/game/overlay_commands.c`.

## port/linux/src/msvc_crt.c

`platform_fopen_host`, `platform_remove_host` and
`platform_remove_directory_host`: a file by the host's own path, untranslated,
opened, removed, and an empty folder removed, for
`port/linux/game/overlay_commands.c`.

## port/linux/src/port_config.c

The settings table with its four rows of 2026-10-24 (`display.particle_limit`,
`display.particle_ticks`, `display.dynamic_light_limit`,
`display.specular_light_limit`) moved out of the `debug.gpu_fault_test` row,
inside whose braces upstream has them: there they are not settings at all
(the compiler takes the first as that row's description and drops the rest,
a warning the guest's `-w` hides), the game logs "no such setting" and reads
0 for each, and the light limits, the particle limit and the once-a-tick
particles stay off. And `game.overlay_commands` (under `HALO_SWITCH_CONSOLE`),
with `config_set_text` and `config_boolean_setting`, for
`port/linux/game/overlay_commands.c`; and `game.terminal_output`, for
`source/interface/terminal.c`.

- Base: upstream `f5abeb99`.
- Upstream: ChupathingyCE/chupathingyce#458 (the rows); the overlay's part
  goes with its addition.

The first was `source/memory/data.c` (the data arrays' address under the
moved window, for checkpoints, cutscene skips and the dynamic lights), from
2026-10-23 until the submodule was repinned to a main that carries Milenko's
own fix of it, ChupathingyCE/chupathingyce 73958f4a (`DATA_ARRAY_OWN_ELEMENTS`).
Ten more, of 2026-10-24 (the dynamic light limits, the particle limit and the
once-a-tick particles, the player names' line of sight once a tick, the small
blurs drawn on copies, the LRU caches' walk left out of release builds, a
client's 32 KB reads, the sound mixer's lock, the dynamic vertex buffers' 16
storages), went upstream as ChupathingyCE/chupathingyce#450 to #457, all
merged the same day, and left with the repin to `f5abeb99`.
