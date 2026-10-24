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

## source/objects/object_lights.c

`display.dynamic_light_limit` and `display.specular_light_limit`: of the
dynamic lights on the screen (muzzle flashes, plasma bolts, explosions), the
8 largest as seen from the camera light the level and the 2 largest add their
specular highlights, the first-person weapon's own first; the rest still
light the objects near them. Each dynamic light redraws the level's surfaces
it reaches: in Chill Out with 64 players a frame's six lights took 11.3 ms of
the Switch's GPU for their specular passes and 3.7 ms for their diffuse ones.
0 is the Xbox's behaviour, every one rendered. The log says every 300 frames
how many there were and how many were let go.

- From halo-ce-universal bd294a490, 6028fd037 and c31dc4f6e (2026-10-23).
- Base: upstream `3705fa1a`.
- Upstream: ChupathingyCE/chupathingyce#450 (with the two settings in
  `port/linux/src/port_config.c`).

## source/effects/particles.c

Two things, one pull request's worth. `display.particle_limit`: the most
particles (sparks, smoke, casings, debris) alive at once, 2048 on the Switch
and 4096 elsewhere (the Xbox's pool was 1024, the port's is 8192); past it
the oldest alive is let go for the new one, never the first-person weapon's.
With 64 players in a small map the pool filled and the particles were 30% of
the Switch's game thread. And the particles not attached to an object move,
and cast their collision rays, once a 30 Hz tick as on the Xbox rather than
at every frame drawn, and are drawn between their ticks by the time into the
tick; one not drawn since the tick before moves once every 4 ticks by all it
was owed. The rays were about a sixth of the game thread.
`debug.original_particles` moves them each frame, as before. The log says
every 10 s how many lived.

- From halo-ce-universal adf076e79, 4f8ec94c9, ca43a1ec2, 04e4f58bc and
  5bf2e32f5 (2026-10-23), with `source/effects/particles.h` (the prototype of
  `particle_render_position`) and `source/render/render_particles.c` below.
- Base: upstream `3705fa1a`.
- Upstream: ChupathingyCE/chupathingyce#451 (with the two settings in
  `port/linux/src/port_config.c`).

## source/effects/particles.h

The prototype of `particle_render_position`, for `source/effects/particles.c`
above and `source/render/render_particles.c` below. Goes with them
(ChupathingyCE/chupathingyce#451).

## source/render/render_particles.c

The particles drawn where `particle_render_position` puts them between their
ticks (`source/effects/particles.c` above), and the visible particles sorted
by a stable radix sort on qsort's key rather than qsort, from halo-ce-universal
7e5aecc29 (2026-10-23). Goes with particles.c
(ChupathingyCE/chupathingyce#451).

## source/interface/hud.c

Player names over the heads: an enemy's line of sight is tested once a tick,
and only after the screen and the range tests, which no longer look for the
heads of the far. With 64 players the tests were a measurable share of the
Switch's game thread.

- From halo-ce-universal a4f9adbfd (2026-10-23).
- Base: upstream `3705fa1a`.
- Upstream: ChupathingyCE/chupathingyce#452.

## source/rasterizer/xbox/rasterizer_xbox_screen_effect.c

A blur screen effect (the cryo bay's waking up, cutscenes) drawn small is
drawn on copies as large as its spread hides, so a10's waking up no longer
loses its sharpness; `debug.original_blur` draws it in passes over the whole
screen, as the game does. Refines the blurs drawn small that chupathingyce#414
brought.

- From halo-ce-universal e13e9f211 (2026-10-23); `debug.original_blur` is
  upstream's own row already (chupathingyce#414), so no settings change.
- Base: upstream `3705fa1a`.
- Upstream: ChupathingyCE/chupathingyce#453.

## source/memory/lruv_cache.c

Release builds leave out the LRU caches' walk over every block at each
operation, a check only, which the debug builds keep.

- From halo-ce-universal 7840fadbd (2026-10-23).
- Base: upstream `3705fa1a`.
- Upstream: ChupathingyCE/chupathingyce#454.

## source/networking/network_connection.c

A client reads its host's stream 32 KB at a time, not 4 KB: each read is a
call to the system's sockets, on the Switch an IPC, and the local player's
client reading a 64-player game's stream was about 9% of the game thread.

- From halo-ce-universal 167820d0a (2026-10-23), the game's half; the host's
  half (the receives counted) is in the port already.
- Base: upstream `3705fa1a`.
- Upstream: ChupathingyCE/chupathingyce#455.

## port/linux/src/dsound_sdl.c

The sound mixer and the game's thread no longer wait on each other: the
mixer holds its lock one voice at a time and lets the game's thread in
between voices; the game's thread no longer waits for the lock to tell
streams their packets are done (tried, and told the next frame); and 256
frames are mixed at a time, not 1024, so a sound started or stopped waits out
at most 5 ms of mixing (2.7 ms of the Switch's game thread per call before).

- From halo-ce-universal cc0cfe80b, 1ff5a44fe and 764f5d02c (2026-10-23 and
  24); two hunks placed by hand (the stream setters' lock and the silent
  clock's 10 ms in two chunks), and the lock taken the new way at the nine
  call sites chupathingyce's file has that hcu's does not (the listener's and
  the buffers' setters).
- Base: upstream `3705fa1a`.
- Upstream: ChupathingyCE/chupathingyce#456.

## port/linux/src/d3d8_resources.c

Dynamic vertex buffers get up to 16 storages, so a frame no longer waits
behind the Sentinels' beams for a storage the GPU is still reading.

- From halo-ce-universal bd0da7c99 (2026-10-20).
- Base: upstream `3705fa1a`.
- Upstream: ChupathingyCE/chupathingyce#457.

## port/linux/src/port_config.c

The settings table, with the rows the other overrides read:
`display.dynamic_light_limit` (8) and `display.specular_light_limit` (2) for
`source/objects/object_lights.c`; `display.particle_limit` (2048 under
`HALO_SWITCH_CONSOLE`, 4096 elsewhere) and `debug.original_particles` for
`source/effects/particles.c`. Each row goes upstream with the override that
reads it.

- Base: upstream `3705fa1a`.

The first was `source/memory/data.c` (the data arrays' address under the
moved window, for checkpoints, cutscene skips and the dynamic lights), from
2026-10-23 until the submodule was repinned to a main that carries Milenko's
own fix of it, ChupathingyCE/chupathingyce 73958f4a (`DATA_ARRAY_OWN_ELEMENTS`).
