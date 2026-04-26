"""Tests for ``lib/set_orch/category_resolver.py``.

Pins the contract from
``openspec/specs/change-category-resolver/spec.md``. The LLM call is
mocked at ``set_orch.category_resolver._call_llm`` for all tests so we
never hit the real API.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from set_orch.category_resolver import (
    ResolverResult,
    _compute_cache_key,
    _parse_llm_response,
    resolve_change_categories,
)
from set_orch.profile_loader import NullProfile


class _StubProfile(NullProfile):
    """Test double — overrides each hook to return a deterministic value
    so we can verify per-layer contributions without coupling tests to
    the web profile's actual patterns."""

    def __init__(
        self,
        *,
        change_type_cats: dict[str, set[str]] | None = None,
        scope_cats_for: dict[str, set[str]] | None = None,
        path_cats_rules: list[tuple[str, set[str]]] | None = None,
        req_cats_rules: dict[str, set[str]] | None = None,
        project_cats: set[str] | None = None,
        taxonomy: list[str] | None = None,
    ):
        self._change_type_cats = change_type_cats or {}
        self._scope_cats_for = scope_cats_for or {}
        self._path_cats_rules = path_cats_rules or []
        self._req_cats_rules = req_cats_rules or {}
        self._project_cats = project_cats or {"general"}
        self._taxonomy = taxonomy or [
            "general", "frontend", "auth", "api", "database",
            "payment", "scaffolding", "ci-build-test",
        ]

    def categories_from_change_type(self, change_type):
        return set(self._change_type_cats.get(change_type, set()))

    def categories_from_requirements(self, req_ids):
        out: set[str] = set()
        for rid in req_ids:
            for prefix, cats in self._req_cats_rules.items():
                if prefix in rid:
                    out |= cats
        return out

    def categories_from_paths(self, paths):
        out: set[str] = set()
        for p in paths:
            for needle, cats in self._path_cats_rules:
                if needle in p:
                    out |= cats
        return out

    def detect_scope_categories(self, scope):
        out: set[str] = set()
        for needle, cats in self._scope_cats_for.items():
            if needle in scope:
                out |= cats
        return out

    def detect_project_categories(self, project_path):
        return set(self._project_cats)

    def category_taxonomy(self):
        return list(self._taxonomy)

    def project_summary_for_classifier(self, project_path):
        return "Test project."


@pytest.fixture
def jsonl(tmp_path: Path) -> str:
    """Return a JSONL audit-log path that lives in a fresh tmp dir."""
    return str(tmp_path / "category-classifications.jsonl")


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    return tmp_path


# ─── _compute_cache_key ─────────────────────────────────────────────────


def test_cache_key_stable_across_input_order():
    """Order of req_ids/deps must NOT affect the cache key."""
    k1 = _compute_cache_key("scope", ["REQ-A", "REQ-B"], ["dep1", "dep2"])
    k2 = _compute_cache_key("scope", ["REQ-B", "REQ-A"], ["dep2", "dep1"])
    assert k1 == k2


def test_cache_key_changes_on_scope_edit():
    """Scope edit MUST invalidate cache."""
    k1 = _compute_cache_key("scope v1", [], [])
    k2 = _compute_cache_key("scope v2", [], [])
    assert k1 != k2


# ─── _parse_llm_response ────────────────────────────────────────────────


def test_parse_clean_json():
    parsed = _parse_llm_response(
        '{"categories": ["auth", "api"], "confidence": "high", "reasoning": "x"}'
    )
    assert parsed is not None
    cats, meta = parsed
    assert cats == {"auth", "api"}
    assert meta["confidence"] == "high"


def test_parse_strips_code_fences():
    """Sonnet sometimes wraps JSON in ```json ... ``` despite instructions."""
    raw = '```json\n{"categories": ["auth"], "confidence": "med", "reasoning": ""}\n```'
    parsed = _parse_llm_response(raw)
    assert parsed is not None
    cats, _ = parsed
    assert cats == {"auth"}


def test_parse_malformed_json_returns_none():
    assert _parse_llm_response("not json") is None
    assert _parse_llm_response('{"categories": "not a list"}') is None
    assert _parse_llm_response("[]") is None  # not a dict


# ─── resolve_change_categories — primary layers ─────────────────────────


