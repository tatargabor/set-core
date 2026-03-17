# Design: wt-web-ac-coverage-display

## Context

The orchestration backend now produces:
1. **acceptance_criteria** per digest requirement (array of strings in requirements.json)
2. **spec_coverage_result** per change (pass/fail/timeout in orchestration state)
3. **spec-coverage-report.md** (state-aware markdown report in wt/orchestration/)
4. **coverage-merged.json** (accumulated coverage across orchestration cycles)

The wt-web dashboard currently displays none of these. The frontend TypeScript types (`DigestReq`, `ChangeInfo`) don't include the new fields, and no UI components render them.

## Goals / Non-Goals

**Goals:**
- Display AC items inline in requirement tables with simple checked state (change merged = checked)
- Add cross-cutting AC tab for aggregate AC progress by domain
- Show spec coverage gate badge (SC) in GateBar alongside existing T/B/R/S badges
- Serve and render the spec coverage report
- Use merged coverage data when available

**Non-Goals:**
- Per-AC pass/fail from verifier output parsing (requires backend work — future change)
- AC editing or manual state management from the UI
- Modifying backend digest/verifier/planner logic

## Decisions

### D1: AC checked state = change status (simple mode)
**Decision:** AC items are displayed as checked when their parent requirement's associated change has a "done" status (merged/done/completed/skip_merged). All AC items for a requirement share the same checked state.

**Rationale:** The verifier currently evaluates AC as a prompt instruction but does not persist per-AC results. Deriving per-AC state would require backend changes. Simple mode provides immediate value with zero backend work.

**Alternative considered:** Parse verifier review_output for per-AC verdicts. Rejected because review_output format is not structured for reliable parsing, and would couple frontend to LLM output format.

### D2: AC tab as DigestView sub-tab (not top-level dashboard tab)
**Decision:** The AC view lives as a sub-tab within DigestView (alongside overview/requirements/domains/triage), not as a new top-level dashboard tab.

**Rationale:** AC data comes from the digest pipeline and is semantically part of digest data. A top-level tab would dilute the already-crowded tab bar. Users viewing AC are already in the digest/requirements context.

### D3: SC badge in existing GateBar pattern
**Decision:** Add spec_coverage as a 5th gate badge ("SC") using the same visual pattern as T/B/R/S. In GateDetail, add an expandable section that shows the result and optionally the coverage report excerpt.

**Rationale:** Consistency with existing gate display. Users already know the gate badge pattern. The SC gate is functionally identical to other gates (pass/fail result per change).

### D4: Coverage report as API endpoint + markdown viewer
**Decision:** New `GET /api/{project}/coverage-report` endpoint that returns the raw markdown. Frontend renders it using the existing `MarkdownPanel` component from DigestView.

**Rationale:** The report is already generated as markdown by planner.py. Reusing MarkdownPanel avoids building a new renderer. The report is small (typically < 10KB) so returning it inline is fine.

### D5: Prefer coverage-merged over coverage in overview
**Decision:** DigestView overview checks for `coverage_merged` in the API response and uses it when available, falling back to `coverage`.

**Rationale:** `coverage-merged.json` accumulates coverage across replan cycles, giving a more accurate picture. The base `coverage.json` only reflects the latest plan version.

## Risks / Trade-offs

**[Risk] AC items all checked/unchecked as a group** → Users might expect per-AC granularity. Mitigation: simple mode is clearly useful for "is this req done?" questions, and a future rich mode can add granularity.

**[Risk] GateBar getting crowded with 5 badges** → On mobile the 5 badges might wrap. Mitigation: SC only shows when spec_coverage_result exists (it's optional), so older runs without it still show 4 or fewer.

**[Risk] Coverage report file missing during active run** → The report is generated at terminal state, so during a run it may not exist. Mitigation: "No report yet" fallback message.

## Open Questions

None — all decisions are straightforward extensions of existing patterns.
