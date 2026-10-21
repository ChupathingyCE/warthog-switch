<h1 align="center">Warthog for Switch</h1>

<p align="center"><b>Chupathingy on the Nintendo Switch.</b></p>

<p align="center">
<a href="https://github.com/ChupathingyCE/chupathingyce">The game</a> ·
<a href="https://chupathingy.org">chupathingy.org</a> ·
<a href="https://discord.gg/chupathingy">Discord</a>
</p>

Warthog for Switch is the Nintendo Switch port of
[Chupathingy](https://github.com/ChupathingyCE/chupathingyce), the port of the
Halo: Combat Evolved decompilation built for stability and community play.
It runs as homebrew on a Switch with Atmosphere, and plays online with the
PC builds and the Xbox (Warthog) in the same games.

This repository holds only the Switch's own code: the game is the
`chupathingyce/` submodule, and the shared code's console hooks live there.

## Status

**Working: boots and plays on Switch hardware (October 2026).** The port is
maintained by [thelinkin3000](https://github.com/thelinkin3000). There is no
release yet. The port is here: the game's image with a deko3d renderer, the
host that runs it as homebrew, the shader cache with deko3d's compiler built
in, gyro aiming, and internet play with the game list
([port/switch/README.md](port/switch/README.md) has the whole of it). Every
push and pull request is checked by the
[Build workflow](.github/workflows/build.yml), which builds the program and
the game's image in devkitPro's container; a pushed tag `v<number>` makes a
release ([Release workflow](.github/workflows/release.yml)), which installed
builds offer to update to.

Known limits, from the port's changes to the game
([chupathingyce#414](https://github.com/ChupathingyCE/chupathingyce/pull/414)):

- **Sprites:** at most 8 sprites that cover more than half the view are drawn
  in a frame (`display.big_sprite_limit`; the Xbox drew 11), to keep the
  Halo level's falls within the Switch's GPU time.
- **Zoom and cutscene blurs:** drawn on a smaller copy of the screen, so they
  are a little softer than on other builds. `debug.original_zoom` and
  `debug.original_blur` draw them as the game does.
- **Hosted games:** up to 48 players, which the console was measured to hold.
- **Gyro aiming:** `input.gyro_aim` (always, only while zoomed in, or off), on
  Controls Setup's GYRO page.

## What you'll need

- **A Switch that runs homebrew** (Atmosphere), with room on its SD card for
  the game's files.
- **Your own Halo disc's maps.** The North American (NTSC) release,
  01.10.12.2276, as every Chupathingy build and server uses. The PAL disc's
  maps work too. Warthog never provides maps, disc images or other game
  data, and never links to them. Don't share yours.
- **To build it:** [devkitPro](https://devkitpro.org) with devkitA64,
  libnx, deko3d and the Switch portlibs (SDL2, Mesa, libdrm_nouveau); the
  Android NDK, which builds the game's half; and Python 3, Ninja and clang.
  For the shader compiler built into the program: meson, flex, bison 3 and
  Python's mako. [port/switch/README.md](port/switch/README.md),
  "Requirements", has the versions and the install commands.

## Install

1. Build the port (see "Building it yourself"), or take the Build workflow's
   artifact on this repository's Actions page: the card's folder, with
   `halo.nro` (the program), `halo_guest.elf` (the game), its menu files and
   the broker list for internet play.
2. Copy the `maps` folder from your own disc to your computer.
3. Lay it out for the SD card:
   `python3 tools/switch_package.py --maps /path/to/maps --out ~/Downloads/warthog-switch`.
   This puts the build and your maps in `switch/ChupaThingyCE/`.
4. Copy that `switch` folder to the SD card's root, so the game is in
   `sd:/switch/ChupaThingyCE/`. (Without maps, the game unpacks a disc image
   it finds on the card itself: port/switch/README.md, "Game data".)
5. Start it from the Homebrew Menu.

`tools/switch_deploy.py` sends a build to a console running an FTP server,
in place of the card going back and forth. A release build asks GitHub for a
newer release when it starts and offers it; `update.auto = false` in
`config.toml` turns that off.

## Building it yourself

```sh
git clone --recursive https://github.com/ChupathingyCE/warthog-switch.git
cd warthog-switch
python3 chupathingyce/configure.py --console-port port/switch [--devkitpro DIR] [--android-ndk DIR]
ninja switch
```

`configure.py` is the game's, and `port/switch/build.py` adds the Switch's
targets to it; the game's
[docs/building.md](https://github.com/ChupathingyCE/chupathingyce/blob/main/docs/building.md),
"Console ports", has the layout and the options every console takes.
devkitPro is found at `--devkitpro DIR`, `DEVKITPRO`, or `/opt/devkitpro`;
the NDK at `--android-ndk DIR` or `ANDROID_NDK_HOME`. The first build
downloads musl, SDL and the shader compiler's sources to
`build/switch/third_party`.

The [Build workflow](.github/workflows/build.yml) is the same build in
devkitPro's container, with the NDK and LLVM's clang added to the image: a
way to build without a devkitPro install, and the set-up to copy if you want
to do it in Docker on your computer.

`tools/switch_package.py` lays out the build and your maps for the SD card
(`sd:/switch/ChupaThingyCE/`).

After a `git pull`, run `git submodule update` to move the game to the
version this repository uses.

## Credits

- [thelinkin3000](https://github.com/thelinkin3000): the Switch port, and its
  maintainer.
- **puginatux**: the Switch port.
- **Chupathingy** and its contributors: the game
  ([its README](https://github.com/ChupathingyCE/chupathingyce#readme) has the full credits).

## License

Warthog for Switch is free software: you can redistribute it and modify it
under the terms of the GNU General Public License as published by the Free
Software Foundation, either version 3 of the License or (at your option) any
later version (`GPL-3.0-or-later`). It comes with no warranty. The full text
is in [LICENSE](LICENSE).

- **The Switch port** is thelinkin3000's work, contributed under
  GPL-3.0-or-later.
- **The game** (`chupathingyce/`) has its own license notes in its README.
- **Third-party code** keeps its own license, which goes beside it:
  nanosvg (zlib) in `port/switch/third_party`. The build links devkitPro's
  libnx (ISC) and deko3d (zlib) from your devkitPro install, and builds
  deko3d's shader compiler UAM (zlib) into the program from its own
  download; they are not included here.
- **Halo itself is not covered.** The license covers the work of this
  repository's and Chupathingy's authors. It gives no rights in Halo, its
  maps or anything else Microsoft owns.

Nintendo Switch is a trademark of Nintendo. This project is not affiliated
with or endorsed by Nintendo or Microsoft.
