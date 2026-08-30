## Context

Two code tables own the Anthropic mapping today, and they must stay consistent by hand:

- `ANTHROPIC_MODEL_NAMES` (`lib/set_orch/config.py:41`) — the accepted short names, from
  which `MODEL_NAME_RE` is derived. Note the in-code exception: `fable` is deliberately NOT
  in `_MODEL_MAP` (CLI resolves it natively; measured 2026-08-29).
- `_MODEL_MAP` (`lib/set_orch/subprocess_utils.py:154`) — short name → CLI id
  (`sonnet` → `claude-sonnet-4-6`, `opus-1m` → `claude-opus-4-6[1m]`), applied on launch
  only for providers in `MODEL_MAP_PROVIDERS` (`resolver.py:211`), currently `{"anthropic"}`.

Consumers: the resolver's launch plans (`Provider.launch_args`), `subprocess_utils.resolve_model_id`
(called by `chat.py`, `category_resolver.py`, `engine.sh` paths for the framework's OWN
launches), the model-name validators, and `migrate.build` (which writes the anthropic
declaration into a migrated `providers.json`).

The GLM catalogue already lives entirely in configuration data, `model_aliases` included.
The spec (`agent-provider-config`) requires catalogue-as-data; Anthropic is the violation.

## Goals / Non-Goals

**Goals:**
- The Anthropic mapping becomes configuration data: a `model_ids` block on the provider
  declaration, with the measured mapping shipped as the default.
- One source of truth: validators, launch plans, migrations and templates read the same data.
- Existing configurations (which declare anthropic with no `model_ids`) keep working
  unchanged.

**Non-Goals:**
- No implicit providers: a file that does not declare anthropic still refuses loudly
  (spec: "MUST NOT substitute a built-in default provider"). The default fills a field of a
  declared provider only.
- No per-key merge of declared maps with the default — whole-block replacement, same
  reasoning as the credential+endpoint "one block" rule.
- The orchestration engine's role-based model chain is untouched (out of scope in the spec).
- No new CLI commands; `set-providers show` simply comes to display the effective mapping.

## Decisions

1. **The field is `model_ids`, whole-block, declared-or-default.**
   *Alternative considered:* reusing `model_aliases` — rejected: aliases map OTHER names
   onto catalogue models (glm's `sonnet` → `glm-5.3`), a different direction than
   catalogue name → external CLI id; overloading one field with both directions makes the
   B-118 class of wrong-value bugs easier to write.
   *Alternative considered:* per-key merge with the default — rejected: a hand-written
   partial table silently missing one pin delivers that name raw, which is a wrong value,
   not an error. Whole-block replacement makes the gap loud at the cost of verbosity;
   verbosity is what `set-providers show` is for.

2. **The default lives in one new module** (`lib/set_orch/providers/defaults.py`):
   the catalogue tuple, the default `model_ids` mapping, and nothing else.
   `config.ANTHROPIC_MODEL_NAMES` / `MODEL_NAME_RE` re-export from it (the public import
   paths stay — external plugins and the shim may import them);
   `subprocess_utils._MODEL_MAP` is deleted and `resolve_model_id` reads the defaults
   module, keeping its signature and pass-through behaviour. Import direction:
   `subprocess_utils` → `providers.defaults` is a new edge — acceptable because defaults
   imports nothing from set_orch (leaf data module).

3. **The resolver drops `MODEL_MAP_PROVIDERS`.** Translation applies when the provider's
   effective `model_ids` is non-empty: declared block, else the shipped default for that
   provider name, else no translation. `fable`'s absence from the map is preserved exactly
   (it passes through, deliberately — the comment moves with the data). A name colliding
   with a map key under a provider whose catalogue holds real ids keeps its own meaning
   (B-118), because that provider has an empty effective map.

4. **`migrate.build` writes the full declaration** — catalogue AND `model_ids` — so a
   migrated file is explicit and a future default change cannot move a migrated machine
   under its feet. Hand-written minimal files that omit the block get the default
   (backwards compatible), and the docs' default template is updated to carry the block.

## Risks / Trade-offs

- [A second import path to the same data drifts apart again] → the validators, resolver and
  migrate all import `providers.defaults`; a test asserts `subprocess_utils` holds no
  private copy (grep-level test that the name no longer resolves there).
- [An existing config that relied on pinning through code sees a different id after
  overriding `model_ids` partially] → whole-block replacement is documented and
  `set-providers show` displays the effective map; no merge happens to be silently wrong.
- [`fable` regression] → the default map simply does not contain it; a resolver test
  asserts `--model fable` passes through untranslated.
- [Import cycle `providers ← subprocess_utils`] → defaults.py is a leaf; measured by
  importing it first in the unit tests.

## Migration Plan

Ship in one commit sequence: defaults module → consumers re-pointed → code tables deleted.
No configuration file changes on existing machines (the default applies implicitly).
Rollback is a revert; no data format changed. `model_ids` is additive to the declaration
schema, so older files read fine.

## Open Questions

(none — the mapping values are measured and in production use; this change relocates them.)
