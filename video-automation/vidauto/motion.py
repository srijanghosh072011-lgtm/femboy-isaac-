"""Turn a still image into a moving 9:16 segment.

This is the module that replaces the video model. A slow, physically plausible
camera move over a photograph reads as footage to a scrolling viewer, provided
two things hold:

  * the move is slow and linear -- eased or fast moves read as a slideshow
    transition, which breaks the "this is a photograph of a real place" spell;
  * the source is upscaled hard before zoompan runs. zoompan quantises its
    crop window to integer pixels, so on a slow zoom over a 1:1 source the
    window snaps a pixel at a time and the result visibly judders. Scaling to
    3x target height first makes each snap a third of an output pixel.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg
from .config import FPS, HEIGHT, WIDTH

# Work at 3x output height before zoompan; see module docstring.
SUPERSAMPLE = 3
WORK_H = HEIGHT * SUPERSAMPLE
WORK_W = WIDTH * SUPERSAMPLE

# How far a push-in travels over one segment. 12% over ~4.5s is slow enough to
# feel like a locked-off camera drifting, not a zoom.
ZOOM_TRAVEL = 0.12
# Constant zoom used by pan moves, which need headroom to pan *into*.
PAN_ZOOM = 1.10


@dataclass(frozen=True)
class Move:
    name: str
    # Crop anchor within the (wider than 9:16) source, 0.0 = left, 1.0 = right.
    anchor: float = 0.5


MOVES = (
    Move("push_in"),
    Move("pull_out"),
    Move("pan_right", anchor=0.35),
    Move("pan_left", anchor=0.65),
    Move("drift_down"),
    Move("drift_up"),
)


def move_for_index(index: int) -> Move:
    """Pick a move for segment `index`, alternating so no two neighbours match."""
    return MOVES[index % len(MOVES)]


def _expressions(move: str, frames: int) -> tuple[str, str, str]:
    """Return (z, x, y) zoompan expressions for a move.

    `on` is the output frame index. Progress is on/(frames-1), clamped by the
    expression bounds so the final frame lands exactly on the endpoint.
    """
    last = max(frames - 1, 1)
    centred_x = "iw/2-(iw/zoom/2)"
    centred_y = "ih/2-(ih/zoom/2)"

    if move == "push_in":
        z = f"min(1.0+{ZOOM_TRAVEL}*on/{last},{1.0 + ZOOM_TRAVEL})"
        return z, centred_x, centred_y
    if move == "pull_out":
        z = f"max({1.0 + ZOOM_TRAVEL}-{ZOOM_TRAVEL}*on/{last},1.0)"
        return z, centred_x, centred_y

    z = str(PAN_ZOOM)
    span_x = "(iw-iw/zoom)"
    span_y = "(ih-ih/zoom)"
    if move == "pan_right":
        return z, f"{span_x}*on/{last}", centred_y
    if move == "pan_left":
        return z, f"{span_x}*(1-on/{last})", centred_y
    if move == "drift_down":
        return z, centred_x, f"{span_y}*on/{last}"
    if move == "drift_up":
        return z, centred_x, f"{span_y}*(1-on/{last})"
    raise ValueError(f"Unknown move {move!r}")


def render_segment(image: Path, dest: Path, seconds: float, move: Move) -> None:
    """Render one still into a moving segment at `dest`."""
    if not image.exists():
        raise FileNotFoundError(f"Source image missing: {image}")
    frames = max(int(round(seconds * FPS)), 2)
    z, x, y = _expressions(move.name, frames)

    # Scale to working height, then crop a 9:16 window. The source is 2:3, so
    # after scaling to height there is surplus width; `anchor` chooses where in
    # that surplus the window sits, which varies composition between segments.
    crop_x = f"(iw-{WORK_W})*{move.anchor:.3f}"
    chain = (
        f"scale=-2:{WORK_H}:flags=lanczos,"
        f"crop={WORK_W}:{WORK_H}:{crop_x}:0,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"format=yuv420p"
    )
    ffmpeg.run(
        [
            "-i", str(image),
            "-vf", chain,
            "-frames:v", str(frames),
            "-r", str(FPS),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            str(dest),
        ],
        description=f"rendering {move.name} segment from {image.name}",
    )
