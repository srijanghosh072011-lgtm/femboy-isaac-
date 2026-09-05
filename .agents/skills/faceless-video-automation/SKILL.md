---
name: faceless-video-automation
description: Master prompt pack for faceless short-form video automation pipelines — Sora 2 hyperreal "Real or Not?" clips, archival-footage documentaries with AI narration, and editing-first clip repurposing. Use when building or running an automated content pipeline for YouTube Shorts, TikTok, or Instagram Reels: generating topics, writing Sora shot prompts, scripting narrated documentaries, routing scenes between stock/archival footage and AI generation, producing edit decision lists (cuts, captions, zooms, SFX), and applying retention and AI-disclosure rules before posting.
---

# FACELESS VIDEO AUTOMATION — MASTER PROMPT PACK

You are the prompt engineer and pipeline architect for a faceless, no-personal-brand
short-form video operation. Output is 9:16 vertical, posted natively to YouTube Shorts,
TikTok, and Instagram Reels.

Every prompt in this skill is designed to be **called by an automation** (Make, n8n,
Zapier, or a custom script) and to return **strict JSON** so the next step can parse it
without a human in the loop.

---

## 0. PICK THE MODEL FIRST

Three production models. They differ almost entirely in **where the cost sits**. Choose
before writing anything.

| | Model A — Full Generation | Model B — Archival + Narration | Model C — Editing-First |
|---|---|---|---|
| **Footage** | 100% Sora 2 generated | Public domain / stock + small generated B-roll | Real source video you own or licensed |
| **Cost driver** | Sora credits per generated second — scales linearly with volume | Flat stock subscription; credits only on `generate` scenes | Transcription + render compute only |
| **Voice** | None (ambient audio only) | TTS narration every scene | Source audio, captions carry the edit |
| **Best for** | Hyperreal "wonder" clips, pure short-form | Long-form YouTube (mid-roll RPM) + vertical teasers | High-volume repurposing of an existing library |
| **Main risk** | Credit burn at scale | Footage licensing on non-public-domain sources | Copyright — you must own or license the source |

**Default recommendation for a new channel at scale: Model B**, with Model C as the
repurposing layer on top of it. Model A is the highest-cost-per-post of the three —
run it when the generated visual *is* the product, not as a footage substitute.

---

# MODEL A — FULL SORA 2 GENERATION

### The niche: "Real or Not?" hyperreal wonder clips

Faceless, no dialogue, no brand tie-in. Each clip is a physically real-looking moment
that is borderline unbelievable — a wave freezing mid-air, a bee's wing in impossible
slow-motion, a droplet reshaping into a perfect sphere, a desert flash-flood pattern,
metal cooling into crystal.

Why this niche and not a personality- or news-driven one:

- **The realism is the hook.** Viewers commenting *"wait is this real??"* is the
  retention mechanic. The ambiguity does the virality work — you don't have to
  manufacture it on top of the visual.
- **No real people, no historical claims** → no deepfake or consent problem, no
  misinformation exposure.
- **Infinite topic supply** — physics, weather, geology, macro biology, food science,
  space. It never runs dry, which is what an always-on automation needs.
- **No voiceover or script** → fewer pipeline stages, fewer failure points.
- **Loop-friendly by nature** (satisfying, cyclical motion) → strong completion and
  rewatch rate, which every platform weights heavily.

Format: 15–25 second clips, 9:16.

### A1. Topic generator prompt (LLM step)

Call this each run to produce one fresh structured topic. It emits JSON so the
automation can feed `sora_prompt` straight into the generation step.

```
You generate ideas for a faceless short-video channel called "Real or Not?"
The channel shows hyperrealistic 15-25 second clips of real-world physics,
nature, or material phenomena that look almost too strange to be real,
but are scientifically plausible or literally true.

Rules:
- No real people, celebrities, or brands
- No historical events or news
- No text that could be seen as misinformation
- Must be visually simple enough to render in one continuous shot
- Must have a "wow, is that real?" quality in the first second

Output ONLY valid JSON in this exact shape:
{
  "topic": "short topic name",
  "science_fact": "1-2 sentence true fact that makes the clip meaningful",
  "hook_caption": "on-screen text, under 8 words, curiosity-gap phrasing",
  "closing_caption": "one line comment-bait question, e.g. 'Real or AI? 👇'",
  "sora_prompt": "a full cinematic video prompt (see template below)"
}
```

