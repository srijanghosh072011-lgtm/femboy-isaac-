"""Topic generation and shot-prompt construction.

Niche note, and it is the single most important design decision in this file:

The original "Real or Not?" pack was written for a video model and its examples
are all *motion events* -- a droplet crown collapsing, a wing mid-beat, metal
crystallising. A still image with a camera move cannot sell any of those. The
"is this real?" reaction to a physics event comes from watching the physics
happen, and there is no physics in a photograph.

What a still absolutely can sell is a *place, object, or scene* that looks
photographic and shouldn't exist. That reaction is identical in kind -- the
viewer interrogates the frame -- and it survives a slow push-in, because the
image was never claiming to move in the first place.

So the niche here is the same hook mechanic pointed at subjects that hold still.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, asdict

# Subject families that work photographically. Each is a thing you could
# plausibly have photographed, not an event you would have had to film.
SUBJECT_FAMILIES = (
    "an impossible-looking natural landscape that could plausibly exist on Earth",
    "an extreme macro texture of a natural material, unrecognisable at first glance",
    "an isolated geological formation with improbable but physically real structure",
    "a deep-space or planetary-surface scene of the kind a probe would return",
    "a man-made structure in an environment that makes its scale hard to read",
    "a cross-section or interior of a natural object rarely seen from that angle",
)

CAMERA_LOOKS = (
    "shot on a medium-format camera, 80mm lens, deep focus",
    "shot on a full-frame camera, 35mm lens, natural perspective",
    "shot on a telephoto lens from a distance, compressed perspective",
    "shot on a macro lens, shallow depth of field, single plane of focus",
    "shot from the air, straight down, flat orthographic framing",
)

LIGHTING = (
    "overcast diffuse daylight, no hard shadows",
    "low golden-hour sun raking across the surface",
    "flat blue-hour light just after sunset",
    "single hard directional light against deep shadow",
    "bright high-altitude midday sun, thin clean air",
)


@dataclass
class Topic:
    """One video's worth of creative direction."""

    topic: str
    science_fact: str
    hook_caption: str
    closing_caption: str
    image_prompt: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Topic":
        missing = {f for f in ("topic", "science_fact", "hook_caption", "closing_caption", "image_prompt")} - set(data)
        if missing:
            raise ValueError(f"Topic is missing required field(s): {', '.join(sorted(missing))}")
        return cls(
            topic=str(data["topic"]).strip(),
            science_fact=str(data["science_fact"]).strip(),
            hook_caption=str(data["hook_caption"]).strip(),
            closing_caption=str(data["closing_caption"]).strip(),
            image_prompt=str(data["image_prompt"]).strip(),
        )

    def warnings(self) -> list[str]:
        """Soft checks from the retention checklist. Advisory, never fatal."""
        out = []
        if len(self.hook_caption.split()) > 8:
            out.append(f"hook_caption is {len(self.hook_caption.split())} words; the checklist says under 8")
        if len(self.closing_caption.split()) > 10:
            out.append("closing_caption is long for comment bait; keep it to a short question")
        for banned in ("AI-generated", "digital art", "render", "CGI", "3D render", "illustration"):
            if banned.lower() in self.image_prompt.lower():
                out.append(
                    f"image_prompt contains {banned!r}, which pushes the model toward a "
                    "stylised look; describe it as a photograph instead"
                )
        return out


# The prompt sent to the text model. Mirrors the pack's topic generator, but
# asks for a photographic subject rather than a filmed event.
TOPIC_SYSTEM_PROMPT = """\
You generate ideas for a faceless short-video channel called "Real or Not?"
Each post is a single hyperreal PHOTOGRAPH held on screen with a slow camera
move, of a real-world place, object, material, or natural formation that looks
almost too strange to be real, but is scientifically plausible or literally true.

Rules:
- The subject must be photographable and STILL. No motion events (no splashes,
  no wingbeats, no explosions) -- a photograph cannot show those.
- No real people, celebrities, or brands
- No real named places, historical events, or news
- No text anywhere in the image
- Must read as a photograph, never as an illustration or a render
- Must have a "wow, is that real?" quality in the first second

Output ONLY valid JSON in this exact shape, with no markdown fence:
{
  "topic": "short topic name",
  "science_fact": "1-2 sentence true fact that makes the image meaningful",
  "hook_caption": "on-screen text, under 8 words, curiosity-gap phrasing",
  "closing_caption": "one line comment-bait question, e.g. 'Real or AI?.'",
  "image_prompt": "a full photographic description: subject, camera and lens, lighting, environment, and what makes the composition strange. One paragraph, no camera movement, no text in frame."
}"""


