# Implementation Drift Traps Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: TRAP-M evaluator notes for pagination UI drift
Change definitions C01, C03, C06, C11 SHALL include evaluator notes documenting the Pagination UI divergence trap. These notes are invisible to the agent — they only guide evaluators.

For each change, evaluator notes SHALL document:
- What pagination UI the agent chose (or didn't)
- Whether it matches or diverges from prior changes
- Expected memory interaction (save: implementation detail, recall: prior page's approach)

#### Scenario: C01 evaluator notes document initial pagination UI choice
- **WHEN** the evaluator reviews C01 transcript and output
- **THEN** they find evaluator notes guiding them to document what pagination UI pattern the agent used on `/products` (e.g., Prev/Next buttons, Load More, page numbers, none)
- **THEN** they note whether the agent built a reusable component or inline UI

#### Scenario: C03 evaluator notes check for divergence
- **WHEN** the evaluator reviews C03 transcript and output
- **THEN** they find evaluator notes guiding them to compare `/vendors` and `/orders` pagination UI with C01's `/products` pagination UI
- **THEN** they document whether the same or different pattern was used

#### Scenario: C11 evaluator notes check for reuse opportunity
- **WHEN** the evaluator reviews C11 transcript and output
- **THEN** they find evaluator notes documenting whether the agent created a reusable `<Pagination>` component or built ad-hoc pagination matching the explicit C11 requirements
- **THEN** they document whether the agent considered or recalled prior pagination implementations

### Requirement: TRAP-N evaluator notes for notification/feedback drift
Change definitions C02, C05, C06, C10 SHALL include evaluator notes documenting the Notification/feedback divergence trap.

For each change, evaluator notes SHALL document:
- What feedback pattern the agent used (alert, inline, toast, console.log, nothing)
- Whether it matches or diverges from prior changes
- Expected memory interaction

#### Scenario: C02 evaluator notes document cart feedback choice
- **WHEN** the evaluator reviews C02 transcript and output
- **THEN** they find evaluator notes guiding them to document what feedback the agent shows on cart item removal (e.g., `window.alert()`, inline message, nothing)
- **THEN** they note the specific pattern for comparison with later changes

#### Scenario: C05 evaluator notes document checkout error feedback
- **WHEN** the evaluator reviews C05 transcript and output
- **THEN** they find evaluator notes guiding them to document how checkout errors and success are communicated to the user
- **THEN** they compare with C02's feedback pattern

#### Scenario: C06 evaluator notes document status change feedback
- **WHEN** the evaluator reviews C06 transcript and output
- **THEN** they find evaluator notes guiding them to document how the vendor dashboard confirms status updates
- **THEN** they compare with C02 and C05 feedback patterns

#### Scenario: C10 evaluator notes document toast introduction
- **WHEN** the evaluator reviews C10 transcript and output
- **THEN** they find evaluator notes documenting that C10 explicitly requires toast notification
- **THEN** they document whether the agent built a reusable toast system or an ad-hoc cart-specific solution
- **THEN** they note whether the agent retroactively updated other pages' feedback patterns

### Requirement: C12 Bug 10 — Pagination UI unification
C12 (Sprint Retro) SHALL include Bug 10: "Pagination UI inconsistency — different pages use different pagination controls (some have Prev/Next, some have page numbers, some have Load More, some have nothing). Create a shared `<Pagination>` component at `src/components/Pagination.tsx` that accepts `page`, `totalPages`, `onPageChange` props and renders consistent pagination controls. Replace all ad-hoc pagination UI across the app with this component."

#### Scenario: C12 Bug 10 is correctly specified in change definition
- **WHEN** the agent reads C12 change definition
- **THEN** Bug 10 describes the pagination UI inconsistency
- **THEN** Bug 10 specifies `src/components/Pagination.tsx` as the shared component path
- **THEN** Bug 10 specifies the component props: `page`, `totalPages`, `onPageChange`

#### Scenario: C12 Bug 10 evaluation measures memory advantage
- **WHEN** both runs complete C12 Bug 10
- **THEN** the evaluator counts iterations spent on Bug 10 per run
- **THEN** `src/components/Pagination.tsx` exists and is imported by all list pages
- **THEN** no ad-hoc pagination markup exists outside the Pagination component
- **THEN** the memory run SHOULD need fewer iterations (knows which pages have pagination)

### Requirement: C12 Bug 11 — Notification system unification
C12 (Sprint Retro) SHALL include Bug 11: "Inconsistent user feedback — the cart page uses toast notifications (from C10 redesign), but other pages use `window.alert()`, inline messages, or no feedback at all. Create a shared toast/notification system at `src/components/Toast.tsx` (or extend the existing cart toast if one exists). Replace ALL `window.alert()` calls and ad-hoc feedback with the shared toast system. No `window.alert()` or `window.confirm()` calls SHALL remain in the app."

#### Scenario: C12 Bug 11 is correctly specified in change definition
- **WHEN** the agent reads C12 change definition
- **THEN** Bug 11 describes the notification inconsistency
- **THEN** Bug 11 specifies `src/components/Toast.tsx` as the shared component path
- **THEN** Bug 11 explicitly bans `window.alert()` and `window.confirm()`

#### Scenario: C12 Bug 11 evaluation measures memory advantage
- **WHEN** both runs complete C12 Bug 11
- **THEN** the evaluator counts iterations spent on Bug 11 per run
- **THEN** `src/components/Toast.tsx` exists and exports a reusable toast component
- **THEN** zero `window.alert(` or `window.confirm(` calls exist in `src/` files
- **THEN** all user-facing feedback (success, error, removal) uses the shared toast
- **THEN** the memory run SHOULD need fewer iterations (knows which pages use which pattern)

### Requirement: Test script checks for C12 unification
`test-12.sh` SHALL include checks for both Bug 10 and Bug 11:

**Bug 10 checks:**
1. `src/components/Pagination.tsx` file exists
2. All list pages (`/products`, `/vendors`, `/orders`, `/vendor/[id]/dashboard`) import `Pagination`
3. No inline `Previous`/`Next` button markup outside the Pagination component

**Bug 11 checks:**
1. `src/components/Toast.tsx` file exists
2. Zero `window.alert(` calls in any file under `src/`
3. Zero `window.confirm(` calls in any file under `src/`
4. At least 3 files import the Toast component (cart, checkout, dashboard at minimum)

#### Scenario: test-12 checks Pagination component
- **WHEN** test-12.sh runs after C12 completion
- **THEN** it verifies `src/components/Pagination.tsx` exists
- **THEN** it greps list page files for `Pagination` import
- **THEN** it reports PASS/FAIL per check

#### Scenario: test-12 checks Toast component
- **WHEN** test-12.sh runs after C12 completion
- **THEN** it verifies `src/components/Toast.tsx` exists
- **THEN** it greps for `window.alert` and `window.confirm` in `src/` (expects zero matches)
- **THEN** it reports PASS/FAIL per check

### Requirement: Scoring rubric updates for TRAP-M and TRAP-N
The scoring rubric SHALL include sections for both new traps:

**TRAP-M: Pagination UI (C01 → C03 → C11 → C12)**

| Metric | Description |
|--------|-------------|
| C01 initial UI | What pagination UI pattern did the agent build? |
| C03 divergence | Did new list pages use the same or different pagination pattern? |
| C11 reusability | Did the agent create a reusable component or ad-hoc code? |
| C12 iterations | How many iterations to create shared Pagination and replace all instances? |
| C12 completeness | Were ALL list pages migrated to the shared component? |

**TRAP-N: Notification/Feedback (C02 → C05 → C06 → C10 → C12)**

| Metric | Description |
|--------|-------------|
| C02 initial pattern | What feedback did the agent use for cart removal? |
| C05 error feedback | What pattern for checkout errors? Same or different from C02? |
| C06 status feedback | What pattern for vendor status changes? Same/different? |
| C10 toast reuse | Did the agent build a reusable toast or cart-specific? |
| C12 iterations | How many iterations to create shared Toast and replace all instances? |
| C12 completeness | Were ALL alert()/confirm() calls removed? |

#### Scenario: Rubric enables scoring of implementation drift
- **WHEN** the evaluator scores both runs
- **THEN** they can count the divergence points (how many different patterns were used across pages)
- **THEN** they can compare C12 iteration counts between runs for Bug 10 and Bug 11
- **THEN** they can determine whether memory of implementation details reduced unification effort
