# Smart Truncation

## Why

When LLM-driven gates (review, smoke fix, build fix, replan) receive truncated output, they make wrong decisions — the review gate reported a test file as "missing" because the diff was silently truncated. This pattern exists in 12+ places across the codebase: `output[-N:]` slicing drops the beginning of output (where setup errors and root causes live) without any marker.

The review gate was fixed with a file-aware approach (stat summaries for omitted files), but every other truncation site still uses blind tail slicing: build output (2-3K), test output (2K), smoke output (1-2K), E2E output (8K), security rules (4K budget). Each risks the same class of bug: an LLM making decisions based on incomplete information without knowing it's incomplete.

## What Changes

- **New utility**: `smart_truncate()` function that preserves head + tail with a visible "[truncated N lines]" marker in the middle
- **Variant for structured output**: `smart_truncate_structured()` that identifies error/warning lines and preserves them even if they fall in the truncated middle section
- **Apply across all truncation sites**: Replace blind `[-N:]` slicing in verifier, templates, merger, engine, dispatcher
- **Rules injection**: Budget-based rule loading gets a visible "N rules omitted" note instead of silent cutoff

## Capabilities

### New Capabilities
- `smart-truncate` — head+tail truncation utility with visible markers and optional error-line preservation

### Modified Capabilities
- Gate output handling in verifier, merger, engine — use smart truncation instead of blind slicing
- Template output injection — preserve error context in smoke/build fix prompts
- Rule injection in dispatcher/verifier — visible truncation markers

## Impact

- **`lib/set_orch/truncate.py`** (new): Core utility module
- **`lib/set_orch/verifier.py`**: Replace ~6 truncation sites
- **`lib/set_orch/merger.py`**: Replace ~4 truncation sites  
- **`lib/set_orch/engine.py`**: Replace ~2 truncation sites
- **`lib/set_orch/templates.py`**: Replace ~2 truncation sites
- **`lib/set_orch/dispatcher.py`**: Replace rule injection truncation
- **`tests/unit/test_truncate.py`** (new): Unit tests for utility
- **Risk**: Low — truncation is cosmetic/contextual, not logic. All changes are output formatting.
