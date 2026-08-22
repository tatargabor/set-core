## Why

`remove-shodh-memory` took out the framework's memory subsystem after measuring what it
actually injected: over 21 days and 4958 transcripts, **187 memory lines reached a session and
168 of them (89.8 %) were `User frustrated` records** — a detector that fired on exclamation
marks, so `szuper!!!` and `pont így akartam!!!` were stored and replayed as anger. Exactly one
line in 187 was a reusable fact. Seven capabilities went with it, and the user has asked for
**one** of them back, in a different shape: not the automatic *capture* that produced those
numbers, but a **distillation** — a pass that reads a finished session and writes down what was
*learned*.

The distinction is the whole point. Capture ran on `Stop`, which fires at the end of **every
assistant turn**, so it wrote whatever prompt happened to be in flight — including harness
artifacts it had no business storing. A distillation runs once, on a completed transcript, and
has to justify every line it writes.

## What Changes

- A **`SessionEnd` hook** that does no reading and no writing beyond a queue entry: transcript
  path, project slug, timestamp. **BREAKING** with the old design on purpose — the previous
  carrier was `Stop`, and its firing frequency is the measured cause of the noise.
- A **distiller** that runs out of band over the queue, reads the finished transcript, and
  proposes candidate facts.
- An **admissibility gate** that refuses a candidate rather than filing it: no claim about the
  user's state, no harness artifact stored verbatim, nothing the repository already records,
  nothing that only mattered inside the session.
- A **confidentiality gate that runs before the write**, reusing `bin/set-leakscan`'s
  runtime-resolved private-slug list. A pattern list committed to this repo would itself be the
  leak, which is why the list is resolved at run time from `~/.config/set-core/projects.json`.
- An **index-budget refusal**: `MEMORY.md` is injected only up to **200 lines / 25 KB** and
  nothing warns past the cut, so the distiller stops appending at 150 lines / 20 KB and reports
  instead of silently disabling memory for every later session in that project.
- A **trace requirement**: the distiller is judged on the file it wrote, never on its own
  report. A subagent's "done" is not evidence that anything happened.
- No second store. Everything lands in the native per-repository directory
  `~/.claude/projects/<slug>/memory/`, one file per fact plus one index line.

## Capabilities

### New Capabilities
- `session-distillation`: what a distillation pass reads, what it may write, what disqualifies a
  candidate, where the output goes, and the two budgets (index size, confidentiality) it must
  treat as refusals rather than warnings.
- `session-end-queue`: the `SessionEnd` hook contract — what it enqueues, what it must not do
  in-process, and how a queue entry is retired with evidence rather than with a report.

### Modified Capabilities
<!-- None. `native-memory-layer` is the capability this builds on, but it is still a delta
     inside the unarchived `remove-shodh-memory` change, so it has no entry in
     `openspec/specs/` to file a delta against. It is named in Impact instead. -->

## Impact

- **Depends on, and must not contradict, `remove-shodh-memory`** — specifically its
  `native-memory-layer` spec (still unarchived) and the `CLAUDE.md` memory rules it wrote. If
  this change would need a second store, it has failed rather than the rule.
- **New:** a hook script under `bin/`, its registration in `.claude/settings.json`, and the
  distiller itself. Both are framework-owned and deployable (`set-project init`).
- **Reuses:** `bin/set-leakscan`'s `private_slugs()` / allowlist resolution as a library rather
  than a re-implementation — a second copy of that list drifts the moment it is written.
- **Reads:** Claude Code transcripts at `~/.claude/projects/<slug>/*.jsonl` (measured shape:
  `user`, `assistant`, `attachment`, `system`, `file-history-snapshot` records) and writes only
  into that project's `memory/` directory.
- **Consumer-facing:** the confidentiality gate is what makes this safe to deploy at all; a
  distiller without it would persist consumer-derived content, which is the exact carrier
  `External Project Confidentiality` names.
