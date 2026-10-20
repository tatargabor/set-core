## Context

Model selection in set-core is currently scattered. The Phase 1 audit identified 40+ touch points across six categories:

- **A) Per-change agent**: `Change.model` field in plan.json, populated by the planner LLM, consumed by the dispatcher's `resolve_change_model()` and ultimately passed to ralph/claude inside a worktree.
- **B) Planner LLM calls**: `digest.call_digest_api(model="opus")`, `planner.decompose_brief(model=...)`, `planner.decompose_domain(model=...)`, `planner.decompose_merge(model=...)`. Defaults vary across signatures.
- **C) Verify-pipeline LLM gates**: `verifier.py::DEFAULT_REVIEW_MODEL = "sonnet"` with implicit sonnet→opus escalation; `_execute_spec_verify_gate` does the same; `llm_verdict.LLMVerdict.model = "sonnet"`.
- **D) Supervisor / canary / sentinel**: `supervisor/canary.py` hardcodes `model="sonnet"`; `supervisor/ephemeral.py` defaults to sonnet; `supervisor/triggers.py::DEFAULT_MODEL_BY_TRIGGER` maps trigger types → opus/sonnet; `manager/supervisor.py` builds `--model sonnet` for the sentinel.md invocation.
- **E) Default + routing logic**: `dispatcher.resolve_change_model()` (default_model + model_routing flag), `engine.py::Directives.default_model`, `cli.py` defaults across 20+ flags.
- **F) Bash mirror**: `bin/set-common.sh::resolve_model_id` parallel mapping; `lib/orchestration/dispatcher.sh` reads model via jq.

Phase A landed the prerequisites: `chat.py` always passes `--model`; the test-bundling guards are fail-loud; `change_type` is a required prompt field; planner.py is Layer-1 pure with profile hooks.

The user's two concrete asks:
1. **Switch the agent default to `opus-4-6`** (currently the alias `opus` resolves to `opus-4-7`).
2. **Make all model selections operator-controllable from one place**.

Plus the audit-driven follow-up: the planner prompt template tells the LLM "use opus for features, sonnet for infrastructure/cleanup/docs" — observed extension to `foundational` caused a 134m run on sonnet for a job that would take 14m on opus. Fix is in the prompt template, not the dispatcher.

## Goals / Non-Goals

**Goals:**
- One YAML block (`models:`) controls every model selection in the orchestration pipeline. Operator can change defaults without touching code.
- Every Python call site that needs a model reads it via a single `resolve_model(role)` helper. The helper handles the resolution chain and validates output.
- Bash side mirrors the same chain via `set-common.sh::resolve_model_id --config` and the shell wrappers under `lib/orchestration/` so model selection is consistent across Python and bash entry points.
- Profile plugins can override per-role via `model_for(role)`. The override is per-stack (e.g. WebProjectType could pin `review_escalation` to opus-4-7 if it observes that opus-4-6 underperforms on TSX review).
- Sonnet-routing fix: `foundational → opus` is the documented planner instruction; the LLM no longer treats foundational like infrastructure.
- `opus-4-6` becomes the new agent default (BREAKING for operators who relied on the implicit `opus → opus-4-7` mapping).

**Non-Goals:**
- No reduction in the number of distinct roles or any unification of "agent" with "review_escalation" — each role exists for a reason and operators may want them different.
- No change to the `_MODEL_MAP` in `subprocess_utils.py` or `set-common.sh::resolve_model_id` — they stay the canonical short-name → full-id table.
- No change to per-change model assignment by the planner. The planner LLM still picks per-change models from the prompt instructions; the prompt instructions just stop saying "foundational → sonnet".
- No new model-routing strategy in `dispatcher.resolve_change_model` (`off` and `complexity` stay as-is).
- No change to billing/cost tracking (`cost.py` stays unchanged; full model IDs are already in the rates table).
- No async/parallel model calls — this is plumbing, not a behavior change.

## Decisions

### D1 — `models:` directive block schema

Add to `lib/set_orch/config.py::DIRECTIVE_DEFAULTS`:

