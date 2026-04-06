# Spec: Dispatcher Integration

## AC-1: Scaffold generated after worktree bootstrap
GIVEN a change is dispatched and has test plan entries
WHEN the worktree bootstrap completes
THEN `generate_skeleton()` is called and the spec file is written before the agent starts

## AC-2: Skeleton path logged
GIVEN a skeleton was generated
WHEN the dispatcher finishes dispatch
THEN an INFO log shows the file path and test block count

## AC-3: No scaffold when profile lacks method
GIVEN a profile without `render_test_skeleton` method (e.g., NullProfile)
WHEN dispatch runs
THEN skeleton generation is skipped (no error)

## AC-4: Existing spec file not overwritten on redispatch
GIVEN the agent already modified the spec file (filled in test bodies)
WHEN the change is redispatched (e2e retry)
THEN the existing spec file is preserved, not overwritten with a fresh skeleton
