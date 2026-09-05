"""The number / name / stat card burned over each clip.

Rendered with Pillow for the same reasons captions are (see captions.py): no
libfreetype dependency, and real font metrics.

Layout is deliberately bottom-weighted. The top third of a vertical clip is
usually where the subject is, and the bottom is where the platform's own UI
already lives, so the card sits just above that -- readable without covering
the thing the viewer came to see.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..config import HEIGHT, WIDTH, find_font

NUMBER_SIZE = 150
NAME_SIZE = 76
STAT_SIZE = 44

MARGIN_X = 56
BLOCK_BOTTOM = int(HEIGHT * 0.78)
SCRIM_HEIGHT = int(HEIGHT * 0.42)


def _fit(text: str, font_path: str, size: int, max_width: int) -> ImageFont.FreeTypeFont:
    """Shrink the font until the text fits on one line, within reason."""
    while size > 20:
        font = ImageFont.truetype(font_path, size)
        bbox = font.getbbox(text)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 4
    return ImageFont.truetype(font_path, size)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines, current = [], words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if font.getbbox(candidate)[2] - font.getbbox(candidate)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def render_item_card(rank: int, name: str, stat: str, dest: Path) -> None:
    """Render the overlay for one ranking entry as a full-frame RGBA PNG."""
    font_path = find_font()
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # A gradient scrim rather than a solid plate: text stays readable over a
    # bright clip without boxing off half the frame.
    for i in range(SCRIM_HEIGHT):
        alpha = int(200 * (i / SCRIM_HEIGHT) ** 1.6)
        y = HEIGHT - SCRIM_HEIGHT + i
        draw.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha))

    max_width = WIDTH - 2 * MARGIN_X

    stat_font = ImageFont.truetype(font_path, STAT_SIZE)
    stat_lines = _wrap(stat, stat_font, max_width)
    name_font = _fit(name, font_path, NAME_SIZE, max_width)
    number_font = ImageFont.truetype(font_path, NUMBER_SIZE)

    stat_h = (stat_font.getbbox("Ay")[3] - stat_font.getbbox("Ay")[1]) + 12
    name_h = name_font.getbbox("Ay")[3] - name_font.getbbox("Ay")[1]

    # Lay the block out from the bottom up.
    y = BLOCK_BOTTOM
    for line in reversed(stat_lines):
        y -= stat_h
        draw.text((MARGIN_X, y), line, font=stat_font, fill=(235, 235, 235, 255))

    y -= name_h + 26
    bbox = name_font.getbbox(name)
    draw.text((MARGIN_X - bbox[0], y - bbox[1]), name, font=name_font, fill=(255, 255, 255, 255))

    number_text = f"#{rank}"
    nbox = number_font.getbbox(number_text)
    y -= (nbox[3] - nbox[1]) + 30
    # The number is the navigational element -- it tells the viewer how far
    # through the countdown they are, so it gets the accent colour.
    draw.text((MARGIN_X - nbox[0], y - nbox[1]), number_text, font=number_font, fill=(255, 214, 10, 255))

    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest)


def render_title_card(title: str, subtitle: str, dest: Path) -> None:
    """Render the opening card."""
    font_path = find_font()
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=(0, 0, 0, 150))

    max_width = WIDTH - 2 * MARGIN_X
    title_font = ImageFont.truetype(font_path, 92)
    lines = _wrap(title, title_font, max_width)
    line_h = int((title_font.getbbox("Ay")[3] - title_font.getbbox("Ay")[1]) * 1.45)

    total = line_h * len(lines)
    y = HEIGHT // 2 - total // 2
    for line in lines:
        bbox = title_font.getbbox(line)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x - bbox[0], y - bbox[1]), line, font=title_font, fill=(255, 255, 255, 255))
        y += line_h

    if subtitle:
        sub_font = ImageFont.truetype(font_path, 48)
        bbox = sub_font.getbbox(subtitle)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x - bbox[0], y + 24 - bbox[1]), subtitle, font=sub_font, fill=(255, 214, 10, 255))

    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest)
