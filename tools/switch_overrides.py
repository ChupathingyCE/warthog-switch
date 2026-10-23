#!/usr/bin/env python3
"""The port's overrides of the game's files (port/switch/overrides/README.md):
fixes the Switch needs in the game itself, each a whole copy of the fixed
file, compiled in the game file's place until upstream has it.

  python3 tools/switch_overrides.py          lists them, and checks them
  python3 tools/switch_overrides.py --diff   shows each one's change

The check fails (exit 1) when an override no longer differs from the
submodule's file (upstream has it: repin, delete the override and its entry),
when the game has no file at its path (renamed or removed upstream), or when
README.md does not list it. The Port tests workflow runs it.
"""

import argparse
import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "chupathingyce"
OVERRIDES = ROOT / "port" / "switch" / "overrides"
README = OVERRIDES / "README.md"


def overrides() -> list:
    """the override files, by their path in the game ("source/memory/data.c")"""
    return sorted(path.relative_to(OVERRIDES).as_posix() for path in OVERRIDES.rglob("*")
                  if path.is_file() and path.suffix in (".c", ".h"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--diff", action="store_true", help="show each override's change against the game's file")
    arguments = parser.parse_args()

    names = overrides()
    readme = README.read_text(encoding="utf-8") if README.is_file() else ""
    failed = False
    if not names:
        print("no overrides: the game is built from the submodule alone")
        return 0
    for name in names:
        override = OVERRIDES / name
        upstream = GAME / name
        if not upstream.is_file():
            print(f"{name}: FAILED, the game has no such file (renamed or removed upstream?)")
            failed = True
            continue
        ours = override.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        theirs = upstream.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        changed = sum(1 for line in difflib.unified_diff(theirs, ours, n=0) if line[:1] in "+-" and
                      not line.startswith(("+++", "---")))
        if not changed:
            print(f"{name}: FAILED, identical to the submodule's file: upstream has it, so delete the override "
                  f"and its entry in {README.relative_to(ROOT)}")
            failed = True
        elif f"## {name}" not in readme:
            print(f"{name}: FAILED, not listed in {README.relative_to(ROOT)} (a heading '## {name}')")
            failed = True
        else:
            print(f"{name}: overrides the submodule's ({changed} lines differ)")
        if arguments.diff:
            sys.stdout.writelines(difflib.unified_diff(theirs, ours, fromfile=f"chupathingyce/{name}",
                                                       tofile=f"port/switch/overrides/{name}"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
