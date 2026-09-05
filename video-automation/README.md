# vidauto

Two faceless vertical-video pipelines that share an assembly engine.

```
python3 -m pip install -r requirements.txt
python3 -m vidauto check     # what can this machine and this key do?

python3 -m vidauto rank      # ranking / countdown video from sourced clips
python3 -m vidauto run       # generated stills, animated with camera moves
```

| | `rank` | `run` |
|---|---|---|
| Footage | Real licensed stock, found and verified | Generated stills, animated |
| The hard part | **Finding a clip that actually shows the thing** | Prompting for photoreal output |
| Cost driver | Vision checks (cents) | Image generation (~$0.12–0.25/video) |
| Output | ~19s countdown, number cards burned in | ~17s loop-shaped wonder clip |

Both commands work on a clean machine with an empty environment, using mock
providers: no credentials, no cost, and a real playable 1080x1920 MP4 at the
end. That is the point — the whole pipeline is exercisable before you decide
which vendor to pay.

---

# `rank` — ranking / countdown videos

The editing here is a for-loop: number card, clip, cut, repeat. **Clip sourcing
is the entire problem**, and it has a specific failure mode worth naming.

## The specificity gap

> Ranking videos are about specific things. Stock libraries are indexed by
> generic concepts.

Search any stock API for a list item and it returns *something*, ranked by
keyword overlap and popularity rather than by whether the clip depicts the
thing. Ask for "commercial fisherman" and you may get a seafood dinner. Take
result #1 on faith across ten items and you have a finished video that is
confidently wrong — which is exactly what automated ranking channels look like.

**Search recall is not the problem. Verification is.**

## How this pipeline handles it

```
topic ─► ranked list, each item with 3-4 search variants
      ─► fan out: every source x every variant  ─► candidate pool
      ─► free filters first: resolution, duration, already-used
      ─► VISION GATE: hosted preview ─► "does this show <item>? 0-10"
      ─► first candidate over threshold wins  (early stop)
      ─► no winner? leave the item UNRESOLVED. never fall back.
      ─► ledger the clip so no future video reuses it
```

Four decisions carry most of the weight:

- **The search terms describe visible action, not the noun.** "logger" returns
  posed portraits; "felling a tree with a chainsaw" returns the shot. Each item
  carries several phrasings and the pipeline tries all of them.
- **The gate checks the source's hosted preview image**, not a downloaded
  video, so rejecting a candidate costs one small image — and most candidates
  are rejected. Only the winner is downloaded.
- **Free filters run before any model is consulted**, and checks stop as soon
  as something clears the bar. `MAX_VISION_CHECKS` caps the spend per item.
- **There is no "best of a bad bunch" fallback.** An item with no acceptable
  clip is left out and flagged loudly in `POSTING.md`. Nine right items beat
  ten with one obvious lie in it. This is tested directly.

## What you get

```
runs/<timestamp>-rank-<slug>/
  final.mp4       1080x1920, number/name/stat cards burned in
  CREDITS.md      per-clip licensing, attribution-required split out first
  POSTING.md      unresolved items, licensing, disclosure, checklist
  manifest.json   full sourcing trace: found / checked / rejected, per item
clip-ledger.json  every clip ever used  <- back this up
```

The **sourcing trace** in `manifest.json` is what you read when a video comes
out with gaps: how many candidates each item found, how many the gate checked,
how many it rejected and why.

## Licensing

Attribution obligations are carried per clip, not assumed per source, because
they genuinely differ — Pexels and Pixabay need none, Wikimedia Commons is
mostly CC-BY/CC-BY-SA and does. `CREDITS.md` puts anything requiring
attribution in its own section at the top; paste it into the description.

Two pieces of widely-repeated advice this repo deliberately does **not**
follow, because both are wrong:

- *"Clips under ~10 seconds are safe."* There is no safe-length rule in
  copyright. Content ID matches fingerprints at any usable length.
- *"Diversify sources so detection doesn't catch the copyrighted ones."* That
  is evading detection of infringement, not licensing. It also fails — claims
  land retroactively.

The workable answer is upstream: rank things whose footage is genuinely
licensable. Everyday life, jobs, food, nature, science and engineering are well
covered by free stock. Movies, games, sport and TV are not, at any scale.

## Adding a source

Subclass `Source` in `ranking/sources.py` with `search()` and `download()`,
then add it to `build_sources`. Wikimedia Commons, NASA, Openverse, Pond5 and
Envato all fit this shape. Set `attribution_required` honestly — the credits
file is generated from it.

---

# `run` — generated stills, animated

Where `rank` finds real footage, `run` makes its own: one generated still per
shot, each animated with a slow camera move, assembled into a loop-shaped clip.

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
| Both pipelines on mock providers | **Verified** — 58 tests pass, including five end-to-end ffmpeg runs |
| ffmpeg motion, cards, concat, loop, captions, encode | **Verified** — output confirmed 1080x1920 H.264 + AAC |
| Gate / ledger / no-fallback behaviour | **Verified** — tested directly, including across two runs |
| OpenAI Images, Chat, Vision adapters | **Written, not executed** — no API key was available here |
| Pexels / Pixabay response parsing | **Verified against the documented shapes** — fixture tests in `tests/test_source_parsing.py` |
| Pexels / Pixabay live calls | **Never executed** — both hosts are blocked by the build environment's egress policy |

The network adapters follow each API's documented request shape but have never
made a real call, so expect one round of fixes on first contact. Run
`python3 -m vidauto check --probe-image` as your first paid action: it
generates exactly one image and reports what happened.

For `rank`, start with `python3 -m vidauto check`. It runs a real search
against every configured clip source and reports what came back, which costs
nothing — stock search is free. Then:

```bash
CLIP_SOURCES=pexels VISION_PROVIDER=mock python3 -m vidauto rank
```

That exercises live search and download while the gate stays free, isolating
the source adapters from the vision one. Flip `VISION_PROVIDER` once you know
the source layer works.

The response *parsing* is pinned by fixture tests built from each API's
published documentation, so the silent failure — every field reading None and
every candidate quietly discarded — is covered. What those tests cannot catch
is an auth or endpoint mistake; only a live call does that.

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

Ranking-specific settings (`CLIP_SOURCES`, `VISION_PROVIDER`,
`VERIFY_THRESHOLD`, `MAX_VISION_CHECKS`, `CANDIDATES_PER_QUERY`, `RANK_ITEMS`,
`SECONDS_PER_ITEM`, `LEDGER_PATH`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`) are
documented in `.env.example`.

```bash
python3 -m vidauto rank --sources pexels,pixabay --items 10
python3 -m vidauto rank --threshold 6      # looser gate, more fills, more risk
python3 -m vidauto rank --keep-intermediates   # keep downloaded clips to inspect
```

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
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q                 # 58 tests, ~9 min
python3 -m pytest -q -m "not slow"   # ~5s, skips the ffmpeg runs
```

The end-to-end tests run real ffmpeg and dominate that runtime. They are also
the ones that matter: every bug found while building this — the xfade frame
rate, the missing drawtext filter, the vertical-preference tie — survived unit
tests on the surrounding logic.
