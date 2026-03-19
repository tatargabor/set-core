## Context

The benchmark system (CraftBazaar, 12 changes, A/B comparison) runs two autonomous Claude agents with/without persistent memory. The v6 results showed no memory advantage; post-run investigation blamed weak tests (now fixed) and missing injection quality metrics.

The metrics system (`lib/metrics.py`, `wt-hook-memory` metrics appendage) was added post-v6. It collects per-hook injection data (query, result count, relevance scores, duration, token estimate, dedup hits) into a session cache file, then flushes to SQLite on Stop. It also scans transcripts for citation patterns. But the benchmark init scripts don't enable it.

## Goals / Non-Goals

**Goals:**
- Enable metrics collection during benchmark runs so injection quality can be measured alongside trap/test scores
- Update documentation to reflect current state (test fixes done, metrics available)
- Strengthen recall-verify guidance in with-memory.md based on v6 finding that memory can cause overconfidence

**Non-Goals:**
- Change test scripts (already fixed in v6-test-fixes commit)
- Change hook behavior or memory pipeline
- Change scoring rubric or trap definitions
- Add new traps or changes

## Decisions

### Decision 1: Enable metrics in both runs
**Choice**: Enable metrics in both init-baseline.sh AND init-with-memory.sh. Run A generates hook metrics too (SessionStart, UserPromptSubmit via wt-hook-skill) even without memory — capturing baseline hook overhead and providing a comparison denominator.

### Decision 2: Metrics enablement via flag file
**Choice**: Create `~/.local/share/set-core/metrics/.enabled` in init scripts. This matches the existing opt-in mechanism in `wt-hook-memory` (line 47-49). The flag is user-global, not project-local, so create it once and it persists. Add a cleanup note to run-guide.

### Decision 3: Post-run metrics analysis as manual step
**Choice**: Add a new section to run-guide.md with `set-memory metrics report` or `python3 lib/dashboard.py` commands for post-run analysis. Don't automate collection into the evaluator pipeline — keep it a manual inspection step.

### Decision 4: CLAUDE.md recall-verify wording
**Choice**: Keep the existing recall-verify paragraph (line 67 of with-memory.md) but add a stronger version: "Memory provides starting points, not final answers. After recalling implementation details, always grep/read the current code to verify — files may have changed since the memory was saved." This addresses the v6 finding where Run B used half the tokens on C12 but produced worse implementations.

## Risks / Trade-offs

- **Metrics flag is user-global**: If the user runs other projects concurrently during the benchmark, those will also generate metrics. Acceptable — the metrics include project name and can be filtered.
- **Metrics add ~10ms per hook invocation**: The timer and Python append add overhead. In v6, Run B was already 20min slower. This should add <1min total (negligible).
- **CLAUDE.md change may reduce memory utilization**: Stronger recall-verify guidance could make Run B slower (more verification steps). But the v6 result showed quality matters more than speed.
