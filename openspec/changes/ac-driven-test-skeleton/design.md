# Design: AC-Driven Test Skeleton

## Context

The DOMAIN → REQ → AC → TEST flow currently breaks at AC → TEST because there's no stable identifier. The pipeline uses slugified AC text for matching, which fails when agents write tests with different wording (run36: 20/46 bound, run32: 3/46 bound before segment-split fix).

### Current data flow
```
requirements.json                    test-plan.json                     skeleton.spec.ts
  acceptance_criteria: [               scenario_slug: "header-visible"    test('REQ-NAV-001: Header visible')
    "Header visible on all pages",     scenario_name: "Header visible"
    "Site title displayed"             req_id: "REQ-NAV-001"
  ]                                    (NO ac_id)                         (NO AC-ID in name)
```

### Target data flow  
```
requirements.json                    test-plan.json                     skeleton.spec.ts
  acceptance_criteria: [               ac_id: "REQ-NAV-001:AC-1"         test('REQ-NAV-001:AC-1 — Header visible')
    {                                  scenario_slug: "header-visible"
      "ac_id": "REQ-NAV-001:AC-1",    req_id: "REQ-NAV-001"
      "text": "Header visible..."
    }
  ]
```

## Goals

- AC-ID is the stable identifier from digest through dashboard — never changes
- Skeleton provides the structure; agent only fills test body
- Coverage binding is deterministic (regex AC-ID match), not fuzzy (slug match)
- 100% backwards compatible — old data without ac_id works via current slug fallback

## Non-Goals

- Changing the digest LLM prompt (AC extraction stays as-is)
- Per-AC pass/fail in dashboard (future — `ac-display` spec marks this as future)
- Removing slug matching entirely (kept as fallback)

## Decisions

### 1. AC-ID format: `REQ-XXX-NNN:AC-M`
**Choice**: Colon-separated compound ID using the parent REQ-ID + ordinal.
**Why**: Parseable by extending existing `REQ-[A-Z]+-\d+` regex to `REQ-[A-Z]+-\d+:AC-\d+`. The colon is safe in Playwright test names and Markdown.
**Alternative**: Separate `AC-NNN` global namespace — rejected because AC-1 is meaningless without its REQ parent.

### 2. Generate AC-IDs at consumption time, not in digest
**Choice**: Don't modify the digest LLM prompt. Instead, generate AC-IDs when `requirements.json` is read by `generate_test_plan()` and `dispatcher.py`.
**Why**: The digest already extracts `acceptance_criteria` as a string array. Adding a structured object to the LLM output is fragile (JSON-in-JSON). Instead, assign ordinal IDs programmatically: `acceptance_criteria[0]` → `AC-1`, `[1]` → `AC-2`.
**Stability**: The ordinal is stable because the digest extracts ACs in spec order. A re-digest of the same spec produces the same order.

### 3. Skeleton test name format: `'REQ-XXX-NNN:AC-M — description'`
**Choice**: AC-ID first (regex-parseable), em-dash separator, then human-readable description.
**Why**: The regex `REQ-[A-Z]+-\d+:AC-\d+` can be extracted without parsing the description. The description after `—` is for human readability only. The agent may change the description but the AC-ID prefix stays because it's part of the skeleton (not the body).

### 4. Three-phase binding: AC-ID → slug → REQ-level
**Choice**: Add Phase 0 (AC-ID match) before existing Phase 1 (slug match):
```
Phase 0: Extract REQ-XXX-NNN:AC-M from test name → direct AC binding (100% reliable)
Phase 1: Extract REQ-XXX-NNN + slug matching (current, ~43% reliable)  
Phase 2: Test file/name lookup (JOURNEY-TEST-PLAN.md, rarely used)
Phase 3: REQ-level fallback (covers REQ but not individual ACs)
```
**Why**: Each phase is a fallback. New skeleton tests hit Phase 0. Old tests without AC-IDs hit Phase 1. Tests from JOURNEY-TEST-PLAN.md hit Phase 2.

### 5. Dashboard uses ac_id field on TestCase
**Choice**: Add `ac_id: string` to TestCase dataclass. ACPanel matches by `tc.ac_id === ac.ac_id` first, falls back to `scenario_slug`.
**Why**: Minimal dashboard change — one additional field check before existing logic.

## Risks / Trade-offs

- **[Risk] Agent modifies AC-ID prefix** → The skeleton provides the test name. If agent renames the test, the AC-ID is lost. Mitigated: skeleton tests are pre-generated, agents are instructed to only fill the body. The planning rules already say "fill skeleton, don't rename."
- **[Risk] AC ordinal instability** → If the spec changes and ACs reorder, ordinals shift. Mitigated: ordinals are assigned per-digest, not per-run. Within a single orchestration run, ACs don't change.
- **[Risk] Large diff** → Touches digest, test_plan, test_scaffold, test_coverage, dispatcher, dashboard. Mitigated: each change is additive (new field), no deletions.

## Open Questions

None.
