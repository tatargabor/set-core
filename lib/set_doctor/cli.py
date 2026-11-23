"""set-doctor's command line: text for a person, `--json` for a calling tool."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter

from set_doctor import SCHEMA
from set_doctor.checks import RANK, Context, head_label, run_all

logger = logging.getLogger(__name__)

SECTIONS = [("install", "INSTALL"), ("checkout", "CHECKOUT"), ("tools", "TOOLS"), ("mcp", "MCP SERVER"),
            ("bus", "AGENT BUS"), ("project", "PROJECTS"), ("modules", "MODULES"), ("providers", "PROVIDERS"),
            ("github", "GITHUB")]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="set-doctor",
                                description="Is the set-core side of this developer machine in order? "
                                            "Reports every problem with the command that fixes it; repairs nothing.")
    p.add_argument("--json", action="store_true", help="the versioned machine contract (set-doctor/1)")
    p.add_argument("--project", metavar="GLOB", help="check only registered projects matching this name glob")
    p.add_argument("--offline", action="store_true", help="no git fetch, no relay check")
    p.add_argument("--deep", action="store_true", help="also run `set-project init --dry-run` per project (slow)")
    p.add_argument("--live", action="store_true", help="also make one paid GLM call (set-glm --check)")
    p.add_argument("--strict", action="store_true", help="exit non-zero on warnings too")
    p.add_argument("--all", action="store_true", help="text output: list every project, not only those with a problem")
    p.add_argument("--verbose", action="store_true", help="debug log on stderr")
    return p


def exit_code(checks: list, strict: bool) -> int:
    bad = {"fail", "warn"} if strict else {"fail"}
    return 1 if any(c.status in bad for c in checks) else 0


def payload(ctx: Context, checks: list, code: int) -> dict:
    return {"schema": SCHEMA, "ok": code == 0, "root": ctx.root, "head": head_label(ctx.root),
            "counts": dict(Counter(c.status for c in checks)), "checks": [c.to_dict() for c in checks]}


MARK = {"ok": "ok  ", "warn": "WARN", "fail": "FAIL", "skip": "skip"}


def render_text(ctx: Context, checks: list, show_all: bool) -> str:
    lines = [f"set-doctor — {ctx.root} ({head_label(ctx.root)})"]
    for key, title in SECTIONS:
        sec = [c for c in checks if c.section == key]
        if not sec:
            continue
        lines.append("")
        if key != "project":
            lines.append(title)
            for c in sec:
                lines.extend(line_for(c))
            continue
        top = [c for c in sec if not c.project]
        by_proj: dict = {}
        for c in sec:
            if c.project:
                by_proj.setdefault(c.project, []).append(c)
        worst = {n: max(cs, key=lambda c: RANK[c.status]).status for n, cs in by_proj.items()}
        tally = Counter(worst.values())
        parts = ", ".join(f"{tally[s]} {s}" for s in ("ok", "warn", "fail", "skip") if tally[s])
        lines.append(f"{title} ({len(by_proj)}" + (f": {parts})" if parts else ")"))
        for c in top:
            lines.extend(line_for(c))
        for name in sorted(by_proj, key=lambda n: (-RANK[worst[n]], n)):
            cs = by_proj[name]
            if worst[name] == "ok" and not show_all:
                continue
            lines.append(f"  {MARK[worst[name]]}  {name}")
            for c in cs:
                if c.status in ("warn", "fail") or show_all:
                    lines.extend(line_for(c, indent="        "))
        hidden = sum(1 for n in by_proj if worst[n] == "ok")
        if hidden and not show_all:
            lines.append(f"  ({hidden} project(s) all ok — --all lists them)")
    counts = Counter(c.status for c in checks)
    lines.append("")
    lines.append("summary: " + ", ".join(f"{counts[s]} {s}" for s in ("fail", "warn", "skip", "ok") if counts[s]))
    return "\n".join(lines)


BUILT_IN_MODULES = ("sac", "set-kb")  # their record names already say what they are


def line_for(c, indent="  ") -> list:
    name = f"{c.module}:{c.name}" if c.module and c.module not in BUILT_IN_MODULES and c.name != c.module else c.name
    out = [f"{indent}{MARK[c.status]}  {name:<12} {c.detail}"]
    if c.fix and c.status in ("warn", "fail"):
        out.append(f"{indent}      → {c.fix}")
    return out


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                        format="set-doctor: %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    ctx = Context(root=root, home=os.path.expanduser("~"), offline=args.offline, deep=args.deep,
                  live=args.live, project_glob=args.project)
    logger.info("start: root=%s offline=%s deep=%s live=%s project=%s", root, args.offline, args.deep, args.live,
                args.project)
    checks = run_all(ctx)
    code = exit_code(checks, args.strict)
    if args.json:
        print(json.dumps(payload(ctx, checks, code), indent=2, ensure_ascii=False))
    else:
        print(render_text(ctx, checks, args.all))
    logger.info("done: exit %d, %s", code, dict(Counter(c.status for c in checks)))
    return code
