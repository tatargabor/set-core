from __future__ import annotations

"""Orchestration configuration: directives, duration, hashing, input resolution.

Migrated from: lib/orchestration/utils.sh (parse_directives, resolve_directives,
load_config_file, parse_duration, format_duration, brief_hash, find_input,
find_openspec_dir, parse_next_items, auto_detect_test_command)
"""

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict, fields
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ─── Directive Defaults ─────────────────────────────────────────────
# Migrated from: bin/set-orchestrate L39-70 (DEFAULT_* constants)

# Single source of truth for the validator regex covering every short
# model name accepted by set-core. Defined here so model_config.py and
# the per-key validators can share it.
MODEL_NAME_RE: str = (
    r"^(haiku|sonnet|opus|sonnet-1m|opus-1m"
    r"|opus-4-6|opus-4-7|opus-4-6-1m|opus-4-7-1m)$"
)

# Default model assignment for every orchestration touch point.
# `agent` is the per-change agent that runs ralph/claude inside a
# worktree. The remaining roles cover orchestrator-side LLM calls and
# supervisor/canary checks. Trigger sub-dict maps trigger types to the
# model used when that trigger fires.
#
# IMPORTANT: `agent` default is `opus-4-6` (NOT `opus`, which aliases
# to `opus-4-7`). This is the new framework default introduced by the
# `model-config-unified` change. Operators wanting the prior behavior
# set `models.agent: opus-4-7` (or use `--model-profile all-opus-4-7`).
_DEFAULT_MODELS: dict[str, Any] = {
    "agent": "opus-4-6",
    "agent_small": "sonnet",
    "digest": "opus-4-6",
    "decompose_brief": "opus-4-6",
    "decompose_domain": "opus-4-6",
    "decompose_merge": "opus-4-6",
    "review": "sonnet",
    "review_escalation": "opus-4-6",
    "spec_verify": "sonnet",
    "spec_verify_escalation": "opus-4-6",
    "classifier": "sonnet",
    "supervisor": "sonnet",
    "canary": "sonnet",
    "trigger": {
        "integration_failed": "opus-4-6",
        "non_periodic_checkpoint": "opus-4-6",
        "terminal_state": "opus-4-6",
        "default": "sonnet",
    },
}


