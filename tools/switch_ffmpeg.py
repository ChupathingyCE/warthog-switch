"""FFmpeg for the Switch's guest: the game's Android guest FFmpeg with clips.

The Switch's guest is the game's Android guest (port/switch/README.md), so
its FFmpeg is the one the game's tools/android_ffmpeg.py builds for that ABI:
the movies' Bink demuxer and decoders, swscale and swresample. The Switch
records clips as well (capture_clips.c, HALO_CAPTURE through
HALO_CONSOLE_CAPTURE), which take FFmpeg's encoders the Android build leaves
out: MPEG-4 Part 2 for the picture, AAC for the sound, and the MP4 muxer that
writes the file. This runs the game's tool with those added to its configure,
and nothing else changed.

The game's tool finds the guest's musl and headers where the Android build
puts them (build/android/...); the Switch's are in build/switch, so it is
handed a tree of links to them (<build directory>/tree).

Usage: switch_ffmpeg.py <build directory> --game <the game's folder> --switch-build <build/switch> [--ndk <ndk>]
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# what clips need beyond the movies (capture_clips.c: avcodec_find_encoder_by_name
# "mpeg4" and "aac", avformat_alloc_output_context2's "mp4")
CLIP_OPTIONS = ["--enable-encoder=mpeg4,aac", "--enable-muxer=mp4"]


def take_option(name):
    """an option's value, taken out of the command line"""
    if name not in sys.argv:
        raise SystemExit(__doc__)
    at = sys.argv.index(name)
    value = sys.argv[at + 1]
    del sys.argv[at:at + 2]
    return Path(value).resolve()


def link(path, target):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.exists():
        if path.is_symlink() and Path(path.readlink()) == target:
            return
        path.unlink()
    path.symlink_to(target)


def main():
    game = take_option("--game")
    switch_build = take_option("--switch-build")
    arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
    if not arguments:
        raise SystemExit(__doc__)
    root = Path(arguments[0]).resolve()
    sys.path.insert(0, str(game / "tools"))
    import android_ffmpeg  # noqa: E402

    # (the game's tool starts over when its own configure changes, by its
    # stamp; a change to these options has to as well)
    stamp = root / "switch-options.stamp"
    options = "\n".join(CLIP_OPTIONS)
    if stamp.is_file() and stamp.read_text() != options and (root / "build").is_dir():
        shutil.rmtree(root / "build")
    root.mkdir(parents=True, exist_ok=True)

    # (the Android build's places, as the game's tool looks for them, linked
    # to the Switch's)
    tree = root / "tree"
    link(tree / "build" / "android" / "third_party", switch_build / "third_party")
    link(tree / "build" / "android" / "guest" / "libc_include", switch_build / "guest" / "libc_include")
    link(tree / "port", game / "port")
    link(tree / "tools", game / "tools")
    # (not every NDK's clang has -fno-define-target-os-macros, 26's 17.0.2
    # among them: dropped as port/switch/build.py drops it, __APPLE__ and
    # __MACH__ being undefined by the flags anyway)
    if "--ndk" in sys.argv:
        clang = (Path(sys.argv[sys.argv.index("--ndk") + 1]) / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64" /
                 "bin" / "clang")
        probe = subprocess.run([str(clang), "--target=arm64_32-apple-watchos", "-fno-define-target-os-macros",
                                "-E", "-x", "c", os.devnull, "-o", os.devnull], capture_output=True)
        if probe.returncode != 0:
            android_ffmpeg.GUEST_FLAGS = android_ffmpeg.GUEST_FLAGS.replace("-fno-define-target-os-macros ", "")
    write_guest_compiler = android_ffmpeg.write_guest_compiler
    android_ffmpeg.write_guest_compiler = lambda root, _tree, ndk: write_guest_compiler(root, tree, ndk)

    run = android_ffmpeg.run

    def run_with_clips(command, *args, **kwargs):
        if command and Path(str(command[0])).name == "configure":
            command = [*command, *CLIP_OPTIONS]
        return run(command, *args, **kwargs)

    android_ffmpeg.run = run_with_clips
    android_ffmpeg.main()
    stamp.write_text(options)


if __name__ == "__main__":
    main()
