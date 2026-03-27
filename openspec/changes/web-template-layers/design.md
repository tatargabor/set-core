# Design: Web Template Layers

## Template Resolution Order

```
set-project init --name my-project --project-type web --template nextjs

  1. Core rules       (templates/core/rules/)          → .claude/rules/set-*
  2. Web module       (modules/web/templates/nextjs/)   → root + .claude/rules/*
  3. Project override (.claude/project-templates/)      → merge on top
```

Layer 2 scaffold templates are NOT part of `set-project init` — the E2E runner scripts handle those separately after init.

## Layer 1: Web Module Template Files

New files in `modules/web/set_project_web/templates/nextjs/`:

```
src/
├── app/
│   └── globals.css           ← @import "tailwindcss"
└── lib/
    ├── utils.ts              ← cn() helper (shadcn)
    └── prisma.ts             ← globalThis PrismaClient singleton

.env.example                  ← DATABASE_URL, NEXTAUTH_SECRET

tests/
└── e2e/
    └── global-setup.ts       ← prisma generate + db push + seed
```

### Deployment rules
- Files in `src/` are deployed to the project root `src/` (not into `.claude/`)
- `.env.example` goes to project root
- `tests/e2e/global-setup.ts` goes to project root `tests/e2e/`
- `manifest.yaml` updated to list new files
- `profile_deploy.py` `_target_path()` already handles root-relative paths correctly

### What agents stop doing
With these templates, the foundation change no longer needs to:
- Create `globals.css` (already exists)
- Create `lib/utils.ts` (already exists)
- Create `lib/prisma.ts` (already exists, naming fixed)
- Create `.env.example` (already exists)
- Create `tests/e2e/global-setup.ts` (already exists)

## Layer 2: Scaffold Templates

Each scaffold can have a `templates/` directory:

```
tests/e2e/scaffolds/minishop/
├── docs/spec.md
├── scaffold.yaml
├── set/orchestration/config.yaml
└── templates/                          ← NEW
    └── rules/
        └── minishop-conventions.md
```

### scaffold.yaml extension
```yaml
project_type: web
template: nextjs
# Optional: scaffold-specific templates to deploy after set-project init
templates:
  deploy_to: ".claude/rules/"
```

### Runner script change
After `set-project init`, the runner copies scaffold templates:
```bash
if [[ -d "$SCAFFOLD_DIR/templates/rules" ]]; then
    cp "$SCAFFOLD_DIR/templates/rules/"*.md "$TEST_DIR/.claude/rules/"
fi
```

### Scaffold rules content

**minishop-conventions.md:**
- Placeholder images from `https://placehold.co/`
- EUR currency, `formatPrice()` uses €
- 6 seed products with 3 attribute types (Size, Color, Material)
- Prisma schema: Product → Variant → AttributeType → AttributeValue
- Admin: bcrypt auth, session-based

**micro-web-conventions.md:**
- No database, no auth, no API routes
- Static pages only: Home, About, Blog (hardcoded posts array), Contact (client-side validation)
- Minimal dependencies: next, react, tailwindcss only

**craftbrew-conventions.md:**
- Coffee product types: Single Origin, Blend, Espresso
- Roast levels: Light, Medium, Dark
- Subscription model: weekly/bi-weekly/monthly
- HUF currency, Hungarian locale conventions
- Design system from Figma export (docs/figma-raw/)

## Layer 3: Project-Level Template Override

### Mechanism
`profile_deploy.py` gains a new step after template deployment:

```python
def deploy_templates(template_dir, target_dir, ...):
    # ... existing template deployment ...

    # NEW: project-level override
    project_templates = target_dir / ".claude" / "project-templates"
    if project_templates.is_dir():
        _merge_project_templates(project_templates, target_dir)
```

### Merge logic
```python
def _merge_project_templates(templates_dir: Path, target_dir: Path):
    """Merge project-level template overrides on top of module templates."""
    for src in templates_dir.rglob("*"):
        if src.is_file():
            rel = src.relative_to(templates_dir)
            dst = _target_path(str(rel), target_dir)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
```

### Usage by external projects
```
my-fintech-app/
├── .claude/
│   └── project-templates/         ← user creates this
│       ├── rules/
│       │   ├── pci-compliance.md
│       │   └── idor-patterns.md
│       └── src/lib/prisma.ts      ← custom: audit logging added
└── set/knowledge/project-knowledge.yaml
```

When `set-project init` runs:
1. Web module deploys `src/lib/prisma.ts` (standard)
2. Project override replaces with custom version (audit logging)

### Documentation
- Add "Project Templates" section to `docs/plugins.md`
- Add example in scaffold `README.md`

## Key Decisions

1. **Template files are NOT gitignored** — they become part of the project, agent can modify them
2. **Layer 3 override is optional** — if `.claude/project-templates/` doesn't exist, nothing happens
3. **Scaffold rules use standard `.claude/rules/` path** — no special mechanism, just file copy
4. **`.env.example` not `.env`** — template provides example, agent creates actual `.env` from it
