"""Two ledgers that outlive any single run.

**Used clips.** Reusing the same footage across videos is precisely what
platform "recycled / mass-produced content" rules are written to catch, and at
automation scale it happens constantly: the same three clips top the search
results for "warehouse work" every time you ask. So every clip ever used is
recorded and excluded from future selection.

**Licenses.** Attribution obligations differ per source, and the penalty for
getting it wrong is infringing while believing you are safe. Every clip that
lands in a video is recorded with its license and attribution text, and each
run emits a CREDITS file built from that record.

A JSON file, not a database. It is append-mostly, read once per run, and small
enough that a few thousand videos of history still loads instantly -- adding a
database engine here would buy nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import Candidate


@dataclass
class Ledger:
    path: Path
    used: dict[str, dict]

    @classmethod
    def load(cls, path: Path) -> "Ledger":
        if path.exists():
            try:
                raw = json.loads(path.read_text())
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Clip ledger at {path} is corrupt ({exc}). Move it aside to start fresh; "
                    "deleting it silently would let previously-used clips be reused."
                ) from exc
            return cls(path=path, used=raw.get("used", {}))
        return cls(path=path, used={})

    def has_used(self, candidate: Candidate) -> bool:
        return candidate.key in self.used

    def record(self, candidate: Candidate, video: str, item_name: str) -> None:
        self.used[candidate.key] = {
            "source": candidate.source,
            "source_id": candidate.source_id,
            "title": candidate.title,
            "page_url": candidate.page_url,
            "license": candidate.license,
            "attribution_required": candidate.attribution_required,
            "attribution_text": candidate.attribution_text,
            "used_in": video,
            "used_for": item_name,
            "used_at": datetime.now(timezone.utc).isoformat(),
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "used": self.used}
        # Write via a temp file so an interrupted save cannot truncate the
        # ledger and silently un-remember every clip already used.
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n")
        tmp.replace(self.path)

    def __len__(self) -> int:
        return len(self.used)


def write_credits(dest: Path, candidates: list[Candidate], title: str) -> None:
    """Emit the attribution file for one video."""
    required = [c for c in candidates if c.attribution_required]
    lines = [f"# Credits -- {title}", ""]

    if required:
        lines += [
            "## Attribution REQUIRED",
            "",
            "These licenses oblige you to credit the creator. Put this in the",
            "video description before publishing.",
            "",
        ]
        for c in required:
            lines.append(f"- {c.attribution_text or c.title} -- {c.license} -- {c.page_url}")
        lines.append("")

    optional = [c for c in candidates if not c.attribution_required]
    if optional:
        lines += ["## Attribution not required", "", "Credited here for your records only.", ""]
        for c in optional:
            lines.append(f"- {c.attribution_text or c.title} -- {c.license} -- {c.page_url}")
        lines.append("")

    dest.write_text("\n".join(lines))
