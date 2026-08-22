# Memory

set-core ships **no memory subsystem**. Durable, cross-session knowledge lives in Claude
Code's own per-repository memory directory, and the framework's job is to stay out of its
way.

## Where it lives

```
~/.claude/projects/<project-slug>/memory/
├── MEMORY.md              # the index — one line per memory
├── user_*.md              # who the user is, how they work
├── feedback_*.md          # guidance they have given, and why
├── project_*.md           # ongoing work and constraints
└── reference_*.md         # pointers to dashboards, tickets, URLs
```

`/memory` browses and edits it. `/context` shows what actually loaded this session.

## The limit that decides how you write the index

**Only the first 200 lines, or 25 KB, of `MEMORY.md` load at session start.** Content past
that cut reaches nobody, and **nothing warns you** — the absence looks exactly like having
no memories on that topic. Keep the index to one line per memory, and prune at 150 lines or
20 KB rather than at the limit.

The topic files are **not** loaded at startup. The index is a table of contents; the agent
opens the file it points at, with ordinary file tools, when the entry looks relevant.

## What this does not do

No semantic search. No tags. No temporal queries. No full-text search. No cross-device sync.
No version history. No automatic extraction at session end.

Searching means reading the index and opening the file it names.

That list is not an oversight, and it is worth the number it cost to learn: the subsystem
this replaced had **all seven** of those capabilities, and over 21 days it injected 187
memory lines into sessions of which **exactly one** was a reusable fact. The other 186 were
false `User frustrated` records — its detector fired on exclamation marks — carrying raw
task notifications and other agents' prompts as their payload. Seven capabilities delivering
one useful line is not a trade worth restoring by reflex. If you need one of them, that is a
change of its own, measured against this layer rather than against a vacuum.

The full account is in
[`openspec/changes/remove-shodh-memory/proposal.md`](../../openspec/changes/remove-shodh-memory/proposal.md);
the original 2026-02 audit that first found the subsystem's knowledge graph empty is in
[`docs/research/shodh-memory-audit.md`](../research/shodh-memory-audit.md).

## Writing a memory

One fact per file. Frontmatter carries a `name` (kebab-case slug), a one-line `description`
used to judge relevance, and a `type` of `user` / `feedback` / `project` / `reference`. Link
related memories with `[[their-name]]`. Then add one line to `MEMORY.md`.

**Two rules on content, both learned expensively:**

- **A memory records a fact, never a claim about the user's state.** No inferred emotion, no
  sentiment label the source text does not support. And never store a harness artifact
  verbatim — a task notification, a cross-session message, another agent's system prompt, a
  transcript fragment. Those were 89.8 % of what the removed system injected.
- **Nothing derived from a consumer's data.** No consumer project name, partner name, or
  personal name. Generalise before saving; a memory naming a real entity is a defect to
  correct, not harmless content. See
  [External Project Confidentiality](../../CLAUDE.md).

## Verifying against a memory

A memory is a hypothesis, not a verdict. It records what was true when it was written, and
it is not branch- or worktree-aware. During `/opsx:verify`, check the filesystem — never
skip a check because a memory says "known false positive" or "same pattern".
