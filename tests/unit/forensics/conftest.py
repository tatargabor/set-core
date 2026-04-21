"""Shared fixtures for forensics unit tests."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _encode(path: Path) -> str:
    return str(path).replace("/", "-").replace(".", "-")


@pytest.fixture
def run_layout(tmp_path: Path) -> dict[str, Any]:
    """Build a synthetic run layout with main + 2 worktrees + orchestration dir.

    Returns dict:
      - claude_projects_root
      - e2e_runs_root
      - run_id
      - main_session_dir, worktree_dirs (by change), orchestration_dir
    """
    claude_root = tmp_path / ".claude" / "projects"
    e2e_root = tmp_path / "e2e-runs"
    run_id = "minishop-run-20260420-1200"

    run_path = e2e_root / run_id
    run_path.mkdir(parents=True)

    # Neighbour with name-collision suffix — must NOT be picked up.
    collision_path = e2e_root / f"{run_id}x"
    collision_path.mkdir(parents=True)

    base = _encode(run_path)
    collision_base = _encode(collision_path)

    main_dir = claude_root / base
    main_dir.mkdir(parents=True)
    wt_auth = claude_root / f"{base}-wt-auth-setup"
    wt_auth.mkdir()
    wt_cart = claude_root / f"{base}-wt-cart-and-session"
    wt_cart.mkdir()
    # Collision dir exists but must be ignored.
    collision_dir = claude_root / collision_base
    collision_dir.mkdir()

    return {
        "claude_projects_root": claude_root,
        "e2e_runs_root": e2e_root,
        "run_id": run_id,
        "main_session_dir": main_dir,
        "worktree_dirs": {
            "auth-setup": wt_auth,
            "cart-and-session": wt_cart,
        },
        "collision_session_dir": collision_dir,
        "orchestration_dir": run_path,
    }


@pytest.fixture
def write_session():
    """Return a helper that writes a jsonl session file with the given records."""

    def _writer(dir_path: Path, session_uuid: str, records: list[dict[str, Any]]) -> Path:
        path = dir_path / f"{session_uuid}.jsonl"
        _write_jsonl(path, records)
        return path

    return _writer
