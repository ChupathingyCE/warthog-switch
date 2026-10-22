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

The game's own view of the console is that of a 1280x720 handheld or a
1920x1080 docked display; `SDL_GetDesktopDisplayMode` reports which, and the
game is told the width to render at. It resizes on its own if the console is
docked or undocked while the game runs.

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

The stick aims as it does anywhere else. With `input.gyro_aim = "true"` in
`config.toml`, the first player's controller gyroscope turns the view too.
`input.gyro_sensitivity_horizontal` and `input.gyro_sensitivity_vertical`
are how far the view turns each way (`1` is the sensor's own turn), and
`input.gyro_invert_horizontal` and `input.gyro_invert_vertical` are separate
inverts, neither following the stick's Invert Look. The host reads these five
itself (`host_sdl2.c`, `host_touch_look_read`), and reads them again when the
file changes, so the game need not know them; the game logs each as an
unknown setting when it starts, which is expected.

The turn reaches the game through the path its Android touch controls use
for a swipe, scaled as the mouse's is and scaled down while zoomed in. Two
things that path cannot carry: a second to fourth player's turn (only the
first pad aims), and `"zoom"` (aiming with the gyroscope only while zoomed
in), which needs the game's zoom state and aims at all times here. Both
would take a hook in the game's `player_control.c`, which the port keeps out
of the shared code for now. A Pro Controller, the console held in the hands,
and a single Joy-Con each use their one sensor; when two Joy-Con are
attached, the right one is read. It is not used in the menus.

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

`host_net.c` gives the game libnx's BSD sockets, through the same
translation to Winsock that `posix_net.c` does on the other builds, so
system link and internet play work as on Android. The desktop-only parts of
`posix_net.c` (URL schemes, Discord, UPnP) are answered as having nothing
to offer. Voice chat records from a headset in the console's jack
(`host_microphone.c`).

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