# Digest and Triage

## What Is a Digest?

A digest is a structured extract of the specification. It breaks a multi-thousand-line spec document into machine-processable JSON format, where every requirement receives a unique identifier (REQ-001, REQ-002, etc.).

This enables the orchestrator to:

- **Track** which requirement is implemented by which change
- **Verify** that every requirement is covered
- **Identify** ambiguous points before development begins

![The complete digest generation flow](diagrams/rendered/02-digest-flow.png){width=90%}

## Digest Generation Steps

### 1. Spec Scanning (`scan_spec_directory`)

The system maps the input file or directory:

```bash
wt-orchestrate --spec docs/specs/ digest
```

Scan results:

- **file_count**: number of files processed
- **source_hash**: hash computed from all file contents (freshness check)
- **master_file**: if there is an `index.md` or similar, it becomes the main file

### 2. Prompt Assembly (`build_digest_prompt`)

The system builds a structured prompt for the Claude API, containing all spec files and the expected output format.

### 3. API Call and Parsing

Claude processes the specification and returns structured JSON output:

```json
{
  "requirements": [
    {
      "id": "REQ-001",
      "title": "JWT authentication",
      "brief": "Token-based auth on /api/* endpoints",
      "priority": "high",
      "source_file": "docs/v3-security.md",
      "section": "2.1 Authentication"
    }
  ],
  "phases": [...],
  "ambiguities": [...]
}
```

### 4. ID Stabilization (`stabilize_ids`)

If a previous digest exists, the system preserves existing REQ-XXX identifiers so that requirement tracking doesn't break after an update.

## Digest Output Files

The digest writes to the `wt/orchestration/digest/` directory:

| File | Contents |
|------|---------|
| `requirements.json` | All requirements with REQ-XXX identifiers |
| `phases.json` | Phase structure (what belongs to which phase) |
| `digest-meta.json` | Hash, date, file counts |
| `ambiguities.json` | Ambiguous or incomplete points |

## Freshness Check

The `source_hash` field enables quick freshness verification:

```bash
# If the hash hasn't changed, the digest is up-to-date
if [[ "$current_hash" == "$stored_hash" ]]; then
    echo "Digest up-to-date, skipping"
fi
```

This prevents unnecessary regeneration when the spec hasn't changed.

## Ambiguity Triage

Digest generation automatically identifies ambiguous points in the specification. These are handled through the **triage** process.

### Triage Generation

The system generates a `triage.md` file that lists ambiguous points and offers decision options:

```markdown
## AMB-001: Unclear session handling

**Context**: The spec mentions "session timeout" but doesn't define the value.

**Options**:
- [ ] A: 30 minutes (web standard)
- [ ] B: 60 minutes (longer session)
- [ ] C: Configurable (runtime setting)

**Decision**: ___
```

### Human Decision

A human (or the sentinel) fills in the triage file. The decision is written back to `ambiguities.json`, and the planner takes it into account during decomposition.

### Automatic Triage Merging

The `merge_triage_to_ambiguities()` and `merge_planner_resolutions()` functions ensure that:

- Human decisions are incorporated into the digest
- Planner-made decisions are also preserved
- In case of conflict, the human decision wins

\begin{keypoint}
The triage gate is the only point where the orchestrator stops and asks for human intervention. Every other decision is made autonomously. If there are no ambiguous points, the triage step is automatically skipped.
\end{keypoint}

## Requirement Coverage

The digest enables requirement coverage tracking throughout the entire pipeline:

```bash
wt-orchestrate coverage
```

Output:

```
Requirement Coverage: 12/15 (80%)
  ✓ REQ-001: JWT authentication      → change/auth-system (merged)
  ✓ REQ-002: User profile            → change/user-profile (running)
  ✗ REQ-003: Admin panel             → (not assigned)
  ...
```

The `update_coverage_status()` function automatically updates coverage when a change's status changes (merged, failed, etc.).