DIRECTIVE_DEFAULTS: dict[str, Any] = {
    "max_parallel": 1,
    "merge_policy": "eager",
    "checkpoint_every": 0,
    "test_command": "",
    "notification": "desktop",
    "token_budget": 0,
    "pause_on_exit": False,
    "auto_replan": False,
    "review_before_merge": True,
    "test_timeout": 600,
    # verify-gate-resilience-fixes Phase 3: raised 8 → 12.
    # Empirical: order-cancellation-and-returns retried 9 times before
    # convergence in craftbrew-run-20260423-2223; 12 leaves slack.
    "max_verify_retries": 12,
    "summarize_model": "haiku",
    "review_model": "opus",
    "default_model": "opus",
    "smoke_command": "",
    "smoke_timeout": 120,
    "smoke_blocking": True,
    "smoke_fix_token_budget": 500000,
    "smoke_fix_max_turns": 15,
    "smoke_fix_max_retries": 3,
    "smoke_health_check_url": "",
    "smoke_health_check_timeout": 30,
    "smoke_dev_server_command": "",
    "monitor_idle_timeout": 1800,
    "merge_timeout": 1800,
    "post_merge_command": "",
    # DEPRECATED (verify-gate-resilience-fixes): redundant with
    # `per_change_token_runaway_threshold`. Still parsed for backward compat
    # but ignored at runtime — engine emits a deprecation WARNING at startup
    # if set in orchestration.yaml. Operators should migrate to
    # `per_change_token_runaway_threshold` (50M default).
    "token_hard_limit": 20000000,
    "events_log": True,
    "events_max_size": 1048576,
    "watchdog_timeout": None,
    "watchdog_loop_threshold": None,
    "max_tokens_per_change": None,
    "context_pruning": True,
    "plan_approval": False,
    "checkpoint_auto_approve": False,
    "plan_method": "api",
    "model_routing": "off",
    "team_mode": False,
    "post_phase_audit": True,
    "hook_pre_dispatch": None,
    "hook_post_verify": None,
    "hook_pre_merge": None,
    "hook_post_merge": None,
    "hook_on_fail": None,
    "milestones_enabled": False,
    "milestones_dev_server": None,
    "milestones_base_port": 3100,
    "milestones_max_worktrees": 3,
    "e2e_port_base": None,
    "gate_overrides": {},
    "discord": None,
    "completion_timeout": 300,
    # fix-replan-stuck-gate-and-decomposer: per-change stuck-loop circuit breaker.
    # After N consecutive `loop_status=stuck` exits with an identical
    # last_gate_fingerprint, the change is hard-failed and escalated to fix-iss.
    # Phase 3 (verify-gate-resilience-fixes): raised 3 → 5. False-positive
    # stuck detections on planner-blamed (but actually-progressing) work seen
    # in 2 runs — 5 gives more headroom.
    "max_stuck_loops": 5,
    # Per-change token-runaway circuit breaker. If input_tokens grow by more than
    # this delta without the gate fingerprint changing, mark failed:token_runaway.
    # Must match the engine.py @dataclass default; divergence makes the limit
    # silently downgrade to the smaller value (config.py defaults win at runtime).
    "per_change_token_runaway_threshold": 50_000_000,
    # Aggregate retry wall-time budget per change (ms). Sum of every retry's
    # verify-pipeline wall time. Exhaustion escalates to fix-iss. Must match
    # engine.py @dataclass default — divergence here was the root cause of
    # craftbrew-run-20260423-2223 catalog-product-detail's spurious
    # `failed:retry_wall_time_exhausted` after the 30→90 min code default raise:
    # config.py kept 30m and won at runtime, so the engine.py raise was a no-op.
    "max_retry_wall_time_ms": 5_400_000,
    # Gate-retry policy cap — after N cache reuses in a row on the same gate,
    # the gate runs fully the next time regardless of scope overlap.
    "max_consecutive_cache_uses": 2,
    # Decomposer granularity budget — estimated LOC threshold per change.
    "per_change_estimated_loc_threshold": 1500,
    "loc_schema_weight": 120,
    "loc_ambiguity_weight": 80,
    # Replan divergent-plan reconciliation mode — "enabled" destroys stale
    # branches/dirs, "dry-run" only writes the manifest.
    "divergent_plan_dir_cleanup": "enabled",
    # ─── verify-gate-resilience-fixes: hoist hardcoded constants to directives ───
    # These mirror module-level constants (MAX_MERGE_RETRIES, WATCHDOG_TIMEOUT_*,
    # DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS, DEFAULT_MAX_REPLAN_RETRIES) so all
    # retry/circuit limits live in a single source of truth. Phase 1 keeps
    # CURRENT default values (no behavior change). Phase 3 raises them to
    # evidence-based ceilings.
    # Phase 3: raised 3 → 5. Three runs hit MAX_MERGE_RETRIES on cross-cutting
    # changes; 5 unblocks them.
    "max_merge_retries": 5,
    # Phase 3: raised 3 → 5. Sibling-spec convergence often needs more rebases.
    "max_integration_retries": 5,
    # Phase 3: raised 600s → 1800s (30 min). Agent gondolkodás >10m frequent.
    "watchdog_timeout_running": 1800,
    # Phase 3: raised 300s → 1200s (20 min). Empirical: 24-spec Playwright
    # suite averages 12-15 min; 20 min absorbs flake.
    "watchdog_timeout_verifying": 1200,
    # Unchanged (dispatch bootstrap takes 30-60s, 120s sufficient).
    "watchdog_timeout_dispatched": 120,
    # Phase 3: raised 3600s → 5400s (90 min). ISS-006 needed ~65 min from
    # diagnosed → fix-iss-005 dispatch in craftbrew-run; 90 min absorbs chain.
    "issue_diagnosed_timeout_secs": 5400,
    # Phase 3: raised 3 → 5.
    "max_replan_retries": 5,
    # Phase 3: raised 5 → 8. Sibling-test pollution convergence.
    "e2e_retry_limit": 8,
    # Unified model-selection block — see _DEFAULT_MODELS for the
    # canonical defaults. model-config-unified change.
    "models": _DEFAULT_MODELS,
}