### A2. Master Sora 2 video prompt template

Sora responds best to prompts written like a **cinematographer's shot description** —
not "make an AI video of X."

**Never put these words in the prompt itself:** "AI-generated", "digital art",
"render", "CGI", "animation". They push Sora toward a stylized, less photoreal look —
the exact opposite of what this niche needs.

```
[SUBJECT] in extreme macro/close-up, [SPECIFIC ACTION happening in real time].
Shot on a [CAMERA TYPE, e.g. RED cinema camera / iPhone 17 Pro macro lens],
[LENS BEHAVIOR: shallow depth of field, slow push-in / static tripod shot].
Lighting: [natural window light / golden hour / overcast diffuse — pick one, be specific].
Environment: [minimal, uncluttered background, e.g. plain concrete surface,
out-of-focus greenery].
Motion: [describe the physical motion precisely — droplet falling, wing beating,
crystal forming — as if narrating real footage, not an effect].
The first frame must already show the phenomenon mid-action — no slow build-up.
Duration: 18 seconds. Aspect ratio: 9:16. Natural ambient audio only
(no music, no voiceover, no on-screen text).
```

Slot-filling rules that keep output photoreal:

- **One subject, one camera move.** Two moving elements or a compound camera move is
  where realism collapses and credits get wasted on a reroll.
- **Name a real camera and a real lens behavior.** Specificity anchors the physics.
- **Pick exactly one lighting condition** and commit to it. Mixed lighting reads fake.
- **Keep the background empty and out of focus.** Clutter is where artifacts hide.
- **Describe motion as physics, not as an effect** — "the crown of water rises, holds,
  collapses back", never "a cool water effect".
- **No baked-in text.** Captions are a separate overlay step; text rendered inside the
  video can't be edited, localized, or A/B tested.

### A3. Filled-in examples

1. *"A single water droplet in extreme macro, suspended mid-splash forming a perfect
   crown shape as it hits a still black surface, shot on a high-speed cinema camera
   with shallow depth of field and a static tripod shot. Lighting: single hard backlight
   creating a rim-lit silhouette on the crown of water. Environment: pure black
   background, no distractions. Motion: droplet impacts and the crown rises, holds for
   a beat, then collapses back into the surface in ultra slow motion. First frame
   already mid-splash. Duration: 18 seconds. Aspect ratio 9:16. Natural ambient audio
   only."*

2. *"A honeybee's wing in extreme macro slow motion, membrane catching afternoon
   sunlight and showing iridescent color shifts as it beats, shot on a macro cinema
   lens with shallow depth of field and a slow push-in. Lighting: golden hour side
   light. Environment: soft out-of-focus garden greenery behind. Motion: wing beats are
   already mid-cycle in frame one, slowing to reveal individual beats. Duration: 15
   seconds. Aspect ratio 9:16. Natural ambient audio only."*

3. *"Molten metal cooling on a dark steel surface in macro close-up, orange glow fading
   to black as crystalline patterns form and spread across the surface in real time,
   shot on a static macro rig. Lighting: the metal itself is the only light source,
   gradually dimming. Environment: plain dark workshop surface, out of focus tools
   barely visible in background. Motion: crystallization pattern is already spreading
   in frame one. Duration: 20 seconds. Aspect ratio 9:16. Natural ambient audio only."*

---

# MODEL B — ARCHIVAL FOOTAGE + AI NARRATION

The model most faceless documentary/history channels actually run: **real or archival
footage + AI-written script + AI voiceover**, with generated B-roll filling only the
gaps nothing exists for.

This is cheaper for a structural reason, not a marginal one: generation bills per
generated second, while a stock or public-domain library costs the same whether you cut
one video or two hundred.

### Flagship pick: history / "Hollywood-level" documentaries

- **Public-domain footage is genuinely free and legally clean:** NASA (all public
  domain), Library of Congress, the National Archives, the Prelinger Archives
  (public-domain newsreels and industrial films on the Internet Archive), plus
  Pexels / Videvo / Pixabay for general B-roll.
- **Infinite, evergreen topic supply** that doesn't go stale like news.
- **Splits naturally into two products:** one long-form YouTube video (higher RPM,
  mid-roll ads) and several 25–30s vertical teasers that drive traffic back to it.

**Niches to skip until licensing is sorted:**

- *Police bodycam* — real identifiable people, and the footage is usually owned by the
  department or the news outlet that obtained it.
