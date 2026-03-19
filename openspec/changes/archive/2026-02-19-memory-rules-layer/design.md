## Context

The set-core memory system has two injection paths in `wt-hook-memory`:
1. `cheat-sheet` tagged memories — loaded at L1 (session start) via `set-memory recall --tags cheat-sheet`
2. Semantic recall — L2 (UserPromptSubmit), L3 (PreToolUse) via `proactive_and_format()`

Both paths go through shodh-memory's relevance filtering. There is no guaranteed, deterministic injection path for operational constraints that MUST be surfaced. The gap: agents trial-and-error with credentials/gates rather than using the known-correct value immediately.

New file: `.claude/rules.yaml` — per-project, git-committable, no shodh-memory dependency.

## Goals / Non-Goals

**Goals:**
- Deterministic injection of operational rules when topic matches
- `set-memory rules` CLI for managing rules without hand-editing YAML
- Rules section appears BEFORE project memory in hook output (priority order)
- Zero shodh-memory dependency for the rules path
- Clarify cheat-sheet's role: soft conventions only

**Non-Goals:**
- Replacing semantic memory — rules are for explicit constraints, not emergent knowledge
- Per-agent or per-branch rules — project-scoped only
- GUI editor for rules (CLI only for now)
- Rule expiry or TTL

## Decisions

### D1: File format — YAML in `.claude/rules.yaml`

Chosen over: JSON (less readable), separate DB table (shodh-memory dependency), new shodh-memory type (needs library change).

`.claude/` is already the per-project config dir (settings.json, hot-topics.json). YAML is human-readable and git-diffable. Rules are explicit, deliberate — not emergent — so a file edited/committed by the team makes more sense than a DB record.

File location: `.claude/rules.yaml` (relative to project root via `git rev-parse --show-toplevel`).

### D2: Topic matching — keyword list, not embeddings

Rule has an explicit `topics: [customer, sql, credentials]` list. The hook does simple bash string matching against the user prompt text.

Chosen over: embedding similarity (adds latency, shodh-memory dependency, same non-determinism problem we're trying to solve).

Match logic: any rule whose topics array has ≥1 word appearing in the lowercased prompt text is injected. Fast, transparent, zero false negatives for known-critical terms.

### D3: Injection position — MANDATORY RULES section above PROJECT MEMORY

```
=== MANDATORY RULES ===
[rule-id] <content>
===========================

=== PROJECT MEMORY — ...
```

Visual separation + label contrast ("MANDATORY" vs "Past experience") signals to the agent that these are constraints, not suggestions. This is purely a formatting decision in the hook output — no schema changes.

### D4: `set-memory rules` subcommand in existing `set-memory` CLI

Adding to `bin/set-memory` (bash script) rather than a new binary. Keeps the CLI surface unified. Subcommands: `add`, `list`, `remove`.

`add` syntax:
```bash
set-memory rules add --topics "customer,sql" "Use customer_ro / XYZ123 for customer table"
```

`remove` takes the rule id (auto-generated slug from content prefix).

### D5: Cheat-sheet scope clarification — docs + L5 extraction prompt

The L5 haiku extraction prompt will be updated to explicitly NOT promote credential-like or hard-constraint-like content to cheat-sheet. Those belong in rules. The `cheat-sheet-curation` spec gets a MODIFIED requirement.

## Risks / Trade-offs

- **Topic list maintenance**: If user forgets to add relevant topics, rule won't fire. Mitigation: `set-memory rules add` CLI makes it low-friction; docs show examples.
- **Prompt text dependency**: Matching on the raw user prompt means "mi a customer tábla tartalma" (Hungarian) needs "customer" in topics list — not "ügyfél". Mitigation: users add terms in the language they actually use.
- **YAML parse failure**: If `.claude/rules.yaml` is malformed, hook should silently skip rules injection (graceful degrade). Hard fail would break the entire hook.
- **Rules vs cheat-sheet confusion**: Two mechanisms for "important things to remember." Mitigation: clear docs and CLI help text distinguishing the two.

## Migration Plan

1. Hook reads `.claude/rules.yaml` if present; skips silently if absent or malformed
2. No migration needed for existing memories
3. Users adopt rules gradually via `set-memory rules add`
4. Existing cheat-sheet entries remain valid — no removal, just scope guidance in docs

## Open Questions

- Should `.claude/rules.yaml` be gitignored by default or committed? (Proposal: committed — rules are team knowledge, not secrets. Credentials in rules should be a placeholder pointing to a secrets manager, not the actual secret.)
- Should rules support a `severity` field (warning vs hard-block)? (For now: all rules are equally "mandatory" — YAGNI.)
