## MODIFIED Requirements

### Requirement: Hooks replace inline memory instructions in skills and commands
All `<!-- wt-memory hooks -->` blocks (including `hooks-midflow`, `hooks-remember`, `hooks-reflection`, `hooks-save` variants) SHALL be removed from OpenSpec skill SKILL.md files and opsx command .md files. The 5-layer hook system handles recall (L2 on every prompt) and save (L5 on every stop) automatically — skills SHALL NOT contain manual `wt-memory recall` or `wt-memory remember` instructions.

The UserPromptSubmit handler SHALL additionally perform emotion detection on the user's prompt before proactive recall. When emotion is detected:
- **Moderate or high**: save the entire prompt as a `Learning` memory with `frustration,recurring` tags (moderate) or `frustration,high-priority` tags (high), AND inject a warning into `additionalContext`
- **Mild**: inject a warning into `additionalContext` only (no save)
- **None**: proceed with normal proactive recall, no additional output

The handler SHALL maintain a `frustration_history` key in the session dedup cache to track emotional prompt count across the session.

**All text truncation in the UserPromptSubmit handler SHALL use character-level operations (`cut -c1-N`) instead of byte-level operations (`head -c N`).** This applies to emotion save content (line 583), recall query with change name (line 600), and recall query without change name (line 602).

#### Scenario: Frustrated prompt triggers save and injection
- **WHEN** UserPromptSubmit fires with prompt "nem ezt kértem, rossz fájlt szerkeszted!!"
- **THEN** emotion detection returns "high" (agent-correction), memory is saved with `frustration,high-priority` tags, AND additionalContext includes a warning to the current agent

#### Scenario: Mildly frustrated prompt injects only
- **WHEN** UserPromptSubmit fires with prompt "this still doesn't work"
- **THEN** emotion detection returns "mild" (1 medium trigger), additionalContext includes a lighter warning, no memory is saved

#### Scenario: Non-frustrated prompt proceeds normally
- **WHEN** UserPromptSubmit fires with prompt "please read the config file"
- **THEN** emotion detection returns "none", no injection, normal proactive recall proceeds

#### Scenario: Session frustration history persists and escalates
- **WHEN** three consecutive prompts in the same session trigger mild detection
- **THEN** the fourth prompt with a single medium trigger escalates to moderate (save + inject)

#### Scenario: Hungarian prompt truncation preserves character boundaries
- **WHEN** UserPromptSubmit fires with a 600-character Hungarian prompt containing "működik" at position 498
- **AND** the 500-char truncation limit is applied for emotion save
- **THEN** the truncated content SHALL NOT contain orphaned bytes from the "ű" character (0xc5 0xb1)
- **AND** the saved memory SHALL be valid UTF-8

### Requirement: CLAUDE.md uses "Persistent Memory" pattern
The CLAUDE.md "Proactive Memory" section SHALL be rewritten to a "Persistent Memory" section that:
1. Explains hooks handle recall and save automatically (agent does not need to manage it)
2. Documents `wt-memory remember` as an emphasis tool for HIGH IMPORTANCE items only
3. Documents `wt-memory forget` for correcting wrong memories
4. Does NOT contain manual `wt-memory recall` instructions
5. Does NOT contain "When to save" / "When NOT to save" rules (L5 handles this)
6. Does NOT contain "Recall before major work" instructions (L2 handles this)
7. Does NOT contain deduplication notes about skill hooks (no skill hooks exist)

### Requirement: Skills retain full functionality without memory hooks
After removing inline memory hooks, all OpenSpec skills (apply, continue, ff, explore, archive, verify, sync, new) SHALL continue to function identically for their primary purpose. Memory operations that were done by inline hooks are now handled by the automatic hook layer.
