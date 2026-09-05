"""Generating the ranked list.

The search terms are the part that matters. Stock libraries index footage by
what is visibly happening, not by the noun a list uses: "logger" returns
posed portraits, "felling a tree with a chainsaw" returns the shot you want.
So every item carries several phrasings, weighted toward *actions and scenes*
rather than job titles or category names, and the pipeline tries all of them.

This is also why the everyday/jobs/food category automates well. Its items are
concepts that stock libraries are actually organised around, so the gap between
"what I asked for" and "what exists" is small. A ranking of specific named
entities would need entity-specific archives instead.
"""

from __future__ import annotations

import json
import random

from .models import RankItem, RankList

LIST_SYSTEM_PROMPT = """\
You write ranked lists for a faceless short-form countdown channel covering \
everyday life, food, jobs and human interest.

Rules:
- Exactly {count} items, ordered as a countdown: rank {count} first, rank 1 last
- Rank 1 must be the strongest, most surprising entry -- it is the payoff
- Every item needs ONE concrete stat or fact, under 10 words, that justifies its place
- Items must be generic concepts, not specific named people, brands or companies
- No claims that need fact-checking against news or current events

For each item, give 3-4 stock-footage search terms. This is the important part:
- Describe the VISIBLE ACTION or SCENE, not the job title or category name
- Good: "welder sparks close up", "crab boat deck in rough sea"
- Bad: "welder", "dangerous job", "fisherman"
- Vary them, so that if one returns nothing another still hits

Output ONLY valid JSON, no markdown fence:
{{
  "title": "video title",
  "hook_caption": "on-screen text for frame 1, under 8 words",
  "closing_caption": "one line comment bait, e.g. 'What did I miss?'",
  "items": [
    {{"rank": {count}, "name": "item name", "stat": "the one fact", "search_terms": ["...", "...", "..."]}}
  ]
}}"""


OFFLINE_LISTS = (
    RankList(
        title="Most Dangerous Jobs",
        hook_caption="Number 1 is not what you think",
        closing_caption="What did I miss?",
        items=[
            RankItem(5, "Roofer", "51 deaths per 100,000 workers", [
                "roofer working on steep roof", "laying roof shingles high up", "construction worker on rooftop"]),
            RankItem(4, "Refuse collector", "Struck by vehicles most often", [
                "garbage truck collection street", "refuse collector lifting bins", "waste truck early morning"]),
            RankItem(3, "Commercial fisherman", "Freezing water, 20 hour shifts", [
                "crab boat deck rough sea", "fishing trawler hauling nets", "fisherman in storm at sea"]),
            RankItem(2, "Logger", "Falling timber, remote locations", [
                "felling tree with chainsaw", "logging truck forest road", "lumberjack cutting timber"]),
            RankItem(1, "Bush pilot", "Landing on gravel and ice", [
                "small plane landing gravel strip", "bush plane snow landing", "cockpit small aircraft mountains"]),
        ],
    ),
    RankList(
        title="Foods That Take The Longest To Make",
        hook_caption="Number 1 takes years",
        closing_caption="Would you wait for it?",
        items=[
            RankItem(5, "Sourdough bread", "5 days from starter to loaf", [
                "sourdough starter bubbling jar", "kneading bread dough hands", "bread baking in oven"]),
            RankItem(4, "Kimchi", "Weeks of fermentation", [
                "making kimchi cabbage hands", "fermentation jars vegetables", "korean side dishes table"]),
            RankItem(3, "Soy sauce", "Six months in brine", [
                "soy sauce brewing barrels", "fermentation vats factory", "pouring dark sauce bottle"]),
            RankItem(2, "Parmesan", "Two years minimum", [
                "cheese wheels aging shelves", "cheese ageing cellar rows", "cutting hard cheese wheel"]),
            RankItem(1, "Balsamic vinegar", "Twelve years in wooden casks", [
                "wooden barrels ageing cellar", "dark vinegar pouring spoon", "wine barrels stacked cellar"]),
        ],
    ),
    RankList(
        title="Hardest Skills To Learn",
        hook_caption="Most people quit at number 3",
        closing_caption="Which one beat you?",
        items=[
            RankItem(5, "Juggling", "Two weeks for three balls", [
                "juggling balls hands close up", "street performer juggling", "person practising juggling"]),
            RankItem(4, "Welding", "Hundreds of hours for a clean bead", [
                "welder sparks close up", "welding torch metal seam", "workshop welding mask"]),
            RankItem(3, "Glassblowing", "Years before a usable piece", [
                "glassblower shaping molten glass", "glass furnace workshop", "molten glass on rod"]),
            RankItem(2, "Violin", "Ten years to sound good", [
                "violin bow strings close up", "person practising violin", "orchestra string section"]),
            RankItem(1, "Surgery", "Fifteen years of training", [
                "surgeons operating theatre", "surgical instruments tray", "hands in surgical gloves"]),
        ],
    ),
)


def offline_list(seed: int | None = None) -> RankList:
    rng = random.Random(seed)
    chosen = rng.choice(OFFLINE_LISTS)
    # Deep copy so a caller mutating `chosen` (setting item.chosen, say) does
    # not poison the module-level bank for the next run in the same process.
    return RankList(
        title=chosen.title,
        hook_caption=chosen.hook_caption,
        closing_caption=chosen.closing_caption,
        items=[
            RankItem(i.rank, i.name, i.stat, list(i.search_terms)) for i in chosen.items
        ],
    )


def parse_list_json(raw: str) -> RankList:
    text = raw.strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.splitlines() if not l.strip().startswith("```")).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model did not return valid JSON: {exc}\n---\n{raw[:600]}") from exc

    for field in ("title", "hook_caption", "closing_caption", "items"):
        if field not in data:
            raise ValueError(f"Ranked list is missing required field {field!r}")
    if not isinstance(data["items"], list) or not data["items"]:
        raise ValueError("Ranked list has no items")

    items = []
    for raw_item in data["items"]:
        for field in ("rank", "name", "stat"):
            if field not in raw_item:
                raise ValueError(f"List item is missing {field!r}: {raw_item}")
        terms = raw_item.get("search_terms") or []
        if isinstance(terms, str):
            terms = [terms]
        items.append(
            RankItem(
                rank=int(raw_item["rank"]),
                name=str(raw_item["name"]).strip(),
                stat=str(raw_item["stat"]).strip(),
                search_terms=[str(t).strip() for t in terms if str(t).strip()],
            )
        )
    items.sort(key=lambda i: i.rank, reverse=True)

    return RankList(
        title=str(data["title"]).strip(),
        hook_caption=str(data["hook_caption"]).strip(),
        closing_caption=str(data["closing_caption"]).strip(),
        items=items,
    )
