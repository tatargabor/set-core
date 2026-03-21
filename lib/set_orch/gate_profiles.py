"""Gate profiles — per-change-type verification gate configuration.

Resolves which gates run for each change based on:
1. Universal defaults for all gate types
2. Universal per-change_type defaults
3. Profile-registered gate defaults
4. Profile gate_overrides()
5. Per-change explicit overrides from plan
6. Orchestration directive overrides
"""

from typing import Optional
import logging

logger = logging.getLogger(__name__)


class GateConfig:
    """Resolved gate configuration for a single change.

    Stores gate modes as a dict[str, str] supporting arbitrary gate names.
    Non-gate attributes (test_files_required, max_retries, etc.) are direct attrs.
    """

    def __init__(self, gates: dict[str, str] | None = None, **kwargs):
        self._gates: dict[str, str] = dict(gates) if gates else {}
        self.test_files_required: bool = kwargs.get("test_files_required", True)
        self.max_retries: Optional[int] = kwargs.get("max_retries")
        self.review_model: Optional[str] = kwargs.get("review_model")
        self.review_extra_retries: int = kwargs.get("review_extra_retries", 3)

    def should_run(self, gate_name: str) -> bool:
        """Whether a gate should execute at all."""
        val = self._gates.get(gate_name, "run")
        return val in ("run", "warn", "soft")

    def is_blocking(self, gate_name: str) -> bool:
        """Whether gate failure should block merge."""
        return self._gates.get(gate_name, "run") == "run"

    def is_warn_only(self, gate_name: str) -> bool:
        """Whether gate failure is warning-only (non-blocking)."""
        val = self._gates.get(gate_name, "run")
        return val in ("warn", "soft")

    def get(self, gate_name: str, default: str = "run") -> str:
        """Get gate mode by name."""
        return self._gates.get(gate_name, default)

    def set(self, gate_name: str, mode: str) -> None:
        """Set gate mode by name."""
        self._gates[gate_name] = mode

    def gate_names(self) -> list[str]:
        """Return all configured gate names."""
        return list(self._gates.keys())


# ── Universal defaults per change_type (universal gates only) ──────

UNIVERSAL_DEFAULTS: dict[str, dict[str, str]] = {
    "infrastructure": {
        "build": "skip",
        "test": "skip",
        "scope_check": "run",
        "test_files": "skip",
        "review": "run",
        "rules": "warn",
        "spec_verify": "soft",
    },
    "schema": {
        "build": "run",
        "test": "warn",
        "scope_check": "run",
        "test_files": "run",
        "review": "run",
        "rules": "run",
        "spec_verify": "run",
    },
    "foundational": {
        "build": "run",
        "test": "run",
        "scope_check": "run",
        "test_files": "run",
        "review": "run",
        "rules": "run",
        "spec_verify": "run",
    },
    "feature": {
        "build": "run",
        "test": "run",
        "scope_check": "run",
        "test_files": "run",
        "review": "run",
        "rules": "run",
        "spec_verify": "run",
    },
    "cleanup-before": {
        "build": "run",
        "test": "warn",
        "scope_check": "run",
        "test_files": "run",
        "review": "run",
        "rules": "run",
        "spec_verify": "soft",
    },
    "cleanup-after": {
        "build": "run",
        "test": "warn",
        "scope_check": "run",
        "test_files": "run",
        "review": "skip",
        "rules": "skip",
        "spec_verify": "soft",
    },
}

# Non-gate attributes per change_type
_CHANGE_TYPE_ATTRS: dict[str, dict] = {
    "infrastructure": {"test_files_required": False},
    "schema": {"test_files_required": False},
    "cleanup-before": {"test_files_required": False},
    "cleanup-after": {"test_files_required": False},
}


def resolve_gate_config(
    change,
    profile=None,
    directives: dict | None = None,
) -> GateConfig:
    """Resolve the gate configuration for a change.

    Resolution chain (later layers override earlier):
    1. Universal gate defaults (all "run")
    2. Universal per-change_type defaults
    3. Profile-registered gate defaults (register_gates)
    4. Profile gate_overrides()
    5. Per-change skip flags + gate_hints
    6. Orchestration directive overrides
    """
    change_type = getattr(change, "change_type", None) or "feature"

    # Step 1: Start with universal gates all "run"
    gates: dict[str, str] = {
        "build": "run", "test": "run", "scope_check": "run",
        "test_files": "run", "review": "run", "rules": "run",
        "spec_verify": "run",
    }

    # Step 2: Apply universal change_type defaults
    gates.update(UNIVERSAL_DEFAULTS.get(change_type, {}))

    # Non-gate attrs from change_type
    type_attrs = _CHANGE_TYPE_ATTRS.get(change_type, {})

    # Step 3: Add profile-registered gate defaults
    if profile is not None and hasattr(profile, "register_gates"):
        try:
            for gd in profile.register_gates():
                if gd.phase != "pre-merge":
                    continue
                gates[gd.name] = gd.defaults.get(change_type, "run")
        except Exception:
            logger.warning("Failed to load profile gates", exc_info=True)

    # Step 4: Profile gate_overrides()
    if profile is not None and hasattr(profile, "gate_overrides"):
        overrides = profile.gate_overrides(change_type)
        if overrides:
            for key, val in overrides.items():
                if key in ("test_files_required", "max_retries", "review_model", "review_extra_retries"):
                    type_attrs[key] = val
                else:
                    gates[key] = val

    config = GateConfig(gates=gates, **type_attrs)

    # Step 5: Per-change explicit overrides
    if getattr(change, "skip_test", False):
        config.set("test", "skip")
        config.test_files_required = False
    if getattr(change, "skip_review", False):
        config.set("review", "skip")

    gate_hints = getattr(change, "gate_hints", None) or {}
    for key, val in gate_hints.items():
        if key in ("test_files_required", "max_retries", "review_model", "review_extra_retries"):
            setattr(config, key, val)
        else:
            config.set(key, val)

    # Step 6: Directive overrides (nested dict: {change_type: {gate: mode}})
    if directives:
        gate_overrides_dict = directives.get("gate_overrides", {})
        if isinstance(gate_overrides_dict, dict):
            type_overrides = gate_overrides_dict.get(change_type, {})
            if isinstance(type_overrides, dict):
                for key, val in type_overrides.items():
                    if key in ("test_files_required", "max_retries", "review_model", "review_extra_retries"):
                        setattr(config, key, val)
                    else:
                        config.set(key, val)

    change_name = getattr(change, "name", "?")
    logger.debug(
        "Gate config for %s (type=%s): %s",
        change_name, change_type,
        {k: v for k, v in sorted(config._gates.items())},
    )
    return config
