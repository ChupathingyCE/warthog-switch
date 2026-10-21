#!/usr/bin/env python3
"""Lay out the Switch build and your maps for the SD card.

    python3 tools/switch_package.py --maps /path/to/your/maps --out ~/Downloads/warthog-switch

writes OUT/switch/halo/halo.nro (build/switch/halo.nro, from `ninja switch`)
and OUT/switch/halo/maps with the maps folder's *.map and loading.tga, from
your own copy of Halo. Copy the `switch/` folder to the SD card's root
(sd:/switch/halo/).
"""

import argparse
import os
import shutil
import sys
from pathlib import Path


def place(source: Path, destination: Path) -> None:
    if destination.exists():
        destination.unlink()
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--nro", type=Path, default=Path("build/switch/halo.nro"))
    parser.add_argument("--maps", type=Path, required=True, help="your copy of Halo's maps folder")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    maps = args.maps.expanduser()
    out = args.out.expanduser()
    if not args.nro.is_file():
        print(f"no {args.nro}: run ninja switch first", file=sys.stderr)
        return 1
    files = sorted(maps.glob("*.map")) + [p for p in [maps / "loading.tga"] if p.is_file()]
    if not any(p.name == "ui.map" for p in files):
        print(f"no ui.map in {maps}", file=sys.stderr)
        return 1

    app_dir = out / "switch" / "halo"
    (app_dir / "maps").mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.nro, app_dir / "halo.nro")
    for path in files:
        place(path, app_dir / "maps" / path.name)
    print(f"{app_dir}: halo.nro and {len(files)} map files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
