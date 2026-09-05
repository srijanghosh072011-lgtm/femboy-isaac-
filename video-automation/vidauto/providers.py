"""Text and image providers.

Two implementations of each: a `mock` that needs no credentials and still
produces real output, and an `openai` one that calls the live API.

The mock path is not a stub. It generates genuinely different images per
segment and a genuine topic, so `python -m vidauto run` with an empty
environment produces a finished, watchable MP4. That is what makes the
pipeline testable before anyone has decided which vendor to pay.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path

import requests

from . import ffmpeg, topics
from .config import Config, IMAGE_SIZE

TIMEOUT = 180
RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4


class ProviderError(RuntimeError):
    pass


def _post(cfg: Config, path: str, payload: dict) -> dict:
    """POST to the OpenAI API with backoff on transient failures."""
    url = f"{cfg.openai_base_url.rstrip('/')}{path}"
    headers = {
        "Authorization": f"Bearer {cfg.openai_api_key}",
        "Content-Type": "application/json",
    }
    last_error = ""
    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        except requests.RequestException as exc:
            last_error = f"network error: {exc}"
        else:
            if resp.status_code == 200:
                return resp.json()
            body = resp.text[:400]
            last_error = f"HTTP {resp.status_code}: {body}"
            # Auth, permission and validation errors will not fix themselves.
            if resp.status_code not in RETRY_STATUS:
                raise ProviderError(f"{path} failed -- {last_error}")
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep(2**attempt)
    raise ProviderError(f"{path} failed after {MAX_ATTEMPTS} attempts -- {last_error}")


# --------------------------------------------------------------------------
# text
# --------------------------------------------------------------------------


def generate_topic(cfg: Config, seed: int | None = None) -> topics.Topic:
    if cfg.text_provider == "mock":
        return topics.offline_topic(seed)

    payload = {
        "model": cfg.text_model,
        "messages": [
            {"role": "system", "content": topics.TOPIC_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Generate one topic. Return only the JSON object.",
            },
        ],
    }
    data = _post(cfg, "/chat/completions", payload)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise ProviderError(f"Unexpected chat response shape: {json.dumps(data)[:400]}") from exc
    return topics.parse_topic_json(content)


# --------------------------------------------------------------------------
# images
# --------------------------------------------------------------------------


def _mock_image(prompt: str, dest: Path, index: int) -> None:
    """Render a deterministic stand-in image with ffmpeg.

    Derived from a hash of the prompt so each segment looks distinct and the
    same prompt always yields the same frame -- which makes the mock path
    usable in tests as well as demos.
    """
    digest = hashlib.sha256(prompt.encode()).digest()
    hue = digest[0] / 255.0
    seed = int.from_bytes(digest[1:5], "big") % 100000
    w, h = (int(x) for x in IMAGE_SIZE.split("x"))

    # A multi-stop gradient with light grain: cheap, deterministic, and visually
    # distinct enough that motion and cuts are clearly readable in the output.
    #
    # The grain is kept low on purpose. Heavy noise is incompressible, and an
    # x264 encode of pure noise produces a file several times larger than the
    # real photographic footage this stands in for -- which makes the mock a
    # misleading proxy for delivery size.
    filt = (
        f"gradients=s={w}x{h}"
        f":c0=0x{digest[2]:02x}{digest[3]:02x}{digest[4]:02x}"
        f":c1=0x{digest[5]:02x}{digest[6]:02x}{digest[7]:02x}"
        f":c2=0x{digest[8]:02x}{digest[9]:02x}{digest[10]:02x}"
        f":x0={seed % w}:y0={seed % h}:x1={(seed * 7) % w}:y1={(seed * 3) % h}"
        f":nb_colors=3:seed={seed},"
        f"noise=alls={6 + index * 2}:allf=u,"
        # Blurring the grain turns TV static into something closer to an
        # out-of-focus photograph, which both looks less alarming in a demo
        # and compresses like the real footage it stands in for.
        f"gblur=sigma=1.6,"
        f"hue=h={hue * 360:.1f}:s=0.85,"
        f"vignette=PI/5"
    )
    ffmpeg.run(
        ["-f", "lavfi", "-i", filt, "-frames:v", "1", str(dest)],
        description=f"rendering mock image {index}",
    )


def _openai_image(cfg: Config, prompt: str, dest: Path, index: int) -> None:
    payload = {
        "model": cfg.image_model,
        "prompt": prompt,
        "size": IMAGE_SIZE,
        "quality": cfg.image_quality,
        "n": 1,
    }
    data = _post(cfg, "/images/generations", payload)
    try:
        item = data["data"][0]
    except (KeyError, IndexError) as exc:
        raise ProviderError(f"Unexpected image response shape: {json.dumps(data)[:400]}") from exc

    if item.get("b64_json"):
        dest.write_bytes(base64.b64decode(item["b64_json"]))
        return
    if item.get("url"):
        resp = requests.get(item["url"], timeout=TIMEOUT)
        if resp.status_code != 200:
            raise ProviderError(f"Could not download generated image {index}: HTTP {resp.status_code}")
        dest.write_bytes(resp.content)
        return
    raise ProviderError(f"Image response for segment {index} contained neither b64_json nor url")


def generate_image(cfg: Config, prompt: str, dest: Path, index: int) -> None:
    """Generate one still image to `dest`. Skips work if it already exists."""
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if cfg.image_provider == "mock":
        _mock_image(prompt, dest, index)
    else:
        _openai_image(cfg, prompt, dest, index)
    if not dest.exists() or dest.stat().st_size == 0:
        raise ProviderError(f"Image provider produced no output for segment {index}")
