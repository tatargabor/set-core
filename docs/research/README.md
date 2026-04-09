# Research & Analysis

Technical deep-dives, competitive analysis, and benchmark investigations. This is where we document the *why* behind set-core's design choices — root-cause analyses, cost-optimization studies, framework comparisons, and empirical measurements from real E2E runs.

Dated documents capture a point-in-time investigation — the conclusions may be partially or fully superseded by later work. Check the date and the "Related commits" section at the bottom of each document to see what still applies.

| Document | Topic |
|---|---|
| [Token Optimization Analysis (2026-04-09)](token-optimization-analysis-2026-04-09.md) | Claude token usage deep-dive: session-restart bug, cache tier decode, efficiency rule impact, Max-plan vs API-key cost framing |
| [Template Divergence Elimination (2026-03-28)](template-divergence-elimination-2026-03-28.md) | Consumer template drift investigation and cleanup strategy |
| [Orchestration Output Divergence (2026-03-27)](orchestration-output-divergence-2026-03-27.md) | Cross-run structural divergence analysis for the same spec |
| [E2E Testing Strategy](e2e-testing-strategy.md) | Design and philosophy of the consumer E2E runner suite |
| [Benchmark Results](benchmark-results.md) | Memory system benchmarks (CraftBazaar + MemoryProbe synthetic) |
| [Shodh-Memory Audit](shodh-memory-audit.md) | Integration audit of shodh-memory capabilities |
| [Pi vs set-core](pi-mono-comparison.md) | Comparative analysis with Pi coding agent |
