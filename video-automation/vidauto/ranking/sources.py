"""Clip sources.

Every source implements the same two operations -- search and download -- so
the pipeline fans out across whatever is configured without caring which is
which. Adding Pond5, Envato, Wikimedia Commons or NASA is a matter of writing
one more `Source` subclass.

Licensing is carried on every candidate rather than assumed per source,
because it genuinely differs: Pexels and Pixabay require no attribution, while
Wikimedia Commons is mostly CC-BY/CC-BY-SA and does. Getting this wrong means
infringing while believing you are safe, so the field is mandatory.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import requests

from .. import ffmpeg
from .models import Candidate

TIMEOUT = 60


class SourceError(RuntimeError):
    pass


class Source:
    name = "base"

    def search(self, query: str, limit: int) -> list[Candidate]:
        raise NotImplementedError

    def download(self, candidate: Candidate, dest: Path) -> Path:
        """Default: fetch download_url over HTTP."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        try:
            with requests.get(candidate.download_url, stream=True, timeout=TIMEOUT) as r:
                if r.status_code != 200:
                    raise SourceError(f"{self.name} download failed: HTTP {r.status_code}")
                with dest.open("wb") as fh:
                    for chunk in r.iter_content(chunk_size=1 << 16):
                        fh.write(chunk)
        except requests.RequestException as exc:
            raise SourceError(f"{self.name} download failed: {exc}") from exc
        return dest


# --------------------------------------------------------------------------
# mock
# --------------------------------------------------------------------------


class MockSource(Source):
    """A network-free source that fabricates plausible candidates.

    It deliberately returns a mix of on-topic and off-topic clips, because a
    real stock API always returns *something* for any query and the wrong
    results are the interesting case. Each candidate carries `true_subject`,
    which the mock verifier reads to simulate a vision judgement.

    What this proves is the plumbing: fan-out, gating, quality filtering,
    deduplication, selection and assembly. It cannot prove a real vision
    model's accuracy -- nothing offline can.
    """

    name = "mock"

    # How many of every N candidates are deliberately wrong.
    WRONG_EVERY = 3

    def __init__(self, decoys: tuple[str, ...] = ("a parking lot", "an empty office", "a houseplant")):
        self.decoys = decoys

    def search(self, query: str, limit: int) -> list[Candidate]:
        out: list[Candidate] = []
        for i in range(limit):
            digest = hashlib.sha256(f"{query}:{i}".encode()).digest()
            wrong = i % self.WRONG_EVERY == self.WRONG_EVERY - 1
            subject = self.decoys[digest[0] % len(self.decoys)] if wrong else query

            # Vary shape and length so the quality filter has something to do.
            vertical = digest[1] % 3 == 0
            width, height = (1080, 1920) if vertical else (1920, 1080)
            if digest[2] % 7 == 0:  # occasional unusable low-res result
                width, height = width // 4, height // 4

            out.append(
                Candidate(
                    source=self.name,
                    source_id=digest.hex()[:16],
                    title=f"{subject} (mock {i})",
                    page_url=f"https://example.invalid/{digest.hex()[:8]}",
                    download_url="",
                    width=width,
                    height=height,
                    duration=2.0 + (digest[3] % 10),
                    license="mock-public-domain",
                    attribution_required=False,
                    true_subject=subject,
                )
            )
        return out

    def download(self, candidate: Candidate, dest: Path) -> Path:
        """Render a synthetic clip instead of fetching one."""
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(candidate.source_id.encode()).digest()
        colour = f"0x{digest[0]:02x}{digest[1]:02x}{digest[2]:02x}"
        ffmpeg.run(
            [
                "-f", "lavfi",
                "-i", f"color=c={colour}:s={candidate.width}x{candidate.height}:d={candidate.duration:.2f}:r=30",
                "-f", "lavfi",
                "-i", f"gradients=s={candidate.width}x{candidate.height}:seed={digest[3]}:d={candidate.duration:.2f}:r=30",
                "-filter_complex", "[0:v][1:v]blend=all_mode=overlay:all_opacity=0.6,noise=alls=8:allf=t,format=yuv420p[v]",
                "-map", "[v]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                "-t", f"{candidate.duration:.2f}",
                str(dest),
            ],
            description=f"rendering mock clip for {candidate.title}",
        )
        return dest


def _title_from(video: dict, query: str) -> str:
    """Best available human label for a Pexels video.

    The Video resource carries `tags` (a list); `alt` belongs to the Photo
    resource. Both are checked because the API has carried each at different
    times, and the query is the last resort so a candidate is never nameless
    in the credits file.
    """
    alt = video.get("alt")
    if isinstance(alt, str) and alt.strip():
        return alt.strip()
    tags = video.get("tags")
    if isinstance(tags, list) and tags:
        return ", ".join(str(t) for t in tags[:5])
    if isinstance(tags, str) and tags.strip():
        return tags.strip()
    return query


# --------------------------------------------------------------------------
# pexels
# --------------------------------------------------------------------------


