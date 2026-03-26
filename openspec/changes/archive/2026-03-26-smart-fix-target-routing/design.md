## Fix Target Decision

The investigation agent's `/opsx:ff` already produces a proposal.md. We add a required field to the proposal:

```markdown
## Fix Target
- **Target:** framework | consumer | both
- **Reasoning:** Would this bug affect other projects? [yes/no and why]
```

The investigator parses this field from the proposal. If missing, falls back to keyword heuristic.

## Three-Way Routing

```
Investigation → proposal.md with fix_target
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   framework     consumer      both
        │           │           │
   set-core      local repo   set-core THEN local
   /opsx:ff      /opsx:apply  /opsx:ff + deploy
   /opsx:apply                + local /opsx:apply
   deploy back
```

## "both" Flow

1. Investigation creates proposal with `fix_target: both`
2. Fixer creates TWO openspec changes:
   - `fix-{id}-framework` in set-core → template/rule fix
   - `fix-{id}-consumer` in consumer → apply the fix locally
3. Framework fix runs first (set-core), then `set-project init` deploys
4. Consumer fix runs second (apply locally with updated framework)

In practice, most "both" cases are framework-only — once the template is fixed, the next deploy fixes the consumer. The consumer fix is only needed for already-deployed broken state.

## Investigation Prompt Addition

Add to INVESTIGATION_PROMPT:

```
## Fix Target Classification

Determine where the fix belongs:
- **framework** — This bug would affect ANY project using set-core (merger bug, gate bug, template defect). Fix goes in set-core.
- **consumer** — This bug is specific to THIS project (merge conflict, missing file, wrong config). Fix goes in the local repo.
- **both** — Root cause is in set-core (template/rule) but the symptom also needs a local fix in this project.

Add a "## Fix Target" section to your proposal with your classification and reasoning.
```

## Parsing

The `_parse_proposal()` looks for:

```python
# Look for explicit fix target in proposal
target_match = re.search(r'\*\*Target:\*\*\s*(framework|consumer|both)', proposal)
if target_match:
    fix_target = target_match.group(1)
```

Falls back to existing keyword heuristic if not found.
