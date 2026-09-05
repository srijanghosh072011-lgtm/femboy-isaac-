"""Parsing tests against the documented API response shapes.

The Pexels and Pixabay hosts are unreachable from the build environment, so
these adapters cannot be exercised end to end here. What *can* be pinned down
offline is the part most likely to be wrong: reading the response.

The fixtures below mirror the field names and nesting in each API's published
documentation. They will not catch an auth or endpoint mistake -- only a live
call does that -- but they do catch the silent failure mode where every field
comes back None and every candidate is quietly discarded.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vidauto.ranking.sources import (  # noqa: E402
    PexelsSource,
    PixabaySource,
    SourceError,
    _title_from,
)


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


# Mirrors https://www.pexels.com/api/documentation/ -- Video resource.
PEXELS_PAYLOAD = {
    "page": 1,
    "per_page": 2,
    "total_results": 200,
    "videos": [
        {
            "id": 1358988,
            "width": 3840,
            "height": 2160,
            "url": "https://www.pexels.com/video/light-city-man-people-1358988/",
            "image": "https://images.pexels.com/videos/1358988/free-video-1358988.jpg",
            "duration": 19,
            "tags": ["roof", "worker", "sky"],
            "user": {"id": 2421, "name": "Rene Asmussen", "url": "https://www.pexels.com/@rene"},
            "video_files": [
                {
                    "id": 58184,
                    "quality": "sd",
                    "file_type": "video/mp4",
                    "width": 640,
                    "height": 360,
                    "fps": 25,
                    "link": "https://player.vimeo.com/external/sd.mp4",
                },
                {
                    "id": 58185,
                    "quality": "hd",
                    "file_type": "video/mp4",
                    "width": 1920,
                    "height": 1080,
                    "fps": 25,
                    "link": "https://player.vimeo.com/external/hd.mp4",
                },
            ],
            "video_pictures": [{"id": 133236, "nr": 0, "picture": "https://x/pic.png"}],
        }
    ],
}

# Mirrors https://pixabay.com/api/docs/ -- videos endpoint.
PIXABAY_PAYLOAD = {
    "total": 120,
    "totalHits": 100,
    "hits": [
        {
            "id": 125,
            "pageURL": "https://pixabay.com/videos/id-125/",
            "type": "film",
            "tags": "flowers, yellow, blossom",
            "duration": 12,
            "picture_id": "1234567",
            "videos": {
                "large": {
                    "url": "https://cdn.pixabay.com/vimeo/large.mp4",
                    "width": 1920,
                    "height": 1080,
                    "size": 6615235,
                    "thumbnail": "https://i.vimeocdn.com/video/large.jpg",
                },
                "medium": {
                    "url": "https://cdn.pixabay.com/vimeo/medium.mp4",
                    "width": 1280,
                    "height": 720,
                    "size": 1618644,
                    "thumbnail": "https://i.vimeocdn.com/video/medium.jpg",
                },
            },
            "user": "CoverrFreeFootage",
        }
    ],
}


def test_pexels_parses_the_documented_shape(monkeypatch):
    monkeypatch.setattr(
        "vidauto.ranking.sources.requests.get",
        lambda *a, **kw: FakeResponse(PEXELS_PAYLOAD),
    )
    results = PexelsSource("key").search("roofer", 10)

    assert len(results) == 1
    c = results[0]
    assert c.source == "pexels"
    assert c.source_id == "1358988"
    # The highest-resolution video_file wins, not the first.
    assert c.download_url.endswith("hd.mp4")
    assert (c.width, c.height) == (1920, 1080)
    assert c.duration == 19
    assert c.preview_url.startswith("https://images.pexels.com/")
    assert c.attribution_required is False
    assert "Rene Asmussen" in c.attribution_text
    assert c.page_url.startswith("https://www.pexels.com/")


def test_pexels_does_not_restrict_orientation_by_default(monkeypatch):
    seen = {}

    def capture(*a, **kw):
        seen.update(kw.get("params", {}))
        return FakeResponse(PEXELS_PAYLOAD)

    monkeypatch.setattr("vidauto.ranking.sources.requests.get", capture)
    PexelsSource("key").search("roofer", 10)
    # Filtering to portrait at the API level would discard most of the library;
    # framing is handled downstream by the blurred fill.
    assert "orientation" not in seen


def test_pexels_portrait_only_is_opt_in(monkeypatch):
    seen = {}

    def capture(*a, **kw):
        seen.update(kw.get("params", {}))
        return FakeResponse(PEXELS_PAYLOAD)

    monkeypatch.setattr("vidauto.ranking.sources.requests.get", capture)
    PexelsSource("key", portrait_only=True).search("roofer", 10)
    assert seen.get("orientation") == "portrait"


def test_pexels_skips_videos_with_no_files(monkeypatch):
    payload = {"videos": [{"id": 1, "video_files": []}]}
    monkeypatch.setattr(
        "vidauto.ranking.sources.requests.get", lambda *a, **kw: FakeResponse(payload)
    )
    assert PexelsSource("key").search("x", 5) == []


def test_pexels_surfaces_a_bad_key(monkeypatch):
    monkeypatch.setattr(
        "vidauto.ranking.sources.requests.get",
        lambda *a, **kw: FakeResponse({}, status_code=401, text="unauthorised"),
    )
    with pytest.raises(SourceError, match="401"):
        PexelsSource("bad").search("x", 5)


def test_pixabay_parses_the_documented_shape(monkeypatch):
    monkeypatch.setattr(
        "vidauto.ranking.sources.requests.get",
        lambda *a, **kw: FakeResponse(PIXABAY_PAYLOAD),
    )
    results = PixabaySource("key").search("flowers", 10)

    assert len(results) == 1
    c = results[0]
    assert c.source == "pixabay"
    assert c.source_id == "125"
    # "large" is preferred over "medium".
    assert c.download_url.endswith("large.mp4")
    assert (c.width, c.height) == (1920, 1080)
    assert c.duration == 12
    assert c.preview_url.endswith("large.jpg")
    assert "CoverrFreeFootage" in c.attribution_text
    assert c.attribution_required is False


def test_pixabay_falls_back_to_a_smaller_stream(monkeypatch):
    payload = {
        "hits": [
            {
                "id": 9,
                "pageURL": "https://pixabay.com/videos/id-9/",
                "tags": "x",
                "duration": 5,
                "videos": {
                    "large": {},  # present but unusable
                    "small": {
                        "url": "https://cdn/small.mp4",
                        "width": 960,
                        "height": 540,
                        "thumbnail": "https://cdn/small.jpg",
                    },
                },
                "user": "someone",
            }
        ]
    }
    monkeypatch.setattr(
        "vidauto.ranking.sources.requests.get", lambda *a, **kw: FakeResponse(payload)
    )
    results = PixabaySource("key").search("x", 5)
    assert len(results) == 1
    assert results[0].download_url.endswith("small.mp4")


def test_pixabay_skips_hits_with_no_usable_stream(monkeypatch):
    payload = {"hits": [{"id": 1, "videos": {}}]}
    monkeypatch.setattr(
        "vidauto.ranking.sources.requests.get", lambda *a, **kw: FakeResponse(payload)
    )
    assert PixabaySource("key").search("x", 5) == []


@pytest.mark.parametrize(
    "video,expected",
    [
        ({"alt": "a roofer at work"}, "a roofer at work"),
        ({"tags": ["roof", "worker"]}, "roof, worker"),
        ({"tags": "roof, worker"}, "roof, worker"),
        ({}, "the query"),
        ({"alt": "   "}, "the query"),
    ],
)
def test_title_extraction_never_returns_empty(video, expected):
    assert _title_from(video, "the query") == expected
