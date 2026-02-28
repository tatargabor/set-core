# Orchestration Planning Guide

How to write effective inputs for `wt-orchestrate` so your batch runs succeed on the first attempt.

> **Prerequisites**: This guide assumes you've read [docs/orchestration.md](orchestration.md) and know how to run `wt-orchestrate plan`, `start`, and `status`.

---

## Table of Contents

1. [Input Formats](#1-input-formats) — spec mode vs brief mode
2. [Scope Isolation](#2-scope-isolation) — keeping changes parallel-safe
3. [Dependencies](#3-dependencies) — explicit and implicit
4. [Testing Requirements](#4-testing-requirements) — what to specify
5. [Plan Sizing](#5-plan-sizing) — S/M/L and optimal batch size
6. [Phase Splitting](#6-phase-splitting) — multi-batch orchestration
7. [Design Rules](#7-design-rules) — what to specify vs leave open
8. [Web Project Patterns](#8-web-project-patterns) — DB, auth, API, deployment
9. [Anti-patterns](#9-anti-patterns) — common mistakes and how to avoid them

See also: [Plan Review Checklist](plan-checklist.md) for a quick pre-flight check.

---

## 1. Input Formats

The orchestrator supports two input modes. **Spec mode is recommended** — it accepts any document format and uses an LLM to extract actionable work.

### Spec Mode (`--spec <path>`)

Pass any markdown document — a release plan, design doc, feature list, or roadmap. The orchestrator sends it to Claude (opus) for decomposition into changes.

```bash
wt-orchestrate --spec docs/v4-release.md plan
```

**Good spec structure:**

```markdown
# v4 Release

## Orchestrator Directives
- max_parallel: 3
- merge_policy: checkpoint
- test_command: pnpm test

## Phase 1 — Data Layer
- Add audit logging: track all entity mutations with actor, timestamp, and diff.
  Uses a separate `audit_log` table. Include Prisma migration.
- Add soft delete: `deletedAt` column on Company, Contact, Campaign.
  Filter soft-deleted records from all queries. Add restore endpoint.

## Phase 2 — API & UI
- Company CSV import: upload CSV, map columns, preview, import.
  Validate emails, deduplicate by domain. Show progress bar.
- Email template editor: WYSIWYG editor for email drafts.
  Support variables ({{company.name}}, {{contact.name}}).
```

**What makes this effective:**
- **Directives at the top** — the orchestrator finds them regardless of position, but top is conventional
- **Phases clearly marked** — `## Phase 1`, `## Phase 2` lets you run one phase at a time with `--phase 1`
- **Each item is self-contained** — includes what to build AND key constraints
- **Technical specifics** — "separate `audit_log` table", "Prisma migration", "`deletedAt` column" — reduces agent guesswork
- **No ambiguity about scope boundaries** — each bullet is one change

**For large specs** (>8000 tokens estimated), the orchestrator auto-summarizes before decomposition. To control which phase is planned, use `--phase`:

```bash
wt-orchestrate --spec docs/v4-release.md --phase 1 plan    # by number
wt-orchestrate --spec docs/v4-release.md --phase "Data" plan # by name
```

### Brief Mode (`project-brief.md`)

A structured template for simpler projects. Auto-detected from `openspec/project-brief.md`:

```markdown
# Project Brief

## Purpose
Internal CRM for tracking sales leads.

## Tech Stack
Next.js 15, Prisma, PostgreSQL, Tailwind, shadcn/ui

## Domain Context
Companies have Contacts. Contacts receive EmailDrafts via Campaigns.

## Feature Roadmap

### Done
- Basic CRUD for companies and contacts
- Email draft generation with AI

### Next
- Audit logging: track entity mutations with actor, timestamp, diff
- Soft delete: deletedAt on Company, Contact, Campaign; filter from queries
- CSV import for companies: upload, column mapping, preview, import

### Ideas
- Real-time collaboration
- Mobile app

## Orchestrator Directives
- max_parallel: 2
- merge_policy: checkpoint
```

The `### Next` section is parsed directly (no LLM call) — each bullet becomes a candidate change. This is faster but less flexible than spec mode.

**When to use which:**

| | Spec mode | Brief mode |
|---|---|---|
| Input format | Any markdown document | Structured template |
| Parsing | LLM (opus) | Bash regex |
| Phase support | Yes (`--phase`) | No |
| Auto-replan | Yes | Yes |
| Best for | Complex multi-phase projects | Simple feature batches |

---

## 2. Scope Isolation

The #1 cause of merge-blocked changes is **overlapping scopes** — two changes editing the same files in parallel.

### The Rule

> If two changes would edit the same file, one MUST depend on the other.

### Parallel-Safe Scopes (Good)

```
Change A: "Add audit logging"      → new table, new module src/lib/audit/
Change B: "Add CSV import"          → new page, new module src/lib/import/
Change C: "Add email templates"     → new component, modifies src/lib/email/
```

These are safe because they touch different directories and modules.

### Overlapping Scopes (Bad)

```
Change A: "Add audit logging"       → adds ActivityAction types to activity-logger.ts
Change B: "Add email review queue"  → adds ActivityAction types to activity-logger.ts
Change C: "Add follow-up tasks"     → adds ActivityAction types to activity-logger.ts
```

All three changes add union type variants to the same file. When they merge in sequence, each creates a merge conflict on the same lines.

### How to Fix Overlapping Scopes

**Option 1: Declare dependencies** — chain changes that touch the same file:

```markdown
- Audit logging: adds `audit_created`, `audit_viewed` activity types
- Email review queue: adds `batch_review` activity type. depends_on: audit-logging
- Follow-up tasks: adds `task_created`, `task_completed` types. depends_on: email-review-queue
```

**Option 2: Extract shared changes** — put the shared modification in its own change:

```markdown
- Extend activity types: add all new ActivityAction variants for v4 features
- Audit logging: depends_on extend-activity-types
- Email review queue: depends_on extend-activity-types
- Follow-up tasks: depends_on extend-activity-types
```

**Option 3: Be specific about which files each change touches** — so the decomposition prompt can detect conflicts:

```markdown
- Audit logging: new src/lib/audit/ module. Does NOT modify activity-logger.ts.
  Uses its own audit_log table instead.
```

### Common Shared Files to Watch

| File pattern | Why it conflicts | Mitigation |
|---|---|---|
| Type union files (`types.ts`, `activity-logger.ts`) | Multiple changes add variants | Extract type changes into a shared change |
| Barrel exports (`index.ts`) | Re-exports added by multiple changes | Chain dependent changes |
| Config files (`next.config.js`, `.env`) | Multiple changes add entries | Chain or use a setup change |
| Schema files (`schema.prisma`) | Multiple migrations conflict | DB changes MUST be sequential |
| Generated files (`.claude/reflection.md`, lockfiles) | Per-session AI-generated content | Already handled by wt-merge auto-resolution |

---

## 3. Dependencies

### Explicit Dependencies

If change B imports code from change A, B depends on A:

```markdown
- Add auth middleware (JWT validation, session management)
- Add user roles: depends_on auth-middleware (uses auth context)
- Add admin dashboard: depends_on user-roles (checks role permissions)
```

### Implicit Dependencies

These are harder to spot but cause the same merge conflicts:

**DB schema migrations** — Two changes adding Prisma migrations create conflicting migration timestamps:
```markdown
# BAD: parallel schema changes
- Add audit_log table
- Add soft delete columns to Company

# GOOD: sequential schema changes
- Add audit_log table
- Add soft delete columns to Company. depends_on: add-audit-log
```

**Shared type definitions** — Union types, enums, interfaces extended by multiple changes:
```markdown
# Specify upfront which types are shared
- Extend shared types: add all new ActivityAction variants, DraftStatus values
- Feature A: depends_on extend-shared-types
- Feature B: depends_on extend-shared-types
```

**Package.json modifications** — Multiple changes adding dependencies:
```markdown
# If two changes add different npm packages, the second merge
# will conflict on package.json. The orchestrator handles this
# with post-merge dependency install, but it's cleaner to chain them.
```

**Environment variables** — Multiple changes adding `.env` entries:
```markdown
# Specify env requirements in the scope so the agent adds them
- Add email sending: needs SMTP_HOST, SMTP_PORT, SMTP_USER env vars
```

**Barrel exports and route registrations** — `index.ts` files, route arrays, navigation menus:
```markdown
# If multiple changes add routes to the same router file,
# chain them or extract a "register routes" setup change
```

### Dependency Declaration in Specs

In spec mode, mention dependencies naturally in the item description — the LLM extracts them:

```markdown
## Features
- User auth: JWT middleware, login/logout endpoints
- User profiles: profile page, avatar upload. Requires auth to be in place first.
- Admin panel: user management. Requires auth and roles.
```

The orchestrator's decomposition prompt converts these into `depends_on` arrays in the plan.

---

## 4. Testing Requirements

### Why Specify Tests in the Plan

If you don't mention testing, the agent may:
- Skip tests entirely
- Write minimal happy-path tests
- Use a test framework that doesn't match your project

### How to Specify Test Requirements

Include test expectations in each item's scope:

```markdown
- Add auth middleware: JWT validation, session management.
  Tests: token validation (valid/expired/missing), role checking,
  middleware integration test with mock request.

- Add CSV import: upload, column mapping, preview, import.
  Tests: valid CSV parsing, invalid format rejection, duplicate detection,
  large file handling (>1000 rows).
```

### Test Infrastructure

If your project has **no test setup** (no `vitest.config.ts`, no `jest.config.js`, no test files), the orchestrator automatically makes the first change a test infrastructure setup. You can also be explicit:

```markdown
## Phase 0 — Infrastructure
- Test setup: configure Vitest with React Testing Library.
  Add test helpers for DB mocking and auth context.
  Create example test for an existing component.

## Phase 1 — Features (all depend on test setup)
- Feature A: ... Tests: ...
- Feature B: ... Tests: ...
```

### Match Existing Patterns

If your project already has tests, mention the existing pattern so agents follow it:

```markdown
## Orchestrator Directives
- test_command: pnpm test

## Notes
Existing tests use Vitest + React Testing Library.
Test files live next to source files as `*.test.ts`.
Use `createMockDb()` from `src/test/helpers.ts` for DB mocking.
```

---

## 5. Plan Sizing

### Complexity Guidelines

| Size | Tasks | Scope | Example |
|---|---|---|---|
| **S** | <10 | Single module, one concern | Add rate limiting middleware |
| **M** | 10–25 | Feature with UI + API + tests | CSV import with preview |
| **L** | 25+ | Cross-cutting, multi-module | Full auth system |

**L changes are a warning sign.** They take longer, produce more code for review, and have a higher chance of stalling or producing low-quality results. Prefer splitting L into multiple M changes.

### Optimal Batch Size

**4–6 changes per batch** is the sweet spot:
- Enough parallelism to keep `max_parallel` workers busy
- Small enough to review merged results between batches
- Manageable merge conflict surface

**2–3 changes**: fine for focused work, but underutilizes parallelism.
**7+ changes**: high merge conflict risk, harder to review, longer feedback loop.

### When a Change is Too Large

Warning signs:
- Scope description is longer than 5 sentences
- You can identify 3+ independent sub-features within one change
- The change touches more than 3 existing modules
- You need to say "and also" more than once in the scope

**Split it.** Two focused M changes are better than one sprawling L change.

### When NOT to Split

- The feature is genuinely atomic (e.g., auth middleware — splitting login from session management creates artificial boundaries)
- Split changes would have circular dependencies
- The "glue code" between split changes would be larger than the feature itself

---

## 6. Phase Splitting

### When to Use Phases

Use phases when your spec has more work than fits in one batch (>6 changes), or when later work depends on earlier work being merged and tested.

### How to Structure Phases

Mark phases explicitly in your spec:

```markdown
# v4 Release Plan

## Phase 1 — Data Foundation
- DB schema updates: audit_log table, soft delete columns
- Prisma client regeneration and type updates
- Test infrastructure setup

## Phase 2 — Core Features (depends on Phase 1)
- Audit logging module
- CSV import with preview
- Email template editor

## Phase 3 — Polish (depends on Phase 2)
- Dashboard analytics
- Bulk operations
- Performance optimization
```

### How the Orchestrator Handles Phases

1. `wt-orchestrate plan` decomposes the **first incomplete phase**
2. `wt-orchestrate start` executes that batch
3. When all changes are merged, if `auto_replan: true`, the orchestrator re-reads the spec, detects Phase 1 is done, and plans Phase 2
4. Repeat until all phases are done

To manually control phases:

```bash
# Plan specific phase
wt-orchestrate --spec docs/v4.md --phase 2 plan

# Or update the spec, marking Phase 1 as done, then replan
wt-orchestrate replan
```

### Status Markers

The orchestrator recognizes these as "completed" markers when scanning your spec:

- `[x]` checkboxes
- ~~Strikethrough~~
- Text containing: "done", "implemented", "kész", "ready", "complete"
- Status tables with completion indicators

Update your spec after each batch to mark completed items:

```markdown
## Phase 1 — Data Foundation ✅
- [x] DB schema updates
- [x] Prisma client regeneration
- [x] Test infrastructure setup

## Phase 2 — Core Features ← orchestrator plans this next
- [ ] Audit logging module
- [ ] CSV import with preview
```

### Phase Size

Each phase should produce **4–6 changes**. If a phase decomposes into 8+ changes, split it further.

---

## 7. Design Rules

The spec you write is a contract between you and the agent. Too vague — the agent guesses wrong. Too detailed — you're doing the agent's job and wasting tokens. This section helps you find the right level.

### Think in Layers

When writing a spec, think about each feature at four layers. Specify the top two, leave the bottom two to the agent:

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: BUSINESS INTENT (always specify)          │
│  What does the user want to achieve?                │
│  "Users can import companies from a CSV file"       │
├─────────────────────────────────────────────────────┤
│  Layer 2: CONSTRAINTS & BOUNDARIES (always specify) │
│  What MUST or MUST NOT happen?                      │
│  "Validate emails, deduplicate by domain,           │
│   max 5000 rows, server actions not API routes"     │
├─────────────────────────────────────────────────────┤
│  Layer 3: SOLUTION SHAPE (specify selectively)      │
│  Which patterns, libraries, UI layout?              │
│  Only specify if you have a strong preference       │
│  or the codebase has an established pattern         │
├─────────────────────────────────────────────────────┤
│  Layer 4: IMPLEMENTATION DETAILS (never specify)    │
│  File paths, function names, variable names,        │
│  internal decomposition, import order               │
└─────────────────────────────────────────────────────┘
```

### What to Specify (High Impact)

These constraints save the agent from making wrong architectural decisions:

**Tech stack and patterns** — the foundation that everything else builds on:
```markdown
## Tech Stack
Next.js 15 (App Router), Prisma ORM, PostgreSQL, Tailwind CSS, shadcn/ui

## Architecture Patterns
- Server actions for mutations (no API routes for internal operations)
- Server components by default, client components only when needed
- Prisma for all DB access (no raw SQL)
- Zod for validation at API boundaries
```

**Auth and authorization approach** — wrong choices here break everything:
```markdown
## Auth
- NextAuth.js with credentials provider
- Tenant isolation: all queries scoped by organizationId from session
- Role-based access: ADMIN, MANAGER, USER roles
- Middleware checks auth on all /dashboard/* routes
```

**Error handling strategy** — inconsistency here makes debugging painful:
```markdown
## Error Handling
- Server actions return { data?, error? } — never throw
- Client components use error boundaries
- Log errors to structured logger (not console.log)
```

**Naming conventions** — agents follow existing code, but if it's inconsistent, specify:
```markdown
## Conventions
- Files: kebab-case (add-company-form.tsx)
- Components: PascalCase
- DB tables: PascalCase in Prisma schema (maps to snake_case in DB)
- Server actions: camelCase functions in *-actions.ts files
```

**Database patterns** — consistency here prevents schema drift:
```markdown
## DB Patterns
- All tables have: id (cuid), createdAt, updatedAt
- Soft delete: deletedAt nullable DateTime (not boolean isDeleted)
- Audit: separate audit_log table, not per-table columns
- Relations: always define both sides in Prisma schema
```

**UI patterns** — if you have a component library or layout convention:
```markdown
## UI Patterns
- Use shadcn/ui components (not custom implementations)
- Data tables: use DataTable pattern with column definitions
- Forms: use react-hook-form + zod resolver
- Loading states: use Skeleton components, not spinners
- Toast notifications for success/error feedback
```

### The Spec-Writing Checklist

Before finalizing each feature in your spec, mentally walk through these questions:

| Question | If you skip it... |
|---|---|
| **What data does this feature read/write?** | Agent may invent tables or misuse existing ones |
| **Who can access this?** | Agent may skip auth checks or add wrong ones |
| **What happens on error?** | Agent may throw exceptions, show raw errors, or silently fail |
| **What's the happy path AND edge cases?** | Agent only builds the happy path |
| **Does this interact with existing features?** | Agent may duplicate logic or break existing behavior |
| **What's the UI entry point?** | Agent may create orphan pages with no navigation link |

Example — applying the checklist to "email template editor":

```markdown
- Email template editor:
  Data: new EmailTemplate table (name, subject, body, variables, createdBy).
  Access: any authenticated user can CRUD their own templates. Admin sees all.
  Errors: save failures show toast. Invalid variable syntax highlighted inline.
  Edge cases: empty template, template with undefined variables, very long body.
  Integration: drafts page should show "Use template" button to pre-fill.
  UI: new /templates page linked from sidebar. TipTap editor for body.
  Tests: CRUD operations, variable interpolation, access control.
```

### What to Leave Open (Low Impact)

Over-specifying these wastes tokens and constrains the agent unnecessarily:

- **Exact file paths** — "put the component in `src/app/(dashboard)/companies/components/import-dialog.tsx`" → The agent will find the right place based on existing structure
- **Internal function decomposition** — "create a `parseCSV()` helper that calls `validateRow()` which calls `normalizeEmail()`" → Let the agent decompose naturally
- **Variable and parameter names** — The agent follows existing codebase conventions
- **Import organization** — Auto-handled by the project's linter/formatter
- **Comment placement** — The agent adds comments where logic isn't self-evident
- **Exact component hierarchy** — "wrap in a Card, inside a div with flex" → Just say what data to show; the agent matches existing UI patterns

### What to Specify Selectively (Layer 3)

These are worth specifying when you have a reason, but fine to omit:

| Concern | Specify when... | Skip when... |
|---|---|---|
| **Specific library** (e.g., TipTap, papaparse) | You've evaluated options and have a preference | Any standard library would work |
| **UI layout** (e.g., 3-step wizard, split panel) | UX is critical and you have a wireframe in mind | Standard CRUD layout is fine |
| **API shape** (e.g., REST vs GraphQL, endpoint naming) | Public API or shared with other services | Internal server actions |
| **Caching strategy** | Performance is a known concern | Standard request-response is fine |
| **State management** (e.g., zustand, context) | Complex client-side state | Server-rendered pages |

### The Sweet Spot

Specify **what** + **constraints** + **integration points**. Leave **how** to the agent:

```markdown
# Good: what + constraints + integration
- CSV import: upload CSV, map columns to Company fields, preview first 10 rows,
  then import. Validate emails with zod. Deduplicate by domain.
  Use server actions, not API routes. Show progress with shadcn Progress component.
  Add "Import" button to company list page toolbar.
  Tests: valid CSV, invalid format, duplicate handling, >1000 rows.

# Bad: over-specified implementation
- CSV import: create src/lib/import/csv-parser.ts with parseCsvFile() function
  that uses papaparse. Create src/app/(dashboard)/companies/import/page.tsx
  with a 3-step wizard using useState for step tracking. In step 1...

# Also bad: too vague
- CSV import
```

### Spec Patterns for Common Feature Types

**CRUD feature:**
```markdown
- [Entity] management: full CRUD for [Entity].
  Fields: [list key fields and types].
  Access: [who can read/write].
  UI: list page with search/filter, detail page with edit form.
  Validation: [key validation rules].
  Tests: create, read, update, delete, validation errors, access control.
```

**Integration/import feature:**
```markdown
- [Source] import: [describe input format and source].
  Mapping: [how input fields map to DB fields].
  Validation: [what makes input valid/invalid].
  Deduplication: [how to handle duplicates].
  Error handling: [skip row vs abort vs report].
  Limits: [max rows, file size, rate limits].
  Tests: valid input, invalid input, duplicates, large dataset, edge cases.
```

**Background job / automation:**
```markdown
- [Action] automation: [what triggers it, what it does].
  Schedule: [cron / event-driven / manual trigger].
  Idempotency: [what happens if it runs twice].
  Failure handling: [retry strategy, notification on failure].
  Observability: [how to check status, logs, history].
  Tests: trigger, execution, failure, retry, concurrent runs.
```

**Dashboard / analytics:**
```markdown
- [Name] dashboard: [what questions does it answer].
  Metrics: [list specific metrics with calculation method].
  Time range: [default period, selectable ranges].
  Data source: [which tables/queries, pre-aggregated or live].
  Performance: [acceptable load time, caching strategy if needed].
  Tests: metric calculation accuracy, empty state, date range filtering.
```

---

## 8. Web Project Patterns

Patterns for typical full-stack web projects with database, authentication, API, and deployment.

### DB Schema Changes

**Rule: Schema migrations MUST be in a separate, early change.**

```markdown
## Phase 1 — Schema
- DB schema updates: add audit_log table, add deletedAt to Company/Contact/Campaign,
  add template table for email templates. Single Prisma migration.

## Phase 2 — Features (all depend on schema change)
- Audit logging: uses audit_log table
- Soft delete: uses deletedAt columns
- Email templates: uses template table
```

Why: Prisma generates one migration per `npx prisma migrate dev`. Two parallel changes creating migrations get conflicting timestamps and migration histories.

### Auth Layer

**Rule: Auth changes are foundational — they go first.**

```markdown
## Phase 1
- Auth middleware: JWT validation, session management, role enum
- Tenant isolation: scope all queries by organizationId

## Phase 2 (depends on Phase 1)
- Features that use auth context...
```

Don't add auth to individual features separately — it creates inconsistencies.

### API Routes and Server Actions

**Group by domain, not by HTTP method:**

```markdown
# Good: domain-grouped
- Company management: CRUD endpoints, search, filtering
- Contact management: CRUD endpoints, email validation, dedup
- Campaign management: create, schedule, send, analytics

# Bad: method-grouped
- Add all GET endpoints for companies, contacts, campaigns
- Add all POST endpoints for companies, contacts, campaigns
```

Domain grouping keeps each change's files isolated.

### UI Components

**Isolate by page/feature, not by component type:**

```markdown
# Good: page-isolated
- Company list page: table, filters, search, pagination
- Company detail page: info card, contact list, activity feed
- Import dialog: upload, column mapping, preview, progress

# Bad: component-type-grouped
- Add all table components
- Add all form components
- Add all dialog components
```

### Deployment Platform

Mention platform constraints that affect code:

```markdown
## Deployment
Platform: Railway (Docker-based)
- Build command: pnpm build
- Start command: pnpm start
- Environment: Node 20, PostgreSQL 16
- Env vars managed via Railway dashboard
- No filesystem persistence (use DB or S3 for uploads)
- Health check: GET /api/health
```

This prevents the agent from writing code that assumes local filesystem storage, uses incompatible Node features, or ignores build constraints.

### Environment Variables

List required env vars so the agent adds them to `.env.example`:

```markdown
## Required Env Vars
- DATABASE_URL: PostgreSQL connection string
- NEXTAUTH_SECRET: session encryption key
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS: email sending
- S3_BUCKET, S3_REGION, S3_ACCESS_KEY: file uploads
```

---

## 9. Anti-patterns

### Anti-pattern: Overlapping Scopes Without Dependencies

**Symptom**: Multiple changes merge-blocked on the same files.

```markdown
# Bad
- Add feature A (modifies types.ts)
- Add feature B (modifies types.ts)
- Add feature C (modifies types.ts)
```

**Fix**: Chain them or extract shared type changes (see [Scope Isolation](#2-scope-isolation)).

### Anti-pattern: Missing Test Requirements

**Symptom**: Changes merge without tests. Post-merge build passes but features are broken at runtime.

```markdown
# Bad
- Add CSV import

# Good
- Add CSV import: ... Tests: valid CSV, invalid format, large file, duplicate handling
```

### Anti-pattern: Oversized Changes

**Symptom**: Ralph loop runs 5+ iterations, code quality degrades, change stalls.

```markdown
# Bad: L-sized kitchen sink
- Add complete user management system with auth, roles, profiles,
  admin panel, audit logging, and email notifications

# Good: split into focused changes
- Add auth middleware [M]
- Add user profiles [M] depends_on: auth
- Add admin panel [M] depends_on: auth
- Add audit logging [S]
```

### Anti-pattern: Vague Scope Descriptions

**Symptom**: Agent makes wrong architectural choices, implements the wrong thing.

```markdown
# Bad
- Improve the email system

# Good
- Email template editor: WYSIWYG editor using TipTap for email drafts.
  Support variable interpolation ({{company.name}}, {{contact.name}}).
  Templates saved to email_template table. Server actions for CRUD.
```

### Anti-pattern: Forgetting Shared Infrastructure

**Symptom**: Each change reinvents test helpers, auth mocking, DB setup.

```markdown
# Bad: jump straight to features
- Feature A (sets up its own test helpers)
- Feature B (sets up different test helpers)

# Good: shared infra first
- Test infrastructure: Vitest config, DB mock helpers, auth mock, test factories
- Feature A: depends_on test-infrastructure
- Feature B: depends_on test-infrastructure
```

### Anti-pattern: Ignoring Generated File Conflicts

**Symptom**: Merge-blocked on `.claude/reflection.md`, lockfiles, build artifacts.

These are auto-resolved by `wt-merge` and shouldn't cause manual intervention. If they do, check that the conflicting file pattern is in `wt-merge`'s `GENERATED_FILE_PATTERNS` list.

### Anti-pattern: No Phase Boundaries in Large Specs

**Symptom**: Orchestrator plans 10+ changes in one batch, merge conflicts everywhere, long feedback loop.

```markdown
# Bad: flat list of 15 features
- Feature 1
- Feature 2
...
- Feature 15

# Good: phased
## Phase 1 — Foundation (4 changes)
## Phase 2 — Core Features (5 changes)
## Phase 3 — Polish (6 changes)
```

### Anti-pattern: Missing Runtime Dependency Awareness

**Symptom**: Build passes in the worktree, merge succeeds, but the app crashes at runtime with `Module not found` or `Cannot resolve` errors.

Each worktree has its own `node_modules` populated during `wt-new`. But after merge, main's `node_modules` may be stale — it doesn't have packages added by the merged branch. The orchestrator now runs post-merge `pnpm install` when `package.json` changes, but your spec should still be explicit about new dependencies:

```markdown
# Good: explicit about new packages
- Rich text editor for email templates. Uses TipTap editor (new dependency: @tiptap/react, @tiptap/starter-kit).

# Bad: agent picks a library, you don't know it needs install
- Rich text editor for email templates.
```

### Anti-pattern: No Existence Checks Before Updates

**Symptom**: `PrismaClientKnownRequestError: Record not found` at runtime because agent wrote `.update()` without checking if the record exists.

This is a code quality issue but you can prevent it in the spec:

```markdown
# Good: error handling is part of the spec
- Update draft status: find draft by ID, return error if not found, then update.
  Handle concurrent deletion gracefully.

# Bad: assumes happy path only
- Update draft status
```

Agents tend to skip existence checks before `.update()` and `.delete()` calls. Mentioning error handling in the scope makes the agent write defensive code.

### Anti-pattern: Silent Feature Omission

**Symptom**: The agent implements 80% of a feature and marks the change as done. Missing parts are only discovered during manual testing.

This happens when the scope is vague enough that the agent can justify skipping parts. Prevent it with explicit acceptance criteria:

```markdown
# Good: enumerated deliverables
- Admin dashboard:
  1. User list with search, filter by role, sort by last login
  2. User detail page with edit form and role assignment
  3. Impersonation button (admin can view app as another user)
  4. Navigation link in sidebar (visible only to ADMIN role)

# Bad: agent decides what "admin dashboard" means
- Admin dashboard for user management
```

### Anti-pattern: Progressive Type Accumulation

**Symptom**: First merge succeeds. Second merge has a minor conflict. Third merge is stuck because the same union type file has been modified by every prior merge.

When 3+ changes each add to the same type (union types, enums, activity action lists), the conflict surface grows with each merge. Even with dependency chains, the diff gets harder:

```markdown
# Bad: 4 parallel changes all adding ActivityAction types
- Audit logging (adds: audit_created, audit_viewed)
- CSV import (adds: import_started, import_completed)
- Email templates (adds: template_created, template_used)
- Follow-up tasks (adds: task_created, task_completed)

# Good: extract shared type changes as Phase 0
## Phase 0
- Extend ActivityAction type with all v4 variants:
  audit_created, audit_viewed, import_started, import_completed,
  template_created, template_used, task_created, task_completed

## Phase 1 (depends on Phase 0)
- Audit logging (uses existing ActivityAction types)
- CSV import (uses existing ActivityAction types)
- ...
```
