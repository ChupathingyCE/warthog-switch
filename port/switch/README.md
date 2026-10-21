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
