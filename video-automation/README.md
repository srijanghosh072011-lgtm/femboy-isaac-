# vidauto

A faceless vertical-video pipeline. Generates a still image per shot, animates
each one with a slow camera move, assembles them into a loop-shaped 9:16 clip
with burned-in captions, and writes the posting checklist beside it.

```
python3 -m pip install -r requirements.txt
python3 -m vidauto check     # what can this machine and this key do?
python3 -m vidauto run       # produces a finished MP4, no credentials needed
```

The second command works on a clean machine with an empty environment. It uses
the mock providers, so it costs nothing and produces procedural placeholder
imagery — but it exercises the entire real pipeline and hands you a valid
1080x1920 H.264 file you can play.

---

## Why this generates stills instead of video

The original plan was Sora. Sora is gone:

- **sora.com and the Sora apps shut down on 26 April 2026.**
- **The Videos API and every `sora-*` model shut down on 24 September 2026**,
  announced 24 March 2026.
- **OpenAI's deprecation table lists no replacement**, and OpenAI has no other
  video generation model. ChatGPT has no video generation feature any more.

So "use ChatGPT's video generation" is not an option that exists. What does
exist, and is actively maintained, is **ChatGPT's image generation**
(`gpt-image-2`, shipped 21 April 2026, the model behind ChatGPT Images 2.0),
available through the Images API.

This pipeline is built on that: generate photographs, move a camera over them.
For a scrolling viewer, a slow linear push-in across a photorealistic still
reads as footage. It is also roughly two orders of magnitude cheaper than video
generation was.

> Verify these dates yourself before making decisions on them. They come from
> OpenAI's deprecation and help-centre pages, but this repo's author could not
> reach those pages directly and relied on search summaries of them.

### The honest limitation

A still cannot show a physics **event**. The original prompt pack's examples —
a droplet crown collapsing, a wing mid-beat, metal crystallising — all depend on
watching the physics happen, and there is no physics in a photograph. Feeding
those prompts to an image model gets you a frozen, slightly wrong-looking
moment, which reads as an AI artifact rather than as wonder.

So `topics.py` points the same "is this real?" hook at subjects that hold
still: **places, formations, materials, and objects** that look impossible but
are photographable. Salt flats cracked into hexagons. Basalt columns stepping
into the sea. A brine pool with a shoreline, underwater. The viewer reaction is
the same in kind, and it survives being a photograph.

If you specifically want motion events, you need a real video model, and it
will not be an OpenAI one. `providers.py` is the only file that would change.

---

## What it does

```
topic ─► one image prompt per shot ─► N still images
                                          │
                                          ▼
                              slow camera move on each  (motion.py)
                                          │
                                          ▼
                    concat ─► tail/head crossfade ─► captions ─► H.264
                                          │
                                          ▼
                        runs/<timestamp>-<slug>/final.mp4
                                            POSTING.md
                                            manifest.json
```

Defaults produce 4 shots x 4.5s, crossfaded down to **17.2 seconds** — inside
the 15–22s completion-rate band.

**A run is a directory, and every step skips work whose output already
exists.** Image generation is the only expensive step, so a crash during
assembly must never re-buy the images. Re-run the same command to resume.

Each run also writes `POSTING.md`: the AI-disclosure toggles, the caption copy,
and the retention checklist. Disclosure is a fixed item rather than a judgement
call, because this content is realistic-looking scenes, which is exactly the
condition the platform rules name.

---

## Going live

Set a key and flip the providers:

```bash
cp .env.example .env      # then edit it
python3 -m vidauto check  # confirms the key works and lists your image models
```

**A ChatGPT Plus/Pro subscription does not include API access.** They are
separate products with separate billing. API keys come from
platform.openai.com. `check` will tell you which you have.

### Cost

Roughly **$0.12–$0.25 per video** at 4 shots, medium quality, portrait — versus
about **$5.40** for 18 seconds of Sora 2 Pro when it existed. Cheap enough that
the render is no longer the thing you optimise.

