#!/usr/bin/env python3
"""The Switch's own menu files, written for the card's menus folder.

    python3 tools/switch_menus.py --out build/switch/menus

The game's menus are XML files embedded in it (chupathingyce/port/assets/menus,
tools/embed_assets.py), and a file of the same name in the data folder's
menus/ replaces the embedded one when the game starts (port/linux/src/
menu_files.c logs each). The Switch keeps to the Chupathingy menus (the
game's default, display.menus; the PC version's and the Xbox's menus are
not adjusted for it), and rather than carry its rows in the game's files,
the port writes the three files it needs its own of, with the game's
generator (chupathingyce/tools/port_settings.py) and its rows:

- The settings pages (chupathingy/settings_pages.xml): each page with the
  rows the Switch has, packed with no gaps where the desktop's would be, and
  Video Setup with its own: RESOLUTION LIMIT (display.resolution_limit),
  DYNAMIC RESOLUTION (display.dynamic_resolution) and CPU CLOCK
  (performance.cpu_clock), which the game declares and the Switch's
  renderer and host read. Interface loses MENU STYLE, so the menus stay the
  Chupathingy ones (config.toml's display.menus still chooses, for anyone
  who wants the others as they are). The pages place rows whose widgets the
  PC version's screen files define, so Video Setup's file
  (ce/...video_settings.xml) is written too, for the three rows' widgets.
- The main menu (chupathingy/main_menu.xml): no QUIT, and B does not offer
  to quit: the console's HOME button is the way out.
- Controls Setup's controller gets a third page under SHOW, GYRO (the game's
  menu_functions.c knows the page on the Switch): gyro aim always, only on
  zoom or off, its two sensitivities and two inverts (input.gyro_*, which the
  game declares for the Switch; port/linux/src/xinput_sdl.c reads them). The
  pages place rows whose widgets the PC version's Controls Setup file
  defines, so that file (ce/...controls_setup.xml) is written too.

The most players a game hosted here may have is 48 (port/linux/game/
menu_functions.c's HOSTED_PLAYERS_LIMIT, behind HALO_SWITCH_CONSOLE), which
the console was measured to hold; the host setup's row stops there.

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

MAIN_MENU = "chupathingy/main_menu.xml"
CONTROLS_NAME = f"{port_settings.PE}/{port_settings.CONTROLS_SCREEN}".replace("/", ".") + ".xml"
CONTROLS = f"ce/{CONTROLS_NAME}"
SETTINGS_PAGES = "chupathingy/settings_pages.xml"
VIDEO_NAME = f"{port_settings.PE}/video_settings".replace("/", ".") + ".xml"
VIDEO = f"ce/{VIDEO_NAME}"

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
# the controller's gyro page: its rows (the reference's Gyro Aim screen)
GYRO_SENSITIVITIES = [(f"{value:g}", f"{value:g}") for value in
                      (0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 9, 10)]
GYRO_ROWS = [
    ("GYRO AIM:", "input.gyro_aim", port_settings.ON_OFF + [("ONLY ON ZOOM", "zoom")],
     "Turn the view with the gyroscope,\nalways, or only while zoomed in.", None),
    ("HORIZONTAL SENSITIVITY:", "input.gyro_sensitivity_horizontal", GYRO_SENSITIVITIES,
     "How far the view turns left and right.\n1 is the sensor's own turn.", None),
    ("VERTICAL SENSITIVITY:", "input.gyro_sensitivity_vertical", GYRO_SENSITIVITIES,
     "How far the view turns up and down.\n1 is the sensor's own turn.", None),
    ("INVERT HORIZONTAL:", "input.gyro_invert_horizontal", port_settings.YES_NO,
     "Turning it right looks left.", None),
    ("INVERT VERTICAL:", "input.gyro_invert_vertical", port_settings.YES_NO,
     "Tilting it up looks down.", None),
]
# the Android rows the Switch has too (its game is built as Android's): the
# rest of Android's are its own (its anti-aliasing is the OpenGL renderer's)
ANDROID_ROWS_KEPT = {"display.interpolation"}
# rows for every platform the Switch leaves out: the menus stay the
# Chupathingy ones
ROWS_LEFT_OUT = {"display.menus"}
# the main menu's way to the quit screen: the row, taken out, and B's and
# Back's, made to do nothing (with no handler B's default is back, which
# closes the main menu itself)
QUIT_ROW = '<child widget="chupathingy/main_menu_quit"'
QUIT_HANDLERS = {'<on event="back" open="chupathingy/quit_screen"/>': '<on event="back" run="NULL"/>',
                 '<on event="b" open="chupathingy/quit_screen"/>': '<on event="b" run="NULL"/>'}


def switch_rows(rows: list) -> list:
    """the rows the Switch shows, with no platform: the desktop's left out,
    Android's but the few it shares, and the rest for every platform"""
    kept = []
    for row in rows:
        label, setting, choices, help_text, platform, *named = row
        if platform == "desktop" or setting in ROWS_LEFT_OUT:
            continue
        if platform == "android" and setting not in ANDROID_ROWS_KEPT:
            continue
        kept.append((label, setting, choices, help_text, None, *named))
    return kept


