"""On-screen caption overlays.

Captions are rendered to transparent PNGs with Pillow and composited by
ffmpeg's `overlay` filter, rather than drawn by ffmpeg's `drawtext`.

That is a deliberate choice. drawtext requires an ffmpeg built against
libfreetype, which the portable static builds (including the one pip installs)
are not -- so a drawtext pipeline works on one machine and dies on the next.
Rendering here also buys real font metrics, so wrapping and centring are
measured rather than estimated from character counts, and it removes drawtext's
two-layer escaping rules from the codebase entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import HEIGHT, WIDTH, find_font

HOOK_FONT_SIZE = 68
CLOSING_FONT_SIZE = 58
# Text is wrapped to fit inside this fraction of the frame width, keeping it
# clear of the platform UI that overlays the right and bottom edges.
TEXT_WIDTH_FRACTION = 0.82
LINE_SPACING = 1.22
# Padding around the text inside its plate.
PLATE_PAD_X = 34
PLATE_PAD_Y = 22
PLATE_ALPHA = 130
PLATE_RADIUS = 18


@dataclass
class Caption:
    text: str
    start: float
    end: float
    font_size: int
    # Vertical anchor as a fraction of frame height, for the block's centre.
    y_fraction: float


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Greedy word wrap using measured text width."""
    words = text.split()
    if not words:
        return []

    def width_of(s: str) -> int:
        return int(font.getbbox(s)[2] - font.getbbox(s)[0])

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if width_of(candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def render_caption_png(caption: Caption, dest: Path) -> None:
    """Render one caption as a full-frame transparent PNG.

    Full-frame rather than a tight crop so the overlay filter can composite at
    0,0 with no positioning arithmetic -- the position is baked into the image.
    """
    font = ImageFont.truetype(find_font(), caption.font_size)
    max_text_width = int(WIDTH * TEXT_WIDTH_FRACTION) - 2 * PLATE_PAD_X
    lines = _wrap(caption.text, font, max_text_width)
    if not lines:
        raise ValueError("Cannot render an empty caption")

    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    ascent, descent = font.getmetrics()
    line_height = int((ascent + descent) * LINE_SPACING)
    block_height = line_height * len(lines)
    top = int(HEIGHT * caption.y_fraction - block_height / 2)

    # One plate behind the whole block, sized to the widest line. Per-line
    # plates leave ragged steps and slivers of background between the lines,
    # which reads as an accident rather than a design.
    widest = max(font.getbbox(line)[2] - font.getbbox(line)[0] for line in lines)
    plate_left = (WIDTH - widest) // 2 - PLATE_PAD_X
    plate_right = (WIDTH + widest) // 2 + PLATE_PAD_X
    draw.rounded_rectangle(
        [plate_left, top - PLATE_PAD_Y, plate_right, top + block_height + PLATE_PAD_Y],
        radius=PLATE_RADIUS,
        fill=(0, 0, 0, PLATE_ALPHA),
    )

    for i, line in enumerate(lines):
        bbox = font.getbbox(line)
        text_w = bbox[2] - bbox[0]
        x = (WIDTH - text_w) // 2
        y = top + i * line_height
        # Offset by the bbox origin so glyphs with negative bearing still sit
        # on the intended baseline rather than drifting left or up.
        draw.text((x - bbox[0], y), line, font=font, fill=(255, 255, 255, 255))

    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest)


def standard_captions(hook: str, closing: str, total_seconds: float) -> list[Caption]:
    """The two overlays the retention checklist calls for.

    The hook sits high in frame and lands immediately -- it has to be readable
    before the viewer decides to scroll. The closing sits centre-low and only
    appears once the visual has already done its work.
    """
    out: list[Caption] = []
    if hook.strip():
        out.append(
            Caption(
                text=hook.strip(),
                start=0.2,
                end=min(3.2, total_seconds),
                font_size=HOOK_FONT_SIZE,
                y_fraction=0.20,
            )
        )
    if closing.strip() and total_seconds > 4:
        out.append(
            Caption(
                text=closing.strip(),
                start=max(total_seconds - 3.5, 0.0),
                end=total_seconds,
                font_size=CLOSING_FONT_SIZE,
                y_fraction=0.74,
            )
        )
    return out
