# Switch

`ninja switch` builds the game for the Nintendo Switch, as a devkitA64
homebrew program. The game is the `chupathingyce/` submodule (Chupathingy);
this folder holds the Switch's own code and `build.py`, which the game's
`configure.py` loads (`--console-port port/switch`; the game's
`tools/console_build.py` and its `docs/building.md`, "Console ports"). It
needs two toolchains, and neither can be replaced by the other.

The game is the same guest image as the game's Android build: the
decompilation compiled as ILP32 AArch64 code, with 32-bit pointers, because
the game's data formats embed pointers of the Xbox's size and they have to
keep their layout. Clang offers exactly one such target,
`arm64_32-apple-watchos`, whose Mach-O output the game's
`tools/android_asm_convert.py` rewrites into ELF. The Android NDK supplies
that clang along with `llvm-ar` and `ld.lld`; devkitA64 cannot build the
guest, because it is LP64 only. The guest's sources, flags, libc and runtime
are the Android build's, read from the game's `tools/android_build.py`; the
deko3d renderer (`guest/`, [DEKO3D.md](DEKO3D.md)) takes the OpenGL
renderer's place in the image.

The host (`host/`) is the game's Android host made into a homebrew program,
linked by devkitA64 against libnx, SDL2, Mesa and deko3d. Refer to the game's
[port/android/README.md](../../chupathingyce/port/android/README.md) for the
guest and the platform layer, and
[port/linux/README.md](../../chupathingyce/port/linux/README.md) for the
platform layer the two share.

The host changes are these:

| File | Why |
|---|---|
| `host_main.c` | no JNI and no APK; libnx start-up; the SD card for data |
| `host_sdl2.c` | answers the guest's SDL3 calls with devkitPro's SDL2 |
| `host_sdl3_events.c` | translates SDL2's events into the guest's SDL3 shapes |
| `host_gl.c` | Mesa is linked in, so there is no `libGLESv3.so` to open |
| `host_mman.c` | `mmap`/`mprotect` over the console's memory services |
| `host_futex.c` | futuxes over libnx's mutex and condition variable |
| `host_net.c` | the network calls over libnx's sockets; see Internet play |
| `host_dk.c`, `host_dk_shaders.c`, `host_dk_hud.c` | the deko3d renderer's host half: the frame's commands, the shader cache with UAM, the high-res HUD decoded on a thread |

Third-party code the port alone uses is in `third_party/` with its own
license: nanosvg (zlib), which draws the menus' panel. The game's third-party
code (zlib, tomlc17, stb and the rest) is the game's.

## Requirements

You do not need the Xbox SDK. You need the tools of the game's Linux build
(Python 3, ninja, clang) and these:

- devkitPro, with `devkitA64`, `libnx`, `deko3d`, `switch-sdl2`,
  `switch-mesa` and `switch-libdrm_nouveau`. `configure.py` looks for it in
  `DEVKITPRO`, then in `/opt/devkitpro` and `~/devkitpro`. The option
  `--devkitpro` selects a different one.
- The Android NDK, for the guest (`ANDROID_NDK_HOME`, or `--android-ndk`).
  See the game's port/android/README.md.