def switch_spec(spec: dict, extra_rows: list) -> dict:
    """a screen's spec with the Switch's rows: the others' pared down and
    its own added, with no row taking another's place"""
    spec = copy.deepcopy(spec)
    spec["rows"] = switch_rows(spec["rows"]) + extra_rows
    # (rows that take the place of a desktop row, which is not here)
    spec["same_place"] = []
    spec["views"] = [(name, label, help_text, switch_rows(rows))
                     for name, label, help_text, rows in spec.get("views", [])]
    return spec


def main_menu_lines() -> list:
    """the game's main menu without QUIT"""
    lines = (MENUS / MAIN_MENU).read_text().split("\n")
    kept, changed = [], 0
    for line in lines:
        if QUIT_ROW in line:
            changed += 1
            continue
        for old, new in QUIT_HANDLERS.items():
            if old in line:
                line = line.replace(old, new)
                changed += 1
        kept.append(line)
    if changed != 1 + len(QUIT_HANDLERS):
        raise SystemExit(f"{MAIN_MENU}: expected the quit row and its two handlers, found {changed}")
    return kept


def controls_rows_with_gyro(original):
    """Controls Setup's rows and widgets with the controller's GYRO page: a
    third choice of SHOW, a mark of its own after the buttons', and the gyro
    rows after it (their labels and helps added to the screen's strings).
    The SHOW chooser's row, marked for the settings and buttons pages, is
    marked for the gyro page too."""
    def rows_and_extra():
        base = f"{port_settings.PE}/{port_settings.CONTROLS_SCREEN}"
        rows, extra = original()
        first_label = len(port_settings.MOUSE_ROWS) + len(port_settings.GAMEPAD_ROWS)
        rows = [(row.replace("view_gamepad_buttons", "view_gamepad_buttons_gyro"), platform, place)
                for row, platform, place in rows]
        extra = [line.replace("view_gamepad_buttons", "view_gamepad_buttons_gyro") for line in extra]
        rows.append((f"{base}/view_gyro", None, 0))
        added = port_settings._mark(base, "gyro")
        for place, row in enumerate(GYRO_ROWS, 2):
            key = port_settings._row_key(row)
            rows.append((f"{base}/op_{key}", None, place))
            added += port_settings._setting_row(base, row, key, first_label + place - 2)
        # (the strings close the widgets: the rows go before them, the
        # labels and helps into them)
        labels_at = next(index for index, line in enumerate(extra) if line == f'\t<strings name="{base}/labels">')
        extra = extra[:labels_at] + added + extra[labels_at:]
        for name, texts in (("labels", [label for label, *_ in GYRO_ROWS]),
                            ("help_strings", [row[3].replace("\n", "\\n") for row in GYRO_ROWS])):
            start = extra.index(f'\t<strings name="{base}/{name}">')
            end = extra.index("\t</strings>", start)
            extra[end:end] = [f"\t\t<string{port_settings.attributes([('text', text)])}/>" for text in texts]
        return rows, extra
    return rows_and_extra


def files() -> dict:
    """the files, by their paths below the menus folder"""
    port_settings.CONTROLLER_PAGES = [*port_settings.CONTROLLER_PAGES, "GYRO"]
    port_settings._controls_rows = controls_rows_with_gyro(port_settings._controls_rows)
    for folder, spec in port_settings.SCREENS.items():
        port_settings.SCREENS[folder] = switch_spec(spec, SWITCH_VIDEO_ROWS if folder == "video_settings" else [])
    return {
        SETTINGS_PAGES: port_settings.chupathingy_settings_pages(),
        MAIN_MENU: main_menu_lines(),
        VIDEO: port_settings.settings_files()[VIDEO_NAME],
        CONTROLS: port_settings.settings_files()[CONTROLS_NAME],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "switch" / "menus",
                        help="the menus folder to write (default: build/switch/menus)")
    parser.add_argument("--stamp", type=Path, help="a file touched when done (the build's)")
    args = parser.parse_args()
    written = files()
    for name, lines in written.items():
        if not (MENUS / name).is_file():
            print(f"{name}: not a file the game embeds, so it would replace nothing", file=sys.stderr)
            return 1
        path = args.out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(lines)
        if not text.endswith("\n"):
            text += "\n"
        path.write_text(text)
    # (files an earlier version wrote and this one does not)
    for stale in sorted(args.out.rglob("*.xml")):
        if stale.relative_to(args.out).as_posix() not in written:
            stale.unlink()
    if args.stamp:
        args.stamp.parent.mkdir(parents=True, exist_ok=True)
        args.stamp.write_text("")
    print(f"{args.out}: {len(written)} menu files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
