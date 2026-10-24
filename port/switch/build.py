"""Ninja rules for the Nintendo Switch build (``ninja switch``): the port's
build.py, which the game's configure.py loads (--console-port port/switch;
the game's tools/console_build.py).

From this repository's root, with the game in chupathingyce/ (a submodule):

    python3 chupathingyce/configure.py --console-port port/switch [--devkitpro DIR]
    ninja switch

The port's own option:

    --devkitpro DIR     devkitPro's install, with devkitA64, libnx, deko3d and
                        the Switch portlibs (SDL2, Mesa; default DEVKITPRO,
                        or /opt/devkitpro)

The port (port/switch/README.md) runs the same ILP32 AArch64 guest image as
the game's Android port inside an ordinary devkitA64 homebrew program. This
graph builds

- the guest image, build/switch/halo_guest.elf: the Android guest, AArch64
  code with 32-bit pointers built by the same clang for arm64_32 and the
  same linker script (the game's port/android), with the deko3d renderer
  (port/switch/guest, port/switch/DEKO3D.md) in the OpenGL renderer's place;
- the host, build/switch/halo.nro: port/switch/host, the Android host made
  into a homebrew program, which answers the guest's SDL3 calls with
  devkitPro's SDL2 and draws with deko3d.

Two toolchains are involved and neither can be replaced by the other. The
guest needs clang's arm64_32 target and the NDK's llvm-ar and ld.lld, and
devkitA64 is LP64 only, so it cannot build the guest. The host needs
devkitA64's compiler and libnx. The NDK is used only for the guest
(configure.py --android-ndk, or ANDROID_NDK_HOME, as the Android build).

The guest's sources, flags, libc and runtime are the Android build's
(the game's tools/android_build.py), read from there; what is the Switch's
is here. The build is generated when devkitPro and the NDK are found, and
writes a comment saying why when they are not.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.android_build import (ANDROID_API, EXPAT_SOURCES, GUEST_ABI_FLAGS, GUEST_CODE_FLAGS, MUSL_DIRECTORIES,
                                 MUSL_EXCLUDE, MUSL_FILES, MUSL_SHA256, MUSL_THREAD_PREFIXES, MUSL_URL, MUSL_VERSION,
                                 SDL_COMMIT, SDL_TAG, SDL_URL, VARIADIC_PROTOTYPE_FILES, ZLIB_DEFINES, ZLIB_SOURCES,
                                 _find_ndk, ndk_toolchain)
from tools.console_build import ConsolePort, console_defines
from tools.embed_assets import FONT_LIST, PROMPT_ICONS, UI_FONT_FILES, hud_asset_inputs, hud_configure_inputs
from tools.linux_build import (compile_launcher, CUSTOM_EDITION_DEFINES, game_browser_defines, LINUX_PROFILE,
                                MINIUPNPC_DEFINES, pgo_mode, pgo_profile, profile_use_flags, updater_defines,
                                XDK_INCLUDE)
from tools.ninja_syntax import Writer
from tools.version import VERSION_SOURCES, commit_inputs

# devkitPro's static graphics and window libraries. Mesa is static (the
# switch-mesa package ships libEGL.a and libGLESv2.a), so there is no
# libEGL.so to load at run time and none has to be shipped.
# libglapi is Mesa's own dispatch table and has to be named; Mesa is C++
# (nv50_ir and its exceptions), so the host is linked with the C++ driver
# to bring in the standard library, which is what LittleGPTracker's Switch
# Makefile does for the same reason. deko3d is the installed libdeko3d.a,
# for the deko3d renderer's host half (host_dk.c).
HOST_LIBRARIES = ["SDL2", "EGL", "GLESv2", "glapi", "drm_nouveau", "deko3d", "nx", "pthread", "m"]

# UAM, deko3d's shader compiler, built as a library for the console so that
# the deko3d renderer can compile shaders at run time (port/switch/DEKO3D.md).
# devkitPro ships it only as a PC tool. Pinned, and patched (uam.patch) to
# build a static library beside the tool and to check for mako without
# distutils, which Python 3.12 dropped. Its build runs Python's mako, bison
# and flex on the build machine. The shader cache names its folder for the
# commit (host_dk_shaders.c).
UAM_URL = "https://github.com/devkitPro/uam.git"
UAM_COMMIT = "5a5afc2bae8b55409ab36ba45be63fcb73f68993"

# What the console shows for this program in its menus. Fixed rather than
# taken from the environment: $USER on a build machine is whoever's account
# ran it, which would put a different publisher on every release and on CI
# whatever the runner happens to be called.
NACP_TITLE = "ChupaThingyCE"
NACP_AUTHOR = "thelinkin3000"
NACP_VERSION = "1.0.0"

# Where the Switch's guest image is linked to run: HALO_GUEST_IMAGE_BASE under
# HALO_SWITCH_CONSOLE in the game's port/android/include/halo_android_abi.h,
# which has to say the same. Not Android's 0x88000000, which a Switch will not
# map. The link places the image header there (--section-start) and the rest
# of the game's port/android/guest/guest.ld follows it, so the Android port's
# link and image stay as they are.
GUEST_IMAGE_BASE = 0x3c000000

# The OpenGL renderer's device, texture cache, anti-aliasing passes and
# shader cache, whose places the deko3d renderer's units take; and the
# host-only units the guest runtime replaces
# (ui_overlay.c draws with GL: port/switch/guest/ui_overlay_dk.c is its twin here)
OPENGL_ONLY = {"d3d8_gl.c", "xbox_textures.c", "xgpu_post.c", "xgpu_shader_cache.c", "ui_overlay.c"}
GUEST_HOST_ONLY = {"memory_watch.c"}  # replaced by guest_memory_watch.c
# the overrides of the game's files already announced by this configure run
_overrides_said: set = set()

# this repository's tools, beside the port
TOOLS_DIR = Path(os.path.relpath(Path(__file__).resolve().parents[2] / "tools"))


def _quote(path: Any) -> str:
    text = str(path).replace(os.sep, "/")
    return f'"{text}"' if " " in text else text


def add_arguments(parser: Any) -> None:
    """the port's own configure.py options"""
    parser.add_argument(
        "--devkitpro",
        metavar="DIR",
        type=Path,
        help="devkitPro's install for `ninja switch`, with devkitA64, libnx, deko3d and the Switch portlibs "
        "(default: DEVKITPRO, or /opt/devkitpro)",
    )


def devkitpro_dir(sln: Any) -> Optional[Path]:
    """devkitPro's install: --devkitpro's alone when it is given, else
    DEVKITPRO's, /opt/devkitpro or ~/devkitpro, whichever is there"""
    explicit = getattr(sln.args, "devkitpro", None)
    candidates = [str(explicit)] if explicit else [os.environ.get("DEVKITPRO"), "/opt/devkitpro",
                                                    str(Path.home() / "devkitpro")]
    for candidate in candidates:
        if candidate and Path(candidate).expanduser().is_dir():
            return Path(candidate).expanduser().resolve()
    return None


def configure_inputs(port: ConsolePort) -> List[Path]:
    """Files whose change must re-run configure.py."""
    game = port.game
    return [port.path("host"), port.path("guest"), port.path("overrides"), port.path("host_imports.list"),
            port.path("uam.patch"),
            game / "port" / "android" / "guest" / "runtime", game / "port" / "android" / "host_imports.list",
            game / "port" / "linux" / "src", game / "port" / "linux" / "port.json",
            *(game / path for path in hud_configure_inputs()),
            # (the game's commit, recorded in the guest's identity: tools/version.py)
            *commit_inputs()]


# ---------- the downloads: musl and SDL3 (the Android build's, pinned the same), and UAM

