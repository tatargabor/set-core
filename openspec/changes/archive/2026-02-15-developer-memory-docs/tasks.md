## 1. Developer Memory User Guide (`docs/developer-memory.md`)

- [x] 1.1 Create `docs/developer-memory.md` with header and "What is it?" intro (3 sentences)
- [x] 1.2 Write Quick Start section: `set-memory health`, `remember` with piped content, `recall` with query
- [x] 1.3 Write use case: "Avoiding repeated mistakes" — agent saves a failure as Learning, future agent recalls it
- [x] 1.4 Write use case: "Project decisions" — decision saved, recalled when related change starts
- [x] 1.5 Write use case: "Technical gotchas" — non-obvious behavior saved during implementation (mid-flow)
- [x] 1.6 Write use case: "Background context" — project context saved for onboarding future agents
- [x] 1.7 Write Memory Types section with comparison table (Decision / Learning / Context)
- [x] 1.8 Write OpenSpec Integration section: ASCII flow diagram showing all 6 phases with recall/remember annotations
- [x] 1.9 Write OpenSpec phase detail table: Phase, Hook type, What happens, Example
- [x] 1.10 Write GUI section: [M] button, Browse dialog, Remember Note dialog, hook installation menu
- [x] 1.11 Write Ambient Memory section: how proactive memory works outside OpenSpec, when agents save/don't save
- [x] 1.12 Write CLI Reference section: all `set-memory` and `set-memory-hooks` subcommands with flags and examples
- [x] 1.13 Write Setup section: pip install, hooks install, graceful degradation note
- [x] 1.14 Write Architecture appendix: ASCII diagram showing layer stack (agent session → CLI → shodh-memory/RocksDB)

## 2. Update `docs/readme-guide.md`

- [x] 2.1 Expand Section 6 (Features) Developer Memory instructions: overview paragraph, 3 concrete examples, CLI commands, link to deep-dive doc, experimental note
- [x] 2.2 Add Section 13 (Use Cases) Developer Memory instructions: cross-session recall scenario, OpenSpec integration scenario, "When to use what" table entry
- [x] 2.3 Verify Section 8 (CLI Reference) Developer Memory category lists all `set-memory` and `set-memory-hooks` commands
- [x] 2.4 Update the mandatory section order in Section numbering if changed (verify current README matches guide)

## 3. Update `README.md`

- [x] 3.1 Expand the Developer Memory subsection in Features (Section 6): overview paragraph, concrete examples, link to `docs/developer-memory.md`
- [x] 3.2 Add a "Developer Memory" use case in Use Cases (Section 13) with cross-session example and OpenSpec integration
- [x] 3.3 Add memory entry to the "When to use what" summary table
- [x] 3.4 Verify CLI Reference Developer Memory table is complete against `set-memory --help` output