# ─── Validation Rules ───────────────────────────────────────────────
# Maps directive key → (type, validator_regex_or_None)
# Migrated from: utils.sh:parse_directives() case statement L340-615

_VALIDATORS: dict[str, tuple[str, str | None]] = {
    # key: (type, regex_pattern_or_None)
    "max_parallel": ("int_pos", None),
    "merge_policy": ("enum", r"^(eager|checkpoint)$"),
    "checkpoint_every": ("int_pos", None),
    "test_command": ("str", None),
    "notification": ("enum", r"^(desktop|email|desktop\+email|gui|none)$"),
    "token_budget": ("int", None),
    "pause_on_exit": ("bool", None),
    "auto_replan": ("bool", None),
    "review_before_merge": ("bool", None),
    "test_timeout": ("int_pos", None),
    "max_verify_retries": ("int", None),
    "summarize_model": ("enum", MODEL_NAME_RE),
    "review_model": ("enum", MODEL_NAME_RE),
    "default_model": ("enum", MODEL_NAME_RE),
    "smoke_command": ("str", None),
    "smoke_timeout": ("int_pos", None),
    "smoke_blocking": ("bool", None),
    "smoke_fix_token_budget": ("int_pos", None),
    "smoke_fix_max_turns": ("int_pos", None),
    "smoke_fix_max_retries": ("int", None),
    "smoke_health_check_url": ("str", None),
    "smoke_health_check_timeout": ("int_pos", None),
    "smoke_dev_server_command": ("str", None),
    "monitor_idle_timeout": ("int_pos", None),
    "merge_timeout": ("int_pos", None),
    "post_merge_command": ("str", None),
    # token_hard_limit: DEPRECATED — see DIRECTIVE_DEFAULTS comment.
    "token_hard_limit": ("int", None),
    "events_log": ("bool", None),
    "events_max_size": ("int", None),
    "watchdog_timeout": ("int_pos", None),
    "watchdog_loop_threshold": ("int_pos", None),
    "max_tokens_per_change": ("int_pos", None),
    "context_pruning": ("bool", None),
    "plan_approval": ("bool", None),
    "checkpoint_auto_approve": ("bool", None),
    "plan_method": ("enum", r"^(api|agent)$"),
    "model_routing": ("enum", r"^(off|complexity)$"),
    "team_mode": ("bool", None),
    "post_phase_audit": ("bool", None),
    "hook_pre_dispatch": ("str", None),
    "hook_post_verify": ("str", None),
    "hook_pre_merge": ("str", None),
    "hook_post_merge": ("str", None),
    "hook_on_fail": ("str", None),
    "milestones_enabled": ("bool", None),
    "milestones_dev_server": ("str", None),
    "milestones_base_port": ("int", None),
    "milestones_max_worktrees": ("int", None),
    "e2e_port_base": ("int", None),
    "completion_timeout": ("int_pos", None),
    "max_stuck_loops": ("int_pos", None),
    "per_change_token_runaway_threshold": ("int_pos", None),
    "max_retry_wall_time_ms": ("int_pos", None),
    "max_consecutive_cache_uses": ("int_pos", None),
    "per_change_estimated_loc_threshold": ("int_pos", None),
    "loc_schema_weight": ("int_pos", None),
    "loc_ambiguity_weight": ("int_pos", None),
    "divergent_plan_dir_cleanup": ("enum", r"^(enabled|dry-run)$"),
    # verify-gate-resilience-fixes: validators for hoisted retry/circuit limits.
    "max_merge_retries": ("int_pos", None),
    "max_integration_retries": ("int_pos", None),
    "watchdog_timeout_running": ("int_pos", None),
    "watchdog_timeout_verifying": ("int_pos", None),
    "watchdog_timeout_dispatched": ("int_pos", None),
    "issue_diagnosed_timeout_secs": ("int_pos", None),
    "max_replan_retries": ("int_pos", None),
    "e2e_retry_limit": ("int_pos", None),
}


