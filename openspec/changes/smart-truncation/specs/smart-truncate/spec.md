# Smart Truncate

## Overview

A utility module (`lib/set_orch/truncate.py`) providing safe text truncation that never silently drops content. Replaces all `output[-N:]` patterns across the codebase.

## API

### `smart_truncate(text: str, max_chars: int, *, head_ratio: float = 0.3) -> str`

If `len(text) <= max_chars`, return as-is.

Otherwise, split the budget:
- **Head**: first `max_chars * head_ratio` characters (setup errors, root causes)
- **Tail**: last `max_chars * (1 - head_ratio)` characters (final errors, summaries)
- **Middle marker**: `\n\n... [truncated {N} lines — {M} chars omitted] ...\n\n`

The marker counts truncated lines and chars so the LLM knows the scale of what's missing.

```python
smart_truncate(build_output, 3000)
# Returns:
# <first ~900 chars>
#
# ... [truncated 247 lines — 12340 chars omitted] ...
#
# <last ~2100 chars>
```

### `smart_truncate_structured(text: str, max_chars: int, *, head_ratio: float = 0.3, keep_patterns: list[str] | None = None) -> str`

Like `smart_truncate` but scans the truncated middle section for important lines matching `keep_patterns` (default: lines containing `error`, `Error`, `FAIL`, `CRITICAL`, `WARNING`, `panic`, `Traceback`).

Preserved lines are inserted between head and tail:

```
<head>

... [truncated 247 lines — 12340 chars omitted, 3 error lines preserved below] ...

  > line 45: ERROR: Cannot find module 'prisma'
  > line 102: Error: ENOENT: no such file or directory
  > line 189: FAIL src/auth.test.ts

<tail>
```

Each preserved line is prefixed with `> line N:` to show its position. If preserved lines would exceed 20% of `max_chars`, keep only the first N that fit.

### `truncate_with_budget(items: list[tuple[str, str]], max_chars: int) -> tuple[list[tuple[str, str]], list[str]]`

For budget-based truncation (security rules, planning rules). Takes `(name, content)` pairs.

Returns `(included_items, omitted_names)` — includes items until budget is reached, returns names of items that didn't fit. Caller is responsible for adding "N items omitted: [names]" marker to prompt.

## Application Sites

### verifier.py — Gate retry context (build/test/e2e output)

| Current | New |
|---------|-----|
| `build_output[-3000:]` | `smart_truncate_structured(build_output, 3000)` |
| `test_output[-3000:]` | `smart_truncate_structured(test_output, 3000)` |
| `e2e_output[:8000]` | `smart_truncate_structured(e2e_output, 8000)` |
| `output[-max_chars:]` in `run_tests_in_worktree` | `smart_truncate(output, max_chars)` |
| `verify_output[-400:]` | `smart_truncate(verify_output, 400)` |

### verifier.py — Security rules injection

| Current | New |
|---------|-----|
| `content[:1500]` per rule, `total > 4000 break` | `truncate_with_budget(rules, 4000)` + omitted note |

### templates.py — Smoke/build fix prompts

| Current | New |
|---------|-----|
| `output_tail[-2000:]` | `smart_truncate_structured(output_tail, 2000)` |
| `build_output[-3000:]` | `smart_truncate_structured(build_output, 3000)` |

### merger.py — State storage

| Current | New |
|---------|-----|
| `output[-1000:]` smoke | `smart_truncate_structured(output, 1000)` |
| `output[-2000:]` build | `smart_truncate_structured(output, 2000)` |
| `output[-2000:]` test | `smart_truncate_structured(output, 2000)` |
| `output[-8000:]` e2e | `smart_truncate_structured(output, 8000)` |

### engine.py — Replan context

| Current | New |
|---------|-----|
| `e2e_output[-2000:]` | `smart_truncate_structured(e2e_output, 2000)` |

### dispatcher.py — Rule injection

| Current | New |
|---------|-----|
| `total + len(content) > 4000: break` | `truncate_with_budget(rules, 4000)` + omitted note |

## Acceptance Criteria

- AC-1: `smart_truncate` preserves head+tail with visible marker showing omitted count
- AC-2: `smart_truncate_structured` extracts error/warning lines from truncated middle
- AC-3: `truncate_with_budget` returns omitted item names for explicit markers
- AC-4: All 12+ truncation sites in verifier/merger/engine/templates/dispatcher replaced
- AC-5: Unit tests cover edge cases: empty input, input smaller than limit, no error lines in middle, many error lines exceeding 20% budget
- AC-6: No behavioral regressions — gates still pass/fail based on same criteria, just with better context