```python
DIRECTIVE_DEFAULTS = {
    # ... existing keys ...
    "models": {
        "agent": "opus-4-6",                     # NEW DEFAULT (was opus → opus-4-7)
        "digest": "opus-4-6",
        "decompose_brief": "opus-4-6",
        "decompose_domain": "opus-4-6",
        "decompose_merge": "opus-4-6",
        "review": "sonnet",                       # initial review pass
        "review_escalation": "opus-4-6",          # on review fail
        "spec_verify": "sonnet",                  # initial spec-verify pass
        "spec_verify_escalation": "opus-4-6",     # on spec-verify fail
        "classifier": "sonnet",                   # llm_verdict classifier (cheap)
        "supervisor": "sonnet",                   # set:sentinel agent
        "canary": "sonnet",                       # health-check canary
        "trigger": {
            "integration_failed": "opus-4-6",
            "non_periodic_checkpoint": "opus-4-6",
            "terminal_state": "opus-4-6",
            "default": "sonnet",
        },
    },
}
```

Validation regex stays at the existing pattern:
```python
^(haiku|sonnet|opus|sonnet-1m|opus-1m|opus-4-6|opus-4-7|opus-4-6-1m|opus-4-7-1m)$
```

The `models.trigger` sub-dict is special — it's a mapping of trigger names to models, validated key-by-key. Its keys must be valid trigger names (validated against the existing `TriggerType` enum).

**Alternative considered**: keep the existing flat directives (`default_model`, `review_model`, `summarize_model`, `digest_model`, `investigation_model`) and just add new ones for missing roles. Rejected — the flat namespace is already inconsistent (3 of those exist in `engine.py::Directives` and 3 in `config.py::DIRECTIVE_DEFAULTS`). Cleaner to consolidate under `models:` and deprecate the flat names in a future migration (`default_model` etc. continue working via fallback).

**Backwards compatibility**: when `models.agent` is unset BUT the legacy `default_model` directive is set, `resolve_model("agent")` returns the legacy value with a one-shot DEPRECATION warning. The legacy keys are removed in a future change.

### D2 — `resolve_model(role, *, project_dir=".") -> str`

New module `lib/set_orch/model_config.py`:

```python
def resolve_model(
    role: str,
    *,
    project_dir: str = ".",
    cli_override: Optional[str] = None,
) -> str:
    """Resolve the model name for a given role.

    Resolution chain (first hit wins):
      1. cli_override (caller-supplied, e.g. from argparse)
      2. ENV var SET_ORCH_MODEL_<ROLE_UPPER>  (e.g. SET_ORCH_MODEL_AGENT)
      3. orchestration.yaml::models.<role> (or models.trigger.<sub>)
      4. profile.model_for(role) — returns Optional[str]
      5. DIRECTIVE_DEFAULTS["models"][<role>]
      6. RuntimeError if no value at any level (signals invalid role)

    Trigger sub-keys: pass role="trigger.integration_failed" etc.
    The chain operates on the dotted path.

    Returned name is validated against MODEL_NAME_RE; raises ValueError
    on invalid input from any source.
    """
```

The helper is the SOLE Python entry point for model selection. Every existing literal `"opus"`, `"sonnet"`, `model="sonnet"` constructor argument, etc. routes through it. Hardcoded values inside the helper itself are only the last-resort fallback when DIRECTIVE_DEFAULTS itself is corrupted (defensive — should not happen).

**Alternative considered**: separate helpers per role (`resolve_agent_model()`, `resolve_review_model()`, etc.). Rejected — adds boilerplate for every new role; the unified `resolve_model(role)` is one symbol to remember and one function to test.

### D3 — Profile `model_for(role)` hook

Add to `ProjectType` ABC (`lib/set_orch/profile_types.py`):

```python
def model_for(self, role: str) -> Optional[str]:
    """Per-stack model override for `role`. Default: None (use config chain).

    Plugins return a short model name (e.g. "opus-4-7") to pin a specific
    role for their stack. Returning None means "no opinion — use the chain
    as configured".

    Reads after orchestration.yaml::models in the resolution chain (so the
    operator's explicit yaml setting still wins) and before
    DIRECTIVE_DEFAULTS (so the plugin's preference beats the framework
    default).
    """
    return None
```

CoreProfile inherits the None default. WebProjectType ships with no override initially (inherits None) — we have no evidence yet that the web stack needs a different model than the framework default. The hook is there for future plugin authors.

**Alternative considered**: a single `models_for_stack() -> dict[str, str]` returning all overrides at once. Rejected — too easy to over-specify and hide which role a plugin actually cares about; the per-role lookup is more discoverable.

