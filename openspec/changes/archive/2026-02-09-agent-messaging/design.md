## Context

The set-core system currently has two communication channels:
1. **Broadcast** (`activity.json`): One-way status announcements via `/context:broadcast`, synced through git. Agents can broadcast but can only see others via `/context:status` which relies on LLM file parsing.
2. **Chat** (`wt-control-chat`): E2E encrypted 1:1 messaging with GUI dialog. Only human-accessible — no agent integration.

Cross-machine ping-pong testing between gep1-mac and gep2-linux revealed:
- The broadcast→sync pipeline works but the `team_status.json` cache didn't propagate the broadcast field (fixed in `f8252ca8`)
- Agents had to poll raw git files because `/context:status` was unreliable
- There's no way for an agent to send a targeted message to another agent
- The single `chat/messages.jsonl` file is a merge conflict risk with concurrent writers

GitHub load analysis for git operations:
- Current (sync only, 2 machines, 30sec poll): ~480 git ops/hour — well within limits
- Naive messaging (push per message): ~1560 git ops/hour — risky, GitHub may throttle
- Git SSH/HTTPS has no hard rate limit but GitHub soft-throttles aggressive repos (~100+ push/hour)

## Goals / Non-Goals

**Goals:**
- Enable agents to send directed messages to specific agents/members via `/wt:msg`
- Expose messaging through MCP tools for programmatic access
- Unify command namespace under `/wt:*`
- Eliminate git merge conflicts in chat storage
- Show communication activity in the GUI with minimal visual footprint
- Zero additional GitHub load from messaging (piggyback on existing sync cycle)
- Control branch history compaction to prevent unbounded growth

**Non-Goals:**
- Real-time push notifications (polling is acceptable)
- Group messaging (broadcast covers this use case)
- Message threading or replies
- Changing the E2E encryption model (NaCl Box stays)
- Mobile or web clients
- Changing how `activity.json` works (broadcast stays as-is)
- Local fast-path messaging (V2 — for now all messages go through git)

## Decisions

### D1: Per-sender outbox files for chat storage

**Decision**: Replace `chat/messages.jsonl` with `chat/outbox/{sender-name}.jsonl`

**Rationale**: Each machine only appends to its own outbox file. When reading, the reader scans all outbox files and merges/sorts by timestamp. This eliminates git merge conflicts entirely — two machines never write to the same file.

**Alternatives considered**:
- Per-conversation files (`chat/{a}--{b}.jsonl`): Both parties write to the same file — still conflicts
- Per-message files (`chat/msg/{timestamp}-{uuid}.json`): No conflicts but creates thousands of files over time
- CRDT-based merge: Too complex for the current use case

**Migration**: On first read, if `chat/messages.jsonl` exists and `chat/outbox/` doesn't, split messages into per-sender outbox files. The migration runs once per machine.

### D2: Batched messaging — zero extra git load

**Decision**: `send_message()` only appends to a local outbox file. It does NOT commit or push. The existing `wt-control-sync` cycle (every 15 seconds) picks up outbox changes and pushes them alongside member status updates — one commit, one push.

**Rationale**: This means messaging adds ZERO additional git operations. Whether an agent sends 0 or 100 messages in a 15-second window, the sync cost is identical. GitHub load stays at ~480 ops/hour regardless of message volume.

**Flow**:
```
send_message("target", "msg")
  → append to chat/outbox/{me}.jsonl    (local file write, <1ms)
  → return "queued"

15 sec later: wt-control-sync --full
  → git pull --rebase
  → update members/{me}.json
  → git add -A  (members + any new outbox lines)
  → git commit --amend "Update status: {me}"
  → git push
```

**Inbox reading** is also zero-cost: `get_inbox()` reads local outbox files that were already pulled by the last sync. No additional git operations.

**Consequence**: The MCP `send_message()` does NOT need to relax the read-only constraint. It only writes a local file (same as broadcast writing `activity.json`). The git push is the sync worker's job, not MCP's.

**Alternatives considered**:
- Push per message: Too much GitHub load, ~3x increase
- Separate message push queue: Unnecessary complexity when sync already exists
- Longer batch window (60sec): Acceptable but 15sec feels responsive enough

### D3: Slash command namespace change

**Decision**: Move from `/context:*` to `/wt:*` namespace. New commands: `/wt:broadcast`, `/wt:status`, `/wt:msg`, `/wt:inbox`.

**Rationale**: All other set-core commands use the `/wt:` prefix. The `context` namespace was created before the convention was established.

