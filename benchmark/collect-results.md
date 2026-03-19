# Results Collection — Agent-Assisted Evaluation

Use this guide (or paste it as a prompt to Claude) to semi-automate the post-run evaluation. A Claude session reads both repos' data and generates the comparison report.

## Setup

Start a Claude session in a directory that can access both repos:
```bash
cd ~/benchmark
claude
```

## Prompt

Paste the following prompt to start agent-assisted evaluation:

---

I've completed a shodh-memory benchmark with two runs:
- **Run A** (baseline, no memory): `~/benchmark/run-a/craftbazaar/`
- **Run B** (with memory): `~/benchmark/run-b/craftbazaar/`

Both implemented the CraftBazaar project (6 sequential changes). I need you to collect data, analyze the results, and generate a comparison report.

### Step 1: Collect automatic data from both runs

For each run, collect:
```bash
# In each repo:
cd ~/benchmark/<run>/craftbazaar

# Check which changes completed
openspec list --json

# Get iteration history
set-loop history

# Read agent-written status files
cat results/*.json

# Get git log
git log --oneline --format="%h %ai %s"
```

For Run B additionally:
```bash
cd ~/benchmark/run-b/craftbazaar
set-memory list --json
set-memory status
```

### Step 2: Read session transcripts

Read the transcripts to understand what happened in each run:
```bash
cat ~/benchmark/run-a/craftbazaar/.claude/ralph-loop.log
cat ~/benchmark/run-b/craftbazaar/.claude/ralph-loop.log
```

For each change in each run, identify:
- How many iterations were spent
- Dead ends (agent tried something, backtracked)
- Repeated mistakes (same error from a previous change)
- Design rework (had to modify previous change's code)
- Whether tests passed on first try

For Run B, also identify:
- Each `set-memory recall` call and whether results influenced behavior
- Each `set-memory remember` call and the quality of what was saved

### Step 3: Read evaluator notes

The evaluator notes for each change are in:
```
<set-core-root>/benchmark/changes/01-product-catalog.md
<set-core-root>/benchmark/changes/02-shopping-cart.md
<set-core-root>/benchmark/changes/03-multi-vendor.md
<set-core-root>/benchmark/changes/04-discounts.md
<set-core-root>/benchmark/changes/05-checkout.md
<set-core-root>/benchmark/changes/06-order-workflow.md
```

Read the "Evaluator Notes" section (below the marker line) for each change. Use the trap documentation and memory predictions to guide your analysis.

### Step 4: Generate the comparison report

Using the template at `<set-core-root>/benchmark/templates/comparison-report.md`, fill in:

1. **Aggregate metrics** table (sum across all changes per run)
2. **Per-change comparison** tables with key observations
3. **Narrative findings** — where memory helped most, where it didn't, surprises
4. **Diagnostic summary** — memory gap analysis (see `<set-core-root>/benchmark/diagnostic-framework.md`)
5. **Conclusion** — overall assessment with evidence

Save the completed report to `~/benchmark/results/comparison-report.md`.

### Step 5: Generate per-change annotations

For each change × run combination (12 total), fill out the session annotation template at `<set-core-root>/benchmark/templates/session-annotation.md`.

Save to `~/benchmark/results/annotations/run-<a|b>-change-<NN>.md`.

---

## What to Review

After the agent generates the report, verify:

1. **Metric accuracy**: Cross-check iteration counts with `set-loop history` output
2. **Dead end identification**: Verify by reading the transcript sections
3. **Memory event accuracy**: Verify recall/save counts against Run B transcript
4. **Trap assessments**: Check against evaluator notes — did the agent correctly identify which traps were encountered?
5. **Narrative objectivity**: Ensure findings are evidence-based, not speculative

## Tips

- The agent may need multiple rounds to process both transcripts (they can be large)
- Focus the agent on one change at a time if transcripts are too long
- The agent's analysis of "useful recalls" is subjective — verify the critical ones manually
- The diagnostic gap analysis is the most valuable output — spend extra time verifying it
