# Sentinel Autonomy Rules

When acting as sentinel supervisor:

## NEVER MERGE MANUALLY — GATES ONLY

**NEVER run `git merge` manually to merge a change into main.** All merges MUST go through the engine's merge pipeline (`execute_merge_queue`) which runs integration gates (dep install → build → test → e2e). Manual merges bypass gate validation and can introduce broken code (duplicate routes, build failures, type errors) that the gates would have caught. If a merge is blocked, fix the underlying issue (build error, conflict) and let the engine retry — do NOT shortcut by merging manually.

## Other rules

- **Never ask before fixing and restarting.** If a bug is found, fix it, commit it, and restart the orchestration immediately.
- **Never ask before restarting.** If the orchestrator crashes or stops, restart it after cleanup — no confirmation needed.
- **Commit fixes immediately.** Bug fixes discovered during E2E monitoring get committed right away with clear commit messages.
- **Update findings continuously.** Write observations to the findings MD file as they happen, don't wait for a report.
- **Deploy fixes to running E2E.** After committing a fix, restart the test with the new code — the whole point of E2E is to validate fixes.
- **Polling must never stop on its own.** The sentinel poll loop runs continuously until the user explicitly asks to stop. If a fix is applied, resume polling immediately after. If a restart happens, resume polling with the new PID. If context compacts, resume polling. Never let the poll loop silently die — always dispatch the next background poll after handling an event.
