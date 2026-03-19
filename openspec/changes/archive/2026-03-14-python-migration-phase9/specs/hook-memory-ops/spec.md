## Purpose

Migrate `lib/hooks/memory-ops.sh` (393 LOC) to `lib/set_hooks/memory_ops.py`. Memory recall, proactive context retrieval, rules.yaml matching, and output formatting with dedup.

## Requirements

### MEMOPS-01: Memory Recall
- `recall_memories(query, limit, tags)` calls `set-memory recall` CLI
- Parse JSON response into `Memory` dataclasses
- Apply dedup filter: skip memories already surfaced this session
- Return sorted by relevance score

### MEMOPS-02: Proactive Context
- `proactive_context(context_str, limit)` calls `set-memory proactive` CLI
- Higher quality retrieval than basic recall — includes relevance scores
- Used by SessionStart and UserPromptSubmit handlers

### MEMOPS-03: Rules Matching
- `load_matching_rules(prompt_text)` reads `.claude/rules.yaml`
- Match prompt against rule patterns (glob or regex)
- Return list of matching rule contents for context injection

### MEMOPS-04: Output Formatting
- `format_memory_output(memories, header)` produces the injected context block
- Format: `=== <HEADER> ===\n  - [MEM#<id>] <content>`
- Truncate long memories (max 300 chars per entry)
- Track surfaced memory IDs for dedup (via session cache)

### MEMOPS-05: Context ID Tracking
- `_LAST_CONTEXT_IDS` global for metrics — which memories were shown
- Used by callers for citation tracking

### MEMOPS-06: Unit Tests
- Test recall with mock set-memory output
- Test dedup filtering across multiple calls
- Test rules matching with mock rules.yaml
- Test output formatting truncation