# Used when TEXT_PROVIDER=mock. These are real, usable topics -- the offline
# path produces a genuine video, not a placeholder with lorem ipsum.
OFFLINE_TOPICS = (
    Topic(
        topic="Salt polygon flats",
        science_fact=(
            "As groundwater evaporates through a salt crust, the crust cracks into "
            "near-perfect hexagons metres across, driven by convection cells in the brine below."
        ),
        hook_caption="Nature does not use straight lines",
        closing_caption="Real or AI?",
        image_prompt=(
            "A vast salt flat cracked into enormous near-perfect hexagonal tiles stretching to "
            "the horizon, each ridge raised a few centimetres above the pale surface, shot from "
            "the air straight down with flat orthographic framing on a medium-format camera. "
            "Lighting: bright high-altitude midday sun, thin clean air, hard-edged shadows in "
            "every crack. Environment: nothing but salt to every edge of the frame, no horizon, "
            "no objects for scale. The geometry is so regular it reads as manufactured."
        ),
    ),
    Topic(
        topic="Basalt column coastline",
        science_fact=(
            "Slowly cooling lava contracts and fractures into hexagonal columns; the slower the "
            "cooling, the more regular the geometry becomes."
        ),
        hook_caption="This coastline was not built",
        closing_caption="Real or AI?",
        image_prompt=(
            "A sea cliff made entirely of tightly packed vertical hexagonal stone columns of "
            "varying heights, stepping down into dark water like a flight of stairs built for "
            "nothing, shot on a full-frame camera with a 35mm lens and natural perspective. "
            "Lighting: flat blue-hour light just after sunset, no hard shadows. Environment: "
            "cold grey sea, low cloud, no boats or buildings anywhere in frame."
        ),
    ),
    Topic(
        topic="Bismuth crystal terraces",
        science_fact=(
            "Bismuth crystallises in stepped rectangular spirals, and the rainbow colours are a "
            "thin oxide layer refracting light, not pigment."
        ),
        hook_caption="A metal that grows in staircases",
        closing_caption="Real or AI?",
        image_prompt=(
            "An extreme macro of a bismuth crystal: concentric rectangular terraces spiralling "
            "inward like an aerial view of a stepped city, surfaces shifting between magenta, "
            "cyan and gold, shot on a macro lens with shallow depth of field and a single plane "
            "of focus. Lighting: single hard directional light against deep shadow. Environment: "
            "plain matte black surface, nothing else in frame."
        ),
    ),
    Topic(
        topic="Underwater brine pool",
        science_fact=(
            "Dense salty water can pool on the seafloor and stay separate from the ocean above "
            "it, forming a lake with a shoreline and visible waves -- underwater."
        ),
        hook_caption="A lake at the bottom of the sea",
        closing_caption="Real or AI?",
        image_prompt=(
            "A pool of denser water resting on the seafloor with a clearly defined shoreline and "
            "a visible rippled surface, mussels crusting its rim, the water above it perfectly "
            "clear, shot on a full-frame camera with a 35mm lens from a low angle. Lighting: "
            "single hard directional light from above against deep shadow, as from a submersible. "
            "Environment: dark sediment plain, nothing else visible beyond the light's falloff."
        ),
    ),
)


def offline_topic(seed: int | None = None) -> Topic:
    rng = random.Random(seed)
    return rng.choice(OFFLINE_TOPICS)


def parse_topic_json(raw: str) -> Topic:
    """Parse a model response into a Topic, tolerating a markdown fence."""
    text = raw.strip()
    if text.startswith("```"):
        lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model did not return valid JSON: {exc}\n---\n{raw[:600]}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")
    return Topic.from_dict(data)


def shot_prompts(topic: Topic, segments: int, seed: int | None = None) -> list[str]:
    """Derive one image prompt per segment.

    Each segment is a different framing of the same subject rather than a
    different subject: the clip has to read as one continuous place, or the
    cuts feel like a slideshow instead of a camera exploring something real.
    """
    if segments < 1:
        raise ValueError("segments must be at least 1")
    rng = random.Random(seed)
    base = topic.image_prompt.rstrip(". ")

    # Segment 0 is always the establishing frame exactly as written -- it is the
    # one the hook caption sits on, and it is what the topic prompt was tuned for.
    prompts = [topic.image_prompt]

    framings = [
        "Same subject and location, framed tighter on the most structurally strange detail",
        "Same subject and location, a wider frame showing more of the surrounding terrain",
        "Same subject and location, viewed from a lower angle close to the surface",
        "Same subject and location, an oblique view across the structure rather than square on",
        "Same subject and location, framed on the boundary where the structure meets what surrounds it",
    ]
    rng.shuffle(framings)

    for i in range(1, segments):
        framing = framings[(i - 1) % len(framings)]
        camera = rng.choice(CAMERA_LOOKS)
        prompts.append(
            f"{framing}. {base}. Consistent lighting, materials and colour with the "
            f"establishing frame; {camera}. No text in frame."
        )
    return prompts
