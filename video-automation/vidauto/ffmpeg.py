"""ffmpeg discovery and invocation.

We deliberately avoid depending on ffprobe: every duration in this pipeline is
something we chose, so there is nothing to probe. That keeps the pip-installed
static ffmpeg (which ships no ffprobe) a fully supported option.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def ffmpeg_bin() -> str:
    """Locate an ffmpeg binary.

    Order: explicit FFMPEG_BIN, then PATH, then the static build bundled with
    imageio-ffmpeg. The last one is what makes `pip install -r requirements.txt`
    sufficient on a machine with no system ffmpeg.
    """
    explicit = os.environ.get("FFMPEG_BIN")
    if explicit:
        if not Path(explicit).exists():
            raise FFmpegError(f"FFMPEG_BIN is set to {explicit!r} but that file does not exist")
        return explicit

    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path

    try:
        import imageio_ffmpeg
    except ImportError as exc:  # pragma: no cover - depends on install state
        raise FFmpegError(
            "No ffmpeg found. Install it system-wide (apt install ffmpeg / brew install ffmpeg), "
            "or run `pip install imageio-ffmpeg` for a bundled static build, "
            "or point FFMPEG_BIN at a binary."
        ) from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(args: list[str], *, description: str) -> None:
    """Run ffmpeg with the given arguments, raising with useful context on failure."""
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        detail = "\n".join(tail[-15:]) if tail else "(no stderr)"
        raise FFmpegError(f"ffmpeg failed while {description}:\n{detail}")


def escape_drawtext(text: str) -> str:
    r"""Escape a string for use as an ffmpeg drawtext `text=` value.

    drawtext parsing is layered: the filtergraph parser eats one level, and
    drawtext's own expansion eats another. Backslash first (so we do not
    re-escape our own escapes), then the characters that terminate a filter
    option or trigger expansion.
    """
    out = text.replace("\\", "\\\\")
    for ch in (":", "'", "%", ",", "[", "]", ";", "="):
        out = out.replace(ch, "\\" + ch)
    return out