- For the shader compiler built into the host (UAM, deko3d's): meson, flex,
  bison 3 and Python's mako. Without them the build still makes the program,
  which then has only the shaders already on the card.
- A network connection for the first build: `configure.py` downloads musl
  1.2.5, SDL 3.4.16 and UAM to `build/switch/third_party`.

To install the devkitPro packages:

```
sudo dkp-pacman -S --needed devkitA64 libnx switch-sdl2 switch-mesa switch-libdrm_nouveau
```

## Build and install

From the root folder of this repository, with the game checked out
(`git submodule update --init`):

```
python3 chupathingyce/configure.py --console-port port/switch
ninja switch
```

That writes two files to `build/switch`:

- `halo.nro`, the program.
- `halo_guest.elf`, the game.

To install, put both on the SD card:

```
sdmc:/switch/ChupaThingyCE/halo.nro
sdmc:/switch/ChupaThingyCE/halo_guest.elf
```

and start `halo.nro` from the Homebrew Menu. The Homebrew Menu shows the log
while it runs. `tools/switch_package.py` lays the two out with your maps for
the card, and `tools/switch_deploy.py` sends them to a console running the
Homebrew Menu's FTP server.

### Releases and updates

A release is made by pushing a tag `v<version>` on a commit of main
(`git tag -a v0.8.0d-beta1 && git push origin v0.8.0d-beta1`; the tag's
message becomes the release's notes): `.github/workflows/release.yml` builds
the port in devkitPro's image, in both flavours, with the version from the
tag and the build number from the workflow's run number, and publishes the
GitHub release `build-<number>`, titled with the version and marked latest,
with `halo-switch-release.zip` and `halo-switch-debug.zip`: the card's
folder as `tools/switch_package.py` lays it out (the program, the game,
`brokers.txt` and `menus/`), stored rather than deflated. A build with a
number asks GitHub for the latest release before the game starts and offers
it (`port/switch/host/host_update.c`): the program is replaced at once, the
game image and the menu files at the next start. Builds made by hand have no
number and never look, and `update.auto = false` in config.toml turns the
look off. The installed builds compare their number with the latest
release's, which is why the number is the run's and not the version: it only
ever grows.

The shared shader keys (`keys.dkk` and `keys.sha1` at the root of main) come
the same way when the repository has them; this one does not yet.

The game's own view of the console is that of a 1280x720 handheld or a
1920x1080 docked display; `SDL_GetDesktopDisplayMode` reports which, and the
game is told the width to render at. It resizes on its own if the console is
docked or undocked while the game runs.

### Overrides of the game's files

A fix the Switch needs in the game itself waits on an upstream pull request
to [ChupathingyCE/chupathingyce](https://github.com/ChupathingyCE/chupathingyce);
until it is merged, the fixed file is kept whole in
[`port/switch/overrides/`](overrides/README.md), laid out as the game is
(`overrides/source/memory/data.c` for `source/memory/data.c`), and the build
compiles it in the game file's place with the same flags (a header override
is found before the game's), so the submodule stays at upstream's commit and
the workflows need nothing.
`overrides/README.md` lists each override, what it fixes and the pull request
it waits on; `python3 tools/switch_overrides.py` lists them and `--diff`
shows each one's change against the submodule's file. The Port tests
workflow runs the tool, which fails when an override no longer differs from
upstream's file (upstream has it: repin, delete the override and its entry)
or when its game file is gone.

## Game data

The game needs the `maps/` folder out of an Xbox disc image (`.xiso` or
`.iso`) of any version of the game. The disc image itself is not included, and
neither is `maps/`.

Put the disc image on the card:

```
sdmc:/switch/ChupaThingyCE/halo.iso
```

`halo.xiso`, `maps.iso` and `halo-xbox.iso` are also recognised, as is any
other `.iso` or `.bin` in the same folder. There is no file browser on the
console, so the name and the folder are fixed.

The game unpacks `maps/` itself on the first run. That is about 1.7 GB written
to the card and takes a few minutes, so leave the card in and make sure there
is that much free; the log says which file it is copying and how far it has
got. It reads the image the same way `extract-xiso` does, so all three disc
formats work.

Unpacking it yourself works too. If `maps/` is already there the game uses it
and never looks for an image:

```
sdmc:/switch/ChupaThingyCE/maps/
```

The game checks for `sdmc:/switch/ChupaThingyCE/maps/ui.map` and, with no image
either, refuses to start and says so. Saves go in `sdmc:/switch/ChupaThingyCE/save/`,
and the settings file `config.toml` goes in `sdmc:/switch/ChupaThingyCE/`.

Custom Edition maps go in `sdmc:/switch/ChupaThingyCE/custom_maps/`, with
`bitmaps.map`, `sounds.map` and `loc.map` in that folder. A map in a
subfolder is listed under the folder's name: campaign maps under CUSTOM
SINGLEPLAYER, multiplayer maps under CUSTOM MULTIPLAYER. One level of
folders is read. A map you do not have is downloaded from the other players
while you wait in the lobby. Refer to the root
[README.md](../../README.md#custom-edition-maps).

## Gyro aiming

The stick aims as it does anywhere else. Open a profile, choose Controls
Setup, set DEVICE to GAMEPAD and SHOW to GYRO. Gyro Aim is off until it is
set to ON, which aims with the gyroscope all the time, or ONLY ON ZOOM,
which aims with it only while you are zoomed in (a scope), for fine aiming;
the stick aims the rest of the time. Horizontal and vertical sensitivity are
how far the view turns each way (`1` is the sensor's own turn; the page goes
from `0.25` to `10`). Invert horizontal and invert vertical are separate, and
neither follows the stick's Invert Look. The same five are `input.gyro_aim`,
`input.gyro_sensitivity_horizontal`, `input.gyro_sensitivity_vertical`,
`input.gyro_invert_horizontal` and `input.gyro_invert_vertical` in
`config.toml`. Each local player reads their own controller. A Pro
Controller, the console held in the hands, and a single Joy-Con each use
their one sensor; when two Joy-Con are attached, the right one is read. It
is not used in the menus.

The host reads the sensor (`host_sdl2.c`, `host_sdl_gamepad_gyro`) and the
game's input layer applies the turn (its `xinput_sdl.c` and
`player_control.c`, behind the Switch define in the `chupathingyce/`
submodule as this port pins it); the GYRO page is the port's own menu file
(`tools/switch_menus.py`).

In a split-screen match on this console alone, the pause menu's LEAVE GAME
leaves the match for both players and returns to the main menu. Each
player's window is cleared only inside itself, so the second player's clear
does not wipe the first player's view.

## Performance

The console shows the game at 1280x720 in handheld and 1920x1080 docked.
`display.resolution_limit` in `config.toml` (`"480"`, `"720"`, `"900"` or
`"1080"`) chooses the lines the game draws at, which are scaled up to that:
480, the game's own, 720 (the default), 900 or 1080, no more than the
console shows (1080 draws at 720 in handheld). Docking or undocking switches
at once. `display.dynamic_resolution` steps the lines down while the GPU
falls behind. Video Setup has rows for both (RESOLUTION LIMIT and DYNAMIC
RESOLUTION) and for the CPU clock below: those rows are the Switch's own
menu files (`tools/switch_menus.py`, written by `ninja switch` into
`build/switch/menus` and put on the card as `menus/` by the packager and
the deploy tool), which the game takes over its built-in ones. The Switch
keeps to the Chupathingy menus, the game's default: the files are theirs,
they take QUIT off the main menu (HOME is the way out) and MENU STYLE off
Interface, and the PC version's and the Xbox's menus are not adjusted for
the console (`display.menus` in `config.toml` still chooses them, as they
are). The most players a game hosted on the console may have is 48, the
most it was measured to hold: the host setup's row stops there (the game's
`menu_functions.c`, behind `HALO_SWITCH_CONSOLE`).

`performance.cpu_clock` in `config.toml` is the CPU's clock: `"1785"` (the
default, 1.7 GHz, the fastest Nintendo's own games use), `"1020"` (the
console's handheld rate: cooler, and the battery lasts longer) or `"stock"`
(left at the rate the console started the game with). It changes at once. The memory and the GPU stay at the rates the game sets for
itself, and every clock goes back to the console's when the game exits.

`display.big_sprite_limit` (8 by default; the Xbox drew 11) is the most
sprites covering more than half the view drawn in a frame: the Halo level's
falls have 11 sheets of mist, 5.5 ms of a Switch Lite's GPU. The zoom's blur
and a cutscene's are drawn on a small copy of the screen and blended over it
once (`debug.original_zoom` and `debug.original_blur` draw them as the game
does). Both are changes to the game's own code behind `HALO_SWITCH_CONSOLE`,
in the `chupathingyce/` submodule as this port pins it.

## The memory model

This is the part of the port that is not like the others, and it is worth
writing down because it shaped the host and because it is the one thing here
that was established by experiment rather than by reading a manual.

Everything the guest can address has to be below 4 GB, because the guest's
pointers are 32 bits. That is not a restriction the console imposes: it is
the same restriction the game's data formats impose, and it is why the
guest image is linked at `HALO_GUEST_IMAGE_BASE` (0x3c000000) with the Xbox
contiguous window at 0x80000000 (port/android/include/halo_android_abi.h).

The answers below were measured on a console running Horizon 21.2.0 with
Atmosphère 1.10.2, by the programs in `port/switch/probe`. They are:

- The address space below 4 GB is free. There is nothing in the way.
- `svcMapPhysicalMemory` (SVC 0x2C), which sounds like the call this needs,
  is refused on this firmware. `svcMapMemory` (SVC 0x05) instead places
  memory at an address the caller chooses.
- No mapping is ever both writable and executable.
  `svcSetMemoryPermission` answers 0xd801 for `Perm_X`, as its documentation
  says it must. Executable memory is a separate kind, made with
  `svcCreateCodeMemory` (0x4B) and `svcControlCodeMemory` (0x4C).
- A code memory object has a writable owner view and a read-execute slave
  view, and the two are one memory: bytes written through one are read
  through the other.

So the guest image cannot be given one writable-and-executable mapping, the
way the Android host gives it one and then `mprotect`s it. `host_mman.c`
splits the image by permission instead, placing each part at the offset the
guest was linked for:

- executable pages become a code memory slave at `HALO_GUEST_IMAGE_BASE` plus their
  offset, filled in through a writable view at a scratch address;
- `.data`, `.bss`, the guest's arenas and the Xbox window become ordinary
  `svcMapMemory` regions.

The guest is not changed by this. It still sees one contiguous range,
because the segments land at exactly the addresses it was linked for.

`mprotect` is correspondingly not cheap here: adding `PROT_EXEC` copies the
range into a code memory object, maps it, and attends to both caches, which
for a large segment is tens of milliseconds. The loader does this a few times
while loading the image and never again; the calls it makes during play are
between read and write, and those are a single syscall on a page.

## SDL2, and why there is a shim

The guest was built against SDL3's headers. There is no SDL3 for the Switch:
devkitPro's SDL has `switch-sdl-3.2` and `switch-sdl-3.4` branches, but no
packaged, working port, and the repository of Switch examples this port
started from uses `pkg-config sdl2` throughout.

So `host_sdl2.c` answers the guest's SDL3 calls with devkitPro's SDL2, which
is the same arrangement the Anbernic port uses for its own reasons. SDL
objects are 64-bit pointers that the guest cannot hold, so the guest gets
small integer handles into a table. Most of the values agree between the two
versions; `host_sdl3_events.c` translates the ones that do not.

Where the graphics come from is worth noting, because it decided the port
early. devkitPro's SDL2 is built with `--disable-filesystem` and links
`switch-mesa`: Mesa 20.1.0 over `libdrm_nouveau`, statically. SDL2's Switch
video driver puts an EGL surface on the console's default `nwindow`, so
`SDL_GL_CreateContext` and `SDL_GL_SwapWindow` — the two calls the renderer
makes — work as they do anywhere else. The port started out drawing that
way. The game now draws with deko3d, the console's native interface,
through its own renderer (`port/switch/guest/d3d8_dk.c` and
`port/switch/host/host_dk.c`; see [DEKO3D.md](DEKO3D.md)); Mesa remains
linked because SDL2 needs it.

## Internet play

The game's online screens (the Multiplayer menu's ONLINE GAMES, the
Controls screen, the Link Profile panel, the invite prompt) are drawn by its
overlay, `port/linux/src/ui_overlay.c`, with OpenGL calls, which this
console's deko3d-only renderer cannot run. `port/switch/guest/ui_overlay_dk.c`
is that file with its OpenGL part replaced: the same gathering line for
line, the atlas, icons and picture as images of the renderer's texture
cache, the overlay's two shaders compiled by the host's shader service from
the OpenGL renderer's program in UAM's dialect (a few frames the first time,
then from the card's shader cache), and the gathered vertices drawn over the
back buffer at Present through the device's own commands (`dk_overlay_draw`
in `d3d8_dk.c`). The game's file is left out of the Switch guest; a change
to the gathering there is a change to copy here.

The game list's requests are the game's own `posix_browser.c` with its
Mbed TLS, built into the host as the Android app builds them (`build.py`,
`host_tls.c`: the library is told it is on a Unix, its entropy is the
console's random service and its millisecond clock the console's). The
library trusts certificate authorities from a PEM bundle it is given, since
the console keeps none where it looks: put one beside `config.toml` as
`cacert.pem` (Mozilla's, or your system's `ca-certificates.crt`) and the host
points the library at it; without one an HTTPS game list cannot be reached,
and the log says so at start.

`host_net.c` gives the game libnx's BSD sockets, through the same
translation to Winsock that `posix_net.c` does on the other builds, so
system link and internet play work as on Android. The desktop-only parts of
`posix_net.c` (URL schemes, Discord, UPnP) are answered as having nothing
to offer. Voice chat records from a headset in the console's jack
(`host_microphone.c`).

## Overlay commands

An Ultrahand overlay talks to the game through files in its package's folder,
`/switch/.packages/halo/overlay`, which must be there when the game starts
(then the main menu says "Ultrahand Overlay present and enabled", one of
the game's messages, which `game.terminal_output` draws in the main menu on
the Switch):

- `command.txt`: one line, looked for once a second, taken (deleted) and run.
  Either a console command as typed at the console (`cheat_deathless_player
  true`, `map_name a10`, `game_revert`) or `config <setting> <value>` (also
  `config <setting> = <value>`), which sets and saves a setting.
- `result.txt`: the last command and `ok`, or `error: why`.
- `flags/<name>.flag`: present while that boolean is true, a console global
  (`cheat_infinite_ammo`) or a setting (`display.vsync`); `show_hud`'s is
  `hud.flag`. The folder is emptied at the start and kept up to date once a
  second.
- `game/ChupaThingyCE.flag`: which game the package is talking to.

`game.overlay_commands = false` in config.toml turns it off. The unit is
`port/switch/overrides/port/linux/game/overlay_commands.c`, on its way
upstream.

## What the port does not have

Three things in the Android host are absent here, all of them development
aids rather than part of the game, and all for the same reason: libnx
exposes no syscall for installing a signal handler.

- The crash handler in `host_memory.c`, which logged the faulting address,
  the program counter and the guest's frame chain.
- The thread sampler in `host_debug.c`, which `debug.sample_seconds` in
  `config.toml` starts. It is worth having; see each file for how it could be
  built on the console's thread context syscalls instead.
- `host_probe.c`, which walks the memory window looking for the pointers
  that would have to move if the window moved. Its question is already
  answered, and the answer is in port/android/README.md.

## The probes

`port/switch/probe` holds the programs the memory model above was measured
with. They are standalone devkitA64 projects, not part of the port's build,
and they are kept because the answers they gave are the reason the port is
shaped the way it is. Each writes its findings to `sdmc:/`, so they can be
read back off the card:

```
cd port/switch/probe/mem
make
```

`mem` is at its fifth version; the earlier ones found the same things less
directly, and the comments say what each was for.