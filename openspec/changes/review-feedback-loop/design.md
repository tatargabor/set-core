# Design: Review Feedback Loop

## Context

Across 12 E2E runs (minishop + craftbrew), the code review gate found the same CRITICAL patterns repeatedly:
- **Payment before order**: Run #6 cart-checkout (3x retry, failed)
- **Client-supplied pricing**: Run #6 cart-checkout, Run #19 order-placement
- **Non-atomic stock**: Run #6 cart-checkout
- **IDOR on mutations**: Run #16, #19 (multiple changes)

The IDOR pattern is already in `security-patterns.md` (section 1). The transaction ordering / pricing / atomicity patterns are NOT covered anywhere — they're pure business logic safety, not auth/authz.

## Goals / Non-Goals

**Goals:**
- Add proven CRITICAL patterns to rules files so agents see them during implementation
- Keep rules concise and actionable (wrong pattern → correct pattern → why)
- Deploy automatically via `set-project init`

**Non-Goals:**
- Automated extraction from review output (future — requires parsing [CRITICAL] blocks)
- Modifying the review gate itself
- Adding non-web patterns

## Decisions

### 1. Separate file for transaction patterns
**Decision:** Create `.claude/rules/web/transaction-patterns.md` rather than expanding security-patterns.md.

**Rationale:** Security patterns cover auth/authz/validation (OWASP-style). Transaction patterns cover business logic ordering, atomicity, and server-side recalculation — conceptually different. Separate files keep each focused and scannable. Cross-reference links them.

### 2. Anti-pattern + correct pattern format
**Decision:** Each rule shows the **wrong** pattern first (marked forbidden), then the **correct** pattern, then **why**.

**Rationale:** Agents learn from contrast. Showing the exact wrong pattern helps them recognize it in their own code. This matches the existing security-patterns.md format.

### 3. Framework-agnostic with ORM examples
**Decision:** Show patterns in Prisma (primary) with notes for other ORMs.

**Rationale:** Most E2E runs use Next.js + Prisma. The pattern is the same regardless of ORM — create-before-charge, recalculate-server-side, atomic-conditional-update.

## Risks / Trade-offs

- **[Risk] Rules file too long → agents ignore it** → Mitigation: keep to 3-4 patterns max, each under 20 lines
- **[Risk] Prisma-specific examples don't help Django/FastAPI** → Mitigation: explain the principle, not just the syntax
