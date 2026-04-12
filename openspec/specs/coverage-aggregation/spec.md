# Spec: Coverage Aggregation

## AC-1: Post-merge coverage uses per-change requirements
GIVEN a change has `requirements` field with N REQ-IDs (e.g., cart: 8 REQs)
WHEN `_parse_test_coverage_if_applicable` runs after merge
THEN coverage is calculated as covered/N (not covered/total_digest_reqs)

## AC-2: Coverage gate and post-merge parser agree
GIVEN the coverage gate calculated 100% for a change (8/8 own REQs)
WHEN the post-merge coverage parser runs
THEN the stored `coverage_pct` matches the gate result (100%, not 4.1%)

## AC-3: Dashboard shows per-change coverage correctly
GIVEN cart-and-promotions has 8 REQs and all 8 are covered by tests
WHEN the dashboard displays coverage
THEN it shows 100% for cart-and-promotions (not the global 2/49 ratio)

## AC-4: Global coverage aggregated from per-change data
GIVEN 6 changes each with their own coverage percentages
WHEN the dashboard displays overall coverage
THEN it shows the union of all covered REQs across all changes divided by total unique REQs

## AC-5: Fallback for acceptance-test changes
GIVEN a change with `change_type=acceptance-tests` (cross-cutting E2E)
WHEN post-merge coverage runs
THEN it uses ALL digest REQ-IDs (global coverage responsibility)
