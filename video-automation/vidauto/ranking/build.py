"""Assembling the ranking video.

Source clips arrive in whatever shape the library had them, mostly 16:9. Rather
than centre-cropping (which throws away the sides, and stock framing usually
puts the subject there) each clip is composited over a blurred, darkened copy
of itself scaled to fill. The subject stays whole and the frame stays 9:16.

No title card and no build-up: the countdown's first entry starts on frame one
with the hook as an overlay. A title card would spend the only two seconds that
decide whether the viewer stays.
"""

from __future__ import annotations

from pathlib import Path

from .. import assemble, ffmpeg
from ..captions import render_caption_png, Caption
from ..config import FPS, HEIGHT, WIDTH
from . import cards
from .models import RankItem, RankList

# How long the hook and the closing bait stay on screen.
HOOK_SECONDS = 2.6
CLOSING_SECONDS = 2.6


def _normalise_and_card(
    clip: Path,
    card: Path,
    dest: Path,
    seconds: float,
    extra_overlays: list[tuple[Path, float, float]],
) -> None:
    """Render one ranking entry: clip filled to 9:16, card burned on top."""
    inputs = [
        # Loop short clips rather than freezing on a last frame or cutting the
        # segment short -- stock clips are often under four seconds.
        "-stream_loop", "-1", "-i", str(clip),
        "-i", str(card),
    ]
    for path, _start, _end in extra_overlays:
        inputs += ["-i", str(path)]

    steps = [
        f"[0:v]fps={FPS},split=2[s1][s2]",
        # Background: fill the frame, blur hard, darken so the card reads.
        f"[s1]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},gblur=sigma=28,eq=brightness=-0.12[bg]",
        # Foreground: the whole clip, untouched, letterboxed into the middle.
        f"[s2]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease[fg]",
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base]",
        "[base][1:v]overlay=0:0[withcard]",
    ]

    current = "withcard"
    for i, (_path, start, end) in enumerate(extra_overlays):
        label = f"ov{i}"
        steps.append(
            f"[{current}][{i + 2}:v]overlay=0:0:enable='between(t,{start:.2f},{end:.2f})'[{label}]"
        )
        current = label
    steps.append(f"[{current}]format=yuv420p[vout]")

    ffmpeg.run(
        [
            *inputs,
            "-filter_complex", ";".join(steps),
            "-map", "[vout]",
            "-an",
            "-t", f"{seconds:.2f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            str(dest),
        ],
        description=f"rendering ranking entry from {clip.name}",
    )


def build(
    ranking: RankList,
    clips: dict[int, Path],
    run_dir: Path,
    seconds_per_item: float,
    final_item_bonus: float = 1.6,
) -> tuple[Path, float]:
    """Assemble the finished video. Returns (path, duration)."""
    resolved = [i for i in ranking.items if i.chosen and i.rank in clips]
    if not resolved:
        raise ValueError("No resolved items to build from")

    work = run_dir / "segments"
    work.mkdir(parents=True, exist_ok=True)

    segments: list[Path] = []
    total = 0.0
    for index, item in enumerate(resolved):
        is_last = index == len(resolved) - 1
        seconds = seconds_per_item + (final_item_bonus if is_last else 0.0)

        card = work / f"card_{item.rank}.png"
        cards.render_item_card(item.rank, item.name, item.stat, card)

        overlays: list[tuple[Path, float, float]] = []
        if index == 0 and ranking.hook_caption.strip():
            hook_png = work / "hook.png"
            render_caption_png(
                Caption(ranking.hook_caption, 0, HOOK_SECONDS, 62, 0.13), hook_png
            )
            overlays.append((hook_png, 0.15, HOOK_SECONDS))
        if is_last and ranking.closing_caption.strip():
            closing_png = work / "closing.png"
            render_caption_png(
                Caption(ranking.closing_caption, 0, CLOSING_SECONDS, 56, 0.13), closing_png
            )
            overlays.append((closing_png, max(seconds - CLOSING_SECONDS, 0.0), seconds))

        segment = work / f"seg_{index:02d}.mp4"
        _normalise_and_card(clips[item.rank], card, segment, seconds, overlays)
        segments.append(segment)
        total += seconds

    body = run_dir / "body.mp4"
    assemble.concat(segments, body)

    final = run_dir / "final.mp4"
    # Loop shaping is deliberately skipped: a countdown ends on its payoff, and
    # crossfading that back into the opening would undercut it.
    assemble.finish(body, final, hook="", closing="", duration=total, burn_captions=False)
    return final, total