def fetch_third_party(third_party: Path) -> None:
    """Download musl and SDL3 into the build's third_party (configure time, once)."""
    musl_dir = third_party / f"musl-{MUSL_VERSION}"
    sdl_dir = third_party / "SDL3"
    third_party.mkdir(parents=True, exist_ok=True)
    if not musl_dir.is_dir():
        print(f"Downloading {MUSL_URL}")
        archive = third_party / f"musl-{MUSL_VERSION}.tar.gz"
        subprocess.run(["curl", "-sSfL", "-o", str(archive), MUSL_URL], check=True)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != MUSL_SHA256:
            archive.unlink()
            raise SystemExit(f"{MUSL_URL}: SHA-256 {digest}, not the pinned {MUSL_SHA256}")
        subprocess.run(["tar", "xzf", archive.name], cwd=third_party, check=True)
        archive.unlink()
    if not sdl_dir.is_dir():
        print(f"Cloning SDL3 {SDL_TAG}")
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", SDL_TAG, SDL_URL, str(sdl_dir)], check=True)
        commit = subprocess.run(["git", "-C", str(sdl_dir), "rev-parse", "HEAD"], capture_output=True, text=True,
                                check=True).stdout.strip()
        if commit != SDL_COMMIT:
            shutil.rmtree(sdl_dir)
            raise SystemExit(f"SDL3 {SDL_TAG} is {commit}, not the pinned {SDL_COMMIT}")


def musl_sources(musl_dir: Path) -> List[Path]:
    """the musl sources the guest's libc is built from (the Android build's
    choice: tools/android_build.py's MUSL_* lists)"""
    src = musl_dir / "src"
    result = set()
    for directory in MUSL_DIRECTORIES:
        result.update((src / directory).glob("*.c"))
    for name in MUSL_FILES:
        result.add(src / name)
    for path in (src / "thread").glob("*.c"):
        if path.name.startswith(MUSL_THREAD_PREFIXES):
            result.add(path)
    sources = []
    for path in sorted(result):
        relative = path.relative_to(src).as_posix()
        if relative in MUSL_EXCLUDE or any(relative.startswith(e + "/") for e in MUSL_EXCLUDE):
            continue
        sources.append(path)
    return sources


def fetch_uam(uam_dir: Path, patch: Path) -> None:
    """Clone UAM at its pinned commit and apply the port's patch (configure
    time, and again whenever the patch changes: the marker records which
    patch the clone has)."""
    marker = UAM_COMMIT + " " + hashlib.sha256(patch.read_bytes()).hexdigest() + "\n"
    if (uam_dir / ".patched").is_file() and (uam_dir / ".patched").read_text() == marker:
        return
    if uam_dir.exists():
        shutil.rmtree(uam_dir)
    uam_dir.parent.mkdir(parents=True, exist_ok=True)
    print(f"Cloning UAM {UAM_COMMIT[:12]}")
    subprocess.run(["git", "init", "-q", str(uam_dir)], check=True)
    subprocess.run(["git", "-C", str(uam_dir), "fetch", "-q", "--depth", "1", UAM_URL, UAM_COMMIT], check=True)
    subprocess.run(["git", "-C", str(uam_dir), "checkout", "-q", "FETCH_HEAD"], check=True)
    subprocess.run(["git", "-C", str(uam_dir), "apply", str(patch.resolve())], check=True)
    (uam_dir / ".patched").write_text(marker)