Quality tiers move this a lot (`IMAGE_QUALITY=low` is several times cheaper,
`high` several times dearer). Confirm current per-image prices before planning
volume; they change.

### Verification status

| Path | Status |
|---|---|
| Whole pipeline on mock providers | **Verified** — 24 tests pass, including two end-to-end ffmpeg runs |
| ffmpeg motion, concat, loop, captions, encode | **Verified** — output confirmed 1080x1920 H.264 + AAC, 17.2s |
| OpenAI Images / Chat adapters | **Written, not executed** — no API key was available here |

The live adapters follow the documented request shapes but have never made a
real call. Run `python3 -m vidauto check --probe-image` as your first paid
action: it generates exactly one image and reports what happened.

---

## Configuration

Every setting is an environment variable, so a scheduler needs no config file.
CLI flags override for one run.

| Variable | Default | Notes |
|---|---|---|
| `IMAGE_PROVIDER` | `mock` | `mock` or `openai` |
| `TEXT_PROVIDER` | `mock` | `mock` uses the built-in topic bank |
| `OPENAI_API_KEY` | — | Required once a provider is `openai` |
| `IMAGE_MODEL` | `gpt-image-2` | `gpt-image-1` deprecates 2026-10-23 |
| `IMAGE_QUALITY` | `medium` | `low` / `medium` / `high` |
| `TEXT_MODEL` | `gpt-5` | Any chat-completions model |
| `SEGMENTS` | `4` | Shots per video |
| `SECONDS_PER_SEGMENT` | `4.5` | Before loop shaping |
| `LOOP_SHAPE` | `true` | Crossfade tail into head |
| `BURN_CAPTIONS` | `true` | |
| `OUT_DIR` | `runs` | |
| `FFMPEG_BIN` | — | Overrides discovery |
| `CAPTION_FONT` | — | Path to a bold `.ttf` |

```bash
python3 -m vidauto run --count 5              # batch; one failure will not stop the rest
python3 -m vidauto run --segments 3 --seconds 5
python3 -m vidauto run --seed 42              # deterministic
python3 -m vidauto topic --show-prompts       # tune prompts without rendering
```

---

## What it deliberately does not do

**It does not post anything.** It writes a file and a checklist. Automated
posting is a much larger project than it looks: YouTube needs OAuth and has a
low default upload quota, TikTok's Content Posting API requires an approved
developer app (unapproved apps can only post privately), and Instagram needs a
Business account through the Graph API. Each is an application-and-waiting
process. Paying Blotato, Metricool or Publer to own that step is usually the
better trade.

**It does not vary output per account.** Posting a byte-identical file to
several owned accounts is what platform "mass-produced content" rules are
written to catch. Vary at least the hook caption per account.

---

## Implementation notes

Three things here look like over-engineering and are not. Each was a bug first.

- **`motion.py` upscales 3x before `zoompan`.** zoompan quantises its crop
  window to integer pixels; on a slow zoom over a 1:1 source it snaps a pixel
  at a time and visibly judders.
- **`captions.py` renders text with Pillow, not `drawtext`.** drawtext needs an
  ffmpeg built against libfreetype. The portable static builds — including the
  one pip installs — are not, so a drawtext pipeline works on one machine and
  dies on the next. Pillow also gives real font metrics, so wrapping is
  measured rather than estimated.
- **`assemble.py` re-stamps `fps` after `trim`.** `trim` leaves the frame rate
  undeclared and `xfade` refuses a variable rate.

`ffmpeg.py` finds a binary from `FFMPEG_BIN`, then `PATH`, then the static build
bundled with `imageio-ffmpeg`. Nothing calls `ffprobe`: every duration in the
pipeline is one we chose, so there is nothing to probe, and that keeps the
pip-installed ffmpeg fully supported.

## Tests

```bash
python3 -m pip install pytest
python3 -m pytest -q          # 24 tests, ~35s
python3 -m pytest -q -m "not slow"
```

The two end-to-end tests run real ffmpeg. They are slow and they are the ones
that matter: all three bugs above passed unit tests on the filter strings.