def test_all_five_primary_layers_contribute(jsonl, project_path):
    """Each per-change layer feeds the union; project_state stays out
    when primary union has > 2 categories."""
    profile = _StubProfile(
        change_type_cats={"feature": {"frontend"}},
        req_cats_rules={"AUTH": {"auth"}},
        path_cats_rules=[("api/", {"api"})],
        scope_cats_for={"prisma": {"database"}},
        project_cats={"general", "frontend", "auth", "api", "database"},
    )
    with patch(
        "set_orch.category_resolver._call_llm",
        return_value=(set(), {"skipped": "test"}),
    ):
        result = resolve_change_categories(
            change_name="ch1",
            change_type="feature",
            scope="Use prisma migration",
            req_ids=["REQ-AUTH-001"],
            manifest_paths=["src/app/api/users/route.ts"],
            deps=["foundation"],
            profile=profile,
            project_path=project_path,
            audit_log_path=jsonl,
        )
    # All 5 primary layers contributed:
    assert "frontend" in result.final_categories
    assert "auth" in result.final_categories
    assert "api" in result.final_categories
    assert "database" in result.final_categories
    assert "general" in result.final_categories
    # project_state suppressed (primary union > 2)
    assert result.deterministic["signals"]["project_state"] == []


def test_project_state_fallback_engages_on_thin_signal(jsonl, project_path):
    """When per-change layers yield ≤ 2 cats (general + maybe one),
    project_state runs as fallback."""
    profile = _StubProfile(
        change_type_cats={"feature": set()},  # no phase default
        req_cats_rules={},
        path_cats_rules=[],
        scope_cats_for={},
        project_cats={"frontend", "auth", "database"},  # project is rich
    )
    with patch(
        "set_orch.category_resolver._call_llm",
        return_value=(set(), {"skipped": "test"}),
    ):
        result = resolve_change_categories(
            change_name="ch1",
            change_type="feature",
            scope="bare scope",
            req_ids=[],
            manifest_paths=[],
            deps=[],
            profile=profile,
            project_path=project_path,
            audit_log_path=jsonl,
        )
    # project_state fallback ran and added its categories
    assert "frontend" in result.final_categories
    assert "auth" in result.final_categories
    assert "database" in result.final_categories
    assert result.deterministic["signals"]["project_state"]


def test_project_state_fallback_skipped_on_strong_signal(jsonl, project_path):
    """Per-change layers produce > 2 cats → project_state is NOT
    consulted (no over-injection)."""
    profile = _StubProfile(
        change_type_cats={"feature": {"frontend", "ci-build-test"}},
        req_cats_rules={"AUTH": {"auth"}},
        project_cats={"payment", "database"},  # would over-inject
    )
    with patch(
        "set_orch.category_resolver._call_llm",
        return_value=(set(), {"skipped": "test"}),
    ):
        result = resolve_change_categories(
            change_name="ch1",
            change_type="feature",
            scope="x",
            req_ids=["REQ-AUTH-001"],
            manifest_paths=[],
            deps=[],
            profile=profile,
            project_path=project_path,
            audit_log_path=jsonl,
        )
    assert "payment" not in result.final_categories
    assert "database" not in result.final_categories
    assert result.deterministic["signals"]["project_state"] == []


# ─── LLM additive layer ─────────────────────────────────────────────────


def test_llm_adds_implicit_category(jsonl, project_path):
    """LLM proposes a category the deterministic layers missed → unioned in."""
    profile = _StubProfile(
        change_type_cats={"feature": {"frontend"}},
        scope_cats_for={},
    )
    with patch(
        "set_orch.category_resolver._call_llm",
        return_value=({"payment", "frontend"}, {
            "model": "claude-sonnet-4-6",
            "duration_ms": 1200,
            "cost_usd": 0.005,
            "confidence": "high",
            "reasoning": "checkout implies payment",
        }),
    ):
        result = resolve_change_categories(
            change_name="ch1",
            change_type="feature",
            scope="Add checkout flow",
            req_ids=[],
            manifest_paths=[],
            deps=[],
            profile=profile,
            project_path=project_path,
            audit_log_path=jsonl,
        )
    assert "payment" in result.final_categories  # LLM added
    assert "frontend" in result.final_categories  # deterministic
    assert "payment" in result.delta["added_by_llm"]


def test_llm_cannot_remove_deterministic_category(jsonl, project_path):
    """Even if LLM omits a category, deterministic preserves it (union semantics)."""
    profile = _StubProfile(
        change_type_cats={"feature": {"frontend"}},
        scope_cats_for={"login": {"auth"}},
    )
    with patch(
        "set_orch.category_resolver._call_llm",
        return_value=(set(), {  # LLM returns empty
            "model": "claude-sonnet-4-6",
            "duration_ms": 1100,
            "confidence": "low",
            "reasoning": "weak signal",
        }),
    ):
        result = resolve_change_categories(
            change_name="ch1",
            change_type="feature",
            scope="Add login form",
            req_ids=[],
            manifest_paths=[],
            deps=[],
            profile=profile,
            project_path=project_path,
            audit_log_path=jsonl,
        )
    # Deterministic captured auth via scope keyword; LLM didn't remove it
    assert "auth" in result.final_categories
    assert "frontend" in result.final_categories


