# Issue Investigation: {issue_id}

## Context
- **Environment:** {environment}
- **Source:** {source}
- **Affected change:** {affected_change}
- **Severity (initial):** {severity}
- **Detected at:** {detected_at}
- **Occurrence count:** {occurrence_count}

## Error Details
```
{error_detail}
```

## Other Open Issues
{open_issues_summary}

## Instructions

Investigate this issue thoroughly. **Do NOT fix anything** — only diagnose.

1. **Read the error output** — identify the exact failure point (file, line, function)
2. **Read the affected code** — understand the context around the failure
3. **Check git history** — `git log --oneline -20 -- <affected_files>` to see recent changes
4. **Check for patterns** — search for similar past issues in .set/issues/registry.json
5. **Trace the root cause** — follow the chain from symptom to underlying bug
6. **Assess impact** — what breaks if this isn't fixed? Is it blocking?
7. **Check for related open issues** — could this be the same root cause as another issue?

## Output Format

End your response with a JSON diagnosis block:

DIAGNOSIS_START
{{
  "root_cause": "Clear description of the actual underlying bug",
  "impact": "low|medium|high|critical",
  "confidence": 0.85,
  "fix_scope": "single_file|multi_file|cross_module",
  "suggested_fix": "What needs to change and why",
  "affected_files": ["path/to/file.py:42"],
  "related_issues": [],
  "suggested_group": null,
  "group_reason": null,
  "tags": ["relevant", "tags"]
}}
DIAGNOSIS_END
