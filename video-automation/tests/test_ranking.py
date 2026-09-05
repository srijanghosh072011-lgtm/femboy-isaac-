"""Tests for the ranking pipeline.

Two guarantees here are worth more than the rest and get the most attention:

  1. A clip the gate rejected never ends up in the video. The tempting
     "use the best of a bad bunch" fallback is exactly what makes automated
     ranking videos look like slop, so its absence is tested directly.
  2. A clip used in any previous video is never selected again. This is a
     cross-run property, so the test drives two runs against one ledger.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vidauto.config import HEIGHT, WIDTH, Config  # noqa: E402
from vidauto.ffmpeg import ffmpeg_bin  # noqa: E402
from vidauto.ranking import cards, ledger as ledger_mod, listgen, select, verify  # noqa: E402
from vidauto.ranking.models import Candidate, RankItem, RankList  # noqa: E402
from vidauto.ranking.sources import MockSource, build_sources, SourceError  # noqa: E402


def make_candidate(**kwargs) -> Candidate:
    defaults = dict(
        source="mock",
        source_id="abc123",
        title="a thing",
        page_url="https://example.invalid/x",
        download_url="https://example.invalid/x.mp4",
        width=1920,
        height=1080,
        duration=8.0,
        license="test",
        attribution_required=False,
    )
    defaults.update(kwargs)
    return Candidate(**defaults)


def make_item(**kwargs) -> RankItem:
    defaults = dict(rank=1, name="Logger", stat="a stat", search_terms=["felling a tree"])
    defaults.update(kwargs)
    return RankItem(**defaults)


# --------------------------------------------------------------------------
# list generation
# --------------------------------------------------------------------------


def test_offline_lists_are_internally_consistent():
    for ranking in listgen.OFFLINE_LISTS:
        assert ranking.warnings() == [], f"{ranking.title}: {ranking.warnings()}"


def test_offline_list_is_a_deep_copy():
    # A run mutates items (sets .chosen). If offline_list handed back the
    # module-level object, the second run in a process would start dirty.
    first = listgen.offline_list(1)
    first.items[0].chosen = make_candidate()
    second = listgen.offline_list(1)
    assert second.items[0].chosen is None


def test_parse_list_json_sorts_into_countdown_order():
    payload = {
        "title": "t",
        "hook_caption": "h",
        "closing_caption": "c",
        "items": [
            {"rank": 1, "name": "one", "stat": "s", "search_terms": ["a"]},
            {"rank": 3, "name": "three", "stat": "s", "search_terms": ["a"]},
            {"rank": 2, "name": "two", "stat": "s", "search_terms": ["a"]},
        ],
    }
    ranking = listgen.parse_list_json(json.dumps(payload))
    assert [i.rank for i in ranking.items] == [3, 2, 1]


def test_parse_list_json_accepts_a_bare_string_search_term():
    payload = {
        "title": "t", "hook_caption": "h", "closing_caption": "c",
        "items": [{"rank": 1, "name": "one", "stat": "s", "search_terms": "just one"}],
    }
    assert listgen.parse_list_json(json.dumps(payload)).items[0].search_terms == ["just one"]


def test_parse_list_json_rejects_empty_items():
    payload = {"title": "t", "hook_caption": "h", "closing_caption": "c", "items": []}
    with pytest.raises(ValueError, match="no items"):
        listgen.parse_list_json(json.dumps(payload))


def test_ranklist_warns_on_ascending_ranks():
    ranking = RankList("t", "h", "c", [make_item(rank=1), make_item(rank=2)])
    assert any("descending" in w for w in ranking.warnings())


def test_ranklist_warns_on_missing_search_terms():
    ranking = RankList("t", "h", "c", [make_item(rank=1, search_terms=[])])
    assert any("no search terms" in w for w in ranking.warnings())


# --------------------------------------------------------------------------
# quality filter
# --------------------------------------------------------------------------


def test_usable_rejects_low_resolution():
    assert "too small" in select.usable(make_candidate(width=320, height=240), 3.0)


def test_usable_rejects_short_clips():
    assert "too short" in select.usable(make_candidate(duration=1.0), 3.5)


def test_usable_accepts_a_good_clip():
    assert select.usable(make_candidate(), 3.0) is None


def test_usable_rejects_real_source_without_download_url():
    c = make_candidate(source="pexels", download_url="")
    assert "no download url" in select.usable(c, 3.0)


def test_prior_puts_vertical_first():
    vertical = make_candidate(width=1080, height=1920)
    bigger_landscape = make_candidate(width=3840, height=2160)
    assert select._prior(vertical) > select._prior(bigger_landscape)


# --------------------------------------------------------------------------
# the two guarantees
# --------------------------------------------------------------------------


def test_gate_never_falls_back_to_a_rejected_candidate(tmp_path):
    """Every candidate is a decoy, so nothing may be chosen."""
    cfg = Config(vision_provider="mock", verify_threshold=7.0, candidates_per_query=6)
    # A source whose every result is off-topic.
    source = MockSource(decoys=("a parking lot",))
    source.WRONG_EVERY = 1
    item = make_item()
    ledger = ledger_mod.Ledger(path=tmp_path / "l.json", used={})

    report = select.select_for_item(cfg, [source], item, ledger, tmp_path, min_seconds=3.0)

    assert item.chosen is None
    assert report.rejected_by_vision > 0
    assert "no candidate reached" in (report.error or "")


def test_gate_accepts_a_matching_candidate(tmp_path):
    cfg = Config(vision_provider="mock", verify_threshold=7.0, candidates_per_query=6)
    item = make_item()
    ledger = ledger_mod.Ledger(path=tmp_path / "l.json", used={})

    report = select.select_for_item(cfg, [MockSource()], item, ledger, tmp_path, min_seconds=3.0)

    assert item.chosen is not None
    assert item.chosen.relevance >= 7.0
    assert report.checked >= 1


def test_already_used_clips_are_excluded(tmp_path):
    cfg = Config(vision_provider="mock", verify_threshold=7.0, candidates_per_query=6)
    ledger = ledger_mod.Ledger(path=tmp_path / "l.json", used={})

    first = make_item()
    select.select_for_item(cfg, [MockSource()], first, ledger, tmp_path, min_seconds=3.0)
    assert first.chosen is not None
    ledger.record(first.chosen, video="v1", item_name=first.name)

    second = make_item()
    report = select.select_for_item(cfg, [MockSource()], second, ledger, tmp_path, min_seconds=3.0)

    assert report.already_used >= 1
    assert second.chosen is not None
    assert second.chosen.key != first.chosen.key


def test_max_vision_checks_caps_spend(tmp_path):
    cfg = Config(
        vision_provider="mock",
        verify_threshold=11.0,  # unreachable, so every candidate is checked
        candidates_per_query=20,
        max_vision_checks=3,
    )
    item = make_item()
    ledger = ledger_mod.Ledger(path=tmp_path / "l.json", used={})
    report = select.select_for_item(cfg, [MockSource()], item, ledger, tmp_path, min_seconds=3.0)
    assert report.checked <= 3


# --------------------------------------------------------------------------
# ledger
# --------------------------------------------------------------------------


def test_ledger_round_trips(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = ledger_mod.Ledger.load(path)
    candidate = make_candidate()
    assert not ledger.has_used(candidate)
    ledger.record(candidate, video="v1", item_name="Logger")
    ledger.save()

    reloaded = ledger_mod.Ledger.load(path)
    assert reloaded.has_used(candidate)
    assert len(reloaded) == 1


def test_ledger_refuses_to_silently_reset_on_corruption(tmp_path):
    path = tmp_path / "ledger.json"
    path.write_text("{not json")
    with pytest.raises(ValueError, match="corrupt"):
        ledger_mod.Ledger.load(path)


def test_credits_separates_required_attribution(tmp_path):
    dest = tmp_path / "CREDITS.md"
    ledger_mod.write_credits(
        dest,
        [
            make_candidate(source_id="a", attribution_required=True, attribution_text="By A"),
            make_candidate(source_id="b", attribution_required=False, attribution_text="By B"),
        ],
        "A Title",
    )
    text = dest.read_text()
    assert "Attribution REQUIRED" in text
    assert text.index("By A") < text.index("Attribution not required")


# --------------------------------------------------------------------------
# vision gate scoring
# --------------------------------------------------------------------------


def test_mock_vision_scores_a_match_high():
    item = make_item(search_terms=["felling a tree"])
    score, _ = verify._mock_vision(make_candidate(true_subject="felling a tree"), item)
    assert score >= 7


def test_mock_vision_scores_a_decoy_low():
    item = make_item(search_terms=["felling a tree"])
    score, _ = verify._mock_vision(make_candidate(true_subject="a parking lot"), item)
    assert score < 7


def test_parse_score_reads_clean_json():
    assert verify._parse_score('{"score": 8, "shows": "a roof"}')[0] == 8.0


def test_parse_score_strips_a_markdown_fence():
    assert verify._parse_score('```json\n{"score": 3, "shows": "x"}\n```')[0] == 3.0


def test_parse_score_falls_back_to_a_bare_number():
    assert verify._parse_score("I would rate this a 9 out of 10.")[0] == 9.0


def test_parse_score_raises_when_there_is_no_number():
    with pytest.raises(ValueError):
        verify._parse_score("I cannot tell what this is.")


# --------------------------------------------------------------------------
# sources
# --------------------------------------------------------------------------


def test_mock_source_returns_a_mix_of_right_and_wrong():
    results = MockSource().search("felling a tree", 9)
    subjects = {c.true_subject for c in results}
    assert "felling a tree" in subjects
    assert len(subjects) > 1, "mock source should also return decoys"


def test_unknown_source_is_rejected():
    with pytest.raises(SourceError, match="Unknown clip source"):
        build_sources(["definitely-not-a-source"])


def test_no_sources_is_rejected():
    with pytest.raises(SourceError, match="No clip sources"):
        build_sources([])


def test_pexels_requires_a_key(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    with pytest.raises(SourceError, match="PEXELS_API_KEY"):
        build_sources(["pexels"])


# --------------------------------------------------------------------------
# cards
# --------------------------------------------------------------------------


def test_item_card_is_full_frame_with_transparent_top(tmp_path):
    from PIL import Image

    dest = tmp_path / "card.png"
    cards.render_item_card(3, "Commercial fisherman", "Freezing water, 20 hour shifts", dest)
    img = Image.open(dest)
    assert img.size == (WIDTH, HEIGHT)
    # The top of the frame must stay clear -- that is where the subject is.
    assert img.getpixel((WIDTH // 2, 40))[3] == 0


def test_long_names_are_shrunk_to_fit(tmp_path):
    dest = tmp_path / "card.png"
    cards.render_item_card(10, "A Really Very Long Job Title That Should Shrink", "s", dest)
    assert dest.exists()


# --------------------------------------------------------------------------
# end to end
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_end_to_end_rank_run(tmp_path):
    from vidauto.ranking import pipeline as rank_pipeline

    cfg = Config(
        text_provider="mock",
        clip_sources=["mock"],
        vision_provider="mock",
        rank_items=3,
        seconds_per_item=2.0,
        candidates_per_query=6,
        out_dir=tmp_path,
        ledger_path=tmp_path / "ledger.json",
    )
    result = rank_pipeline.run_once(cfg, seed=1)

    assert result.video is not None and result.video.exists()
    assert result.resolved == result.requested

    proc = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-i", str(result.video)], capture_output=True, text=True
    )
    assert f"{WIDTH}x{HEIGHT}" in proc.stderr
    assert "Video: h264" in proc.stderr

    manifest = json.loads((result.directory / "manifest.json").read_text())
    assert len(manifest["sourcing"]) == result.requested
    # The sourcing trace is the thing you read when a video comes out with
    # gaps; it must record the search/check counts, not just the outcome.
    assert all("searched" in row and "vision_checks" in row for row in manifest["sourcing"])

    assert (result.directory / "CREDITS.md").exists()
    assert (result.directory / "POSTING.md").exists()


@pytest.mark.slow
def test_second_run_reuses_no_clips(tmp_path):
    from vidauto.ranking import pipeline as rank_pipeline

    cfg = Config(
        text_provider="mock",
        clip_sources=["mock"],
        vision_provider="mock",
        rank_items=3,
        seconds_per_item=2.0,
        candidates_per_query=12,
        out_dir=tmp_path,
        ledger_path=tmp_path / "ledger.json",
    )
    first = rank_pipeline.run_once(cfg, seed=1)
    second = rank_pipeline.run_once(cfg, seed=1)  # same seed -> same list

    used_first = {i.chosen.key for i in first.ranking.items if i.chosen}
    used_second = {i.chosen.key for i in second.ranking.items if i.chosen}
    assert used_first and used_second
    assert not (used_first & used_second), "second run reused a clip from the first"


@pytest.mark.slow
def test_unresolved_items_are_flagged_not_filled(tmp_path):
    """With an unreachable threshold, nothing resolves and no video is made."""
    from vidauto.ranking import pipeline as rank_pipeline

    cfg = Config(
        text_provider="mock",
        clip_sources=["mock"],
        vision_provider="mock",
        verify_threshold=10.0,
        rank_items=3,
        seconds_per_item=2.0,
        out_dir=tmp_path,
        ledger_path=tmp_path / "ledger.json",
    )
    result = rank_pipeline.run_once(cfg, seed=1)
    assert result.resolved == 0
    assert result.video is None
    assert "Unresolved items" in (result.directory / "POSTING.md").read_text()
