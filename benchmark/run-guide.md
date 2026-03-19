# Benchmark Run Guide

Complete step-by-step guide for executing the shodh-memory benchmark v2.

## Prerequisites

- **set-core** installed and on PATH (`set-loop`, `set-deploy-hooks`, `set-memory` all available)
- **Node.js 18+** (`node --version`)
- **Claude Code CLI** installed (`claude --version`)
- **openspec CLI** installed (`openspec --version`; install: `npm install -g @fission-ai/openspec@1.1.1`)
- Enough disk/RAM for two parallel Next.js projects

## 1. Bootstrap

Two init scripts handle all setup. Each creates a fresh CraftBazaar repo with the right CLAUDE.md, extracts agent-only change files (12 changes), copies test scripts, and commits.

### Run A (Baseline — No Memory)

```bash
./benchmark/init-baseline.sh [target-dir]
# Default: ~/benchmark/run-a/craftbazaar-baseline
```

What it does: `git init` → `npm init` → `openspec init --tools claude` → `set-deploy-hooks` → copies `baseline.md` as CLAUDE.md (PORT=4000) → extracts 12 change files (agent-only, no evaluator notes) → copies test scripts to `tests/` → initial commit.

**No** `set-memory-hooks install` — baseline has no memory.

### Run B (With Memory)

```bash
./benchmark/init-with-memory.sh [target-dir]
# Default: ~/benchmark/run-b/craftbazaar-memory
```

Same as Run A plus: copies `with-memory.md` as CLAUDE.md (PORT=4001, hook-driven persistent memory) → verifies `set-memory health`.

### What the scripts check

Both scripts verify prerequisites before starting and will error if anything is missing. They also verify that evaluator notes didn't leak into the agent-visible change files.

## 2. Starting the Runs

### Option A: Interactive Claude sessions (recommended)

Open two terminals, each running Claude Code interactively:

**Terminal 1 (Run A):**
```bash
cd ~/benchmark/run-a/craftbazaar-baseline
claude --dangerously-skip-permissions
```

**Terminal 2 (Run B):**
```bash
cd ~/benchmark/run-b/craftbazaar-memory
claude --dangerously-skip-permissions
```

Then paste this prompt into **each** Claude session:

```
Read CLAUDE.md, then check openspec list --json and ls docs/benchmark/ to find the next
incomplete change. Read the project spec (if first change) and the change definition file.
Then implement it: run /opsx:ff <change-name> to create artifacts, then /opsx:apply <change-name>
to implement. Run bash tests/test-NN.sh <PORT> after each change and fix until pass.
Follow the Benchmark Task workflow in CLAUDE.md exactly — work through all 12 changes in order.
```

### Option B: set-loop automation

```bash
# Terminal 1 (Run A)
cd ~/benchmark/run-a/craftbazaar-baseline
set-loop start "Build CraftBazaar changes 01-12" --max 30 --stall-threshold 3 --done manual

# Terminal 2 (Run B)
cd ~/benchmark/run-b/craftbazaar-memory
set-loop start "Build CraftBazaar changes 01-12" --max 30 --stall-threshold 3 --done manual
```

### Key flags

| Flag | Value | Purpose |
|------|-------|---------|
| `--max 30` | 30 iterations | Budget for 12 changes with test-fix cycles |
| `--stall-threshold 3` | 3 iterations | Stop if no commits for 3 consecutive iterations |
| `--done manual` | manual completion | Agent decides when done |

### First-run trust

Before starting the loop, open Claude interactively once in each directory to accept the trust prompt:

```bash
cd ~/benchmark/run-a/craftbazaar-baseline && claude --dangerously-skip-permissions
# Type "hello", wait for response, Ctrl+C to exit

cd ~/benchmark/run-b/craftbazaar-memory && claude --dangerously-skip-permissions
# Same — accept trust, then exit
```

### Monitoring

From a third terminal:
```bash
# Check status
cd ~/benchmark/run-a/craftbazaar-baseline && set-loop status
cd ~/benchmark/run-b/craftbazaar-memory && set-loop status
```

## 3. No-Intervention Policy