def test_llm_returns_unknown_category_filtered(jsonl, project_path):
    """A category not in the profile's taxonomy → filtered out, logged as uncovered."""
    profile = _StubProfile(
        change_type_cats={"feature": {"frontend"}},
        taxonomy=["general", "frontend", "auth", "api", "database"],  # no rate-limiting
    )
    with patch(
        "set_orch.category_resolver._call_llm",
        return_value=({"frontend", "rate-limiting"}, {
            "model": "claude-sonnet-4-6",
            "duration_ms": 1500,
        }),
    ):
        result = resolve_change_categories(
            change_name="ch1",
            change_type="feature",
            scope="Add rate-limited endpoint",
            req_ids=[],
            manifest_paths=[],
            deps=[],
            profile=profile,
            project_path=project_path,
            audit_log_path=jsonl,
        )
    assert "rate-limiting" not in result.final_categories  # filtered
    assert "rate-limiting" in result.uncovered_categories  # logged


# ─── Cache behavior ─────────────────────────────────────────────────────


def test_cache_hit_skips_llm_call(jsonl, project_path):
    """Same scope/req_ids/deps → cache hit → no LLM invocation."""
    profile = _StubProfile(change_type_cats={"feature": {"frontend"}})

    # First call: cache miss, LLM is called.
    with patch("set_orch.category_resolver._call_llm") as mock_call:
        mock_call.return_value = (
            {"frontend", "auth"},
            {"model": "claude-sonnet-4-6", "duration_ms": 1000},
        )
        first = resolve_change_categories(
            change_name="ch1",
            change_type="feature",
            scope="login flow",
            req_ids=["REQ-AUTH-001"],
            manifest_paths=[],
            deps=[],
            profile=profile,
            project_path=project_path,
            audit_log_path=jsonl,
        )
        assert mock_call.call_count == 1
        assert first.cache_hit is False

    # Second call with identical inputs: cache hit, LLM NOT called.
    with patch("set_orch.category_resolver._call_llm") as mock_call:
        second = resolve_change_categories(
            change_name="ch1-retry",  # change name differs but cache key is on scope
            change_type="feature",
            scope="login flow",
            req_ids=["REQ-AUTH-001"],
            manifest_paths=[],
            deps=[],
            profile=profile,
            project_path=project_path,
            audit_log_path=jsonl,
        )
        assert mock_call.call_count == 0
        assert second.cache_hit is True
        assert "auth" in second.final_categories


def test_cache_miss_on_scope_edit(jsonl, project_path):
    """Editing scope text → fresh LLM call."""
    profile = _StubProfile()
    with patch("set_orch.category_resolver._call_llm") as mock_call:
        mock_call.return_value = (set(), {"model": "claude-sonnet-4-6", "duration_ms": 100})
        resolve_change_categories(
            change_name="ch", change_type="feature", scope="v1",
            req_ids=[], manifest_paths=[], deps=[],
            profile=profile, project_path=project_path, audit_log_path=jsonl,
        )
        resolve_change_categories(
            change_name="ch", change_type="feature", scope="v2",
            req_ids=[], manifest_paths=[], deps=[],
            profile=profile, project_path=project_path, audit_log_path=jsonl,
        )
        assert mock_call.call_count == 2  # both missed


# ─── Failure modes ──────────────────────────────────────────────────────


def test_llm_timeout_falls_back_to_deterministic(jsonl, project_path):
    """LLM timeout → result has empty LLM cats + error meta, deterministic preserved."""
    profile = _StubProfile(change_type_cats={"feature": {"frontend"}})
    with patch(
        "set_orch.category_resolver._call_llm",
        return_value=(set(), {"model": "claude-sonnet-4-6", "error": "timeout", "duration_ms": 8000}),
    ):
        result = resolve_change_categories(
            change_name="ch", change_type="feature", scope="x",
            req_ids=[], manifest_paths=[], deps=[],
            profile=profile, project_path=project_path, audit_log_path=jsonl,
        )
    assert "frontend" in result.final_categories  # deterministic intact
    assert result.audit_record["llm"]["error"] == "timeout"


