"""set-run-logs CLI entry point. Registered in pyproject.toml [project.scripts]."""
from __future__ import annotations

import argparse
import json
import logging
import sys

from . import digest as digest_mod
from . import discover as discover_mod
from . import grep as grep_mod
from . import orchestration as orch_mod
from . import timeline as timeline_mod
from .digest import digest_run
from .grep import grep_content
from .orchestration import OrchestrationDirMissing, orchestration_summary
from .resolver import NoSessionDirsError, resolve_run
from .timeline import AmbiguousSessionPrefix, SessionNotFound, session_timeline


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


def _cmd_discover(args: argparse.Namespace) -> int:
    resolved = resolve_run(args.run_id)
    payload = discover_mod.build_discover_payload(resolved)
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(discover_mod.to_markdown(payload))
    return 0


def _cmd_digest(args: argparse.Namespace) -> int:
    resolved = resolve_run(args.run_id)
    result = digest_run(resolved)
    if args.json:
        print(json.dumps(digest_mod.to_json(result), indent=2, default=str))
    else:
        print(digest_mod.to_markdown(result))
    return 0


def _cmd_session(args: argparse.Namespace) -> int:
    resolved = resolve_run(args.run_id)
    try:
        timeline = session_timeline(
            resolved,
            args.uuid,
            errors_only=args.errors_only,
            tool=args.tool,
        )
    except AmbiguousSessionPrefix as exc:
        print(f"error: {exc}", file=sys.stderr)
        for c in exc.candidates:
            print(f"  - {c['change']}/{c['session_uuid']}", file=sys.stderr)
        return 2
    except SessionNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(timeline_mod.to_json(timeline), indent=2, default=str))
    else:
        print(timeline_mod.to_markdown(timeline))
    return 0


def _cmd_grep(args: argparse.Namespace) -> int:
    resolved = resolve_run(args.run_id)
    try:
        outcome = grep_content(
            resolved,
            args.pattern,
            tool=args.tool,
            limit=args.limit,
            case_insensitive=args.case_insensitive,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(grep_mod.to_json(outcome), indent=2, default=str))
    else:
        print(grep_mod.to_markdown(outcome))
    return 0


def _cmd_orchestration(args: argparse.Namespace) -> int:
    resolved = resolve_run(args.run_id)
    try:
        summary = orchestration_summary(resolved)
    except OrchestrationDirMissing as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(orch_mod.to_json(summary), indent=2, default=str))
    else:
        print(orch_mod.to_markdown(summary))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="set-run-logs",
        description=(
            "Forensic analysis of a completed orchestration run. "
            "Resolves all Claude Code session transcripts + orchestration logs "
            "for the given run id and exposes filtered views."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose logging")
    parser.add_argument("run_id", help="orchestration run id (directory name)")

    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_discover = sub.add_parser("discover", help="list resolved session dirs + orchestration artifacts")
    p_discover.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    p_discover.set_defaults(func=_cmd_discover)

    p_digest = sub.add_parser("digest", help="aggregate error/anomaly signals across all sessions")
    p_digest.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    p_digest.set_defaults(func=_cmd_digest)

    p_session = sub.add_parser("session", help="targeted view of a single session's timeline")
    p_session.add_argument("uuid", help="session UUID or unique prefix (≥6 chars)")
    p_session.add_argument("--errors-only", action="store_true", help="only show error/timeout entries and anomalous stops")
    p_session.add_argument("--tool", help="filter to one tool name (case-insensitive)")
    p_session.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    p_session.set_defaults(func=_cmd_session)

    p_grep = sub.add_parser("grep", help="regex search over message.content text (not raw jsonl lines)")
    p_grep.add_argument("pattern", help="regular expression")
    p_grep.add_argument("-i", "--ignore-case", dest="case_insensitive", action="store_true")
    p_grep.add_argument("--tool", help="only search tool_use / tool_result for the given tool")
    p_grep.add_argument("--limit", type=int, default=50, help="max matches to emit (default 50)")
    p_grep.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    p_grep.set_defaults(func=_cmd_grep)

    p_orch = sub.add_parser("orchestration", help="summarise orchestration-level events")
    p_orch.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    p_orch.set_defaults(func=_cmd_orchestration)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    try:
        return args.func(args)
    except NoSessionDirsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