class PexelsSource(Source):
    """Pexels video search. Free API key. Commercial use, no attribution."""

    name = "pexels"
    ENDPOINT = "https://api.pexels.com/videos/search"

    def __init__(self, api_key: str, portrait_only: bool = False):
        if not api_key:
            raise SourceError("PEXELS_API_KEY is not set")
        self.api_key = api_key
        self.portrait_only = portrait_only

    def search(self, query: str, limit: int) -> list[Candidate]:
        params: dict[str, object] = {"query": query, "per_page": min(limit, 80)}
        # Deliberately NOT filtering to portrait by default. Most stock footage
        # is landscape, so asking the API for portrait only discards the large
        # majority of the library -- and in a pipeline where finding any
        # correct clip is the hard part, recall matters far more than framing.
        # build.py composites landscape over a blurred fill perfectly well, and
        # select._prior already prefers vertical when both are available. This
        # is opt-in for anyone who would rather have gaps than letterboxing.
        if self.portrait_only:
            params["orientation"] = "portrait"
        try:
            resp = requests.get(
                self.ENDPOINT,
                headers={"Authorization": self.api_key},
                params=params,
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            raise SourceError(f"pexels search failed: {exc}") from exc
        if resp.status_code == 401:
            raise SourceError("pexels rejected the API key (401)")
        if resp.status_code != 200:
            raise SourceError(f"pexels search failed: HTTP {resp.status_code} {resp.text[:200]}")

        out: list[Candidate] = []
        for video in resp.json().get("videos", []):
            files = video.get("video_files", [])
            if not files:
                continue
            # Highest resolution that is still a reasonable download.
            best = max(
                (f for f in files if f.get("width")),
                key=lambda f: f.get("width", 0),
                default=None,
            )
            if not best:
                continue
            out.append(
                Candidate(
                    source=self.name,
                    source_id=str(video.get("id")),
                    title=_title_from(video, query),
                    page_url=video.get("url", ""),
                    download_url=best.get("link", ""),
                    width=int(best.get("width") or 0),
                    height=int(best.get("height") or 0),
                    duration=float(video.get("duration") or 0),
                    preview_url=video.get("image", ""),
                    license="Pexels License",
                    attribution_required=False,
                    attribution_text=f"Video by {video.get('user', {}).get('name', 'unknown')} on Pexels",
                )
            )
        return out


# --------------------------------------------------------------------------
# pixabay
# --------------------------------------------------------------------------


class PixabaySource(Source):
    """Pixabay video search. Free API key. Commercial use, no attribution."""

    name = "pixabay"
    ENDPOINT = "https://pixabay.com/api/videos/"

    def __init__(self, api_key: str):
        if not api_key:
            raise SourceError("PIXABAY_API_KEY is not set")
        self.api_key = api_key

    def search(self, query: str, limit: int) -> list[Candidate]:
        try:
            resp = requests.get(
                self.ENDPOINT,
                params={"key": self.api_key, "q": query, "per_page": max(3, min(limit, 200))},
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            raise SourceError(f"pixabay search failed: {exc}") from exc
        if resp.status_code != 200:
            raise SourceError(f"pixabay search failed: HTTP {resp.status_code} {resp.text[:200]}")

        out: list[Candidate] = []
        for hit in resp.json().get("hits", []):
            streams = hit.get("videos", {})
            best_key = next(
                (k for k in ("large", "medium", "small", "tiny") if streams.get(k, {}).get("url")),
                None,
            )
            if not best_key:
                continue
            stream = streams[best_key]
            out.append(
                Candidate(
                    source=self.name,
                    source_id=str(hit.get("id")),
                    title=(hit.get("tags") or query),
                    page_url=hit.get("pageURL", ""),
                    download_url=stream.get("url", ""),
                    width=int(stream.get("width") or 0),
                    height=int(stream.get("height") or 0),
                    duration=float(hit.get("duration") or 0),
                    preview_url=stream.get("thumbnail", ""),
                    license="Pixabay Content License",
                    attribution_required=False,
                    attribution_text=f"Video by {hit.get('user', 'unknown')} on Pixabay",
                )
            )
        return out


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------


def build_sources(names: list[str]) -> list[Source]:
    sources: list[Source] = []
    for name in names:
        key = name.strip().lower()
        if not key:
            continue
        if key == "mock":
            sources.append(MockSource())
        elif key == "pexels":
            sources.append(
                PexelsSource(
                    os.environ.get("PEXELS_API_KEY", ""),
                    portrait_only=os.environ.get("PEXELS_PORTRAIT_ONLY", "").lower()
                    in {"1", "true", "yes", "on"},
                )
            )
        elif key == "pixabay":
            sources.append(PixabaySource(os.environ.get("PIXABAY_API_KEY", "")))
        else:
            raise SourceError(f"Unknown clip source {name!r} (mock|pexels|pixabay)")
    if not sources:
        raise SourceError("No clip sources configured")
    return sources