def test_llm_disabled_skips_call(jsonl, project_path):
    """Profile with llm_classifier_model=None → resolver skips LLM."""
    class _NoLLM(_StubProfile):
        @property
        def llm_classifier_model(self) -> str | None:
            return None

    profile = _NoLLM(change_type_cats={"feature": {"frontend"}})
    with patch("set_orch.category_resolver.run_claude_logged") as mock_run:
        result = resolve_change_categories(
            change_name="ch", change_type="feature", scope="x",
            req_ids=[], manifest_paths=[], deps=[],
            profile=profile, project_path=project_path, audit_log_path=jsonl,
        )
        assert mock_run.call_count == 0  # subprocess never called
    assert "frontend" in result.final_categories


# ─── Audit record ───────────────────────────────────────────────────────


def test_audit_record_appended_per_call(jsonl, project_path):
    profile = _StubProfile(change_type_cats={"feature": {"frontend"}})
    with patch(
        "set_orch.category_resolver._call_llm",
        return_value=({"frontend"}, {"model": "claude-sonnet-4-6", "duration_ms": 100}),
    ):
        resolve_change_categories(
            change_name="ch1", change_type="feature", scope="a",
            req_ids=[], manifest_paths=[], deps=[],
            profile=profile, project_path=project_path, audit_log_path=jsonl,
        )
        resolve_change_categories(
            change_name="ch2", change_type="feature", scope="b",
            req_ids=[], manifest_paths=[], deps=[],
            profile=profile, project_path=project_path, audit_log_path=jsonl,
        )

    lines = open(jsonl).read().strip().split("\n")
    assert len(lines) == 2
    rec1 = json.loads(lines[0])
    rec2 = json.loads(lines[1])
    assert rec1["change_name"] == "ch1"
    assert rec2["change_name"] == "ch2"
    assert rec1["cache_key"] != rec2["cache_key"]


def test_audit_record_schema_matches_design(jsonl, project_path):
    """Audit record must include the documented top-level fields."""
    profile = _StubProfile(change_type_cats={"feature": {"frontend"}})
    with patch(
        "set_orch.category_resolver._call_llm",
        return_value=({"frontend", "scaffolding"}, {
            "model": "claude-sonnet-4-6",
            "duration_ms": 1200,
            "cost_usd": 0.005,
            "confidence": "high",
            "reasoning": "test",
        }),
    ):
        result = resolve_change_categories(
            change_name="ch1", change_type="feature", scope="test scope",
            req_ids=["REQ-NAV-001"], manifest_paths=["src/app/page.tsx"], deps=[],
            profile=profile, project_path=project_path, audit_log_path=jsonl,
        )

    rec = result.audit_record
    for key in ("ts", "change_name", "cache_key", "cache_hit",
                "change_type", "deterministic", "llm", "final",
                "delta", "uncovered_categories"):
        assert key in rec, f"audit record missing {key}"
    assert "categories" in rec["deterministic"]
    assert "signals" in rec["deterministic"]
    for layer in ("change_type", "requirements", "paths", "scope",
                  "deps", "insights", "project_state"):
        assert layer in rec["deterministic"]["signals"]


def test_concurrent_dispatch_appends_safely(jsonl, project_path):
    """Concurrent resolver invocations produce well-formed JSONL."""
    profile = _StubProfile(change_type_cats={"feature": {"frontend"}})

    def _runner(i: int):
        with patch(
            "set_orch.category_resolver._call_llm",
            return_value=(set(), {"model": "x", "duration_ms": 1}),
        ):
            resolve_change_categories(
                change_name=f"ch{i}", change_type="feature",
                scope=f"scope{i}", req_ids=[], manifest_paths=[], deps=[],
                profile=profile, project_path=project_path, audit_log_path=jsonl,
            )

    threads = [threading.Thread(target=_runner, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = open(jsonl).read().strip().split("\n")
    assert len(lines) == 8
    for line in lines:
        json.loads(line)  # must parse


# ─── ResolverResult shape ───────────────────────────────────────────────


def test_resolver_result_is_dataclass(jsonl, project_path):
    profile = _StubProfile(change_type_cats={"feature": {"frontend"}})
    with patch(
        "set_orch.category_resolver._call_llm",
        return_value=(set(), {"skipped": "test"}),
    ):
        result = resolve_change_categories(
            change_name="ch", change_type="feature", scope="x",
            req_ids=[], manifest_paths=[], deps=[],
            profile=profile, project_path=project_path, audit_log_path=jsonl,
        )
    assert isinstance(result, ResolverResult)
    assert isinstance(result.final_categories, set)
    assert isinstance(result.deterministic, dict)
    assert isinstance(result.llm, dict)
    assert isinstance(result.cache_hit, bool)
    assert isinstance(result.delta, dict)
    assert isinstance(result.uncovered_categories, list)
    assert isinstance(result.audit_record, dict)
