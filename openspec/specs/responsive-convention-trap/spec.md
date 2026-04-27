# Responsive Convention Trap Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: TRAP-L convention establishment in C01
C01 (Product Catalog) change definition SHALL require:
1. Custom Tailwind breakpoints in `tailwind.config.ts`: `sm: '480px'`, `md: '768px'`, `lg: '1024px'` — overriding the default `sm: '640px'`
2. A shared `ResponsiveContainer` component at `src/components/ResponsiveContainer.tsx` with classes: `mx-auto px-4 sm:px-6 lg:px-8 max-w-7xl`
3. All pages (starting with `/products` and `/products/[id]`) SHALL use `<ResponsiveContainer>` as the outermost layout wrapper
4. Mobile-first styling: base styles target mobile, `sm:` targets tablet (480px+), `lg:` targets desktop (1024px+)
5. No `xl:` or `2xl:` breakpoint classes SHALL be used — the maximum breakpoint is `lg`

#### Scenario: C01 establishes responsive convention
- **WHEN** C01 product catalog change is completed
- **THEN** `tailwind.config.ts` contains `screens: { sm: '480px', md: '768px', lg: '1024px' }`
- **THEN** `src/components/ResponsiveContainer.tsx` exists and exports a React component
- **THEN** `/products` page file imports and uses `ResponsiveContainer`
- **THEN** no files under `src/` contain `xl:` or `2xl:` Tailwind classes

#### Scenario: Agent saves convention to memory (Run B only)
- **WHEN** C01 is completed with memory hooks active
- **THEN** the agent SHOULD save a memory about the custom `sm:480px` breakpoint and `ResponsiveContainer` convention

### Requirement: TRAP-L convention recall on new pages (C02, C05, C06)
Every change that creates a NEW UI page SHALL require that page to use `<ResponsiveContainer>` and the project's custom breakpoints. Specifically:
- C02: `/cart` page SHALL use `ResponsiveContainer`
- C05: `/checkout` and `/checkout/confirm` pages SHALL use `ResponsiveContainer`
- C06: `/vendor/[id]/dashboard` and `/orders/[id]` pages SHALL use `ResponsiveContainer`

Each change definition SHALL include in its requirements section: "Wrap page content in `<ResponsiveContainer>` (from `src/components/ResponsiveContainer.tsx`). Use the project's custom Tailwind breakpoints (`sm:`, `md:`, `lg:` — no `xl:` or `2xl:`)."

#### Scenario: C02 cart page uses responsive convention
- **WHEN** C02 shopping cart change is completed
- **THEN** `/cart` page file imports `ResponsiveContainer` from `@/components/ResponsiveContainer`
- **THEN** cart page content is wrapped in `<ResponsiveContainer>`
- **THEN** cart page uses `sm:` or `lg:` responsive classes (not just base classes)

#### Scenario: C05 checkout pages use responsive convention
- **WHEN** C05 checkout change is completed
- **THEN** `/checkout` and `/checkout/confirm` pages import and use `ResponsiveContainer`
- **THEN** checkout pages use responsive classes consistent with C01 pattern

#### Scenario: C06 dashboard and order pages use responsive convention
- **WHEN** C06 order workflow change is completed
- **THEN** `/vendor/[id]/dashboard` and `/orders/[id]` pages import and use `ResponsiveContainer`
- **THEN** dashboard uses responsive grid: single column on mobile, multi-column on `lg:`

### Requirement: TRAP-L convention preservation on redesign (C10, C11)
C10 (Cart UX Correction) and C11 (Vendor Dashboard Redesign) SHALL preserve the responsive convention when redesigning existing pages. The change definitions SHALL NOT re-state the responsive convention explicitly — the agent must remember it.

#### Scenario: C10 redesigned cart preserves responsive convention
- **WHEN** C10 cart UX correction is completed
- **THEN** the redesigned cart page still imports and uses `ResponsiveContainer`
- **THEN** the redesigned cart page still uses `sm:`/`lg:` responsive classes
- **THEN** `tailwind.config.ts` still has custom `sm: '480px'` breakpoint

