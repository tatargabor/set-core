## Context

The `ikp-bridge` change provides the bridge module (`lib/set_orch/ikp_bridge.py`) that wraps the IKP Python API. This change wires it into the actual orchestration pipeline: the decomposer (planner.py), dispatcher (dispatcher.py), category resolver (category_resolver.py), and verify gate (verifier.py).

The decomposer currently assembles context via `build_decomposition_context()` (planner.py:1671) which returns a dict with fields like `design_context`, `memory`, `pk_context`, etc. IKP adds a new `ikp_context` field.

The dispatcher prepares agent context via `_build_input_content()` (dispatcher.py:1961) and injects rules via `_build_rule_injection()` (dispatcher.py:358). IKP adds rule file injection and an input.md section.

The category resolver (category_resolver.py:462) runs 6 deterministic layers + LLM to classify changes. IKP adds an `integration` category signal.

## Goals / Non-Goals

**Goals:**
- Decomposer reads L1+L2 from project's IKP packs and includes integration context in the planning prompt
- Planner output schema gains `ikp_packs: list[str]` per change — the planner assigns relevant packs
- Dispatcher reads `ikp_packs` from change metadata and injects L3 as `.claude/rules/ikp-<pack>.md`
- Dispatcher adds IKP summary section to input.md (capabilities, env vars, pitfalls)
- Category resolver adds `integration` category when `ikp_packs` is non-empty
- Verify gate includes L4 context in review prompt for integration changes

**Non-Goals:**
- Automatic pack detection from spec text without `.ikp.yaml` (future enhancement)
- Per-capability layer loading (load full L3 per pack, not individual sections)
- L5 Operations integration
- IKP pack validation at orchestration start

## Decisions

### D1: Decomposer — new `ikp_context` field in decomposition context

In `build_decomposition_context()`, add a new `ikp_context` parameter:

```python
def build_decomposition_context(
    input_mode: str,
    input_path: str,
    *,
    # ... existing params ...
    ikp_context: str = "",    # NEW
) -> dict:
```

The caller (in `run_planning_pipeline()`) builds this from the bridge:

```python
if ikp_bridge.has_ikp_pipeline(project_path, directives):
    ikp_config = ikp_bridge.load_ikp_config(project_path)
    ikp_ctx = ikp_bridge.get_context_for_phase("decompose", ikp_config)
else:
    ikp_ctx = ""
```

The rendered planning prompt gets a new section:

```markdown
## Integration Knowledge (IKP)

The following external API integrations are declared for this project.
When creating changes that involve these integrations, assign the
relevant pack names to the change's `ikp_packs` field.

### billingo (invoicing)
**Capabilities:** create-invoice (low), record-payment (low), download-pdf (low), ...
**Key pitfalls:** PDF generation is async, no webhook support, partner must exist before invoice
**Complexity drivers:** No webhooks means polling, async PDF needs retry logic

### wise-payments (payment)
...
```

### D2: Planner output schema — `ikp_packs` field

The planner's expected JSON output for each change gains an optional field:

```json
{
  "name": "billingo-invoice-generation",
  "scope": "Billingo API integration for invoice creation...",
  "depends_on": ["data-model-foundation"],
  "ikp_packs": ["billingo"]
}
```

The planner prompt instruction explains:
> For changes that involve external API integrations listed in the IKP section,
> set `ikp_packs` to the list of relevant pack names. Leave empty or omit for
> changes with no integration work.

The plan enrichment step (`_enrich_change_metadata`) preserves this field. If the planner doesn't output it, defaults to `[]`.

### D3: Dispatcher — rule file injection + input.md section

In `dispatch_change()`, after worktree bootstrap and before input.md assembly:

```python
# IKP rule injection (after design deploy, before input.md build)
ikp_packs = change.get("ikp_packs", [])
if ikp_packs and ikp_bridge.has_ikp_pipeline(project_path, directives):
    ikp_config = ikp_bridge.load_ikp_config(project_path)
    ikp_bridge.inject_rules_for_change(
        wt_path=wt_path,
        pack_names=ikp_packs,
        phase="implement",
        language=ikp_config.language,
        packs_dir=ikp_config.packs_dir,
    )
```

