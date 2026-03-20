# Proposal: review-rules-from-e2e

## Why

E2E review analysis of a consumer project orchestration run (89 issues, 19 CRITICAL, 33 HIGH across 3 changes) revealed that 40% of review findings represent genuinely new patterns not covered by any existing rule in `.claude/rules/web/`. Agents cannot follow rules that do not exist. Adding these patterns as explicit rules will prevent the same class of bugs from recurring in future orchestration runs.

## What Changes

- **Extend** `transaction-patterns.md` with 3 new sections: payment failure rollback of side effects, soft status transitions for financial records, and generalize atomic inventory to all finite resources (gift cards, coupons, seat counts)
- **Extend** `security-patterns.md` with secret code enumeration prevention (gift cards, coupons, invite codes, reset tokens)
- **Extend** `api-design.md` with single source of truth for validation logic
- **Create** `schema-integrity.md` — new rules for nullable unique constraints, boolean vs enum modeling, FK cascade strategies, JSON column validation
- **Create** `nextjs-patterns.md` — new rules for force-dynamic anti-pattern and server actions in client effects

## Capabilities

### New Capabilities
- `schema-integrity` — database schema design patterns that prevent data integrity bugs
- `nextjs-patterns` — Next.js-specific patterns that prevent performance and correctness issues

### Modified Capabilities
- `transaction-safety-extensions` — extends existing transaction-patterns.md with 3 new sections
- `secret-code-enumeration` — extends existing security-patterns.md with enumeration prevention
- `validation-single-source` — extends existing api-design.md with validation deduplication

## Impact

- **Files modified**: `.claude/rules/web/transaction-patterns.md`, `.claude/rules/web/security-patterns.md`, `.claude/rules/web/api-design.md`
- **Files created**: `.claude/rules/web/schema-integrity.md`, `.claude/rules/web/nextjs-patterns.md`
- **Downstream**: All consumer projects receive updated rules via `set-project init`
- **No code changes**: These are documentation/rule files only — no runtime behavior changes
