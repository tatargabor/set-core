## Context

The `wt/orchestration/specs/` directory was scaffolded by `wt-directory-convention`. The orchestrator currently requires explicit `--spec <path>` with full file paths. This change makes the orchestrator spec-aware: short names, listing, archiving.

## Goals / Non-Goals

**Goals:**
- Short-name spec resolution: `--spec v12` finds `wt/orchestration/specs/v12.md`
- `wt-orchestrate specs` subcommand for listing and managing specs
- Migrate legacy `docs/v*.md` to `wt/orchestration/specs/archive/`
- Plan metadata records source spec for traceability

**Non-Goals:**
- Spec templating or creation wizard (future)
- Auto-detecting which spec is "active" without `--spec` flag (too magic)
- Spec format changes (content stays free-form markdown)

## Decisions

### Decision 1: Spec Resolution Chain in find_input()

```
--spec "docs/v8.md"                → use literal path (existing behavior)
--spec "v12"                       → try wt/orchestration/specs/v12.md
--spec "archive/v6"                → try wt/orchestration/specs/archive/v6.md
--spec not given                   → brief auto-detect (existing behavior)
```

The resolution step is inserted between "check literal path" and "error":
```bash
# In find_input():
if [[ ! -f "$SPEC_OVERRIDE" ]]; then
    # Try wt/ spec directory
    local wt_spec="wt/orchestration/specs/${SPEC_OVERRIDE}.md"
    if [[ -f "$wt_spec" ]]; then
        SPEC_OVERRIDE="$wt_spec"
    else
        error "Spec file not found: $SPEC_OVERRIDE (also checked $wt_spec)"
        return 1
    fi
fi
```

**Why not auto-detect active spec:** Explicit is better than implicit. The user should always specify which spec to work from. Auto-detection would break when multiple specs exist.

### Decision 2: specs Subcommand

```bash
wt-orchestrate specs              # List all specs (active + archived)
wt-orchestrate specs show <name>  # Cat the spec content
wt-orchestrate specs archive <name>  # Move to archive/ subdir
```

Listing shows:
```
Specs in wt/orchestration/specs/:
  v12-webshop.md        (active)
  archive/
    v6.md               (archived)
    v8.md               (archived)
```

Status detection: a spec is "active" if it's not in `archive/`. No parsing needed — location-based.

### Decision 3: Legacy Spec Migration

`wt-project migrate` gains an additional step: detect `docs/v*.md` files and move them to `wt/orchestration/specs/archive/` (they're completed specs from past runs).

Pattern: `docs/v[0-9]*.md` — matches v6.md, v8.md, v11-billing.md etc.

### Decision 4: Plan Traceability

When creating a plan, record `spec_source` in the plan JSON metadata. This is already partially done via `input_path` — no additional work needed, just ensure the resolved wt/ path is stored (not the short name).

## Risks / Trade-offs

- **[Risk] Short name collision**: unlikely — spec names are user-chosen and project-unique
- **[Trade-off] No auto-active detection**: user must always pass `--spec`, but this prevents ambiguity
