"""`vidauto check` -- work out what this machine and this account can actually do.

Written for the case where you do not know what access you have. It never
spends money: it verifies the key and lists what the account can see, but does
not generate an image. The one paid check is opt-in via `--probe-image`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests

from . import ffmpeg
from .config import Config, find_font

OK = "ok"
WARN = "warn"
FAIL = "fail"

MARK = {OK: "[ ok ]", WARN: "[warn]", FAIL: "[fail]"}


@dataclass
class Check:
    status: str
    label: str
    detail: str


def _check_ffmpeg() -> Check:
    try:
        binary = ffmpeg.ffmpeg_bin()
    except ffmpeg.FFmpegError as exc:
        return Check(FAIL, "ffmpeg", str(exc))
    if os.environ.get("FFMPEG_BIN"):
        source = "FFMPEG_BIN"
    elif "imageio_ffmpeg" in binary:
        source = "bundled static build"
    else:
        source = "PATH"
    return Check(OK, "ffmpeg", f"{binary} (via {source})")


def _check_font() -> Check:
    try:
        return Check(OK, "caption font", find_font())
    except FileNotFoundError as exc:
        return Check(FAIL, "caption font", str(exc))


def _check_key(cfg: Config) -> Check:
    if not cfg.openai_api_key:
        return Check(
            WARN,
            "OPENAI_API_KEY",
            "not set -- the pipeline will run in mock mode. Note: a ChatGPT Plus/Pro "
            "subscription does NOT include API access; API keys are billed separately "
            "at platform.openai.com.",
        )
    key = cfg.openai_api_key
    masked = f"{key[:7]}...{key[-4:]}" if len(key) > 14 else "set"
    return Check(OK, "OPENAI_API_KEY", f"present ({masked})")


def _check_api(cfg: Config) -> list[Check]:
    if not cfg.openai_api_key:
        return []
    url = f"{cfg.openai_base_url.rstrip('/')}/models"
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {cfg.openai_api_key}"},
            timeout=30,
        )
    except requests.RequestException as exc:
        return [Check(FAIL, "API reachability", f"could not reach {url}: {exc}")]

    if resp.status_code == 401:
        return [Check(FAIL, "API auth", "401 -- the key is invalid, revoked, or from a different org")]
    if resp.status_code != 200:
        return [Check(FAIL, "API auth", f"HTTP {resp.status_code}: {resp.text[:200]}")]

    ids = sorted(m.get("id", "") for m in resp.json().get("data", []))
    out = [Check(OK, "API auth", f"key works, {len(ids)} models visible")]

    image_models = [m for m in ids if m.startswith("gpt-image")]
    if image_models:
        preferred = cfg.image_model
        status = OK if preferred in image_models else WARN
        detail = ", ".join(image_models)
        if preferred not in image_models:
            detail += f" -- but IMAGE_MODEL={preferred!r} is not among them"
        out.append(Check(status, "image models", detail))
    else:
        out.append(
            Check(
                FAIL,
                "image models",
                "no gpt-image-* model visible to this key. Image generation may not be "
                "enabled for this account, or the org needs verification.",
            )
        )

    video_models = [m for m in ids if m.startswith("sora")]
    if video_models:
        out.append(
            Check(
                WARN,
                "video models",
                f"{', '.join(video_models)} visible, but the Videos API and all sora-* "
                "models shut down 2026-09-24 with no replacement. Do not build on them.",
            )
        )
    else:
        out.append(
            Check(
                OK,
                "video models",
                "none visible, as expected -- OpenAI has no video generation model. "
                "This pipeline generates stills and animates them instead.",
            )
        )
    return out


def _check_text_model(cfg: Config) -> Check:
    if cfg.text_provider == "mock":
        return Check(
            OK,
            "topic generation",
            "mock -- using the built-in topic bank, no API calls, no cost",
        )
    return Check(OK, "topic generation", f"openai, model {cfg.text_model}")


def probe_image(cfg: Config) -> Check:
    """Actually generate one image. This costs money. Opt-in only."""
    from pathlib import Path
    import tempfile

    from . import providers

    if cfg.image_provider != "openai":
        return Check(WARN, "image probe", "skipped -- IMAGE_PROVIDER is not 'openai'")
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "probe.png"
        try:
            providers.generate_image(cfg, "A plain grey concrete wall, flat lighting.", dest, 0)
        except Exception as exc:  # noqa: BLE001 - surfacing any failure verbatim is the point
            return Check(FAIL, "image probe", str(exc))
        return Check(OK, "image probe", f"generated {dest.stat().st_size:,} bytes with {cfg.image_model}")


def run_checks(cfg: Config, with_probe: bool = False) -> tuple[list[Check], bool]:
    checks = [_check_ffmpeg(), _check_font(), _check_key(cfg), _check_text_model(cfg)]
    checks += _check_api(cfg)
    if with_probe:
        checks.append(probe_image(cfg))
    blocking = any(c.status == FAIL for c in checks[:2])
    return checks, not blocking