def _bison_for_uam() -> Optional[Path]:
    """A bison that accepts UAM's grammar. macOS ships 2.3, which rejects it;
    Homebrew's bison is keg-only, so it is not the bison on PATH."""
    candidates = []
    found = shutil.which("bison")
    if found:
        candidates.append(Path(found))
    candidates.extend([Path("/opt/homebrew/opt/bison/bin/bison"), Path("/usr/local/opt/bison/bin/bison")])
    seen = set()
    for path in candidates:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        result = subprocess.run([str(path), "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            continue
        for word in result.stdout.split():
            if word[:1].isdigit():
                if int(word.split(".", 1)[0]) >= 3:
                    return path
                break
    return None


def _uam_build(n: Writer, build: Path, uam_dir: Path, patch: Path, devkitpro: Path, host_cc: Path,
               host_arch: str) -> Optional[Path]:
    """Ninja rules for build/switch/uam/libuam.a, or None (and a comment) if UAM cannot be built here."""
    if not shutil.which("meson") or not shutil.which("flex"):
        n.comment("Switch build: no UAM (it needs meson and flex)")
        return None
    bison = _bison_for_uam()
    if bison is None:
        n.comment("Switch build: no UAM (it needs bison 3 or newer; macOS ships 2.3, so: brew install bison)")
        return None
    if subprocess.run([sys.executable, "-c", "import mako"], capture_output=True).returncode != 0:
        n.comment("Switch build: no UAM (it needs Python's mako: pip install --user mako)")
        return None
    try:
        fetch_uam(uam_dir, patch)
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"Switch build: cannot fetch UAM ({error})", file=sys.stderr)
        return None

    build_dir = build / "uam"
    cross_file = build_dir / "cross.ini"
    native_file = build_dir / "native.ini"
    flags = ", ".join(f"'{flag}'" for flag in [*host_arch.split(), "-D__SWITCH__", "-isystem",
                                                str(devkitpro / "libnx" / "include")])
    link_flags = ", ".join(f"'{flag}'" for flag in [f"-specs={devkitpro / 'libnx' / 'switch.specs'}",
                                                     *host_arch.split(), f"-L{devkitpro / 'libnx' / 'lib'}", "-lnx"])
    build_dir.mkdir(parents=True, exist_ok=True)
    cross_file.write_text(
        "[binaries]\n"
        f"c = '{host_cc}'\n"
        f"cpp = '{host_cc.parent / 'aarch64-none-elf-g++'}'\n"
        f"ar = '{host_cc.parent / 'aarch64-none-elf-gcc-ar'}'\n"
        f"strip = '{host_cc.parent / 'aarch64-none-elf-strip'}'\n"
        "\n[built-in options]\n"
        f"c_args = [{flags}]\ncpp_args = [{flags}]\n"
        f"c_link_args = [{link_flags}]\ncpp_link_args = [{link_flags}]\n"
        "\n[properties]\nneeds_exe_wrapper = true\n"
        "\n[host_machine]\nsystem = 'horizon'\ncpu_family = 'aarch64'\ncpu = 'cortex-a57'\nendian = 'little'\n",
        encoding="utf-8")
    # bison is a native tool (find_program native: true), so the cross file
    # does not choose it. Point meson at one new enough to parse the grammar.
    native_file.write_text(f"[binaries]\nbison = '{bison}'\n", encoding="utf-8")

    # meson's build of the library is a thin archive (members by path), so it
    # is repacked into an ordinary one that can be linked from anywhere.
    #
    # b_staticpic=false: meson compiles a static library with -fPIC by default,
    # after the cross file's -fPIE, and -fPIC gives thread-local variables an
    # access model that needs the thread pointer in a register - while
    # devkitA64's -mtp=soft gets it from a call (__aarch64_read_tp) whose result
    # overwrites the variable's offset. The code then reads the thread pointer
    # plus itself, and the first compile faults (uam.patch's per-thread state;
    # the probe found it). -fPIE, as the host is built, uses local-exec, which
    # works.
    library = build_dir / "libuam.a"
    meson_dir = build_dir / "meson"
    ar = host_cc.parent / "aarch64-none-elf-ar"
    n.rule(
        name="switch_uam",
        command=(f"rm -rf {meson_dir} && meson setup -Db_staticpic=false --cross-file {cross_file.resolve()} "
                 f"--native-file {native_file.resolve()} "
                 f"{meson_dir.resolve()} {uam_dir.resolve()} > /dev/null && ninja -C {meson_dir} libuam.a > /dev/null && "
                 f"rm -f $out && cd {meson_dir} && {ar} rcs {library.resolve()} $$({ar} t libuam.a)"),
        description="SWITCH UAM $out",
    )
    n.build(outputs=library, rule="switch_uam", implicit=[patch, uam_dir / ".patched", cross_file, native_file])
    n.build(outputs="switch-uam", rule="phony", inputs=[library])
    return library


# ---------- the build

def switch_updater_defines(release: bool) -> str:
    """the self-updater's build (port/switch/host/host_update.c): its number,
    from HALO_BUILD_NUMBER (.github/workflows/release.yml gives a release
    tag's builds its run number; none elsewhere, which never look for
    updates), and
    its flavour, which names the release's archive (halo-switch-<flavour>.zip)"""
    number = os.environ.get("HALO_BUILD_NUMBER", "0")
    if not number.isdigit():
        number = "0"
    flavor = "release" if release else "debug"
    return f'-DHALO_BUILD_NUMBER={int(number)} -DHALO_BUILD_FLAVOR=\\"{flavor}\\"'


def generate(n: Writer, sln: Any, port: ConsolePort) -> None:
    game = port.game
    PORT_DIR = port.root
    ANDROID_DIR = game / "port" / "android"
    LINUX_DIR = game / "port" / "linux"
    THIRD_DIR = game / "port" / "third_party"
    TOML_DIR = THIRD_DIR / "tomlc17"
    EXPAT_DIR = THIRD_DIR / "expat"
    KCP_DIR = THIRD_DIR / "kcp"
    QRCODEGEN_DIR = THIRD_DIR / "qrcodegen"
    MONOCYPHER_DIR = THIRD_DIR / "monocypher"
    ZLIB_DIR = THIRD_DIR / "zlib"
    MUSL_MATH_DIR = THIRD_DIR / "musl-math"
    STB_DIR = THIRD_DIR / "stb"
    MINIUPNPC_DIR = THIRD_DIR / "miniupnpc"
    MBEDTLS_DIR = THIRD_DIR / "mbedtls"
    GAME_TOOLS = game / "tools"
    BUILD: Path = sln.build_dir / "switch"
    THIRD_PARTY = BUILD / "third_party"
    MUSL_DIR = THIRD_PARTY / f"musl-{MUSL_VERSION}"
    SDL_DIR = THIRD_PARTY / "SDL3"
    UAM_DIR = THIRD_PARTY / "uam"
    UAM_PATCH = PORT_DIR / "uam.patch"

    config_path = LINUX_DIR / "port.json"
    if not config_path.is_file() or not (PORT_DIR / "host").is_dir():
        return

    devkitpro = devkitpro_dir(sln)
    if not devkitpro:
        n.comment("Switch build: no devkitPro found (set DEVKITPRO or pass --devkitpro)")
        return
    host_cc = devkitpro / "devkitA64" / "bin" / "aarch64-none-elf-gcc"
    if not host_cc.is_file():
        n.comment(f"Switch build: no aarch64-none-elf-gcc under {devkitpro / 'devkitA64'}")
        return
    portlibs = devkitpro / "portlibs" / "switch"
    if not (portlibs / "lib" / "libSDL2.a").is_file():
        n.comment("Switch build: devkitPro has no SDL2 (dkp-pacman -S switch-sdl2 switch-mesa)")
        return

    ndk = Path(sln.android_ndk) if getattr(sln, "android_ndk", None) else _find_ndk()
    if not ndk or not ndk.is_dir():
        n.comment("Switch build: no NDK found (the guest is ILP32; devkitA64 cannot build it: "
                  "set ANDROID_NDK_HOME or pass --android-ndk)")
        return
    toolchain = ndk_toolchain(ndk)
    if not toolchain or not toolchain.is_dir():
        n.comment("Switch build: the NDK has no LLVM toolchain for this computer")
        return
    try:
        fetch_third_party(THIRD_PARTY)
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"Switch build disabled: cannot fetch musl/SDL3 ({error})", file=sys.stderr)
        return

    config: Dict[str, Any] = port.load_port_config()

    sysroot_include = toolchain / "sysroot" / "usr" / "include"
    ndk_bin = toolchain / "bin"
    # the NDK's own clang, whose compiler runtime the guest links as the
    # Android guest does
    ndk_cc = ndk_bin / f"aarch64-linux-android{ANDROID_API}-clang"
    guest_cc = getattr(sln, "android_guest_cc", None) or "clang"

    guest_dir = BUILD / "guest"
    obj_dir = guest_dir / "obj"
    gen_dir = guest_dir / "gen"
    libc_include = guest_dir / "libc_include"
    libc_internal = guest_dir / "libc_internal"
    gl_include = guest_dir / "gl_include"
    arch = ANDROID_DIR / "guest" / "libc" / "arch" / "arm64_32"
    semantics_header = BUILD / "halo_msvc_semantics.h"
    platform_semantics_header = BUILD / "platform_msvc_semantics.h"
    prefix_header = LINUX_DIR / "include" / "halo_linux_prefix.h"
    image = BUILD / "halo_guest.elf"
    host_obj_dir = BUILD / "host" / "obj"
    nro = BUILD / "halo.nro"
    python = "$python"

    n.comment("Switch build (ninja switch); see port/switch/README.md")
    n.variable("switch_guest_cc", guest_cc)
    n.variable("switch_ndk_bin", str(ndk_bin))
    n.variable("switch_ndk_cc", str(ndk_cc))
    n.variable("switch_host_cc", str(host_cc))
    # the C++ driver, for linking against Mesa
    n.variable("switch_host_gxx", str(host_cc.parent / "aarch64-none-elf-g++"))
    n.variable("switch_specs", str(devkitpro / "libnx" / "switch.specs"))
    # libnx is a separate tree from the portlibs, and the link needs both;
    # the paths are spelled out per -L below rather than in one variable,
    # because a space-separated list is not what -L takes
    switch_includes = " ".join(
        f"-I{path}" for path in (portlibs / "include", devkitpro / "libnx" / "include",
                                 devkitpro / "switch" / "include", devkitpro / "devkitA64" / "newlib" / "include")
    )

    # ---------- what the game's native builds generate, made here for the console's build directory

    # the MSVC semantics the game's sources need (file-scope tags, inline
    # functions as COMDATs), scanned by the game's tool as the Linux build
    # does: the game sees its own and the SDK declarations', the platform
    # layer only the SDK declarations'
    xdk_include = game / XDK_INCLUDE
    n.rule(
        name="switch_msvc_semantics",
        command=f"{python} {_quote(GAME_TOOLS / 'linux_msvc_semantics.py')} --output $out $scan",
        description="SWITCH MSVC SEMANTICS $out",
        restat=True,
    )
    xdk_headers = sorted(xdk_include.glob("*.h"))
    n.build(outputs=semantics_header, rule="switch_msvc_semantics",
            implicit=[GAME_TOOLS / "linux_msvc_semantics.py", *xdk_headers, *port.game_headers()],
            variables={"scan": f"--all-inlines --tags {_quote(game / 'source')} --inlines {_quote(game / 'source')} "
                               f"--inlines {_quote(xdk_include)}"})
    n.build(outputs=platform_semantics_header, rule="switch_msvc_semantics",
            implicit=[GAME_TOOLS / "linux_msvc_semantics.py", *xdk_headers],
            variables={"scan": f"--inlines {_quote(xdk_include)}"})

    # the high-res HUD's textures (the game's port/assets) and the overlay's
    # fonts, embedded by the game's tool (tools/embed_assets.py)
    hud_assets_c = gen_dir / "hud_hires_assets.c"
    n.rule(
        name="switch_embed_assets",
        command=f"{python} {_quote(GAME_TOOLS / 'embed_assets.py')} $out",
        description="SWITCH EMBED $out",
    )
    n.build(outputs=hud_assets_c, rule="switch_embed_assets",
            implicit=[GAME_TOOLS / "embed_assets.py", *(game / path for path in hud_asset_inputs())])
    embedded_sources = [hud_assets_c]
    if getattr(sln, "game_browser", False):
        ui_fonts_c = gen_dir / "ui_fonts.c"
        n.rule(
            name="switch_embed_fonts",
            command=f"{python} {_quote(GAME_TOOLS / 'embed_assets.py')} --fonts $out",
            description="SWITCH EMBED $out",
        )
        n.build(outputs=ui_fonts_c, rule="switch_embed_fonts",
                implicit=[GAME_TOOLS / "embed_assets.py", game / FONT_LIST, *(game / path for path in UI_FONT_FILES),
                          *(game / path for path in PROMPT_ICONS)])
        embedded_sources.append(ui_fonts_c)

    # ---------- the guest image, built exactly as the Android port builds it

    alltypes = libc_include / "bits" / "alltypes.h"
    syscall_h = libc_include / "bits" / "syscall.h"
    version_h = libc_internal / "version.h"
    n.rule(
        name="switch_alltypes",
        command=f"sed -f {MUSL_DIR}/tools/mkalltypes.sed $in > $out",
        description="SWITCH MUSL $out",
    )
    n.build(outputs=alltypes, rule="switch_alltypes",
            inputs=[arch / "bits" / "alltypes.h.in", MUSL_DIR / "include" / "alltypes.h.in"])
    n.rule(
        name="switch_syscall_h",
        command="cp $in $out && sed -n -e s/__NR_/SYS_/p < $in >> $out",
        description="SWITCH MUSL $out",
    )
    n.build(outputs=syscall_h, rule="switch_syscall_h", inputs=[arch / "bits" / "syscall.h.in"])
    n.rule(
        name="switch_version_h",
        command=f"echo '#define VERSION \"{MUSL_VERSION}\"' > $out",
        description="SWITCH MUSL $out",
    )
    n.build(outputs=version_h, rule="switch_version_h")

    # the NDK's OpenGL ES headers (C declarations only) for the guest
    gl_stamp = gl_include / "stamp"
    n.rule(
        name="switch_gl_include",
        command=(f"mkdir -p {gl_include} && ln -sfn {sysroot_include}/GLES2 {gl_include}/GLES2 && "
                 f"ln -sfn {sysroot_include}/GLES3 {gl_include}/GLES3 && "
                 f"ln -sfn {sysroot_include}/KHR {gl_include}/KHR && touch $out"),
        description="SWITCH GL HEADERS",
    )
    n.build(outputs=gl_stamp, rule="switch_gl_include")

    guest_gl_c = gen_dir / "guest_gl.c"
    gl_imports = gen_dir / "gl_imports.list"
    n.rule(
        name="switch_gl_stubs",
        command=(f"{python} {_quote(GAME_TOOLS / 'android_gl_stubs.py')} {LINUX_DIR}/src/gl.h "
                 f"{sysroot_include}/GLES3/gl32.h {sysroot_include}/GLES2/gl2ext.h {guest_gl_c} {gl_imports}"),
        description="SWITCH GL STUBS",
    )
    n.build(outputs=[guest_gl_c, gl_imports], rule="switch_gl_stubs",
            implicit=[GAME_TOOLS / "android_gl_stubs.py", LINUX_DIR / "src" / "gl.h"])

    # posix.h's helpers and the game list's (browser_http.h), as the Android
    # guest has them; the host answers the game list's with the game's own
    # posix_browser.c and Mbed TLS (below, the host)
    guest_posix_c = gen_dir / "guest_posix.c"
    posix_imports = gen_dir / "posix_imports.list"
    n.rule(
        name="switch_posix_stubs",
        command=(f"{python} {_quote(GAME_TOOLS / 'android_posix_stubs.py')} {LINUX_DIR}/src/posix.h "
                 f"{LINUX_DIR}/src/browser_http.h {guest_posix_c} {posix_imports}"),
        description="SWITCH POSIX STUBS",
    )
    n.build(outputs=[guest_posix_c, posix_imports], rule="switch_posix_stubs",
            implicit=[GAME_TOOLS / "android_posix_stubs.py", LINUX_DIR / "src" / "posix.h",
                      LINUX_DIR / "src" / "browser_http.h"])

    # the import stubs and the host's table (the game's tools/android_imports.py
    # through tools/switch_imports.py, which sends the posix helpers that take
    # a descriptor to the host's translation of it: host_syscall.c)
    imports_s = gen_dir / "imports.s"
    host_table_c = BUILD / "host" / "host_import_table.c"
    host_imports_list = ANDROID_DIR / "host_imports.list"
    # the Switch host's own: the deko3d renderer's (port/switch/host/host_dk.c)
    switch_imports_list = PORT_DIR / "host_imports.list"
    n.rule(
        name="switch_imports",
        command=(f"{python} {_quote(TOOLS_DIR / 'switch_imports.py')} {_quote(GAME_TOOLS / 'android_imports.py')} "
                 f"--host-table {host_table_c} {imports_s} $in"),
        description="SWITCH IMPORTS",
    )
    n.build(outputs=[imports_s, host_table_c], rule="switch_imports",
            inputs=[host_imports_list, switch_imports_list, posix_imports, gl_imports],
            implicit=[TOOLS_DIR / "switch_imports.py", GAME_TOOLS / "android_imports.py"])

    generated_headers = [*xdk_headers, alltypes, syscall_h, version_h, gl_stamp, semantics_header,
                         platform_semantics_header]

    n.newline()
    asm_convert = GAME_TOOLS / "android_asm_convert.py"
    n.rule(
        name="switch_guest_cc",
        command=(f"{compile_launcher(sln)}$switch_guest_cc -MMD -MF $out.d $cflags -S $in -o $out.darwin.s && "
                 f"{python} {_quote(asm_convert)} $out.darwin.s $out.s && "
                 f"$switch_guest_cc --target=aarch64-linux-android -c $out.s -o $out"),
        description="SWITCH CC $out",
        depfile="$out.d",
        deps="gcc",
    )
    n.rule(
        name="switch_guest_asm",
        command="$switch_guest_cc --target=aarch64-linux-android -c $in -o $out",
        description="SWITCH AS $out",
    )

    # The Android guest's flags (HALO_ANDROID among them: the Switch guest
    # takes the Android guest's path through the platform layer),
    # HALO_SWITCH_CONSOLE for what is the console's alone, and
    # HALO_WINDOW_REBASE: the console will not map memory at the window's
    # linked address, so the host puts it elsewhere and the game follows it
    # (source/cseries/xbox_address.h). configure.py's console options
    # (--release, --console-debug-tools, --console-no-debug-asserts:
    # tools/console_build.py) apply, but not --console-players: the Switch
    # keeps the PC builds' tables, as the Android guest does, and hosts as
    # the shared code lets it (halo_port_capacity.h).
    # (the game browser, the game list and dedicated servers, as every other
    # build has them: HALO_GAME_BROWSER, configure.py; and Halo PC's Custom
    # Edition maps, linux_build.py CUSTOM_EDITION_DEFINES, as the Android guest)
    console = [define for define in console_defines(sln) if not define.startswith("-DHALO_CONSOLE_PLAYERS=")]
    guest_abi = " ".join(GUEST_ABI_FLAGS + ["-DHALO_SWITCH_CONSOLE", "-DHALO_WINDOW_REBASE"] + console
                         + game_browser_defines(sln) + CUSTOM_EDITION_DEFINES)

    # musl is configured for an Apple target and passes
    # -fno-define-target-os-macros, which tells clang not to define that
    # target's OS macros. Not every clang has it (the NDK's clang 17.0.2 does
    # not), so the compiler is asked. Dropping the flag is safe because the
    # two macros it suppresses, __APPLE__ and __MACH__, are already undefined
    # by GUEST_ABI_FLAGS.
    if "-fno-define-target-os-macros" in guest_abi:
        probe = subprocess.run(
            [guest_cc, "--target=arm64_32-apple-watchos", "-fno-define-target-os-macros",
             "-E", "-x", "c", os.devnull, "-o", os.devnull],
            capture_output=True)
        if probe.returncode != 0:
            n.comment("Switch build: this clang has no -fno-define-target-os-macros; leaving it out")
            guest_abi = guest_abi.replace(" -fno-define-target-os-macros", "")
    guest_code = " ".join(GUEST_CODE_FLAGS)
    tool_implicit = [asm_convert, *generated_headers]
    linux_profile = game / LINUX_PROFILE
    profile = pgo_profile(sln, linux_profile if pgo_mode(sln) == "train" else None, [linux_profile], guest_cc)
    profile_flags = " ".join(profile_use_flags(profile))
    if profile:
        tool_implicit.append(profile)
    # the game's file names as the game spells them ("source/game/game.c",
    # not "chupathingyce/source/game/game.c"): the log's and the asserts'
    # names stay the desktop builds', and the build is the same wherever the
    # game is checked out
    file_names = (f"-fno-file-reproducible -fmacro-prefix-map={_quote(game.as_posix() + '/')}="
                  if game != Path(".") else "")

    def guest_object(source: Path, cflags: str, prefix: str = "") -> Path:
        obj = port.output_path(obj_dir / prefix, source).with_suffix(".o")
        if str(source).startswith(str(BUILD)):
            obj = obj_dir / prefix / source.relative_to(BUILD).with_suffix(".o")
        n.build(outputs=obj, rule="switch_guest_cc", inputs=source, implicit=tool_implicit,
                variables={"cflags": f"{cflags} {file_names}".rstrip()})
        return obj

    libc_includes = [
        f"-isystem {libc_include}", f"-isystem {arch}", f"-isystem {MUSL_DIR}/arch/generic",
        f"-isystem {MUSL_DIR}/include",
    ]

    # musl
    musl_cflags = " ".join([
        guest_abi, "-std=c99", "-ffreestanding", "-fno-common", "-D_XOPEN_SOURCE=700", "-w",
        f"-I{arch}", f"-I{MUSL_DIR}/arch/generic", f"-I{libc_internal}",
        f"-I{ANDROID_DIR}/guest/libc/src_include", f"-I{MUSL_DIR}/src/include",
        f"-I{MUSL_DIR}/src/internal", f"-I{libc_include}", f"-I{MUSL_DIR}/include",
    ])
    musl_objects = [guest_object(source, musl_cflags, "musl") for source in musl_sources(MUSL_DIR)]
    libguestc = guest_dir / "libguestc.a"
    n.rule(
        name="switch_ar",
        command="rm -f $out && $switch_ndk_bin/llvm-ar rcs $out @$out.rsp",
        description="SWITCH AR $out",
        rspfile="$out.rsp",
        rspfile_content="$in_newline",
    )
    n.build(outputs=libguestc, rule="switch_ar", inputs=musl_objects)

    # the game
    objects: List[Path] = []
    game_flags = [
        "-std=gnu89", "-D__STRICT_ANSI__", "-w",
        "-Wno-error=incompatible-pointer-types",
        "-Wno-error=incompatible-function-pointer-types",
        "-Wno-error=int-conversion",
        "-Wno-error=implicit-function-declaration",
        "-Wno-error=implicit-int",
        "-Wno-error=return-type",
    ]
    port_game_dir = game / config["game_sources"]
    # The port's overrides of the game's files (port/switch/overrides, laid
    # out as the game is: overrides/source/memory/data.c stands in for
    # source/memory/data.c): each a fix the Switch needs in the game itself,
    # kept as a whole copy until upstream has it. A .c is compiled in the
    # game file's place with its flags, and a .h is found before the game's
    # (the overrides' directories come first on the include path), so the
    # submodule stays at upstream's commit. overrides/README.md says what
    # each is for and where it is going; tools/switch_overrides.py lists
    # and checks them.
    overrides_dir = PORT_DIR / "overrides"
    overrides_left = {path.relative_to(overrides_dir).as_posix() for path in overrides_dir.rglob("*")
                      if path.suffix in (".c", ".h")}
    override_includes = " ".join(f"-I{overrides_dir / where}" for where in
                                 ("source", "source/main", "source/cseries", "port/linux/include", "port/linux/src")
                                 if (overrides_dir / where).is_dir())
    for name in sorted(overrides_left):
        if not (game / name).is_file():
            raise SystemExit(f"Switch: {overrides_dir / name} overrides no file of the game's: upstream renamed or "
                             f"removed it, or the override is misplaced")

    def override_of(source: Path, name: str):
        """the override to compile in place of the game's source, if there
        is one (said once: configure generates more than once)"""
        if name not in overrides_left:
            return None
        overrides_left.remove(name)
        if name not in _overrides_said:
            _overrides_said.add(name)
            print(f"Switch: {name} is built from the port's override, {overrides_dir / name} "
                  f"(waiting on upstream: {overrides_dir / 'README.md'})")
        return overrides_dir / name

    game_cflags = " ".join([
        guest_abi, guest_code, " ".join(game_flags), profile_flags,
        f"-include {prefix_header}", f"-include {semantics_header}",
        override_includes,
        f"-I{LINUX_DIR}/include",
        # the headers of the port's own game units (port/linux/game), for the
        # game sources that call them
        f"-iquote {_quote(port_game_dir)}",
        port.game_defines_and_includes(config, _quote), *libc_includes, f"-idirafter {_quote(xdk_include)}",
    ])
    for source in port.game_sources(config):
        name = port.game_relative(source)
        cflags = game_cflags
        if name in VARIADIC_PROTOTYPE_FILES:
            cflags += f" -include {ANDROID_DIR}/include/halo_android_variadic_prototypes.h"
        override = override_of(source, name)
        if override:
            # (its "x.h" includes find the game's own directory, as the game
            # file's would; an override header beside it still comes first)
            objects.append(guest_object(override, f"{cflags} -iquote {_quote(source.parent)}", "overrides"))
            continue
        objects.append(guest_object(source, cflags))
    for source in sorted(port_game_dir.glob("*.c")):
        objects.append(guest_object(source, game_cflags))
    # the dedicated server's director, with the game browser (server/), as
    # the Android guest has it
    if getattr(sln, "game_browser", False):
        for source in sorted((game / "server" / "src").glob("*.c")):
            objects.append(guest_object(source, game_cflags))

    # the platform layer shared with Linux, and the guest runtime
    platform_cflags = " ".join([
        guest_abi, guest_code, "-std=gnu11", "-D_GNU_SOURCE", "-DHALO_LINUX_PLATFORM_LAYER", "-w", profile_flags,
        f"-include {prefix_header}", f"-include {platform_semantics_header}",
        override_includes,
        f"-I{LINUX_DIR}/src", f"-I{LINUX_DIR}/include", f"-I{ANDROID_DIR}/guest/runtime",
        f"-I{ANDROID_DIR}/include", f"-I{TOML_DIR}", f"-I{EXPAT_DIR}", f"-I{KCP_DIR}", f"-I{QRCODEGEN_DIR}",
        f"-I{MONOCYPHER_DIR}", f"-I{ZLIB_DIR}", f"-I{game}/source", f"-I{game}/source/cseries",
        f"-I{SDL_DIR}/include", f"-I{gl_include}", *libc_includes, f"-idirafter {_quote(xdk_include)}",
    ])
    # (the overlay's fonts are plain C, drawn in the guest: stb_truetype)
    guest_posix = {"posix_ui_font.c": f"-I{STB_DIR}"}
    # the other posix_*.c run in the host
    for source in sorted((LINUX_DIR / "src").glob("*.c")):
        if source.name in guest_posix:
            objects.append(guest_object(source, f"{platform_cflags} {guest_posix[source.name]}"))
            continue
        if source.name.startswith("posix_") or source.name in GUEST_HOST_ONLY or source.name in OPENGL_ONLY:
            continue
        if source.name in VERSION_SOURCES:
            # (the game's version, channel and commit, as Android's guest has
            # them: tools/version.py; the main menu's version line and the logs)
            objects.append(guest_object(source, f"{platform_cflags} "
                                                f"{updater_defines(getattr(sln, 'port_release', False))}"))
            continue
        override = override_of(source, f"port/linux/src/{source.name}")
        if override:
            objects.append(guest_object(override, f"{platform_cflags} -iquote {_quote(source.parent)}", "overrides"))
            continue
        objects.append(guest_object(source, platform_cflags))
    for source in embedded_sources:
        objects.append(guest_object(source, platform_cflags))
    # the settings file's parser (port/third_party/tomlc17)
    objects.append(guest_object(TOML_DIR / "tomlc17.c", platform_cflags))
    # the menus' XML parser (port/third_party/expat; menu_files.c)
    for name in EXPAT_SOURCES:
        objects.append(guest_object(EXPAT_DIR / name, platform_cflags))
    # internet play's reliable streams (port/third_party/kcp; p2p.c)
    objects.append(guest_object(KCP_DIR / "ikcp.c", platform_cflags))
    # Link Profile's QR code (port/third_party/qrcodegen; browser.c)
    objects.append(guest_object(QRCODEGEN_DIR / "qrcodegen.c", platform_cflags))
    # internet play's signatures, for public games' listings
    # (port/third_party/monocypher; p2p_crypto.c)
    for name in ("monocypher.c", "monocypher-ed25519.c"):
        objects.append(guest_object(MONOCYPHER_DIR / name, platform_cflags))
    # the port's zlib (not the CPU's CRC32 instructions, which the guest's
    # assembly step is not told it may use)
    for name in ZLIB_SOURCES:
        objects.append(guest_object(ZLIB_DIR / name, " ".join([platform_cflags, *ZLIB_DEFINES,
                                                               "-U__ARM_FEATURE_CRC32"])))
    # the game's sin, pow and the rest, the same on every port
    musl_math_cflags = " ".join([
        guest_abi, "-std=gnu11", "-w", profile_flags, *libc_includes, f"-I{MUSL_MATH_DIR}/include",
        f"-include {MUSL_MATH_DIR}/include/libm.h",
    ])
    for source in sorted((MUSL_MATH_DIR / "src").glob("*.c")):
        objects.append(guest_object(source, musl_math_cflags))

    runtime_dir = ANDROID_DIR / "guest" / "runtime"
    runtime_internal_cflags = " ".join([
        guest_abi, "-std=c99", "-ffreestanding", "-fno-common", "-D_XOPEN_SOURCE=700", "-D_GNU_SOURCE",
        f"-I{runtime_dir}", f"-I{ANDROID_DIR}/include",
        f"-I{arch}", f"-I{MUSL_DIR}/arch/generic", f"-I{libc_internal}",
        f"-I{ANDROID_DIR}/guest/libc/src_include", f"-I{MUSL_DIR}/src/include",
        f"-I{MUSL_DIR}/src/internal", f"-I{libc_include}", f"-I{MUSL_DIR}/include",
    ])
    runtime_cflags = " ".join([
        guest_abi, guest_code, "-std=gnu11", "-D_GNU_SOURCE",
        f"-I{runtime_dir}", f"-I{ANDROID_DIR}/include", f"-I{LINUX_DIR}/src",
        f"-I{SDL_DIR}/include", f"-I{gl_include}", *libc_includes,
    ])
    for source in sorted(runtime_dir.glob("*.c")):
        if source.name in ("guest_thread.c", "guest_start.c"):
            objects.append(guest_object(source, runtime_internal_cflags))
        elif source.name == "guest_memory_watch.c":
            objects.append(guest_object(source, platform_cflags))
        else:
            objects.append(guest_object(source, runtime_cflags))
    objects.append(guest_object(guest_gl_c, runtime_cflags))
    objects.append(guest_object(guest_posix_c, runtime_cflags))
    imports_o = obj_dir / "gen" / "imports.o"
    n.build(outputs=imports_o, rule="switch_guest_asm", inputs=imports_s)
    objects.append(imports_o)

    linker_script = ANDROID_DIR / "guest" / "guest.ld"
    n.rule(
        name="switch_guest_link",
        command=(f"$switch_ndk_bin/ld.lld -m aarch64linux -static -nostdlib -T {linker_script} "
                 f"--section-start=.guest_header={GUEST_IMAGE_BASE:#x} "
                 f"-Map $out.map -o $out @$out.rsp {libguestc} "
                 "$$($switch_ndk_cc -print-libgcc-file-name)"),
        description="SWITCH LINK $out",
        rspfile="$out.rsp",
        rspfile_content="$in_newline",
    )
    # The deko3d renderer (port/switch/DEKO3D.md): its device,
    # port/switch/guest/d3d8_dk.c, in the place of d3d8_gl.c; the texture
    # cache, which decodes as xbox_textures.c does and sends the texels to
    # the host; its GLSL generators (the OpenGL renderer's nv2a_vsh.c and
    # nv2a_psh.c stay in the image, and the copies' names do not collide with
    # them); and the shader cache's guest half
    # and the overlay's drawing (the game list's screens: ui_overlay_dk.c,
    # the game's ui_overlay.c with its OpenGL part replaced)
    for name in ("d3d8_dk.c", "xbox_textures_dk.c", "nv2a_vsh_dk.c", "nv2a_psh_dk.c", "dk_shaders.c",
                 "ui_overlay_dk.c"):
        objects.append(guest_object(PORT_DIR / "guest" / name, platform_cflags))
    n.build(outputs=image, rule="switch_guest_link", inputs=objects, implicit=[libguestc, linker_script])

    # ---------- the host, built with devkitA64

    n.newline()
    n.rule(
        name="switch_host_cc",
        command="$switch_host_cc -MMD -MF $out.d $cflags -c $in -o $out",
        description="SWITCH HOST CC $out",
        depfile="$out.d",
        deps="gcc",
    )
    # The architecture flags, and -fPIE with them, are needed at link time
    # as well as compile time. Without them ld fails with "read-only
    # segment has dynamic relocations", which libnx alone reproduces with a
    # four-line program; switch.specs does not add them.
    host_arch = "-march=armv8-a -mtune=cortex-a57 -mtp=soft -fPIE"
    uam_library = _uam_build(n, BUILD, UAM_DIR, UAM_PATCH, devkitpro, host_cc, host_arch)
    host_cflags = " ".join([
        "-O2", "-g", "-Wall", "-Wno-unused-function", "-D_GNU_SOURCE", "-D__SWITCH__", "-DHALO_SWITCH_CONSOLE",
        # Frame pointers, which -O2 omits. host_debug.c walks the x29 chain to
        # print the host's own stack when it gives up, and there is no signal
        # handler to do it for us: the console has no syscall for installing
        # one, so the trace has to be taken by the code that is failing.
        "-fno-omit-frame-pointer",
        host_arch,
        # port/switch/include's shims (the Linux and Android headers the
        # Android-derived host includes) before libnx's and newlib's
        f"-I{ANDROID_DIR}/include", f"-I{PORT_DIR}/host", f"-I{PORT_DIR}/include", f"-I{SDL_DIR}/include",
        f"-I{LINUX_DIR}/src", f"-I{TOML_DIR}", f"-I{libc_include}",
        # the menus' font rasterizer, the game's stb_truetype (host_ui.c)
        f"-I{STB_DIR}", switch_includes,
    ])
    # port/switch/host, with UAM's compiler (DEKO3D.md, phase 5, step 2), or
    # the stub in its place (host_dk_compiler_stub.c) when this build has no
    # UAM: without one the deko3d renderer has only the shaders already on the
    # card
    host_sources = sorted((PORT_DIR / "host").glob("*.c"))
    if uam_library is None:
        n.comment("Switch build: the deko3d renderer will have no shaders it has not already got "
                  "(no UAM: it needs meson, bison, flex and mako)")
    else:
        host_sources = [source for source in host_sources if source.name != "host_dk_compiler_stub.c"]
    host_sources += [
        LINUX_DIR / "src" / "posix_files.c",
        TOML_DIR / "tomlc17.c",
    ]
    # the port's zlib (inflate only, its names z_), for the high-res HUD's
    # PNGs, which the host decodes as a map loads (host_dk_hud.c)
    zlib_sources = [ZLIB_DIR / name for name in ZLIB_SOURCES]
    host_sources += zlib_sources
    # internet play's UPnP: posix_upnp.c with the port's miniupnpc, as the
    # desktop's (the library's own warnings are not ours)
    upnp_sources = [LINUX_DIR / "src" / "posix_upnp.c", *sorted((MINIUPNPC_DIR / "src").glob("*.c"))]
    host_sources += upnp_sources
    upnp_cflags = " ".join([host_cflags, f"-I{MINIUPNPC_DIR / 'include'}", f"-I{MINIUPNPC_DIR / 'src'}",
                            *MINIUPNPC_DEFINES,
                            # (libnx has not these two: host_net.c's, which
                            # answer as the IPv4 network has no scopes)
                            "-Dif_nametoindex=switch_upnp_if_nametoindex",
                            "-Dif_indextoname=switch_upnp_if_indextoname",
                            f"-include {PORT_DIR / 'host' / 'host_upnp_names.h'}"])
    # the game list's requests: the game's own posix_browser.c with its
    # Mbed TLS, in the host as the Android app has them (tools/android_build.py).
    # The console's C library claims no Unix, so the library is told it is
    # one (its sockets, files and time are libnx's POSIX ones); its entropy
    # is the console's random service (host_tls.c's mbedtls_hardware_poll),
    # and its millisecond clock the console's monotonic one (mbedtls_ms_time,
    # the same file), which the library's own platform sources know nothing of
    browser_sources = [LINUX_DIR / "src" / "posix_browser.c", *sorted((MBEDTLS_DIR / "library").glob("*.c"))]
    host_sources += browser_sources
    # (the bundled Mbed TLS's headers before the host's include paths: the
    # devkitPro image's portlibs carry an older Mbed TLS of their own, which
    # has no mbedtls_ms_time_t, and -I directories are searched in order)
    browser_cflags = " ".join([f"-I{MBEDTLS_DIR / 'include'}", f"-I{MBEDTLS_DIR / 'library'}", host_cflags,
                               *game_browser_defines(sln), "-D__unix__=1", "-DMBEDTLS_NO_PLATFORM_ENTROPY",
                               "-DMBEDTLS_ENTROPY_HARDWARE_ALT", "-DMBEDTLS_PLATFORM_MS_TIME_ALT"])
    host_objects: List[Path] = []
    for source in host_sources:
        obj = host_obj_dir / (source.name + ".o")
        cflags = host_cflags
        # the self-updater knows its build number and flavour, and only it, so
        # a new number rebuilds one file (host_update.c)
        if source.name == "host_update.c":
            cflags = f"{host_cflags} {switch_updater_defines(getattr(sln, 'port_release', False))}"
        # the shader cache names its folder for the compiler whose DKSH files
        # it keeps, so a new UAM does not read an old compiler's
        if source.name == "host_dk_shaders.c":
            cflags = f'{host_cflags} -DHOST_DK_UAM_COMMIT=\\"{UAM_COMMIT[:12]}\\"'
        if source in zlib_sources:
            cflags = " ".join([host_cflags, f"-I{ZLIB_DIR}", *ZLIB_DEFINES])
        if source in upnp_sources:
            cflags = upnp_cflags + (" -w" if source.name != "posix_upnp.c" else "")
        if source.name == "host_dk_hud.c":
            cflags = f"{host_cflags} -I{ZLIB_DIR}"
        if source in browser_sources:
            cflags = browser_cflags + (" -w" if source.name != "posix_browser.c" else "")
        # (the player key's file is checked to be the user's own and private,
        # which a FAT card's files never are: the file is taken as the
        # Android app takes its own storage's, whose check that define skips)
        if source.name == "posix_browser.c":
            cflags += " -D__ANDROID__=1"
        if source.name == "host_tls.c":
            # (the bundled headers first, as above)
            cflags = " ".join([f"-I{MBEDTLS_DIR / 'include'}", host_cflags, "-DMBEDTLS_ENTROPY_HARDWARE_ALT",
                               "-DMBEDTLS_PLATFORM_MS_TIME_ALT"])
        n.build(outputs=obj, rule="switch_host_cc", inputs=source, variables={"cflags": cflags},
                implicit=[syscall_h])
        host_objects.append(obj)
    # UAM's compiler, linked into the host as the probe links it (DEKO3D.md,
    # phase 5, step 2; the probe's Makefile is the control for this). One C++
    # file, host_dk_compiler.cpp, is compiled with UAM's own include paths
    # and defines (as UAM's meson build gives them) and linked with UAM's
    # library into a single relocatable object, every symbol they define is
    # renamed (which renames the C++ COMDAT groups too, whose names are what
    # really clash with Mesa's) and all but host_dk_compile_glsl are made
    # local. That is what lets UAM sit beside the Mesa that SDL2 links in:
    # both are Mesa's GLSL compiler, and linked plainly they collide. The
    # object is built without -fPIC, as UAM's library is (step 1: under it,
    # a thread-local variable faulted with devkitA64's -mtp=soft), which is
    # also what the host's own -fPIE asks for.
    if uam_library is not None:
        uam_meson = BUILD / "uam" / "meson"
        uam_cflags = " ".join([
            "-std=c++11", "-DNDEBUG", "-DDESKTOP", "-D_USE_MATH_DEFINES", "-D_GNU_SOURCE", "-DHAVE_POSIX_MEMALIGN",
            "-D__SWITCH__", host_arch, f"-isystem {devkitpro / 'libnx' / 'include'}",
            f"-I{UAM_DIR / 'source'}", f"-I{UAM_DIR / 'mesa-imported'}",
            f"-I{uam_meson / 'mesa-imported'}",
            f"-I{uam_meson / 'mesa-imported' / 'glsl'}",
            f"-I{uam_meson / 'mesa-imported' / 'glsl' / 'glcpp'}",
        ])
        compiler_obj = host_obj_dir / "host_dk_compiler.cpp.o"
        n.rule(
            name="switch_host_cxx",
            command=f"$switch_host_gxx -MMD -MF $out.d {uam_cflags} -c $in -o $out",
            description="SWITCH HOST CXX $out",
            depfile="$out.d",
            deps="gcc",
        )
        n.build(outputs=compiler_obj, rule="switch_host_cxx", inputs=PORT_DIR / "host" / "host_dk_compiler.cpp",
                implicit=[uam_library])
        combined = host_obj_dir / "uam_combined.o"
        symbols = host_obj_dir / "uam_symbols.txt"
        host_uam_object = host_obj_dir / "uam_compiler.o"
        nm_bin = host_cc.parent / "aarch64-none-elf-nm"
        objcopy_bin = host_cc.parent / "aarch64-none-elf-objcopy"
        ld_bin = host_cc.parent / "aarch64-none-elf-ld"
        # UAM's allocations go to the host's allocator for it
        # (port/switch/host/host_uam_alloc.c), each thread's own: newlib's
        # malloc has one lock for the process, and two compile threads on it
        # were slower than one (DEKO3D.md, phase 5, step 4). Every call of
        # the C library's and C++'s, renamed with the rest.
        uam_allocations = [("malloc", "host_uam_malloc"), ("calloc", "host_uam_calloc"),
                           ("realloc", "host_uam_realloc"), ("free", "host_uam_free"),
                           ("strdup", "host_uam_strdup"), ("strndup", "host_uam_strndup"),
                           ("_Znwm", "host_uam_new"), ("_Znam", "host_uam_new_array"),
                           ("_ZdlPv", "host_uam_delete"), ("_ZdaPv", "host_uam_delete_array")]
        allocation_lines = " ".join(f"'{old} {new}'" for old, new in uam_allocations)
        allocation_globals = " ".join(f"--keep-global-symbol={new}" for _, new in uam_allocations)
        n.rule(
            name="switch_uam_combine",
            command=(
                f"{ld_bin} -r -o {combined} {compiler_obj} --whole-archive {uam_library} --no-whole-archive && "
                f"{nm_bin} --defined-only {combined} | awk '{{print $$3}}' | "
                f"grep -v -e '^host_dk_compile_glsl$$' -e '^\\$$' | sort -u | "
                f"awk '{{print $$1\" uam_\"$$1}}' > {symbols} && "
                f"printf '%s\\n' {allocation_lines} >> {symbols} && "
                f"{objcopy_bin} --redefine-syms={symbols} --keep-global-symbol=host_dk_compile_glsl "
                f"{allocation_globals} {combined} $out"
            ),
            description="SWITCH UAM COMBINE $out",
        )
        n.build(outputs=host_uam_object, rule="switch_uam_combine", inputs=[compiler_obj], implicit=[uam_library])
        host_objects.append(host_uam_object)
    # the disc image reader, so a retail .iso on the card can be unpacked into
    # the maps folder by the port itself rather than copied there by hand. It is
    # the same source the desktop port and the guest use, built here without
    # the game's platform layer (see the guard in xiso.c).
    extractor = host_obj_dir / "xiso.c.o"
    n.build(outputs=extractor, rule="switch_host_cc", inputs=LINUX_DIR / "src" / "xiso.c",
            variables={"cflags": f"{host_cflags} -DHALO_EXTRACTOR_STANDALONE"}, implicit=[syscall_h])
    host_objects.append(extractor)

    # the stack switch into the guest, which has to be assembly (it moves the
    # stack pointer), and the menus' fonts and panel, which host_ui_assets.S
    # includes as they are: the game's fonts by their path in the game (-I),
    # the port's panel by its path here
    n.rule(
        name="switch_host_as",
        command=f"$switch_host_cc -c {host_arch} -I{_quote(game)} -o $out $in",
        description="SWITCH HOST AS $out",
    )
    ui_assets = [game / "port" / "assets" / "fonts" / "OpenCE-Regular.ttf",
                 game / "port" / "assets" / "fonts" / "Overpass-750.ttf", PORT_DIR / "art" / "menu_panel.svg"]
    for source in sorted((PORT_DIR / "host").glob("*.S")):
        obj = host_obj_dir / (source.name + ".o")
        n.build(outputs=obj, rule="switch_host_as", inputs=source,
                implicit=ui_assets if source.name == "host_ui_assets.S" else None)
        host_objects.append(obj)

    table_obj = host_obj_dir / "host_import_table.c.o"
    n.build(outputs=table_obj, rule="switch_host_cc", inputs=host_table_c, variables={"cflags": host_cflags})
    host_objects.append(table_obj)

    # The host is linked to an ELF and then packaged into an NRO.
    #
    # Both steps are needed and the second is easy to forget: an NRO is not
    # an ELF. It is a 32-byte header, a 16 KB NACP holding the title and
    # author, an asset section, and then the ELF. Write the ELF out with the
    # .nro name and the result is not an NRO at all - the Homebrew Menu
    # reports it as not supporting the current ABI. port/switch/probe/hello2
    # is the control: it is the same program packaged the same way, and it
    # runs.
    elf = BUILD / "halo.elf"
    nacp = BUILD / "halo.nacp"
    n.rule(
        name="switch_host_link",
        command=(f"$switch_host_gxx -specs=$switch_specs -g {host_arch} -o $out $in "
                 + " ".join(f"-L{path}" for path in (portlibs / "lib", devkitpro / "libnx" / "lib")) + " "
                 + " ".join(f"-l{lib}" for lib in HOST_LIBRARIES)
                 + " -Wl,-Map,$out.map"),
        description="SWITCH HOST LINK $out",
    )
    n.build(outputs=elf, rule="switch_host_link", inputs=host_objects)

    # devkitPro's own tools, which live beside the compiler
    n.rule(
        name="switch_nacp",
        command=f"{devkitpro / 'tools' / 'bin' / 'nacptool'} "
                f"--create '{NACP_TITLE}' '{NACP_AUTHOR}' {NACP_VERSION} $out",
        description="SWITCH NACP $out",
    )
    n.build(outputs=nacp, rule="switch_nacp")

    # The icon does not go in the NACP: it is an asset, embedded by elf2nro.
    # A 256x256 JPEG (port/switch/art/icon.jpg). Absolute, as the other paths
    # are: elf2nro reports "Failed to open input!" for a relative one.
    nro_icon = (Path.cwd() / PORT_DIR / "art" / "icon.jpg").resolve()
    n.rule(
        name="switch_nro",
        # elf2nro is given absolute paths: with relative ones it reports
        # success and writes nothing, which ninja does not notice.
        #
        # --icon goes after the two paths, not before them. Given first it
        # answers "Failed to open input!" and builds nothing.
        command=(f"{devkitpro / 'tools' / 'bin' / 'elf2nro'} "
                 f"{(Path.cwd() / str(elf)).resolve()} {(Path.cwd() / str(nro)).resolve()}"
                 f" --icon={nro_icon} --nacp={(Path.cwd() / str(nacp)).resolve()}"),
        description="SWITCH NRO $out",
    )
    n.build(outputs=nro, rule="switch_nro", inputs=[elf, nacp, nro_icon])

    # The Switch's own menu files (tools/switch_menus.py), for the card's
    # menus folder beside the program: the packager and the deploy tool
    # carry them, and the game takes them over its built-in ones.
    menus_dir = Path(nro).parent / "menus"
    menus_stamp = menus_dir / ".written"
    n.rule(
        name="switch_menus",
        command=f"{python} {_quote(TOOLS_DIR / 'switch_menus.py')} --out {_quote(menus_dir)} --stamp $out",
        description="SWITCH MENUS $out",
    )
    n.build(outputs=menus_stamp, rule="switch_menus",
            implicit=[TOOLS_DIR / "switch_menus.py", GAME_TOOLS / "port_settings.py",
                      game / "port" / "assets" / "menus" / "chupathingy" / "main_menu.xml",
                      game / "port" / "assets" / "menus" / "menus.json"])

    n.build(outputs="switch", rule="phony", inputs=[nro, image, menus_stamp])
    n.newline()
