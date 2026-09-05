"""The vision gate.

Stock search always returns something. For a query like "commercial fisherman"
it will happily return a stock photo of a man in a boat, a fish market, or a
seafood dinner, ranked by keyword overlap and popularity rather than by whether
the clip depicts the thing. Taking result #1 on faith is why automated ranking
videos look like slop.

So every candidate is checked: pull a frame, ask a vision model whether it
depicts the item, keep only what clears a threshold. This is the single most
important step in the pipeline and it is cheap -- one small image per
candidate, a few hundred tokens of reply.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import requests

from .. import ffmpeg
from ..config import Config
from .models import Candidate, RankItem

TIMEOUT = 90

PROMPT = """\
You are checking whether a video frame is usable as illustration for one entry \
in a ranking video.

The entry is: "{item}"

Rate how well this frame depicts that subject, from 0 to 10:
  0-3  = wrong subject, or so ambiguous a viewer could not tell what it shows
  4-6  = related but indirect (an associated object, aftermath, or a symbol of it)
  7-10 = clearly and recognisably shows the subject

Judge only what is visible. Do not give credit for what the clip might show \
later, and do not assume context that is not in the frame.

Reply with ONLY a JSON object, no markdown fence:
{{"score": <0-10>, "shows": "<3-6 words on what is actually visible>"}}"""


def extract_frame(clip: Path, dest: Path, at: float = 1.0) -> Path:
    """Pull a single frame for inspection.

    Taken a second in rather than at 0: many stock clips open on a fade, and a
    black frame scores zero regardless of what the clip contains.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run(
        [
            "-ss", f"{at:.2f}", "-i", str(clip),
            "-frames:v", "1",
            # Downscale hard: the model does not need more, and image tokens
            # are the entire cost of this step.
            "-vf", "scale=512:-2",
            str(dest),
        ],
        description=f"extracting a verification frame from {clip.name}",
    )
    return dest


def _parse_score(raw: str) -> tuple[float, str]:
    text = raw.strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.splitlines() if not l.strip().startswith("```")).strip()
    try:
        data = json.loads(text)
        return float(data["score"]), str(data.get("shows", ""))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        # Models occasionally answer in prose despite instructions. A bare
        # number in the reply is better than discarding the whole judgement.
        match = re.search(r"\b(10|\d)\b", text)
        if match:
            return float(match.group(1)), text[:60]
        raise ValueError(f"Could not read a score from vision reply: {raw[:200]}")


def _openai_vision(cfg: Config, frame: Path, item: str) -> tuple[float, str]:
    b64 = base64.b64encode(frame.read_bytes()).decode()
    payload = {
        "model": cfg.vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT.format(item=item)},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"},
                    },
                ],
            }
        ],
    }
    resp = requests.post(
        f"{cfg.openai_base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {cfg.openai_api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"vision check failed: HTTP {resp.status_code} {resp.text[:200]}")
    return _parse_score(resp.json()["choices"][0]["message"]["content"])


def _anthropic_vision(cfg: Config, frame: Path, item: str) -> tuple[float, str]:
    b64 = base64.b64encode(frame.read_bytes()).decode()
    payload = {
        "model": cfg.vision_model,
        "max_tokens": 200,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                    },
                    {"type": "text", "text": PROMPT.format(item=item)},
                ],
            }
        ],
    }
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": cfg.anthropic_api_key or "",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"vision check failed: HTTP {resp.status_code} {resp.text[:200]}")
    return _parse_score(resp.json()["content"][0]["text"])


def _mock_vision(candidate: Candidate, item: RankItem) -> tuple[float, str]:
    """Simulate a vision judgement from the mock source's ground truth.

    The mock source labels each clip with the query that produced it, so a
    genuine hit is one whose ground truth is one of this item's search terms;
    anything else came from the decoy pool.

    Explicitly a simulation. It proves the gate is wired in and that wrong
    candidates are rejected and replaced -- it says nothing about how well a
    real vision model performs, which cannot be established offline.
    """
    truth = (candidate.true_subject or "").strip().lower()
    if not truth:
        return 5.0, "unknown (no ground truth)"

    terms = {t.strip().lower() for t in item.search_terms}
    if truth in terms or truth == item.name.strip().lower():
        return 9.0, f"clearly {truth}"

    # Shares a distinctive word with the item without being it -- the
    # "related but indirect" band a real gate is meant to catch.
    item_words = {w for w in item.name.lower().split() if len(w) > 3}
    if item_words & set(truth.split()):
        return 5.0, f"partially related: {truth}"
    return 1.0, f"wrong subject: {truth}"


def fetch_preview(candidate: Candidate, dest: Path) -> Path | None:
    """Download the source's own preview still, if it offers one."""
    if not candidate.preview_url:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    try:
        resp = requests.get(candidate.preview_url, timeout=TIMEOUT)
    except requests.RequestException:
        return None
    if resp.status_code != 200 or not resp.content:
        return None
    dest.write_bytes(resp.content)
    return dest


def score_candidate(
    cfg: Config,
    candidate: Candidate,
    clip: Path | None,
    item: RankItem,
    work_dir: Path,
) -> tuple[float, str]:
    """Score one candidate. `clip` may be None if the source offers a preview."""
    if cfg.vision_provider == "mock":
        return _mock_vision(candidate, item)

    # Prefer the hosted preview: rejecting a candidate should not cost a video
    # download, and most candidates are rejected.
    frame = fetch_preview(candidate, work_dir / f"{candidate.source_id}_preview.jpg")
    if frame is None:
        if clip is None:
            raise ValueError(
                f"Candidate {candidate.key} has no preview and no downloaded clip to inspect"
            )
        frame = extract_frame(clip, work_dir / f"{candidate.source_id}.jpg")

    if cfg.vision_provider == "anthropic":
        return _anthropic_vision(cfg, frame, item.name)
    return _openai_vision(cfg, frame, item.name)