- *Gaming compilations* — gameplay is the publisher's copyrighted work.
- *Real estate* — listing photos and video need the owner's or brokerage's permission;
  scraping them is not a gray area at automation scale.

All three are doable with an actual license or a worked-out fair-use position. Neither
is something to improvise inside an automation.

### B1. Script generator prompt (core step)

Each scene decides for itself whether it needs footage that already exists (free) or
generated B-roll (costs credits). That single field is what keeps the pipeline cheap.

```
You are a scriptwriter for a faceless YouTube documentary channel in the
"Hollywood-Level History" niche. Write a tightly-paced narrated script on
the given topic, optimized for retention on YouTube long-form AND for
extracting short vertical clips later.

Rules:
- Open with a single-sentence hook that states the most shocking/surprising
  fact in the story — no scene-setting before it
- Write in short, spoken-style sentences (this will be read aloud by TTS)
- Break the script into scenes of 8-15 seconds each
- For each scene, specify whether real footage likely exists (archival
  footage, public domain film, NASA/gov footage) or whether it needs
  AI-generated B-roll, and if generated, keep the shot simple (one subject,
  one camera move) to minimize render cost
- Total runtime: 8-12 minutes

Output ONLY valid JSON in this shape:
{
  "title": "video title",
  "hook_line": "first sentence spoken, under 20 words",
  "scenes": [
    {
      "scene_number": 1,
      "narration": "exact line(s) of narration for this scene",
      "footage_type": "archival" or "generate",
      "footage_search_query": "search term for stock/archival library (only if archival)",
      "sora_prompt": "cinematic shot description (only if footage_type is generate)",
      "duration_seconds": 10
    }
  ],
  "clip_worthy_scene_numbers": [list of 2-3 scene numbers that would work best as standalone short-form teasers]
}
```

### B2. Short-clip extractor prompt (repurposing step)

Feed it the script JSON from B1. It turns the best scenes into standalone vertical posts.

```
You will receive a documentary script as JSON, including a list of
"clip_worthy_scene_numbers". For each of those scenes, rewrite it as a
standalone 25-30 second vertical short that makes sense without the rest
of the video.

Rules:
- Add one new opening line that re-hooks a viewer with zero context
  ("You won't believe what happened next in [topic]...")
- Keep the original narration for the scene itself
- End with a line that drives to the full video ("Full story linked/on the channel")
- Write an on-screen caption (under 8 words) for the first frame

Output ONLY valid JSON:
{
  "clips": [
    {
      "source_scene_number": 1,
      "narration": "full rewritten narration for this standalone clip",
      "on_screen_caption": "hook text for frame 1",
      "duration_seconds": 28
    }
  ]
}
```

### B3. Automation wiring

- **The cost branch:** route each scene on `footage_type` — `archival` goes to a stock
  or archival search API (Pexels API, Storyblocks, Internet Archive), `generate` goes to
  a Sora call. This single branch is the whole savings.
- **TTS:** feed each scene's `narration` field straight to ElevenLabs (or your TTS) per
  scene, so one bad line is a one-scene re-render, not a whole-video redo.
- **Disclosure:** if *any* scene used generated footage, the finished video is
  AI-generated content for labeling purposes. See §Compliance.

---

# MODEL C — EDITING-FIRST CLIP AUTOMATION

No generation, minimal or no AI narration. Take a real source video, trim it hard, and
put the automation effort into **the edit**: cuts, captions, zooms, sound design. This
is the Opus Clip / Submagic model, except you build the decision layer yourself so the
output doesn't sound AI-generic.

**Sourcing rule, before anything else:** the footage has to be something you have rights
to — your own footage, licensed stock (Storyblocks, Envato), or public domain. Pulling
other creators' videos off YouTube or TikTok without a license is a copyright-strike
risk the moment you're posting at automation scale. It is not a one-off gray area.

### C1. Edit director prompt

Feed it a timestamped transcript of the source clip (most transcription tools emit one)
plus the niche. It returns a full edit decision list that Shotstack, JSON2Video, the
CapCut automation API, or a custom ffmpeg pipeline executes directly.

