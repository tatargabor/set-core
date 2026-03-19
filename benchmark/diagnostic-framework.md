# Diagnostic Framework — Memory Gap Analysis

## Purpose

Beyond measuring "did memory help?", this framework identifies **where memory failed to help and why**. Each gap instance provides actionable insights for improving the memory system.

## Gap Categories

### 1. Missed Recall Opportunity

**Definition**: Relevant memory existed in the store, but the agent didn't recall it (or recalled with wrong query/tags).

**Detection**: Compare Run B's memory store contents at the time of each change with the actual recall queries. If a memory existed that would have been useful but wasn't recalled, this is a missed recall.

**Documentation template**:
```
- Change: C<N>
- Gap: Missed recall
- Memory that existed: "<memory content summary>"
- Memory ID: <id>
- What agent should have queried: "<suggested query>"
- What agent actually queried: "<actual query>" (or "no recall attempted")
- Impact: <what went wrong because of the miss>
- Suggested fix: <how to improve recall relevance or prompt recall at right time>
```

**Common causes**:
- Agent didn't run recall at all (missing recall prompt in workflow)
- Query terms didn't match the memory's content (semantic gap)
- Tags didn't match (filtering too strict)
- Memory was saved with vague content (can't match semantically)

### 2. Low-Quality Save

**Definition**: Memory was saved, but its content was too vague, too long, or too specific to be useful when recalled later.

**Detection**: Review all `set-memory remember` invocations in Run B's transcript. Check if the saved content would actually help in the change where it was later needed.

**Documentation template**:
```
- Change where saved: C<N>
- Memory content: "<what was saved>"
- Change where needed: C<M>
- Why it was low quality: <vague | too long | too specific | wrong type>
- Better version: "<what should have been saved>"
- Suggested fix: <how to improve save quality — better prompts, examples, etc.>
```

**Quality criteria**:
- **Good**: Specific, actionable, includes the "why" — e.g., "SQLite needs WAL mode for concurrent writes. Without it, SQLITE_BUSY errors occur on simultaneous cart operations. Fix: add `PRAGMA journal_mode=WAL` in Prisma client setup."
- **Medium**: Correct but vague — e.g., "Had SQLite issues, needed to change a setting"
- **Poor**: Too specific to reproduce or too generic to act on — e.g., "Fixed a bug" or full error stack trace without explanation

### 3. Missing Memory Type

**Definition**: An event occurred that should have triggered a memory save, but the agent didn't save anything.

**Detection**: Compare Run B's behavior with the trap documentation. For each trap the agent encountered, check if a memory was saved. If the agent hit T2.1 (SQLITE_BUSY) and fixed it but didn't save the learning, this is a missing save.

**Documentation template**:
```
- Change: C<N>
- Event: <what happened that was worth saving>
- Trap: T<N.M> (if applicable)
- Expected save type: <Learning | Decision | Context>
- Expected content: "<what should have been saved>"
- Why it wasn't saved: <agent didn't recognize it | save step skipped | health check failed>
- Suggested fix: <how to improve save triggering — better prompts, automatic detection, etc.>
```

**Common causes**:
- Agent didn't recognize the event as save-worthy
- Agent was in "implementation mode" and skipped reflection
- The error was fixed quickly and the agent moved on without saving
- The save step in the skill was skipped or not reached

### 4. Timing Issue

**Definition**: Memory was saved, but too late to help the current or next change.

**Detection**: Check the timestamp of each memory save against when it was needed. If the agent saved "variants must be a separate table" at the end of C2 (after reworking) but needed it at the start of C2, the timing was wrong.

**Documentation template**:
```
- Change where needed: C<N>
- Memory saved in: C<M> (same or later change)
- Save timestamp vs need timestamp: <saved at iteration X, needed at iteration Y>
- Impact: <agent had to rediscover/rework because save was too late>
- Suggested fix: <how to trigger earlier saves — save on error, not just on reflection>
```

**Common patterns**:
- "Save at session end" misses same-session needs
- Agent saves after debugging is complete, not when the error first occurs
- The "Discover → Save → Tell" ordering wasn't followed

### 5. Recall Relevance Problem

**Definition**: Agent recalled memories, but the results were irrelevant or misleading.

**Detection**: Review recall results in the transcript. If the agent recalled 5 memories but none were relevant to the current task (or worse, led to a wrong approach), this is a relevance problem.

**Documentation template**:
```
- Change: C<N>
- Query: "<recall query>"
- Results returned: <count> memories
- Relevant results: <count>
- Irrelevant results that caused confusion: "<memory content>"
- Impact: <agent wasted time or made wrong decision based on irrelevant recall>
- Suggested fix: <better query strategy, improved ranking, tag filtering>
```

## Analysis Process

### Step 1: Build the memory event timeline

For Run B, extract all memory events from `ralph-loop.log`:
1. All `set-memory recall` calls (query, results, change context)
2. All `set-memory remember` calls (content, type, tags, change context)
3. Order by timestamp

### Step 2: Map traps to memory interactions

For each trap (T1.1 through T6.3):
1. Did the agent encounter this trap? (Check transcript)
2. If yes, was relevant memory available? (Check memory store at that point)
3. If memory was available, was it recalled? (Check recall log)
4. If recalled, did it help? (Check agent behavior after recall)
5. If not recalled or not available, classify the gap

### Step 3: Score each gap

| Severity | Description |
|----------|-------------|
| Critical | Gap directly caused a dead end or design rework |
| Moderate | Gap caused repeated work but agent eventually recovered |
| Minor | Gap caused slight inefficiency but no major impact |

### Step 4: Generate improvement recommendations

Group gaps by category and generate specific, actionable recommendations:

```
## Recommendation: <title>

**Gap category**: <category>
**Occurrences**: <count across all changes>
**Severity**: <Critical | Moderate | Minor>

**Problem**: <description of what went wrong>

**Suggested improvement**: <specific change to memory system, prompts, or workflow>

**Expected impact**: <what would change if this improvement were implemented>
```

## Summary Table

After completing the analysis, fill in this summary:

| Category | Count | Critical | Moderate | Minor |
|----------|-------|----------|----------|-------|
| Missed recall | | | | |
| Low-quality save | | | | |
| Missing memory type | | | | |
| Timing issue | | | | |
| Recall relevance | | | | |
| **Total** | | | | |
