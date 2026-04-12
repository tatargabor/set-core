# Design: E2E Smoke/Functional UI Annotations

## Backend Changes

### merger.py — always save smoke output and stats

Currently smoke output is only saved on failure (L1167). Change to always save:

```python
# After smoke phase completes (pass or fail):
update_change_field(state_file, change_name, "smoke_e2e_output", _smoke_output)
update_change_field(state_file, change_name, "smoke_test_count", len(smoke_names))
update_change_field(state_file, change_name, "own_test_count", len(own_specs))
update_change_field(state_file, change_name, "inherited_file_count", len(inherited_specs))
```

No new API endpoints needed — these go into change extras and are already exposed via `/api/{project}/changes`.

## Frontend Changes

### DigestView.tsx — E2EPanel rewrite

Current: flat list parsed from `e2e_output`.

New: per-change, two sections with badges:

```
┌─────────────────────────────────────────────────────────┐
│ ● pass  content-and-blog-pages          27 test(s)     │
│                                                         │
│  SMOKE (inherited)          2 tests   3.6s    pass     │
│  ✓ navigation.spec.ts › REQ-NAV-001 › cold visit       │
│  ✓ contact-form.spec.ts › REQ-FORM-001 › page loads    │
│                                                         │
│  FUNCTIONAL (own)          11 tests   9.4s    pass     │
│  ✓ content-pages.spec.ts › REQ-BLOG-001 › blog list    │
│  ✓ content-pages.spec.ts › REQ-BLOG-002 › blog post    │
│  ...                                                    │
└─────────────────────────────────────────────────────────┘
```

### Data source mapping

| UI element | API field | Source |
|-----------|-----------|--------|
| Smoke badge | `smoke_e2e_result` | change extras |
| Smoke tests | `smoke_e2e_output` | change extras (NEW: always saved) |
| Smoke time | `gate_e2e_smoke_ms` | change extras |
| Smoke count | `smoke_test_count` | change extras (NEW) |
| Functional tests | `e2e_output` | change field |
| Functional time | `gate_e2e_own_ms` | change extras |
| Own count | `own_test_count` | change extras (NEW) |

### ParsedTest extension

Add `phase` field to distinguish when parsing:
```typescript
interface ParsedTest {
  file: string
  name: string
  result: 'pass' | 'fail'
  duration?: string
  phase?: 'smoke' | 'functional'  // NEW
}
```

### Summary line update

Current: `27 tests across 3 change(s) | 27 passed`
New: `27 tests across 3 change(s) | 27 passed | smoke: 3 | functional: 24`

### ChangeInfo interface — add missing fields

```typescript
// Already exists but not used:
smoke_e2e_result?: string
gate_e2e_smoke_ms?: number
gate_e2e_own_ms?: number

// New fields to add:
smoke_e2e_output?: string
smoke_test_count?: number
own_test_count?: number
inherited_file_count?: number
```
