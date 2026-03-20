# Proposal: Review Feedback Loop

## Why

The code review gate repeatedly finds the same CRITICAL patterns across E2E runs — payment-before-order, client-supplied pricing, non-atomic stock operations, IDOR on mutations. Each time, the agent wastes 2-3 retry cycles (~100K tokens) trying to fix what it should have implemented correctly from the start. These patterns are **known** from 12+ runs but aren't in the security rules that agents see during implementation.

The review gate catches problems **after** implementation. We need to feed proven CRITICAL patterns **back into the rules** so agents avoid them upfront.

## What Changes

- **Expand `.claude/rules/web/security-patterns.md`** with e-commerce transaction patterns (payment ordering, server-side price validation, atomic stock operations) extracted from actual E2E review failures
- **Add `.claude/rules/web/transaction-patterns.md`** for e-commerce-specific business logic safety patterns that go beyond pure security (ordering of operations, atomicity, server-side recalculation)
- **These deploy via `set-project init`** to all consumer projects automatically

## Capabilities

### New Capabilities
- `transaction-safety-rules`: Server-side transaction ordering, price validation, and atomicity rules for e-commerce and payment flows

### Modified Capabilities
_(none — security-patterns.md stays focused on auth/IDOR/XSS, new file covers transaction safety)_

## Impact

- **Modified files**: `.claude/rules/web/security-patterns.md` (minor — add cross-reference to transaction-patterns)
- **New files**: `.claude/rules/web/transaction-patterns.md`
- **Deployment**: `set-project init` auto-deploys to consumer projects
- **Effect**: Agents see transaction safety rules during implementation AND review gate has them as reference
