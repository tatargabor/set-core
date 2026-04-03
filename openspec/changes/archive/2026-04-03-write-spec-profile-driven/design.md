## Context

The write-spec skill is a Claude Code skill (SKILL.md markdown) that guides users through spec creation. It currently has 11 hardcoded phases producing a flat `docs/spec.md`. The profile system (`ProjectType` ABC) already provides `planning_rules()` for the decomposer — we extend it with `spec_sections()` for the write-spec skill.

The modular spec structure (main + features/ + catalog/) used in successful E2E runs consistently produces higher merge rates. We adopt this as the default output format for web projects.

## Goals / Non-Goals

**Goals:**
- write-spec adapts to project type (web gets seed/prisma sections, CLI gets different ones)
- Output is modular (main + features/ + catalog/) for web projects with 3+ features
- Anti-patterns caught before the spec is written
- REQ-IDs and scenarios are mandatory

**Non-Goals:**
- Changing the decomposer (it already parses REQ-IDs when present)
- Implementing non-web profiles (CLI, API — future work)
- Automated spec validation gate in the orchestrator (manual review is fine for now)

## Decisions

### D1: spec_sections() returns section descriptors

```python
@abstractmethod
def spec_sections(self) -> list[SpecSection]:
    """Return spec sections for write-spec skill."""

@dataclass
class SpecSection:
    id: str              # e.g., "data_model"
    title: str           # e.g., "Data Model"
    description: str     # What to ask/generate
    required: bool       # Block assembly if missing
    phase: int           # Order in the write-spec flow
    output_path: str     # Where to write (e.g., "docs/features/{name}.md")
    prompt_hint: str     # Suggested question for the user
```

CoreProfile returns 4 core sections. WebProjectType extends with 7 web sections. The skill reads `profile.spec_sections()` and iterates in phase order.

**Why in the profile?** The profile already knows the tech stack. A CLI project doesn't need Prisma seed data. The profile is the right extension point.

### D2: Skill reads profile at Phase 0

The write-spec skill detects the project type (Phase 0 already does this) and then loads sections:

```bash
# In Phase 0, after detection:
python3 -c "
from set_orch.profile_loader import resolve_profile
p = resolve_profile('$PWD')
import json
sections = [s.__dict__ for s in p.spec_sections()]
print(json.dumps(sections))
"
```

This gives the skill a JSON list of sections to iterate through. If the profile can't be loaded (no set-core installed), fall back to the current hardcoded sections.

### D3: Modular output for web projects

When the project type is `web` and the user defines 3+ features:

```
docs/
├── spec.md              ← Overview, conventions, directives, verification checklist
├── features/
│   ├── auth.md          ← REQ-AUTH-01..N with scenarios
│   ├── catalog.md       ← REQ-CAT-01..N with scenarios
│   └── cart.md          ← REQ-CART-01..N with scenarios
└── catalog/             ← Structured seed data (web only)
    ├── products.md      ← Product names, prices, descriptions
    └── users.md         ← Admin/test user credentials
```

For small projects (1-2 features), everything stays in `docs/spec.md`.

### D4: Anti-pattern detection is advisory, not blocking

Code blocks and file paths produce **warnings** (user can override). Missing scenarios produce a **block** (must add before assembly). This balances strictness with usability.

### D5: REQ-ID format matches decomposer expectations

The decomposer already looks for `REQ-*` patterns in spec text. Using `REQ-<DOMAIN>-<NN>` ensures automatic recognition. The domain slug comes from the feature file name (e.g., `features/auth.md` → `REQ-AUTH-*`).

## Risks

- **[Risk] Profile not available** → write-spec should work without set-core installed. Fall back to hardcoded core sections. The skill already runs `ls package.json` for detection — add graceful fallback if `python3 -c "from set_orch..."` fails.
- **[Risk] Existing specs don't match new format** → Old flat specs still work with the decomposer. This is additive, not breaking.
- **[Risk] Too many questions** → Web profile adds 7 sections on top of 4 core. But most are quick (i18n, auth, design → 1 question each). The heavy ones (features, seed) are where quality matters most.
