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

**In development** by thelinkin3000 and puginatux. There is no release yet.
The port's files arrive in this repository's first pull request; until then
this is the repository's skeleton, and the build stops with a message saying
so.

## What you'll need

- **A Switch that runs homebrew** (Atmosphere), with room on its SD card for
  the game's files.
- **Your own Halo game files.** Chupathingy needs the maps from a copy of
  Halo you own. They are never included or shared here, on the site or on
  the Discord.
- **To build it:** [devkitPro](https://devkitpro.org) with devkitA64,
  libnx and deko3d, and Python 3 and Ninja.

## Building it yourself

```sh
git clone --recursive https://github.com/ChupathingyCE/warthog-switch.git
cd warthog-switch
python3 chupathingyce/configure.py --console-port port/switch [--devkitpro DIR]
ninja switch
```

`configure.py` is the game's, and `port/switch/build.py` adds the Switch's
targets to it; the game's
[docs/building.md](https://github.com/ChupathingyCE/chupathingyce/blob/main/docs/building.md),
"Console ports", has the layout and the options every console takes.
devkitPro is found at `--devkitpro DIR`, `DEVKITPRO`, or `/opt/devkitpro`.

`tools/switch_package.py` lays out the build and your maps for the SD card
(`sd:/switch/halo/`).

After a `git pull`, run `git submodule update` to move the game to the
version this repository uses.

## Credits

- **thelinkin3000**: the Switch port.
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
- **Third-party code** keeps its own license, which goes beside it. The
  build links devkitPro's libnx (ISC) and deko3d (zlib) from your devkitPro
  install; they are not included here.
- **Halo itself is not covered.** The license covers the work of this
  repository's and Chupathingy's authors. It gives no rights in Halo, its
  maps or anything else Microsoft owns.

Nintendo Switch is a trademark of Nintendo. This project is not affiliated
with or endorsed by Nintendo or Microsoft.
