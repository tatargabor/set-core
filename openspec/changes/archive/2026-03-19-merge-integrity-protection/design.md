# Design: Merge Integrity Protection

## Context

The `wt-merge` script handles merge conflict resolution through a multi-layer pipeline: generated files (pattern match), package.json (jq deep merge), JSON files (jq deep merge), and finally LLM resolution for everything else. The LLM resolver receives only raw conflict hunks with no context about file semantics, and there is no post-merge validation. This design adds two verification layers and file-type awareness.

Current merge flow in `wt-merge`:
```
git merge → conflict?
  → auto_resolve_generated_files()   ← pattern match, checkout --ours
  → auto_resolve_package_json()      ← jq deep merge
  → auto_resolve_json_files()        ← jq deep merge
  → llm_resolve_conflicts()          ← NO context, NO validation
  → git commit                       ← NO conservation check
```

New merge flow:
```
git merge → conflict?
  → auto_resolve_generated_files()   ← unchanged
  → auto_resolve_package_json()      ← unchanged
  → auto_resolve_json_files()        ← unchanged
  → load_merge_strategies()          ← NEW: read config
  → llm_resolve_conflicts()          ← ENRICHED: strategy hints per file
  → run_conservation_checks()        ← NEW: verify additions preserved
  → run_entity_checks()              ← NEW: for "additive" strategy files
  → run_validation_commands()        ← NEW: for files with validate_command
  → git commit                       ← only if ALL checks pass
```

## Goals / Non-Goals

**Goals:**
- Block merges where LLM resolution loses content from either side
- Provide file-type context to the LLM so it makes better merge decisions
- Support project-specific and profile-provided merge rules
- Keep the fix in `wt-merge` (bash) — not in Python orchestrator code
- Provide `--no-conservation-check` escape hatch for emergency bypass

**Non-Goals:**
- AST-level parsing of source files (too complex, language-specific)
- Replacing the LLM resolver with a deterministic merger
- Handling non-conflicted file issues (that's the verify gate's job)
- Replacing existing JSON/lockfile handling (those already work, run before LLM)

## Decisions

### D1: Conservation check lives in wt-merge, not merger.py

The conservation check runs inside `wt-merge` after `llm_resolve_conflicts()` and before `git commit --no-edit`. This keeps all merge logic in one place (the bash script) and means both orchestrated and manual `wt-merge` calls get protection.

**Critical implementation detail:** The check runs BEFORE `git commit --no-edit` (line ~830 in current wt-merge). The LLM has resolved files and `git add`-ed them, but the merge commit is not yet created. On failure, use `git reset --merge` to abort the in-progress merge.

**Alternative considered:** Post-merge check in Python `merger.py`. Rejected because: (a) manual wt-merge calls wouldn't be protected, (b) by the time merger.py runs, the commit is already on main.

### D2: Line-content matching, not line-number matching

The conservation check compares line content (trimmed whitespace) not positions. The LLM may reorder lines, add blank lines, or change indentation — that's fine. What matters is: are the semantically meaningful additions from both sides present?

**Implementation:** Convert additions to a set of trimmed non-blank lines. Check set inclusion.

### D3: Strategy config in project-knowledge.yaml, parsed via Python

Merge strategies are declared alongside other project knowledge (test commands, cross-cutting files) in the same file the orchestrator already reads. `wt-merge` is bash but YAML parsing is not feasible in pure bash. The config is parsed via `python3 -c "import yaml; ..."` — the project already depends on Python and the `pyyaml` package.

**Format:**
```yaml
merge_strategies:
  - name: schema
    patterns: ["prisma/schema.prisma", "*.prisma"]
    strategy: additive
    entity_pattern: "^model |^enum "
    validate_command: "npx prisma validate"
    llm_hint: "Database schema. NEVER remove models or fields. Keep ALL from both sides."
  - name: registry
    patterns: ["src/middleware.ts", "src/index.ts"]
    strategy: additive
    entity_pattern: "^export "
    llm_hint: "Registry/config file. Keep ALL entries from both sides."
```

**Only two strategy types:** `additive` (entity counting + conservation + validation) and `llm_with_conservation` (conservation only, default). JSON deep merge and lockfile regeneration are already handled by the existing pre-LLM pipeline and are NOT duplicated here.

### D4: Two-layer protection (specific + generic)

Layer 1 (file-type strategy): For files matching a configured pattern — entity counting, validation commands, enriched LLM prompts. Provides the strongest protection for known critical files.

Layer 2 (generic conservation): For ALL LLM-resolved files, including those without a specific strategy. Checks that additions from both sides are preserved. This is the universal safety net.

Both layers run. A file can pass entity counting but fail conservation (e.g., a comment was lost). Both must pass for the merge to proceed.

### D5: LLM-resolved file tracking

`llm_resolve_conflicts()` currently writes resolved files and calls `git add` but does not return which files it resolved. The function SHALL populate a bash array `LLM_RESOLVED_FILES` (or write to a temp file) that is consumed by `run_conservation_checks()`.

### D6: Strategy config is read by wt-merge at merge time

`wt-merge` reads `project-knowledge.yaml` directly (it's in the project root). No need to pass config through the orchestrator — the merge script is already running in the project directory.

**Profile defaults:** The profile writes a `.set-core/.merge-strategies.json` file during `set-project init` (JSON format — parseable by both bash/jq and Python). `wt-merge` reads profile defaults first, project-knowledge.yaml overrides.

### D7: Agent rule is a static file, not a runtime check

The `db-type-safety.md` rule is deployed as a `.claude/rules/` file. This is the simplest path — it's picked up by Claude Code automatically, no verify gate changes needed. The verify gate's existing code review will naturally flag violations because the rule is in the agent's context.

### D8: Entity counting uses merge-base for additions

Entity count comparison is: `expected = base_count + ours_added + theirs_added`, where additions are counted relative to merge-base. This correctly handles the case where one side legitimately deletes an entity — the deletion is visible as a negative delta and doesn't falsely block.

## Risks / Trade-offs

- **[Risk] False positives on conservation check** — Legitimate refactoring during merge (renaming, restructuring) could trigger false blocks. → Mitigation: The check only runs on LLM-resolved files (not clean merges), uses content matching (not line-position), and `--no-conservation-check` provides an escape hatch.

- **[Risk] Strategy config maintenance burden** — Projects must declare their critical files. → Mitigation: Profiles supply sensible defaults (Prisma for web projects, models.py for Django, etc.). Most projects need zero config.

- **[Risk] Conservation check is O(lines²) for large files** — Set intersection on very large files could be slow. → Mitigation: Conflict files are typically <1000 lines. If performance is an issue, sample the first 500 added lines.

- **[Risk] LLM hint injection increases prompt size** — Adding strategy hints uses tokens. → Mitigation: Hints are 1-2 lines per file. Negligible compared to the conflict hunks themselves.

- **[Risk] `validate_command` is user-controlled shell execution** — project-knowledge.yaml is project-controlled, so this is intentional. Only project owners should edit this file.

## Open Questions

- Should conservation check have a threshold (e.g., allow 1-2 missing lines for trivial whitespace differences) or be strict (any missing line = block)? Starting strict, can relax if false positives are excessive.
