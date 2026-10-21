"""Ninja rules for a Nintendo Switch build (``ninja switch``): the port's
build.py, which the game's configure.py loads (--console-port port/switch;
the game's tools/console_build.py).

From this repository's root, with the game in chupathingyce/ (a submodule):

    python3 chupathingyce/configure.py --console-port port/switch [--devkitpro DIR]
    ninja switch

The port's own option:

    --devkitpro DIR     devkitPro's install, with devkitA64, libnx and
                        deko3d (default DEVKITPRO, or /opt/devkitpro)

The port's sources are not here yet: they arrive in this repository's first
pull request. Until then generate() stops configure.py with a message
saying so.
"""

import os
from pathlib import Path
from typing import Any, List, Optional

from tools.console_build import ConsolePort
from tools.ninja_syntax import Writer


def add_arguments(parser: Any) -> None:
    """the port's own configure.py options"""
    parser.add_argument(
        "--devkitpro",
        metavar="DIR",
        type=Path,
        help="devkitPro's install for `ninja switch`, with devkitA64, libnx and deko3d "
        "(default: DEVKITPRO, or /opt/devkitpro)",
    )


def devkitpro_dir(sln: Any) -> Optional[Path]:
    """devkitPro's install, where it has devkitA64's compiler and libnx"""
    value = getattr(sln.args, "devkitpro", None) or os.environ.get("DEVKITPRO") or "/opt/devkitpro"
    path = Path(value).expanduser().resolve()
    if (path / "devkitA64" / "bin" / "aarch64-none-elf-gcc").is_file() and (path / "libnx" / "include").is_dir():
        return path
    return None


def configure_inputs(port: ConsolePort) -> List[Path]:
    """Files whose change must re-run configure.py."""
    return [port.root]


def generate(n: Writer, sln: Any, port: ConsolePort) -> None:
    sources = [path for path in Path(port.root).rglob("*") if path.suffix in (".c", ".cpp", ".h")]
    if not sources:
        raise SystemExit(
            f"configure.py: {port.root}: the Switch port's files are not here yet; they arrive in "
            "warthog-switch's first pull request (port/switch/README.md)"
        )
    raise SystemExit(f"configure.py: {port.root / 'build.py'} does not build the port's files yet")