```
You are an edit director for short-form social clips in the "{niche}" niche.
You will receive a timestamped transcript of a source video. Your job is
to turn it into one tightly-edited 25-40 second vertical clip that feels
genuinely funny and human-made — NOT like generic AI-captioned content.

Avoid entirely:
- Hype words: "Wow," "Incredible," "You won't believe," "Insane"
- A caption on literally every line — let some moments breathe with no text
- Rhetorical questions as a crutch ("But what happened next?")
- Captions that just repeat the spoken audio verbatim

Do instead:
- Write captions like a sharp friend texting a reaction, not a marketing caption —
  dry, understated, or a one-line joke that lands ON the visual punchline frame
- Use a callback: reference something from early in the clip again near the end
- Vary pacing — some cuts fast (under 1 sec), some held for a beat of silence
- Time captions to land a beat AFTER the joke/action, like a punchline, not before it

Identify:
1. The single best 25-40 second window in the source (in/out timestamps)
2. Every cut point within that window (jump cuts, not just trim)
3. Caption text + timing for each beat that needs one (not every beat)
4. Zoom/punch-in moments (on a reaction, a key word, or a reveal)
5. Sound effect cues (whoosh on hard cuts, a sting on the punchline,
   record-scratch on a twist — use sparingly, 2-4 total, not on every cut)
6. One on-screen hook caption for the very first frame, under 8 words

Output ONLY valid JSON:
{
  "source_in": "00:00:00",
  "source_out": "00:00:00",
  "hook_caption": "text for frame 1",
  "cuts": [ {"start": "00:00:00", "end": "00:00:00"} ],
  "captions": [ {"time": "00:00:00", "text": "...", "style": "beat/reaction/callback"} ],
  "zooms": [ {"time": "00:00:00", "target": "what to punch in on"} ],
  "sfx": [ {"time": "00:00:00", "type": "whoosh/sting/record-scratch"} ]
}
```

---

# RETENTION CHECKLIST — apply before every post

Universal across all three models.

- [ ] **First 1.5 seconds show the subject already in motion.** No slow build-up, no
      logo, no title card.
- [ ] **Runtime 15–22s** for pure short-form, 25–40s for a narrated or edited clip.
- [ ] **Hook caption is an overlay, not baked into the video** — under 8 words,
      curiosity-gap phrasing. Keeping it separate lets you A/B test and localize it.
- [ ] **Ends on comment bait** ("Real or AI? 👇", "Full story on the channel").
- [ ] **Loop-friendly:** last frame visually rhymes with the first, so autoplay replays
      feel seamless.
- [ ] **9:16, no visible watermark**, posted natively to each platform (not a link out).
- [ ] **AI disclosure toggle set** wherever generated footage was used. See below.

---

# COMPLIANCE — label it, don't skip this

**The rule that matters:** platforms require an AI-content label specifically when the
content shows realistic-appearing scenes a viewer could reasonably believe are real.
That is precisely the appeal of Model A and of any generated B-roll in Model B, so it
will trigger the requirement — this is not an edge case you can argue your way out of.

Build the disclosure into the **posting step of the SOP as a fixed field**, not as a
per-video judgment call:

- YouTube Studio — "Altered or synthetic content" checkbox
- TikTok — AI-generated content label
- Instagram — "Made with AI" tag

Labeling does not kill the "is this real" engagement. People still argue about it in the
comments on a labeled clip. What it protects you from is the enforcement side.

**Enforcement specifics change often — verify against current platform policy before
relying on any number.** As reported at the time this pack was written: TikTok pays AI
content at the same rate as traditional content when disclosure conditions are met, but
videos caught by automatic AI detection without a label lose Creator Fund earnings for a
period even if labeled retroactively; YouTube pays disclosed AI content a comparable RPM
to non-AI content in the same niche, but mass-produced or recycled AI video is subject to
escalating Partner Program penalties up to permanent removal. Treat these as directionally
true and re-check the live policy pages before scaling.

---

# POSTING LAYER

- **Multi-account, multi-platform posting:** Blotato, Metricool, or Publer handle native
  posting to several accounts at once. Zapier/Make can hit each platform's API directly
  if you'd rather stay inside an existing stack.
- **Vary something per account.** Posting a byte-identical file across many owned
  accounts with zero variation is the pattern platform "mass-produced / inauthentic
  content" rules are written to catch. A different hook caption, thumbnail, or opening
  frame per account meaningfully reduces that risk for near-zero extra pipeline cost.
- **Post natively at 9:16 with no visible watermark** on every platform. A re-uploaded
  file carrying another platform's watermark is downranked on all of them.
