"""Gate profiles — per-change-type verification gate configuration.

Resolves which gates run for each change based on:
1. Built-in defaults (keyed by change_type)
2. Project-type plugin overrides
3. Per-change explicit overrides from plan
4. Orchestration directive overrides
"""

from dataclasses import dataclass, replace
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class GateConfig:
    """Resolved gate configuration for a single change."""

    # Pre-merge gates (in handle_change_done)
    build: str = "run"
    test: str = "run"
    test_files_required: bool = True
    e2e: str = "run"
    scope_check: str = "run"
    lint: str = "run"
    review: str = "run"
    spec_verify: str = "run"
    rules: str = "run"

    # Post-merge gates (in merger.py)
    smoke: str = "run"

    # Optional overrides (None = use global)
    max_retries: Optional[int] = None
    review_model: Optional[str] = None
    review_extra_retries: int = 3  # extra retries for review gate beyond max_retries

    def should_run(self, gate_name: str) -> bool:
        """Whether a gate should execute at all."""
        val = getattr(self, gate_name, "run")
        return val in ("run", "warn", "soft")

    def is_blocking(self, gate_name: str) -> bool:
        """Whether gate failure should block merge."""
        val = getattr(self, gate_name, "run")
        return val == "run"

    def is_warn_only(self, gate_name: str) -> bool:
        """Whether gate failure is warning-only (non-blocking)."""
        val = getattr(self, gate_name, "run")
        return val in ("warn", "soft")


# ── Built-in profiles per change_type ──────────────────────────────

BUILTIN_GATE_PROFILES: dict[str, GateConfig] = {
    # Infrastructure: test framework, build config, CI/CD.
    # No app to build/test/smoke yet. Only scope + review + rules.
    "infrastructure": GateConfig(
        build="skip",
        test="skip",
        test_files_required=False,
        e2e="skip",
        scope_check="run",
        lint="skip",
        review="run",
        spec_verify="soft",
        rules="run",
        smoke="skip",
    ),
    # Schema: DB migrations, model definitions.
    # Build may work, tests warn-only, no e2e/smoke.
    "schema": GateConfig(
        build="run",
        test="warn",
        test_files_required=False,
        e2e="skip",
        scope_check="run",
        lint="warn",
        review="run",
        spec_verify="run",
        rules="run",
        smoke="skip",
    ),
    # Foundational: auth, shared types, base components.
    # Build + test expected, no e2e or smoke by default.
    "foundational": GateConfig(
        build="run",
        test="run",
        test_files_required=True,
        e2e="skip",
        scope_check="run",
        lint="run",
        review="run",
        spec_verify="run",
        rules="run",
        smoke="skip",
    ),
    # Feature: user-facing functionality. Full pipeline.
    "feature": GateConfig(
        build="run",
        test="run",
        test_files_required=True,
        e2e="run",
        scope_check="run",
        review="run",
        spec_verify="run",
        rules="run",
        smoke="run",
    ),
    # Cleanup-before: refactoring before features.
    # Build + warn-only test, no e2e/smoke.
    "cleanup-before": GateConfig(
        build="run",
        test="warn",
        test_files_required=False,
        e2e="skip",
        scope_check="run",
        lint="warn",
        review="run",
        spec_verify="soft",
        rules="run",
        smoke="skip",
    ),
    # Cleanup-after: dead code, cosmetic. Lightest profile.
    "cleanup-after": GateConfig(
        build="run",
        test="warn",
        test_files_required=False,
        e2e="skip",
        scope_check="run",
        lint="skip",
        review="skip",
        spec_verify="soft",
        rules="skip",
        smoke="skip",
    ),
}

# Default for unknown change_type — feature-equivalent (all "run").
DEFAULT_GATE_PROFILE = GateConfig()


def resolve_gate_config(
    change,
    profile=None,
    directives: dict | None = None,
) -> GateConfig:
    """Resolve the gate configuration for a change.

    Resolution chain (later layers override earlier):
    1. Built-in profile for change_type
    2. Profile plugin gate_overrides()
    3. Per-change skip flags (skip_test, skip_review) + gate_hints
    4. Orchestration directive overrides (gate_overrides nested dict)
    """
    change_type = getattr(change, "change_type", None) or "feature"

    # Step 1: Built-in defaults
    config = replace(BUILTIN_GATE_PROFILES.get(change_type, DEFAULT_GATE_PROFILE))

    # Step 2: Profile plugin overrides
    if profile is not None and hasattr(profile, "gate_overrides"):
        overrides = profile.gate_overrides(change_type)
        if overrides:
            for key, val in overrides.items():
                if hasattr(config, key):
                    setattr(config, key, val)

    # Step 3: Per-change explicit overrides
    if getattr(change, "skip_test", False):
        config.test = "skip"
        config.test_files_required = False
    if getattr(change, "skip_review", False):
        config.review = "skip"

    gate_hints = getattr(change, "gate_hints", None) or {}
    for key, val in gate_hints.items():
        if hasattr(config, key):
            setattr(config, key, val)

    # Step 4: Directive overrides (nested dict: {change_type: {gate: mode}})
    if directives:
        gate_overrides_dict = directives.get("gate_overrides", {})
        if isinstance(gate_overrides_dict, dict):
            type_overrides = gate_overrides_dict.get(change_type, {})
            if isinstance(type_overrides, dict):
                for key, val in type_overrides.items():
                    if hasattr(config, key):
                        setattr(config, key, val)

    change_name = getattr(change, "name", "?")
    logger.debug(
        "Gate config for %s (type=%s): build=%s test=%s e2e=%s lint=%s review=%s smoke=%s spec_verify=%s",
        change_name, change_type,
        config.build, config.test, config.e2e, config.lint, config.review, config.smoke,
        config.spec_verify,
    )
    return config
