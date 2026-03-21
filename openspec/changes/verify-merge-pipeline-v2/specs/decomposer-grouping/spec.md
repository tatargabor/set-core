# Spec: Decomposer Change Grouping

## Requirements

### REQ-DG-001: Domain-based grouping in decompose prompt
The decomposer must group small, related changes into larger bundles instead of creating one change per requirement.

**Acceptance Criteria:**
- [ ] AC1: Decompose prompt includes grouping rules: same domain/directory → single change
- [ ] AC2: Prompt specifies target change count relative to max_parallel (e.g., max_parallel × 2)
- [ ] AC3: S-complexity items in same domain are merged into M-complexity bundles
- [ ] AC4: Grouped changes named by domain ("frontend-page-fixes") not individual bug ("fix-product-detail-500")

### REQ-DG-002: max_parallel injected into decompose context
The decomposer needs to know how many parallel agents are available to optimize change count.

**Acceptance Criteria:**
- [ ] AC1: `max_parallel` value from directives is included in decompose prompt context
- [ ] AC2: Prompt guidance: "Target max_parallel × 2 changes for optimal throughput"
