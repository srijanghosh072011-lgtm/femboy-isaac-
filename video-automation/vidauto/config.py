"""Configuration, loaded from the environment with sane defaults.

Everything here is overridable by env var so the pipeline can run unattended
in a scheduler without a config file, but the defaults are chosen so that
`python -m vidauto run` works with no configuration at all (mock providers).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# 9:16 vertical, the only aspect ratio this pipeline targets.
WIDTH = 1080
HEIGHT = 1920
FPS = 30

# OpenAI's portrait image size. It is 2:3, which is *wider* than 9:16 once
# scaled to our height -- that surplus width is what gives the pan room in
# motion.py. Do not "fix" this to a 9:16 image size; the slack is deliberate.
IMAGE_SIZE = "1024x1536"

CAPTION_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def find_font() -> str:
    """Return a usable bold font path, or raise with a clear remedy."""
    override = os.environ.get("CAPTION_FONT")
    if override:
        if not Path(override).exists():
            raise FileNotFoundError(f"CAPTION_FONT={override!r} does not exist")
        return override
    for candidate in CAPTION_FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError(
        "No caption font found. Install DejaVu or Liberation fonts "
        "(apt install fonts-dejavu-core), or set CAPTION_FONT to a .ttf path."
    )


@dataclass
class Config:
    # --- providers -------------------------------------------------------
    # "openai" uses the real Images API; "mock" renders procedural stand-ins
    # with ffmpeg so the whole pipeline runs with zero credentials.
    image_provider: str = field(default_factory=lambda: os.environ.get("IMAGE_PROVIDER", "mock"))
    text_provider: str = field(default_factory=lambda: os.environ.get("TEXT_PROVIDER", "mock"))

    openai_api_key: str | None = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY"))
    openai_base_url: str = field(
        default_factory=lambda: os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    # gpt-image-2 is the model behind ChatGPT Images 2.0. gpt-image-1 is
    # deprecating 2026-10-23, so it is not offered as a default.
    image_model: str = field(default_factory=lambda: os.environ.get("IMAGE_MODEL", "gpt-image-2"))
    image_quality: str = field(default_factory=lambda: os.environ.get("IMAGE_QUALITY", "medium"))
    text_model: str = field(default_factory=lambda: os.environ.get("TEXT_MODEL", "gpt-5"))

    # --- shape of the output --------------------------------------------
    segments: int = field(default_factory=lambda: _env_int("SEGMENTS", 4))
    seconds_per_segment: float = field(
        default_factory=lambda: float(os.environ.get("SECONDS_PER_SEGMENT", "4.5"))
    )
    burn_captions: bool = field(default_factory=lambda: _env_flag("BURN_CAPTIONS", True))
    loop_shape: bool = field(default_factory=lambda: _env_flag("LOOP_SHAPE", True))

    # --- io ---------------------------------------------------------------
    out_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("OUT_DIR", "runs")).expanduser()
    )

    @property
    def total_seconds(self) -> float:
        return self.segments * self.seconds_per_segment

    def validate(self) -> None:
        if self.segments < 1:
            raise ValueError("SEGMENTS must be at least 1")
        if self.seconds_per_segment <= 0:
            raise ValueError("SECONDS_PER_SEGMENT must be positive")
        # The retention checklist calls for 15-22s. We warn rather than fail:
        # a deliberate 30s cut is a legitimate choice, a 90s one is a mistake.
        if self.total_seconds > 60:
            raise ValueError(
                f"Total runtime {self.total_seconds:.0f}s is over a minute; "
                "that is outside what this pipeline is shaped for. "
                "Lower SEGMENTS or SECONDS_PER_SEGMENT."
            )
        if self.image_provider not in {"mock", "openai"}:
            raise ValueError(f"Unknown IMAGE_PROVIDER {self.image_provider!r} (mock|openai)")
        if self.text_provider not in {"mock", "openai"}:
            raise ValueError(f"Unknown TEXT_PROVIDER {self.text_provider!r} (mock|openai)")
        needs_key = "openai" in {self.image_provider, self.text_provider}
        if needs_key and not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set but a provider is set to 'openai'. "
                "Note this is a platform.openai.com API key -- a ChatGPT Plus/Pro "
                "subscription does not include one. Run `python -m vidauto check` for details."
            )


def load() -> Config:
    cfg = Config()
    cfg.validate()
    return cfg
