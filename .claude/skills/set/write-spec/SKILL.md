---
name: write-spec
description: Interactive spec-writing assistant — guides users through creating a detailed specification for any project type (web, API, CLI, pipeline). Detects project context, asks targeted questions, generates a structured spec.md ready for orchestration.
---

# Write Spec — Interactive Specification Generator

Guide the user through writing a detailed project specification. The spec is the most important input to the orchestration pipeline — spec quality directly determines output quality.

**IMPORTANT**: This skill works for ANY project type — web apps, APIs, CLI tools, data pipelines, hybrid systems. Adapt your questions to the detected project type. Do NOT assume web.

## Workflow

### Phase 0: Project Context Detection

Before asking any questions, investigate the project:

```bash
# Detect project type and tech stack
ls package.json pyproject.toml Cargo.toml go.mod Makefile docker-compose.yml 2>/dev/null
cat package.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('Name:', d.get('name','')); deps=list(d.get('dependencies',{}).keys()); print('Deps:', ', '.join(deps[:15]))" 2>/dev/null
ls prisma/schema.prisma 2>/dev/null && echo "Prisma detected"
ls docs/*.make docs/design.make docs/design-system.md 2>/dev/null && echo "Design files detected"
ls set/orchestration/config.yaml 2>/dev/null && echo "Orchestration config exists"
```

If the tech stack is **unfamiliar or complex**, use the Agent tool (Explore subagent) to investigate:
- Read key source files to understand architecture
- Find entry points, main modules, config files
- Identify patterns (MVC, microservices, monolith, etc.)

Report findings to the user and confirm before proceeding.

### Phase 1: Project Overview

Ask the user (use AskUserQuestion):

> "Tell me about this project in 2-3 sentences. What does it do and who is it for?"

Then combine with detected context to write:

```markdown
# [Project Name] — [One-line description]

[User's description]
Tech stack: [detected from deps]
Target: [ask if not obvious]
```

### Phase 2: Tech Stack & Architecture

Based on detection, confirm with user:

**Web (Next.js, React, Vue):**
> "I detected Next.js with Prisma and next-intl. Is this correct? Any other key tools?"

**API (Express, FastAPI, Django):**
> "I see a FastAPI project with SQLAlchemy. What's the main purpose of this API?"

**CLI (argparse, clap, cobra):**
> "This looks like a CLI tool. What commands does it have? What's the main workflow?"

**Unknown:**
> "I'm not sure about the project type. Let me investigate..."
→ Spawn Explore agent to read key files
→ Report findings, ask user to confirm

### Phase 3: Data Model / State

**If prisma/schema.prisma exists:**
```bash
cat prisma/schema.prisma
```
Summarize existing models and ask: "Is this the complete data model, or are there entities to add?"

**If no schema detected:**
Ask: "What are the main entities/resources in this project? For each, what are the key fields?"

Provide example format:
```
Example: For an e-commerce app:
- Product: name, slug, description, price, category, imageUrl, inStock
- Order: userId, status (PENDING/CONFIRMED/SHIPPED), total, items[]
- User: email, name, role (USER/ADMIN), passwordHash
```

**For APIs:** "What resources does the API manage? What are the main endpoints?"
**For CLIs:** "What data does the tool process? What's the input/output format?"
**For pipelines:** "What data sources, transformations, and outputs are involved?"

### Phase 4: Screens / Endpoints / Commands

Adapt to project type:

**Web — Page Layouts:**
Ask: "List your main pages. For each, describe the layout."

Give example:
```
Example: "Homepage" →
1. Hero Banner — full-width image with overlay text
2. Featured Products — 4-column card grid
3. Subscription CTA — two-column: image left, text right
4. Footer — 3 columns: brand | links | contact
```

**For each page the user mentions**, ask follow-up:
- "How many columns on desktop?"
- "What components are in each section?"
- "What happens on mobile?"

**API — Endpoints:**
Ask: "List your main API endpoints with method, path, and what they do."

**CLI — Commands:**
Ask: "List your main commands with flags and what they do."

