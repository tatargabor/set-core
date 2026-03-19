# MemoryProbe v2 Run Guide

## Prerequisites

- Node.js v18+
- Claude Code CLI (`claude`)
- `set-memory` (for modes B, C, and D)
- ~2 GB disk space (per run)
- Internet for npm install

## Quick Comparison (Mode A vs Mode B)

```bash
# Bootstrap both runs
cd benchmark/synthetic
./scripts/init.sh --mode a --target ~/bench/probe-a
./scripts/init.sh --mode b --target ~/bench/probe-b

# Run both (can run in parallel on different terminals)
./scripts/run.sh ~/bench/probe-a &
./scripts/run.sh ~/bench/probe-b &
wait

# Score and compare
./scripts/score.sh --compare ~/bench/probe-a ~/bench/probe-b
```

Total time: ~30-35 minutes (parallel) or ~60-70 minutes (sequential).

## n=3 Run Protocol (Recommended for Publication)

For publishable results, run each mode **3 times** and use **median** scoring.

```bash
cd benchmark/synthetic

# Mode A: 3 runs
for i in 1 2 3; do
  ./scripts/init.sh --mode a --target ~/bench/probe-a-$i
  ./scripts/run.sh ~/bench/probe-a-$i
done

# Mode B: 3 runs
for i in 1 2 3; do
  ./scripts/init.sh --mode b --target ~/bench/probe-b-$i
  ./scripts/run.sh ~/bench/probe-b-$i
done

# Score all runs
for i in 1 2 3; do
  echo "=== Mode A Run $i ==="
  ./scripts/score.sh ~/bench/probe-a-$i --json > ~/bench/score-a-$i.json
  ./scripts/score.sh ~/bench/probe-a-$i

  echo "=== Mode B Run $i ==="
  ./scripts/score.sh ~/bench/probe-b-$i --json > ~/bench/score-b-$i.json
  ./scripts/score.sh ~/bench/probe-b-$i
done

# Compare best median pair
./scripts/score.sh --compare ~/bench/probe-a-2 ~/bench/probe-b-2
```

**Median selection**: Sort each mode's 3 weighted scores. Use the middle run (run 2 after sorting) for the comparison.

Total time: ~3-3.5 hours (sequential). Can parallelize runs across terminals.

## Mode A: Baseline (No Memory)

```bash
./scripts/init.sh --mode a --target ~/bench/probe-a
./scripts/run.sh ~/bench/probe-a
./scripts/score.sh ~/bench/probe-a
```

What happens:
1. Bootstraps a clean project at `~/bench/probe-a`
2. Runs 5 Claude sessions (C01-C05), each in fresh context
3. Scores convention compliance on C03-C05 (35 probes across 5 categories)

Expected weighted score: 30-50% (Category A passes + some D from code reading)

## Mode B: Full Memory (Save + Recall)

```bash
./scripts/init.sh --mode b --target ~/bench/probe-b
./scripts/run.sh ~/bench/probe-b
./scripts/score.sh ~/bench/probe-b
```

What happens:
1. Same as Mode A, but with `set-memory` enabled
2. C01 session establishes conventions in code
3. C02 session introduces Developer Notes with 13 knowledge items (B1-B4, C1-C3, D1-D3, E1-E3) — agent should save these
4. C03-C05 sessions recall conventions before implementing

Expected weighted score: 75-100% (all categories, depends on save/recall quality)

## Mode C: Pre-Seeded (Recall Only)

```bash
./scripts/init.sh --mode c --target ~/bench/probe-c
./scripts/run.sh ~/bench/probe-c --start 3 --end 5
./scripts/score.sh ~/bench/probe-c
```

What happens:
1. Bootstraps project with 13 convention memories pre-seeded (B1-B4, C1-C3, D1-D3, E1-E3)
2. Skips C01-C02 (conventions already in memory)
3. Runs only C03-C05 — tests pure recall

Expected weighted score: 85-100% (perfect memories, tests recall fidelity)

Time: ~15-20 minutes.

## Mode D: Rules (Deterministic Constraints)

```bash
./scripts/init.sh --mode d --target ~/bench/probe-d
./scripts/run.sh ~/bench/probe-d --start 3 --end 5
./scripts/score.sh ~/bench/probe-d
```

What happens:
1. Bootstraps project with `.claude/rules.yaml` containing all 17 rules (A1-A4, B1-B4, C1-C3, D1-D3, E1-E3)
2. Deploys set-memory hooks so rules are injected as `MANDATORY RULES` on every prompt
3. Skips C01-C02 (conventions already in rules)
4. Runs only C03-C05 — tests deterministic rule injection

