---
name: write-spec
description: Interactive spec-writing assistant — guides users through creating a detailed, profile-driven specification. Detects project type, loads relevant sections from the profile system, enforces REQ-IDs and WHEN/THEN scenarios, generates modular output ready for orchestration.
---

# Write Spec — Profile-Driven Specification Generator

Guide the user through writing a detailed project specification. The spec is the most important input to the orchestration pipeline — spec quality directly determines output quality.

**Key principles:**
- Requirements describe WHAT, not HOW (no code blocks, no file paths)
- Every requirement gets a REQ-ID and at least one WHEN/THEN scenario
- Modular output for projects with 3+ features (main + per-feature files)
- Profile-driven: web projects get data model, seed, auth sections; others get core only

## Workflow

### Phase 0: Project Context Detection + Profile Loading

Before asking questions, detect the project type and load spec sections:

```bash
# Detect project type and tech stack
ls package.json pyproject.toml Cargo.toml go.mod Makefile docker-compose.yml 2>/dev/null
cat package.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('Name:', d.get('name','')); deps=list(d.get('dependencies',{}).keys()); print('Deps:', ', '.join(deps[:15]))" 2>/dev/null
ls prisma/schema.prisma 2>/dev/null && echo "Prisma detected"
ls docs/*.make docs/design.make docs/design-system.md 2>/dev/null && echo "Design files detected"
```

**Load profile sections:**
```bash
python3 -c "
from set_orch.profile_loader import resolve_profile
import json
p = resolve_profile('.')
sections = [{'id':s.id,'title':s.title,'description':s.description,'required':s.required,'phase':s.phase,'output_path':s.output_path,'prompt_hint':s.prompt_hint} for s in p.spec_sections()]
print(json.dumps(sections, indent=2))
" 2>/dev/null
```

If profile loading fails (set-core not installed as package), use these **fallback core sections**:
- overview (phase 1) — Project name, purpose, tech stack
- requirements (phase 5) — Main features with REQ-IDs and scenarios
- orchestrator_directives (phase 10) — Parallel hints, review gates
- verification_checklist (phase 11) — Auto-generated from requirements

If the tech stack is unfamiliar, use the Agent tool (Explore subagent) to investigate before proceeding.

### Phase 1-N: Iterate Through Sections

For each section from the profile (sorted by `phase`):

1. **Ask the user** using the section's `prompt_hint`
2. **Adapt questions** to what you detected:
   - If Prisma schema exists → show existing models for data_model section
   - If design files exist → offer to run `set-design-sync` for design_tokens
   - If i18n deps detected → pre-fill locale info
3. **Collect the answer** and draft the section content
4. **Enforce REQ-IDs** for requirement sections:
   - Format: `REQ-<DOMAIN>-<NN>` (e.g., `REQ-AUTH-01`, `REQ-CART-03`)
   - Domain slug comes from the feature name
5. **Enforce scenarios** for every requirement:
   ```markdown
   #### Scenario: <description>
   - **WHEN** <condition>
   - **THEN** <expected outcome>
   ```
6. If user says "skip" for a non-required section → note as skipped, move on
7. If user says "skip" for a required section → warn and ask to confirm

### Anti-Pattern Detection (before assembly)

Before writing files, review all content and warn about:

| Pattern | Action |
|---------|--------|
| Fenced code block in requirement | WARN: "Requirements describe WHAT, not HOW. Move code to design notes." Ask to keep or remove. |
| File paths (`src/`, `lib/`, `.ts`, `.tsx`) in requirement | WARN: "File paths lock implementation. Describe the behavior instead." |
| Requirement without WHEN/THEN scenario | BLOCK: "Every requirement needs a scenario. Add one for: [name]" |
| Placeholder seed data ("Product 1", "Test Item") | WARN: "Use realistic names. Generic placeholders produce generic apps." |

Code blocks and file paths are **warnings** (user can override). Missing scenarios are a **block** (must add before assembly).

### Assembly: Generate Output Files