### D4 — Touch-point conversion

Every call site in the inventory (40+ locations) gets one of two conversions:

- **Function-signature default** (e.g. `def call_digest_api(..., model: str = "opus"):`): change to `model: Optional[str] = None`. Inside the function: `if model is None: model = resolve_model("digest")`. Caller can still pass an explicit override; `None` triggers the chain.
- **Module-level constant** (e.g. `DEFAULT_REVIEW_MODEL = "sonnet"` in verifier.py): replace with `def _default_review_model(): return resolve_model("review")` and call sites use the function instead of the constant. Constant removed.

The escalation logic in verifier.py (review and spec_verify both start sonnet → escalate to opus) reads two roles: `review` for the initial pass, `review_escalation` for the retry. Same for spec_verify.

The trigger map in `supervisor/triggers.py` reads `resolve_model("trigger.<trigger_name>")` for each lookup. The `default` key is consulted via `resolve_model("trigger.default")` for unmapped triggers.

The chat agent's model field reads `resolve_model("agent")` at construction. Subsequent `--model self.model` invocations honor whatever was set there.

### D5 — Bash mirror

`bin/set-common.sh::resolve_model_id` gains an optional `--config <yaml-path>` argument and an optional `--role <name>` argument:

```bash
resolve_model_id [--config <yaml>] [--role <role>] <name|fallback>
```

When `--config` and `--role` are both provided, the function:
1. Reads `models.<role>` (or the `--<role>-model` ENV var) from the yaml using a small Python one-liner (yq is not universally available; we already require Python 3.10+).
2. Falls through to the positional `<name|fallback>` arg if the yaml read returns nothing.
3. Returns the full claude-CLI model ID after the existing short-name → full-id translation.

Shell entry points (`lib/orchestration/dispatcher.sh`, `lib/orchestration/digest.sh`) pass `--config "$ORCH_YAML" --role <role>` where they currently hardcode opus/sonnet.

**Alternative considered**: ditch the bash mirror entirely and have shell scripts always exec `set-orch-core resolve-model --role X` to get the model. Rejected — slower (Python startup per call) and the bash mirror is in widespread use across the codebase already; minimal extension is safer.

### D6 — CLI flags

Each of the 13 roles gets its own `--<role>-model` flag on the relevant subcommands:

- `engine monitor`, `dispatch`, `plan run`, `digest run`, `verify`, `set-supervisor`, `chat`: each accepts the subset of flags relevant to its operation. Generic flags (`--agent-model`, `--default-model`) work everywhere.
- `--model-profile <preset>` is a shortcut: parsed first, sets all roles to the preset's mapping, then individual `--<role>-model` flags override on top.

Presets:
- `default` — current behavior (the DIRECTIVE_DEFAULTS table)
- `all-opus-4-6` — every role → `opus-4-6` (high quality, 4.6 family)
- `all-opus-4-7` — every role → `opus-4-7` (high quality, 4.7 family — restores pre-Phase-B agent behavior)
- `cost-optimized` — agent/digest/decompose_* → sonnet, review/spec_verify/classifier → haiku, escalations → sonnet, triggers → sonnet (cheapest run, lower quality on big jobs)

**Alternative considered**: drop CLI flags and force operators to edit `orchestration.yaml`. Rejected — temporary one-off overrides (e.g. "this run only, use opus-4-7 to compare") shouldn't require yaml edits.

### D7 — Sonnet-routing fix in planner prompt

In `templates.py::render_brief_prompt`, the existing model-selection guidance reads:

> Model selection: **opus** for feature changes, **sonnet** for infrastructure / cleanup / docs / refactor changes.

Replace with:

> Model selection: **opus** for `feature` AND `foundational` changes (these touch the production-code design surface and benefit from the larger model). **sonnet** for `infrastructure`, `schema`, `cleanup-before`, `cleanup-after` (these are mechanical or scoped). When unsure, prefer opus.

Also remove the same incorrect guidance from `templates.py:537,556,577,811` (other prompts that repeat it).

**Alternative considered**: enforce model assignment post-hoc in `validate_plan` by overriding any sonnet assignment on a foundational change. Rejected — the prompt fix is the right layer (the LLM is making the call); a validator would silently override the LLM's reasoning and obscure what's happening.

## Risks / Trade-offs

