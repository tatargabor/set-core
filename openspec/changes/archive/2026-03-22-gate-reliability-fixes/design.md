# Design: gate-reliability-fixes

## Context

Craftbrew Run 8: 1/6 merged, 3 failed. Root causes identified in post-mortem:
- Lint: `dangerouslySetInnerHTML` matched in comments (agent fixed code but mentioned pattern in fix comment)
- Review: 5 retry rounds, each finding new CRITICALs (whack-a-mole)
- Review: 200K+ tokens burned on review retries alone

## Decisions

### D1: Comment-aware lint matching

`_extract_added_lines()` currently returns ALL added lines from diff. Add filtering:

```python
def _extract_added_lines(diff_output: str, skip_comments: bool = True):
    ...
    for file_path, line_num, content in raw_lines:
        if skip_comments:
            stripped = content.strip()
            # Skip single-line comments
            if stripped.startswith("//") or stripped.startswith("#") or stripped.startswith("*"):
                continue
            # Skip lines that are purely documentation (markdown in code)
            if stripped.startswith("* ") or stripped.startswith("/**"):
                continue
        results.append((file_path, line_num, content))
```

This filters out ~90% of false positives. The `dangerouslySetInnerHTML` pattern will still catch actual JSX usage like `<div dangerouslySetInnerHTML={{__html: content}} />` because that's a code line, not a comment.

### D2: Review fix-verification mode

The review gate already passes `retry_context` with previous findings. The fix: on retry rounds (verify_retry_count > 0), modify the review prompt to include:

```
IMPORTANT: This is a RETRY review. Previous review found these issues:
{previous_findings}

Your task is to verify ONLY whether these specific issues were fixed.
Do NOT scan for new issues. Report:
- FIXED: issue was resolved
- NOT_FIXED: issue still present (CRITICAL)

Only report NOT_FIXED issues as CRITICAL. Do not add new findings.
```

This is done in `_execute_review_gate` by checking `verify_retry_count` and adjusting the review prompt.

### D3: Reduce review_extra_retries default

In `gate_profiles.py` GateConfig:
```python
self.review_extra_retries: int = kwargs.get("review_extra_retries", 1)  # was 3
```

And in `verifier.py` handle_change_done:
```python
extra_retries=getattr(gc, "review_extra_retries", 1),  # was 3
```

Total review attempts: `max_retries(2) + 1 = 3` instead of 5.
