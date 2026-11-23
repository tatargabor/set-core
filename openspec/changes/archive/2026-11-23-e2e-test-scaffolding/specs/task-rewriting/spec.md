# Spec: Task Rewriting

## AC-1: E2E tasks replaced with fill-skeleton instruction
GIVEN tasks.md contains "Create tests/e2e/cart.spec.ts — REQ-CART-001 tests: add product..."
WHEN the dispatcher post-processes tasks.md after scaffold generation
THEN the task is replaced with "Fill test bodies in tests/e2e/cart.spec.ts — N test blocks marked // TODO"

## AC-2: Non-E2E tasks preserved
GIVEN tasks.md contains "Create cart API route at src/app/api/cart/route.ts"
WHEN the dispatcher post-processes tasks.md
THEN this task is unchanged

## AC-3: Multiple E2E tasks collapsed to one
GIVEN tasks.md has tasks 12.1-12.8 all creating tests in the same spec file
WHEN post-processing runs
THEN they are replaced with a single "Fill test bodies in tests/e2e/<name>.spec.ts" task

## AC-4: Task count updated in input.md
GIVEN a skeleton with 131 test blocks was generated
WHEN the Required Tests section is built in input.md
THEN it references the skeleton: "Test skeleton already created at tests/e2e/<name>.spec.ts with 131 blocks"
