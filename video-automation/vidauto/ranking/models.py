"""Core data types for the ranking pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Candidate:
    """One clip a source offered for one list item.

    `true_subject` is populated only by the mock source, which knows what it
    generated. Real sources cannot know this -- establishing what a clip
    actually depicts is exactly what the vision gate exists to do.
    """

    source: str
    source_id: str
    title: str
    page_url: str
    download_url: str
    width: int
    height: int
    duration: float
    license: str
    attribution_required: bool
    attribution_text: str = ""
    # A still the source already hosts. When present the vision gate inspects
    # this instead of downloading the clip, so a rejected candidate never costs
    # a video download -- and most candidates are rejected.
    preview_url: str = ""
    true_subject: str | None = None
    # What the gate said about this clip. Carries the UNVERIFIED marker
    # when the mock gate passed a real clip through without judging it.
    verify_note: str = ""

    # Filled in by the pipeline as the candidate moves through it.
    relevance: float | None = None
    reject_reason: str | None = None

    @property
    def key(self) -> str:
        """Stable identity for the dedupe ledger."""
        return f"{self.source}:{self.source_id}"

    @property
    def is_vertical(self) -> bool:
        return self.height >= self.width

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RankItem:
    """One entry in the ranking."""

    rank: int
    name: str
    stat: str
    # Several phrasings per item. Stock search is keyword matching, so the
    # obvious noun often misses while a near-synonym or the activity it
    # implies hits -- "logger" returns portraits, "felling a tree" returns
    # the shot you actually want.
    search_terms: list[str] = field(default_factory=list)

    chosen: Candidate | None = None
    candidates_seen: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "name": self.name,
            "stat": self.stat,
            "search_terms": self.search_terms,
            "chosen": self.chosen.to_dict() if self.chosen else None,
            "candidates_seen": self.candidates_seen,
        }


@dataclass
class RankList:
    """A whole video's worth of ranking."""

    title: str
    hook_caption: str
    closing_caption: str
    items: list[RankItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "hook_caption": self.hook_caption,
            "closing_caption": self.closing_caption,
            "items": [i.to_dict() for i in self.items],
        }

    @property
    def unresolved(self) -> list[RankItem]:
        return [i for i in self.items if i.chosen is None]

    def warnings(self) -> list[str]:
        out = []
        if len(self.hook_caption.split()) > 8:
            out.append("hook_caption is over 8 words")
        ranks = [i.rank for i in self.items]
        if sorted(ranks, reverse=True) != ranks:
            out.append("items are not in descending rank order (countdown expects 10 -> 1)")
        if len(set(ranks)) != len(ranks):
            out.append("duplicate ranks in the list")
        for item in self.items:
            if not item.search_terms:
                out.append(f"item {item.rank} ({item.name}) has no search terms")
        return out
