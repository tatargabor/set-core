# Spec: Design Brief Stem Match (delta)

## REMOVED Requirements

### Requirement: Stem bidirectional matching

**Reason:** Scope-to-design matching against `design-brief.md` page sections is removed because the brief is no longer authoritative. Replaced by manifest-driven keyword matching against `design-manifest.yaml` route entries (see `v0-design-source` capability, "Scope-keyword matching against manifest" requirement).

**Migration:** Per-route `scope_keywords` in `design-manifest.yaml` provide the new matching surface. The keywords are author-controlled (auto-generated initially, manually editable). For the equivalent of the old stem-match permissiveness, list multiple keyword forms per route in the manifest:

```yaml
- path: /admin/products
  scope_keywords: [admin, products, termekek, product-management, crud]
```