**Implementation**: Move `.claude/commands/context/*.md` to `.claude/commands/wt/broadcast.md` and `wt/status.md`. Add new `wt/msg.md` and `wt/inbox.md`. Remove old `context/` directory.

### D4: GUI activity indicators

**Decision**: Show small colored indicators in the existing agent_status column of team worktree rows. Use subtle icons to distinguish broadcast vs. directed messages.

**Rationale**: The GUI already shows team rows with agent_status. Adding communication indicators alongside avoids new UI elements. The signals should be passive — the human glances and sees who's communicating without needing to click anything.

**Visual design**:
- Team row extra column shows activity when fresh (< 60 seconds):
  - `📡` — recent broadcast sent/updated
  - `💬` — recent directed message sent/received
- Tooltip on the indicator shows the message preview
- No indicator when no recent activity (clean by default)

### D5: Message targeting by change_id

**Decision**: Agents address messages to `<member>/<change_id>` (e.g., `tg@linux/gep2-linux`). For convenience, if there's only one worktree for a member, just `<member>` suffices.

**Rationale**: A member may have multiple worktrees (agents). Targeting by change_id allows precision. The MCP `get_inbox()` tool automatically filters to the current worktree's change_id.

**Alternative**: Target by worktree path — too verbose and machine-specific.

### D6: Control branch history compaction

**Decision**: Add `wt-control-sync --compact` that squashes all commits on the wt-control branch into a single commit and force-pushes. Other machines auto-recover on next sync via the existing recovery mechanism (fetch + reset --hard + reapply).

**Rationale**: The amend strategy keeps history growth slow (~100-200 commits/day with 2 machines), but over months this accumulates (30K-70K commits/year). The .git directory grows and clones slow down. Periodic compaction resets this to 1 commit.

**How it works**:
```
wt-control-sync --compact
  1. git pull (get latest)
  2. git reset --soft $(git rev-list --max-parents=0 HEAD)  (squash to root)
  3. git commit -m "Compacted: all status as of {date}"
  4. git push --force-with-lease origin wt-control
```

**Other machines on next sync**:
```
  1. git pull --rebase fails (diverged history)
  2. Recovery kicks in (already implemented, lines 529-543 of wt-control-sync):
     - git fetch origin wt-control
     - git reset --hard origin/wt-control
     - Re-write own member file
     - git add + commit + push
```

**No locking needed**: `--force-with-lease` prevents two machines from compacting simultaneously. If two try at once, one succeeds and the other gets a rejection → normal sync recovery handles it.

**When to run**: Auto-triggered when commit count exceeds `compact_threshold` (default: 1000, configurable in team settings for testing with low values). Also available manually via `wt-control-sync --compact`.

### D7: Multiline message support

**Decision**: The MCP `send_message()` accepts multiline text natively (it's a string parameter). The slash command `/wt:msg` passes the message as a single shell argument in quotes. The `wt-control-chat send` CLI reads from stdin if message argument is `-`.

**Rationale**: Real use cases like bug reports require multiline messages. The MCP tool handles this naturally. For CLI, stdin is the standard Unix way.

**Example**:
```bash
# MCP (multiline natively)
send_message(recipient="tg@linux/game-ui", message="BUG: Start button\nSteps: 1. Click start\nExpected: Game starts\nActual: Nothing")

# CLI
echo "BUG: Start button..." | wt-control-chat send tg@linux/game-ui -
```

## Risks / Trade-offs

- **[15 sec latency]** Messages are delivered within 15 seconds (next sync cycle), not instantly. → Acceptable for all identified use cases. Agents don't need sub-second messaging.
- **[Git push race]** Two machines pushing simultaneously → one push fails, retried on next sync cycle. → Already handled by existing recovery code.
- **[Migration disruption]** Existing `messages.jsonl` needs splitting into outbox files. → Migration runs automatically on first read; backward-compatible.
- **[Compaction data loss]** Force push after compaction discards git history. → Only status/chat data, no code. Current state is preserved, only history is lost.
- **[Namespace rename]** Renaming `/context:*` to `/wt:*` breaks any saved workflows. → Old commands simply deleted; agents adapt on next conversation.
- **[Outbox file growth]** Per-sender JSONL files grow unbounded. → Compaction squashes commits but not file content. Future: add message TTL or rotation.

## Open Questions

- Should compaction auto-trigger based on commit count, or always be manual?
- Should old outbox messages (>30 days?) be pruned during compaction?
