"""Tests for the pipeline.

The end-to-end test runs the real ffmpeg path with mock providers. It is slow
(tens of seconds) but it is the only test that would have caught any of the
three bugs found while building this: the xfade frame-rate error, the missing
drawtext filter, and the uncapped bitrate. Unit tests on the filter strings
would have passed through all of them.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vidauto import captions, motion, topics  # noqa: E402
from vidauto.config import HEIGHT, WIDTH, Config  # noqa: E402
from vidauto.ffmpeg import escape_drawtext, ffmpeg_bin  # noqa: E402


# --------------------------------------------------------------------------
# topics
# --------------------------------------------------------------------------


def test_offline_topic_is_deterministic_per_seed():
    assert topics.offline_topic(7).topic == topics.offline_topic(7).topic


def test_offline_topics_all_pass_their_own_warnings():
    # The built-in bank is what the mock path ships; if it violates the
    # checklist, every demo run emits warnings and they stop meaning anything.
    for topic in topics.OFFLINE_TOPICS:
        assert topic.warnings() == [], f"{topic.topic}: {topic.warnings()}"


def test_parse_topic_json_strips_markdown_fence():
    payload = {
        "topic": "t",
        "science_fact": "f",
        "hook_caption": "h",
        "closing_caption": "c",
        "image_prompt": "p",
    }
    raw = "```json\n" + json.dumps(payload) + "\n```"
    assert topics.parse_topic_json(raw).topic == "t"


def test_parse_topic_json_rejects_missing_fields():
    with pytest.raises(ValueError, match="missing required field"):
        topics.parse_topic_json('{"topic": "t"}')


def test_parse_topic_json_rejects_non_json():
    with pytest.raises(ValueError, match="did not return valid JSON"):
        topics.parse_topic_json("here you go!")


def test_warnings_flag_stylisation_words():
    topic = topics.Topic("t", "f", "hook", "c", "A 3D render of a cliff")
    assert any("render" in w for w in topic.warnings())


def test_warnings_flag_overlong_hook():
    topic = topics.Topic("t", "f", " ".join(["word"] * 12), "c", "A photograph of a cliff")
    assert any("under 8" in w for w in topic.warnings())


def test_shot_prompts_keeps_establishing_frame_verbatim():
    topic = topics.offline_topic(1)
    prompts = topics.shot_prompts(topic, 4, seed=1)
    assert len(prompts) == 4
    # Segment 0 is the frame the hook caption sits on; it must be exactly the
    # prompt the topic generator tuned, not a reframed variant.
    assert prompts[0] == topic.image_prompt
    assert len({p for p in prompts}) == 4


def test_shot_prompts_rejects_zero_segments():
    with pytest.raises(ValueError):
        topics.shot_prompts(topics.offline_topic(1), 0)


# --------------------------------------------------------------------------
# captions
# --------------------------------------------------------------------------


def test_caption_png_is_full_frame_and_transparent(tmp_path):
    from PIL import Image

    dest = tmp_path / "cap.png"
    captions.render_caption_png(
        captions.Caption("A caption that wraps onto two lines", 0, 2, 68, 0.2), dest
    )
    img = Image.open(dest)
    assert img.size == (WIDTH, HEIGHT)
    assert img.mode == "RGBA"
    # Corners must stay transparent or the overlay would black out the frame.
    assert img.getpixel((5, 5))[3] == 0


def test_caption_wrapping_respects_frame_width():
    from PIL import ImageFont

    from vidauto.config import find_font

    font = ImageFont.truetype(find_font(), 68)
    max_width = int(WIDTH * captions.TEXT_WIDTH_FRACTION) - 2 * captions.PLATE_PAD_X
    lines = captions._wrap("A deliberately long hook caption that must wrap", font, max_width)
    assert len(lines) > 1
    for line in lines:
        bbox = font.getbbox(line)
        assert bbox[2] - bbox[0] <= max_width


def test_empty_caption_raises(tmp_path):
    with pytest.raises(ValueError):
        captions.render_caption_png(captions.Caption("   ", 0, 2, 68, 0.2), tmp_path / "x.png")


def test_standard_captions_timing_is_inside_the_clip():
    result = captions.standard_captions("hook", "Real or AI?", 17.25)
    assert len(result) == 2
    for caption in result:
        assert 0 <= caption.start < caption.end <= 17.25


def test_standard_captions_drops_closing_on_a_very_short_clip():
    assert len(captions.standard_captions("hook", "Real or AI?", 3.0)) == 1


# --------------------------------------------------------------------------
# motion
# --------------------------------------------------------------------------


def test_moves_alternate_between_neighbours():
    names = [motion.move_for_index(i).name for i in range(len(motion.MOVES) + 2)]
    assert all(a != b for a, b in zip(names, names[1:]))


def test_every_move_has_expressions():
    for move in motion.MOVES:
        z, x, y = motion._expressions(move.name, 135)
        assert z and x and y


def test_unknown_move_raises():
    with pytest.raises(ValueError):
        motion._expressions("barrel_roll", 135)


def test_expressions_never_divide_by_zero_on_a_two_frame_segment():
    for move in motion.MOVES:
        for expr in motion._expressions(move.name, 2):
            assert "/0" not in expr


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------


def test_config_rejects_openai_provider_without_a_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = Config(image_provider="openai", openai_api_key=None)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        cfg.validate()


def test_config_rejects_absurd_runtime():
    with pytest.raises(ValueError, match="over a minute"):
        Config(segments=40, seconds_per_segment=10).validate()


def test_config_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown IMAGE_PROVIDER"):
        Config(image_provider="sora").validate()


def test_escape_drawtext_escapes_backslash_first():
    assert escape_drawtext("a\\b:c") == "a\\\\b\\:c"


# --------------------------------------------------------------------------
# end to end
# --------------------------------------------------------------------------


def _stream_info(path: Path) -> str:
    proc = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
    )
    return proc.stderr


@pytest.mark.slow
def test_end_to_end_mock_run_produces_a_valid_vertical_video(tmp_path):
    from vidauto import pipeline

    cfg = Config(
        image_provider="mock",
        text_provider="mock",
        segments=2,
        seconds_per_segment=3.0,
        out_dir=tmp_path,
    )
    result = pipeline.run_once(cfg, seed=1)

    assert result.video.exists()
    assert result.video.stat().st_size > 10_000

    info = _stream_info(result.video)
    assert f"{WIDTH}x{HEIGHT}" in info, info
    assert "Video: h264" in info, info
    # A silent audio track is muxed on purpose; several platforms reject a
    # video with no audio stream at all.
    assert "Audio: aac" in info, info

    manifest = json.loads((result.directory / "manifest.json").read_text())
    assert manifest["ai_generated_imagery"] is False
    assert len(manifest["prompts"]) == 2

    checklist = (result.directory / "POSTING.md").read_text()
    assert "MOCK image provider" in checklist

    # Intermediates are cleaned up by default.
    assert not (result.directory / "segments").exists()
    assert not list(result.directory.glob("caption_*.png"))


@pytest.mark.slow
def test_disclosure_checklist_demands_labels_when_imagery_is_generated(tmp_path):
    from vidauto import pipeline

    cfg = Config(image_provider="mock", text_provider="mock", out_dir=tmp_path)
    topic = topics.offline_topic(1)
    run_dir = tmp_path / "r"
    run_dir.mkdir()

    cfg.image_provider = "openai"  # after the fact, to exercise the branch
    pipeline._write_disclosure(run_dir, topic, cfg)
    text = (run_dir / "POSTING.md").read_text()
    assert "Altered or synthetic content" in text
    assert "Made with AI" in text