def _validate_value(key: str, raw: str) -> Any | None:
    """Validate and coerce a directive value. Returns None if invalid."""
    spec = _VALIDATORS.get(key)
    if spec is None:
        return None  # unknown key

    vtype, pattern = spec

    if vtype == "bool":
        if raw in ("true", "false"):
            return raw == "true"
        return None

    if vtype == "int":
        if re.match(r"^[0-9]+$", raw):
            return int(raw)
        return None

    if vtype == "int_pos":
        if re.match(r"^[0-9]+$", raw) and int(raw) > 0:
            return int(raw)
        return None

    if vtype == "enum":
        if pattern and re.match(pattern, raw):
            return raw
        return None

    if vtype == "str":
        return raw

    return None


# ─── Duration Utilities ──────────────────────────────────────────────


def parse_duration(input_str: str) -> int:
    """Convert human-readable duration string to seconds.

    Migrated from: utils.sh:parse_duration() L46-73

    - Plain number → minutes (e.g., "30" → 1800)
    - "1h30m" → 5400
    - "2h" → 7200
    - Invalid → 0
    """
    input_str = input_str.strip()

    # Plain number → minutes
    if re.match(r"^[0-9]+$", input_str):
        return int(input_str) * 60

    total = 0
    h_match = re.search(r"([0-9]+)h", input_str)
    if h_match:
        total += int(h_match.group(1)) * 3600

    m_match = re.search(r"([0-9]+)m", input_str)
    if m_match:
        total += int(m_match.group(1)) * 60

    return total


def format_duration(secs: int) -> str:
    """Format seconds to human-readable duration.

    Migrated from: utils.sh:format_duration() L119-130

    - 5400 → "1h30m"
    - 7200 → "2h"
    - 300 → "5m"
    - 0 → "0m"
    """
    h = secs // 3600
    m = (secs % 3600) // 60
    if h > 0 and m > 0:
        return f"{h}h{m}m"
    elif h > 0:
        return f"{h}h"
    else:
        return f"{m}m"


# ─── File Hashing ────────────────────────────────────────────────────


def brief_hash(path: str | Path) -> str:
    """Compute SHA-256 hash of a file.

    Migrated from: utils.sh:brief_hash() L732-737

    Returns "unknown" if file cannot be read.
    """
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, IOError):
        return "unknown"


# ─── Brief Parsing ───────────────────────────────────────────────────


def parse_next_items(brief_path: str | Path) -> list[str]:
    """Extract items from the ### Next section of a brief file.

    Migrated from: utils.sh:parse_next_items() L227-261

    Returns list of stripped item strings. Empty list if no ### Next section.
    """
    try:
        lines = Path(brief_path).read_text(encoding="utf-8").splitlines()
    except (OSError, IOError):
        return []

    items: list[str] = []
    in_next = False

    for line in lines:
        # Detect ### Next header
        if re.match(r"^###\s+Next", line):
            in_next = True
            continue

        if in_next:
            # Any ### or ## header stops collection
            if re.match(r"^##", line):
                break

            # Collect bullet items
            m = re.match(r"^\s*-\s+(.+)", line)
            if m:
                item = m.group(1).strip()
                if item:
                    items.append(item)

    return items


# ─── Directive Parsing ───────────────────────────────────────────────