During execution:
- **Do NOT** provide hints, answers, or direction to the agent
- **Do NOT** fix errors, install packages, or modify files
- If the agent asks a yes/no question, set-loop auto-continues (fresh iteration)
- If the loop stalls (3 iterations with no commits), let it stop — the stall is data
- If the loop hits max iterations (30), let it stop — record which changes completed

The only acceptable interventions:
- Restarting if the process crashes (machine reboot, OOM, etc.)
- Checking status with `set-loop status` (read-only)

## 4. Running Acceptance Tests (post-run)

After both runs complete, run the test suite against each project:

```bash
# Start the dev server
cd ~/benchmark/run-a/craftbazaar-baseline
PORT=4000 npm run dev &
sleep 5

# Run all tests
for t in tests/test-*.sh; do
  echo "--- $t ---"
  bash "$t" 4000
  echo ""
done

# Repeat for Run B with PORT=4001
```

## 5. Running Evaluator Scripts (post-run)

The evaluator scripts in `benchmark/evaluator/` provide automated checks:

```bash
EVAL_DIR="/path/to/set-core/benchmark/evaluator"

# For each run:
cd ~/benchmark/run-a/craftbazaar-baseline

# Schema checks (Image table, Int money, CartReservation, indexes)
bash "$EVAL_DIR/eval-schema.sh" .

# API checks (response format, money format) — needs running server
bash "$EVAL_DIR/eval-api.sh" 4000

# Behavior checks (stock logic, transactions, payout formula)
bash "$EVAL_DIR/eval-behavior.sh" .

# Coherence checks (prisma validate, tsc, seed, build)
bash "$EVAL_DIR/eval-coherence.sh" .
```

### Collecting all results

```bash
bash "$EVAL_DIR/collect-results.sh" ~/benchmark/run-a/craftbazaar-baseline "Run A (baseline)"
bash "$EVAL_DIR/collect-results.sh" ~/benchmark/run-b/craftbazaar-memory "Run B (memory)"
```

### Generating comparison

```bash
bash "$EVAL_DIR/compare.sh" \
  ~/benchmark/run-a/craftbazaar-baseline/results-run-a--baseline-.json \
  ~/benchmark/run-b/craftbazaar-memory/results-run-b--memory-.json
```

## 6. Results Collection

After both runs complete, gather data:

### Automatic data

```bash
# For each run (run-a and run-b):
cd ~/benchmark/<run>/craftbazaar-<label>

# Iteration history
set-loop history

# Git log with timestamps
git log --oneline --format="%h %ai %s"

# OpenSpec change completion
openspec list --json

# Agent-written status files
cat results/*.json

# Session transcript
cat .claude/ralph-loop.log
```

### Run B additional data

```bash
cd ~/benchmark/run-b/craftbazaar-memory

# All saved memories
set-memory list --json

# Memory count and health
set-memory status
```

## 7. Post-Run Annotation

For each change in each run:

1. Open the session transcript and find the relevant iterations
2. Review the agent's approach against the evaluator notes in `benchmark/changes/NN-*.md`
3. Fill out `benchmark/templates/session-annotation.md` (one per change per run)
4. Fill out `benchmark/templates/change-metrics.json` (one per change per run)

### Key areas to focus on (v2-specific)

| Changes | What to look for |
|---------|-----------------|
| C07-C09 | Did the agent find all affected code? How many iterations to search? |
| C10 | Did the agent add an "Update cart" button? Use confirm()? |
| C11 | Did the agent remove tabs or enhance them? |
| C12 | How many of the 12 bugs were fixed on first try? |

## 8. Comparison Report

After annotating all changes:

1. Run the automated comparison: `bash benchmark/evaluator/compare.sh run-a.json run-b.json`
2. Copy `benchmark/templates/comparison-report.md`
3. Fill in the per-change comparison sections with transcript evidence
4. For Run B, complete the diagnostic gap analysis using `benchmark/diagnostic-framework.md`

Alternatively, use `benchmark/collect-results.md` for agent-assisted evaluation.

## 9. Current Status (v7)

### v6 Results (2026-02-17)

The v6 benchmark showed no measurable memory advantage:

