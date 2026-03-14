[< Back to README](../README.md)

# OpenSpec Workflow

OpenSpec is a spec-driven development workflow built into wt-tools. It structures changes as a sequence of artifacts — proposal, design, specs, tasks — before implementation begins. Each artifact builds on the previous one, creating a traceable path from idea to code.

## Skills

| Skill | Description |
|-------|-------------|
| `/opsx:new <name>` | Start a new change — create the change directory and scaffold artifacts |
| `/opsx:ff <name>` | Fast-forward — create all artifacts in one go (proposal → design → specs → tasks) |
| `/opsx:continue` | Continue working on a change — create the next artifact |
| `/opsx:apply` | Implement tasks from a change — work through the task list |
| `/opsx:verify` | Verify implementation matches change artifacts |
| `/opsx:archive` | Archive a completed change |
| `/opsx:explore` | Thinking mode — explore ideas, investigate problems, no implementation |
| `/opsx:sync` | Sync delta specs from change to main specs |

## Artifact Flow

```
/opsx:new or /opsx:ff
        │
        ▼
   ┌──────────┐
   │ proposal │  WHY — motivation, scope, capabilities
   └────┬─────┘
        ▼
   ┌──────────┐
   │  design  │  HOW — technical decisions, architecture, trade-offs
   └────┬─────┘
        ▼
   ┌──────────┐
   │  specs   │  WHAT — requirements with testable scenarios (SHALL/MUST)
   └────┬─────┘
        ▼
   ┌──────────┐
   │  tasks   │  DO — implementation checklist with checkboxes
   └────┬─────┘
        ▼
   /opsx:apply     implement tasks one by one
        │
        ▼
   /opsx:verify    check implementation matches specs
        │
        ▼
   /opsx:archive   archive completed change, sync specs
```

## Typical Workflow

### Interactive (step by step)

```
/opsx:new add-user-auth          # creates scaffolded change directory
/opsx:continue                    # create proposal
/opsx:continue                    # create design (reads proposal)
/opsx:continue                    # create specs (reads proposal)
/opsx:continue                    # create tasks (reads design + specs)
/opsx:apply                       # implement tasks
/opsx:verify                      # verify implementation
/opsx:archive                     # archive and clean up
```

### Fast-forward (all at once)

```
/opsx:ff add-user-auth           # creates all artifacts in one session
/opsx:apply                       # implement tasks
/opsx:verify                      # verify
/opsx:archive                     # done
```

### Explore first

```
/opsx:explore                     # think through the problem, no commitment
# ... when ready ...
/opsx:ff add-user-auth           # formalize into artifacts
/opsx:apply                       # implement
```

## File Structure

```
openspec/
├── config.yaml                    # OpenSpec configuration
├── changes/
│   └── add-user-auth/
│       ├── .openspec.yaml         # change metadata
│       ├── proposal.md            # why this change
│       ├── design.md              # how to implement
│       ├── specs/
│       │   └── user-auth/
│       │       └── spec.md        # detailed requirements
│       └── tasks.md               # implementation checklist
└── specs/                         # main specs (accumulated from changes)
    └── user-auth/
        └── spec.md
```

## Specs Format

Specs use a structured format with requirements and scenarios:

```markdown
## ADDED Requirements

### Requirement: User can log in with email
The system SHALL allow users to log in with email and password.

#### Scenario: Successful login
- **WHEN** user submits valid email and password
- **THEN** system returns an authentication token

#### Scenario: Invalid credentials
- **WHEN** user submits wrong password
- **THEN** system returns 401 with error message
```

Delta operations: `ADDED`, `MODIFIED`, `REMOVED`, `RENAMED`.

## In Orchestration

The orchestrator uses OpenSpec internally — each dispatched change runs `/opsx:ff` to generate artifacts, then `/opsx:apply` via a Ralph loop to implement. The spec document drives the plan, and each change gets its own OpenSpec artifacts in its worktree.

## Version

wt-tools is pinned to **OpenSpec v1.1.1**. Do not upgrade — v1.2.0 introduced deselection pruning that can delete our custom skills/commands during `openspec update`.

```bash
npm install -g @fission-ai/openspec@1.1.1
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `wt-openspec status [--json]` | Show OpenSpec change status |
| `wt-openspec init` | Initialize OpenSpec in the project |
| `wt-openspec update` | Update OpenSpec skills to latest version |
| `openspec list [--json]` | List all changes with status |
| `openspec status --change <name> [--json]` | Detailed change status |
| `openspec new change <name>` | Create a new change (CLI) |

---

*See also: [Project Setup](project-setup.md) · [Sentinel & Orchestration](sentinel.md) · [Ralph Loop](ralph.md) · [Getting Started](getting-started.md)*