This writes `ikp-billingo.md`, `ikp-wise-payments.md` etc. into `<wt>/.claude/rules/`. The agent reads them as standard rules.

Additionally, add a brief IKP section to `_build_input_content()`:

```markdown
## Integration Packs (IKP)

This change uses the following integration knowledge packs.
Full implementation patterns are in `.claude/rules/ikp-*.md`.

- **billingo**: Invoicing API — create-invoice, record-payment, download-pdf
  Env vars: BILLINGO_API_KEY (required, sensitive)
  Pitfalls: PDF async, no webhooks, partner-first
```

This is a summary (~200 tokens per pack), not the full L3 content — that's in the rules files.

### D4: Category resolver — add `integration` category

New layer in `resolve_change_categories()` between deps (Layer 5) and insights bias:

```python
# Layer 5b: IKP integration detection
ikp_cats: set[str] = set()
ikp_packs = change_metadata.get("ikp_packs", [])
if ikp_packs:
    ikp_cats.add("integration")
layer_signals["ikp"] = ikp_cats
```

The `integration` category must be added to the profile's `category_taxonomy()` return value. For WebProjectType this means adding `"integration"` to the existing taxonomy list.

The `integration` category enables:
- Integration-specific rules from `.claude/rules/` via `rule_keyword_mapping()`
- Integration-specific review learnings filtering
- Potential future integration-specific gate overrides

### D5: Verify gate — L4 context in review prompt

In `review_change()` (verifier.py), when the change has IKP packs:

```python
ikp_packs = change_metadata.get("ikp_packs", [])
if ikp_packs and ikp_bridge.has_ikp_pipeline(project_path, directives):
    ikp_config = ikp_bridge.load_ikp_config(project_path)
    ikp_test_ctx = ikp_bridge.get_context_for_phase(
        "verify", ikp_packs, ikp_config
    )
    # Append to review prompt
```

The L4 context adds to the review prompt:
- Sandbox setup instructions (does the integration have a test mode?)
- Mock strategies (HTTP mock vs SDK mock vs service-level mock)
- Edge cases to check (rate limits, auth failures, webhook signature)
- Test fixture examples

### D6: Change metadata flow

The `ikp_packs` field flows through the pipeline:

```
planner output → state.json (change metadata) → dispatcher reads → verify reads
```

No new state file — `ikp_packs` is stored as a field on the change object in the existing state.json, alongside `scope`, `depends_on`, `change_type`, etc.

## Risks / Trade-offs

**[Risk] Planner ignores ikp_packs field** → If the planner doesn't output `ikp_packs`, the dispatcher has no packs to inject. Mitigation: the plan enrichment step can do a keyword match as fallback — scan scope text against pack names from `.ikp.yaml`. Log a warning when fallback activates.

**[Risk] Too many IKP rules crowd the agent's context** → Each L3 pack is ~2-3K tokens. With 3 packs that's ~9K tokens of rules. Mitigation: the dispatcher already has a 4K token budget for `_build_rule_injection()`. IKP rules use a separate budget (configurable via directive, default 10K). Log total injected token count.

**[Risk] ikp_packs contains pack names not in .ikp.yaml** → The bridge validates: if a requested pack is not in the project config, log warning and skip it. Don't fail the dispatch.

**[Trade-off] Planner assigns packs vs dispatcher auto-detects** → Having the planner assign packs is more explicit and auditable. Auto-detection from scope text would be fragile (false positives from keyword matching). The planner sees the full IKP context and can make informed decisions. Accepted.

**[Trade-off] ikp_packs as plan field vs separate resolution** → Embedding in the plan keeps the pipeline simple: no extra resolution step, no extra state file. The planner is the right place to decide scope.
