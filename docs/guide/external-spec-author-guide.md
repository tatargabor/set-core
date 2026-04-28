# Spec Authoring Guide for SET — External Producer Edition

> **Audience:** an external system (and its LLM agent) that authors specifications which the SET orchestration framework will then implement autonomously. **Project type:** web (Next.js / TypeScript / shadcn/ui / Playwright / Prisma).
>
> **Why this exists:** SET's autonomy and quality scale with the precision of the spec it consumes. A vague spec costs 5–10× more tokens because agents re-decide things, drift across changes, and fail integration gates. A precise spec — with explicit cross-feature contracts and an authoritative design source — converges on the first attempt.
>
> **What you produce is a deliverable, not a wishlist.** The artefacts described here are the *interface* between your system and ours. Treat field names, file layouts, and contract sections as load-bearing.
>
> **About the design output:** SET's design pipeline was originally built for v0.app exports (Vercel's design tool). You are NOT expected to use v0.app. Instead, you produce the **same kind of artefact v0.app would produce** — a Next.js / shadcn / Tailwind TSX repository — directly, in your own way. The SET importer (`set-design-import`) is design-source-agnostic: as long as the directory structure and conventions described in §6 match, your design is consumed identically to a v0 export. We refer to the materialised directory as `v0-export/` only because that name is hard-coded in our importer; treat the name as a constant, not a tool reference.

---

## Table of Contents

