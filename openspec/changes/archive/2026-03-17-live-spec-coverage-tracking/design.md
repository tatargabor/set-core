## Context

The coverage tracking pipeline has two layers:

**Digest mode (works well):**
- `requirements.json` → structured REQ-IDs
- `coverage.json` → live REQ→change mapping, updated by `update_coverage_status()` on merge
- `coverage-merged.json` → merged REQ history
- `final_coverage_check()` → summary at orchestration end
- `validate_plan()` → EVERY REQ must be COVERED or DEFERRED, else error

**Single-file mode (gap):**
- `roadmap_item` free text → no structured tracking
- No `coverage.json` equivalent
- No validation that all spec items are mapped to changes
- No completion summary

**Report gap (both modes):**
- `spec-coverage-report.md` is generated once during `validate_plan()` and never updated
- It shows COVERED/DEFERRED/UNCOVERED but not MERGED/FAILED/DISPATCHED
- Diverges from the live `coverage.json` data as orchestration progresses

## Goals / Non-Goals

**Goals:**
- Single-file specs get structured coverage tracking (spec item → change mapping)
- `spec-coverage-report.md` reflects live status at orchestration end
- Coverage gap detection works in both digest and single-file modes

**Non-Goals:**
- Modifying the digest pipeline itself (already works well)
- Real-time report regeneration on every merge (terminal regeneration is sufficient)
- Annotating the original spec markdown with checkboxes (too invasive, user's file)

## Decisions

**1. `source_items` array in plan JSON for single-file mode**

The decompose skill already outputs `roadmap_item` per change. We add a plan-level `source_items` array that lists every identifiable item from the original spec:

```json
{
  "source_items": [
    {"id": "SI-1", "text": "Database schema for users and orders", "change": "schema-setup"},
    {"id": "SI-2", "text": "REST API for cart operations", "change": "cart-api"},
    {"id": "SI-3", "text": "Admin bulk export", "change": null}
  ]
}
```

`change: null` means unmapped — caught by validation. This is the single-file equivalent of `requirements.json` + `coverage.json` in digest mode.

Rationale: Adding a full digest pipeline for single-file specs is overkill. The AI that runs decompose already reads the entire spec — extracting structured items at plan generation time is cheap and natural.

**2. `validate_plan()` validates `source_items` in non-digest mode**

When `digest_dir` is None (single-file), `validate_plan()` checks that every `source_items` entry has a non-null `change` reference. Items with `change: null` become warnings (not errors) — the decompose agent may intentionally skip items.

Rationale: Errors would block dispatch; warnings surface gaps without blocking.

**3. `generate_coverage_report()` becomes state-aware**

Currently only reads `plan.json` + `requirements.json`. New version optionally accepts `state_file` to map change names → statuses. Output:

```
| REQ-001 | Title | MERGED ✓ | change-x | 2026-03-17 |
| REQ-002 | Title | DISPATCHED | change-y | — |
| REQ-003 | Title | FAILED | change-z | — |
```

In single-file mode, it reads `source_items` instead of `requirements.json`.

**4. Report regeneration at terminal state only**

`_send_terminal_notifications()` in engine.py already calls `final_coverage_check()`. We add `regenerate_coverage_report()` at the same point. This avoids per-merge overhead while ensuring the final report is accurate.

**5. Decompose skill adds `source_items` generation instruction**

The SKILL.md gets an instruction: "For single-file specs (no digest), generate a `source_items` array listing every identifiable spec item with an assigned change name or null if intentionally excluded."

## Risks / Trade-offs

- **[Risk] AI may miss spec items in `source_items` extraction** → Same risk as the current `roadmap_item` mapping, but now visible (missing items = missing from the list, not silently dropped). Mitigation: the post-plan review can check `source_items` count vs spec line count.
- **[Risk] `source_items` ID stability across replans** → IDs are `SI-N` sequential, not content-based. On replan, they may shift. Acceptable: single-file mode is simpler than digest mode, and replan resets the plan anyway.
- **[Trade-off] Warnings vs errors for unmapped source_items** → Warnings chosen to avoid blocking dispatch for intentional exclusions. If this proves too lenient, can be upgraded to errors with a `deferred_source_items` escape hatch (mirroring `deferred_requirements`).

## Open Questions

None — scope is contained to planner, engine, and decompose skill.