def parse_directives(doc_path: str | Path | None) -> dict[str, Any]:
    """Parse orchestrator directives from a document's ## Orchestrator Directives section.

    Migrated from: utils.sh:parse_directives() L266-729

    Returns dict with all directive keys and their values (defaults for unspecified).
    """
    result = dict(DIRECTIVE_DEFAULTS)

    if doc_path is None:
        return _finalize_directives(result)

    try:
        lines = Path(doc_path).read_text(encoding="utf-8").splitlines()
    except (OSError, IOError):
        return _finalize_directives(result)

    in_directives = False

    for line in lines:
        # Detect ## Orchestrator Directives header
        if re.match(r"^##\s+Orchestrator\s+Directives", line):
            in_directives = True
            continue

        # Any other ## header stops
        if re.match(r"^##\s", line) and in_directives:
            break

        if not in_directives:
            continue

        # Parse key: value lines
        m = re.match(r"^\s*-?\s*([a-z_]+):\s*(.+)", line)
        if not m:
            continue

        key = m.group(1)
        raw_val = m.group(2).strip()

        if key not in _VALIDATORS:
            logger.warning("Unknown directive '%s', ignoring", key)
            continue

        validated = _validate_value(key, raw_val)
        if validated is not None:
            result[key] = validated
        else:
            logger.warning(
                "Invalid %s '%s', using default %s",
                key,
                raw_val,
                DIRECTIVE_DEFAULTS.get(key),
            )

    # Auto-detect test_command if not set
    if not result["test_command"]:
        detected = auto_detect_test_command(".")
        if detected:
            logger.info("Auto-detected test command: %s", detected)
            result["test_command"] = detected

    # Auto-detect smoke_command if not set (build+test when build script exists)
    if not result.get("smoke_command"):
        detected_smoke = auto_detect_smoke_command(".")
        if detected_smoke:
            logger.info("Auto-detected smoke command: %s", detected_smoke)
            result["smoke_command"] = detected_smoke

    return _finalize_directives(result)


def _finalize_directives(d: dict[str, Any]) -> dict[str, Any]:
    """Finalize directives dict: apply null handling for JSON output compatibility.

    Migrated from: utils.sh:parse_directives() L627-729 (jq output block)
    """
    result = {}
    for key, val in d.items():
        # Milestones are nested in output
        if key.startswith("milestones_"):
            continue
        # Empty strings for hook/optional fields → null
        if key.startswith("hook_") and not val:
            continue
        if key in ("smoke_dev_server_command", "watchdog_timeout",
                    "watchdog_loop_threshold", "max_tokens_per_change",
                    "e2e_port_base") and val is None:
            continue
        if key in ("smoke_dev_server_command",) and val == "":
            continue
        result[key] = val

    # Milestones nested object
    milestones: dict[str, Any] = {
        "enabled": d.get("milestones_enabled", False),
    }
    if d.get("milestones_dev_server"):
        milestones["dev_server"] = d["milestones_dev_server"]
    milestones["base_port"] = d.get("milestones_base_port", 3100)
    milestones["max_worktrees"] = d.get("milestones_max_worktrees", 3)
    result["milestones"] = milestones

    # Discord nested object (passed through from YAML config)
    discord_raw = d.get("discord")
    if isinstance(discord_raw, dict) and discord_raw.get("enabled"):
        result["discord"] = _parse_discord_config(discord_raw)
    else:
        result.pop("discord", None)

    return result


# ─── Discord Config ──────────────────────────────────────────────────


DISCORD_DEFAULT_NOTIFY_ON = ["start", "merge", "stuck", "complete", "crash"]


