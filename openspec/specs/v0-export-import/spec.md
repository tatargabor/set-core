# v0-export-import Specification

## Purpose
TBD - created by archiving change design-binding-completeness. Update Purpose after archive.
## Requirements
### Requirement: --with-hygiene flag triggers post-import scan
The `set-design-import` CLI SHALL accept an optional `--with-hygiene` flag. When set, after manifest regeneration, the CLI SHALL run the hygiene scanner and write the checklist to `docs/design-source-hygiene-checklist.md`. If any CRITICAL findings are present, the CLI SHALL exit with code 1 unless `--ignore-critical` is also set.

#### Scenario: Combined import + hygiene with no findings
- **WHEN** `set-design-import --git <url> --ref main --with-hygiene` runs against a clean design source
- **THEN** import completes, manifest regenerated, hygiene scanner finds 0 CRITICAL
- **AND** checklist written with INFO/WARN findings only
- **AND** CLI exits with code 0

#### Scenario: Hygiene finds CRITICAL — exit non-zero
- **WHEN** `set-design-import --with-hygiene` runs and hygiene scanner finds ≥1 CRITICAL
- **THEN** CLI exits with code 1
- **AND** the checklist is still written (operator can review)

#### Scenario: Operator force-bypass
- **WHEN** `set-design-import --with-hygiene --ignore-critical` runs and CRITICAL findings exist
- **THEN** CLI exits with code 0
- **AND** the operator has consciously bypassed the safety check

#### Scenario: Default omits hygiene
- **WHEN** `set-design-import --git <url>` runs WITHOUT `--with-hygiene`
- **THEN** no hygiene scan is performed
- **AND** behavior is identical to today