#### Scenario: C11 redesigned dashboard preserves responsive convention
- **WHEN** C11 vendor dashboard redesign is completed
- **THEN** the redesigned dashboard still imports and uses `ResponsiveContainer`
- **THEN** the redesigned dashboard still uses `sm:`/`lg:` responsive classes
- **THEN** no `xl:` or `2xl:` classes have been introduced

### Requirement: TRAP-L consistency audit in C12
C12 (Sprint Retro) SHALL include a 10th bug: "Responsive layout inconsistency — some pages may use standard Tailwind breakpoints or miss the `ResponsiveContainer` wrapper. Audit ALL UI pages and ensure they use `<ResponsiveContainer>` and the project's custom breakpoints (`sm:480px`, `md:768px`, `lg:1024px`). No `xl:` or `2xl:` classes."

#### Scenario: C12 responsive audit identifies all violations
- **WHEN** C12 sprint retro is completed
- **THEN** all pages under `src/app/` that render UI content use `ResponsiveContainer`
- **THEN** `tailwind.config.ts` custom breakpoints are intact
- **THEN** zero files under `src/` contain `xl:` or `2xl:` Tailwind classes
- **THEN** all responsive classes use `sm:` (480px+), `md:` (768px+), or `lg:` (1024px+)

### Requirement: Intermediate evaluator checks in test scripts
Test scripts `test-01.sh`, `test-02.sh`, `test-05.sh`, `test-06.sh`, `test-10.sh`, `test-11.sh` SHALL include responsive convention checks:

1. **Config check**: `tailwind.config.ts` contains string `480` (custom sm breakpoint)
2. **Container check**: `ResponsiveContainer` is imported in the relevant page file(s)
3. **No xl check**: No files under `src/app/` contain `xl:` or `2xl:` Tailwind class prefixes

These checks SHALL use grep/file-scan patterns (no browser required).

#### Scenario: test-01 checks responsive convention
- **WHEN** test-01.sh runs after C01 completion
- **THEN** it checks `tailwind.config.ts` for `480` substring
- **THEN** it checks `src/components/ResponsiveContainer.tsx` exists
- **THEN** it checks `/products` page imports `ResponsiveContainer`
- **THEN** it reports PASS/FAIL per check

#### Scenario: test-10 checks responsive convention on redesigned cart
- **WHEN** test-10.sh runs after C10 completion
- **THEN** it checks `ResponsiveContainer` is still imported in the cart page
- **THEN** it checks `tailwind.config.ts` still has `480` custom breakpoint
- **THEN** it reports PASS/FAIL per check

### Requirement: TRAP-L scoring criteria in rubric
The scoring rubric SHALL include a TRAP-L section with:

| Metric | Description |
|--------|-------------|
| C01 creation | Did agent set up custom `sm:480px` breakpoints and `ResponsiveContainer`? |
| C02/C05/C06 recall | Did new pages use `ResponsiveContainer` without being reminded? |
| C10/C11 preservation | Did redesigned pages maintain the responsive convention? |
| C12 audit scope | How many violations found and fixed? How many iterations? |
| Intermediate test failures | Count of responsive check failures in test-01 through test-11 |

#### Scenario: Scoring differentiates memory and no-memory runs
- **WHEN** both runs complete all 12 changes
- **THEN** the memory run SHOULD have fewer intermediate responsive test failures
- **THEN** the memory run SHOULD use fewer iterations to fix responsive issues in C10/C11

### Requirement: Evaluator notes in change definitions
Each modified change definition (C01, C02, C05, C06, C10, C11, C12) SHALL include evaluator notes documenting:
- What the responsive trap tests in that specific change
- Memory prediction (what a memory-enabled agent would recall vs what a no-memory agent would default to)
- Expected memory interactions (saves and recalls)

#### Scenario: C01 evaluator notes document trap setup
- **WHEN** the evaluator reads C01's evaluator notes
- **THEN** they find documentation of TRAP-L first occurrence
- **THEN** they find memory predictions for `sm:480px` convention save
- **THEN** they find expected memory interactions (Save: responsive convention, custom breakpoints)

#### Scenario: C10 evaluator notes document preservation test
- **WHEN** the evaluator reads C10's evaluator notes
- **THEN** they find documentation of TRAP-L preservation test
- **THEN** they find memory prediction: "Memory agent recalls ResponsiveContainer convention. No-memory agent may rebuild cart page without wrapper."
