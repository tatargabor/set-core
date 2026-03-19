# Design: Cumulative Review Feedback

## Data Structure

New field on change state in `orchestration-state.json`:

```json
{
  "review_history": [
    {
      "attempt": 1,
      "timestamp": "2026-03-19T02:45:00+01:00",
      "review_output": "CRITICAL: middleware only checks cookie existence...",
      "extracted_fixes": "src/middleware.ts:35 — validate token against DB",
      "diff_summary": null
    },
    {
      "attempt": 2,
      "timestamp": "2026-03-19T02:55:00+01:00",
      "review_output": "CRITICAL: token validation doesn't check expiry...",
      "extracted_fixes": "src/middleware.ts:42 — add expiry check",
      "diff_summary": "Added prisma.session.findUnique() in middleware but no expiry check"
    }
  ]
}
```

- `review_output`: truncated to 1500 chars (same as current)
- `extracted_fixes`: output of `_extract_review_fixes()`
- `diff_summary`: git diff --stat between retry attempts (what changed), null on first attempt

## Component Changes

### 1. verifier.py — Append to review_history (write side)

In the CRITICAL review block (L1771-1815), before building retry_context:

```python
# Capture what agent changed since last attempt
diff_summary = None
if verify_retry_count > 0:
    diff_summary = _capture_retry_diff(wt_path, change_name, state_file)

# Append to review_history
history_entry = {
    "attempt": verify_retry_count + 1,
    "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
    "review_output": rr.output[:1500],
    "extracted_fixes": _extract_review_fixes(rr.output),
    "diff_summary": diff_summary,
}
_append_review_history(state_file, change_name, history_entry)
```

### 2. verifier.py — Build squashed retry prompt (read side)

Replace the current retry_context builder with one that reads full history:

```python
def _build_review_retry_prompt(state_file, change_name, current_review, security_guide):
    history = _get_review_history(state_file, change_name)

    parts = ["CRITICAL CODE REVIEW FAILURE. You MUST fix these security/quality issues.\n"]

    if len(history) > 1:
        parts.append("== PREVIOUS ATTEMPTS (DO NOT REPEAT THESE APPROACHES) ==")
        for h in history[:-1]:  # all except current
            parts.append(f"Attempt {h['attempt']}: {h['extracted_fixes']}")
            if h.get('diff_summary'):
                parts.append(f"  You tried: {h['diff_summary']}")
            parts.append(f"  Result: STILL CRITICAL")
        parts.append("== END PREVIOUS ATTEMPTS ==\n")
        parts.append("The approaches above did NOT work. Try a fundamentally different strategy.\n")

    # Current review fixes (same as before)
    fix_instructions = _extract_review_fixes(current_review.output)
    if fix_instructions:
        parts.append("=== REQUIRED FIXES (apply each one) ===")
        parts.append(fix_instructions)
        parts.append("=== END REQUIRED FIXES ===\n")

    if security_guide:
        parts.append("=== SECURITY REFERENCE ===")
        parts.append(security_guide)
        parts.append("=== END SECURITY REFERENCE ===\n")

    return "\n".join(parts)
```

### 3. verifier.py — Capture retry diff

```python
def _capture_retry_diff(wt_path, change_name, state_file):
    """Capture what the agent changed in the last retry attempt."""
    # Get the commit count at last retry start vs now
    result = run_git("diff", "--stat", "HEAD~1", cwd=wt_path, timeout=10)
    if result.exit_code == 0 and result.stdout.strip():
        return result.stdout.strip()[:500]
    return None
```

### 4. state.py — Helper functions

```python
def _append_review_history(state_file, change_name, entry):
    """Append a review history entry to the change."""
    with locked_state(state_file) as st:
        for c in st.changes:
            if c.name == change_name:
                history = c.extras.get("review_history", [])
                history.append(entry)
                c.extras["review_history"] = history
                break

def _get_review_history(state_file, change_name):
    """Get review history for a change."""
    state = load_state(state_file)
    for c in state.changes:
        if c.name == change_name:
            return c.extras.get("review_history", [])
    return []
```

## Decision: No Cross-Run Persistence Yet

The `review_history` lives in `orchestration-state.json` which is per-run. Cross-run learning (extracting patterns into wt-project-web rules) is a separate future change — done manually at wrap-up or automated later.

## Risks

- State file grows: each review_history entry ~2KB. At 3 retries = 6KB per change. Acceptable.
- diff_summary may be noisy: truncate to 500 chars, only --stat not full diff.
