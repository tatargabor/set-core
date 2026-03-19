## Context

The wt-hook-memory Stop handler currently uses Claude Haiku LLM to extract 5-9 curated insights from session transcripts. This involves preprocessing to last 80 entries, a 2-5s LLM call, staging files with debounce, and commit-on-next-session logic. The PreToolUse hook fires memory recall on all 6 tool types (~50 calls/session), and PostToolUse saves noisy "Modified FILE" memories while also doing proactive recall on all 6 tools.

The explore session established that shodh-memory stores raw text as-is (no summarization, no chunking) with 384-dim sentence embeddings and BM25 keyword index. The key insight: if we save raw conversation turns, recall quality depends entirely on the embedding specificity of each turn.

## Goals / Non-Goals

**Goals:**
- Replace Haiku LLM extraction with zero-cost rule-based raw filter (<100ms vs 2-5s)
- Save ALL meaningful conversation turns (not just last 80) — nothing valuable lost
- Tag raw memories with `raw` so recall hooks can exclude them from injection
- Remove PreToolUse memory recall entirely (PostToolUse timing is better)
- Remove PostToolUse "Modified FILE" saves (noise) and proactive recall
- Keep PostToolUse only for Read + Bash (where file/command context helps most)
- Reduce per-session hook overhead by ~60-70%

**Non-Goals:**
- Changing the recall/injection side (L1 SessionStart, L2 UserPromptSubmit) — those stay as-is
- Adding consolidation/decay for raw memories (future work)
- Changing PostToolUseFailure behavior (it's valuable as-is)
- Modifying SubagentStop behavior
- Adding `--exclude-tags raw` to recall hooks (future optimization if noise becomes problem)

## Decisions

### D1: Rule-based filter instead of LLM

**Choice:** Bash regex/word-count filter instead of Haiku LLM.

**Alternatives considered:**
- Keep Haiku but improve prompt → Still costs money, still loses early turns, still 2-5s
- Use shodh-memory's internal importance scoring → Too coarse (length+type heuristic only)
- No filter, save everything → Too noisy (~50 turns/session including "yes", "ok", tool calls)

**Rationale:** The filter needs to be fast (<100ms), deterministic, and run in background. Rule-based is the only option that meets all three. The rules are conservative — they remove obviously useless turns, not borderline ones.

### D2: Filter rules

The filter SHALL discard:
- System-reminder entries (hook injections, not real conversation)
- User turns < 15 characters (trivial: "yes", "ok", "done", "thanks")
- Assistant turns < 50 characters (trivial acknowledgments)
- Consecutive tool-call-only assistant turns with no text (pure tool use, no insight)
- Repeated file reads (same file path appearing 3+ times)

The filter SHALL keep:
- All user questions/instructions (>= 15 chars)
- Assistant explanations and decisions (>= 50 chars)
- Error messages and their fixes (regardless of length)
- Bash commands that produced output (context for what happened)

### D3: Context prefix on each saved turn

Each raw memory gets a prefix: `[session:<change-name>, turn <N>/<total>]`

This improves embedding specificity — the prefix adds searchable keywords (change name, session context) that help semantic search differentiate between similar turns from different sessions.

### D4: Tag strategy

All raw memories get tags: `raw,phase:auto-extract,source:hook,change:<name>`

Recall hooks can later add `--exclude-tags raw` if noise becomes a problem. For now, raw memories participate in recall normally — the relevance threshold (0.3) should filter most low-quality matches.

### D5: Remove PreToolUse memory recall

PreToolUse injects context BEFORE the tool result arrives. By the time the agent processes the result and thinks about next steps, the pre-tool context is stale. PostToolUse timing is strictly better — context arrives WITH the result.

The activity-track.sh hook on Skill matcher stays (it writes to activity.json, unrelated to memory).

### D6: PostToolUse simplified to Read + Bash only

**Why Read:** After reading a file, the agent decides what to do with it. Memory about that file is most useful here.

**Why Bash:** After running a command, error patterns and past fixes are most useful.

**Why NOT Edit/Write:** The agent already knows what it wrote. Memory about the file was useful BEFORE writing (covered by L2 UserPromptSubmit recall). The "Modified FILE" saves are pure noise.

**Why NOT Task/Grep:** Grep results speak for themselves. Task prompts are too generic for useful memory matching.

### D7: No staging/debounce needed

Without Haiku LLM, there's no expensive operation to debounce. Raw filter runs in <100ms. Each Stop event saves directly to set-memory (no staging files, no .ts timestamps, no commit-on-next-session). Simplifies the code significantly — the entire `_stop_commit_staged()` and staging file management is removed.

### D8: Background execution preserved

The raw filter still runs as a disowned background process (same as current Haiku extraction). Even though it's fast, we don't want to block session exit. The synchronous Stop handler still does metrics flush and dedup cache cleanup.

## Risks / Trade-offs

**[Higher memory volume]** → ~15-25 raw memories/session vs 5-9 curated. Mitigated by `raw` tag for future filtering and relevance threshold in recall.

**[Less curated results]** → Raw turns are verbose, not summarized. Mitigated by context prefix improving search quality, and the fact that LLM extraction was lossy anyway (only last 80 entries).

**[Embedding quality for raw turns]** → Short or generic turns ("I fixed the bug") produce low-specificity embeddings. Mitigated by word-count filter removing the shortest turns, and context prefix adding discriminating keywords.

**[No rollback for staging removal]** → Old staged files from previous sessions won't be committed after upgrade. Mitigated by committing all existing staged files as part of the upgrade (one-time migration in the new code).

**[PostToolUse reduced scope]** → Edit/Write/Task/Grep lose post-tool memory injection. Risk is low — benchmark data showed Pre/PostToolUse had lowest value among all layers. UserPromptSubmit (L2) covers intent-level recall.
