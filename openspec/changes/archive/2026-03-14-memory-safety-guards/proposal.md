## Why

Agent memory (shodh-memory) provides significant value during orchestration — 90.8% of citations are helpful (fresh-worktree fixes, state recall, build fixes). However, analysis of CraftBrew E2E logs revealed that **heuristic memories** (e.g., "review was false positive") create a confirmation bias chain: one correct observation generalizes into a shortcut that skips filesystem verification. 6 out of 76 citations (7.9%) were misleading, all from the same `review-false-positive` pattern. This caused the verify skill to skip actual file-existence checks based on memory alone, accepting unimplemented features as "false positives."

The fix must be surgical — protect against heuristic memory misuse without degrading the 90.8% helpful citation rate.

## What Changes

- Add `⚠️ HEURISTIC` visual prefix when injecting memories that contain heuristic/pattern-matching language (e.g., "false positive", "same pattern as before")
- Tag heuristic memories as `volatile` during stop-hook extraction, enabling time-based decay in orchestration recall
- Add "Memory suggests, never concludes" safety rule to the verify skill — memory can propose a hypothesis but filesystem verification is always required
- Inject safety prompt in verifier.sh before Claude verify invocation — explicit instruction that memory cannot replace filesystem checks
- Add verify-failure quarantine: when verify fails, save a counter-memory warning; when verify passes, save a promotion memory
- Filter volatile memories with 24h decay in `orch_recall()` to prevent stale heuristics from propagating across orchestration phases

## Capabilities

### New Capabilities
- `memory-heuristic-guard`: Detection, tagging, visual marking, and decay of heuristic/volatile memories during injection and orchestration recall

### Modified Capabilities
- `verify-gate`: Add memory safety rule to verify skill, safety prompt injection in verifier.sh, quarantine/promote memories on verify outcome

## Impact

- `lib/hooks/memory-ops.sh` — heuristic detection + `⚠️ HEURISTIC` prefix in proactive_and_format()
- `lib/hooks/stop.sh` — `volatile` tag for heuristic content in raw filter extraction
- `lib/orchestration/orch-memory.sh` — volatile decay filter in orch_recall()
- `lib/orchestration/verifier.sh` — safety prompt injection + quarantine/promote memories
- `.claude/skills/openspec-verify-change/SKILL.md` — "Memory suggests, never concludes" rule
- `CLAUDE.md` template — Memory Safety During Verification section
- **Deploy impact**: memory-ops.sh and stop.sh changes are immediate (symlink); SKILL.md requires set-project init or hot-patch copy; verifier.sh takes effect on next verify call (bash source, no cache)
