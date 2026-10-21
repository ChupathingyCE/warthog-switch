# port/switch

The Switch port: its sources and `build.py`, which the game's `configure.py`
loads (`--console-port port/switch`).

The port's files arrive in this repository's first pull request. Until then
this folder holds only `build.py`, which stops `configure.py` with a message
saying so.

The shared code's console hooks the port uses (`HALO_SWITCH_CONSOLE`,
`HALO_WINDOW_REBASE` and the `HALO_CONSOLE_*` capabilities) are in the game,
`chupathingyce/`; its `docs/building.md`, "Console ports", has what goes
where.

## Getting started

1. Clone with the game: `git clone --recursive https://github.com/ChupathingyCE/warthog-switch.git`
   (or `git submodule update --init` in an existing clone).
2. Put the port's sources in `port/switch/` and fill in `port/switch/build.py`:
   - `add_arguments(parser)`, `configure_inputs(port)` and `generate(n, sln, port)`,
     as `chupathingyce/docs/building.md`, "Console ports", describes. `port` lists the
     game's sources, defines and include folders (`chupathingyce/port/linux/port.json`).
   - The build defines `HALO_SWITCH_CONSOLE` (and `HALO_WINDOW_REBASE` for the moved
     window). That alone turns on the console capabilities the Switch uses:
     `chupathingyce/port/linux/include/halo_console_features.h` lists each one and the
     function the port provides for it.
3. Build: `python3 chupathingyce/configure.py --console-port port/switch [--devkitpro DIR]`,
   then `ninja switch`. Package with `tools/switch_package.py`.

Shared code (anything under `chupathingyce/`) changes through pull requests to
[ChupathingyCE/chupathingyce](https://github.com/ChupathingyCE/chupathingyce), gated
behind a console capability so desktop builds stay the same. Once one is merged,
bump the submodule here: `git -C chupathingyce pull origin main`, then commit
`chupathingyce`.
