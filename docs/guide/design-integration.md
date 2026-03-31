# Design Integration

How to ensure your orchestrated agents implement the correct visual design — not generic framework defaults.

## Why This Matters

Without explicit design context, agents use shadcn/Tailwind defaults: white backgrounds, system fonts, generic spacing. The Figma design exists but doesn't reach the agents automatically — you need to bridge the gap before running the sentinel.

**The rule**: Agents implement exactly what the spec tells them. Vague spec → generic result. Spec with exact tokens (`#78350F`, `Playfair Display`) → matches the design.

## Supported Design Sources

| Source | Tool | Best For |
|--------|------|----------|
| Figma Make `.make` export | `set-design-sync` | Primary — richest data |
| Manual `design-system.md` | None (write directly) | When no Figma design exists |

## Step-by-Step Workflow

### 1. Design in Figma Make

Create your design in [Figma Make](https://www.figma.com/make). Include:
- A design token page (colors, typography, spacing, border-radius)
- Page layouts for each major view (homepage, catalog, detail, cart, checkout, admin)
- Component designs (header, footer, product card, buttons)

**Tip**: Give Figma Make a detailed prompt with exact hex colors, font names, and spacing values. These become the source of truth.

### 2. Export the `.make` File

In Figma Make: **File → Export → Download .make file**

Place it in your project's `docs/` directory:
```bash
cp ~/Downloads/my-design.make docs/design.make
```

### 3. Run `set-design-sync`

```bash
set-design-sync --input docs/design.make --spec-dir docs/
```

This generates:
- **`docs/design-system.md`** — Structured design tokens, component specs, page layouts
- **Updated spec files** — `## Design Reference` sections added with matched page tokens

### 4. Review the Output

Check `docs/design-system.md`:
- Are all colors correct? (`#78350F`, not `var(--color-primary)`)
- Are fonts listed? (Playfair Display, Inter)
- Are page layouts extracted?

Check your spec files:
- Does each page section have a `## Design Reference` block?
- Are the key colors and fonts referenced?

### 5. Start the Sentinel

```bash
curl -X POST http://localhost:7400/api/<project>/sentinel/start \
  -H 'Content-Type: application/json' -d '{"spec":"docs/spec.md"}'
```

The agents will now receive:
- Exact design tokens via the dispatcher (from `design-system.md`)
- Page-specific layout specs matched to each change's scope
- Design compliance checks during code review

## What `design-system.md` Contains

```markdown
# Design System

## Design Tokens
### Colors
- `color-primary`: `#78350F`
- `color-secondary`: `#D97706`
- `color-background`: `#FFFBEB`
...

### Typography
- `font-heading`: `'Playfair Display', serif`
- `font-body`: `'Inter', sans-serif`
...

### Spacing
- `spacing-base`: `8px`
- `spacing-card`: `24px`
...

## Components
### Header
- **colors**: color-primary, font-heading
- Layout: flexbox
...

## Page Layouts
### Home
Uses: Button, ProductCard, Header, Footer
- **Hero Banner** — full-width image with overlay text
- **Featured Products** — 4-column grid
...

## Image References
- **hero**: search "coffee beans barista atmospheric"
...
```

## Updating the Design

When the Figma design changes:

1. Re-export the `.make` file
2. Re-run `set-design-sync --input docs/design.make --spec-dir docs/`
3. The `## Design Reference` sections in specs are replaced (not duplicated)
4. `design-system.md` is regenerated with new tokens

## Manual Design System

If you don't use Figma Make, create `docs/design-system.md` manually with the same structure. The dispatcher will read it automatically — no `.make` file needed.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Agent uses white background instead of brand color | Design tokens not in dispatch context | Run `set-design-sync`, verify `design-system.md` exists |
| Agent uses Inter instead of custom font | Font not in design tokens | Check `### Fonts` section in `design-system.md` |
| Only homepage matches design, other pages generic | Spec doesn't mention page names | Ensure spec mentions "catalog", "cart", etc. for keyword matching |
| `set-design-sync` shows 0 tokens | `.make` file has no `theme.css` | The Figma Make design may not include a theme page — add one |
| Colors show as `var(--name)` instead of hex | CSS variable resolution failed | Check `design-system.md`, file a bug if hex values are missing |
