# Memory Seeding Guide

Build project memory from existing OpenSpec artifacts. This guide is for AI agents working on brownfield projects that have OpenSpec documentation but empty `set-memory`.

## When to Use

- First time working on a project with existing OpenSpec artifacts
- After `set-memory status` shows 0 memories but `openspec/` has content
- When linked from a project's CLAUDE.md

## Prerequisites

Run this check first. If it fails, stop — memory is not available.

```bash
set-memory health
```

## Process

### Step 1: Discover What Exists

Scan the openspec directory to understand what documentation is available:

```
openspec/
  project.md              ← Project-level context
  specs/
    <capability>/spec.md  ← Current truth (synced specs)
  changes/
    <name>/
      proposal.md         ← Why this change exists
      design.md           ← How it was built (highest value)
      specs/*/spec.md     ← Delta specs (may be outdated)
      tasks.md            ← Implementation notes
```

### Step 2: Read and Extract

Process documents in this priority order. For each document, read it fully, then extract discrete insights worth remembering.

#### 1. `openspec/project.md` — Project Context

Extract 1-3 memories covering:
- What this project is and what problem it solves
- Key technology choices and constraints
- Target users or deployment context

**Memory type**: `Context`
**Tags**: `source:openspec,artifact:project`

#### 2. `openspec/specs/*/spec.md` — Current Specifications

These are the synced, authoritative specs. Extract:
- Key capabilities and their purpose
- Non-obvious behavioral requirements
- Important constraints or edge cases

**Memory type**: `Context` for behaviors, `Decision` for architectural choices
**Tags**: `source:openspec,artifact:spec,spec:<name>`

#### 3. `openspec/changes/*/proposal.md` — Change Proposals

The "Why" section is the most valuable part. Extract:
- What problem motivated this change
- What approach was chosen and why
- What alternatives were considered and rejected (if mentioned)

**Memory type**: `Decision` for choices made, `Context` for problem descriptions, `Learning` for rejected alternatives
**Tags**: `source:openspec,artifact:proposal,change:<name>`

#### 4. `openspec/changes/*/design.md` — Technical Designs

**This is typically the highest-value source.** Extract:
- Architecture decisions ("we chose X because Y")
- Trade-offs that were evaluated
- Integration patterns and how components connect
- What was explicitly rejected and why

**Memory type**: `Decision` for choices, `Learning` for trade-offs and rejected approaches
**Tags**: `source:openspec,artifact:design,change:<name>`

#### 5. `openspec/changes/*/specs/` — Delta Specs

**Skip if a main spec already exists** under `openspec/specs/` for the same capability — the main spec is more current. Only process delta specs for capabilities not yet synced to main.

**Memory type**: `Context`
**Tags**: `source:openspec,artifact:delta-spec,change:<name>`

#### 6. `openspec/changes/*/tasks.md` — Task Lists

Only extract if tasks contain notes, gotchas, or lessons learned. Plain checkbox lists with no commentary have no memory value.

**Memory type**: `Learning`
**Tags**: `source:openspec,artifact:tasks,change:<name>`

### Step 3: Save Each Insight

For each extracted insight, save it as a separate memory:

```bash
echo "<concise insight text>" | set-memory remember --type <Decision|Learning|Context> --tags <comma-separated-tags>
```

### Step 4: Summarize

After processing all documents, report what was saved:
- Total memories created
- Breakdown by type (Decision / Learning / Context)
- Which documents were processed

## Extraction Guidelines

### What Makes a Good Memory

Each memory should be:
- **Atomic** — one insight per memory, not a paragraph dump
- **Self-contained** — understandable without reading the source document
- **Concise** — 1-3 sentences, written as a clear statement
- **Valuable** — something a future agent would benefit from knowing

### Memory Type Reference

| Type | Use When | Example |
|------|----------|---------|
| **Decision** | A choice was made between alternatives | "Chose WebSocket over polling for real-time updates because sub-100ms latency is required" |
| **Learning** | Something was tried/rejected, or a non-obvious pattern was discovered | "Shape complexity metrics (convex hull ratio) are more reliable than ML-based cluster rejection for this use case" |
| **Context** | Background information about the project, its domain, or its architecture | "The system uses PointNet for 3D point cloud classification with depth camera input" |

### DO Extract

- "We chose X because Y" → **Decision**
- "X didn't work because Y" → **Learning**
- "The system does X under condition Y" → **Context**
- Rejected alternatives with reasons → **Learning**
- Non-obvious constraints or edge cases → **Learning**
- Key integration points between components → **Context**

### DON'T Extract

- Every individual requirement from a spec (too granular, creates noise)
- Trivial facts ("the project uses Python", "has a main function")
- Full paragraphs copied verbatim (summarize instead)
- Task checkbox items with no commentary
- Information that's obvious from the code itself

### Example Extractions

From a proposal's "Why" section:
> When multiple physical objects are placed touching each other on the table, the system incorrectly classifies them as a single different object with high confidence.

Extract as:
```bash
echo "Touching objects on the table get merged into a single contour by edge detection, causing false classification as a different object with high confidence" | set-memory remember --type Learning --tags source:openspec,artifact:proposal,change:add-cluster-rejection
```

From a design's architecture decision:
> We use shape complexity metrics (convex hull ratio, perimeter-to-area ratio) rather than training a rejection class, because the rejection class approach requires negative samples that are hard to generate realistically.

Extract as:
```bash
echo "Shape complexity metrics (convex hull ratio, perimeter-to-area) chosen over ML rejection class for cluster detection — rejection class requires realistic negative samples that are hard to generate" | set-memory remember --type Decision --tags source:openspec,artifact:design,change:add-cluster-rejection
```

## CLAUDE.md Integration

Add this to a project's CLAUDE.md to trigger seeding when memory is empty:

```markdown
## Memory Seeding

If `set-memory status` shows 0 memories and the `openspec/` directory contains
artifacts, follow the [memory seeding guide](https://raw.githubusercontent.com/tatargabor/set-core/master/docs/memory-seeding-guide.md)
to build initial project memory from existing documentation.
```
