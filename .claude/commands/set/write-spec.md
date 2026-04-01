Interactive spec-writing assistant — generates a detailed specification for orchestration.

Usage: /set:write-spec [output-path]

This skill walks you through creating a structured spec by:
1. Detecting your project type and tech stack (web, API, CLI, pipeline)
2. Reading existing code (prisma schema, package.json, config files)
3. Asking targeted questions per section (data model, pages, auth, design, i18n)
4. Detecting Figma design files and integrating design tokens
5. Generating a complete docs/spec.md ready for sentinel

Works with any project type — not just web apps.

The output path defaults to docs/spec.md. Override with an argument:
  /set:write-spec docs/v2-spec.md
