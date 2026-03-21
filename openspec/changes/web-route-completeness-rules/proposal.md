# Proposal: Web Route Completeness Rules

## Why

CraftBrew Run #7 achieved 14/14 merges but revealed two systematic gaps:

1. **Decomposer gap**: A change scope says "browse products across categories (coffees, equipment, merch, bundles)" but the task breakdown only creates `/kavek/page.tsx` — the other 3 category listing pages are never tasked. The agent implements one example and considers the scope done.

2. **Verify gap**: The `cart-checkout` change has return-request tasks marked `[x]` done in tasks.md, but the actual files (`/api/returns/`, return request UI) don't exist. The verify gate checks task checkboxes, not file existence.

Both are web-specific patterns: route-based applications have a predictable structure (listing page + detail page per category, API routes per feature) that can be mechanically verified.

## What Changes

- **Add `.claude/rules/web/route-completeness.md`** — new review rule that tells agents and reviewers to check route completeness: every category needs a listing page, every detail page needs a listing page, every tasked route must exist as a file.
- **Add route coverage acceptance criteria** to the web security checklist (deployed via profile).
- **Extend `rule_keyword_mapping`** in NullProfile to map "catalog", "listing", "category", "page" keywords to the new rule.

These deploy to consumer projects via `set-project init` automatically.

## Capabilities

### New Capabilities
- `route-completeness-check`: Review rule ensuring every spec-mentioned category/route has corresponding page.tsx and API route files. Catches missing listing pages and phantom task completions.

### Modified Capabilities
- `rule-keyword-mapping`: Extended with "catalog"/"listing"/"category" keywords pointing to the new rule.
- `security-checklist`: Extended with route coverage acceptance criteria.

## Risk

**Low**. Additive-only — new rule file and keyword mappings. No changes to existing gate logic or merge pipeline. Worst case: review gate flags false positives on intentionally missing routes (agent can mark as N/A with justification).