- [Default change to opus-4-6 affects existing behavior] Operators relying on `models.agent` to be `opus → opus-4-7` see a quieter, possibly slightly lower-quality variant. → **Mitigation**: explicit BREAKING note in release notes and a migration recipe (`models.agent: opus-4-7` or use `--model-profile all-opus-4-7`). Tests validate that opus-4-6 is the new default. The opus-4-6 variant is widely used and stable.
- [Bash side gets more complex] `set-common.sh::resolve_model_id --config --role` adds a Python one-liner subprocess on every shell invocation. → **Mitigation**: cache the parsed yaml in a process-local variable; fall back gracefully to the legacy positional fallback when yaml is unreadable.
- [Profile override layer adds resolution cost] Every model lookup may call `profile.model_for(role)`. → **Mitigation**: profile loading is already memoized; the new method is a constant-time dict lookup. Negligible.
- [CLI flag explosion] 13 new flags + presets. → **Mitigation**: presets are the recommended way; per-role flags are advanced/overrides. Documented in `--help` output and the deployed `orchestration.yaml` template.
- [Existing tests reference hardcoded models] Some unit tests assert that `default_model="opus"`. Those break when the resolution chain returns `opus-4-6`. → **Mitigation**: update the tests to either patch DIRECTIVE_DEFAULTS or assert on `resolve_model("agent")` semantically; documented in the test plan.
- [Dispatcher's complexity routing still uses literal "sonnet"] At dispatcher.py:1198-1202 the routing returns `"sonnet"` for S+non-feature. After this change those constants become `resolve_model("agent")` — wait, they should stay relative ("smaller model than agent default"). → **Mitigation**: introduce a `resolve_model("agent_small")` role with default `sonnet`. Operators who want their downgrade target to be e.g. haiku set `models.agent_small: haiku`. Avoid hardcoding "sonnet" in routing logic.

## Migration Plan

1. **Schema + helper**: add `models:` to DIRECTIVE_DEFAULTS, create `model_config.py::resolve_model`, add `model_for` ABC method with None defaults, write the resolver tests.
2. **CLI flags + presets**: add the 13 flags + `--model-profile`. Tests cover override precedence.
3. **ENV var support**: `SET_ORCH_MODEL_<ROLE>` reading. Tests cover ENV precedence.
4. **Touch-point conversion** (per category):
   - **A** dispatcher.resolve_change_model → resolve_model("agent")
   - **B** digest.py + planner.decompose_* → resolve_model("digest"|"decompose_brief"|"decompose_domain"|"decompose_merge")
   - **C** verifier.py review + spec_verify → resolve_model("review"|"review_escalation"|"spec_verify"|"spec_verify_escalation"); llm_verdict.classifier → resolve_model("classifier")
   - **D** canary.py + ephemeral.py + triggers.py + manager/supervisor.py → resolve_model("canary"|"supervisor"|"trigger.<...>")
   - **E** dispatcher complexity routing → resolve_model("agent_small") for the downgrade target; engine Directives default_model → resolve_model("agent") backwards-compat shim
   - **F** bash mirror in set-common.sh → `--config` arg + python helper
5. **Prompt fix**: edit templates.py model-selection guidance for foundational → opus.
6. **Template deployment**: documented `models:` block in `modules/web/.../templates/.../config.yaml`.
7. **Release notes**: prominent BREAKING block for the `agent` default change + migration recipe.

**Rollback**: revert the merge commit. The change is mechanical enough that a clean revert restores prior behavior; only orchestrators started AFTER the merge but BEFORE the revert would have used opus-4-6 (and any plan.json files generated would have `model: opus-4-6` literal — those keep working under the old code because `opus-4-6` is already in `_MODEL_MAP`).

## Open Questions

- Should `agent_small` (the downgrade target for `model_routing="complexity"`) be a separate role or just a fixed `"sonnet"` literal in dispatcher routing? Current proposal: separate role with default sonnet. Confirm with first operator who hits this path.
- Do we want a `--list-models` CLI command that prints the resolution chain for every role + the value each role currently resolves to? Useful for debugging but cosmetic. Defer to a follow-up.
- The `--model-profile cost-optimized` preset uses `haiku` for review/spec_verify/classifier. Validate end-to-end that haiku is sufficient for review verdicts on web changes; if not, drop those to sonnet too.