| Metric | Run A (baseline) | Run B (memory) |
|--------|-----------------|----------------|
| Changes completed | 12/12 | 12/12 |
| Trap score | 11.5/13 | 11/13 |
| C12 bugs fixed | 11/12 | 9/12 |

### v7 Changes (2026-02-20)

**Test fixes (implemented):** All 5 P0/P1 test weaknesses from v6-results.md have been fixed:

| Fix | File | What changed |
|-----|------|-------------|
| TRAP-M render check | test-12.sh | Checks `<Pagination` render, not just import |
| TRAP-N global mount | test-12.sh | Verifies Toast in layout.tsx |
| Payout fail on no data | test-12.sh | Fails instead of auto-passing when no multi-vendor orders |
| Vendor fail not skip | test-12.sh | Fails instead of silently skipping |
| TRAP-G checkout link | test-02.sh | Checks cart has checkout navigation |

**C12 acceptance criteria (implemented):** Bug 11 requires `<Pagination .../>` rendered (not just imported). Bug 12 requires Toast globally mounted in layout.tsx.

**Metrics integration (v7):** Both init scripts now enable metrics collection (`~/.local/share/set-core/metrics/.enabled`). This captures per-hook injection quality data (query, relevance scores, dedup hits, duration) during benchmark runs.

**Recall-verify emphasis (v7):** with-memory.md CLAUDE.md strengthened to address v6 finding that memory-induced overconfidence led to worse C12 implementations (Run B used half the tokens but missed 3 bugs).

**Expected v7 impact:** Stronger tests should reveal whether memory genuinely helps with convention compliance and drift trap resolution. The v6 result where Run A beat Run B on drift traps may have been an artifact of weak test checks.

Note: The **synthetic benchmark** (MemoryProbe) showed +34% weighted improvement in SYN-05/06, but **SYN-07 showed 0% delta** (Mode A = Mode C = 97%). Root cause: Opus 4.6 implements C02 Developer Notes so thoroughly into code that "code-invisible" probes become code-readable. The +34% delta in SYN-05/06 was likely from a less-thorough C02 implementation (non-deterministic variance). See `benchmark/synthetic/syn-07-results.md` for analysis. The benchmark probe design needs hardening — current probes measure code-reading ability, not memory-dependent knowledge.

### SYN-07 Results (2026-02-20)

| Metric | Mode A (baseline) | Mode C (pre-seeded) | Delta |
|--------|------------------|-------------------|-------|
| Weighted score | 97% (57/59) | 97% (57/59) | 0% |
| Cat B (human override) | 9/9 | 9/9 | 0 |
| Cat C (debug knowledge) | 3/3 | 3/3 | 0 |
| Cat E (stakeholder) | 3/3 | 3/3 | 0 |
| Total time | 15m | 16m | +1m |

**Key finding**: The 0% delta is likely a combination of (1) Opus 4.6 being exceptionally good at implementing conventions into code, and (2) test probes not being truly code-invisible. Memory recall works perfectly (Mode C confirms), but the baseline doesn't need it because the code already contains the knowledge. Benchmark v3 needs probes that are genuinely impossible to derive from code inspection.

## 10. Post-Run Metrics Analysis

After both runs complete, analyze injection quality:

```bash
# Injection quality report (covers both runs if they share the same machine)
set-memory metrics --since 2d

# JSON output for scripting
set-memory metrics --since 2d --json

# Full dashboard (requires lib/dashboard.py from set-core)
PYTHONPATH=/path/to/set-core python3 /path/to/set-core/lib/dashboard.py
```

### What to look for

| Metric | Good | Bad | Why it matters |
|--------|------|-----|----------------|
| Avg relevance score | > 0.4 | < 0.3 | Low relevance = noise injections |
| Dedup hit rate | > 30% | < 10% | Low dedup = repeated injections |
| Citation count (Run B) | > 5 | 0 | Zero citations = agent ignoring memory |
| Injection count ratio (B/A) | 2-5x | > 10x | Too many injections = overhead |

### Cleanup after benchmark

```bash
# Disable metrics collection
set-memory metrics --disable

# Or remove the flag file directly
rm ~/.local/share/set-core/metrics/.enabled
```
