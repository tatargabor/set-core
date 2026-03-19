## 1. Code Fixes

- [x] 1.1 Fix `init_state()` (line ~727): change `verify_retried: false` to `verify_retry_count: 0`
- [x] 1.2 ~~Wire `auto_detect_test_command()` into `resolve_directives()`~~ DEFERRED — viselkedésváltozás, külön change-ben opt-in flag-gel

## 2. Create Main Specs for New Capabilities

- [x] 2.1 Create `openspec/specs/agent-merge-resolution/spec.md` — agent-assisted merge conflict resolution
- [x] 2.2 Create `openspec/specs/post-merge-verification/spec.md` — post-merge build verification + dependency install + cache invalidation
- [x] 2.3 Create `openspec/specs/merge-conflict-fingerprint/spec.md` — conflict fingerprint dedup + max merge retry limit

## 3. Create Main Specs for Core Orchestration (Consolidated)

- [x] 3.1 Create `openspec/specs/orchestration-engine/spec.md` — consolidated spec covering: plan generation, dispatch (proposal.md), monitor loop (15s poll), state management (verify_retry_count integer), stalled change cooldown, failed build retry, auto-detect test command, replan safety, time limit, auto-replan, dual-mode input (brief/spec)
- [x] 3.2 Create `openspec/specs/verify-gate/spec.md` — consolidated spec covering: gate step order (test→build→test-file→review→verify), base build health check, merge-rebase fast path, retry context, model tiering
- [x] 3.3 Create `openspec/specs/orchestrator-memory/spec.md` — consolidated spec covering: helper functions, event memories (merge/test/review/stall), per-item recall, replan recall, dispatch enrichment, gate timing, retry token tracking, periodic audit
- [x] 3.4 Create `openspec/specs/orchestrator-tui/spec.md` — consolidated spec covering: TUI launch, header status, change table, live log tail, checkpoint approval, auto-refresh, keyboard navigation

## 4. Update Existing Main Specs

- [x] 4.1 Update `openspec/specs/ralph-loop/spec.md` — add stall_count reset behavior (reset in poll_change on fresh mtime, NOT in resume_change), stale-but-alive PID handling

## 5. Verify

- [x] 5.1 Run `openspec status` to confirm all specs are properly structured
- [x] 5.2 Spot-check each new main spec against `bin/set-orchestrate` code for accuracy
