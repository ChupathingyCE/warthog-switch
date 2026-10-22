#!/usr/bin/env python3
"""The Switch's own menu files, written for the card's menus folder.

    python3 tools/switch_menus.py --out build/switch/menus

The game's menus are XML files embedded in it (chupathingyce/port/assets/menus,
tools/embed_assets.py), and a file of the same name in the data folder's
menus/ replaces the embedded one when the game starts (port/linux/src/
menu_files.c logs each). The Switch's settings differ from the desktop's and
Android's, and rather than carry its rows in the game's files, the port
writes the few files it needs its own of, with the game's generator
(chupathingyce/tools/port_settings.py) and its rows:

- Video Setup (ce/...video_settings.xml, and the Chupathingy menus' settings
  pages, chupathingy/settings_pages.xml): the rows the Switch has, packed
  with no gaps where the desktop's would be, and its own: RESOLUTION LIMIT
  (display.resolution_limit), DYNAMIC RESOLUTION (display.dynamic_resolution)
  and CPU CLOCK (performance.cpu_clock), which the game declares and the
  Switch's renderer and host read.
- The main menu (ce/main_menu.xml): no QUIT GAME, and B does not offer to
  quit: the console's HOME button is the way out.
- Create Game's server settings (ce/...server_settings.xml): the most
  players a game hosted here may have is 48, which the console was measured
  to hold (port/switch/host/host_main.c, host_net.c), so the spinner stops
  there; the game indexes its own table by position, so the first eight
  choices are the same ones.

tools/switch_package.py and tools/switch_deploy.py put the folder on the
card beside the program.
"""

import argparse
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME = ROOT / "chupathingyce"
MENUS = GAME / "port" / "assets" / "menus"

sys.path.insert(0, str(GAME / "tools"))
import port_settings  # noqa: E402

PE = port_settings.PE
VIDEO = f"{PE}/video_settings".replace("/", ".") + ".xml"
SERVER = f"{port_settings.MT}/server_settings".replace("/", ".") + ".xml"
MAIN_MENU = "main_menu.xml"

# the Switch's rows of Video Setup, after the rows it shares with the others
# (label, setting, choices, help, platform): the setting is the game's, its
# value read by port/switch/guest/d3d8_dk.c and port/switch/host/host_sdl2.c
SWITCH_VIDEO_ROWS = [
    ("RESOLUTION LIMIT:", "display.resolution_limit",
     [("480P", "480"), ("720P", "720"), ("900P", "900"), ("1080P", "1080")],
     "What the game draws at. Shown at 720p in handheld\nand 1080p docked; handheld draws 720p at most.", None),
    ("DYNAMIC RESOLUTION:", "display.dynamic_resolution", port_settings.ON_OFF,
     "Draw one step lower while the frame rate would\nfall under 55, and back up once it fits again.", None),
    ("CPU CLOCK:", "performance.cpu_clock", [("STOCK", "stock"), ("1 GHZ", "1020"), ("1.7 GHZ", "1785")],
     "1.7 GHz is the fastest Nintendo's games use.\n1 GHz and stock run cooler, and the battery lasts.", None),
]
# the Android rows the Switch has too (its game is built as Android's): the
# rest of Android's are its own (its anti-aliasing is the OpenGL renderer's)
ANDROID_ROWS_KEPT = {"display.interpolation"}
# the most players a game hosted on the console may have
HOSTED_PLAYERS_LIMIT = 48


def switch_rows(rows: list) -> list:
    """the rows the Switch shows, with no platform: the desktop's left out,
    Android's but the few it shares, and the rest for every platform"""
    kept = []
    for row in rows:
        label, setting, choices, help_text, platform, *named = row
        if platform == "desktop":
            continue
        if platform == "android" and setting not in ANDROID_ROWS_KEPT:
            continue
        kept.append((label, setting, choices, help_text, None, *named))
    return kept


def switch_video_spec() -> dict:
    spec = copy.deepcopy(port_settings.SCREENS["video_settings"])
    spec["rows"] = switch_rows(spec["rows"]) + SWITCH_VIDEO_ROWS
    # (rows that take the place of a desktop row, which is not here)
    spec["same_place"] = []
    spec["views"] = [(name, label, help_text, switch_rows(rows)) for name, label, help_text, rows in spec["views"]]
    return spec


def main_menu_lines() -> list:
    """the game's main menu without QUIT GAME: its row, and B's and Back's
    way to the quit screen"""
    lines = (MENUS / "ce" / MAIN_MENU).read_text().split("\n")
    gone = ('<on event="back" open="main_menu/quit_select/quit_screen"/>',
            '<on event="b" open="main_menu/quit_select/quit_screen"/>',
            '<child widget="main_menu/main_menu_item_quit_game"')
    kept = [line for line in lines if not any(text in line for text in gone)]
    if len(kept) != len(lines) - 3:
        raise SystemExit(f"{MAIN_MENU}: expected the quit row and its two handlers, found {len(lines) - len(kept)}")
    return kept


def files() -> dict:
    """the files, by their paths below the menus folder"""
    port_settings.SCREENS["video_settings"] = switch_video_spec()
    port_settings.MAXIMUM_PLAYERS = [count for count in port_settings.MAXIMUM_PLAYERS if count <= HOSTED_PLAYERS_LIMIT]
    settings = port_settings.settings_files()
    multiplayer = port_settings.multiplayer_files()
    return {
        f"ce/{VIDEO}": settings[VIDEO],
        f"ce/{SERVER}": multiplayer[SERVER],
        f"ce/{MAIN_MENU}": main_menu_lines(),
        "chupathingy/settings_pages.xml": port_settings.chupathingy_settings_pages(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "switch" / "menus",
                        help="the menus folder to write (default: build/switch/menus)")
    parser.add_argument("--stamp", type=Path, help="a file touched when done (the build's)")
    args = parser.parse_args()
    for name, lines in files().items():
        if not (MENUS / name).is_file():
            print(f"{name}: not a file the game embeds, so it would replace nothing", file=sys.stderr)
            return 1
        path = args.out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(lines)
        if not text.endswith("\n"):
            text += "\n"
        path.write_text(text)
    if args.stamp:
        args.stamp.parent.mkdir(parents=True, exist_ok=True)
        args.stamp.write_text("")
    print(f"{args.out}: {len(files())} menu files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
