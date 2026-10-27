## Why

The `agent-provider-config` spec requires that adding a model to a provider is a data edit
with no framework change, and the GLM catalogue already works that way. The Anthropic
catalogue does not: its short-name → CLI-id mapping lives in two framework code tables
(`ANTHROPIC_MODEL_NAMES` in `lib/set_orch/config.py`, `_MODEL_MAP` in
`lib/set_orch/subprocess_utils.py`), so adding or re-pinning an Anthropic model is a code
change — the exact failure the spec was written to prevent. Measured the same day on a
third machine: the hand-written minimal configuration the docs taught carried a truncated
Anthropic list, and names like `opus-4-7` were refused by a catalogue the user never chose.

## What Changes

- A provider declaration MAY carry a `model_ids` block: short catalogue name → the id
  delivered to the agent CLI. When present, launch translation resolves through it; when
  absent, names deliver as declared (today's GLM behaviour, unchanged).
- The framework ships the measured Anthropic mapping as DEFAULT configuration data — the
  built-in default `model_ids` for the anthropic catalogue, applied to a DECLARED anthropic
  provider that does not carry its own `model_ids` block. A declared block replaces the
  default whole; no partial merge.
- The two code tables collapse into that one default-data module:
  `subprocess_utils.resolve_model_id` and the derived model-name regex read the same
  mapping instead of owning private copies.
- The documented default `providers.json` template (README, configuration reference,
  migration output) carries the full Anthropic declaration — catalogue and id map — so a
  hand-written file no longer truncates it.
- NOT changing: a missing configuration still fails loudly and never falls back. The
  default id map fills a field of a provider the file already declares; it never
  substitutes a provider the file does not declare.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `agent-provider-config`: a declaration may carry its CLI id mapping as data; the
  framework ships a default mapping for the Anthropic catalogue that an explicit block
  overrides whole; the mapping is no longer owned by framework code tables.

## Impact

- `lib/set_orch/providers/` — new defaults module; resolver's launch-plan translation
  reads the declared-or-default map instead of `MODEL_MAP_PROVIDERS` + hardcoded table
- `lib/set_orch/subprocess_utils.py` — `_MODEL_MAP` moves to the defaults module;
  `resolve_model_id` keeps its signature and behaviour
- `lib/set_orch/config.py` — `ANTHROPIC_MODEL_NAMES` / `MODEL_NAME_RE` derive from the
  defaults module (single source)
- `lib/set_orch/providers/migrate.py` — the migrated Anthropic declaration carries the
  full catalogue and id map
- Callers that resolve ids for the framework's own launches (`chat.py`,
  `category_resolver.py`, `engine.sh` paths through `subprocess_utils`) keep their
  behaviour, now fed from the shared data
- Docs: README, `docs/reference/configuration.md`, `.claude/skills/set/glm/SKILL.md`
  templates updated to the full declaration
- Tests: resolver, migrate, subprocess_utils, and the validator regex suite
