# Change: Add Confluence Documentation Generation

JIRA Key: TBD
Story: TBD

## Why
Document set-core and OpenSpec usage for the team. The documentation should be published to Confluence, and importantly, it must be **automatically updatable** as tools change. Generating documentation from spec files ensures documentation stays in sync with actual functionality.

## What Changes
- New `docs/` directory for generated Markdown documentation
- New `bin/docs-gen` script: generate Markdown documentation from spec files
  - Tutorial section: step-by-step guide for beginners
  - Reference section: detailed description of every command
  - Automatic example generation from spec.md Scenarios
- New `bin/docs-export` script: export to Confluence-compatible format
- GitHub Action / CI hook: regenerate documentation on spec changes (optional)
- The generated `docs/confluence.md` file can be easily copied to Confluence

## Impact
- Affected specs: confluence-docs (new capability)
- Affected code: `bin/` directory (new scripts), `docs/` directory (generated output)
- Does not modify existing functionality
