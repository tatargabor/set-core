"""Unified model-selection resolver for set-core.

Every Python call site that picks an LLM model SHOULD route through
``resolve_model(role)``. The helper implements a 5-tier resolution
chain: CLI override → ENV var → orchestration.yaml::models.<role> →
profile.model_for(role) → DIRECTIVE_DEFAULTS["models"][<role>].

Trigger sub-roles use a dotted path (e.g. ``trigger.integration_failed``).
ENV var names map dots to underscores and uppercase the path
(``SET_ORCH_MODEL_TRIGGER_INTEGRATION_FAILED``).

Returned names are validated against ``MODEL_NAME_RE`` from config.py.
Invalid values from any source raise ``ValueError`` naming the source
tier and the offending value.

Presets (used by the ``--model-profile`` CLI shortcut):
  - ``default``        — use DIRECTIVE_DEFAULTS as-is (no overrides)
  - ``all-opus-4-6``   — every role → opus-4-6
  - ``all-opus-4-7``   — every role → opus-4-7
  - ``cost-optimized`` — agent/digest/decompose_*/supervisor/canary →
                         sonnet; review/spec_verify/classifier → haiku;
                         escalations and triggers → sonnet
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

from .config import DIRECTIVE_DEFAULTS, MODEL_NAME_RE

logger = logging.getLogger(__name__)


# Compiled regex for validating short model names from any source.
_MODEL_NAME_RE_COMPILED = re.compile(MODEL_NAME_RE)


# Presets selectable via ``--model-profile``. Keys mirror every leaf in
# DIRECTIVE_DEFAULTS["models"] (excluding the ``trigger`` sub-dict, which
# is filled from the trigger entries below).
_ROLE_KEYS_FLAT = (
    "agent", "agent_small", "digest",
    "decompose_brief", "decompose_domain", "decompose_merge",
    "review", "review_escalation",
    "spec_verify", "spec_verify_escalation",
    "classifier", "supervisor", "canary",
)

_TRIGGER_SUBKEYS = (
    "integration_failed", "non_periodic_checkpoint",
    "terminal_state", "default",
)


def _all_opus_preset(model: str) -> dict[str, Any]:
    flat = {role: model for role in _ROLE_KEYS_FLAT}
    flat["trigger"] = {sub: model for sub in _TRIGGER_SUBKEYS}
    return flat


PRESETS: dict[str, dict[str, Any]] = {
    "default": dict(DIRECTIVE_DEFAULTS["models"]),
    "all-opus-4-6": _all_opus_preset("opus-4-6"),
    "all-opus-4-7": _all_opus_preset("opus-4-7"),
    "cost-optimized": {
        "agent": "sonnet",
        "agent_small": "haiku",
        "digest": "sonnet",
        "decompose_brief": "sonnet",
        "decompose_domain": "sonnet",
        "decompose_merge": "sonnet",
        "review": "haiku",
        "review_escalation": "sonnet",
        "spec_verify": "haiku",
        "spec_verify_escalation": "sonnet",
        "classifier": "haiku",
        "supervisor": "sonnet",
        "canary": "sonnet",
        "trigger": {
            "integration_failed": "sonnet",
            "non_periodic_checkpoint": "sonnet",
            "terminal_state": "sonnet",
            "default": "sonnet",
        },
    },
}


def list_role_keys() -> list[str]:
    """Return every fully-qualified role name (flat + trigger.<sub>)."""
    keys = list(_ROLE_KEYS_FLAT)
    keys.extend(f"trigger.{sub}" for sub in _TRIGGER_SUBKEYS)
    return keys


def _validate(value: Any, *, source: str, role: str) -> str:
    """Validate `value` is a valid short model name; raise ValueError if not."""
    if not isinstance(value, str) or not _MODEL_NAME_RE_COMPILED.match(value):
        raise ValueError(
            f"Invalid model name from {source} for role '{role}': "
            f"{value!r}. Allowed: haiku, sonnet, opus, opus-4-6, "
            f"opus-4-7, sonnet-1m, opus-1m, opus-4-6-1m, opus-4-7-1m."
        )
    return value


def _env_var_name(role: str) -> str:
    """Convert role name to its ENV var name.

    Examples:
      "agent"                       → "SET_ORCH_MODEL_AGENT"
      "trigger.integration_failed"  → "SET_ORCH_MODEL_TRIGGER_INTEGRATION_FAILED"
    """
    return "SET_ORCH_MODEL_" + role.replace(".", "_").upper()


def _read_env(role: str) -> Optional[str]:
    val = os.environ.get(_env_var_name(role))
    return val if val else None


def _read_yaml_models(project_dir: str) -> dict[str, Any]:
    """Read the `models:` block from orchestration.yaml.

    Resolution order: project_dir/.claude/orchestration.yaml first, then
    project_dir/orchestration.yaml. Returns the parsed `models` dict, or
    an empty dict if neither file exists / read fails / no `models:` key.
    """
    cwd = Path(project_dir)
    candidates = [
        cwd / ".claude" / "orchestration.yaml",
        cwd / "orchestration.yaml",
        cwd / "set" / "orchestration" / "config.yaml",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            import yaml as _yaml
            with open(path) as _fh:
                data = _yaml.safe_load(_fh) or {}
        except Exception:
            logger.warning(
                "Failed to read orchestration yaml at %s for model resolution",
                path,
                exc_info=True,
            )
            return {}
        if not isinstance(data, dict):
            return {}
        models = data.get("models")
        return models if isinstance(models, dict) else {}
    return {}


_LEGACY_DIRECTIVE_MAP: dict[str, str] = {
    "agent": "default_model",
    "digest": "summarize_model",
    "review": "review_model",
}

# Process-wide one-shot deprecation tracker so we don't spam logs.
_legacy_warned: set[str] = set()


def _read_legacy_directive(project_dir: str, role: str) -> Optional[str]:
    """Backwards-compat: when models.<role> is unset but the legacy flat
    directive is, return the legacy value with a one-shot DEPRECATION
    warning. Only `agent`, `digest`, `review` have legacy mappings.
    """
    legacy_key = _LEGACY_DIRECTIVE_MAP.get(role)
    if not legacy_key:
        return None
    cwd = Path(project_dir)
    candidates = [
        cwd / ".claude" / "orchestration.yaml",
        cwd / "orchestration.yaml",
        cwd / "set" / "orchestration" / "config.yaml",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            import yaml as _yaml
            with open(path) as _fh:
                data = _yaml.safe_load(_fh) or {}
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        legacy_val = data.get(legacy_key)
        if isinstance(legacy_val, str) and legacy_val:
            if legacy_key not in _legacy_warned:
                _legacy_warned.add(legacy_key)
                logger.warning(
                    "Directive '%s' is DEPRECATED — set 'models.%s' "
                    "in orchestration.yaml instead. Honoring legacy "
                    "value %r for now.",
                    legacy_key, role, legacy_val,
                )
            return legacy_val
        return None
    return None


def _read_yaml(project_dir: str, role: str) -> Optional[str]:
    """Read role from orchestration.yaml, including legacy fallback."""
    models = _read_yaml_models(project_dir)
    # Walk dotted path
    cur: Any = models
    for part in role.split("."):
        if not isinstance(cur, dict):
            cur = None
            break
        cur = cur.get(part)
    if isinstance(cur, str) and cur:
        return cur
    # Fallback to legacy flat directive when models.<role> unset
    return _read_legacy_directive(project_dir, role)


def _read_profile(project_dir: str, role: str) -> Optional[str]:
    """Consult profile.model_for(role). Profile-load failure → None."""
    try:
        from .profile_loader import load_profile
        profile = load_profile(project_dir)
    except Exception:
        logger.warning(
            "Profile load failed in resolve_model(%r); "
            "skipping profile override",
            role,
            exc_info=True,
        )
        return None
    try:
        return profile.model_for(role)
    except Exception:
        logger.warning(
            "profile.model_for(%r) raised; treating as no override",
            role,
            exc_info=True,
        )
        return None


def _read_defaults(role: str) -> Optional[str]:
    """Look up the role in DIRECTIVE_DEFAULTS["models"], walking dotted paths."""
    cur: Any = DIRECTIVE_DEFAULTS.get("models", {})
    for part in role.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur if isinstance(cur, str) else None


def resolve_model(
    role: str,
    *,
    project_dir: str = ".",
    cli_override: Optional[str] = None,
) -> str:
    """Resolve the model name for a given role.

    See module docstring for the resolution chain. Returns a validated
    short model name. Raises ValueError on invalid input from any source
    or on unknown role.
    """
    # Tier 1: CLI override
    if cli_override is not None:
        return _validate(cli_override, source="CLI", role=role)

    # Tier 2: ENV var
    env_val = _read_env(role)
    if env_val is not None:
        return _validate(env_val, source="ENV", role=role)

    # Tier 3: orchestration.yaml
    yaml_val = _read_yaml(project_dir, role)
    if yaml_val is not None:
        return _validate(yaml_val, source="orchestration.yaml", role=role)

    # Tier 4: profile.model_for
    profile_val = _read_profile(project_dir, role)
    if profile_val is not None:
        return _validate(profile_val, source="profile.model_for", role=role)

    # Tier 5: DIRECTIVE_DEFAULTS
    default_val = _read_defaults(role)
    if default_val is not None:
        return _validate(default_val, source="DIRECTIVE_DEFAULTS", role=role)

    raise ValueError(
        f"Unknown model role {role!r}: no value supplied at any tier "
        f"and no DIRECTIVE_DEFAULTS entry. Valid roles: "
        f"{', '.join(list_role_keys())}"
    )
