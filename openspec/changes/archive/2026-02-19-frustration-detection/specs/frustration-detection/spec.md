## ADDED Requirements

### Requirement: Bilingual emotion detection with simple trigger logic
The emotion detection module (`lib/frustration.py`) SHALL detect emotionally charged prompts in both English and Hungarian using ~30-35 regex patterns organized in two trigger groups (strong and medium). Hungarian patterns SHALL use character classes (e.g., `[aá]`, `[eé]`, `[oó]`) to match both accented and unaccented input. The module SHALL NOT use numeric scoring, weighted categories, or intensity multipliers.

#### Scenario: English agent-correction detected as strong
- **WHEN** user prompt contains "that's not what I asked"
- **THEN** detection returns level "high" with trigger group "agent-correction"

#### Scenario: Hungarian repetition + negation detected as medium
- **WHEN** user prompt contains "megint nem mukodik"
- **THEN** detection returns level "mild" (single medium trigger, no save)

#### Scenario: Two medium triggers combine to moderate
- **WHEN** user prompt contains "megint nem mukodik, mar mondtam"
- **THEN** detection returns level "moderate" (repetition-negation + temporal = 2 medium triggers)

#### Scenario: Hungarian without accents detected
- **WHEN** user prompt contains "mar sokadszorra rontod el"
- **THEN** detection matches the same patterns as "már sokadszorra rontod el"

#### Scenario: Neutral technical prompt not detected
- **WHEN** user prompt contains "please read the config file and check the settings"
- **THEN** detection returns level "none"

### Requirement: Three trigger groups
Patterns SHALL be organized into three groups with simple trigger logic:

**Strong triggers** (any single match = high):
- Agent-correction: patterns detecting user corrections of agent behavior (EN + HU)
- Expletives: strong/vulgar language (EN + HU)
- Giving-up: abandonment language (EN + HU)

**Medium triggers** (2+ matches = moderate, 1 match = mild):
- Repetition + negation combo
- Temporal frustration
- Escalation/absolutes
- Intensifiers (ALL CAPS 2+ words, excessive punctuation)

**Session boost**: when session history shows 3+ prior triggers, a single medium trigger escalates to moderate.

The trigger logic SHALL be:
- 1 strong → high (save + inject)
- 2+ medium → moderate (save + inject)
- 1 medium + session count >= 3 → moderate (save + inject)
- 1 medium → mild (inject only, no save)
- 0 triggers → none (no action)

#### Scenario: Single strong trigger fires immediately
- **WHEN** user prompt is "basszus, ez szar"
- **THEN** detection returns level "high"

#### Scenario: Single medium trigger is mild only
- **WHEN** user prompt is "this doesn't work again"
- **THEN** detection returns level "mild"

#### Scenario: Session boost escalates single medium to moderate
- **WHEN** session history count is 3 and user prompt matches 1 medium trigger
- **THEN** detection returns level "moderate" instead of "mild"

### Requirement: Agent-correction as primary strong trigger
The module SHALL include agent-correction patterns as strong triggers, detecting when the user corrects the agent's behavior. These patterns SHALL cover both English and Hungarian and SHALL include at minimum:
- Misunderstanding: "nem ezt kértem", "that's not what I asked", "not what I meant"
- Wrong target: "rossz fájlt", "wrong file", "wrong function"
- Blame/accusation: "miért nem olvastad el", "you didn't read", "te nem figyelsz", "you're not listening"
- Ignored input: "pont ezt mondtam", "I just said", "already told you this"

#### Scenario: Hungarian correction detected
- **WHEN** user prompt contains "nem ezt kértem, nézd meg újra"
- **THEN** detection returns level "high" with trigger "agent-correction"

#### Scenario: English blame detected
- **WHEN** user prompt contains "you didn't even read the file before editing it"
- **THEN** detection returns level "high" with trigger "agent-correction"

### Requirement: Full prompt saved as memory
When detection level is moderate or high, the module SHALL save the ENTIRE user prompt as a `Learning` memory via `set-memory remember`. The saved content SHALL use a prefix indicating the level:
- High: `"🔴 User frustrated (high): <entire prompt>"`
- Moderate: `"⚠️ User frustrated (moderate): <entire prompt>"`

The module SHALL NOT attempt to extract or strip frustration markers from the prompt.

#### Scenario: High-level prompt saved with prefix
- **WHEN** detection level is "high" for prompt "baszd meg, ez a deploy MEGINT nem megy!!"
- **THEN** memory is saved as `"🔴 User frustrated (high): baszd meg, ez a deploy MEGINT nem megy!!"`

#### Scenario: Mild-level prompt not saved
- **WHEN** detection level is "mild"
- **THEN** no memory is saved (inject only)

### Requirement: Immediate context injection to current agent
For ANY detection level (mild, moderate, or high), the hook SHALL add a warning to the `additionalContext` output. The warning SHALL include the detected trigger categories and an instruction to the agent to acknowledge the user's concern and be extra careful.

#### Scenario: Warning injected for moderate detection
- **WHEN** detection returns level "moderate" with triggers "repetition-negation, temporal"
- **THEN** additionalContext includes a warning mentioning the triggers and instructing careful behavior

#### Scenario: Warning injected for mild detection too
- **WHEN** detection returns level "mild" with 1 medium trigger
- **THEN** additionalContext includes a lighter warning (inject but no save)

#### Scenario: No injection for no detection
- **WHEN** detection returns level "none"
- **THEN** additionalContext does NOT include any frustration warning

### Requirement: Session frustration history
The module SHALL accept an optional `session_history` dict to track frustration across prompts. When the history shows 3+ prior triggers (any level above none), a single medium trigger SHALL escalate from mild to moderate. The module SHALL update the history in-place.

#### Scenario: Accumulated mild frustration escalates
- **WHEN** session history count is 3 and current prompt has 1 medium trigger
- **THEN** level escalates from "mild" to "moderate" (save + inject)

#### Scenario: Fresh session has no escalation
- **WHEN** session history is empty and current prompt has 1 medium trigger
- **THEN** level remains "mild" (inject only)

### Requirement: Detect function returns structured result
The `detect()` function SHALL accept a prompt string and optional session_history dict, returning a dict with:
- `level` (str): "none", "mild", "moderate", or "high"
- `triggers` (list[str]): names of matched trigger groups
- `save` (bool): whether a memory should be saved
- `inject` (bool): whether a context warning should be injected

#### Scenario: Result for high detection
- **WHEN** `detect("nem ezt kértem, rossz fájlt szerkeszted")` is called
- **THEN** result has level="high", triggers=["agent-correction"], save=True, inject=True

#### Scenario: Result for no detection
- **WHEN** `detect("please create a new file")` is called
- **THEN** result has level="none", triggers=[], save=False, inject=False

### Requirement: No external dependencies
The module SHALL use only Python standard library modules (`re`, `json`). No external packages SHALL be required.

#### Scenario: Module imports with stdlib only
- **WHEN** `lib/frustration.py` is imported in a clean Python environment
- **THEN** import succeeds without ImportError
