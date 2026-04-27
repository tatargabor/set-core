# Tasks: v0 Design Pipeline

## Phase 1 — v0 Design Generation (manual, in browser)

- [ ] T01: Set up v0.dev project with CraftBrew theme preamble
- [ ] T02: Generate Header + Footer designs (prompt 1)
- [ ] T03: Generate Homepage (prompt 2)
- [ ] T04: Generate Product Catalog (prompt 3)
- [ ] T05: Generate Product Detail with all 4 variant states (prompt 4)
- [ ] T06: Generate Cart page with signed-in/anonymous variants (prompt 5)
- [ ] T07: Generate Checkout 3-step flow (prompt 6)
- [ ] T08: Generate Auth pages — Login, Register, Password Reset (prompt 7)
- [ ] T09: Generate Account Sidebar + Dashboard (prompt 8)
- [ ] T10: Generate User Profile + Addresses (prompt 9)
- [ ] T11: Generate Stories List + Detail (prompt 10)
- [ ] T12: Generate Subscription Wizard 5 steps (prompt 11)
- [ ] T13: Generate Admin Layout + Dashboard (prompt 12)
- [ ] T14: Generate Admin Products (prompt 13)
- [ ] T15: Generate Admin Orders (prompt 14)
- [ ] T16: Generate Admin Deliveries (prompt 15)
- [ ] T17: Generate Admin Coupons/PromoDays/GiftCards/Reviews (prompt 16)
- [ ] T18: Generate Error Pages (prompt 17)
- [ ] T19: Review all designs for token consistency and contrast

## Phase 2 — Update design-brief.md from v0 output

- [ ] T20: Update design-brief.md with any new layout patterns discovered in v0
- [ ] T21: Save v0 screenshots as reference (optional, in docs/design-ref/)

## Phase 3 — Scaffold cleanup

- [ ] T22: Remove `docs/design.make` from craftbrew scaffold
- [ ] T23: Remove `docs/design-system.md` from craftbrew scaffold
- [ ] T24: Verify `globals.css` in scaffold has correct shadcn theme variables (including muted-foreground)
- [ ] T25: Add `docs/v0-prompts.md` to scaffold for reproducibility
- [ ] T26: Update `docs/design-brief-aliases.txt` if page names changed

## Phase 4 — Pipeline changes

- [ ] T27: `run-craftbrew.sh` — remove set-design-sync invocation and Figma URL extraction
- [ ] T28: `bridge.sh` — add globals.css token extraction fallback in `design_context_for_dispatch()`
- [ ] T29: `design-bridge.md` rule — update to reflect design-system.md is optional
- [ ] T30: Verify per-change design.md generation still works (dispatcher test)

## Phase 5 — Validation

- [ ] T31: Run craftbrew E2E with new scaffold (no .make, no design-system.md)
- [ ] T32: Verify agents correctly read design-brief.md + globals.css tokens
- [ ] T33: Verify design compliance gate works without design-system.md
