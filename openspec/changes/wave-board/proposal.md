## Why

A multi-step job that runs in waves — a cleanup across ten projects, a migration done one
group at a time — has no place where its execution state lives. Today it lives in the
conversation that started it, and that is the carrier that goes first: a compact, a `/clear`,
a second machine or a second person each lose it, and the job's status then has to be
re-derived from memory, which is how a step gets reported done that is not.

What was asked for is a **process roadmap**, not a product roadmap: which wave a job is in,
which item is done, in progress or blocked, and what is left — readable as a live page, and
updated "the most reliable way". The second half is the hard one. An agent's own report of
"step done" is the fastest signal and the least reliable: it is skipped when the agent forgets,
and it is wrong when the agent is wrong. So the state has to come from **evidence** that a
script can check, with the agent's report as the fast lane only.

One platform fact shapes the whole design: the board is a claude.ai Artifact page whose live
data is the Artifact's database, and **only the agent can write that database** (its
`ArtifactData` tool). A shell script or a hook cannot. So the deterministic part computes the
state and writes a payload file, and a hook makes the agent push it.

## What Changes

- **`bin/set-wave-board`** (Python 3, stdlib only, macOS + Linux): one tracked job file per job
  at `docs/waveboard/<job>.json` in the consumer repo; commands `init`, `add`, `set` (fast
  lane), `sync` (derive status from evidence, write the payload), `pushed`, `pending`, `page`,
  `render`.
- **Four evidence types**, evaluated deterministically: an OpenSpec change's task boxes (with
  the archive as "done"), a path that exists, a commit whose message matches, and any of these
  evaluated in **another registered project** resolved by name through the set-core registry —
  never by an absolute path in the job file.
- **`templates/waveboard/page.html`**: the read-only board page. It subscribes to the
  Artifact's `board/state` document and falls back to an embedded seed when the database is
  not available (an offline render, a signed-out viewer).
- **`bin/set-hook-waveboard`** (Stop hook): syncs quietly and, when a job's payload differs
  from what was last pushed, blocks the stop once with the exact push procedure — at most once
  per 30 minutes per job, never on a stop it caused itself, never touching the network.
- **Deployment**: `set-deploy-hooks` adds the hook to the Stop array, and its "already
  canonical" early return now also requires it, so projects initialised before this change
  receive it on their next `set-project init`. `install.sh` links both commands.
- **Skill `set:wave-board`**: when to use a board, the creation flow, the push procedure, and
  the cross-machine notes.

## Capabilities

### New Capabilities

- `wave-board`: the job file and its schema, evidence-derived status and its precedence, the
  idempotent sync and its payload, the push hand-off to the agent, the Stop hook, the board
  page, and how the hook reaches existing projects.

### Modified Capabilities

(none) — `hook-auto-install` describes `set-deploy-hooks`, but its requirements still name
the removed memory hooks and are already inaccurate; the one deploy behaviour this change adds
is stated inside `wave-board`, where it can be checked against the code that ships with it.

## Impact

- New: `bin/set-wave-board`, `bin/set-hook-waveboard`, `templates/waveboard/page.html`,
  `.claude/skills/set/wave-board/SKILL.md`, `tests/unit/test_wave_board.py`.
- Changed: `bin/set-deploy-hooks` (one Stop hook added, canonical check extended),
  `install.sh` (two scripts linked).
- Consumer repos: a new tracked directory `docs/waveboard/` exists only in projects that create
  a job; machine-local state lives under `.set/waveboard/`, which the tool keeps ignored itself.
- No new dependency: Python 3 standard library and `git`.
- New environment variables: `SET_CORE_REGISTRY` (registry path override, default
  `~/.config/set-core/projects.json`), `SET_WAVEBOARD_PUSH=off` (silence the hook),
  `SET_WAVEBOARD_NAG_SECONDS` (backoff override, default 1800).