**Check for existing spec:**
```bash
ls docs/spec.md 2>/dev/null && echo "EXISTING SPEC FOUND"
```
If `docs/spec.md` exists, ask: "A spec already exists. Overwrite, update in-place, or create alongside as docs/spec-v2.md?"

**Modular output** (web projects with 3+ features):
```
docs/
├── spec.md              ← Overview, tech stack, conventions, directives, verification checklist
├── features/
│   ├── auth.md          ← REQ-AUTH-01..N with scenarios
│   ├── catalog.md       ← REQ-CAT-01..N with scenarios
│   └── cart.md          ← REQ-CART-01..N with scenarios
└── catalog/             ← Structured seed data (web with Prisma only)
    ├── products.md      ← Product names, prices, descriptions
    └── users.md         ← Admin/test user credentials
```

**Single-file output** (small projects, 1-2 features):
```
docs/
└── spec.md              ← Everything in one file
```

**spec.md structure:**
```markdown
# [Project Name] — [Description]

## Tech Stack
[detected + confirmed]

## Data Model
[entities with fields — or link to feature files]

## Business Conventions
[currency, language, image strategy, etc.]

## Orchestrator Directives
```yaml
max_parallel: 3
review_before_merge: true
e2e_mode: per_change
```

## Verification Checklist
[auto-generated from requirements — one checkbox per requirement]

## Feature Specs
- [Auth & Accounts](features/auth.md)
- [Product Catalog](features/catalog.md)
- [Shopping Cart](features/cart.md)
```

**Feature file structure** (`docs/features/<name>.md`):
```markdown
# <Feature Name>

## Requirements

### REQ-<DOMAIN>-01: <Requirement title>
<Description of what the system should do>

#### Scenario: <Happy path>
- **WHEN** <condition>
- **THEN** <expected outcome>

#### Scenario: <Error case>
- **WHEN** <error condition>
- **THEN** <error handling>
```

### Verification Checklist Generation

Auto-generate from requirements:
```markdown
## Verification Checklist

### Auth
- [ ] REQ-AUTH-01: Registration form with email, password, name
- [ ] REQ-AUTH-02: Login with email/password, redirect to previous page
- [ ] REQ-AUTH-03: Protected routes redirect unauthenticated users

### Catalog
- [ ] REQ-CAT-01: Product listing with grid layout
- [ ] REQ-CAT-02: Product detail with variant selector
```

### Orchestrator Directives

Ask the user (or use defaults):

**Web projects:**
```yaml
max_parallel: 3          # How many changes run simultaneously
review_before_merge: true # Code review gate before merge
e2e_mode: per_change     # Each change owns its E2E tests
```

**Other projects:**
```yaml
max_parallel: 2
review_before_merge: true
```

### Final Summary

After writing files, show:
```
Spec generated:
  Main: docs/spec.md
  Features: docs/features/auth.md, docs/features/catalog.md, ...
  Seed data: docs/catalog/products.md, docs/catalog/users.md
  Requirements: 12 (all with REQ-IDs and scenarios)
  Verification items: 12

Next steps:
  1. Review the spec files — edit anything that needs refinement
  2. Start orchestration via dashboard or: /set:sentinel --spec docs/spec.md
```

## Guardrails

- **ALWAYS ask when uncertain** — use AskUserQuestion, never guess critical details
- **Adapt to project type** — don't force web sections on a CLI tool
- **Use Explore agents** — for unknown stacks, investigate before asking
- **Warn about anti-patterns** — code blocks, file paths, missing scenarios
- **REQ-IDs are mandatory** — every requirement gets one, format: `REQ-<DOMAIN>-<NN>`
- **Scenarios are mandatory** — every requirement needs at least one WHEN/THEN
- **Never skip data model** — this is the most common source of merge conflicts
- **Realistic seed data** — always push for real names, not "Test 1"
- **Profile fallback** — if profile loading fails, use core sections only
- **Don't overwrite silently** — if docs/spec.md exists, ask first
