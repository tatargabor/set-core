## Context

The orchestrator dispatches changes to wt-loop with `--model opus` hardcoded in both `dispatch_change()` (line 2596) and `resume_change()` (line 2725). The planner prompt generates a plan JSON with `name`, `scope`, `complexity`, `change_type`, `depends_on`, and `roadmap_item` — but no model field. Directives have `review_model` but no `default_model` for implementation work.

Current model usage:
- Implementation (dispatch/resume): hardcoded opus
- Plan decomposition: hardcoded opus
- Code review: configurable via `review_model` directive (default sonnet)
- Build fix LLM: sonnet with opus escalation

## Goals / Non-Goals

**Goals:**
- Per-change `model` field in plan JSON (optional override)
- Global `default_model` directive (default: opus for backward compat)
- Complexity-based heuristic fallback when no explicit model set
- Per-change `skip_review` and `skip_test` flags for doc/trivial changes
- Documentation updates (checklist + planning guide)

**Non-Goals:**
- Changing planner model (stays opus — planning quality is critical)
- Per-change token budgets (separate concern, not this change)
- Per-change max_iterations (could be derived from complexity later, not now)

## Decisions

### 1. Model resolution order: explicit > directive > heuristic

**Decision**: Three-level fallback chain:
```
effective_model = change.model ?? directives.default_model ?? heuristic(change)
```

Heuristic logic:
- S-complexity + change_type in (cleanup-before, cleanup-after): sonnet
- Everything else: opus

**Alternative considered**: Let the planner LLM suggest models. Rejected — the planner doesn't know about token budgets or user preferences. Model choice is an operational concern, not a planning concern.

### 2. Plan JSON schema addition

**Decision**: Add three optional fields to the change object:
```json
{
  "name": "doc-sync-ui",
  "model": "sonnet",
  "skip_review": true,
  "skip_test": true,
  ...existing fields...
}
```

All three default to null/false. `init_state()` carries them from plan JSON to state JSON.

**Alternative considered**: Separate config file for per-change overrides. Rejected — the plan JSON is the natural place, and users already edit it or the spec/brief that generates it.

### 3. Directive: `default_model`

**Decision**: Add `default_model` to directives block (alongside existing `review_model`). Default value: `"opus"` for backward compatibility.

Parsed in `monitor_loop()` from directives JSON, passed to `dispatch_change()` and `resume_change()`.

### 4. Gate skip flags pass through verify gate

**Decision**: In `handle_change_done()`, check `skip_test` and `skip_review` from state before running test/review gates. When skipped, log the skip and set result to `"skipped"`.

This is simpler than a separate `verify_policy` field and stays explicit per-change.

### 5. Planner prompt does NOT suggest models

**Decision**: The planner prompt stays unchanged. Model selection is done post-plan by the user (editing plan JSON) or by the heuristic. The checklist reminds users to review model choices.

**Rationale**: Planner output is already complex. Adding model suggestions risks hallucinated model names and makes the JSON harder to validate.

## Risks / Trade-offs

- **Risk**: Users forget to set models and S changes run on expensive opus → **Mitigation**: Heuristic catches S-complexity cleanup changes automatically; checklist item reminds about model selection
- **Risk**: Sonnet produces lower quality on complex tasks → **Mitigation**: Only auto-downgrade for S-complexity cleanup; features stay opus by default
- **Risk**: `skip_test` hides real bugs in doc changes that touch code → **Mitigation**: Only flags, not automatic; user must explicitly set them; the checklist warns about this

## Open Questions

None.
