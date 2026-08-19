"""End-to-end mocked test of the serial decompose path.

Validates that `run_planning_pipeline()` with the new strategy router:
  - Resolves to `serial` for a typical-sized digest.
  - Fires exactly ONE Claude call (not the 1+N+1 of the parallel path).
  - Tags the call with `strategy="serial"`.
  - Produces a plan that passes validation.
  - Records `plan_method=serial` in the enriched output.

Uses the reconstructed consumer-d digest (37 reqs, 7 domains) as the
realistic input. Claude is mocked — no network or billing.

Capability: planner-strategy-routing (decompose-replan-optimization).
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from unittest import mock

import pytest

from set_orch import planner
from set_orch.subprocess_utils import ClaudeResult


# Path to the reconstructed consumer-d digest staged earlier by the user.
# Falls back to building one if not present.
_DIMOP_DIGEST = Path("/tmp/consumer-d-digest-test")


@pytest.fixture
def dimop_project(tmp_path, monkeypatch):
    """Stage a project layout with the consumer-d digest at the canonical path.

    `run_planning_pipeline` derives `digest_dir` from `os.getcwd()`, so the
    test must chdir into a directory whose `set/orchestration/digest`
    matches the input_path.
    """
    if not _DIMOP_DIGEST.is_dir():
        pytest.skip(
            f"Reconstructed consumer-d digest not present at {_DIMOP_DIGEST}; "
            "skip the e2e mock test"
        )
    project = tmp_path / "project"
    digest_target = project / "set" / "orchestration" / "digest"
    digest_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_DIMOP_DIGEST, digest_target)
    monkeypatch.chdir(project)
    # Auto-defer the digest's unresolved ambiguities so the triage gate
    # passes. Matches how a non-interactive run is configured.
    monkeypatch.setenv("TRIAGE_AUTO_DEFER", "true")
    return digest_target


def _canned_plan_response() -> str:
    """A minimal-but-valid plan JSON the LLM would emit for the dimop digest."""
    return json.dumps({
        "phase_detected": "Phase 1: i18n + schema foundation",
        "reasoning": "Foundation changes ship first; payment depends on schema.",
        "changes": [
            {
                "name": "i18n-setup-and-migration",
                "scope": (
                    "Migrate the existing HU pages to next-intl with no locale "
                    "prefix on the root path. Includes locale detection, "
                    "messages/hu.json bootstrap, and middleware update. Tests: "
                    "GET / returns 200, /jogi 200, /megoldas 200; /en/* return "
                    "404; /api/lead unaffected. Adds e2e/i18n.spec.ts."
                ),
                "complexity": "S",
                "change_type": "foundational",
                "model": "opus",
                "has_manual_tasks": False,
                "depends_on": [],
                "phase": 1,
                "requirements": ["REQ-I18N-001", "REQ-I18N-002", "REQ-I18N-003", "REQ-I18N-004"],
                "spec_files": ["tests/e2e/i18n.spec.ts"],
                "gate_hints": {},
            },
            {
                "name": "schema-and-migration",
                "scope": (
                    "Add Product, Order, InvoiceLog Prisma models + initial "
                    "migration with seed for the single SKU. Tests: schema "
                    "round-trip, seed insert/read, OrderStatus enum. Adds "
                    "tests/schema.spec.ts."
                ),
                "complexity": "S",
                "change_type": "schema",
                "model": "sonnet",
                "has_manual_tasks": False,
                "depends_on": [],
                "phase": 1,
                "requirements": ["REQ-SCHEMA-001", "REQ-SCHEMA-002", "REQ-SCHEMA-003"],
                "spec_files": ["tests/schema.spec.ts"],
                "gate_hints": {},
            },
        ],
    })


def test_serial_path_fires_exactly_one_call(dimop_project, monkeypatch):
    """run_planning_pipeline() with auto strategy + small digest → 1 Claude call."""
    monkeypatch.delenv("SET_ORCH_PLANNER_STRATEGY", raising=False)

    # Track every run_claude_logged invocation.
    calls: list[dict] = []

    def fake_run_claude_logged(prompt, **kwargs):
        calls.append({
            "prompt_len": len(prompt) if isinstance(prompt, str) else 0,
            "purpose": kwargs.get("purpose"),
            "strategy": kwargs.get("strategy"),
            "model": kwargs.get("model"),
            "timeout": kwargs.get("timeout"),
        })
        return ClaudeResult(
            stdout=_canned_plan_response(),
            stderr="",
            exit_code=0,
            duration_ms=120000,
            input_tokens=1500,
            output_tokens=2400,
            cache_read_tokens=42000,
            cache_create_tokens=8000,
            cost_usd=0.85,
            timed_out=False,
        )

    # Patch the symbol the planner imports lazily.
    monkeypatch.setattr(
        "set_orch.subprocess_utils.run_claude_logged",
        fake_run_claude_logged,
    )

    plan = planner.run_planning_pipeline(
        input_mode="digest",
        input_path=str(dimop_project),
        state_path="",
        model="opus",
    )

    # AC: exactly one Claude call (vs 9+ for the parallel path).
    assert len(calls) == 1, f"expected 1 call, got {len(calls)}: {calls}"
    call = calls[0]

    # AC-86: the call is tagged with strategy=serial.
    assert call["strategy"] == "serial", call
    # purpose=decompose (single-call path), not decompose_brief/domain/merge.
    assert call["purpose"] == "decompose", call

    # AC-83: plan has the expected top-level keys + passes validation.
    assert "changes" in plan
    assert "phase_detected" in plan
    assert "reasoning" in plan
    assert isinstance(plan["changes"], list)
    assert len(plan["changes"]) >= 1

    # AC-84: plan_method recorded as `serial`.
    assert plan.get("plan_method") == "serial", plan.get("plan_method")


def test_parallel_path_fires_three_phases(dimop_project, monkeypatch):
    """Forcing parallel runs the 3-phase pipeline (1 brief + N domain + 1 merge)."""
    monkeypatch.setenv("SET_ORCH_PLANNER_STRATEGY", "parallel")

    purposes: list[str] = []

    def fake_run_claude_logged(prompt, **kwargs):
        purposes.append(kwargs.get("purpose", ""))
        # Return shape depends on which phase we're in.
        purpose = kwargs.get("purpose", "")
        if purpose == "decompose_brief":
            stdout = json.dumps({
                "domain_priorities": ["i18n", "schema", "payment", "checkout", "buy", "legal", "seo"],
                "resource_ownership": {"prisma/schema.prisma": "schema"},
                "cross_cutting_changes": [],
                "phasing_strategy": "Foundation first, then features.",
            })
        elif purpose == "decompose_domain":
            # Each domain returns at least one change.
            stdout = json.dumps({
                "changes": [{
                    "name": f"feat-{len(purposes)}",
                    "scope": "x" * 800,
                    "complexity": "S",
                    "change_type": "feature",
                    "model": "opus",
                    "depends_on": [],
                    "requirements": [],
                    "spec_files": ["tests/e2e/foo.spec.ts"],
                }],
            })
        elif purpose == "decompose_merge":
            stdout = _canned_plan_response()
        else:
            stdout = "{}"
        return ClaudeResult(
            stdout=stdout, stderr="", exit_code=0, duration_ms=60000,
            input_tokens=1000, output_tokens=2000,
            cache_read_tokens=40000, cache_create_tokens=10000,
            cost_usd=0.50, timed_out=False,
        )

    monkeypatch.setattr(
        "set_orch.subprocess_utils.run_claude_logged",
        fake_run_claude_logged,
    )

    plan = planner.run_planning_pipeline(
        input_mode="digest",
        input_path=str(dimop_project),
        state_path="",
        model="opus",
    )

    # 1 brief + 7 domains + 1 merge = 9 calls.
    n_brief = sum(1 for p in purposes if p == "decompose_brief")
    n_domain = sum(1 for p in purposes if p == "decompose_domain")
    n_merge = sum(1 for p in purposes if p == "decompose_merge")
    assert n_brief == 1, f"expected 1 brief, got {n_brief}: {purposes}"
    assert n_domain == 7, f"expected 7 domains, got {n_domain}: {purposes}"
    assert n_merge == 1, f"expected 1 merge, got {n_merge}: {purposes}"

    # Plan still validates and is tagged parallel.
    assert plan.get("plan_method") == "parallel"


def test_serial_call_is_tagged_in_event_payload(dimop_project, monkeypatch):
    """The LLM_CALL event payload has the strategy field (AC-86)."""
    monkeypatch.delenv("SET_ORCH_PLANNER_STRATEGY", raising=False)

    captured_events: list[dict] = []

    # Real run_claude_logged → emits to event_bus → we hook the bus.
    from set_orch import events
    orig_emit = events.event_bus.emit

    def capturing_emit(event_type, change="", data=None):
        if event_type == "LLM_CALL":
            captured_events.append({"change": change, "data": data or {}})
        return orig_emit(event_type, change=change, data=data)

    monkeypatch.setattr(events.event_bus, "emit", capturing_emit)

    # Mock run_claude (the lower-level call) to return a fake result so
    # run_claude_logged still fires its event.
    from set_orch import subprocess_utils
    fake_result = ClaudeResult(
        stdout=_canned_plan_response(), stderr="", exit_code=0,
        duration_ms=120000, input_tokens=1500, output_tokens=2400,
        cache_read_tokens=42000, cache_create_tokens=8000,
        cost_usd=0.85, timed_out=False,
    )
    monkeypatch.setattr(subprocess_utils, "run_claude", lambda *a, **kw: fake_result)

    planner.run_planning_pipeline(
        input_mode="digest",
        input_path=str(dimop_project),
        state_path="",
        model="opus",
    )

    decompose_events = [e for e in captured_events if e["data"].get("purpose") == "decompose"]
    assert len(decompose_events) == 1
    assert decompose_events[0]["data"].get("strategy") == "serial", decompose_events[0]
