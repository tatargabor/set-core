## Why

SYN-07 proved that the MemoryProbe benchmark measures the wrong thing. Opus 4.6 implements C02 Developer Notes so thoroughly into code that all "code-invisible" probes become code-readable by C03+. Result: Mode A (baseline) = Mode C (pre-seeded memory) = 97%. Delta = 0%. The benchmark measures code-reading ability, not memory-dependent knowledge.

Six benchmark runs (SYN-01 through SYN-07) show the synthetic benchmark cannot reliably differentiate memory from no-memory. The +34% delta in SYN-05/06 was a lucky artifact of a less-thorough C02 implementation. Memory's real value is in the **negative space** — knowledge that code CANNOT carry: why decisions were made, what NOT to do, failed experiments, user corrections, and cross-session debug patterns.

## What Changes

- Archive current MemoryProbe v2 benchmark as "v2-archived" with retrospective document explaining why it was retired
- Create new benchmark retrospective document (`benchmark/synthetic/RETROSPECTIVE.md`) analyzing all 7 runs and the fundamental design flaw
- Design new probe types that test genuinely code-invisible knowledge:
  - **Negative constraints**: "Don't do X" (no code trace when X is absent)
  - **Rationale probes**: "Why was X chosen over Y?" (code shows X, not why)
  - **Revert knowledge**: "We tried Y, it failed" (no trace after revert)
  - **User corrections**: Multi-turn human preference that overrides defaults
- Update existing specs (probe-categories, trap-design, scoring-system) with delta specs reflecting the pivot

## Capabilities

### New Capabilities
- `benchmark-retrospective`: Post-mortem analysis document for SYN-01 through SYN-07, documenting what was learned and why the approach was flawed

### Modified Capabilities
- `probe-categories`: Redefine categories around code-invisible knowledge types instead of convention weight
- `trap-design`: New trap types that test negative constraints, rationale, and revert knowledge
- `scoring-system`: Adapt scoring for new probe types that may require semantic checking (not just grep)

## Impact

- `benchmark/synthetic/` — retrospective doc, archived v2 marker
- `benchmark/synthetic/run-guide.md` — link to retrospective, v3 design direction
- `openspec/specs/probe-categories/` — delta spec with new categories
- `openspec/specs/trap-design/` — delta spec with new trap types
- `openspec/specs/scoring-system/` — delta spec for semantic scoring
- No code changes — this is a documentation and design change
