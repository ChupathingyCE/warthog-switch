#!/usr/bin/env python3
"""The Switch guest's import stubs and the host's import table, from the
game's tools/android_imports.py, with the three posix helpers that take a
descriptor sent to the host's translation of the guest's descriptor table
(port/switch/host/host_syscall.c: host_guest_posix_fstat, _seek, _truncate).

Usage: switch_imports.py GAME_ANDROID_IMPORTS --host-table table.c output.s list...

GAME_ANDROID_IMPORTS is the game's tools/android_imports.py; the rest are
its arguments. The table it writes names posix_<name> for each
hostposix_<name> import; the three are renamed in it afterwards.
"""

import re
import subprocess
import sys
from pathlib import Path

TRANSLATED = ("fstat", "seek", "truncate")


def main() -> int:
    arguments = sys.argv[1:]
    if len(arguments) < 4 or arguments[1] != "--host-table":
        print(__doc__, file=sys.stderr)
        return 2
    tool, table = Path(arguments[0]), Path(arguments[2])
    subprocess.run([sys.executable, str(tool), *arguments[1:]], check=True)
    text = table.read_text(encoding="utf-8")
    for name in TRANSLATED:
        text = re.sub(rf"(?<![A-Za-z0-9_])posix_{name}(?![A-Za-z0-9_])", f"host_guest_posix_{name}", text)
    table.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