1. [The big picture: how SET consumes your spec](#1-the-big-picture)
2. [Deliverables checklist](#2-deliverables-checklist)
3. [The master spec file](#3-the-master-spec-file)
4. [Per-feature spec files](#4-per-feature-spec-files)
5. [The seed-data catalog](#5-the-seed-data-catalog)
6. [The design package (TSX export, v0-compatible format)](#6-the-design-package)
7. [Spec ↔ design alignment & GAP analysis](#7-spec--design-alignment--gap-analysis)
8. [Phase splitting for large specs](#8-phase-splitting)
9. [Token economy: keeping the agent lean](#9-token-economy)
10. [Anti-patterns to avoid](#10-anti-patterns)
11. [Quality checklist before handover](#11-quality-checklist)
12. [Templates](#12-templates)
13. [Appendix A — How SET decomposes your spec](#appendix-a)
14. [Appendix B — Glossary](#appendix-b)

---

## 1. The big picture

SET is an orchestration framework that takes a written specification and turns it into a working application by dispatching parallel coding agents in isolated git worktrees. The pipeline is roughly:

```
Your scaffold              Your design source
(markdown + scaffold.yaml)  (TSX repo or ZIP)
        │                          │
        │                          │  set-design-import
        │                          │  clones / extracts → <scaffold>/v0-export/
        │                          │  generates docs/design-manifest.yaml
        │ ◄────────────────────────┘
        ▼
┌──────────────────────────────────────────────────────┐
│ DIGEST PHASE                                         │
│ - Reads every file under <scaffold>/docs/            │
│ - Extracts requirements (REQ-*), domains, contracts  │
│ - Detects ambiguities and missing acceptance         │
│ - Outputs structured JSON for the planner            │
└──────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────┐
│ DECOMPOSE PHASE (planner)                            │
│ - Slices the spec into independent "changes"         │
│ - Binds every design route to a change               │
│ - Computes dependency order, complexity, parallel    │
│   safety, and merge hazards                          │
│ - Outputs orchestration-plan.json                    │
└──────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────┐
│ DISPATCH PHASE (per change)                          │
│ - Creates a git worktree for the change              │
│ - Generates input.md for the agent (scope + design   │
│   tokens + project context + cross-cutting rules)    │
│ - Sends OpenSpec artefacts (proposal → tasks)        │
└──────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────┐
│ IMPLEMENTATION PHASE (the coding agent)              │
│ - Reads input.md, design.md, project rules           │
│ - Writes code, tests, migrations                     │
│ - Iterates against verification gates                │
└──────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────┐
│ GATE PHASE                                           │
│ - test / lint / build (per worktree, pre-merge)      │
│ - design-fidelity (screenshot diff vs v0 reference)  │
│ - review (code review by Claude)                     │
│ - smoke (post-merge on main)                         │
└──────────────────────────────────────────────────────┘
```

### What this means for your spec

Three operational truths:

1. **The spec is read by an LLM, not a human.** The decomposer is a planning agent that scans every word. Concise, grep-friendly structure (headings, tables, lists, kebab-case names) is read more reliably than prose.

2. **The spec is the contract between many parallel agents.** Twenty changes may execute simultaneously. They never see each other's code in flight — they only see your spec and any merged code. If your spec is the only point of agreement on enum values, error codes, table names, route slugs, or selectors, then those must be **listed exhaustively in one place** and treated as immutable.

3. **The design package is authoritative, not illustrative.** SET's current design pipeline is **v0-only**. Agents *integrate* the v0-generated TSX into the project rather than reconstruct UI from a prose description. HTML mockups are **deprecated** as primary design input — see §6.

---

## 2. Deliverables checklist

A complete spec package for a web project consists of:

A complete deliverable is **one scaffold directory** plus **one external design source** that the scaffold references.

**The scaffold** is a directory you author and hand to SET (typically committed to a git repo, but `set-design-import` can run against any local path). It contains the spec markdown, the orchestrator config, and a pointer to the design source. Layout:

```
<project-scaffold>/
├── scaffold.yaml                # MANDATORY — project type, template, design_source pointer
├── docs/
│   ├── v1-<project-name>.md     # MASTER SPEC (overview + cross-feature contracts)
│   ├── features/                # one file per feature domain — names are project-specific
│   │   ├── auth.md              #   (auth is universal; the rest depends on your project)
│   │   ├── <domain-1>.md        #   e.g. billing.md / cart-checkout.md / publishing.md
│   │   ├── <domain-2>.md        #   e.g. workspaces.md / catalog.md / moderation.md
│   │   ├── admin.md             #   (admin / back-office is common across project types)
│   │   └── ...
│   ├── catalog/                 # seed-data definitions — files are project-specific
│   │   ├── users.md             #   (universal: at least one regular + one admin user)
│   │   ├── <records-1>.md       #   e.g. products.md / plans.md / articles.md
│   │   └── ...
│   ├── design-direction.md      # brand vibe + per-page direction (drives the design source)
│   ├── content-fixtures.yaml    # seed data for the design-fidelity reference render
│   ├── design-brief.md          # OPTIONAL 1-page non-authoritative brand vibe note
│   ├── gap-analysis.md          # pre-handover spec ↔ design alignment report (see §7)
│   ├── (design-manifest.yaml)   # GENERATED by set-design-import; do NOT hand-author
│   └── (v0-import-report.md)    # GENERATED by set-design-import; review for findings
├── shadcn/                       # OPTIONAL — overrides for shadcn primitives the agent will use
├── templates/                    # OPTIONAL — additional template overrides
└── (v0-export/)                  # GENERATED by set-design-import; gitignore this
```

**The design source** is a self-contained Next.js / shadcn / Tailwind TSX project. It can be:
- A **separate git repo** (recommended), referenced by `scaffold.yaml`'s `design_source: { type: v0-git, repo, ref }` block, OR
- A **ZIP archive** living at any path, referenced by `design_source: { type: v0-zip, path }`

`set-design-import` clones / extracts the design source into `<scaffold>/v0-export/`. Structure of the design source itself is detailed in §6 — that's the larger of the two contracts.

The reason for the split: the spec markdown evolves freely (you edit it as you learn), while the design source is a versioned artefact (the importer pins to a SHA). Keeping them in separate repos lets each have its own history and review process. If you don't have separate hosting for the design, the ZIP fallback (§6.17) keeps everything inside the scaffold.

### Where to put new spec material

If a future requirement isn't covered by the files listed above, **add it to the scaffold's `docs/` directory** rather than inventing a new location. The planner reads everything under `docs/` recursively. The exception is the design source itself — that always lives outside the scaffold (or as a ZIP referenced by `scaffold.yaml`), never as TSX inside `docs/`.

### Mandatory vs optional

| Artefact | Status | Notes |
|---|---|---|
| `scaffold.yaml` | **MANDATORY** | Drives `set-project init` and design import. Declares `design_source`. |
| `docs/v1-<project>.md` | **MANDATORY** | The hub document. Without contracts here, agents drift. |
| `docs/features/*.md` | **MANDATORY** for any project with >1 feature domain | Single-file specs are accepted only for projects with 1 feature, ≤200 lines. |
| `docs/catalog/*.md` | **MANDATORY** if your app has seed data | Without this, agents invent records that conflict across changes. |
| Design source (external repo or ZIP) | **MANDATORY** for any UI work | Real TSX. Replaces HTML mockups (which force agents to reconstruct UI from prose). |
| `docs/design-direction.md` | **STRONGLY RECOMMENDED** | The brand-vibe + per-page narrative that drove the design source. Lets the design be regenerated reproducibly when scope grows. |
| `docs/content-fixtures.yaml` | **MANDATORY** when the design-fidelity gate is enabled | Reference data the gate renders both the design source and the agent's build with. |
| `docs/design-brief.md` | OPTIONAL | A short brand-vibe note for written content (subject lines, microcopy tone). Non-authoritative for layout. |
| `docs/gap-analysis.md` | **STRONGLY RECOMMENDED** | Pre-handover GAP analysis report covering routes / components / data shape / states / errors / selectors / tokens / conventions. See §7. |
| `docs/design-manifest.yaml` | **DO NOT HAND-AUTHOR** | Generated by `set-design-import` from the design source. |
| `docs/v0-import-report.md` | **DO NOT HAND-AUTHOR** | Generated by `set-design-import` validator pass — review for findings. |

---

## 3. The master spec file

**Path:** `docs/v1-<project-name>.md` (the `v*-*.md` glob is how SET detects it as the master).

The master file is the **hub**: it tells SET what the project is, lists the **cross-feature contracts** (the things that, if disagreed upon by parallel changes, will produce broken code), and gives the human-readable verification checklist.

> **About the examples in this guide.** SET implements *any* web project — SaaS dashboards, internal tools, marketing sites, CMSs, e-commerce, fintech, social platforms, B2B portals. The **structure** described in §3-§5 (domain models, error catalog, testid registry, conventions, requirements, catalog files) applies to all of them. The **specific contents** of the example tables below — Coupon validation codes, Cart endpoints, Coffee product catalog, etc. — are for an illustrative e-commerce project (the working CraftBrew reference). Your project will have entirely different domains: a SaaS app might have BILLING_*, WORKSPACE_*, INVITE_* error codes; a CMS might have PUBLISH_*, MODERATION_*, ASSET_* codes; a fintech app might have TRANSFER_*, KYC_*, LIMIT_* codes. Read the examples for *shape*, not for *content*. Where this guide says "use these EXACT codes", the rule applies to whatever codes *you* declare in your master spec — not to the literal codes shown in the example.

### Required sections (in this order)

```markdown
# <Project Name> v1 — <One-line description>

> Business specification — the complete functional and content description of <project>.

## Spec Structure

(Brief paragraph explaining that this is the hub, with detailed feature specs in features/ and seed data in catalog/.)

## Shared Domain Models (cross-feature index)

## Error Code Catalog

## E2E Test Conventions

## Business Conventions

## Project-Wide Directives (orchestrator instructions)

## Verification Checklist
```

Each is detailed below.

### 3.1 Shared Domain Models

A table of every persisted entity, with **exact** field names and relationships. This is the **single source of truth for schema names**. Without this, two parallel changes will pick `userId` vs `user_id` vs `usrId`, and the migration will fight itself.

The example below mixes universal entities (User) with domain-specific ones (Product, Order — e-commerce). For a SaaS app the table would list Workspace, Membership, Plan, Subscription, Invoice; for a CMS, Article, Asset, Author, Taxonomy, Revision; for an internal tool, Record, Lookup, Audit. The shape is the contract; the entities are yours.

```markdown
## Shared Domain Models (cross-feature index)

These entities are referenced from multiple features. To prevent schema drift,
use these exact entity names, key fields, and relationships. Field types are
illustrative — agents may add fields, but MUST NOT rename the listed ones.

| Entity | Key fields | Relationships |
|---|---|---|
| `User` | `id`, `email` (unique), `password_hash`, `name`, `role` (`USER`\|`ADMIN`), `created_at` | (project-specific relationships) |
| `<Entity>` | `id`, `<field>`, `<field>`, `<status_enum>` (`<VAL_A>`\|`<VAL_B>`), `created_at` | hasMany / belongsTo ... |
| `<Entity>` | ... | ... |
| ... | ... | ... |

**Rules for changes:**
- A change that introduces a new entity adds it here in the same PR.
- A change that adds a field to an existing entity does NOT need to update this table.
- NEVER rename an entity or one of its listed key fields without updating this index AND every reference across `features/*.md`.
- State enum values are listed in UPPER_SNAKE_CASE — use these exact strings in code.
```

#### Rules for the domain table

- **`id` is always present** — assume `string` (UUID/cuid) unless you specify otherwise.
- **Enum values in UPPER_SNAKE_CASE**, listed inline with `|` separators inside the cell.
- **Never abbreviate** field names (`organizationId` not `orgId`, `customer_id` not `cust_id`).
- **List the relationships** — `hasMany` / `belongsTo` / `many-to-many via JoinTable`. This drives migration ordering.
- **Pick a casing convention and stick to it across all features.** snake_case for DB columns is recommended; camelCase for JSON payloads. State this in §3.4 (Business Conventions).

### 3.2 Error Code Catalog

Stable machine-readable error codes (UPPER_SNAKE_CASE) with HTTP status and i18n key. **This becomes the contract for E2E test assertions** — agents that invent new codes break tests written by other agents.

The catalog is organised as one sub-table per *domain* (auth, billing, checkout, content moderation, file upload, rate limiting, whatever your project actually has). Auth almost always appears; the rest depends entirely on the project type.

```markdown
## Error Code Catalog

User-facing validation errors return a stable machine-readable `code` plus an
HTTP status, plus a localized message keyed by i18n. The `code` is what E2E
tests assert on (via `data-testid="error-banner"` + the code as
`data-error-code`); the message is what the user sees. Use these EXACT codes.

API response shape (4xx/5xx errors):
```json
{
  "error": {
    "code": "<UPPER_SNAKE_CASE_CODE>",
    "message": "Human-readable, already localized",
    "field": "optional_field_name"
  }
}
```

### Auth errors  (universal — virtually every project has these)

| Code | HTTP | i18n key | When |
|---|---|---|---|
| `AUTH_INVALID_CREDENTIALS` | 401 | `error.auth.invalid` | Wrong email or password (do NOT distinguish — single message) |
| `AUTH_EMAIL_TAKEN` | 409 | `error.auth.email_taken` | Registration with already-registered email |
| `AUTH_PASSWORD_TOO_SHORT` | 400 | `error.auth.password_too_short` | < 8 characters |
| `AUTH_RESET_TOKEN_INVALID` | 400 | `error.auth.token_invalid` | Reset token does not exist or malformed |
| `AUTH_RESET_TOKEN_EXPIRED` | 400 | `error.auth.token_expired` | Token > 1 hour old |
| ... | ... | ... | ... |

### <Your-domain> errors  (one sub-table per domain)

(Add as many sub-tables as you have domains. See the rules below.)

**Rules:**
- The `code` is contractual; renaming it breaks E2E tests. Adding new codes is fine.
- The user-visible message MAY be reworded (it's i18n-keyed); the i18n key MUST stay stable.
- Server NEVER returns raw exception messages or stack traces to the client.
- For 5xx errors not in this table, fall back to `code: "INTERNAL_ERROR"` HTTP 500.
```

#### What counts as a "domain"

A domain is a coherent feature area whose codes share a prefix. Pick whatever maps to your project:

| Project type | Typical domains |
|---|---|
| **E-commerce** | AUTH_*, CART_*, COUPON_*, GIFT_CARD_*, STOCK_*, CHECKOUT_*, ORDER_*, REVIEW_*, SUBSCRIPTION_*, RETURN_* |
| **SaaS / B2B** | AUTH_*, WORKSPACE_*, INVITE_*, BILLING_*, SUBSCRIPTION_*, SEAT_*, PERMISSION_*, API_KEY_*, WEBHOOK_* |
| **CMS / publishing** | AUTH_*, CONTENT_*, PUBLISH_*, ASSET_*, COMMENT_*, MODERATION_*, REVISION_*, TAXONOMY_* |
| **Fintech** | AUTH_*, KYC_*, ACCOUNT_*, TRANSFER_*, LIMIT_*, AML_*, CARD_*, STATEMENT_* |
| **Social** | AUTH_*, POST_*, COMMENT_*, REPORT_*, FOLLOW_*, BLOCK_*, MEDIA_*, NOTIFICATION_* |
| **Internal tools** | AUTH_*, RECORD_*, EXPORT_*, IMPORT_*, AUDIT_*, JOB_* |
| **Booking / scheduling** | AUTH_*, BOOKING_*, AVAILABILITY_*, CANCELLATION_*, PAYMENT_*, NOTIFICATION_* |

These are not prescriptive groupings — they are illustrative of the *granularity* you want. Pick whatever maps to the natural feature boundaries in your project.

#### Example sub-table from an e-commerce project

For concreteness, here's how an e-commerce project might fill in one of its domain sub-tables (Coupon validation):

```markdown
### Coupon validation

| Code | HTTP | i18n key | Condition |
|---|---|---|---|
| `COUPON_NOT_FOUND` | 404 | `error.coupon.not_found` | Code does not exist |
| `COUPON_EXPIRED` | 400 | `error.coupon.expired` | `expires_at < now()` |
| `COUPON_MAX_USES_REACHED` | 400 | `error.coupon.max_uses` | `uses_count >= max_uses` |
| `COUPON_FIRST_ORDER_ONLY` | 400 | `error.coupon.first_order_only` | User has prior orders |
| `COUPON_MIN_ORDER_NOT_MET` | 400 | `error.coupon.min_order` | Subtotal < `min_order` |
```

A SaaS project would have a similarly-shaped table for `BILLING_*` codes; a CMS for `PUBLISH_*`; a fintech app for `TRANSFER_*`. The shape is the contract; the contents are yours.

#### How exhaustive should the catalog be?

Cover **every error a UI element will display.** Skip purely server-internal errors (those become 500 INTERNAL_ERROR by the fallback rule). A typical project has 20–60 codes; a simple CRUD app may have only 10–15.

### 3.3 E2E Test Conventions

Three sub-sections:

**(a) Selector strategy** — fix the contract for how Playwright tests will find DOM elements:

```markdown
### Selector strategy (in priority order)

1. **`getByRole()` with accessible name** — gold standard. Use for buttons,
   links, form fields, headings.
   ```ts
   page.getByRole('button', { name: /add to cart/i })
   ```
2. **`data-testid` for non-semantic elements** — when role-based selection
   is impossible (badges, image-only buttons, modals). Naming pattern:
   `data-testid="<feature>-<element>[-<modifier>]"` (kebab-case).
3. **Never use `text=` selectors for assertions on translated UI text** —
   they are locale-coupled. Use role+name with case-insensitive regex, OR
   i18n-keyed `data-i18n-key` attributes.
```

**(b) Required `data-testid` registry** — a table listing every `data-testid` that E2E tests will rely on. This is the **DOM contract**. Without it, every change invents its own test IDs, and cross-feature tests fail.

The example rows below come from an e-commerce project. Adapt the entries to whatever pages and components your project actually has — the only universal entries are `error-banner` (any form) and the domain-specific status badges. Naming pattern: `<feature>-<element>[-<modifier>]` in kebab-case.

```markdown
### Required `data-testid` registry

| `data-testid` | Component / page | Notes |
|---|---|---|
| `error-banner` | Any form | Has `data-error-code` matching Error Code Catalog (universal) |
| `<feature>-status-badge` | Detail / list pages | Has `data-status` (UPPER_SNAKE_CASE) when the feature has a state machine |
| `<feature>-<element>` | <Page or component> | <Notes — what tests rely on this> |
| ... | ... | ... |

(Example rows from an e-commerce project: `header-cart-icon`, `header-cart-badge`,
`product-card` with `data-product-id`, `cart-item-row` with `data-variant-id`,
`checkout-step-1` / `checkout-step-2` / `checkout-step-3` for stepper containers,
`order-status-badge` with `data-status="NEW"` etc.)
```

**(c) Test data conventions** — how test users / fixtures / time control work:

```markdown
### Test data conventions

- **Test users:** seed creates one regular user and one admin user, both with
  known credentials. Convention: `user1@example.com / user1pass` and
  `admin@example.com / adminpass`. Tests use these directly; do not create
  new users mid-test unless testing the registration flow.
- **Adversarial fixtures:** seed includes intentional XSS-attempt strings,
  SQL-injection-like payloads, oversized inputs in user-generated-content
  fields. These are NOT bugs — they test sanitization. Listed explicitly in
  the relevant `catalog/*.md` files.
- **Test isolation:** each test resets the DB to seed state via `beforeEach`
  (use `prisma db push --force-reset && pnpm seed`, OR a transaction wrapper).
- **Time-sensitive tests:** for any logic that reads the wall clock (token
  expiry, scheduled jobs, time-window features), use `page.clock.install()`
  to fix `Date.now()`. Do not rely on real wall clock.
```

### 3.4 Business Conventions

Settle the cross-cutting decisions that 20 agents must agree on:

```markdown
## Business Conventions

(Declare every cross-cutting decision that has more than one reasonable
answer. Below is a checklist of areas to cover — adapt the values to your
project. Omit items that do not apply.)

- **Currency:** <if your app handles money — declare currency code and
  display format, e.g. "USD, formatted '$1,234.50'">
- **Languages:** <if multi-locale — primary + secondary, URL strategy
  (locale segments? cookie? subdomain?), translation source>
- **Database casing:** <snake_case vs camelCase for column names; JSON
  payload casing if different>
- **Auth:** <session cookie vs JWT; OAuth providers; expiry; MFA;
  multi-tenancy isolation strategy>
- **IDs:** <UUID v4 vs cuid vs nanoid vs autoincrement; visible to users?>
- **Money:** <integer minor units vs Decimal; currency conversion rules>
- **Dates:** <ISO 8601 in API; UI display format; user-local vs UTC display>
- **Soft delete:** <yes (deleted_at nullable) vs hard delete; per-entity
  override>
- **Audit:** <which mutations write audit rows; retention policy>
- **Time zones:** <server timestamps in UTC always; UI display zone — user
  preference vs project-fixed>
- **File uploads:** <if applicable — storage backend, size limits, allowed
  MIME types, virus scanning>
- **Rate limiting:** <if applicable — per-IP, per-user, per-endpoint thresholds>
- **PII handling:** <if applicable — encryption at rest, redaction in logs,
  GDPR / CCPA right-to-delete>
```

These statements **prevent contradiction across changes**. State everything that has more than one reasonable answer.

### 3.5 Project-Wide Directives

A YAML-fenced block of orchestrator-relevant settings:

```markdown
## Project-Wide Directives (orchestrator instructions)

```yaml
test_command: pnpm test
e2e_command: npx playwright test
smoke_command: pnpm test:smoke
build_command: pnpm build
default_model: opus
max_parallel: 1            # 1 if heavy schema churn; 3 if features mostly independent
auto_replan: true
review_before_merge: true
```
```

### 3.6 Verification Checklist

A human-runnable smoke test for the orchestrator's verifier and for the human reviewing the finished app:

```markdown
## Verification Checklist

After full orchestration, the following must hold. The first six items below
are universal; the last block is project-specific — replace with concrete
end-to-end scenarios for your project's primary user journeys.

- [ ] All migrations applied cleanly from a fresh DB (`pnpm prisma migrate reset`)
- [ ] Seed runs without errors and produces the cataloged records
- [ ] Homepage renders at `/` with brand chrome
- [ ] All routes from `design-manifest.yaml` are reachable and styled
- [ ] All `data-testid` selectors from the registry exist in the DOM
- [ ] All error codes from the catalog are returned by at least one endpoint
- [ ] Playwright suite passes locally (`npx playwright test`)
- [ ] No `console.log` statements remain in `src/`

Project-specific scenarios (replace with your own):
- [ ] <Anonymous user can complete the primary unauthenticated journey>
- [ ] <Authenticated user can complete the primary authenticated journey end-to-end>
- [ ] <Admin user can transition the primary state-machine entity through every state>
- [ ] <Search / filter / pagination work on every list page>
- [ ] <Email / notification side-effects are queued (or sent in dev mode)>
```

---

## 4. Per-feature spec files

**Path:** `docs/features/<feature-domain>.md`. One file per feature domain. Pick names that match natural product boundaries: `auth.md`, `cart-checkout.md`, `catalog.md`, `subscription.md`, `admin.md`, `reviews-wishlist.md`, `i18n.md`, `seo.md`, `email-notifications.md`.

### Why split by feature

The decomposer reads each file in parallel and asks: "what changes does this feature need?" A 2,000-line single-file spec forces the planner to either truncate (losing detail) or to make one giant L-sized change (which the implementing agent will struggle with). Splitting into 8–12 focused files of 100–400 lines each gives clean boundaries.

### Required structure per feature file

```markdown
# <Feature Name>

## Overview

(2–4 sentence summary of what this feature does and why it exists.)

## Requirements

(Numbered list of requirements as REQ-<DOMAIN>-NNN. Each requirement has
acceptance criteria. See "Requirement format" below.)

## Data

(Which entities from the master domain table this feature reads/writes.
Any feature-specific fields agents need to add.)

## API Surface / Server Actions

(Endpoints OR server actions this feature exposes. Group by domain.)

## UI / Routes

(Routes this feature owns. Reference design-manifest.yaml route paths exactly.)

## State Machines (if applicable)

(Allowed state transitions, with side effects per transition.)

## Error Cases

(Reference error codes from the master Error Code Catalog. List which codes
this feature can emit, when, and how the UI presents them.)

## Edge Cases & Business Rules

(Stock-conflict, race-condition, idempotency, time-zone — anything subtle.)

## Test Coverage

(One bullet per scenario the E2E test suite must cover.)
```

### Requirement format

Each requirement is a contract item the digest will extract. Format below uses an Auth example because it applies to virtually every web project; substitute your own domain's verb.

```markdown
### REQ-AUTH-001: Email + password registration

**Summary:** A new visitor can create an account using email and password.

**Acceptance criteria:**
- AC-1: Registration form on `/register` with fields: email, password,
  password-confirm, terms checkbox
- AC-2: Email must match RFC 5322; password min 8 characters; passwords
  must match; terms must be checked
- AC-3: Validation rejects already-registered email with error code
  `AUTH_EMAIL_TAKEN`
- AC-4: Validation rejects unaccepted terms with error code
  `AUTH_TERMS_NOT_ACCEPTED`
- AC-5: On success, user is created with `role=USER`, `email_verified=false`,
  a verification email is queued, and the user is redirected to a
  "check your inbox" page
- AC-6: User cannot log in until they click the verification link (which
  sets `email_verified=true` and signs them in)
- AC-7: Verification token expires after 24 hours; expired tokens return
  `AUTH_VERIFY_TOKEN_EXPIRED` and a "resend verification" CTA
```

#### Requirement quality rules

- **One requirement per discrete user-visible behavior.** "Register" is one REQ; "Email verification" is another; "Resend verification email" is another.
- **Numbered acceptance criteria** — agents implement to AC granularity. AC numbers become test names.
- **Reference error codes** by their exact name from the catalog.
- **State the WHY only when non-obvious.** Standard behaviour ("required fields rejected") needs no justification; non-obvious choices ("we never reveal whether an email is registered, to prevent enumeration") warrant a one-sentence rationale.
- **Do not specify implementation.** No file paths, no function names, no class structure. The agent picks those.

### Example: a complete feature file outline

> **Illustrative only.** The example below is one feature file from an e-commerce project (CraftBrew). The *structure* (Overview → Requirements → Data → API → UI → State Machine → Errors → Edge Cases → Test Coverage) is what to copy. The *contents* — Cart, Stripe, Order State Machine — are domain-specific to e-commerce. A SaaS billing feature would have the same skeleton but talk about Subscription, Invoice, Webhook; a CMS publishing feature would talk about Draft, Publish, Schedule, Revision.

```markdown
# Cart & Checkout

## Overview

The shopping cart is session-based for anonymous users and user-bound for
authenticated users. Checkout is a 3-step flow (Shipping → Payment →
Confirmation) with deterministic zone-based shipping pricing and
transactional order creation.

## Requirements

### REQ-CART-001: Add to cart
(...)

### REQ-CART-002: Cart page
(...)

### REQ-CHK-001: Step 1 — Shipping address
(...)

### REQ-CHK-002: Step 2 — Payment (Stripe)
(...)

### REQ-CHK-003: Step 3 — Confirmation
(...)

### REQ-ORD-001: Order processing transaction
(...)

## Data

Reads: `Product`, `Variant`, `User`, `Address`, `Coupon`, `GiftCard`
Writes: `Cart`, `CartItem`, `Order`, `OrderItem`, `OrderCoupon`,
`GiftCardTransaction`, `AuditLog`

Adds field to `Order`: `payment_intent_id` (Stripe PI ID, indexed).

## API Surface

Server actions (no public REST):
- `addToCart(variantId, quantity)`
- `updateCartItem(cartItemId, quantity)`
- `removeCartItem(cartItemId)`
- `applyCoupon(code)`
- `applyGiftCard(code)`
- `createOrder(addressId, paymentMethodId)`

Webhooks:
- `POST /api/webhooks/stripe` — payment_intent.succeeded, .payment_failed

## UI / Routes

- `/kosar` — cart page
- `/penztar` — checkout (3 steps via local UI state, not separate routes)
- `/rendelesek/[orderNumber]` — order detail / confirmation

(Match exactly to `design-manifest.yaml` route paths.)

## Order State Machine

`NEW` → `PROCESSING` → `PACKED` → `SHIPPING` → `DELIVERED`
                                                  ↓
                                             (terminal)
Plus `CANCELLED` reachable from `NEW`, `PROCESSING`, `PACKED` only.

| From → To | Trigger | Authorization | Side effects |
|---|---|---|---|
| (none) → `NEW` | Successful order placement | Customer (own checkout) | Stock decreased; cart cleared; email: order confirmation |
| `NEW` → `PROCESSING` | Admin "Start processing" | ADMIN | Audit log |
| ... | ... | ... | ... |

(Be exhaustive — list every legal transition AND state explicitly that
non-listed transitions return HTTP 409 with code `ORDER_INVALID_TRANSITION`.)

## Error Cases

This feature can emit:
- `STOCK_INSUFFICIENT` (add to cart, checkout)
- `STOCK_VARIANT_INACTIVE` (add to cart, checkout)
- `COUPON_*` (cart page, applyCoupon)
- `GIFT_CARD_*` (cart page, applyGiftCard)
- `ADDRESS_REQUIRED` (Step 1)
- `PAYMENT_DECLINED`, `PAYMENT_PROCESSING_ERROR` (Step 2)
- `ORDER_INVALID_TRANSITION` (admin status changes)

UI presentation: each error renders in `data-testid="error-banner"` with
`data-error-code="<CODE>"`. Inline form errors render under the offending
field with `data-testid="field-error-<field-name>"`.

## Edge Cases & Business Rules

- Cart items do NOT reserve stock — stock is checked at checkout time.
- If stock changes while items are in the cart, return to cart shows a
  warning banner and disables affected lines.
- Stripe payment runs OUTSIDE the DB transaction; if payment succeeds but
  the DB transaction fails, the system MUST issue a Stripe refund as
  compensation (logged + retried by background job).
- Concurrent admin status transitions are serialized by `SELECT ... FOR
  UPDATE` on the order row.
- Status transitions are idempotent — re-clicking a button is a no-op if
  the order is already in the target state. Email NOT re-sent.

## Test Coverage

Functional E2E (`tests/e2e/cart-checkout.spec.ts`):
- Happy path: anonymous user adds 2 items, logs in, completes checkout
- Stock conflict: race condition simulation, cart shows warning
- Coupon application: valid coupon applies, invalid returns correct code
- Gift card covers full order: Step 2 (Payment) is skipped
- Admin: order transitions through every state with correct emails

Smoke (`tests/smoke/checkout.smoke.spec.ts`):
- `/kosar` renders without 500
- `/penztar` redirects unauthenticated users to login
```

---

## 5. The seed-data catalog

**Path:** `docs/catalog/<domain>.md`. One file per major data domain.

### Why catalog matters

If you say "ten records of category X" without listing them, every change that touches the catalog will invent different records. Some will use lowercase names, others Title Case. One agent writes seed data; another writes a UI page that filters by category and assumes a different list. Tests fail because the assertions don't match the seed.

### What goes in the catalog

Anything the application needs to be present at first launch. Examples by project type:

| Project type | Catalog files |
|---|---|
| **E-commerce** | `products.md`, `users.md` (test users + admin), `coupons.md`, `categories.md` |
| **SaaS** | `users.md` (test workspace owners), `workspaces.md`, `plans.md` (pricing tiers), `roles.md` (RBAC seed) |
| **CMS** | `users.md` (editor / author / admin), `content-types.md`, `sample-articles.md`, `taxonomies.md` |
| **Internal tool** | `users.md`, `record-fixtures.md`, `lookup-tables.md` (statuses, regions, departments) |
| **Booking** | `users.md`, `services.md`, `time-slots.md`, `locations.md` |

The pattern is always the same: human-readable list of canonical records, one file per domain.

### Catalog file structure

Each catalog file is a list of structured records that your seed script will insert verbatim. The example below is one file from an e-commerce project — adapt the field names to match whatever domain table entities your project actually has.

```markdown
# Coffee Products  (example — e-commerce project)

(8 products — all `category: COFFEE`, all bilingual HU/EN names and
descriptions, all 2 variants minimum: 250g whole bean + 250g ground.)

---

### 1. Etióp Yirgacheffe

- `slug`: etiop-yirgacheffe
- `name_hu`: Etióp Yirgacheffe
- `name_en`: Ethiopian Yirgacheffe
- `description_hu`: Virágos, citrusos, könnyű testű kávé Yirgacheffe régióból. ...
- `description_en`: Floral, citrusy, light-bodied coffee from the Yirgacheffe region. ...
- `origin`: Ethiopia, Yirgacheffe
- `roast`: light
- `processing`: washed
- `flavor_notes`: ["jasmine", "bergamot", "lemon"]
- `altitude`: 1900-2100m
- `farm`: Konga Cooperative
- `base_price`: 4990
- variants:
  - sku `YIR-250-WHOLE`, options `{ size: "250g", form: "whole" }`, price_modifier 0, stock 50
  - sku `YIR-250-GROUND`, options `{ size: "250g", form: "ground" }`, price_modifier 0, stock 30
- `active`: true

### 2. Kolumbiai Huila
... (etc, all 8) ...
```

### Adversarial / edge-case fixtures

Include **deliberate boundary inputs** so the seed exercises sanitization:

```markdown
### Adversarial review fixtures (test data for sanitization)

These are seeded into the DB to verify the review feature handles malicious
or malformed input. They are NOT bugs — agents must keep them in seed:

- Review with title containing `<script>alert(1)</script>` — must render
  escaped, not execute
- Review with text containing 5,000 character lorem ipsum — must wrap, not
  break layout
- Review with emoji-only text "🔥🔥🔥" — must render
- Review with mixed RTL/LTR text — must render readable
```

---

## 6. The design package

> **The biggest single lever for design fidelity.** SET does not accept HTML/PNG mockups as primary design input. The design contract is a **complete TSX repository** in the same shape v0.app produces, that the SET importer (`set-design-import`) clones into `v0-export/`. Agents *mount* those components into the project rather than re-inventing them. The importer is design-source-agnostic — it does not care whether v0.app, your own LLM, a designer, or a code generator produced the TSX, only that the directory matches the contract below.

### 6.1 Required technology stack — non-negotiable

The design repository MUST use exactly the following stack. The SET importer, the agent's project, and the design-fidelity gate all assume this stack. Any deviation breaks `set-design-import` (the validator runs `pnpm build` and `tsc --noEmit` against this stack), or causes the agent's worktree to diverge from the reference build (failing the screenshot diff).

| Layer | Required | Notes |
|---|---|---|
| **Language** | TypeScript ≥ 5.7 | `.tsx` for components, `.ts` for utilities. No `.jsx` or `.js`. `strict: true` in tsconfig. |
| **Framework** | Next.js 15 or 16 | **App Router only** — `app/<route>/page.tsx`. Pages Router (`pages/*.tsx`) is NOT supported and will fail manifest generation. |
| **React** | React 19 (`^19.0.0`) + react-dom `^19.0.0` | Server Components are allowed (default in App Router); Client Components require `"use client"` directive at file top. |
| **Styling** | Tailwind CSS v4 (`^4.0.0`) | Configure via `@tailwindcss/postcss`. Theme tokens live as CSS custom properties in `app/globals.css`. NO inline `style` attributes for layout. NO CSS Modules. NO styled-components / emotion. |
| **Component library** | shadcn/ui (style: `new-york`, baseColor: `neutral`, cssVariables: `true`) | Primitives in `components/ui/<name>.tsx`. Configured via `components.json`. NO MUI / Chakra / Mantine / Ant Design / Bootstrap. |
| **Headless primitives** | Radix UI (`@radix-ui/react-*`) | Underlies the shadcn primitives. Add a `@radix-ui/react-<name>` dep for each shadcn primitive used. |
| **Forms** | `react-hook-form` + `zod` + `@hookform/resolvers` | The shadcn `Form` primitive requires this trio. NO Formik / react-final-form. |
| **Class utilities** | `clsx` + `tailwind-merge` | Combined via the canonical `cn()` helper in `lib/utils.ts`. shadcn primitives import this — do not replace. |
| **Icons** | `lucide-react` | Configured in `components.json` as `iconLibrary: "lucide"`. NO heroicons / react-icons / font-awesome. |
| **Variants** | `class-variance-authority` (cva) | Used by shadcn primitives for variant props (button variants, badge variants, etc.). |
| **Animation** | `framer-motion` (optional) + `tw-animate-css` | Use sparingly — animations are part of the design contract and the agent will preserve them. |
| **Theming** | `next-themes` | Drives the `.dark` variant in `app/globals.css`. Mount `ThemeProvider` in `app/layout.tsx`. |
| **Toasts** | `sonner` | Mounted via shadcn's `Toaster` primitive. NO react-hot-toast / react-toastify. |
| **Date utilities** | `date-fns` ≥ 4 + `react-day-picker` ≥ 9 | Used by the shadcn `Calendar` primitive. NO moment / dayjs / luxon. |
| **Package manager** | pnpm | The importer runs `pnpm install` and `pnpm build`. npm/yarn lockfiles are ignored. Ship a `pnpm-lock.yaml` if you can. |
| **Build tool** | Next.js's built-in (Turbopack/Webpack) | NO Vite, NO custom Webpack. The `next build` script is what the importer invokes. |

#### What the design repo MUST NOT contain

These are **hard exclusions** — the importer rejects builds that include them, or the agent fails to integrate them cleanly:

- **No real backend dependencies:** no `prisma`, no `@prisma/client`, no database SDKs, no `axios` to a real API, no `swr` / `tanstack-query` pointing at real endpoints. The build must succeed offline with no network.
- **No `app/api/**` route handlers:** the design renders deterministic UI from inlined data only. Route handlers belong in the agent's worktree.
- **No real authentication:** no `next-auth` config, no `@clerk/*`, no Auth0 SDK initialised. Auth state may be *simulated* by a React Context (see "tolerated" below) — but the design must not actually call an identity provider at build or runtime.
- **No tests:** no `*.test.tsx` / `*.spec.tsx`, no `playwright/` / `__tests__/` directories. Tests are authored by the implementing agent on the project side.
- **No environment dependence:** no `process.env.*` reads outside of Next.js's built-in `NEXT_PUBLIC_*` defaults. The importer builds the design repo with no `.env` file.
- **No CMS adapters with real credentials:** no Contentful / Sanity / Strapi *clients* talking to a real workspace. Content is inlined.
- **No i18n runtime:** no `next-intl` / `next-i18next` / `i18next` initialised. UI strings are hardcoded literals at the design level (the agent wires i18n later if the spec requires it).

#### What is tolerated (and how the agent handles it)

These patterns are **typical of v0.app output and acceptable**. The implementing agent removes or rewires them as part of normal integration — they cause friction, not failure:

- **Mock React contexts in `lib/`** for cart, auth, orders, theme state, etc. — typically named `*-context.tsx`. The agent either (a) keeps the provider component shells and rewires them to call server actions / server-side data, or (b) discards them and uses Server Components with direct Prisma queries. Either is fine.
- **Inlined sample data arrays** at `lib/data.ts`, `lib/fixtures.ts`, or as exported constants inside page TSX. The agent replaces the array reads with data-layer queries. Field shapes from the design serve as a *visual* contract; the spec's domain model is the *implementation* contract (where they differ, see the spec's "Design ↔ Spec Alignment" table).
- **`useState` / `useEffect` simulating async loading** — common in v0 outputs where a `setTimeout` mocks a fetch. The agent replaces with a real `await` in a Server Component, or `<Suspense>` with a fetch.
- **Hardcoded "current user" objects** — fine. The agent wires a real session.
- **`console.log` in submit handlers** — fine, the agent replaces with a server action call.

State your **canonical contract in the spec** (domain model, error codes, route shapes) and let the agent reconcile the differences. Do not contort the design to look like the implementation — that defeats the design contract.

When in doubt, refer to the spec's "Design ↔ Spec Alignment Notes" section, which lists known divergences and their resolution rule (typically "spec wins for implementation, design wins for layout"). See §7 for the GAP analysis discipline that produces this table.

#### Why this stack and not another

This stack matches what `set-project init --project-type web --template nextjs` deploys to the agent's worktree. The agent literally copies your TSX files into its project — if your TSX imports `@mui/material/Button`, the agent's project doesn't have that dependency and the build breaks. If your CSS uses Tailwind v3 syntax, the agent's Tailwind v4 build fails. The single-stack rule is what makes "agent mounts your component" work as a contract, instead of "agent re-implements your component in the project's stack" (which is HTML-mockup territory).

If you have a stack constraint that genuinely requires deviating (e.g., the project must use a specific component library), raise it before authoring the design repo — SET's web profile may need to be configured first.

### 6.2 Why HTML mockups failed

HTML mockups force every agent to **reconstruct** the design in React from a description. Three agents will produce three different DOM structures, three different Tailwind class lists, three different colour values drifting from your tokens by the second iteration. Token usage explodes because the agent re-derives the same layout decisions per page, and the design-fidelity screenshot diff fails because the underlying component tree is not the same shape as the reference.

The fix: ship the agent **the actual rendered TSX components** in the stack above. The agent's job is then *integration* (wire data, server actions, validation) rather than *re-creation* (deciding markup, classes, tokens). This is the single largest token-economy win in the system.

### 6.3 The pipeline

```
You (external system)                  SET                            Agent
─────────────────────                  ───                            ─────
(1) Author or generate
    a Next.js / shadcn /
    Tailwind TSX repository
    (the "design repo")
(2) Push it to git
    (your own host)
(3) Reference it in
    scaffold.yaml as
    design_source.repo
                                       (4) set-design-import
                                           clones the design repo to
                                           <project>/v0-export/
                                           runs validator (tsc, build,
                                           shadcn consistency, dead-link,
                                           naming consistency)
                                           writes docs/v0-import-report.md
                                           generates design-manifest.yaml
                                       (5) Per change: dispatcher binds
                                           routes from manifest, lists
                                           the relevant TSX files in
                                           openspec/changes/<c>/design.md
                                                                       (6) Reads design.md.
                                                                           Copies / mounts the
                                                                           TSX from v0-export/.
                                                                           Wires data layer
                                                                           (Prisma, server
                                                                           actions, i18n).
                                                                           Adds tests.
                                       (7) design-fidelity gate:
                                           screenshot-diffs the agent
                                           build vs the reference build
                                           at 3 viewports.
```

The directory name `v0-export/` is **a constant in the importer**, not a reference to v0.app. Your design repo's *source* directory layout, however, IS the contract — see §6.5.

### 6.4 What you produce: the design repository

A self-contained Next.js project. Minimum viable structure:

```
<your-design-repo>/
├── package.json                  # MANDATORY (see §6.6 for deps)
├── tsconfig.json                 # MANDATORY (paths: { "@/*": ["./*"] })
├── tailwind.config.ts            # OPTIONAL on Tailwind v4 + @tailwindcss/postcss (config-less JIT works)
├── postcss.config.mjs            # MANDATORY
├── next.config.mjs               # MANDATORY (or .ts / .js — Next.js's choice)
├── components.json               # MANDATORY (shadcn config — see §6.7)
├── README.md                     # OPTIONAL but recommended
│
├── app/                          # MANDATORY — Next.js App Router
│   ├── layout.tsx                # root layout (mounts ThemeProvider, fonts, etc.)
│   ├── globals.css               # MANDATORY — theme tokens as CSS custom props
│   ├── page.tsx                  # homepage at /
│   ├── error.tsx                 # error boundary
│   ├── not-found.tsx             # 404 page
│   ├── <route-1>/page.tsx        # one page.tsx per route
│   ├── <route-2>/page.tsx
│   ├── <segment>/<route>/page.tsx
│   └── ...
│
├── components/                   # MANDATORY
│   ├── ui/                       # MANDATORY — shadcn primitives
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   └── ... (every shadcn primitive used anywhere)
│   ├── theme-provider.tsx        # next-themes wrapper
│   ├── site-header.tsx           # site chrome (header + footer recognised by importer)
│   ├── site-footer.tsx
│   └── <feature-component>.tsx   # feature-specific components
│
├── lib/
│   └── utils.ts                  # MANDATORY — exports `cn()` helper (see §6.7)
│
├── hooks/                        # OPTIONAL — custom hooks
├── public/                       # static assets (logos, seed images, fonts)
└── styles/                       # OPTIONAL — extra CSS modules
```

#### Hard rules

1. **One `page.tsx` per route.** Do NOT combine multiple routes into one file with conditional rendering. The importer maps `app/**/page.tsx` → routes via path inference.
2. **Every interactive element imports from `components/ui/`** — never raw `<button>`, never raw `<input>`. The validator flags inconsistent shadcn usage as a quality warning (and as BLOCKING under `--strict-quality`).
3. **All `Link` `href` and `router.push()` targets must point to existing routes** in `app/`. The validator's navigation check fails on broken links.
4. **No top-level type errors.** `tsc --noEmit` must pass. Under `--strict`, any TS error is BLOCKING; otherwise warnings.
5. **`pnpm build` must succeed.** The importer runs a build smoke test. A reference design that doesn't build cannot be the basis for a fidelity diff.

### 6.5 The directory contract enforced by the importer

`set-design-import` reads the cloned repo and infers the manifest from the file tree. Specifically:

- `app/**/page.tsx` → one route per file. Path is the file's directory relative to `app/`. Example: `app/admin/orders/page.tsx` → route `/admin/orders`.
- `components/ui/**` → always classified as **shared** (every change references them).
- `components/site-header.tsx`, `components/site-footer.tsx`, `components/header.tsx`, `components/footer.tsx`, `app/layout.tsx`, `app/globals.css` → also classified as **shared**.
- All other `components/*.tsx` files → classified as **per-route component dependencies** based on import-graph traversal (the importer follows imports from each `page.tsx`).

This means your **route URLs are determined by your file layout**. If your spec says a page is at `/dashboard`, you must put it at `app/dashboard/page.tsx`. If your spec says a detail page is at `/admin/records/[id]`, you must put it at `app/admin/records/[id]/page.tsx`. Localised slugs (e.g. `/penztar` instead of `/checkout`) work the same way — whatever the directory is, that's the route.

This is also how the design-route binding contract (§6.14) works: every route the importer discovers must be assigned to exactly one change. Routes you generate that the spec doesn't mention will trigger a `design_gap` warning.

### 6.6 `package.json` — required dependencies

The importer runs `pnpm install` and `pnpm build`. Use Next.js 15 or 16 (the agent's project will be on the same major) and react 19. A working dependency set:

```json
{
  "name": "<your-design-repo-name>",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint ."
  },
  "dependencies": {
    "next": "^16.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@radix-ui/react-accordion": "^1.2.0",
    "@radix-ui/react-alert-dialog": "^1.1.0",
    "@radix-ui/react-avatar": "^1.1.0",
    "@radix-ui/react-checkbox": "^1.3.0",
    "@radix-ui/react-collapsible": "^1.1.0",
    "@radix-ui/react-dialog": "^1.1.0",
    "@radix-ui/react-dropdown-menu": "^2.1.0",
    "@radix-ui/react-label": "^2.1.0",
    "@radix-ui/react-popover": "^1.1.0",
    "@radix-ui/react-radio-group": "^1.3.0",
    "@radix-ui/react-scroll-area": "^1.2.0",
    "@radix-ui/react-select": "^2.2.0",
    "@radix-ui/react-separator": "^1.1.0",
    "@radix-ui/react-slot": "^1.2.0",
    "@radix-ui/react-switch": "^1.2.0",
    "@radix-ui/react-tabs": "^1.1.0",
    "@radix-ui/react-toast": "^1.2.0",
    "@radix-ui/react-tooltip": "^1.2.0",
    "@hookform/resolvers": "^3.9.0",
    "react-hook-form": "^7.54.0",
    "zod": "^3.24.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^3.0.0",
    "lucide-react": "^0.500.0",
    "next-themes": "^0.4.0",
    "sonner": "^1.7.0",
    "framer-motion": "^12.0.0",
    "date-fns": "^4.0.0",
    "react-day-picker": "^9.0.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4.0.0",
    "tailwindcss": "^4.0.0",
    "tw-animate-css": "^1.0.0",
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "postcss": "^8.5.0",
    "typescript": "^5.7.0"
  }
}
```

Add other Radix packages if you use the corresponding shadcn primitives (slider, toggle, hover-card, menubar, navigation-menu, progress, context-menu, aspect-ratio, breadcrumb, etc.). Drop unused ones. The agent will add data-layer dependencies (`prisma`, `next-auth`, `next-intl`, etc.) on its side — do NOT include them in the design repo.

### 6.7 The shadcn baseline files

Three files are non-negotiable because every shadcn primitive depends on them:

**`components.json`** — shadcn config. Tells the agent's `npx shadcn add` calls where to drop new primitives:

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "app/globals.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "iconLibrary": "lucide"
}
```

**`lib/utils.ts`** — the `cn()` helper that every shadcn primitive imports:

```ts
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

**`tsconfig.json`** — must include the `@/*` path alias:

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "target": "ES6",
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

### 6.8 Theme tokens — `app/globals.css`

This is the **single source of design tokens**. The agent will read CSS custom properties from this file and use them via Tailwind's theme integration. Hex is acceptable; OKLCH (the v0.app default) is preferred because it preserves perceptual lightness.

Structure:

```css
@import 'tailwindcss';
@import 'tw-animate-css';

@custom-variant dark (&:is(.dark *));

/* <Project> Theme — <one-line brand description> */
:root {
  /* Core palette */
  --background: oklch(0.988 0.015 85);   /* Warm cream  #FFFBEB */
  --foreground: oklch(0.147 0.004 49);   /* Stone 900   #1C1917 */

  /* Surface / Cards */
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.147 0.004 49);
  --popover: oklch(1 0 0);
  --popover-foreground: oklch(0.147 0.004 49);

  /* Primary brand colour */
  --primary: oklch(0.407 0.108 54);      /* #78350F */
  --primary-foreground: oklch(1 0 0);

  /* Secondary / accent */
  --secondary: oklch(0.666 0.179 55);    /* #D97706 */
  --secondary-foreground: oklch(1 0 0);

  /* Muted / subdued */
  --muted: oklch(0.95 0.006 85);
  --muted-foreground: oklch(0.444 0.011 73);

  /* Accent (often same family as secondary, lighter) */
  --accent: oklch(0.95 0.03 85);
  --accent-foreground: oklch(0.407 0.108 54);

  /* Destructive */
  --destructive: oklch(0.577 0.245 27);
  --destructive-foreground: oklch(1 0 0);

  /* Borders & focus ring */
  --border: oklch(0.923 0.003 73);
  --input: oklch(0.923 0.003 73);
  --ring: oklch(0.666 0.179 55);

  /* Status */
  --success: oklch(0.627 0.194 142);     /* #16A34A */
  --warning: oklch(0.666 0.179 55);      /* #D97706 */
  --error:   oklch(0.577 0.245 27);      /* #DC2626 */

  /* Charts */
  --chart-1: oklch(0.407 0.108 54);
  --chart-2: oklch(0.666 0.179 55);
  --chart-3: oklch(0.627 0.194 142);
  --chart-4: oklch(0.75 0.12 85);
  --chart-5: oklch(0.55 0.08 55);

  --radius: 0.5rem;

  /* Sidebar variant (admin layouts) */
  --sidebar: oklch(0.988 0.015 85);
  --sidebar-foreground: oklch(0.147 0.004 49);
  --sidebar-primary: oklch(0.407 0.108 54);
  --sidebar-primary-foreground: oklch(1 0 0);
  --sidebar-accent: oklch(0.95 0.03 85);
  --sidebar-accent-foreground: oklch(0.407 0.108 54);
  --sidebar-border: oklch(0.923 0.003 73);
  --sidebar-ring: oklch(0.666 0.179 55);
}

.dark {
  /* Dark-mode overrides for the same tokens */
  --background: oklch(0.147 0.004 49);
  --foreground: oklch(0.988 0.015 85);
  /* ... mirror every :root token ... */
}
```

#### Token rules

1. **Every token defined in `:root` must also be defined in `.dark`** (even if dark mode is not in v1 — the agent will assume the system supports it, and missing tokens cause Tailwind class errors).
2. **Use the exact token names listed above.** shadcn's primitive components hard-code these names (`bg-primary`, `text-muted-foreground`, etc.). Renaming breaks every primitive.
3. **Every brand colour that the spec references in business conventions must have a corresponding token.** "Status badges use --success/--warning/--error" only works if those tokens exist.
4. **Add `--chart-1` through `--chart-5`** even if v1 has no charts — the shadcn `chart` primitive will reference them when the agent adds dashboards later.

### 6.9 Per-page generation guidance

The TSX you produce per route is consumed *as authoritative layout*. Write the components with the same care a human designer would put into a Figma file. Below is the discipline that produces fidelity-passing output.

#### (a) Tag every page by intent

Adopt internal tags that drive how prescriptive your generation is:

- **`[EDITORIAL]`** — landing pages, story pages, marketing sections. Strong opinion on layout, asymmetric grids, full-bleed hero imagery, generous whitespace. Vary composition between routes.
- **`[FUNCTIONAL]`** — admin tables, dashboards, multi-step wizards, settings forms. Match conventional UX patterns (DataTable with sticky header, sortable columns, pagination footer; sidebar layout with collapsible groups).
- **`[HYBRID]`** — checkout flow, account dashboard. Functional structure with editorial accents.
- **`[STATIC]`** — legal pages, terms, privacy, cookie policy. Single column, restrained typography, no decoration.

These tags do not appear in the TSX itself but should appear in `docs/design-direction.md` (see §6.11) so the design can be regenerated consistently.

#### (b) Render every state, not just default

For every interactive component, the TSX must render — or be capable of rendering via a state prop / variant — every relevant state:

- **Buttons:** default, hover, focus-visible, active, disabled, loading
- **Form fields:** default, focused, filled, error (with inline error message), disabled
- **Lists / tables:** populated, empty (with empty state), loading (with skeleton), error (with retry)
- **Cards (with data):** full, partial, missing-image fallback
- **Auth-gated UI:** anonymous variant, signed-in variant
- **Counts / badges:** zero (often hidden), 1, 99+

You can either (i) render state variants side-by-side on the page (useful for admin component-library pages), or (ii) make the component accept a state prop and let the agent invoke it appropriately. Either is acceptable; just make sure no state is *missing* from the TSX.

#### (c) Always render the mobile breakpoint

A page that only looks right at 1440px is half a deliverable. Write responsive Tailwind classes (`sm:`, `md:`, `lg:`, `xl:` prefixes) such that the page renders correctly at:

- **375×667** (mobile)
- **768×1024** (tablet)
- **1440×900** (desktop)

These are the three viewports the design-fidelity gate screenshots at. If your design only works at desktop, the gate will fail mobile and tablet diffs.

#### (d) shadcn primitive selection

Use shadcn primitives for every interactive element. Common mapping:

| UI need | shadcn primitive |
|---|---|
| Action button | `Button` (with `variant`: default / destructive / outline / secondary / ghost / link) |
| Text input | `Input` + `Label` |
| Long text | `Textarea` |
| Select dropdown | `Select` |
| Yes/no toggle | `Switch` (preferred) or `Checkbox` |
| Mutually exclusive options | `RadioGroup` |
| Modal | `Dialog` |
| Confirm prompt | `AlertDialog` |
| Drawer (mobile) | `Sheet` |
| Tabs | `Tabs` |
| Collapsible section | `Accordion` or `Collapsible` |
| Tooltip | `Tooltip` |
| Toast notification | `Toaster` (sonner) |
| User avatar | `Avatar` |
| User menu | `DropdownMenu` |
| Status / category tag | `Badge` |
| Page navigation | `Breadcrumb` + `NavigationMenu` |
| Date picker | `Calendar` + `Popover` |
| Loading placeholder | `Skeleton` |
| Image carousel | `Carousel` |
| Tabular data | shadcn DataTable pattern (TanStack Table + Table primitive) |
| Multi-select toggle | `ToggleGroup` |
| Image with aspect ratio | `AspectRatio` |
| Sidebar | `Sidebar` (shadcn's sidebar pattern) |
| Search palette | `Command` (cmdk-based) |

When you need something the shadcn library does not provide as a primitive (e.g., a custom kanban board), build it from primitives (Card + DropdownMenu) rather than ad-hoc markup.

#### (e) Do not wire data

The TSX you ship must render with **fixture data inlined into the component**, not fetched from an API. For example:

```tsx
// app/admin/orders/page.tsx — design repo version
const SAMPLE_ORDERS = [
  { id: '1', orderNumber: '#1042', status: 'NEW', total: 9980, placedAt: '2026-04-01' },
  { id: '2', orderNumber: '#1043', status: 'PROCESSING', total: 14990, placedAt: '2026-04-02' },
  // ... a representative set ...
]

export default function AdminOrdersPage() {
  return <OrdersTable orders={SAMPLE_ORDERS} />
}
```

The agent will replace `SAMPLE_ORDERS` with a real database query (Prisma) and pass the result through the same component. **Do not** call `fetch()`, **do not** import a Prisma client, **do not** use `next-auth` — none of those packages are installed in the design repo. Fixture data is the contract: keep it inlined or in `lib/fixtures/`.

If you want the design source to share data with the design-fidelity gate's reference render, also publish the fixture data in `<scaffold>/docs/content-fixtures.yaml` — see §6.12.

### 6.10 What the importer validates

`set-design-import` runs these checks against your repo. The output goes to `docs/v0-import-report.md`:

| Check | Severity | What it does |
|---|---|---|
| **TypeScript type-check** (`tsc --noEmit`) | WARNING (default) / BLOCKING (`--strict`) | Catches type errors, missing imports, malformed JSX |
| **Build smoke test** (`pnpm build`) | BLOCKING | Catches runtime errors at build time |
| **Component naming consistency** | WARNING | Flags inconsistent casing / pluralisation across components |
| **Navigation integrity** | BLOCKING (default) / WARNING (`--ignore-navigation`) | Every `Link href` and `router.push()` target must point to an existing route |
| **shadcn primitive consistency** | WARNING (default) / BLOCKING (`--strict-quality`) | Flags raw `<button>` / `<input>` when the corresponding shadcn primitive is used elsewhere |
| **Variant coverage** | WARNING | Flags components where some pages use a `variant` prop and others don't |

Pass all of these and your design will import cleanly. Failing BLOCKING checks aborts the import (the orchestrator cannot start).

### 6.11 `docs/design-direction.md` — the brand-vibe document

A markdown file at `<scaffold>/docs/design-direction.md` that documents the brand vibe and per-page direction. This file does NOT control SET behaviour — it is the human/LLM-readable narrative that drove the design source's contents. Its purpose:

1. **Reproducibility:** when scope grows and new pages are needed, you can re-read this doc and produce additions consistent with the original intent.
2. **Spec ↔ design coherence:** the planner reads it to understand the rationale behind your route choices; reviewers read it during quality audits.

Recommended structure:

```markdown
# Design Direction — <Project>

## Brand voice

(2-3 paragraphs: who is the customer, what feeling should the site evoke,
what kind of brands does this take inspiration from, what does it
deliberately AVOID looking like. Be specific. "Premium specialty coffee,
editorial like Apartamento magazine, NOT a generic Shopify template.")

## Theme tokens (mirror of app/globals.css)

| Token | Value | Usage |
|---|---|---|
| `--primary` | #78350F (coffee brown) | Primary CTAs, hero accents |
| `--secondary` | #D97706 (amber) | Secondary CTAs, hover states |
| `--background` | #FFFBEB (warm cream) | Page background |
| ... | ... | ... |

## Typography

- Headings: <font> (serif/sans), bold display sizes for hero
- Body: <font>
- Mono: <font> (codes, order numbers)

## Layout principles

- Generous whitespace
- Asymmetric editorial composition
- Hierarchy through scale, not borders
- Mobile-first (designed for thumb, not just shrunk desktop)

## Per-page direction

### 1. Header + Footer  [EDITORIAL]

PURPOSE: Premium magazine masthead.
CONTENT: <list>
FUNCTIONAL: <scroll behaviour, search, language toggle, etc>
STATES: anonymous, signed-in, mobile (Sheet / hamburger)
shadcn USED: Avatar, Badge, Button, Command, DropdownMenu, NavigationMenu, Sheet, Separator

### 2. Homepage (`/`)  [EDITORIAL]

PURPOSE: Editorial landing — story-led, not catalogue-led.
HERO: Full-bleed image, bold serif headline, single CTA.
SECTIONS: About / Featured products / Editorial story / Newsletter
shadcn USED: Button, Card, Carousel, Separator

### 3. Product list (`/kavek`)  [HYBRID]

PURPOSE: Browse with editorial accents.
LAYOUT: Filter sidebar (collapsible groups) + 3-column product grid.
PRODUCT CARD: Aspect-ratio image, name, origin, price.
EMPTY STATE: When filters yield no results.
shadcn USED: Card, Sheet (mobile filters), Select, ToggleGroup, Skeleton

### 4. Admin orders (`/admin/rendelesek`)  [FUNCTIONAL]

PURPOSE: Operational table — staff productivity.
LAYOUT: Sidebar (admin nav) + DataTable.
TABLE: Sortable, filterable, pagination, row actions.
STATES: Loading skeleton, empty, error retry.
shadcn USED: Sidebar, Table, Badge, Button, DropdownMenu, Pagination

(... etc, one section per page ...)

## Page generation order

1. Header + Footer (chrome that every other page reuses)
2. Homepage (sets the editorial tone)
3. Product list / detail (the customer-facing core)
4. Auth pages (login / register / password reset)
5. Cart + checkout flow
6. Account dashboard + order history
7. Admin pages (sidebar, dashboard, orders, products, users, settings)
8. Static pages (terms, privacy, cookie, FAQ)
```

#### Direction-writing rules

1. **Open every page section with PURPOSE.** "Magazine masthead, not generic shop nav" anchors every other decision.
2. **Separate CONTENT, FUNCTIONAL, STATES.** Mixing them produces a page that handles only one state.
3. **Be specific about what to AVOID.** "Symmetric 3/4-column card grids as default" prevents template look.
4. **Trust composition for [EDITORIAL] pages.** Constraining layout exhaustively defeats the point. Give vibe + content + functionality, then let the generation compose freely.
5. **Constrain layout for [FUNCTIONAL] pages.** Admin tables and wizards have strong UX expectations — be specific about structure (DataTable / sidebar / stepper).
6. **List every state explicitly.** "Default, hover, focus, selected, disabled, loading, error" so the generation renders all variants.
7. **Always specify mobile.** Every page section must mention mobile behaviour.
8. **Reuse via reference.** "Reuse the previously generated header and footer." Prevents regenerating chrome per page.

### 6.12 `docs/content-fixtures.yaml` — design-fidelity reference data

YAML file at `<scaffold>/docs/content-fixtures.yaml` that the design-fidelity gate uses to render both your design source and the agent's build with **identical data**, so the screenshot diff measures design (not data churn).

```yaml
# content-fixtures.yaml — used by design-fidelity gate
products:
  - id: 1
    slug: etiop-yirgacheffe
    name_hu: Etióp Yirgacheffe
    name_en: Ethiopian Yirgacheffe
    base_price: 4990
    image_url: /images/seed/etiop.jpg
  - id: 2
    slug: kolumbiai-huila
    name_hu: Kolumbiai Huila
    name_en: Colombian Huila
    base_price: 5290
    image_url: /images/seed/kolumbiai.jpg
  # ... 6 more

users:
  - email: customer1@example.com
    name: "Test Vásárló"
    role: CUSTOMER
  - email: admin@example.com
    name: "Admin User"
    role: ADMIN

orders:
  - order_number: "#1042"
    status: NEW
    grand_total: 9980
    placed_at: "2026-04-01T14:23:00Z"

# ... one entry per persisted entity needed for the reference render ...
```

Field names must match the Domain Models table in your master spec exactly. This file is **separate from `catalog/*.md`**: catalog is human-readable seed-data spec; content-fixtures is the machine-readable subset used by the gate.

If your design repo uses inlined sample arrays (per §6.9e), publish the same shape here so the agent's render matches.

### 6.13 The design-fidelity gate

After every change merges, the gate:

1. **Skeleton check.** Verifies the agent's worktree has the same routes and shared component files as the design repo.
2. **Reference build.** Builds the design repo with `content-fixtures.yaml` substituted as data.
3. **Agent build.** Builds the agent's worktree.
4. **Pixel diff.** Playwright screenshots at 1440×900, 768×1024, 375×667. Pixelmatch diff vs threshold (default 1.5% of pixels with a 200-pixel floor).

Failures are **blocking** by default. The agent then iterates to bring the worktree closer to the reference. With:

```yaml
# set/orchestration/config.yaml
gates:
  design-fidelity:
    warn_only: true
```

…failures become warnings instead. Use this only if the design is intentionally aspirational rather than authoritative.

### 6.14 Design-route binding contract

Once `design-manifest.yaml` exists, the planner binds **every route discovered in the design repo** to **exactly one change** OR to `deferred_design_routes` with a reason.

Implications:

- Every UI route mentioned in your spec MUST exist as `app/<route>/page.tsx` in the design repo (and therefore in the manifest).
- If your spec mentions a UI page but the design repo doesn't include it, the planner emits a `design_gap`. Resolution: (a) regenerate the missing page, (b) remove the spec mention, (c) accept the gate skip for that page.
- Routes the design repo includes that the spec doesn't reference are flagged as orphan routes — either add a spec entry or remove from the design.

Practical advice: **finalise the design repo and the spec in lockstep.** Treat them as a coherent pair under shared version control. A spec that mentions 3 admin pages the design repo doesn't cover will block decomposition until resolved.

### 6.15 Design-source authentication

If your design repo is private:

```bash
# SSH key (recommended)
ssh-add ~/.ssh/id_ed25519
ssh-add -l
```
```yaml
design_source:
  type: v0-git
  repo: git@github.com:your-org/your-design-repo.git
```

```bash
# OR GitHub PAT
export GITHUB_TOKEN=ghp_...
```
```yaml
design_source:
  type: v0-git
  repo: https://github.com/your-org/your-design-repo.git
```

Deploy keys also work — see [docs/design-pipeline.md](../design-pipeline.md) for the full auth matrix.

### 6.16 Lessons from real v0 outputs

Patterns we have seen consistently in v0.app-generated TSX repositories (and how to think about them):

**1. Route groups are normal.** Projects with distinct chrome variants (e.g. `(auth)/`, `(storefront)/`, `admin/`) commonly use Next.js route groups with one `layout.tsx` per group. The SET importer handles route groups correctly — the `(name)` segments are stripped during route inference. Do not flatten routes into a single layout if the chrome legitimately differs.

**2. Mock contexts are the v0 default.** v0 outputs typically include `lib/auth-context.tsx`, `lib/cart-context.tsx`, `lib/orders-context.tsx` etc. — React Context providers wrapping `useState` to make the preview clickable. These are tolerated (§6.1 above); the agent rewires them. Do not strip them from the design just to satisfy a stale "no data layer" rule.

**3. Header naming is flexible.** The importer's hardcoded `SHARED_GLOBS` baseline expects `site-header.tsx` / `site-footer.tsx`, but a Tier A auto-detect classifies every `components/*.tsx` (top-level, non-`ui/`) as shared anyway. So `storefront-header.tsx` works fine. Use semantically meaningful names if your project has multiple chrome variants (e.g. `storefront-header.tsx` + `admin-sidebar.tsx`).

**4. Toaster + ThemeProvider mounts are easy to forget.** v0 frequently puts `sonner` / `next-themes` in `package.json` but does not mount `<Toaster />` and `<ThemeProvider>` in `app/layout.tsx`. Verify both are mounted — without them, `toast()` calls render nothing and `useTheme()` returns undefined. The agent will not notice this if their feature path doesn't exercise it.

**5. Footer often missing.** v0 outputs typically render headers but skip footers unless you prompt for one. Add a `components/site-footer.tsx` and mount it in the relevant layout(s).

**6. Duplicate `globals.css` (`app/globals.css` AND `styles/globals.css`) is normal.** Both are present in most v0 outputs. The importer reads `app/globals.css` (matching `components.json`'s `tailwind.css` field). The duplicate is harmless dead weight; you can leave it.

**7. `app/page.tsx` may just be a redirect.** Small projects often have `export default function HomePage() { redirect("/products") }` as the homepage. This is a valid design choice — do not mistake it for a missing page.

**8. ID and price types differ from the spec.** v0 typically generates `string` IDs ("1", "1-black") and `number` prices (89.99). The implementation contract (Prisma schema) usually uses `Int` IDs and integer cents. Resolve in the spec's "Design ↔ Spec Alignment Notes" — the agent reconciles when wiring the data layer.

**9. Status enum casing diverges.** Design source tends to use lowercase ("pending", "completed") while spec convention is UPPER_SNAKE_CASE ("PENDING", "COMPLETED"). Spec wins for the implementation; the agent maps for display when needed.

**10. Variants typically lack SKU/label.** v0's variant shape is `{ id, attributes, price, stock }`; production schemas usually need `sku` (unique) and human-readable `label`. Add them in the spec's Domain Models table; the agent adds them to the Prisma schema.

These are not problems — they're the *normal contour* of v0 output. The job of the spec author is to declare the implementation contract clearly enough that the agent can resolve every divergence deterministically.

### 6.17 ZIP fallback if you cannot host the design repo

If git hosting is impractical, hand-deliver a zipped tarball:

```yaml
design_source:
  type: v0-zip
  path: ./designs/v1-design.zip
```

The importer extracts the ZIP to `v0-export/` (after stripping the wrapping top-level directory if present) and runs the same validators. ZIP mode loses the ref-pinning advantage of git but is otherwise equivalent.

---

## 7. Spec ↔ design alignment & GAP analysis

Spec and design are not two parallel deliverables — they are **two halves of the same contract**. The spec describes behaviour; the design describes appearance and interaction. The agent reads both together and assumes they agree. When they disagree, one of three failures happens:

1. **Decomposition blocks.** The planner finds spec routes that have no matching design page (or vice versa) and emits `design_gap` ambiguities the planner cannot silently resolve.
2. **Agent invents the missing half.** If the spec says "subscription pause flow" and the design has no pause UI, the agent invents one — usually badly, always inconsistently with sibling changes.
3. **Tests fail at integration.** The spec's `data-testid` registry references selectors that the design TSX does not contain; E2E tests fail in the gate; the agent retries; tokens burn.

The fix is **iterative co-development with a GAP analysis pass before handover**. This section describes the practice.

### 7.1 Develop spec and design in lockstep, not sequentially

Writing the entire spec, then generating the entire design, then handing both to SET produces the largest GAP gap. Better:

```
1. Draft master spec (domain models, error catalog, conventions, list of feature areas)
2. Draft design-direction.md (brand vibe, list of pages with intent tag)
3. Generate design v0 (header, footer, homepage, ~3 representative pages)
4. RECONCILE — does the design imply data the spec didn't mention? Does the spec
   reference UI the design doesn't show? Update both sides.
5. Write per-feature spec files for ~3 features
6. Generate design pages for those features
7. RECONCILE again
8. Continue until full coverage
9. Pre-handover GAP analysis (§7.4)
```

Steps 4 and 7 are where most of the work happens — and where most of the value comes from. A page that the designer adds (e.g. a saved-cards screen) should provoke a spec entry; a feature the spec describes (e.g. a CSV bulk import) should provoke a design page. When neither side knows about something, neither side will produce it, and the agent will silently leave it out.

### 7.2 What "properly elaborated" means

For every feature, the spec and design together must answer all of the following questions. If either side is silent on a question, the answer is implicitly "the agent decides" — which means the answer is non-deterministic and non-reviewed.

| Question | Spec must answer | Design must answer |
|---|---|---|
| **What entities does it read/write?** | Yes — list in feature's Data section | Implicitly via fixture data shape |
| **What fields does the form / page expose?** | Yes — list in acceptance criteria | Yes — render the fields visually |
| **Which validation errors are possible?** | Yes — reference error codes from catalog | Yes — render error UI for each (banner / inline / toast) |
| **What states can the UI be in?** | Yes — empty / loading / partial / full / error / unauthenticated | Yes — render each state explicitly |
| **What actions does the page expose?** | Yes — primary CTA, secondary actions, destructive actions | Yes — buttons / links / menus visible |
| **Where does each action navigate?** | Yes — list destinations | Yes — `Link href` / `router.push` to actual routes |
| **Who can access it?** | Yes — role gate, ownership rules | Yes — anonymous variant + signed-in variant + admin variant when relevant |
| **What does the mobile view look like?** | Often silent — design owns | Yes — render at 375×667 viewport |
| **What confirmations / dialogs are required?** | Yes — destructive operations require AlertDialog | Yes — render the dialog |
| **What audit / notification side-effects fire?** | Yes — list in feature's Edge Cases | N/A — design has no side-effect surface |
| **What happens after success?** | Yes — toast text, redirect target | Yes — show the toast; after-state of the page |

Use this table as a worksheet per feature. Both spec author and design author tick the columns they own. Empty cells are gaps.

### 7.3 The six GAP axes

A spec/design package is consistent when it has zero gaps on all six axes below. A gap on any axis is a place where the agent will guess or stall.

**Axis 1 — Routes.** Every route the design exposes (`app/<route>/page.tsx`) must be referenced by a spec feature, AND every spec feature that mentions UI must have a corresponding design route.

```
SPEC says page X exists  ⊆  DESIGN has app/X/page.tsx
DESIGN has app/Y/page.tsx ⊆  SPEC mentions Y in some feature
```

If `SPEC ⊄ DESIGN`: design must add the page, OR spec defers it (`[Phase 2]`).
If `DESIGN ⊄ SPEC`: spec must add a feature entry, OR design removes the page.

**Axis 2 — Components.** Every per-route component dependency (in `components/*.tsx`) should make sense for the spec feature it supports. A `<SubscriptionPauseDialog>` in the design implies the spec has a Subscription pause requirement; a Subscription pause requirement in the spec implies the design has the dialog component.

**Axis 3 — Data shape.** Every prop the design TSX expects must be derivable from the spec's domain models. If the design's `<OrderRow>` accepts `{id, orderNumber, status, total, customerName}` but the spec's `Order` entity has no `customerName` field (it has `user_id`, which links to `User.name`), the agent has to write a join. State that explicitly in the spec or change the prop shape.

**Axis 4 — States.** Every state the spec describes (loading / empty / partial / error / unauthenticated) must be renderable by the design. If the spec says "while subscriptions load, show a skeleton matching the row layout" but the design only ships the populated state, the agent invents a skeleton — and gets it wrong.

**Axis 5 — Errors.** Every error code in the master catalog should have a destination in the design — either an `error-banner` slot on the page that produces it, or an inline field-error slot, or a destructive-modal error. If the catalog has 40 codes and the design renders error UI for only 5, the other 35 will appear as raw JSON in the user's browser when they trigger.

**Axis 6 — Selectors.** Every `data-testid` in the master spec's registry must exist in the design TSX, with the exact same string and on the right kind of element. If the registry says `header-cart-icon` is on the header but the design's site-header.tsx has `data-testid="cart-icon"`, the E2E test breaks.

### 7.4 The pre-handover GAP analysis

Run this checklist as the final step before submitting the package. Treat each failure as blocking — fix before handover, not after the agent reports it.

```
=== ROUTES ===
□ List every app/**/page.tsx in the design repo
□ For each, find the spec sentence that motivates it; note absences
□ List every spec feature mention of a route or page; note design absences
□ Resolve each absence: add to design, add to spec, or defer with reason

=== COMPONENTS ===
□ For each non-shared component in components/*.tsx, identify the spec
  feature it serves
□ For each spec feature with substantial UI (>3 ACs), identify the
  components in the design that implement it
□ Components without a spec feature → orphan, remove or document
□ Spec features without components → missing, regenerate design pages

=== DATA SHAPE ===
□ For each design component that accepts props, list the prop names
□ For each prop, verify it maps cleanly to a field in the spec's
  domain models (direct field, computed value, or relation join)
□ Missing fields → add to domain model OR change prop shape
□ Extra props the spec doesn't justify → remove or document

=== STATES ===
□ For each spec feature that involves async data, verify the design
  renders: loading skeleton, empty state, populated state, error state
□ For each spec feature with auth gating, verify the design renders:
  anonymous variant, signed-in variant, admin variant (where applicable)
□ For each form, verify the design renders: pristine, valid, invalid
  (with inline errors), submitting (disabled + spinner), success after-state

=== ERRORS ===
□ List every error code in the master catalog
□ For each code, identify where it surfaces in the design:
   - error-banner on which page?
   - inline field-error under which field?
   - destructive-action-failure dialog?
   - toast?
□ Codes with no surface → add UI OR remove code from catalog

=== SELECTORS ===
□ List every data-testid in the master registry
□ Grep the design repo for each: must match exactly, must be on the
  semantically-correct element type
□ Mismatches → fix design TSX or update registry

=== TOKENS ===
□ List every CSS custom property in app/globals.css
□ Cross-check against design-direction.md theme tokens — must agree
□ Cross-check brand colours referenced in design-direction.md prose
  ("--primary is coffee brown #78350F") against the actual oklch/hex
  value in globals.css — must match
□ Mismatches → update one side to match the other

=== CONVENTIONS ===
□ Spec declares currency format (e.g. "1 234,50 €") — verify design
  examples render numbers in that format
□ Spec declares date format — verify design examples render dates
  correctly
□ Spec declares language strategy — verify design copy is in the
  declared primary language (or uses placeholder keys if i18n is enabled)
□ Spec declares status enum values UPPER_SNAKE_CASE — verify design
  badges render those exact strings (or have data-status attributes
  with those values)

=== SEED ↔ FIXTURE PARITY ===
□ For each entity in catalog/*.md, verify content-fixtures.yaml has
  the same fields and shape (the design-fidelity gate uses fixtures
  to render the reference; if they diverge from seed, the agent's
  build won't match)
□ Catalog field names ↔ domain model field names must match exactly
□ Fixture record IDs must be stable across runs (deterministic)
```

### 7.5 GAP analysis output document

Produce a `docs/gap-analysis.md` and ship it with the spec package. The planner reads it during decomposition and uses it to identify intentionally-deferred items. Format:

```markdown
# GAP Analysis — <Project> v1

Run on: <date>
Spec version: <git-sha-of-spec-repo>
Design version: <git-sha-of-design-repo>

## Status: clean | <N> blocking gaps remaining | <N> deferred items

## Routes coverage

| Spec mention | Design page | Status |
|---|---|---|
| Homepage (REQ-HOME-001) | app/page.tsx | ✅ |
| Catalog list (REQ-CAT-001) | app/catalog/page.tsx | ✅ |
| Subscription pause (REQ-SUB-005) | (none) | ⚠️ DEFERRED to Phase 2 — design generation in next sprint |
| (none) | app/admin/internal-tools/page.tsx | ⚠️ ORPHAN — staff-only debugging page, intentionally undocumented |
| ... | ... | ... |

## Errors coverage

| Error code | UI surface | Status |
|---|---|---|
| `AUTH_INVALID_CREDENTIALS` | error-banner on /login | ✅ |
| `BILLING_PAYMENT_FAILED` | error-banner on /checkout, toast on /account/billing | ✅ |
| `KYC_VERIFICATION_PENDING` | (none in design) | ❌ MISSING — needs banner on /account |
| ... | ... | ... |

## Data shape mismatches

(List any design prop that doesn't map cleanly to a spec domain field,
with the resolution.)

## Selector mismatches

(List any registry entry that doesn't appear in the design, with the
resolution.)

## Deferred items

(Items intentionally left for a later phase, with justification.)
```

This document gives reviewers (and the planner) a single place to see what's intentional vs accidental in the package. **A handover with a "clean" status line is usable; one with unresolved blocking gaps will fail decomposition.**

### 7.6 Working GAP analysis tools

You don't have to run all of §7.4 manually. The SET importer already does part of the work — it produces `docs/v0-import-report.md` (validator findings) and detects manifest coverage during decomposition. But these run *after* you submit. To run a check *before* handover:

1. **Local validator pass.** Run `pnpm install && pnpm build && tsc --noEmit` in your design repo. Failures here will fail the importer too — fix them now.
2. **Selector grep.** Extract the `data-testid` list from your master spec, then grep the design repo for each value. Mismatches surface in seconds.
3. **Route inventory.** `find <design-repo>/app -name 'page.tsx'` lists every route the importer will discover. Diff against your spec's UI mentions.
4. **Prop ↔ field check.** For each design component file, list its prop interface; cross-reference each prop name against your domain model. Mismatches are gaps.
5. **Error coverage check.** For each error code in your master catalog, grep the design repo for the literal code string (`COUPON_EXPIRED`) and for `data-error-code=`. A code with zero matches has no UI surface.

These five checks together catch ~90% of the gaps that would otherwise surface during decomposition.

### 7.7 What to do when alignment is impossible

Sometimes spec and design genuinely cannot align in v1 (e.g. design lacks an admin section because the design generator hasn't been run for it yet). In those cases:

- **Defer explicitly.** Add the unaligned routes to `deferred_design_routes` in `gap-analysis.md` AND add a note in the spec ("Phase 2: admin pages — design pending").
- **Mark UI-bound spec entries non-blocking.** If a spec REQ mentions UI but design hasn't caught up, mark the REQ as `[design-pending]` in its summary. The planner will assign the requirement to a later phase when the design is ready.
- **Never ship blocking gaps unmarked.** A gap the planner can't disambiguate from intent will block the entire decomposition.

The system design assumes deferrals are a routine part of the workflow — handle them transparently in `gap-analysis.md` rather than hoping the planner won't notice.

## 8. Phase splitting

Specs that exceed roughly **6 changes after decomposition** must be split into phases. Symptoms of an unsplit too-large spec: parallel changes step on each other (high merge conflict rate), agents stall in long iteration loops, the design-fidelity gate blocks because too many UI changes land at once.

### How to phase

Insert `## Phase N` headings in the master spec OR in the relevant feature files. The decomposer detects these markers and processes one phase at a time. After Phase 1 merges, set `auto_replan: true` and the orchestrator re-reads the spec, detects Phase 2 as the next incomplete section, and dispatches it.

### Marking completion

The decomposer treats these as "done":

- A list item with `[x]`
- A heading or item with ~~strikethrough~~
- A line containing the words "done", "implemented", or "complete" in context

Use these markers if you re-emit the spec after a partial run.

### Phase ordering recipe

1. **Phase 1 — Data foundation.** Schema, auth, seed, base layout chrome.
2. **Phase 2 — Core read-side features.** List / detail / search / filter pages — anything that displays existing data.
3. **Phase 3 — Core write-side features.** Forms, multi-step flows, mutations — anything the user creates / edits / submits.
4. **Phase 4 — Admin / back-office.** Internal tools for staff or operators.
5. **Phase 5 — Polish.** Email templates, SEO, i18n completion, static content pages.

Each phase should be 4–6 changes. If a phase exceeds 6, split it further (e.g. "Phase 3a — primary-flow, Phase 3b — secondary-flows").

---

## 9. Token economy

Every word the agent reads costs tokens. Every decision the agent makes that the spec didn't make is two costs: tokens for the deliberation, and the risk that the next agent decides differently. Spec quality directly drives token efficiency.

### What burns tokens

| Cause | Why it burns | Fix |
|---|---|---|
| Vague scope ("improve the dashboard") | Agent re-reads the codebase to invent a definition | State the deliverable as a list of acceptance criteria |
| Missing contracts (no error code catalog) | Each agent invents its own; later agents read prior code to harmonize | Catalog them in master spec |
| Missing data-testid registry | Each agent invents IDs; tests written across changes use mismatched IDs | Registry in master spec |
| HTML mockup, no TSX design repo | Agent reconstructs UI per page from description | A complete TSX design repo (§6) is the design contract |
| No catalog/*.md files | Agent invents seed data; tests assert on different data | Author the catalog upfront |
| L-sized changes | Agent's iteration loop balloons (build → fix → build → fix) | Split into S/M changes |
| Spec that contradicts itself | Agent reads both sides and picks one (often badly) | Single source of truth per fact |
| Spec that omits state machines | Agent invents transition logic; later admin agent disagrees | Exhaustive transition table |

### Quantitative impact (observed in practice)

- A spec with explicit error code catalog uses **~30% fewer total tokens** for the same feature set vs. a spec that omits it.
- A spec with a real TSX design repo as the authoritative source uses **~40% fewer tokens for UI changes** vs. an HTML / PNG mockup, AND produces visibly higher design fidelity (the agent mounts components rather than reconstructing them).
- A spec with seed data fully cataloged eliminates ~1 full retry per data-touching change.

### The token economy rule

> **Every fact the spec leaves to the agent's discretion costs you a decision the agent has to make, and that decision is non-deterministic across changes.**

If a fact has more than one reasonable answer (and "more than one reasonable answer" is the common case for: enums, error codes, route slugs, table names, casing, URL segments, currency format, date format, locale handling, default sort orders, pagination size, image sizes, breakpoints), put the answer in the spec.

---

## 10. Anti-patterns

### 9.1 Over-specifying implementation

> ❌ "Create `src/lib/<feature>.ts` with a `<Feature>Service` class that exposes `<verb1>()`, `<verb2>()`, etc."

The agent picks file paths and abstractions based on codebase conventions. Telling it the file path is brittle and overrides healthy patterns the agent would otherwise apply. Specify behavior, not structure.

> ✅ "<Feature> operations: <verb1> (with arguments and validation), <verb2>, <verb3>. All operations are server actions; idempotent under double-submit; emit `<DOMAIN>_NOT_FOUND` when target does not exist."

### 9.2 Repeating the same fact in two places

If a state-machine enum (e.g. `<Entity>.status` values) is listed in master + features/<feature>.md + features/admin.md, you will eventually edit one and forget the others. Decomposer agents notice the contradiction and either pick wrong or stall.

**Rule:** master spec is the single source of truth for shared facts. Feature specs *reference* the master, never re-declare.

### 9.3 Spec items disguised as discussion

> ❌ "We've been thinking about whether to include subscriptions. Pro: recurring revenue. Con: complexity. Currently leaning toward yes for v1, but might defer to v2 if scope is too large."

The decomposer cannot act on equivocation. Either include subscriptions (and write the requirements) or defer (and don't mention them). Hand the discussion log to the human; hand decisions to SET.

### 9.4 UI references without a design backing

> ❌ "Add a kanban-style admin order board where staff can drag orders between columns."

If your design repo doesn't include this kanban board, the agent has to invent the layout, which defeats the TSX-as-authoritative pipeline. Either generate the page into the design repo first, or scope it for a later phase after the design is updated.

### 9.5 Inventing test scenarios per requirement

If every REQ-* has its own ad-hoc test, you end up with 80 micro-tests and no structured E2E coverage. Instead:

- One **functional E2E** per feature happy path (chains the requirements).
- Smoke tests for shallow rendering checks across every route.
- Per-requirement acceptance criteria are *assertions*, not separate test files.

### 9.6 Smoke tests with feature logic

Smoke tests run post-merge on `main`. They must be **shallow**: page renders, no 500, expected critical element visible. If your smoke test logs in, navigates a multi-step flow, mutates data, and asserts on a workflow outcome — that's a functional E2E, not a smoke test. Calling it smoke means it runs in the wrong gate, slows the pipeline, and adds flakiness on `main`.

### 9.7 i18n as an afterthought

If your features assume English copy and you add a second language at the end, agents will retrofit `t('key')` calls everywhere with low confidence. Instead, in §3.4 declare the bilingual (or multilingual) strategy and have every requirement reference i18n keys:

> ✅ "Action buttons use the `<feature>.actions.<verb>` i18n key (e.g. EN: 'Add to cart', DE: 'In den Warenkorb')."

### 9.8 Authentication implied but unspecified

Every project needs authentication. If the spec doesn't say:

- Session cookie vs JWT?
- Email + password vs OAuth?
- Email verification required for signup?
- Password reset flow?
- Session lifetime?
- Multi-tenant isolation?

…then twenty agents will pick differently.

### 9.9 Missing transactional semantics

> ❌ "When the user submits the form, do A, B, C and notify the user."

Implies a transaction, doesn't specify boundaries. Agents will either put external side-effects (payment, third-party API call, email) inside the DB transaction (where rollback can't undo them), or commit destructive cleanup before the primary write (data-loss bug on failure).

> ✅ "<Operation> is transactional. Steps INSIDE the DB transaction: <list of writes>. Steps OUTSIDE: <external API call> (BEFORE the transaction — if it fails, abort), <notification / email> (AFTER commit — if it fails, do not roll back; queue retry). On in-transaction failure, full rollback (DB-driver default). On post-payment in-transaction failure, the system MUST issue a compensating action (refund / void / reverse-call), logged and retried by a background job."

### 9.10 Placeholder names in catalog seed

If your catalog uses "Item 1", "Item 2", "User A", agents stop respecting the catalog (it looks like placeholder data) and invent more interesting names. Use real-feeling names from your project's domain — the actual product names if e-commerce, the actual content titles if a CMS, the actual workspace names if SaaS. The catalog is consumed both as seed and as a reference users will see during testing.

---

## 11. Quality checklist

Before handing the spec to SET, verify:

### Master spec

- [ ] Every entity an agent might create or modify is in the Domain Models table
- [ ] Every state enum has UPPER_SNAKE_CASE values listed inline
- [ ] Error Code Catalog covers every UI-displayed error
- [ ] data-testid registry covers every selector used by E2E tests
- [ ] Selector strategy is stated (role-first, testid-second, never text=)
- [ ] Business Conventions covers currency, language, casing, auth, dates, soft-delete, audit, time zones
- [ ] Project-Wide Directives YAML block has test_command, e2e_command, smoke_command, build_command
- [ ] Verification Checklist is concrete and human-runnable

### Per-feature specs

- [ ] One file per feature domain, named in kebab-case
- [ ] Every file follows the standard structure (Overview, Requirements, Data, API, UI, State Machines, Errors, Edge Cases, Test Coverage)
- [ ] Every requirement has an REQ-DOMAIN-NNN ID
- [ ] Every requirement has numbered acceptance criteria (AC-1, AC-2, …)
- [ ] State machines list every legal transition AND the rule for non-listed transitions
- [ ] Error cases reference codes from the master catalog (no new codes here)
- [ ] UI routes match design-manifest.yaml exactly

### Catalog

- [ ] Every persisted "list of things" the app needs at first launch is cataloged
- [ ] Records use the exact field names from the Domain Models table
- [ ] Adversarial / edge-case fixtures are explicitly labeled as intentional

### Design source (external repo or ZIP)

- [ ] Design repository exists and covers every spec route
- [ ] Design source is referenced in `scaffold.yaml` as `design_source: { type: v0-git, repo, ref }` OR `{ type: v0-zip, path }`
- [ ] `app/<route>/page.tsx` exists for every route the spec mentions
- [ ] `components/ui/` contains every shadcn primitive used in pages (no raw `<button>` / `<input>`)
- [ ] `app/globals.css` defines every required CSS custom property in `:root` AND `.dark`
- [ ] `lib/utils.ts` exports `cn()` exactly as specified
- [ ] `components.json` is present with the standard aliases
- [ ] `package.json` lists Next.js, React 19, Tailwind v4, every Radix primitive used
- [ ] Sample/fixture data is inlined in components — no `fetch`, no Prisma client, no `next-auth`
- [ ] `pnpm install && pnpm build` succeeds in the design repo
- [ ] `tsc --noEmit` passes in the design repo
- [ ] All `Link href` / `router.push` targets resolve to existing routes
- [ ] Pages render correctly at 375×667, 768×1024, 1440×900

### Design direction & fixtures

- [ ] `docs/design-direction.md` documents brand vibe + per-page direction, tagged [EDITORIAL]/[FUNCTIONAL]/etc.
- [ ] `docs/design-direction.md` mirrors the theme tokens with hex values and usage notes
- [ ] `docs/content-fixtures.yaml` exists with representative seed data matching domain field names
- [ ] No legacy `.make` files, no design.html, no PNG-as-design

### Spec ↔ design alignment (§7)

- [ ] `docs/gap-analysis.md` exists and ends with status line `clean | <N> blocking gaps` (no blocking gaps unresolved)
- [ ] Routes axis: every `app/**/page.tsx` traces to a spec mention; every spec UI mention traces to an `app/<route>/page.tsx`
- [ ] Components axis: every non-shared component in `components/*.tsx` serves a documented spec feature (no orphans)
- [ ] Data-shape axis: every prop on every design component maps to a domain-model field (or a documented join)
- [ ] States axis: every async-data spec feature has design renderings for loading / empty / populated / error
- [ ] Errors axis: every error code in the master catalog has a UI surface in the design (banner / inline / dialog / toast)
- [ ] Selectors axis: every `data-testid` in the master registry exists at the right element in the design TSX
- [ ] Tokens axis: theme tokens in `app/globals.css`, `design-direction.md`, and any spec mention all agree
- [ ] Seed ↔ fixture parity: `content-fixtures.yaml` and `catalog/*.md` use identical field names and shapes
- [ ] All deferred items are listed explicitly in `gap-analysis.md` with reasons (not silently absent)

### Phases

- [ ] If decomposed plan would be >6 changes, `## Phase N` markers are inserted
- [ ] Phases are ordered: data foundation → core read → core write → admin → polish
- [ ] No Phase contains >6 changes after decomposition

### General

- [ ] No file path or function name appears in the spec (the agent picks those)
- [ ] No equivocation ("we might / leaning toward / TBD") — every fact is decided
- [ ] No fact appears in two places contradictorily (single source of truth per fact)
- [ ] No reference to a UI page that the design repo doesn't include

---

## 12. Templates

Copy these and fill in.

### 12.1 Master spec template

```markdown
# <Project Name> v1 — <One-line description>

> Business specification — the complete functional and content description of <project>.

## Spec Structure

This spec is modular. The main file (this one) contains the overview,
conventions, and verification checklist. Detailed specs are in subdirectories:

- `features/` — one file per feature domain
- `catalog/` — seed data definitions

## Shared Domain Models (cross-feature index)

These entities are referenced from multiple features. Use these exact entity
names, key fields, and relationships. Field types are illustrative — agents
may add fields, but MUST NOT rename the listed ones.

| Entity | Key fields | Relationships |
|---|---|---|
| `<Entity>` | `id`, `<field>`, ... | hasMany / belongsTo ... |
| ... | ... | ... |

**Rules for changes:**
- A change that introduces a new entity adds it here.
- A change that adds a field to an existing entity does NOT need to update this table.
- NEVER rename an entity or one of its listed key fields without updating this index AND every reference across `features/*.md`.
- State enum values are UPPER_SNAKE_CASE — use these exact strings in code.

## Error Code Catalog

API response shape (4xx/5xx errors):
```json
{
  "error": {
    "code": "<UPPER_SNAKE_CASE>",
    "message": "Human-readable, already localized",
    "field": "optional_field_name"
  }
}
```

### <Domain> validation

| Code | HTTP | i18n key | Condition |
|---|---|---|---|
| `<CODE>` | 4XX | `error.<domain>.<code>` | <when> |
| ... | ... | ... | ... |

(Repeat for every domain.)

**Rules:**
- The `code` is contractual; renaming breaks tests.
- The user-visible message MAY be reworded; the i18n key MUST stay stable.
- For 5xx not in this table, fall back to `code: "INTERNAL_ERROR"` HTTP 500.

## E2E Test Conventions

### Selector strategy
1. `getByRole()` with accessible name (gold standard)
2. `data-testid` for non-semantic elements (kebab-case: `<feature>-<element>[-<modifier>]`)
3. NEVER `text=` for translated UI

### Required `data-testid` registry

| `data-testid` | Component / page | Notes |
|---|---|---|
| `header-cart-icon` | Header | ... |
| ... | ... | ... |

### Test data conventions
- Test users: `customer1@... / customer123`, `admin@... / admin123`
- Adversarial fixtures: see catalog/<domain>.md sections labeled "Adversarial"
- Test isolation: DB reset via `beforeEach`
- Time-sensitive tests: `page.clock.install()`, never real wall clock

## Business Conventions

- **Currency:** <currency>, formatted "<example>"
- **Languages:** primary <lang>, secondary <lang>; URLs do/do-not contain locale segments
- **Database casing:** snake_case columns, camelCase JSON
- **Auth:** <session cookie | JWT>, <30-day | other> expiry
- **Money:** integers in minor units (e.g., cents)
- **Dates:** ISO 8601 in API, localized in UI
- **Soft delete:** `deleted_at` nullable, NEVER hard delete
- **Audit:** every admin mutation writes `AuditLog`
- **Time zones:** UTC server, `<TZ>` UI

## Project-Wide Directives

```yaml
test_command: pnpm test
e2e_command: npx playwright test
smoke_command: pnpm test:smoke
build_command: pnpm build
default_model: opus
max_parallel: 1
auto_replan: true
review_before_merge: true
```

## Verification Checklist

After full orchestration, verify:
- [ ] Migrations apply cleanly from a fresh DB
- [ ] Seed runs without errors and produces the cataloged fixtures
- [ ] All routes from `design-manifest.yaml` are reachable and styled
- [ ] All `data-testid` selectors from the registry exist in the DOM
- [ ] All error codes from the catalog are returned by at least one endpoint
- [ ] Authenticated user completes full happy-path checkout
- [ ] Admin transitions an order through every state
- [ ] Playwright suite passes
- [ ] No `console.log` in `src/`
```

### 12.2 Feature spec template

```markdown
# <Feature Name>

## Overview

<2-4 sentence summary of what this feature does and why it exists.>

## Requirements

### REQ-<DOMAIN>-001: <Short title>

**Summary:** <One sentence what.>

**Acceptance criteria:**
- AC-1: <criterion>
- AC-2: <criterion>
- AC-3: <criterion>

(Repeat REQ blocks.)

## Data

Reads: `<Entity>`, `<Entity>`
Writes: `<Entity>`, `<Entity>`

Adds field to `<Entity>`: `<field_name>` (<type>, <indexed | unique | etc>).

## API Surface / Server Actions

Server actions:
- `<actionName>(<args>)`
- ...

Webhooks (if any):
- `POST /api/webhooks/<service>` — <events>

## UI / Routes

- `/<route>` — <page name>
- `/<route>/[param]` — <page name>

(Match exactly to `design-manifest.yaml`.)

## State Machines (if applicable)

`<INITIAL>` → `<NEXT>` → `<NEXT>` → `<TERMINAL>`

| From → To | Trigger | Authorization | Side effects |
|---|---|---|---|
| ... | ... | ... | ... |

Non-listed transitions return HTTP 409 with `<CODE>`.

## Error Cases

This feature can emit (codes from master catalog):
- `<CODE>` (where it triggers)
- ...

UI presentation: ...

## Edge Cases & Business Rules

- <rule>
- <rule>
- <rule>

## Test Coverage

Functional E2E (`tests/e2e/<feature>.spec.ts`):
- Happy path: <description>
- <edge case>: <description>

Smoke (`tests/smoke/<feature>.smoke.spec.ts`):
- `/<route>` renders without 500
- <other shallow check>
```

### 12.3 Catalog template

```markdown
# <Domain> Catalog

(<count> records — all `<entity>: <category>`, all <constraint>.)

---

### 1. <Name>

- `slug`: <slug>
- `name_<lang>`: <name>
- `<field>`: <value>
- variants:
  - sku `<SKU>`, options `<JSON>`, price_modifier <n>, stock <n>
- `active`: true

### 2. <Name>
... (etc)
```

### 12.4 `scaffold.yaml` template

Goes at the **scaffold root** (sibling of `docs/`). Pick ONE of the two `design_source` variants below.

```yaml
project_type: web
template: nextjs
ui_library: shadcn

# Variant A — design source is a separate git repo (recommended)
design_source:
  type: v0-git
  repo: https://github.com/<your-org>/<design-repo>.git
  ref: main                       # branch / tag / commit SHA — pin to SHA for reproducibility
```

OR:

```yaml
project_type: web
template: nextjs
ui_library: shadcn

# Variant B — design source is a ZIP archive at a path
design_source:
  type: v0-zip
  path: ./designs/v1-design.zip   # relative to scaffold root, or absolute
```

### 12.5 `content-fixtures.yaml` template

```yaml
# content-fixtures.yaml — used by design-fidelity gate
products:
  - id: 1
    slug: <slug>
    name_<lang>: <name>
    base_price: <price>
    image_url: /images/seed/<file>.jpg

users:
  - email: customer1@example.com
    name: <name>
    role: CUSTOMER
  - email: admin@example.com
    name: <admin name>
    role: ADMIN

orders:
  - order_number: "#1042"
    status: NEW
    grand_total: <total>
    placed_at: "2026-04-01T14:23:00Z"
```

---

## Appendix A — How SET decomposes your spec

You don't need to know this to write a good spec, but it's useful for understanding why some structures work better than others.

### A.1 The decompose phase

When SET starts, the planner is invoked with `SPEC_PATH=docs/`. It:

1. **Detects multi-file mode** — the directory contains a master `v*-*.md` plus subdirectories. Spawns parallel Explore agents, one per subdirectory.
2. **Reads the master file directly** (it's the hub).
3. **Reads `set/plugins/project-type.yaml`** for verification rules.
4. **Reads `docs/design-manifest.yaml`** for the route inventory (generated by `set-design-import` — the AUTHORITATIVE route list).
5. **Reads `set/orchestration/digest/`** if it exists (extracted requirements, domain summaries, dependency graph).
6. **Recalls relevant memories** (`set-memory recall ... --tags phase:planning`).
7. **Generates `orchestration-plan.json`** with:
   - `changes[]` — each with name, scope, complexity (S/M/L), change_type, model, depends_on, design_routes, requirements
   - `deferred_requirements[]` — requirements not in this batch, with reasons
   - `deferred_design_routes[]` — routes not in this batch
   - `source_items[]` — every spec item with its assigned change

### A.2 What signals the planner picks up

- **Heading hierarchy** — `## Phase N` markers are detected as batch separators.
- **Requirement IDs** — `REQ-<DOMAIN>-NNN` patterns are extracted as discrete units of work with acceptance criteria.
- **Domain Models table** — entities and their relationships drive migration ordering and merge-hazard detection.
- **State machines** — full transition tables drive admin/customer flow change boundaries.
- **Error codes** — assignment of which feature emits which code drives change boundaries (the `Auth` feature owns AUTH_*; the `Cart` feature owns CART_*).
- **UI routes** — matched against `design-manifest.yaml` to bind changes to design components.
- **Completion markers** — `[x]`, ~~strikethrough~~, "done"/"implemented" cause the planner to skip those items.

### A.3 What the dispatcher sends to each agent

For every change, the dispatcher generates `openspec/changes/<change>/input.md`:

```markdown
## Scope
<detailed description of what to build + constraints>

## Implementation Manifest
- New files to create: <extracted from scope>
- New dependencies: <extracted>
- Database: <extracted>

## Project Context
<memory-injected learnings, project patterns, past decisions>

## Project Type
<verification rules, conventions specific to web>

## Sibling Context
<info about parallel changes in the same batch>

## Design Context
<design tokens + per-route component file list from design.md>

## Focus files for this change
<v0-export TSX paths the agent should mount>

## Assigned Requirements
- REQ-CART-001: Add to cart
  - AC-1: ...
  - AC-2: ...

## Cross-Cutting Requirements (awareness only)
<requirements assigned to other changes that affect shared code>

## Read Before Writing
- `.claude/rules/web-frontend.md` — loading states on async buttons
- `docs/data-model.md` — entity relationships

## Project Conventions
<i18n, API style, DB patterns from spec>
```

The agent reads this file and implements the change in the worktree.

### A.4 The gate pipeline

Before merge, every change passes through gates in order:

1. **test** — `pnpm test` (unit + integration)
2. **lint** — `pnpm lint`
3. **build** — `pnpm build`
4. **review** — Claude code review against project conventions
5. **design-fidelity** — screenshot diff vs v0 reference at 3 viewports

After merge, on `main`:

6. **smoke** — `pnpm test:smoke`

Failures send the agent back to iterate. Catastrophic failures (build can't pass after retries) escalate to the sentinel for replan or human intervention.

### A.5 Why this drives spec quality

- **Implementation Manifest is extracted by regex from your scope text.** If your scope says "create types.ts and audit.ts", the manifest will list those. If you write vague prose, the manifest is empty and the agent doesn't know what to scaffold first.
- **Assigned Requirements are quoted verbatim from your feature files.** Bad requirement text goes straight to the agent.
- **Design Context comes from `design-manifest.yaml`** (generated from your design repo). No design repo = no manifest = no design context = generic styling.
- **Cross-Cutting Requirements list other changes' work.** This is what prevents collisions on shared code.

---

## Appendix B — Glossary

| Term | Meaning |
|---|---|
| **Change** | A unit of work assigned to one agent in one worktree. Typical size: 10–25 tasks (~1–4 hours of agent time). |
| **Decompose** | The planner step that turns your spec into `orchestration-plan.json`. |
| **Digest** | An optional preprocessing step that extracts requirements, domains, dependencies as JSON for the planner. |
| **Dispatch** | The step that creates a worktree and generates `input.md` for an agent. |
| **Gate** | A check the change must pass before merging (test, lint, build, design-fidelity, review). |
| **Manifest (design)** | `docs/design-manifest.yaml` — generated route → component-file map. |
| **OpenSpec** | The lightweight spec/change format SET uses internally for proposals → tasks → archived changes. You don't write OpenSpec directly; agents do. |
| **Phase** | A batch of changes processed together. Triggered by `## Phase N` headings in your spec. |
| **Plan** | `orchestration-plan.json` — the planner's output describing all changes in the current batch. |
| **Profile / project type** | The plugin (e.g., `web`) that supplies project-type-specific gates and verification rules. |
| **Replan** | When `auto_replan: true`, after a phase merges, the planner re-reads the spec to find the next phase. |
| **Requirement (REQ-*)** | A discrete contract item with acceptance criteria, extracted from your feature files. |
| **Scaffold** | Project skeleton (`scaffold.yaml`) that declares project type, template, and design source. |
| **Sentinel** | The supervising orchestrator process that watches all worktrees and intervenes on failures. |
| **Smoke test** | A shallow post-merge test that verifies routes render without crashing. NOT a feature test. |
| **v0-export** | The materialised TSX directory under the project root, cloned by `set-design-import` from your design repo. The name is a constant in the importer; it does NOT imply you must use v0.app. |
| **Design repo** | A self-contained Next.js / shadcn / Tailwind TSX repository you publish, in the shape v0.app would produce. The pipeline's authoritative design source. |
| **Worktree** | A git worktree on a branch dedicated to one change. Isolated from main and from sibling worktrees. |

---

## Final word

The leverage point of this entire system is **the spec you produce.** A spec that:

- Names every entity with stable casing
- Catalogs every error code
- Registers every test selector
- Ships a real Next.js / shadcn TSX design repository (not HTML mockups)
- Lists state-machine transitions exhaustively
- Splits >6-change scope into phases
- Cites the same fact in only one place

…will produce a working, design-faithful application on the first orchestration run, using a fraction of the tokens an underspecified version would. That is the contract this guide describes.
