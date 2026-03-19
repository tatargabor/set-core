## 1. Design Context Extraction for Dispatch

- [x] 1.1 Add `design_context_for_dispatch()` function to `lib/design/bridge.sh` — extracts Design Tokens section + frame-filtered Component Hierarchy from `design-snapshot.md`. Args: scope text, snapshot path. Returns filtered markdown (max 150 lines). Frame matching: case-insensitive substring of frame names against scope text.
- [x] 1.2 Integrate into `dispatch_change()` in `lib/orchestration/dispatcher.sh` — after the existing `design_ref` block (line ~428), call `design_context_for_dispatch "$scope" "$DESIGN_SNAPSHOT_DIR"` and append result to `proposal.md` under `## Design Context` header. Only if `design-snapshot.md` exists and is non-empty.
- [x] 1.3 Update `design_prompt_section()` in `bridge.sh` to add planner instruction: "Embed specific design token values (colors, sizes) and frame names in each change scope description that involves UI work"

## 2. Design Compliance in Verify Gate

- [x] 2.1 Add `build_design_review_section()` function to `lib/design/bridge.sh` — extracts concise token summary (primary colors, radius, typography scale, shadows — max 15-20 tokens) from `design-snapshot.md` for the review prompt. Returns empty string if no snapshot.
- [x] 2.2 Add `design_compliance` field to `render_review_prompt()` in `lib/set_orch/templates.py` — pass-through for the design review section (same pattern as `req_context`)
- [x] 2.3 Integrate into `review_change()` in `lib/orchestration/verifier.sh` — call `build_design_review_section` and include result in review prompt. Add instruction: "Report design token mismatches as [WARNING], not [CRITICAL]"
- [x] 2.4 Update review template in `templates.py` to include design compliance section when `design_compliance` is non-empty

## 3. Imperative Design Bridge Rule

- [x] 3.1 Rewrite `.claude/rules/design-bridge.md` — change from passive ("if available, query") to imperative ("MUST read design-snapshot.md BEFORE implementing UI", "Use EXACT token values", "Match component hierarchy"). Add conditional: if no design tools available, ignore rule entirely.

## 4. Snapshot Accessibility

- [x] 4.1 Update `fetch_design_snapshot()` in `bridge.sh` — after saving to `$DESIGN_SNAPSHOT_DIR`, also copy to `$PROJECT_ROOT/design-snapshot.md` if they differ. This ensures worktree agents can find the snapshot.

## 5. Testing

- [x] 5.1 Add unit test for `design_context_for_dispatch()` — verify frame filtering, token extraction, 150-line limit, empty snapshot case
- [x] 5.2 Add unit test for `build_design_review_section()` — verify token summary extraction, max token count, empty snapshot case
- [ ] 5.3 Manual validation: re-run MiniShop spec with updated pipeline, verify agent proposal contains design tokens and frame hierarchy, verify review output contains design compliance warnings
