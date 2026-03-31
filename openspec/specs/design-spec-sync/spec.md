# Spec: Design Spec Sync

## Status: new

## Requirements

### REQ-SPEC-SYNC: Inject design references into spec files
- The tool SHALL scan all `.md` files in `--spec-dir` for page/feature keywords
- Keywords to match: homepage/home/landing, catalog/listing/products, product detail, cart/basket, checkout/payment, admin/dashboard, auth/login/register, subscription, stories/blog, profile/account, search, footer, header
- For each match, it SHALL add or replace a `## Design Reference` section at the end of the spec file
- The Design Reference section SHALL contain: page/component name, reference to design-system.md section, key layout elements (column count, component list), critical tokens (primary color, heading font, key spacing)
- It SHALL NOT modify any other content in the spec file — only append or replace the `## Design Reference` block
- If a `## Design Reference` section already exists, it SHALL be replaced entirely (not duplicated)

### REQ-SPEC-PRESERVE: Preserve existing spec content
- The tool SHALL never delete, reorder, or modify content outside the `## Design Reference` section
- The tool SHALL preserve frontmatter (YAML between `---` markers) unchanged
- If the spec file has no matching keywords, it SHALL not be modified

### REQ-SPEC-IDEMPOTENT: Running multiple times produces same result
- Running `set-design-sync` twice with the same inputs SHALL produce identical output
- If the design source changes (new .make file), re-running SHALL update the Design Reference sections to reflect the new design
