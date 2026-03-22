# Design: gate-lint-forbidden-patterns

## Context

The verify pipeline has 8 gates executed sequentially: build → test → e2e → scope_check → test_files → review → rules → spec_verify. The review gate is the only mechanism that checks code quality patterns in the diff, and it relies entirely on LLM judgment. Documented failures show agents using type hacks (`any` casts) that pass the build gate but create runtime errors — the review LLM inconsistently classifies these as CRITICAL.

## Goals / Non-Goals

**Goals:**
- Deterministic grep-based lint gate that catches forbidden patterns with 100% reliability
- Pattern sources from profile plugins and project-knowledge.yaml
- Positioned before review gate so issues are caught early (less token waste)
- Blocking for CRITICAL patterns, warning for WARNING patterns

**Non-Goals:**
- Replace the LLM review gate (it handles nuanced judgment that grep can't)
- Run full linters (eslint, ruff) — those are covered by test_command
- Cross-file analysis (only scans the diff)

## Decisions

### D1: Lint gate position — after scope_check, before review

**Decision:** Register lint gate between test_files and review in the pipeline.

**Pipeline order:**
```
build → test → e2e → scope_check → test_files → LINT → review → rules → spec_verify
```

**Why after scope/test_files?** Those are fast structural checks. Lint is next — faster than review, catches issues before expensive LLM call.

**Why before review?** If lint catches a CRITICAL pattern, the agent retries before the review LLM even runs — saves review tokens.

### D2: Pattern format

**Decision:** Patterns are dicts with `pattern` (regex), `severity` ("critical" or "warning"), `message` (human-readable), and optional `file_glob` (restrict to matching files).

```python
{
    "pattern": r"prisma:\s*any|as\s+any.*[Pp]risma",
    "severity": "critical",
    "message": "Never use 'any' for database client — fix the schema instead",
    "file_glob": "*.ts"  # optional — only check .ts files
}
```

### D3: Pattern sources — profile + project-knowledge.yaml

**Decision:** Two sources, merged at runtime:

1. **Profile plugin**: `profile.get_forbidden_patterns()` returns a list of pattern dicts. The web profile would include Prisma-specific patterns, Next.js anti-patterns, etc.

2. **project-knowledge.yaml**: `verification.forbidden_patterns` section. Project-specific additions.

```yaml
# project-knowledge.yaml
verification:
  forbidden_patterns:
    - pattern: "console\\.log\\("
      severity: warning
      message: "Remove console.log before merge"
    - pattern: "TODO.*HACK"
      severity: warning
      message: "Unresolved hack marker"
```

Profile patterns are loaded first, then project-knowledge patterns are appended. No deduplication needed — grep runs all patterns.

### D4: Scanning the diff, not the worktree

**Decision:** Scan `git diff <merge_base>..HEAD` output (the same diff the review gate uses), not the full worktree.

**Why?** We only care about patterns INTRODUCED by this change, not pre-existing code. Scanning the full worktree would produce false positives from code the agent didn't touch.

**Implementation:** Extract added lines (lines starting with `+`) from the diff, then grep each forbidden pattern against them.

### D5: GateConfig integration

**Decision:** Add `lint: str = "run"` field to GateConfig. Default profiles:
- infrastructure: lint="skip"
- schema: lint="warn"
- foundational: lint="run"
- feature: lint="run"
- cleanup-before: lint="warn"
- cleanup-after: lint="skip"

### D6: Retry context for CRITICAL matches

**Decision:** On CRITICAL match, the retry_context includes:
- Which pattern matched
- The exact file and line from the diff
- The message explaining why it's forbidden
- Instruction to fix the root cause, not work around it

```
FORBIDDEN PATTERN DETECTED:
  File: src/lib/session.ts (diff line 42)
  Pattern: prisma: any
  Rule: Never use 'any' for database client — fix the schema instead

Fix the root cause. Do NOT use type casts to bypass build errors.
```