Expected weighted score: 85-100% (deterministic injection; may miss rules whose topics don't match the prompt)

Time: ~15-20 minutes.

### Mode C vs Mode D Comparison

```bash
./scripts/init.sh --mode c --target ~/bench/probe-c
./scripts/init.sh --mode d --target ~/bench/probe-d

./scripts/run.sh ~/bench/probe-c --start 3 --end 5 &
./scripts/run.sh ~/bench/probe-d --start 3 --end 5 &
wait

./scripts/score.sh --compare ~/bench/probe-c ~/bench/probe-d
```

This comparison answers: **does deterministic rule injection outperform probabilistic memory recall?**

## Scoring

### What Gets Scored

~35 convention probes across C03-C05, organized into 5 weighted categories:

| Category | Weight | Probes | What it tests |
|----------|--------|--------|---------------|
| A: Code-readable | x1 | A1 pagination, A2 ID prefix, A3 ok wrapper, A4 date helper | Conventions visible in C01 code |
| B: Human override | x2 | B1 dot.notation, B2 result key, B3 order param, B4 removedAt | C02 corrections that override C01/spec |
| C: Debug knowledge | x3 | C1 busy_timeout, C2 nanoid(16), C3 body-parser limit | Invisible in code — only in memory |
| D: Architecture | x2 | D1 flat categories, D2 db query layer, D3 no try-catch | Visible in code structure, rationale is not |
| E: Stakeholder | x3 | E1 ISO 8601 dates, E2 bulk max 100, E3 list max 1000 | External constraints — invisible in code |

| Change | Probes | Categories Tested |
|--------|--------|-------------------|
| C03 (Comments & Activity) | ~9 | A1, A2, A3, B1, B2, D2, D3 |
| C04 (Dashboard & Export) | ~13 | A1(x2), A2, A3, A4, B1, B2, B3, C1, D1, D2, E1 |
| C05 (Bulk Operations) | ~13 | A1, A2, A3, B1, B2, B4, C2, C3, D2, E2, E3 |

### Weighted Scoring

```
Raw    = A_pass×1 + B_pass×2 + C_pass×3 + D_pass×2 + E_pass×3
Max    = A_total×1 + B_total×2 + C_total×3 + D_total×2 + E_total×3
Score  = Raw / Max × 100%
```

### Why This Weighting?

- **A (x1)**: Code-readable conventions. Both baseline and memory agents can learn these from C01 code. Low discriminative value.
- **B (x2)**: Human override conventions. C02 Developer Notes correct or extend C01 patterns. Memory agents that recall these have an advantage, but some B traps (like B4 removedAt) are partially visible in code.
- **C (x3)**: Debug knowledge. `busy_timeout`, `nanoid(16)`, `body-parser limit` — these are impossible to derive from code. Only agents with memory of the C02 debug findings will know them.
- **D (x2)**: Architecture decisions. The structure is visible in code (db/ layer, middleware), but the rationale (why flat categories, why no inline SQL) is only in memory.
- **E (x3)**: Stakeholder constraints. ISO 8601 for mobile apps, bulk max 100, list max 1000 — external requirements invisible in code. Only memory agents know these.

### Expected Scores

| Mode | Cat A (x1) | Cat B (x2) | Cat C (x3) | Cat D (x2) | Cat E (x3) | Weighted |
|------|-----------|-----------|-----------|-----------|-----------|----------|
| A (no memory) | 7-9/10 | 2-4/8 | 0/3 | 3-5/5 | 0-1/3 | 30-50% |
| B (full memory) | 9-10/10 | 6-8/8 | 2-3/3 | 4-5/5 | 2-3/3 | 75-100% |
| C (pre-seeded) | 8-10/10 | 7-8/8 | 2-3/3 | 4-5/5 | 2-3/3 | 85-100% |
| D (rules) | 9-10/10 | 6-8/8 | 1-3/3 | 4-5/5 | 2-3/3 | 75-100% |

**WARNING — SYN-07 showed Mode A = 97%, same as Mode C (0% delta).**
This happens when C02 is implemented thoroughly — all "code-invisible" conventions become code-visible. The expected scores above assume a less-thorough C02 implementation (which happened in SYN-05/06). Results are **non-deterministic** depending on how well the C02 agent implements Developer Notes into code. See `syn-07-results.md` for details.

**Key signals:**
- Categories C and E provide the strongest signal (code-invisible, high weight)
- Category B provides the spec-vs-memory conflict signal
- Category A is the baseline — both modes should pass most A probes
- The expected delta between Mode A and Mode B should be **>30%** (but may be 0% if C02 is thorough)

### Known Limitations (from SYN-07)

- **Code persistence defeats memory**: When Opus 4.6 implements C02 conventions into code, subsequent sessions read them from code, not memory
- **Non-deterministic C02 quality**: The baseline score ranges from 45% (SYN-05/06) to 97% (SYN-07) depending on how thorough the C02 implementation is
- **score.sh server bug**: The Node server's event loop empties and exits immediately — use inline test results from run.sh, not score.sh
- **Benchmark v3 needed**: Probes should test knowledge genuinely impossible to derive from code inspection (negative constraints, rationale-dependent decisions, conflict resolution)

### Automated Scoring

```bash
# Single run
./scripts/score.sh ~/bench/probe-a

# Compare two runs
./scripts/score.sh --compare ~/bench/probe-a ~/bench/probe-b

# JSON output (for scripts)
./scripts/score.sh ~/bench/probe-a --json
```

## Manual Run (Per-Session)

Instead of the automated runner, run each session manually:

```bash
cd ~/bench/probe-a

# Session 1
claude --dangerously-skip-permissions \
  -p "Implement docs/changes/01-event-crud.md. Read it first, then read docs/project-spec.md. Start server with: PORT=3000 node src/server.js & — then run: bash tests/test-01.sh 3000. Fix any failures." \
  --max-turns 30

git add -A && git commit -m "Change 01 complete"

# Session 2 (fresh context!)
claude --dangerously-skip-permissions \
  -p "Implement docs/changes/02-tags-filtering.md. Read it and docs/project-spec.md first. Start server, run tests/test-02.sh 3000." \
  --max-turns 30

git add -A && git commit -m "Change 02 complete"

# ... repeat for sessions 3-5
```

## Troubleshooting

**Server won't start**: Check if port is in use: `lsof -i :3000`. Kill: `pkill -f "node src/server.js"`.

**Test script hangs**: Server may not be running. Start it manually: `node src/server.js &`

**Memory not working (Mode B)**: Check `set-memory health`. Verify hooks: `ls .claude/hooks/`.

**Score is 0%**: Tests may not find the server running. score.sh starts the server automatically, but if port 3000 is in use, it'll skip. Kill existing processes first.

**Claude session times out**: Increase `--max-turns` in run.sh (default 30 for baseline, 50 for memory mode).

**C/E probes all fail (Mode A)**: This was expected in SYN-05/06, but **SYN-07 showed Mode A can pass all C/E probes** if C02 is implemented thoroughly. See Known Limitations above.

**score.sh shows very low score but inline tests pass**: The Node server's event loop empties and exits immediately after `app.listen()`. score.sh can't keep it alive. Use inline test results from run.sh output — those are reliable.

## C-first Execution Protocol (Recommended)

When validating memory system changes, use the C-first protocol instead of running A+B in parallel:

```
Step 1: Mode C (pre-seeded recall, ~15 min)
  → Tests recall quality without save dependency
  → GATE: C-category probes > 0? Weighted > 75%?
  → If NO: debug hooks, don't waste time on A/B

Step 2: Mode A (baseline, ~30 min)
  → Tests what the baseline achieves
  → COMPARE: A vs C delta

Step 3 (optional): Mode B (full save+recall, ~30 min)
  → Tests end-to-end including save
  → COMPARE: B ≈ C? Then save works too
```

This saves ~15-30 min per failed run by catching recall failures early.

## Results History

| Run | Mode A | Mode B/C | Delta | Notes |
|-----|--------|----------|-------|-------|
| SYN-01 | n/a | n/a | ~0% | Pre-v8 design |
| SYN-02 | 83% | 83% | 0% | Code persistence + probe leak |
| SYN-03 | 45% | 45% | 0% | Agent never saved to memory |
| SYN-04 | 45% | 38% | -7% | Tainted run |
| SYN-05 | 45% | 79% | +34% | Post-session extraction works |
| SYN-06 | 45% | 79% | +34% | Hook-driven recall, -20% tokens |
| SYN-07 | **97%** | **97% (C)** | **0%** | Code persistence wins — test design flaw |

## Cleanup

```bash
rm -rf ~/bench/probe-a ~/bench/probe-b ~/bench/probe-c ~/bench/probe-d
# For n=3 runs:
rm -rf ~/bench/probe-a-{1,2,3} ~/bench/probe-b-{1,2,3} ~/bench/score-*.json
```
