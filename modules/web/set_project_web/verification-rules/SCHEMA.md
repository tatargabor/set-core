# Verification Rule YAML Schema

Verification rules are declarative checks run during `opsx:verify`. Each rule
is defined in a YAML file with a fixed schema.

## Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique identifier (kebab-case) |
| `description` | string | yes | Human-readable description |
| `check` | string | yes | Check type (see below) |
| `severity` | enum | yes | `error`, `warning`, or `info` |
| `config` | object | no | Check-specific configuration |
| `ignore` | list | no | File paths excluded from this rule |

## Check Types

### `cross-file-key-parity`
Compares keys across multiple files of the same type.
- `files.pattern` — glob pattern matching the files to compare
- Extracts all leaf keys (dot-path for nested JSON) and reports differences

### `file-mentions`
Checks that source files are referenced in target files.
- `source.pattern` — glob for source files
- `source.exclude` — globs to exclude from source
- `target` — role name from `cross_cutting_files` in project-knowledge.yaml

### `cross-reference`
Checks consistency across groups of cross-cutting files.
- `groups[].files[].role` — roles from `cross_cutting_files`
- `groups[].key_pattern` — how to extract keys (e.g., `route-segment`)

### `schema-migration-sync`
Checks that schema changes have corresponding migrations.
- `schema_file` — path to schema file
- `migrations_dir` — path to migrations directory
- `design_doc` — path to design documentation (optional)

### `file-line-count`
Checks that files don't exceed a line count limit.
- `pattern` — glob for files to check
- `max_lines` — maximum allowed lines

### `pattern-absence`
Checks that a forbidden pattern does NOT appear in matching files.
- `pattern` — glob for files to check
- `forbidden` — regex pattern that should not match

## Severity Levels

| Level | Behavior |
|-------|----------|
| `error` | Blocks merge — must be fixed |
| `warning` | Reported but does not block |
| `info` | Informational, logged only |

## Consumer Overrides

Rules can be customized in `set/plugins/project-type.yaml`:

```yaml
# Disable a rule
disabled_rules:
  - ghost-button-text

# Override severity or config
rule_overrides:
  file-size-limit:
    severity: info
    config:
      max_lines: 600

# Add ignore entries
rule_overrides:
  route-registered:
    ignore:
      - src/app/preview/page.tsx
```
