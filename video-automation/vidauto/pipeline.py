"""Run orchestration.

A run is a directory. Every intermediate artifact is written to it and every
step skips work whose output already exists, so re-running after a failure
resumes instead of paying for the images again. That property is the whole
reason this is a directory of files rather than an in-memory pipeline: image
generation is the expensive step and it must never be repeated by accident.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import assemble, motion, providers, topics
from .config import Config


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:max_len].rstrip("-")) or "untitled"


@dataclass
class RunResult:
    directory: Path
    video: Path
    topic: topics.Topic
    duration: float
    warnings: list[str]


def _write_manifest(run_dir: Path, payload: dict) -> None:
    (run_dir / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n")


def _write_disclosure(run_dir: Path, topic: topics.Topic, cfg: Config) -> None:
    """Write the posting checklist.

    Kept as a file next to the video rather than a line in a log because the
    posting step is manual: the person uploading needs something to read, and
    the AI-disclosure toggle is the one item that carries a real penalty for
    being skipped.
    """
    generated = cfg.image_provider != "mock"
    lines = [
        f"# Posting checklist -- {topic.topic}",
        "",
        "## AI disclosure (REQUIRED)",
        "",
    ]
    if generated:
        lines += [
            "This video contains AI-generated imagery showing a realistic-looking scene.",
            "That is exactly the condition the platform rules are written for. Set the",
            "disclosure on every platform before publishing:",
            "",
            "- [ ] YouTube Studio -> Altered or synthetic content -> Yes",
            "- [ ] TikTok -> AI-generated content label",
            "- [ ] Instagram -> Made with AI",
            "",
        ]
    else:
        lines += [
            "This run used the MOCK image provider, so the footage is procedural test",
            "output, not a realistic scene. It is not publishable. Disclosure rules will",
            "apply as soon as you switch IMAGE_PROVIDER to a real generator.",
            "",
        ]
    lines += [
        "## Copy",
        "",
        f"- Hook caption (burned into frame 1): {topic.hook_caption}",
        f"- Closing caption: {topic.closing_caption}",
        f"- Description / pinned comment: {topic.science_fact}",
        "",
        "## Retention checklist",
        "",
        "- [ ] Subject is already on screen in the first frame (no build-up)",
        "- [ ] Runtime is in the 15-22s band",
        "- [ ] Ends on the comment-bait line",
        "- [ ] Loop is seamless on repeat",
        "- [ ] Posted natively at 9:16, no watermark from another platform",
        "- [ ] Hook caption varied if posting to more than one owned account",
        "",
    ]
    (run_dir / "POSTING.md").write_text("\n".join(lines))


def run_once(cfg: Config, seed: int | None = None, keep_intermediates: bool = False) -> RunResult:
    cfg.validate()

    topic = providers.generate_topic(cfg, seed=seed)
    warnings = topic.warnings()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = cfg.out_dir / f"{stamp}-{slugify(topic.topic)}"
    images_dir = run_dir / "images"
    segments_dir = run_dir / "segments"
    for d in (images_dir, segments_dir):
        d.mkdir(parents=True, exist_ok=True)

    prompts = topics.shot_prompts(topic, cfg.segments, seed=seed)

    segment_paths: list[Path] = []
    for i, prompt in enumerate(prompts):
        image_path = images_dir / f"{i:02d}.png"
        providers.generate_image(cfg, prompt, image_path, i)

        segment_path = segments_dir / f"{i:02d}.mp4"
        if not segment_path.exists() or segment_path.stat().st_size == 0:
            motion.render_segment(
                image_path,
                segment_path,
                cfg.seconds_per_segment,
                motion.move_for_index(i),
            )
        segment_paths.append(segment_path)

    body = run_dir / "body.mp4"
    assemble.concat(segment_paths, body)
    duration = cfg.total_seconds

    if cfg.loop_shape:
        looped = run_dir / "looped.mp4"
        duration = assemble.shape_loop(body, looped, duration)
        staged = looped
    else:
        staged = body

    final = run_dir / "final.mp4"
    assemble.finish(
        staged,
        final,
        hook=topic.hook_caption,
        closing=topic.closing_caption,
        duration=duration,
        burn_captions=cfg.burn_captions,
    )

    _write_manifest(
        run_dir,
        {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "topic": topic.to_dict(),
            "prompts": prompts,
            "moves": [motion.move_for_index(i).name for i in range(len(prompts))],
            "config": {
                "image_provider": cfg.image_provider,
                "text_provider": cfg.text_provider,
                "image_model": cfg.image_model if cfg.image_provider == "openai" else None,
                "image_quality": cfg.image_quality if cfg.image_provider == "openai" else None,
                "text_model": cfg.text_model if cfg.text_provider == "openai" else None,
                "segments": cfg.segments,
                "seconds_per_segment": cfg.seconds_per_segment,
                "loop_shape": cfg.loop_shape,
                "burn_captions": cfg.burn_captions,
            },
            "duration_seconds": round(duration, 3),
            "ai_generated_imagery": cfg.image_provider != "mock",
            "warnings": warnings,
        },
    )
    _write_disclosure(run_dir, topic, cfg)

    if not keep_intermediates:
        shutil.rmtree(segments_dir, ignore_errors=True)
        leftovers = [body, run_dir / "looped.mp4", run_dir / "segments.txt"]
        leftovers += sorted(run_dir.glob("caption_*.png"))
        for leftover in leftovers:
            leftover.unlink(missing_ok=True)

    return RunResult(directory=run_dir, video=final, topic=topic, duration=duration, warnings=warnings)
