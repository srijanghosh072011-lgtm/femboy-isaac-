"""Ranking-video run orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import Config
from ..pipeline import slugify
from . import build as build_mod
from . import ledger as ledger_mod
from . import listgen, select
from .models import RankList
from .sources import build_sources


@dataclass
class RankRunResult:
    directory: Path
    video: Path | None
    ranking: RankList
    duration: float
    resolved: int
    requested: int
    reports: list[select.SelectionReport]


def generate_list(cfg: Config, seed: int | None = None) -> RankList:
    if cfg.text_provider == "mock":
        return listgen.offline_list(seed)

    from .. import providers  # local import keeps the mock path import-light

    payload = {
        "model": cfg.text_model,
        "messages": [
            {"role": "system", "content": listgen.LIST_SYSTEM_PROMPT.format(count=cfg.rank_items)},
            {"role": "user", "content": "Generate one ranked list. Return only the JSON object."},
        ],
    }
    data = providers._post(cfg, "/chat/completions", payload)
    return listgen.parse_list_json(data["choices"][0]["message"]["content"])


def run_once(cfg: Config, seed: int | None = None, keep_intermediates: bool = False) -> RankRunResult:
    cfg.validate()
    sources = build_sources(cfg.clip_sources)

    ranking = generate_list(cfg, seed=seed)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = cfg.out_dir / f"{stamp}-rank-{slugify(ranking.title)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    ledger = ledger_mod.Ledger.load(cfg.ledger_path)

    reports: list[select.SelectionReport] = []
    clips: dict[int, Path] = {}
    for item in ranking.items:
        report = select.select_for_item(
            cfg, sources, item, ledger, run_dir, min_seconds=cfg.seconds_per_item
        )
        reports.append(report)
        if item.chosen:
            try:
                clips[item.rank] = select.download_chosen(sources, item.chosen, run_dir)
            except Exception as exc:  # noqa: BLE001 - one bad download is not fatal
                report.error = f"download of chosen clip failed: {exc}"
                item.chosen = None

    resolved = [i for i in ranking.items if i.chosen and i.rank in clips]

    video: Path | None = None
    duration = 0.0
    if resolved:
        video, duration = build_mod.build(ranking, clips, run_dir, cfg.seconds_per_item)
        # Only record clips that actually made it into a rendered video --
        # recording earlier would burn a clip that a later failure discarded.
        for item in resolved:
            ledger.record(item.chosen, video=run_dir.name, item_name=item.name)
        ledger.save()
        ledger_mod.write_credits(
            run_dir / "CREDITS.md", [i.chosen for i in resolved], ranking.title
        )

    _write_manifest(run_dir, cfg, ranking, reports, duration, len(resolved))
    _write_posting(run_dir, cfg, ranking, resolved)

    if not keep_intermediates and video is not None:
        import shutil

        shutil.rmtree(run_dir / "segments", ignore_errors=True)
        shutil.rmtree(run_dir / "clips", ignore_errors=True)
        for leftover in run_dir.glob("*.jpg"):
            leftover.unlink(missing_ok=True)
        (run_dir / "body.mp4").unlink(missing_ok=True)
        (run_dir / "segments.txt").unlink(missing_ok=True)

    return RankRunResult(
        directory=run_dir,
        video=video,
        ranking=ranking,
        duration=duration,
        resolved=len(resolved),
        requested=len(ranking.items),
        reports=reports,
    )


def _write_manifest(
    run_dir: Path,
    cfg: Config,
    ranking: RankList,
    reports: list[select.SelectionReport],
    duration: float,
    resolved: int,
) -> None:
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "ranking": ranking.to_dict(),
        "duration_seconds": round(duration, 2),
        "resolved_items": resolved,
        "requested_items": len(ranking.items),
        "config": {
            "clip_sources": cfg.clip_sources,
            "vision_provider": cfg.vision_provider,
            "vision_model": cfg.vision_model if cfg.vision_provider != "mock" else None,
            "verify_threshold": cfg.verify_threshold,
            "max_vision_checks": cfg.max_vision_checks,
            "candidates_per_query": cfg.candidates_per_query,
            "seconds_per_item": cfg.seconds_per_item,
        },
        # The per-item sourcing trace. This is the thing to read when a video
        # comes out with gaps: it says how many clips were found, how many the
        # gate rejected, and why.
        "sourcing": [
            {
                "rank": r.item.rank,
                "name": r.item.name,
                "searched": r.searched,
                "already_used": r.already_used,
                "filtered_out": r.filtered_out,
                "vision_checks": r.checked,
                "rejected_by_vision": r.rejected_by_vision,
                "resolved": r.item.chosen is not None,
                "chosen": r.item.chosen.to_dict() if r.item.chosen else None,
                "error": r.error,
            }
            for r in reports
        ],
        "warnings": ranking.warnings(),
    }
    (run_dir / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n")


def _write_posting(run_dir: Path, cfg: Config, ranking: RankList, resolved: list) -> None:
    unresolved = [i for i in ranking.items if i.chosen is None]
    generated = cfg.clip_sources != ["mock"]

    lines = [f"# Posting checklist -- {ranking.title}", ""]

    from .verify import UNVERIFIED_NOTE

    unverified = [i for i in resolved if UNVERIFIED_NOTE in (i.chosen.verify_note or "")]
    if unverified:
        lines += [
            "## THESE CLIPS WERE NOT CHECKED",
            "",
            "VISION_PROVIDER=mock cannot judge a real clip, so these went into the",
            "video without anything confirming they show what the entry says. Watch",
            "the video before posting, or set VISION_PROVIDER=openai/anthropic and",
            "re-run to have them actually verified.",
            "",
        ]
        for item in unverified:
            lines.append(f"- #{item.rank} {item.name} -- {item.chosen.title}")
        lines.append("")

    if unresolved:
        lines += [
            "## Unresolved items (READ THIS FIRST)",
            "",
            "No clip cleared the relevance gate for these entries, so they are NOT",
            "in the video. The pipeline leaves a gap rather than using a clip it",
            "knows is wrong. Either add search terms, lower VERIFY_THRESHOLD, add a",
            "source, or swap the item out.",
            "",
        ]
        for item in unresolved:
            lines.append(f"- #{item.rank} {item.name}")
        lines.append("")

    lines += ["## Licensing", ""]
    if generated:
        lines += [
            "See CREDITS.md. Anything under 'Attribution REQUIRED' must appear in",
            "the video description before you publish -- those licenses oblige it.",
            "",
        ]
    else:
        lines += [
            "This run used the MOCK clip source, so the footage is procedurally",
            "generated placeholder, not real stock. It is not publishable.",
            "",
        ]

    lines += [
        "## AI disclosure",
        "",
    ]
    if generated:
        lines += [
            "The footage here is real licensed stock, not generated, so the",
            "synthetic-media labels do not apply to the clips. If you later add",
            "generated B-roll or an AI voiceover, they do -- set them then.",
            "",
        ]
    else:
        lines += ["Mock run; not publishable, so nothing to disclose yet.", ""]

    lines += [
        "## Copy",
        "",
        f"- Hook: {ranking.hook_caption}",
        f"- Closing: {ranking.closing_caption}",
        "",
        "## Checklist",
        "",
        "- [ ] Countdown reads correctly and #1 lands last",
        "- [ ] Every on-screen stat is one you can stand behind",
        "- [ ] Required attributions pasted into the description",
        "- [ ] Hook varied if posting to more than one owned account",
        "",
    ]
    (run_dir / "POSTING.md").write_text("\n".join(lines))
