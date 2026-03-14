## Context

The wt-tools memory system (shodh-memory) injects recalled memories into agent sessions via hooks (L1-L5). During CraftBrew E2E orchestration (471 sessions, 76 explicit citations), analysis revealed a specific failure mode:

1. Agent correctly identifies a "false positive" pattern in worktree A (user-auth review only checked diff, not filesystem)
2. Memory saves this as a general pattern
3. Next verify on different worktree/branch — memory suggests "same pattern, skip check"
4. Agent shortcuts filesystem verification based on memory alone
5. 6 out of 76 citations were misleading, all from this `review-false-positive` chain

**Key insight**: Deterministic memories (e.g., "prisma generate fixes fresh worktree") are 100% accurate across contexts. Heuristic memories (e.g., "this is a known false positive") are context-dependent and dangerous when generalized.

### Current architecture

```
Hook event → wt-memory recall/proactive → filter (score ≥ 0.3) → format with MEM#id → inject as system-reminder
Stop hook → extract transcript → wt-memory remember → tags: phase:auto-extract
```

No distinction exists between deterministic and heuristic memories at any layer.

## Goals / Non-Goals

**Goals:**
- Visually distinguish heuristic memories from deterministic ones during injection
- Tag heuristic memories as `volatile` for time-based decay in orchestration recall
- Enforce filesystem verification in verify skill regardless of memory suggestions
- Quarantine memories from failed verifications; promote memories from passed verifications
- Deploy safely to running projects with zero downtime (symlink-based hooks = immediate)

**Non-Goals:**
- Changing the core shodh-memory storage model (no schema changes)
- Adding a "confidence" field to the memory data model
- Per-worktree memory isolation (too invasive; tag-based filtering is sufficient)
- Modifying how memories are scored or ranked by the recall engine

## Decisions

### Decision 1: Heuristic detection via keyword matching in formatting layer

**Choice**: Detect heuristic content during `proactive_and_format()` (memory-ops.sh) using keyword patterns, NOT at remember-time.

**Rationale**: Formatting-time detection lets us mark ALL existing memories retroactively without re-tagging the database. The patterns are clear:
- `false positive`, `same pattern`, `known pattern`, `not the case`, `unlike previous`
- `was a false positive`, `same issue as`, `this is not a real`

**Alternative considered**: Tag at remember-time in stop.sh — rejected because existing memories in the database wouldn't get the tag, and the raw filter extraction happens in a background process where content classification would add latency.

**Implementation**: In the Python formatter block within `proactive_and_format()`, check content against heuristic patterns before emitting. If matched, prepend `⚠️ HEURISTIC: ` to the output line (after the `[MEM#xxxx]` prefix).

### Decision 2: `volatile` tag at extraction time (stop.sh)

**Choice**: Add `volatile` tag to memories whose content matches heuristic patterns during `_stop_raw_filter()`.

**Rationale**: New memories get tagged going forward. Combined with Decision 1 (display-time detection for existing memories), this provides both retroactive and proactive coverage.

**Implementation**: In the Python block that calls `wt-memory remember`, check content for the same heuristic patterns and append `,volatile` to the tags string.

### Decision 3: Volatile decay in orch_recall() — 24h window

**Choice**: Filter out memories tagged `volatile` that are older than 24 hours in `orch_recall()` (orch-memory.sh).

**Rationale**: Heuristic memories are useful within their immediate context (same orchestration run, ~4h) but dangerous when carried across runs. 24h is generous enough to cover long runs, short enough to prevent cross-run contamination.

**Implementation**: Extend the existing jq filter in `orch_recall()` line 30 to check `volatile` tag + `created_at` timestamp.

**Alternative considered**: Hard-filter all volatile memories — rejected because within the same run they may be genuinely useful (e.g., "this change's review was a false positive" is correct for THAT change).

### Decision 4: "Memory suggests, never concludes" — verify skill rule

**Choice**: Add an explicit rule section to the verify SKILL.md that forbids using memory as a substitute for filesystem checks.

**Rationale**: The skill instructions are the most direct way to influence agent behavior during verification. Claude reads SKILL.md on every `/opsx:verify` invocation. This is the single most effective defense — it alone would have prevented all 6 misleading citations.

**Implementation**: Add a `## Memory Safety Rule` section after the existing "Verification Heuristics" section (line ~152). Also add a one-line reminder in CLAUDE.md template.

### Decision 5: Safety prompt injection in verifier.sh

**Choice**: Modify the verify prompt in `verifier.sh:1327` to include an explicit memory-safety instruction.

**Rationale**: Belt-and-suspenders with Decision 4. The SKILL.md rule covers interactive verify calls; the verifier.sh prompt covers automated orchestration verify calls. Both paths need protection.

**Implementation**: Change the echo string from `"Run /opsx:verify $change_name"` to include a one-line safety reminder.

### Decision 6: Quarantine on failure, promote on success

**Choice**: After verify gate outcome, save a counter-memory (failure) or promotion-memory (success) via `orch_remember()`.

**Rationale**: Creates a self-correcting feedback loop. If "false positive" memory caused a wrong PASS, the next verify failure creates a quarantine memory that warns future agents. If verify genuinely passes, the promotion memory reinforces correct behavior.

**Implementation**: Add `orch_remember()` calls in verifier.sh at the PASS branch (line ~1337) and FAIL branch (line ~1360).

## Risks / Trade-offs

**[Risk] Heuristic keyword false positives** — A legitimate memory containing "false positive" gets marked as heuristic when it shouldn't.
→ Mitigation: The `⚠️ HEURISTIC` prefix is informational only — the memory is still shown, just marked. Agent can still use it if filesystem confirms. No data is lost.

**[Risk] 24h volatile decay too aggressive** — Useful heuristic memories expire during a long orchestration run.
→ Mitigation: 24h is generous for typical runs (2-6h). The decay only affects `orch_recall()`, not the hook-level `proactive_and_format()` which still shows volatile memories with the HEURISTIC prefix.

**[Risk] SKILL.md hot-patch may be overwritten** — If `openspec update --force` or `wt-project init` runs on a consumer project, the SKILL.md gets replaced from source.
→ Mitigation: The change modifies the SOURCE SKILL.md in wt-tools, so wt-project init deploys the new version. openspec update only regenerates from npm templates, which don't include our custom sections.

**[Risk] Quarantine memories accumulate** — Many verify failures could flood memory with quarantine warnings.
→ Mitigation: Quarantine memories are tagged `phase:verify-failed,volatile` — they auto-decay via the same 24h volatile filter. The existing dedup system also prevents identical content.
