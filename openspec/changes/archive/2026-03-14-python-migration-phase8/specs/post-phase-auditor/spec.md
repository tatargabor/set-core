## Purpose

Migrate `lib/orchestration/auditor.sh` (298 LOC) to `lib/wt_orch/auditor.py`. The auditor runs post-phase LLM analysis comparing merged changes against spec requirements to detect implementation gaps.

## Requirements

### AUDIT-01: Audit Prompt Construction
- `build_audit_prompt(state, cycle)` collects merged changes with scopes and file lists
- Include spec/digest content for comparison
- Include per-change scope descriptions and modified file paths (max 50 files per change)
- Output: structured JSON for template rendering

### AUDIT-02: Audit Execution
- `run_audit(prompt, model)` calls Claude CLI in print mode
- Parse structured response: `{gaps: [], recommendations: [], coverage_score: float}`
- Handle API errors with retry
- Emit `audit_complete` event with results

### AUDIT-03: Audit Result Parsing
- `parse_audit_result(response)` extracts structured findings
- Each gap: `{requirement_id, description, severity, suggested_fix}`
- Severity levels: critical, warning, info
- Critical gaps block phase completion; warnings are advisory

### AUDIT-04: CLI Subcommands
- `wt-orch-core audit run [--cycle <n>]` — run post-phase audit
- `wt-orch-core audit prompt [--cycle <n>]` — print audit prompt without executing
- Registered in `cli.py` under `audit` group

### AUDIT-05: Unit Tests
- Test prompt construction with mock state (multiple merged changes)
- Test result parsing with various response formats
- Test gap severity classification
