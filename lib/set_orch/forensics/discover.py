"""`discover` output: list resolved sources without reading content."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .resolver import ResolvedRun

KNOWN_ORCHESTRATION_ARTIFACTS = [
    "orchestration-events.jsonl",
    "orchestration-state-events.jsonl",
    "orchestration-plan.json",
    "orchestration-state.json",
    "journals",
    "messages",
]


def _format_size(n: int) -> str:
    num = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024.0 or unit == "GB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024.0
    return f"{num:.1f} GB"


def _session_dir_info(path: Path) -> dict[str, Any]:
    jsonls = sorted(path.glob("*.jsonl"))
    total_size = sum(p.stat().st_size for p in jsonls)
    most_recent = None
    if jsonls:
        mtimes = [p.stat().st_mtime for p in jsonls]
        most_recent = max(mtimes)
    return {
        "path": str(path),
        "jsonl_count": len(jsonls),
        "total_bytes": total_size,
        "total_size_human": _format_size(total_size),
        "most_recent_mtime": most_recent,
    }


def _orchestration_info(resolved: ResolvedRun) -> dict[str, Any]:
    if resolved.orchestration_dir is None:
        return {"path": None, "artifacts": {}}
    artifacts: dict[str, bool] = {}
    for name in KNOWN_ORCHESTRATION_ARTIFACTS:
        candidate = resolved.orchestration_dir / name
        artifacts[name] = candidate.exists()
    return {
        "path": str(resolved.orchestration_dir),
        "artifacts": artifacts,
    }


def build_discover_payload(resolved: ResolvedRun) -> dict[str, Any]:
    main = None
    if resolved.main_session_dir is not None:
        main = _session_dir_info(resolved.main_session_dir)

    worktrees = {
        change: _session_dir_info(path)
        for change, path in sorted(resolved.worktree_session_dirs.items())
    }

    return {
        "run_id": resolved.run_id,
        "main": main,
        "worktrees": worktrees,
        "orchestration": _orchestration_info(resolved),
    }


def to_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = [f"# Discover: {payload['run_id']}", ""]

    lines.append("## Session dirs")
    lines.append("| change | path | jsonl_count | size | most_recent_mtime |")
    lines.append("| --- | --- | --- | --- | --- |")

    def _fmt_mtime(m: Any) -> str:
        if not isinstance(m, (int, float)):
            return ""
        from datetime import datetime, timezone
        return datetime.fromtimestamp(m, tz=timezone.utc).isoformat(timespec="seconds")

    main = payload.get("main")
    if main:
        lines.append(
            f"| `main` | `{main['path']}` | {main['jsonl_count']} |"
            f" {main['total_size_human']} | {_fmt_mtime(main['most_recent_mtime'])} |"
        )
    for change, info in payload.get("worktrees", {}).items():
        lines.append(
            f"| `{change}` | `{info['path']}` | {info['jsonl_count']} |"
            f" {info['total_size_human']} | {_fmt_mtime(info['most_recent_mtime'])} |"
        )
    lines.append("")

    lines.append("## Orchestration artifacts")
    orch = payload.get("orchestration", {})
    if orch.get("path") is None:
        lines.append("_Orchestration dir not found._")
    else:
        lines.append(f"- path: `{orch['path']}`")
        for name, exists in orch.get("artifacts", {}).items():
            marker = "(found)" if exists else "(missing)"
            lines.append(f"  - `{name}` {marker}")
    return "\n".join(lines)
