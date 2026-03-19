## MODIFIED Requirements

### Requirement: Proactive Context Noise Prevention
The `set-memory proactive` command SHALL pass `auto_ingest=False` to the shodh-memory `proactive_context()` API. Working-state context strings MUST NOT be saved as permanent memories.

#### Scenario: Proactive recall without auto-ingest
- **WHEN** `set-memory proactive "Working on change: X"` is called
- **THEN** no `Conversation` type memory SHALL be created from the context string
- **THEN** the proactive recall results SHALL still be returned normally

### Requirement: Change Tag Propagation
All memories saved by `wt-hook-memory-save` transcript extraction SHALL include a `change:<name>` tag. The change name MUST be injected at the bash level, not dependent on the LLM including it.

#### Scenario: Transcript extraction saves memory with change tag
- **WHEN** the transcript extraction LLM outputs `Learning|error,shopping-cart|some insight`
- **THEN** the memory SHALL be saved with tags `phase:auto-extract,source:hook,change:shopping-cart,error,shopping-cart`

#### Scenario: Multiple change names in session
- **WHEN** the session involves multiple change names (comma-separated in `$change_names`)
- **THEN** the first change name SHALL be used for the `change:` tag

### Requirement: Code Map Safety Net Reliability
The code-map safety net SHALL scan all commits since the last marker (not just the latest commit). It SHALL also check the `openspec/changes/` directory for active change names when commit message parsing fails to extract a change name.

#### Scenario: Code map generated from multi-commit change
- **WHEN** a change involves 3 commits with different message formats
- **THEN** the safety net SHALL aggregate changed files from all 3 commits for code-map generation

#### Scenario: Change name from openspec directory
- **WHEN** a commit message does not follow the `change-name: description` format
- **THEN** the safety net SHALL check `openspec/changes/` for active change directories and use the most likely match

### Requirement: Benchmark TRAP-F Explicit Requirement
The `benchmark/changes/07-stock-rethink.md` change definition SHALL include an explicit acceptance criterion: "Coupon `currentUses` MUST be incremented inside the checkout-confirm transaction, NOT at coupon-apply time."

#### Scenario: TRAP-F explicit in change definition
- **WHEN** the agent reads `07-stock-rethink.md`
- **THEN** it SHALL find an explicit requirement about coupon `currentUses` increment timing
