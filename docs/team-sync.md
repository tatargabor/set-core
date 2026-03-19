[< Back to README](../README.md)

# Team Sync & Messaging

Cross-machine collaboration **without a central server** — using a `set-control` git branch for team and machine-level coordination. Each machine syncs agent status automatically. Includes encrypted chat and directed agent-to-agent messaging.

> **Status:** Experimental. Usable but expect rough edges.

> **Note:** Claude Code's Teams feature does not replace this — set-core team sync operates at the agent level, enabling different remote machines, users, or local agents to coordinate at a higher level.

## Setup

```bash
# On each machine (one-time)
set-control-init
set-control-sync --full
```

Now the Control Center on each machine shows what the other is doing:

```
│  tg@linux/add-api     │ running │ opsx:apply │ 32%  │
│  tg@mac/add-frontend  │ waiting │ opsx:apply │ 55%  │
```

## Agent Messaging

Agents can send direct messages to each other across machines:

```
# Send a message
/set:msg tg@mac/add-frontend "API endpoints ready, schema at docs/api.md"

# Read incoming messages
/set:inbox
# → [10:30] tg@linux/add-api: API endpoints ready, schema at docs/api.md

# Broadcast what you're working on
/set:broadcast "Refactoring checkout flow"

# See all agent activity
/set:status
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `set-control-init` | Initialize set-control team sync branch |
| `set-control-sync` | Sync member status (pull/push/compact) |
| `set-control-chat send <to> <msg>` | Send encrypted message |
| `set-control-chat read` | Read received messages |

### Skills

| Skill | Description |
|-------|-------------|
| `/set:msg <target> <msg>` | Send message to another agent |
| `/set:inbox` | Read incoming messages |
| `/set:broadcast <msg>` | Broadcast what you're working on |
| `/set:status` | Show agent activity |

## Use Cases

### Cross-machine development

One machine handles backend, another handles frontend:

```
# On linux (backend agent):
/set:msg tg@mac/game-ui "Game loop API ready at engine.start()"

# On mac (frontend agent):
/set:inbox
# → [10:30] tg@linux/game-logic: Game loop API ready at engine.start()
```

### Parallel testing with bug reports

One machine codes, another tests. Bug reports go via `/set:msg`:

```
# Tester agent finds a bug:
/set:msg tg@mac/feature-x "BUG: Start button unresponsive.
Steps: 1. Click start button
Expected: Game starts
Actual: Nothing happens"

# Developer agent reads and fixes:
/set:inbox
/set:msg tg@linux/testing "Fixed in commit def456, please retest"
```

## Batch Messaging Architecture

Messages add **zero additional git operations**. Messages are written to local outbox files and picked up by the next normal sync cycle:

```
Agent sends message:
  send_message("target", "msg")
    → append to chat/outbox/{me}.jsonl  (local file write, <1ms)
    → NO git commit, NO git push

Next sync cycle (every 2 minutes):
  set-control-sync --full
    → git pull --rebase
    → git add -A  ← picks up outbox changes too
    → git commit --amend
    → git push --force-with-lease
```

Whether an agent sends 0 or 100 messages in a sync window, the sync cost is identical. Per-sender outbox files prevent git merge conflicts — each machine writes only to its own file.

> **Traffic note:** `set-control-sync` runs git fetch+push on every sync cycle. The default interval is 2 minutes. Lower intervals increase GitHub API traffic — at 15 seconds, that's ~480 git operations/hour per machine. Adjust in Settings > Team Sync interval.

## History Compaction

The `set-control` branch uses `--amend` to keep history small.

```bash
# Manual compaction
set-control-sync --compact

# Auto-compaction triggers when commit count exceeds threshold (default: 1000)
# Configure in team_settings.json on the set-control branch:
# { "compact_threshold": 50 }
```

Recovery after compaction is automatic — when a machine's `git pull --rebase` fails due to force-push, the existing recovery mechanism resets and re-syncs.

## Encrypted Chat

`set-control-chat` uses NaCl Box (libsodium) for end-to-end encrypted messages between team members.

---

*See also: [Control Center GUI](gui.md) · [MCP Server](mcp-server.md) · [Architecture](architecture.md)*
