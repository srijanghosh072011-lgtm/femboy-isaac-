"""Assembly: concat segments, shape the loop, burn captions, final encode."""

from __future__ import annotations

from pathlib import Path

from . import captions as captions_mod
from . import ffmpeg
from .config import FPS, HEIGHT, WIDTH

# Length of the tail-to-head crossfade used for loop shaping.
LOOP_FADE = 0.75

# Delivery bitrate ceiling for 1080x1920@30. Comfortably above what this
# footage needs and comfortably below every platform's upload limit.
MAX_BITRATE_KBPS = 12000


def concat(segments: list[Path], dest: Path) -> None:
    """Concatenate identically-encoded segments without re-encoding."""
    if not segments:
        raise ValueError("No segments to concatenate")
    listing = dest.parent / "segments.txt"
    # The concat demuxer resolves paths relative to the list file, and treats
    # single quotes specially; absolute paths with quotes escaped avoids both.
    lines = [f"file '{str(p.resolve()).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'" for p in segments]
    listing.write_text("\n".join(lines) + "\n")
    ffmpeg.run(
        ["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(dest)],
        description="concatenating segments",
    )


def shape_loop(source: Path, dest: Path, duration: float) -> float:
    """Crossfade the tail into the opening so autoplay repeats seamlessly.

    Returns the new duration. The clip loses LOOP_FADE seconds: the tail is
    blended with a copy of the head rather than appended to it.
    """
    fade = min(LOOP_FADE, duration / 4)
    offset = duration - 2 * fade
    if offset <= 0:
        # Too short to shape; hand back the source unchanged.
        dest.write_bytes(source.read_bytes())
        return duration

    # xfade refuses a variable frame rate, and `trim` leaves the rate
    # undeclared (ffmpeg reports 1/0), so both branches are re-stamped with an
    # explicit fps before they meet.
    graph = (
        f"[0:v]split=2[a][b];"
        f"[a]trim=0:{duration - fade:.3f},setpts=PTS-STARTPTS,fps={FPS}[main];"
        f"[b]trim=0:{fade:.3f},setpts=PTS-STARTPTS,fps={FPS}[head];"
        f"[main][head]xfade=transition=fade:duration={fade:.3f}:offset={offset:.3f}[v]"
    )
    ffmpeg.run(
        [
            "-i", str(source),
            "-filter_complex", graph,
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            str(dest),
        ],
        description="shaping the loop",
    )
    return duration - fade


def finish(
    source: Path,
    dest: Path,
    hook: str,
    closing: str,
    duration: float,
    burn_captions: bool = True,
    work_dir: Path | None = None,
) -> None:
    """Composite captions and produce the delivery encode.

    A silent AAC track is muxed in deliberately: several platforms treat a
    video with no audio stream at all as malformed on upload, and this niche
    ships without narration.
    """
    work_dir = work_dir or dest.parent
    captions = captions_mod.standard_captions(hook, closing, duration) if burn_captions else []

    inputs = ["-i", str(source)]
    for i, caption in enumerate(captions):
        png = work_dir / f"caption_{i}.png"
        captions_mod.render_caption_png(caption, png)
        inputs += ["-i", str(png)]
    # Silent audio goes last so caption inputs keep contiguous indices 1..N.
    audio_index = len(captions) + 1
    inputs += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]

    steps: list[str] = []
    current = "0:v"
    for i, caption in enumerate(captions):
        label = f"v{i}"
        steps.append(
            f"[{current}][{i + 1}:v]overlay=0:0:"
            f"enable='between(t,{caption.start:.3f},{caption.end:.3f})'[{label}]"
        )
        current = label
    # Always terminate with an explicit scale+format so the delivery encode is
    # exactly 1080x1920 yuv420p regardless of what came in.
    steps.append(f"[{current}]scale={WIDTH}:{HEIGHT},format=yuv420p[vout]")
    graph = ";".join(steps)

    ffmpeg.run(
        [
            *inputs,
            "-filter_complex", graph,
            "-map", "[vout]", "-map", f"{audio_index}:a:0",
            "-c:v", "libx264", "-preset", "slow", "-crf", "19",
            "-profile:v", "high", "-level", "4.0",
            # Cap the delivery bitrate. CRF alone is unbounded, and a
            # high-detail frame can spike a short clip past the upload limits
            # the platforms enforce; every one of them re-encodes anyway, so
            # spending bits above this buys nothing.
            "-maxrate", f"{MAX_BITRATE_KBPS}k",
            "-bufsize", f"{MAX_BITRATE_KBPS * 2}k",
            "-r", str(FPS),
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            str(dest),
        ],
        description="producing the final encode",
    )