def _parse_discord_config(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse and validate the discord: config section."""
    return {
        "enabled": True,
        "guild_id": str(raw.get("guild_id", "")),
        "channel_name": raw.get("channel_name", ""),
        "notify_on": raw.get("notify_on", DISCORD_DEFAULT_NOTIFY_ON),
        "mention_on_error": raw.get("mention_on_error", ""),
        "member_map": raw.get("member_map", {}),
    }


def get_discord_config(directives: dict[str, Any]) -> dict[str, Any] | None:
    """Get parsed Discord config from resolved directives. Returns None if disabled.

    Token resolution order:
    1. SET_DISCORD_TOKEN env var
    2. ~/.config/set-core/discord.json (global config from set-discord-setup)

    Guild ID resolution order:
    1. discord.guild_id in orchestration.yaml (per-project)
    2. ~/.config/set-core/discord.json (global config)
    """
    cfg = directives.get("discord")
    if not cfg:
        # Check if global config has auto_enable: true
        global_auto = _read_global_discord_field("auto_enable")
        if global_auto == "True":
            cfg = {"enabled": True, "guild_id": "", "channel_name": "",
                   "notify_on": DISCORD_DEFAULT_NOTIFY_ON,
                   "mention_on_error": "", "member_map": {}}
        else:
            return None

    # Token: env var first, then global config
    token = os.environ.get("SET_DISCORD_TOKEN", "")
    if not token:
        token = _read_global_discord_field("token")
    if not token:
        logger.warning("Discord enabled but no token found — Discord disabled")
        return None
    # Set in env so the bot can use it
    os.environ["SET_DISCORD_TOKEN"] = token

    # Guild ID: per-project config first, then global
    if not cfg.get("guild_id"):
        global_guild = _read_global_discord_field("guild_id")
        if global_guild:
            cfg["guild_id"] = global_guild

    return cfg


def _read_global_discord_field(field: str) -> str:
    """Read a field from ~/.config/set-core/discord.json."""
    import json
    global_path = Path.home() / ".config" / "set-core" / "discord.json"
    if not global_path.is_file():
        return ""
    try:
        with open(global_path) as f:
            data = json.load(f)
        return str(data.get(field, ""))
    except (json.JSONDecodeError, OSError):
        return ""


# ─── Config File Loading ─────────────────────────────────────────────


def load_config_file(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load directives from YAML config file.

    Migrated from: utils.sh:load_config_file() L743-784

    Tries PyYAML first, falls back to simple key:value parser.
    Returns empty dict if file doesn't exist or can't be parsed.
    """
    if not config_path:
        return {}

    path = Path(config_path)
    if not path.is_file():
        return {}

    # Try PyYAML
    try:
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return {}
        return data
    except ImportError:
        pass
    except Exception as e:
        logger.warning("YAML parse error for %s: %s", path, e)
        return {}

    # Fallback: simple key:value parser
    # Migrated from: utils.sh:load_config_file() L756-767 (Python inline)
    result: dict[str, Any] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                key, _, val = line.partition(":")
                key, val = key.strip(), val.strip()
                if val.isdigit():
                    result[key] = int(val)
                elif val in ("true", "false"):
                    result[key] = val == "true"
                else:
                    result[key] = val
    except (OSError, IOError):
        pass
    return result


# ─── Directive Resolution ────────────────────────────────────────────


def resolve_directives(
    input_file: str | Path,
    config_path: str | Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve directives with 4-level precedence.

    Migrated from: utils.sh:resolve_directives() L788-819

    Precedence (highest to lowest):
    1. CLI overrides
    2. Config file (orchestration.yaml)
    3. In-document directives
    4. Defaults (built into parse_directives)
    """
    input_path = Path(input_file)

    # Level 4+3: defaults + in-document directives
    if input_path.is_dir():
        doc_directives = parse_directives(None)
    else:
        doc_directives = parse_directives(input_file)

    # Level 2: config file
    config_directives = load_config_file(config_path)

    # Merge: config overrides doc
    for key, val in config_directives.items():
        if val is not None:
            doc_directives[key] = val

    # Level 1: CLI overrides
    if cli_overrides:
        for key, val in cli_overrides.items():
            if val is not None:
                doc_directives[key] = val

    return doc_directives


# ─── Input Resolution ────────────────────────────────────────────────


def find_openspec_dir() -> str:
    """Find the openspec directory.

    Migrated from: utils.sh:find_openspec_dir() L216-224
    """
    if Path("openspec").is_dir():
        return "openspec"
    elif Path("../openspec").is_dir():
        return "../openspec"
    return "openspec"  # default, may not exist


def find_input(
    spec_override: str | None = None,
    brief_override: str | None = None,
    brief_filename: str = "project-brief.md",
    brief_fallback: str = "project.md",
) -> tuple[str, str]:
    """Resolve orchestration input source, returning (mode, path).

    Migrated from: utils.sh:find_input() L160-213

    Returns:
        ("digest", abs_path) for spec input
        ("brief", abs_path) for brief input

    Raises:
        FileNotFoundError: if no input can be found
    """
    # --spec takes priority
    if spec_override:
        p = Path(spec_override)
        if p.is_dir():
            return ("digest", str(p.resolve()))
        if p.is_file():
            return ("digest", str(p.resolve()))
        # Short-name resolution
        for candidate in [
            Path(f"set/orchestration/specs/{spec_override}.md"),
            Path(f"set/orchestration/specs/{spec_override}"),
        ]:
            if candidate.exists():
                return ("digest", str(candidate.resolve()))
        raise FileNotFoundError(f"Spec file not found: {spec_override}")

    # --brief or auto-detect
    brief_path = _find_brief(brief_override, brief_filename, brief_fallback)
    if brief_path:
        items = parse_next_items(brief_path)
        if items:
            return ("brief", brief_path)
        raise FileNotFoundError(
            f"Brief found ({brief_path}) but ### Next section is empty. "
            "Add items to ### Next, or use --spec <path>."
        )

    raise FileNotFoundError(
        "No input found. Use --spec <path> or create openspec/project-brief.md"
    )


def _find_brief(
    override: str | None,
    filename: str,
    fallback: str,
) -> str | None:
    """Find brief file. Migrated from: utils.sh:find_brief() L135-156."""
    if override:
        return override if Path(override).is_file() else None

    openspec_dir = find_openspec_dir()
    for name in (filename, fallback):
        p = Path(openspec_dir) / name
        if p.is_file():
            return str(p)
    return None


# ─── Test Command Auto-Detection ─────────────────────────────────────


def auto_detect_test_command(directory: str = ".") -> str:
    """Auto-detect test command from project configuration.

    Resolution: profile.detect_test_command() → legacy fallback.

    Returns empty string if no test command found.
    """
    from .profile_loader import load_profile

    profile = load_profile(directory)
    cmd = profile.detect_test_command(directory)
    if cmd:
        return cmd

    # TODO(profile-cleanup): remove after profile adoption confirmed
    # Legacy fallback — delegates PM detection to canonical function
    d = Path(directory)
    pkg_json = d / "package.json"

    if not pkg_json.is_file():
        return ""

    pkg_mgr = detect_package_manager(directory)

    # Check scripts in priority order
    try:
        data = json.loads(pkg_json.read_text(encoding="utf-8"))
        scripts = data.get("scripts", {})
    except (json.JSONDecodeError, OSError):
        return ""

    for candidate in ("test", "test:unit", "test:ci"):
        if scripts.get(candidate):
            return f"{pkg_mgr} run {candidate}"

    return ""


# ─── Smoke Command Auto-Detection ────────────────────────────────────


def auto_detect_smoke_command(directory: str = ".") -> str:
    """Auto-detect smoke command: build+test when build script exists.

    Resolution chain:
    1. Explicit smoke_command from config (handled by caller, not here)
    2. If build script exists: ``<pm> run build && <test_command>``
    3. Fall back to test_command alone

    Returns empty string if no test command found.
    """
    test_cmd = auto_detect_test_command(directory)
    if not test_cmd:
        return ""

    d = Path(directory)
    pkg_json = d / "package.json"
    if not pkg_json.is_file():
        return test_cmd

    try:
        data = json.loads(pkg_json.read_text(encoding="utf-8"))
        scripts = data.get("scripts", {})
    except (json.JSONDecodeError, OSError):
        return test_cmd

    pkg_mgr = detect_package_manager(directory)

    # Prefer build:ci over build
    if scripts.get("build:ci"):
        return f"{pkg_mgr} run build:ci && {test_cmd}"
    elif scripts.get("build"):
        return f"{pkg_mgr} run build && {test_cmd}"

    return test_cmd


# ─── Package Manager Detection ───────────────────────────────────
# Migrated from: lib/orchestration/server-detect.sh:detect_package_manager()


def detect_package_manager(project_dir: str = ".") -> str:
    """Detect package manager from lockfile presence.

    Resolution: profile.detect_package_manager() → legacy fallback.
    Returns: bun, pnpm, yarn, pip, poetry, or npm (default).
    """
    from .profile_loader import load_profile

    profile = load_profile(project_dir)
    pm = profile.detect_package_manager(project_dir)
    if pm:
        return pm

    # TODO(profile-cleanup): remove after profile adoption confirmed
    # Legacy fallback
    d = Path(project_dir)
    if (d / "bun.lockb").is_file() or (d / "bun.lock").is_file():
        return "bun"
    elif (d / "pnpm-lock.yaml").is_file():
        return "pnpm"
    elif (d / "yarn.lock").is_file():
        return "yarn"
    elif (d / "poetry.lock").is_file():
        return "poetry"
    elif (d / "Pipfile.lock").is_file():
        return "pip"
    return "npm"


def install_dependencies(project_dir: str = ".") -> bool:
    """Install dependencies using detected package manager.

    Resolution: profile.post_merge_install() → legacy fallback.
    Returns: True on success, False on failure (non-blocking).
    """
    from .profile_loader import NullProfile, load_profile

    profile = load_profile(project_dir)
    if not isinstance(profile, NullProfile):
        return profile.post_merge_install(project_dir)

    # TODO(profile-cleanup): remove after profile adoption confirmed
    # Legacy fallback
    d = Path(project_dir)
    if not (d / "package.json").is_file():
        return True  # Nothing to install

    pm = detect_package_manager(project_dir)
    logger.info("Installing dependencies in %s with %s", project_dir, pm)

    from .subprocess_utils import run_command

    install_cmd = [pm, "install"]
    result = run_command(install_cmd, timeout=120, cwd=project_dir)

    if result.exit_code == 0:
        logger.info("Dependencies installed successfully (%s)", pm)
        return True
    else:
        logger.warning("Dependency install failed (%s) — non-blocking", pm)
        return False


# ─── Dev Server Detection ────────────────────────────────────────
# Migrated from: lib/orchestration/server-detect.sh:detect_dev_server()


def detect_dev_server(
    project_dir: str = ".",
    milestone_dev_server: str = "",
    smoke_dev_server_command: str = "",
) -> str | None:
    """Auto-detect dev server command for a project.

    Detection cascade:
    1. milestones.dev_server directive (explicit override)
    2. smoke_dev_server_command directive
    3. package.json scripts.dev
    4. docker-compose.yml or compose.yml
    5. Makefile dev/serve target
    6. manage.py (Django)

    Args:
        project_dir: Project directory path.
        milestone_dev_server: Explicit override from milestones directive.
        smoke_dev_server_command: Reuse smoke config.

    Returns:
        Command string or None if not detected.
    """
    d = Path(project_dir)

    # 1. Explicit milestone override
    if milestone_dev_server:
        return milestone_dev_server

    # 2. Reuse smoke_dev_server_command
    if smoke_dev_server_command:
        return smoke_dev_server_command

    # 3. Profile-aware detection
    from .profile_loader import load_profile

    profile = load_profile(project_dir)
    cmd = profile.detect_dev_server(project_dir)
    if cmd:
        return cmd

    # 4. package.json scripts.dev (legacy fallback)
    pkg_json = d / "package.json"
    if pkg_json.is_file():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            if data.get("scripts", {}).get("dev"):
                pm = detect_package_manager(project_dir)
                return f"{pm} run dev"
        except (json.JSONDecodeError, OSError):
            pass

    # 5. docker-compose.yml or compose.yml
    if (d / "docker-compose.yml").is_file() or (d / "compose.yml").is_file():
        return "docker compose up"

    # 6. Makefile with dev or serve target
    makefile = d / "Makefile"
    if makefile.is_file():
        try:
            content = makefile.read_text(encoding="utf-8")
            if re.search(r"^dev:", content, re.MULTILINE):
                return "make dev"
            if re.search(r"^serve:", content, re.MULTILINE):
                return "make serve"
        except (OSError, IOError):
            pass

    # 7. manage.py (Django)
    if (d / "manage.py").is_file():
        return "python manage.py runserver"

    return None
