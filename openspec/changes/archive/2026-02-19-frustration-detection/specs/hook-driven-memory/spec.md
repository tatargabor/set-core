## MODIFIED Requirements

### Requirement: Hooks replace inline memory instructions in skills and commands
All `<!-- set-memory hooks -->` blocks (including `hooks-midflow`, `hooks-remember`, `hooks-reflection`, `hooks-save` variants) SHALL be removed from OpenSpec skill SKILL.md files and opsx command .md files. The 5-layer hook system handles recall (L2 on every prompt) and save (L5 on every stop) automatically — skills SHALL NOT contain manual `set-memory recall` or `set-memory remember` instructions.

The UserPromptSubmit handler SHALL additionally perform emotion detection on the user's prompt before proactive recall. When emotion is detected:
- **Moderate or high**: save the entire prompt as a `Learning` memory with `frustration,recurring` tags (moderate) or `frustration,high-priority` tags (high), AND inject a warning into `additionalContext`
- **Mild**: inject a warning into `additionalContext` only (no save)
- **None**: proceed with normal proactive recall, no additional output

The handler SHALL maintain a `frustration_history` key in the session dedup cache to track emotional prompt count across the session.

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
