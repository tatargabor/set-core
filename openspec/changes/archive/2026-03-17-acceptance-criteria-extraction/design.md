## Context

The digest pipeline currently extracts requirements with `id`, `title`, `domain`, `brief` — but no testable conditions. When dispatching, the agent gets a `scope` text and REQ IDs; when verifying, the reviewer gets `title — brief` per requirement. Both phases work from descriptions, not from contracts.

The fix is additive: add `acceptance_criteria: string[]` to the REQ schema, extract it during digest, and thread it through dispatch and verify.

## Goals / Non-Goals

**Goals:**
- Digest LLM extracts concrete AC items per REQ (HTTP contracts, state transitions, error cases)
- Implementing agent sees AC items in `input.md` alongside scope
- Reviewer sees AC items as a checkbox list in the review prompt

**Non-Goals:**
- Changing the digest JSON format in breaking ways (additive only)
- Generating test code from AC items (agent does this, not the orchestrator)
- AC validation against test files (out of scope — verifier checks coverage, not test quality)

## Decisions

**1. Format: flat string array, not Given/When/Then objects**

AC items are stored as plain strings (`"POST /api/cart/items → 201"`, `"Error 400 if qty > stock"`). Rationale: the LLM produces varied formats from specs (HTTP contracts, state assertions, user-facing behaviors) — imposing a rigid Given/When/Then structure would require the spec to already have that format. Plain strings preserve the intent without over-structuring.

**2. Graceful degradation for old digests**

`acceptance_criteria` is absent in pre-existing `requirements.json`. All consumers (dispatcher, verifier) MUST fall back to `brief` when the field is missing or empty. No migration of old digest files needed.

**3. Dispatcher injects AC per-change, not globally**

Only the AC items for a change's *assigned* REQs go into `input.md`. Cross-cutting REQs (`also_affects_reqs`) get title-only, no AC — same policy as today. Rationale: keeps input.md focused; implementing agents shouldn't write tests for REQs they don't own.

**4. Verifier renders AC as Markdown checkboxes**

```
- [ ] POST /api/cart/items → 201 with cartItemId
- [ ] Stock decremented by quantity
- [ ] Returns 400 if quantity > stock
```

The LLM reviewer treats these as pass/fail checklist items. If the diff doesn't contain evidence for an AC item, it flags `ISSUE: [CRITICAL] REQ-ID: AC item not implemented`.

**5. Digest prompt size constraint**

AC array is capped at 5 items per REQ in the prompt instruction. If a spec has more than 5 testable behaviors per requirement, it should be split — this enforces the existing single-responsibility rule.

## Risks / Trade-offs

- **[Risk] AC quality depends on spec quality** → AC extraction is best-effort; vague specs produce vague AC items. Mitigation: the `brief` fallback ensures backward compatibility; AC items add signal but aren't mandatory for dispatch/verify to function.
- **[Risk] Token growth in input.md** → Each REQ gains up to 5 AC strings. For a change with 6 REQs × 5 items = 30 lines. Acceptable growth. Mitigation: cap enforced in digest prompt.
- **[Risk] Review prompt grows** → Same 30-line cap. The `build_req_review_section()` already truncates at large sizes; AC checkboxes replace the single `brief` line, not add to it.
- **[Risk] Prompt size limit interference** → The digest prompt has an aggressive `CRITICAL: Output Size Limit` block (`MAX 50 requirements, ONE short sentence per brief`). Under token pressure the LLM may omit AC items to comply with size limits. Mitigation: place AC extraction instruction before the size limit block and clarify that the 5-item AC cap is per-requirement, not counted toward the requirements total.

## Open Questions

None — scope is fully contained to three files.
