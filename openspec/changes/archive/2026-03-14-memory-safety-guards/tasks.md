## 1. Heuristic Detection at Display Time (memory-ops.sh)

- [x] 1.1 Add heuristic pattern list as a Python constant in the `proactive_and_format()` formatter block (memory-ops.sh ~line 89)
- [x] 1.2 Add content check against heuristic patterns before emitting each memory line
- [x] 1.3 Prepend `⚠️ HEURISTIC: ` after `[MEM#xxxx]` prefix for matching memories
- [x] 1.4 Verify non-matching memories are emitted unchanged

## 2. Volatile Tag at Extraction Time (stop.sh)

- [x] 2.1 Add heuristic pattern detection in the `_stop_raw_filter()` Python block (stop.sh ~line 190)
- [x] 2.2 Append `,volatile` to the tags string when content matches heuristic patterns
- [x] 2.3 Verify non-heuristic content does not get the volatile tag

## 3. Volatile Decay in Orchestration Recall (orch-memory.sh)

- [x] 3.1 Extend the jq filter in `orch_recall()` (orch-memory.sh line 30) to exclude volatile memories older than 24h
- [x] 3.2 Ensure non-volatile memories and recent volatile memories pass through unchanged
- [x] 3.3 Ensure existing `stale:true` filter still takes precedence

## 4. Verify Skill Memory Safety Rule (SKILL.md)

- [x] 4.1 Add `## Memory Safety Rule` section to `.claude/skills/openspec-verify-change/SKILL.md` after the "Verification Heuristics" section (~line 152)
- [x] 4.2 Include explicit instructions: memory can suggest hypothesis, filesystem is the verdict
- [x] 4.3 Add note that memory is not branch/worktree-aware

## 5. Verifier Safety Prompt Injection (verifier.sh)

- [x] 5.1 Modify the verify prompt at `verifier.sh:1327` to include memory-safety instruction
- [x] 5.2 Keep the prompt concise (one-line addition, not a paragraph)

## 6. Verify Outcome Memory Feedback (verifier.sh)

- [x] 6.1 Add `orch_remember()` call on VERIFY_RESULT: PASS (verifier.sh ~line 1337) with tags `phase:verified,change:<name>`
- [x] 6.2 Add `orch_remember()` call on verify failure (verifier.sh ~line 1360) with tags `phase:verify-failed,change:<name>,volatile`
- [x] 6.3 Verify quarantine memories include the `volatile` tag for decay

## 7. CLAUDE.md Memory Safety Section

- [x] 7.1 Add "Memory Safety During Verification" subsection under the Persistent Memory section in CLAUDE.md
- [x] 7.2 Keep it to 3-4 lines: memory is hypothesis, filesystem is verdict, never skip checks

## 8. Validation

- [x] 8.1 Test heuristic detection: recall a memory with "false positive" content, verify `⚠️ HEURISTIC` prefix appears
- [x] 8.2 Test volatile tag: save a memory via stop hook with heuristic content, verify `volatile` tag present
- [x] 8.3 Test orch_recall decay: verify volatile memories older than 24h are filtered
- [x] 8.4 Test verify skill: run `/opsx:verify` on a known change, verify filesystem checks happen
- [x] 8.5 Hot-patch verify: copy updated SKILL.md to active consumer projects (`/tmp/craftbrew-e2e/`, `/tmp/minishop-run11/`)
