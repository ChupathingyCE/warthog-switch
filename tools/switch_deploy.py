#!/usr/bin/env python3
"""Copy the Switch build to the console over FTP.

The console runs an FTP server from its Homebrew Menu, so a build can be put
on the card and run without taking it out. That makes the edit-build-run
loop a matter of one command and a wait, rather than a card reader.

Usage: python3 tools/switch_deploy.py [--host 192.168.2.173] [--port 5000]
                                     [--destination /switch/ChupaThingyCE]
                                     [--user anonymous] [--password ...]
                                     [build/switch/halo.nro ...]

With no files, it uploads what the port needs: the program, the guest
image (halo_guest.elf, with the deko3d renderer), internet play's
brokers.txt, and the Switch's own menu files (build/switch/menus,
tools/switch_menus.py) into menus/, as a release carries them.
The game's own data (maps/) is not touched - it is large, it does not change
between builds, and it belongs to the player rather than to the build.
"""

import argparse
import ftplib
import sys
from pathlib import Path

DEFAULT_HOST = "192.168.2.173"
DEFAULT_PORT = 5000
DEFAULT_DESTINATION = "/switch/ChupaThingyCE"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", type=Path,
                        help="files to upload; the default is the program and the guest images")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--destination", default=DEFAULT_DESTINATION)
    parser.add_argument("--user", default="anonymous")
    parser.add_argument("--password", default=None,
                        help="anonymous by default, which is what the console's server uses")
    args = parser.parse_args()

    # (and internet play's brokers, which a release carries beside the
    # game: without them the server browser lists nothing)
    files = args.files or [Path("build/switch/halo.nro"), Path("build/switch/halo_guest.elf"),
                          Path("chupathingyce/port/assets/network/brokers.txt")]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        print("not built: " + ", ".join(missing), file=sys.stderr)
        return 1

    try:
        ftp = ftplib.FTP()
        ftp.connect(args.host, args.port, timeout=30)
        ftp.login(args.user, args.password or "anonymous@")
    except (OSError, ftplib.Error) as error:
        print("cannot reach the console's FTP server at %s:%d: %s" % (args.host, args.port, error),
              file=sys.stderr)
        return 1

    try:
        ftp.cwd(args.destination)
    except ftplib.error_perm as error:
        print("no %s on the card: %s" % (args.destination, error), file=sys.stderr)
        ftp.quit()
        return 1

    for path in files:
        # Straight over the old file, with no rename dance.

        # The first version uploaded to name.new and renamed over the top,
        # on the reasoning that a failure part way through would leave the
        # old program runnable. That reasoning was wrong in the case that
        # mattered: this server refuses to rename onto an existing file, so
        # the fallback deleted the target first - which opens a window in
        # which neither the old name nor the new one exists, and loses the
        # program if anything goes wrong in it. A direct STOR replaces the
        # file in one step, which is checked to work here and has no such
        # window. The cost is that a transfer cut short leaves a truncated
        # file rather than an old one, which is why the size is compared
        # afterwards.
        print("%s -> %s/%s (%.1f MB)" % (path, args.destination, path.name, path.stat().st_size / 1048576.0))
        with path.open("rb") as handle:
            ftp.storbinary("STOR " + path.name, handle)
        expected = path.stat().st_size
        actual = ftp.size(path.name)
        if actual != expected:
            print("warning: %s is %d bytes on the card, %d expected; the transfer was cut short"
                  % (path.name, actual, expected), file=sys.stderr)
    if not args.files:
        menus_upload(ftp, args.destination, Path("build/switch/menus"))
    ftp.quit()
    print("done")
    return 0


def menus_upload(ftp: ftplib.FTP, destination: str, menus: Path) -> None:
    """the Switch's menu files into menus/ below the destination, their
    folders made as needed (the server's MKD fails for one that is there)"""
    files = sorted(menus.rglob("*.xml")) if menus.is_dir() else []
    if not files:
        print("no menu files in %s (ninja switch writes them); the card's are left as they are" % menus)
        return
    # (a menu file of an earlier build that this one does not write would
    # go on replacing the game's: taken off the card)
    wanted = set(path.relative_to(menus).as_posix() for path in files)
    for folder, name in card_menu_files(ftp, destination + "/menus"):
        if folder[len(destination) + len("/menus"):].lstrip("/") + ("/" if folder != destination + "/menus" else "") + name not in wanted:
            print("%s/%s: not in this build; removed from the card" % (folder, name))
            ftp.delete(folder + "/" + name)
    made = set()
    for path in files:
        relative = path.relative_to(menus)
        folder = destination + "/menus" + "".join("/" + part for part in relative.parent.parts if part != ".")
        if folder not in made:
            parts = folder.split("/")
            for depth in range(len(destination.split("/")) + 1, len(parts) + 1):
                try:
                    ftp.mkd("/".join(parts[:depth]))
                except ftplib.error_perm:
                    pass
            made.add(folder)
        ftp.cwd(folder)
        print("%s -> %s/%s" % (path, folder, path.name))
        with path.open("rb") as handle:
            ftp.storbinary("STOR " + path.name, handle)
    ftp.cwd(destination)


def card_menu_files(ftp: ftplib.FTP, folder: str) -> list:
    """the .xml files below the card's menus folder, as (folder, name), two
    levels deep (the game's own layout); none when the folder is not there"""
    found = []
    try:
        ftp.cwd(folder)
    except ftplib.error_perm:
        return found
    entries = []
    ftp.retrlines("LIST", entries.append)
    for entry in entries:
        parts = entry.split(None, 8)
        if len(parts) < 9:
            continue
        name = parts[8]
        if entry.startswith("d"):
            inner = []
            ftp.cwd(folder + "/" + name)
            ftp.retrlines("LIST", inner.append)
            for line in inner:
                words = line.split(None, 8)
                if len(words) == 9 and not line.startswith("d") and words[8].endswith(".xml"):
                    found.append((folder + "/" + name, words[8]))
            ftp.cwd(folder)
        elif name.endswith(".xml"):
            found.append((folder, name))
    return found


if __name__ == "__main__":
    raise SystemExit(main())