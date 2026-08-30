"""The shipped-default Anthropic model data: the catalogue and its CLI ids.

ONE body of data, read by every consumer — the model-name validator, the
resolver's launch-plan translation, the migration's generated Anthropic
declaration, and `resolve_model_id` for the framework's own launches. The
spec (`agent-provider-config`, "The mapping has one source") forbids a second
private copy, because two copies drift without either looking wrong.

This module is a LEAF: it imports nothing from set_orch, so both
`set_orch.config` and `set_orch.subprocess_utils` can read it without an
import cycle.

These values are configuration DEFAULTS, not constants. A provider declaration
in `providers.json` may carry its own `model_ids` block, which replaces the
default WHOLE for that provider (no merge — a partial table silently missing
one pin delivers that name untranslated, a wrong value rather than an error).
The default applies only to a provider the configuration DECLARES; it never
conjures one the file does not name.
"""

from __future__ import annotations

from typing import Dict

#: The short model names set-core accepts for the Anthropic provider. Moved
#: verbatim from `set_orch.config` (which re-exports it — the public import
#: path is unchanged), comments included; the ordering note below still holds.
#:
#: measured 2026-08-29, `glm-5.3` and `glm-5.3-flash` fail the model-name
#: regex, so an alternative provider's names did not hit a missing entry, they
#: hit a wall.
#:
#: Order is preserved deliberately: the derived pattern is asserted
#: byte-for-byte against the literal it once replaced, and reordering would
#: break that check for a reason that has nothing to do with behaviour.
ANTHROPIC_MODEL_NAMES: tuple[str, ...] = (
    "haiku", "sonnet", "opus", "sonnet-1m", "opus-1m",
    "opus-4-6", "opus-4-7", "opus-4-6-1m", "opus-4-7-1m",
    # `fable` — CLI-native: measured 2026-08-29 with an unreachable endpoint,
    # `--model fable` in a clean environment produced no unrecognized_model and
    # attempted the call, while `--model sonnet-1m` was refused under its own
    # name. It is therefore deliberately NOT in DEFAULT_MODEL_IDS below —
    # pass-through is the correct delivery, and B-118's anchor accepts it.
    "fable",
)

#: The shipped-default id mapping for the Anthropic catalogue: short name ->
#: the model id the agent CLI consumes. Moved verbatim from
#: `subprocess_utils._MODEL_MAP`, comments included.
DEFAULT_MODEL_IDS: Dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    # `opus` shorthand resolves to 4.6 — the established default for
    # framework orchestration (better token economy than 4.7 at
    # comparable quality on agent/decompose tasks). Operators wanting
    # 4.7 must pin it explicitly via `opus-4-7` or `models.agent: opus-4-7`.
    "opus": "claude-opus-4-6",
    "opus-1m": "claude-opus-4-6[1m]",
    "sonnet-1m": "claude-sonnet-4-6[1m]",
    # Explicit version pins — bypass the shorthand default.
    "opus-4-6": "claude-opus-4-6",
    "opus-4-7": "claude-opus-4-7",
    "opus-4-6-1m": "claude-opus-4-6[1m]",
    "opus-4-7-1m": "claude-opus-4-7[1m]",
}

#: Which provider name the default mapping belongs to. A provider whose
#: catalogue holds real ids (`glm`) must never have it applied: translating
#: there would send a Claude id at that provider's endpoint — a wrong value
#: delivered silently (B-118). A DECLARED provider without a default entry and
#: without its own `model_ids` block gets NO translation.
DEFAULT_MODEL_IDS_PROVIDER = "anthropic"
