"""Command line interface."""

from __future__ import annotations

import argparse
import sys
import traceback

from . import checks, pipeline, topics
from .config import Config, load


def _load_dotenv() -> None:
    """Load a .env from the working directory if present.

    Deliberately hand-rolled: one small file read is not worth a dependency,
    and existing environment variables always win so a scheduler can override.
    """
    from pathlib import Path

    path = Path(".env")
    if not path.exists():
        return
    import os

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def cmd_check(args: argparse.Namespace) -> int:
    cfg = Config()  # not validated: check exists precisely to diagnose bad config
    results, usable = checks.run_checks(cfg, with_probe=args.probe_image)
    print()
    for c in results:
        print(f"  {checks.MARK[c.status]} {c.label}: {c.detail}")
    print()
    if usable:
        print("  Ready to run. `python -m vidauto run` works right now in mock mode.")
    else:
        print("  Not runnable yet -- fix the [fail] items above.")
    print()
    return 0 if usable else 1


def cmd_run(args: argparse.Namespace) -> int:
    try:
        cfg = load()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.segments:
        cfg.segments = args.segments
    if args.seconds:
        cfg.seconds_per_segment = args.seconds
    if args.provider:
        cfg.image_provider = args.provider
        cfg.text_provider = args.provider
    try:
        cfg.validate()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    failures = 0
    for n in range(args.count):
        try:
            result = pipeline.run_once(
                cfg,
                seed=args.seed if args.seed is None else args.seed + n,
                keep_intermediates=args.keep_intermediates,
            )
        except Exception as exc:  # noqa: BLE001 - one bad run must not kill a batch
            failures += 1
            print(f"\n  run {n + 1}/{args.count} FAILED: {exc}", file=sys.stderr)
            if args.traceback:
                traceback.print_exc()
            continue

        print(f"\n  {result.topic.topic}  ({result.duration:.1f}s)")
        print(f"  video     {result.video}")
        print(f"  checklist {result.directory / 'POSTING.md'}")
        for warning in result.warnings:
            print(f"  warn      {warning}")

    print()
    if failures:
        print(f"  {args.count - failures}/{args.count} runs succeeded.")
    return 1 if failures else 0


def cmd_topic(args: argparse.Namespace) -> int:
    """Print a topic without rendering anything -- useful for tuning prompts."""
    import json

    from . import providers

    try:
        cfg = load()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    topic = providers.generate_topic(cfg, seed=args.seed)
    print(json.dumps(topic.to_dict(), indent=2))
    for warning in topic.warnings():
        print(f"# warn: {warning}", file=sys.stderr)
    if args.show_prompts:
        print("\n# per-segment image prompts", file=sys.stderr)
        for i, p in enumerate(topics.shot_prompts(topic, cfg.segments, seed=args.seed)):
            print(f"\n[{i}] {p}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vidauto",
        description="Faceless vertical video pipeline: generated stills, animated and assembled.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="report what this machine and API key can do")
    p_check.add_argument(
        "--probe-image",
        action="store_true",
        help="actually generate one image to prove access works (COSTS MONEY)",
    )
    p_check.set_defaults(func=cmd_check)

    p_run = sub.add_parser("run", help="produce one or more finished videos")
    p_run.add_argument("--count", type=int, default=1, help="how many videos to produce")
    p_run.add_argument("--segments", type=int, help="override number of shots")
    p_run.add_argument("--seconds", type=float, help="override seconds per shot")
    p_run.add_argument("--provider", choices=("mock", "openai"), help="override both providers")
    p_run.add_argument("--seed", type=int, help="deterministic topic and framing choice")
    p_run.add_argument("--keep-intermediates", action="store_true", help="keep per-segment files")
    p_run.add_argument("--traceback", action="store_true", help="print full tracebacks on failure")
    p_run.set_defaults(func=cmd_run)

    p_topic = sub.add_parser("topic", help="print one topic as JSON without rendering")
    p_topic.add_argument("--seed", type=int)
    p_topic.add_argument("--show-prompts", action="store_true", help="also print per-segment prompts")
    p_topic.set_defaults(func=cmd_topic)

    return parser


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    args = build_parser().parse_args(argv)
    return args.func(args)