### Phase 5: Component Behavior / Business Logic

Ask about interactive elements:
- "What happens when a user clicks [button/link]?"
- "What does the error state look like for [form/action]?"
- "Are there any complex interactions (drag-drop, wizards, real-time updates)?"

If user says "use defaults" → note it explicitly in the spec:
```markdown
### Cart Behavior
Standard e-commerce cart with quantity controls. Use shadcn defaults for UI.
```

### Phase 6: Auth & Roles

Detect auth deps, then ask:
- "What roles exist? (e.g., USER, ADMIN, MODERATOR)"
- "Which routes/endpoints are protected?"
- "How do users register and log in?"

### Phase 7: Seed / Fixture Data

Ask: "What initial data should the app have?"

**IMPORTANT**: Warn against placeholder names:
> "Don't use 'Product 1', 'Test Item'. Use realistic names like 'Ethiopia Yirgacheffe', 'Colombia Supremo'. This makes the app look real from day one."

Ask for:
- Product/entity names (realistic, in the correct language)
- Admin credentials
- Test user credentials (for E2E tests)
- Sample content (stories, descriptions)

### Phase 8: Design Integration

Check for design files:

```bash
ls docs/*.make docs/design.make docs/design-system.md 2>/dev/null
```

**If .make file found:**
> "I found a Figma Make export at docs/design.make. Want me to run `set-design-sync` to extract design tokens? This will add exact colors, fonts, and layouts to the spec."

If user agrees, run:
```bash
set-design-sync --input docs/design.make --spec-dir docs/ --output docs/design-system.md
```

**If design-system.md exists:**
Read it and add `## Design Reference` section with key tokens.

**If nothing found:**
Ask: "Do you have a design?"
1. "Yes, I'll export a .make file from Figma Make" → pause, wait for file
2. "No, but I have brand colors and fonts" → ask for hex values, font names
3. "No design, use framework defaults" → note explicitly

### Phase 9: i18n

Detect i18n deps (next-intl, react-i18next, etc.):
- If found: "I see next-intl. What locales? Which is the default?"
- If not found: "Does this app need multiple languages?"

### Phase 10: Testing Strategy

Adapt to project type:
- **Web:** "Which user flows are most critical to E2E test?"
- **API:** "Which endpoints need integration tests?"
- **CLI:** "What input/output scenarios should be tested?"

Always add test user credentials and critical flow list.

### Phase 11: Assembly

Combine all sections into a single `docs/spec.md`:

```markdown
# [Project Name] — [Description]

## Tech Stack
[detected + confirmed]

## Data Model
[entities with fields]

## Pages / Endpoints / Commands
[per-page/endpoint layout descriptions]

## Component Behavior
[interactive element details]

## Auth & Roles
[roles, protected routes]

## Seed Data
[realistic names, credentials]

## Design Tokens
[colors, fonts, spacing — or "use defaults"]

## Internationalization
[locales, framework — or "English only"]

## E2E Tests
[test user, critical flows]

## Design Reference
[auto-generated from design-system.md if available]
```

Write to `docs/spec.md` (or user-specified path).

Show summary:
```
Spec generated: docs/spec.md
  Sections: 10
  Entities: 5
  Pages: 8
  Design: tokens from design-system.md
  Locales: hu, en

Next steps:
  1. Review docs/spec.md — edit anything that needs refinement
  2. If you have a Figma design: set-design-sync --input docs/design.make --spec-dir docs/
  3. Start orchestration: sentinel start via dashboard or API
```

## Guardrails

- **ALWAYS ask when uncertain** — use AskUserQuestion, never guess critical details
- **Adapt to project type** — don't force web sections on a CLI tool
- **Use Explore agents** — for unknown stacks, investigate before asking
- **Warn about vague specs** — if a section is too vague, tell the user and ask for detail
- **Reference the guide** — read `docs/guide/writing-specs.md` if you need examples or conventions
- **Never skip data model** — this is the most common source of merge conflicts
- **Realistic seed data** — always push for real names, not "Test 1"
