# Proposal: Team Sync & Collaboration

JIRA Key: TBD
Story: EXAMPLE-466

## Summary

Team-level synchronization and collaboration features for the Control Center. Makes visible who's working on what, shared task queue, conflict warnings, and team chat.

## Motivation

Currently every developer works in isolation with their own Control Center. There's no visibility into:
- Who's working on what right now
- Which files others are modifying
- Which PRs are waiting for review
- Shared task status

The "Multiplayer AI" concept means agents with team-level context are more effective.

### Motivation and Experience Sharing

The team feature isn't just about productivity, it's also about **motivation**:
- Seeing that others also use the wt + Claude combination → "I'm not alone"
- Sharing successes: "Look, it solved it in 5 minutes!"
- Learning from each other: how to write good prompts, what workflows work
- Positive competition: who can work more efficiently

**Experience sharing forms:**
- **Screenshots/GIFs**: "This is how I did it" moments
- **Tips & Tricks**: Proven solutions, prompt templates
- **Success stories**: "Today I shipped 3 features with Claude"
- **Documentation integration**: Documenting best practices

**Goal:** To make the team **enjoy** working with the set-core + Claude combination, and for usage to spread organically.

## Proposed Features

### 1. Team Status Board
Real-time view of all team members' worktree status:
- How many agents each person runs
- Which changes they're working on
- Agent status (running/waiting/idle)
- Last activity time

### 2. Conflict Warning
Warning when two developers are working on the same file(s):
- Git diff monitoring
- Real-time warning in the GUI
- "Peter is also modifying: UserService.ts"

### 3. Shared Task Queue
Shared task list that any agent can pick up:
- Synced from JIRA or manual
- Auto-assign to idle agents
- Priority ordering
- "Claim" button in the GUI

### 4. Team Chat
Simple messaging from the Control Center:
- No need to switch to Slack
- Agents can also send messages (e.g., "I'm done, need a review")
- Mention support (@name)

### 5. Findings Sharing
Shared knowledge base:
- "I found this: X pattern works for Y"
- Agents can also contribute
- Searchable, taggable

### 6. PR Review Queue
GitLab/GitHub PRs waiting for review:
- Team member PRs
- Review requests
- Quick approve/comment

## Architecture Options

### Option A: Git-based Sync (Recommended for start)
```
~/.set-core/team/
├── members/
│   ├── john.json      # Status, worktrees
│   ├── peter.json
│   └── anna.json
├── queue/
│   └── tasks.json      # Shared task queue
├── chat/
│   └── messages.jsonl  # Append-only chat log
└── findings/
    └── findings.json   # Shared knowledge
```

- Dedicated git repo (e.g., `team-sync.git`)
- Periodic push/pull (30s interval)
- Conflict resolution: last-write-wins for status
- Simple, no server dependency

### Option B: WebSocket Server
- Central server (Node.js/Python)
- Real-time updates
- More infrastructure overhead
- More scalable

### Option C: JIRA/Confluence Integration
- Existing infrastructure
- Task queue = JIRA board filter
- Status = JIRA custom fields
- Limited real-time capability

## UI Design

### Control Center Extension
```
┌─────────────────────────────────────────────────────────────┐
│  [Local] [Team]  tabs                                        │
├─────────────────────────────────────────────────────────────┤
│  Team View:                                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ John (3 running)    │ Peter (1 waiting)  │ Anna         ││
│  │ • add-auth ●        │ • fix-payment ⚡    │ (idle)       ││
│  │ • add-api ●         │                    │              ││
│  │ • tests ●           │                    │              ││
│  └─────────────────────────────────────────────────────────┘│
│  ⚠️ Conflict: UserService.ts (John & Peter)                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Peter: need review for fix-payment                      ││
│  │ John: 10 min and I'll check it                          ││
│  │ [Message input...]                          [Send]      ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Configuration

```json
{
  "team": {
    "enabled": true,
    "sync_repo": "git@github.com:org/wt-sync.git",
    "member_name": "john",
    "sync_interval_ms": 30000,
    "features": {
      "status_board": true,
      "conflict_warning": true,
      "task_queue": true,
      "chat": true,
      "findings": false
    }
  }
}
```

## Implementation Phases

### Phase 1: Status Board (MVP)
- Team member status JSON sync
- Basic GUI tab
- Manual refresh

### Phase 2: Conflict Warning
- File change tracking
- Real-time warning display
- Git diff integration

### Phase 3: Task Queue
- Shared queue file
- Claim/release mechanism
- JIRA integration optional

### Phase 4: Chat & Findings
- Message sync
- Findings database
- Search/filter

## Security Considerations

- Git repo access control
- No sensitive data in sync (only status, not code)
- Member name validation

## Out of Scope

- Video/voice chat
- Screen sharing
- Full project management (use JIRA)
- Code review in GUI (use GitLab)

## Open Questions

1. Git-based vs WebSocket - which is preferred?
2. How many team members would use it?
3. How important is JIRA integration?
4. Is chat needed or is Slack sufficient?
