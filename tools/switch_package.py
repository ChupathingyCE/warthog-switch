#!/usr/bin/env python3
"""Lay out the Switch build and your maps for the SD card.

    python3 tools/switch_package.py --maps /path/to/your/maps --out ~/Downloads/warthog-switch

writes OUT/switch/ChupaThingyCE/ with the program (build/switch/halo.nro) and
the game (build/switch/halo_guest.elf), from `ninja switch`; internet play's
broker list (the game's port/assets/network/brokers.txt); and maps/ with the
maps folder's *.map and loading.tga from your own copy of Halo. Copy the
`switch/` folder to the SD card's root (sd:/switch/ChupaThingyCE/).

The maps are never part of the build or of a release: they come from a disc
you own. With no --maps, only the build is laid out, and the game unpacks a
disc image it finds on the card itself (port/switch/README.md, "Game data").
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "switch"
BROKERS = ROOT / "chupathingyce" / "port" / "assets" / "network" / "brokers.txt"
# the folder on the card: HOST_ROOT in port/switch/host/host.h
CARD_FOLDER = Path("switch") / "ChupaThingyCE"


def place(source: Path, destination: Path) -> None:
    """a hard link where the file system allows one, a copy elsewhere"""
    if destination.exists():
        destination.unlink()
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--nro", type=Path, default=BUILD / "halo.nro", help="the program (default: the build's)")
    parser.add_argument("--guest", type=Path, default=BUILD / "halo_guest.elf", help="the game (default: the build's)")
    parser.add_argument("--maps", type=Path, help="your copy of Halo's maps folder (its *.map and loading.tga)")
    parser.add_argument("--out", type=Path, required=True, help="the folder to lay the card out in")
    args = parser.parse_args()

    for path in (args.nro, args.guest):
        if not path.is_file():
            print(f"no {path}: run ninja switch first", file=sys.stderr)
            return 1
    maps = []
    if args.maps:
        folder = args.maps.expanduser()
        maps = sorted(folder.glob("*.map")) + [p for p in [folder / "loading.tga"] if p.is_file()]
        if not any(p.name == "ui.map" for p in maps):
            print(f"no ui.map in {folder}", file=sys.stderr)
            return 1

    app_dir = args.out.expanduser() / CARD_FOLDER
    app_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.nro, app_dir / "halo.nro")
    shutil.copy2(args.guest, app_dir / "halo_guest.elf")
    if BROKERS.is_file():
        shutil.copy2(BROKERS, app_dir / "brokers.txt")
    if maps:
        (app_dir / "maps").mkdir(exist_ok=True)
        for path in maps:
            place(path, app_dir / "maps" / path.name)
    print(f"{app_dir}: halo.nro, halo_guest.elf" + (f" and {len(maps)} map files" if maps else " (no maps)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
