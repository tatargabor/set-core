# Design: orchestrator-start-fixes

## Approach

Direct fixes in existing files — no new architecture needed.

### 1. default_model directive

Add `default_model` case to the directive parser (~line 432) and add it to the JSON output object. Validate against `^(haiku|sonnet|opus)$`.

### 2. sentinel restart args

The sentinel.md Step 3 crash recovery section has:
```bash
set-orchestrate start &
```
Should be:
```bash
set-orchestrate start $ARGUMENTS &
```

### 3. No new state management needed

The auto-plan fix (already committed) handles spec mismatch detection. These fixes complement it.
