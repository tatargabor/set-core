# Design: learnings-to-rules

## Context

The learnings-web-pipeline change established capture and display of orchestration learnings. This change closes the remaining loop: converting recurring patterns into actionable rules. The existing `/set:harvest` skill extracts rules from source project files (human-written code), but nothing extracts rules from orchestration experience (machine-observed patterns). The two skills are complementary — harvest reads code, learn reads run history.

Key existing infrastructure:
- `review-findings.jsonl` — structured JSONL with per-issue severity, file, line, fix
- `_persist_run_learnings()` — saves recurring patterns to memory at run end
- `generate_review_findings_summary()` — deduplication and pattern counting
- Profile `rule_keyword_mapping()` — keyword → glob mapping for rule injection at dispatch
- `deploy.sh` — copies core rules with `set-` prefix to consumer projects

## Goals / Non-Goals

**Goals:**
- Extract actionable rule candidates from review findings patterns
- Classify candidates by scope (core/plugin/project-local)
- Provide both CLI skill (`/set:learn`) and web UI for review and approval
- Write approved rules in the correct format and location
- Prevent re-suggestion of dismissed rules

**Non-Goals:**
- LLM-based rule text generation (template-based is sufficient and deterministic)
- Auto-deploying rules without user confirmation
- Modifying or merging with existing rules (creates new files only)
- Real-time rule generation during orchestration (post-run analysis only)

## Decisions

### D1: Template-based rule generation, not LLM

Rule text is generated from templates filled with pattern data (severity, description, file patterns, fix guidance). No LLM call needed — the review findings already contain structured issue descriptions and fix suggestions.

**Why:** Deterministic, fast, no API cost. The review gate already used an LLM to analyze the code — we're just reformatting its structured output.

**Template structure:**
```markdown
---
globs:
  - "{extracted_file_patterns}"
---
# {title}

{description}

## Guidelines

{bullet_points_from_issues}

## Common Mistakes

{examples_from_findings}
```

### D2: Analyzer is a Python module, not a standalone CLI

`learnings_analyzer.py` lives in `lib/set_orch/` alongside the other orchestration modules. It's called by both the API endpoint and the skill.

**Why:** Shares imports with the rest of the orchestration system (state, memory, profile). A standalone CLI would duplicate dependency resolution.

### D3: Rule candidates stored as JSON file, not in memory

Candidates are written to `set/orchestration/rule-candidates.json` after analysis. The web UI reads them via API. Accepted/dismissed status is tracked in this file.

**Why:** Memory is good for cross-run recall but not for structured state with accept/dismiss workflows. A JSON file is simpler, inspectable, and doesn't pollute the memory system.

### D4: Classification uses keyword heuristics + profile

Classification works in two steps:
1. **Keyword heuristics** — if the pattern references React, Next.js, API routes, CSS → "web". If generic coding (imports, null checks, types) → "core". If references specific files/entities → "project".
2. **Profile override** — if a profile plugin is loaded, `profile.classify_learning_pattern(pattern)` can override the heuristic.

**Why:** Simple heuristics cover 90% of cases. Profile override handles edge cases per project type. No LLM needed.

### D5: Dismissed rules tracked by normalized pattern slug in memory

When a user dismisses a candidate, a memory entry is saved: `type: "Decision", tags: "dismissed-rule,slug:<normalized-slug>"`. Future runs check memory before presenting candidates.

**Why:** Memory survives across sessions and runs. The slug normalization (strip severity, lowercase, first 50 chars) matches the pattern normalization used in `generate_review_findings_summary()`.

### D6: `/set:learn` skill follows the harvest skill pattern

The skill reads findings, calls the analyzer, presents candidates, and gets user approval — same interaction pattern as `/set:harvest` but with a different data source.

**Why:** Consistent UX. Users familiar with harvest understand learn immediately.

### D7: Web UI accept/dismiss is fire-and-forget

The web endpoint writes the rule file immediately on accept and saves dismissal to memory. No staged/pending state — the action is immediate.

**Why:** Rules are additive. Writing a new rule file has low blast radius. If the user regrets, they can delete the file.

## Risks / Trade-offs

- **[Risk] Generated rules may be too generic or too specific** → Mitigation: User must approve every rule. Confidence scoring helps prioritize. Dismissed rules are not re-suggested.
- **[Risk] File pattern extraction may be wrong** → Mitigation: Globs in frontmatter are based on actual file paths from findings. User can edit before accepting.
- **[Risk] Plugin template repo may not be accessible** → Mitigation: If plugin template directory is not writable, fall back to project-local deployment with a note.

## Open Questions

- Should the skill also read build/test failure patterns (not just review findings)? Deferred — start with review findings which have the richest structured data.
