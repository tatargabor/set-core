"""Integration-ish tests for the per-gate retry policy wiring inside
`GatePipeline` (section 12 of fix-replan-stuck-gate-and-decomposer).

These exercise `_try_cache_reuse`, `_try_scoped_run`, and the surrounding
counter bookkeeping without spinning up the full verifier or a real git
worktree. The pipeline is fed a minimal fake profile + fake executor.

Covers:
  AC-41 (cached reuse when diff is out-of-scope)
  AC-42 (cache invalidated by scope overlap)
  AC-43 (cache-use cap reached forces full run)
  AC-45 (scoped e2e returns subset, VERIFY_GATE scoped_subset present)
  AC-48 (first verify run ignores policy)
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"))

from set_orch.gate_runner import GatePipeline, GateResult  # noqa: E402
from set_orch.state import Change, GateRetryEntry  # noqa: E402


class _FakeGateConfig:
    def __init__(self, blocking: dict[str, bool]):
        self._blocking = blocking

    def should_run(self, gate_name: str) -> bool:
        return True

    def is_blocking(self, gate_name: str) -> bool:
        return self._blocking.get(gate_name, True)

    def get(self, gate_name: str, default: str = "?") -> str:
        return "run"


class _FakeEventBus:
    def __init__(self):
        self.emitted: list[tuple[str, dict]] = []

    def emit(self, event: str, change: str = "", data=None, **_):
        self.emitted.append((event, {"change": change, "data": data or {}}))


class _FakeProfile:
    def __init__(
        self,
        policy: dict[str, str],
        cache_scopes: dict[str, list[str]] | None = None,
        scope_filter_result: list[str] | None = None,
    ):
        self._policy = policy
        self._cache_scopes = cache_scopes or {}
        self._scope_filter = scope_filter_result
        self.filter_calls: list[tuple[str, list[str]]] = []

    def gate_retry_policy(self):
        return dict(self._policy)

    def gate_cache_scope(self, gate_name: str):
        return list(self._cache_scopes.get(gate_name, []))

    def gate_scope_filter(self, gate_name: str, diff_files: list[str]):
        self.filter_calls.append((gate_name, list(diff_files)))
        return list(self._scope_filter) if self._scope_filter else None


def _init_repo(tmp: Path, files: dict[str, str]) -> str:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.email", "x@y.z"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.name", "x"], cwd=tmp, check=True)
    for rel, content in files.items():
        dest = tmp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    subprocess.run(["git", "add", "."], cwd=tmp, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp, capture_output=True, text=True, check=True,
    ).stdout.strip()
    return head


def _commit(tmp: Path, files: dict[str, str], msg: str = "update") -> str:
    for rel, content in files.items():
        dest = tmp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    subprocess.run(["git", "add", "."], cwd=tmp, check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=tmp, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp, capture_output=True, text=True, check=True,
    ).stdout.strip()


def _make_state_file(tmp: Path, change: Change | None = None) -> str:
    import json
    path = tmp / "orchestration-state.json"
    payload: dict = {"changes": [], "extras": {}}
    if change is not None:
        payload["changes"].append(change.to_dict())
    path.write_text(json.dumps(payload))
    return str(path)


def test_first_verify_run_ignores_cache_policy(tmp_path):
    """AC-48: verify_retry_index == 0 → no cached gates, full run."""
    wt = tmp_path / "wt"
    wt.mkdir()
    baseline_sha = _init_repo(wt, {"src/a.tsx": "a"})

    change = Change(
        name="c1", scope="x",
        worktree_path=str(wt),
        gate_retry_tracking={
            "review": GateRetryEntry(
                consecutive_cache_uses=1,
                last_verdict_sha=baseline_sha,
                last_run_retry_index=0,
            ),
        },
        verify_retry_index=0,
    )
    gc = _FakeGateConfig({"review": True})
    profile = _FakeProfile(
        policy={"review": "cached"},
        cache_scopes={"review": ["src/**"]},
    )
    bus = _FakeEventBus()

    def exec_review():
        return GateResult("review", "pass", duration_ms=1)

    pipeline = GatePipeline(
        gc, _make_state_file(tmp_path, change), "c1", change,
        max_retries=2, event_bus=bus, profile=profile,
    )
    pipeline.register("review", exec_review)
    pipeline.run()

    # No GATE_CACHED emitted; review ran fully.
    assert not any(ev[0] == "GATE_CACHED" for ev in bus.emitted)
    assert "review" in pipeline._gate_full_ran_this_run


def test_cached_review_reused_when_diff_is_out_of_scope(tmp_path):
    """AC-41: retry diff touches only out-of-scope files → cached."""
    wt = tmp_path / "wt"
    wt.mkdir()
    baseline_sha = _init_repo(wt, {"src/a.tsx": "a"})
    # Commit something outside the review cache-scope: a README
    _commit(wt, {"README.md": "hi"}, "docs-only")

    change = Change(
        name="c2", scope="x",
        worktree_path=str(wt),
        gate_retry_tracking={
            "review": GateRetryEntry(
                consecutive_cache_uses=0,
                last_verdict_sha=baseline_sha,
                last_run_retry_index=0,
            ),
        },
        verify_retry_index=1,
    )
    gc = _FakeGateConfig({"review": True})
    profile = _FakeProfile(
        policy={"review": "cached"},
        cache_scopes={"review": ["src/**", "tests/**", "prisma/**"]},
    )
    bus = _FakeEventBus()

    called = {"review": 0}

    def exec_review():
        called["review"] += 1
        return GateResult("review", "fail")

    pipeline = GatePipeline(
        gc, _make_state_file(tmp_path, change), "c2", change,
        max_retries=2, event_bus=bus, profile=profile,
    )
    pipeline.register("review", exec_review)
    pipeline.run()

    # Cache used — executor never called, GATE_CACHED emitted.
    assert called["review"] == 0
    cached_events = [ev for ev in bus.emitted if ev[0] == "GATE_CACHED"]
    assert len(cached_events) == 1
    assert cached_events[0][1]["data"]["gate"] == "review"


def test_cache_invalidated_by_scope_overlap(tmp_path):
    """AC-42: retry diff touches src/**/*.tsx → design-fidelity cache busted."""
    wt = tmp_path / "wt"
    wt.mkdir()
    baseline_sha = _init_repo(wt, {"src/a.tsx": "a"})
    _commit(wt, {"src/components/cart/cart-item.tsx": "new"}, "cart")

    change = Change(
        name="c3", scope="x",
        worktree_path=str(wt),
        gate_retry_tracking={
            "design-fidelity": GateRetryEntry(
                consecutive_cache_uses=0,
                last_verdict_sha=baseline_sha,
                last_run_retry_index=0,
            ),
        },
        verify_retry_index=1,
    )
    gc = _FakeGateConfig({"design-fidelity": True})
    profile = _FakeProfile(
        policy={"design-fidelity": "cached"},
        cache_scopes={"design-fidelity": [
            "src/**/*.tsx", "src/**/*.css",
            "public/design-tokens.json", "tailwind.config.ts",
        ]},
    )
    bus = _FakeEventBus()
    called = {"design-fidelity": 0}

    def exec_df():
        called["design-fidelity"] += 1
        return GateResult("design-fidelity", "pass", duration_ms=1)

    pipeline = GatePipeline(
        gc, _make_state_file(tmp_path, change), "c3", change,
        max_retries=2, event_bus=bus, profile=profile,
    )
    pipeline.register("design-fidelity", exec_df)
    pipeline.run()

    # Cache invalidated → gate ran fully.
    assert called["design-fidelity"] == 1
    assert not any(ev[0] == "GATE_CACHED" for ev in bus.emitted)


def test_cache_use_cap_reached_forces_full_run(tmp_path):
    """AC-43: 3rd consecutive cache use forces full run."""
    wt = tmp_path / "wt"
    wt.mkdir()
    baseline_sha = _init_repo(wt, {"src/a.tsx": "a"})
    _commit(wt, {"README.md": "change"}, "out-of-scope")

    change = Change(
        name="c4", scope="x",
        worktree_path=str(wt),
        gate_retry_tracking={
            "review": GateRetryEntry(
                consecutive_cache_uses=2,  # already at cap
                last_verdict_sha=baseline_sha,
                last_run_retry_index=0,
            ),
        },
        verify_retry_index=3,
    )
    gc = _FakeGateConfig({"review": True})
    profile = _FakeProfile(
        policy={"review": "cached"},
        cache_scopes={"review": ["src/**"]},
    )
    bus = _FakeEventBus()
    called = {"review": 0}

    def exec_review():
        called["review"] += 1
        return GateResult("review", "pass", duration_ms=1)

    pipeline = GatePipeline(
        gc, _make_state_file(tmp_path, change), "c4", change,
        max_retries=2, event_bus=bus, profile=profile,
        max_consecutive_cache_uses=2,
    )
    pipeline.register("review", exec_review)
    pipeline.run()

    assert called["review"] == 1
    assert not any(ev[0] == "GATE_CACHED" for ev in bus.emitted)


def test_scoped_gate_uses_subset_when_filter_returns_list(tmp_path):
    """AC-45: scoped e2e passes subset through to the executor."""
    wt = tmp_path / "wt"
    wt.mkdir()
    baseline_sha = _init_repo(wt, {"src/app/cart/page.tsx": "c"})
    _commit(wt, {"src/app/cart/page.tsx": "edit"}, "cart edit")

    change = Change(
        name="c5", scope="x",
        worktree_path=str(wt),
        gate_retry_tracking={
            "e2e": GateRetryEntry(
                consecutive_cache_uses=0,
                last_verdict_sha=baseline_sha,
                last_run_retry_index=0,
            ),
        },
        verify_retry_index=1,
    )
    gc = _FakeGateConfig({"e2e": True})
    profile = _FakeProfile(
        policy={"e2e": "scoped"},
        scope_filter_result=["tests/e2e/cart.spec.ts"],
    )
    bus = _FakeEventBus()

    called = {"e2e": 0}

    def exec_e2e():
        called["e2e"] += 1
        return GateResult("e2e", "pass", duration_ms=1)

    pipeline = GatePipeline(
        gc, _make_state_file(tmp_path, change), "c5", change,
        max_retries=2, event_bus=bus, profile=profile,
    )
    pipeline.register("e2e", exec_e2e)
    pipeline.run()

    # Gate ran fully (not cached) but the scoped_subset was populated so
    # the verifier's register-closure would pass it into the executor.
    assert called["e2e"] == 1
    assert pipeline._gate_scoped_subset.get("e2e") == ["tests/e2e/cart.spec.ts"]


def test_cache_reuse_replays_prior_fail_verdict(tmp_path):
    """CRITICAL-2 regression: if the last full run failed, the cache
    reuse MUST report fail — not silently pass.

    Without this guarantee, a review gate that failed on retry N would
    cache a pass on retry N+1 when the diff is out-of-scope, hiding the
    failure and potentially letting the change merge.
    """
    wt = tmp_path / "wt"
    wt.mkdir()
    baseline_sha = _init_repo(wt, {"src/a.tsx": "a"})
    # Commit something outside the review cache-scope
    _commit(wt, {"README.md": "docs"}, "docs-only")

    change = Change(
        name="c7", scope="x",
        worktree_path=str(wt),
        gate_retry_tracking={
            "review": GateRetryEntry(
                consecutive_cache_uses=0,
                last_verdict_sha=baseline_sha,
                last_verdict="fail",  # prior run failed
                last_run_retry_index=0,
            ),
        },
        verify_retry_index=2,
        verify_retry_count=1,
    )
    gc = _FakeGateConfig({"review": True})
    profile = _FakeProfile(
        policy={"review": "cached"},
        cache_scopes={"review": ["src/**"]},
    )
    bus = _FakeEventBus()
    called = {"review": 0}

    def exec_review():
        called["review"] += 1
        return GateResult("review", "pass", duration_ms=1)

    pipeline = GatePipeline(
        gc, _make_state_file(tmp_path, change), "c7", change,
        max_retries=5, event_bus=bus, profile=profile,
    )
    pipeline.register("review", exec_review)
    action = pipeline.run()

    # Cache reuse happened but reported the prior FAIL, stopping the pipeline.
    assert called["review"] == 0
    assert any(ev[0] == "GATE_CACHED" for ev in bus.emitted)
    assert action in ("retry", "failed")
    # The cached replay surfaced a fail result, not a pass.
    replayed = [r for r in pipeline.results if r.gate_name == "review"]
    assert len(replayed) == 1
    assert replayed[0].status == "fail"


def test_cache_invalidated_on_git_diff_failure(tmp_path):
    """CRITICAL-1 regression: if git diff cannot be computed (bad
    baseline sha, missing worktree), the cache MUST be invalidated and
    the gate MUST run fully — never reuse a cache based on an unknown
    diff state.
    """
    wt = tmp_path / "wt"
    wt.mkdir()
    _init_repo(wt, {"src/a.tsx": "a"})

    # Deliberately nonsense baseline sha → git diff will fail
    bogus_sha = "deadbeef" * 5  # 40 chars but doesn't exist as a commit
    change = Change(
        name="c8", scope="x",
        worktree_path=str(wt),
        gate_retry_tracking={
            "review": GateRetryEntry(
                consecutive_cache_uses=0,
                last_verdict_sha=bogus_sha,
                last_verdict="pass",
                last_run_retry_index=0,
            ),
        },
        verify_retry_index=1,
    )
    gc = _FakeGateConfig({"review": True})
    profile = _FakeProfile(
        policy={"review": "cached"},
        cache_scopes={"review": ["src/**"]},
    )
    bus = _FakeEventBus()
    called = {"review": 0}

    def exec_review():
        called["review"] += 1
        return GateResult("review", "pass", duration_ms=1)

    pipeline = GatePipeline(
        gc, _make_state_file(tmp_path, change), "c8", change,
        max_retries=2, event_bus=bus, profile=profile,
    )
    pipeline.register("review", exec_review)
    pipeline.run()

    # Cache was invalidated because the diff could not be computed.
    assert called["review"] == 1
    assert not any(ev[0] == "GATE_CACHED" for ev in bus.emitted)


def test_retry_diff_files_distinguishes_none_from_empty(tmp_path):
    """Unit: `_retry_diff_files` returns None on git failure and [] on
    a successful diff with zero file changes (same commit)."""
    wt = tmp_path / "wt"
    wt.mkdir()
    baseline_sha = _init_repo(wt, {"src/a.tsx": "a"})

    change = Change(name="c9", scope="x", worktree_path=str(wt))
    gc = _FakeGateConfig({})
    pipeline = GatePipeline(
        gc, _make_state_file(tmp_path, change), "c9", change,
        max_retries=2, event_bus=_FakeEventBus(), profile=None,
    )

    # Empty baseline → None (safe default).
    assert pipeline._retry_diff_files("") is None

    # Valid baseline == HEAD → empty list (zero changes).
    assert pipeline._retry_diff_files(baseline_sha) == []

    # Bogus baseline → None (git fails).
    assert pipeline._retry_diff_files("deadbeef" * 5) is None


def test_cache_full_run_resets_consecutive_counter(tmp_path):
    """commit_results: after a full run, consecutive_cache_uses resets to 0."""
    wt = tmp_path / "wt"
    wt.mkdir()
    baseline_sha = _init_repo(wt, {"src/a.tsx": "a"})
    _commit(wt, {"src/a.tsx": "modified"}, "in-scope")

    state_file = _make_state_file(tmp_path)
    # Seed state file with the change
    import json
    st = {
        "changes": [{
            "name": "c6", "scope": "x",
            "worktree_path": str(wt),
            "gate_retry_tracking": {
                "review": {
                    "consecutive_cache_uses": 1,
                    "last_verdict_sha": baseline_sha,
                    "last_run_retry_index": 0,
                },
            },
            "verify_retry_index": 1,
        }],
        "extras": {},
    }
    Path(state_file).write_text(json.dumps(st))

    change = Change.from_dict(st["changes"][0])
    gc = _FakeGateConfig({"review": True})
    profile = _FakeProfile(
        policy={"review": "cached"},
        cache_scopes={"review": ["src/**"]},
    )
    bus = _FakeEventBus()

    def exec_review():
        return GateResult("review", "pass", duration_ms=1)

    pipeline = GatePipeline(
        gc, state_file, "c6", change,
        max_retries=2, event_bus=bus, profile=profile,
    )
    pipeline.register("review", exec_review,
                      result_fields=("review_result", "gate_review_ms"))
    pipeline.run()
    pipeline.commit_results()

    # State file now has consecutive_cache_uses=0 and last_verdict_sha updated
    updated = json.loads(Path(state_file).read_text())
    tr = updated["changes"][0]["gate_retry_tracking"]["review"]
    assert tr["consecutive_cache_uses"] == 0
    assert tr["last_verdict_sha"] != baseline_sha  # got new HEAD
