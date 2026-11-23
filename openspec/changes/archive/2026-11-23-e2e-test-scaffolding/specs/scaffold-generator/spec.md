# Spec: Scaffold Generator

## AC-1: Skeleton generated from test plan entries
GIVEN a change has test plan entries (filtered by change requirements)
WHEN `generate_skeleton()` is called with the entries and profile
THEN a `.spec.ts` file is written to `tests/e2e/<change-name>.spec.ts` in the worktree containing one test block per entry

## AC-2: REQ-ID prefix in every test block
GIVEN a test plan entry with `req_id=REQ-CART-001` and `scenario_name="add product"`
WHEN the skeleton is rendered
THEN the test block name starts with `REQ-CART-001:` (e.g., `test('REQ-CART-001: add product', ...)`)

## AC-3: Smoke tag applied
GIVEN a test plan entry with `type=smoke`
WHEN the skeleton is rendered
THEN the test includes `{ tag: '@smoke' }` in its options

## AC-4: Tests grouped by REQ under describe blocks
GIVEN multiple entries for REQ-CART-001
WHEN the skeleton is rendered
THEN they are grouped under `test.describe('REQ-CART-001: <requirement title>', () => { ... })`

## AC-5: TODO marker in body
GIVEN a generated test block
WHEN the agent hasn't filled it yet
THEN the body contains `// TODO: implement` as a searchable marker

## AC-6: Profile-driven rendering (core/web separation)
GIVEN a WebProjectType profile
WHEN the core calls `profile.render_test_skeleton(entries, change_name)`
THEN the output uses Playwright syntax (`import { test, expect } from '@playwright/test'`)

## AC-7: No skeleton for changes without test plan entries
GIVEN a change with 0 matching test plan entries
WHEN the dispatcher runs scaffold generation
THEN no skeleton file is created (no empty file)
