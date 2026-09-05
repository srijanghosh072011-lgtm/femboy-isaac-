"""Finding the right clip for one list item.

The expensive resource here is vision checks, so the order of operations
matters: everything that can be decided for free (resolution, duration,
already-used, aspect ratio) is decided before any model is asked anything, and
the survivors are checked best-prior-first with an early stop as soon as one
clears the bar.

A run that cannot find a good clip for an item leaves it unresolved rather than
falling back to the least-bad candidate. Publishing a confidently wrong clip is
worse than publishing nine items instead of ten -- it is the specific failure
that makes automated ranking videos recognisable as slop.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from . import verify
from .ledger import Ledger
from .models import Candidate, RankItem
from .sources import Source, SourceError

# Below this the clip is not usable even after upscaling.
MIN_WIDTH = 640
MIN_HEIGHT = 640


@dataclass
class SelectionReport:
    item: RankItem
    searched: int = 0
    filtered_out: int = 0
    already_used: int = 0
    checked: int = 0
    rejected_by_vision: int = 0
    error: str | None = None


def _prior(candidate: Candidate) -> tuple[int, float]:
    """Cheap ordering heuristic, applied before any model is consulted.

    Vertical clips first (they need no letterboxing), then by pixel count.

    Lexicographic rather than a weighted sum on purpose: with a multiplier,
    a large enough landscape clip outranks a vertical one -- 3840x2160 ties
    1080x1920 at 4x exactly -- which silently loses the preference for the
    clips that fill the frame. This decides only the *order* of vision checks,
    never whether a clip is acceptable; that is the gate's job.
    """
    return (1 if candidate.is_vertical else 0, float(candidate.width * candidate.height))


def gather(
    sources: list[Source],
    item: RankItem,
    per_query: int,
) -> tuple[list[Candidate], list[str]]:
    """Fan out across every source x every search term."""
    pool: dict[str, Candidate] = {}
    errors: list[str] = []
    for term in item.search_terms:
        for source in sources:
            try:
                for candidate in source.search(term, per_query):
                    # First sighting wins; the same clip often appears under
                    # several of an item's search terms.
                    pool.setdefault(candidate.key, candidate)
            except SourceError as exc:
                errors.append(f"{source.name}/{term!r}: {exc}")
    return list(pool.values()), errors


def usable(candidate: Candidate, min_seconds: float) -> str | None:
    """Return a rejection reason, or None if the candidate passes."""
    if candidate.width < MIN_WIDTH or candidate.height < MIN_HEIGHT:
        return f"too small ({candidate.width}x{candidate.height})"
    if candidate.duration and candidate.duration < min_seconds:
        return f"too short ({candidate.duration:.1f}s < {min_seconds:.1f}s)"
    if not candidate.download_url and candidate.source != "mock":
        return "no download url"
    return None


def select_for_item(
    cfg: Config,
    sources: list[Source],
    item: RankItem,
    ledger: Ledger,
    work_dir: Path,
    min_seconds: float,
) -> SelectionReport:
    report = SelectionReport(item=item)

    pool, errors = gather(sources, item, cfg.candidates_per_query)
    if errors and not pool:
        report.error = "; ".join(errors[:3])
        return report
    report.searched = len(pool)

    viable: list[Candidate] = []
    for candidate in pool:
        if ledger.has_used(candidate):
            report.already_used += 1
            continue
        reason = usable(candidate, min_seconds)
        if reason:
            candidate.reject_reason = reason
            report.filtered_out += 1
            continue
        viable.append(candidate)

    viable.sort(key=_prior, reverse=True)
    item.candidates_seen = len(viable)

    best_below_threshold: Candidate | None = None
    for candidate in viable[: cfg.max_vision_checks]:
        clip: Path | None = None
        # The mock source has no preview, so its clip must exist to be scored;
        # real sources are scored from the hosted preview and only downloaded
        # once they have actually won.
        if cfg.vision_provider == "mock" or not candidate.preview_url:
            try:
                clip = _download(sources, candidate, work_dir)
            except SourceError as exc:
                candidate.reject_reason = f"download failed: {exc}"
                continue

        try:
            score, shows = verify.score_candidate(cfg, candidate, clip, item, work_dir)
        except Exception as exc:  # noqa: BLE001 - a bad check must not kill the run
            candidate.reject_reason = f"vision check failed: {exc}"
            continue

        report.checked += 1
        candidate.relevance = score

        if score >= cfg.verify_threshold:
            item.chosen = candidate
            return report

        candidate.reject_reason = f"scored {score:.1f} ({shows})"
        report.rejected_by_vision += 1
        if best_below_threshold is None or score > (best_below_threshold.relevance or 0):
            best_below_threshold = candidate

    # Deliberately no fallback to `best_below_threshold`. It is recorded on the
    # report so the manifest can explain the miss, but a clip the gate rejected
    # does not go in the video.
    if best_below_threshold is not None:
        report.error = (
            f"no candidate reached {cfg.verify_threshold}; best was "
            f"{best_below_threshold.relevance:.1f} ({best_below_threshold.title})"
        )
    elif not report.checked:
        report.error = "no viable candidates to check"
    return report


def _download(sources: list[Source], candidate: Candidate, work_dir: Path) -> Path:
    source = next((s for s in sources if s.name == candidate.source), None)
    if source is None:
        raise SourceError(f"No configured source named {candidate.source!r}")
    dest = work_dir / "clips" / f"{candidate.source}_{candidate.source_id}.mp4"
    return source.download(candidate, dest)


def download_chosen(sources: list[Source], candidate: Candidate, work_dir: Path) -> Path:
    """Fetch the winning clip (a no-op if the gate already downloaded it)."""
    return _download(sources, candidate, work_dir)
