Harvest rules from a source project into reusable template modules.

**Input**: `--from /path/to/project` (required) — the source project to harvest from. Optionally `--template <name>` to target a specific template variant.

**You are a content analyst agent.** Your job is to compare a source project's rules against the current template, identify candidates for generalization, and write approved candidates as new optional template modules.

## Prerequisites

Determine the source project's project type and template:

```bash
# Read source project's project-type.yaml
cat <source-project>/wt/plugins/project-type.yaml
```

Extract `type` and `template` fields. These determine which template package to compare against.

## Steps

### 1. Diff source vs template

Read all rule files from the source project:
```bash
ls <source-project>/.claude/rules/*.md
```

Load the template's manifest to get the list of core + module files:
```bash
# Find the template directory from the installed package
python3 -c "
from importlib.metadata import entry_points
from wt_project_base.deploy import resolve_template, _load_manifest
eps = entry_points(group='wt_tools.project_types')
for ep in eps:
    if ep.name == '<type-name>':
        pt = ep.load()()
        tid, tdir = resolve_template(pt, '<template-name>' or None)
        print(tdir)
        break
"
```

Read both the source rules and the template rules. For each source rule file:
- If it has no corresponding template file → **new candidate**
- If it exists in template but source is significantly richer (more sections, more detail) → **divergence candidate**
- If identical or template is superset → **skip**

### 2. Classify candidates

For each new candidate, analyze its content and classify:
- **base** — Universal rule applicable to any project type (e.g., data-privacy, testing patterns, git conventions). Should go to `wt-project-base` default template.
- **web** — Web-specific rule (e.g., UI patterns, API conventions, auth flows). Should go to `wt-project-web` template.
- **skip** — Too project-specific to generalize (contains hardcoded paths, entity names, business logic specific to one project).

Classification criteria:
- References to specific frameworks (Next.js, React) → web
- References to HTTP, REST, GraphQL, CSS, components → web
- References to databases, caching, queues in generic terms → base
- References to specific table names, API endpoints, business entities → skip (unless generalizable)

### 3. Generalize content

For each `base` or `web` candidate:
- Strip project-specific paths (e.g., `/app/api/webhooks/stripe` → `/app/api/webhooks/[provider]`)
- Replace entity names with generic placeholders (e.g., "User subscription" → "domain entity")
- Remove references to specific third-party services unless the rule is about integration patterns
- Keep the structure, headings, and rule format intact
- Preserve the actionable guidance — generalize the examples, not the principles

### 4. Show summary and get approval

Present each candidate to the user:

```
## Harvest Candidates

### 1. data-privacy.md → base/default (new module: data-privacy)
  Classification: base
  Reason: Universal data retention and privacy patterns

  Changes from original:
  - Removed references to specific table names
  - Generalized "user" to "entity"

  [approve] [edit] [skip]

### 2. ui-conventions.md → web/nextjs (divergence — 3 new sections)
  Classification: divergence
  Sections added in source:
  - "Loading States" (new)
  - "Error Boundaries" (new)
  - "Accessibility Checklist" (new)

  [merge back] [skip]
```

Use the **AskUserQuestion tool** to get approval for each candidate (or batch if many).

### 5. Write approved files

For each approved candidate:

**New module:**
1. Write the generalized file to the template directory:
   - base → `wt-project-base/wt_project_base/templates/default/rules/<filename>`
   - web → `wt-project-web/wt_project_web/templates/<template>/rules/<filename>`
2. Update `manifest.yaml` — add the file as a new optional module:
   ```yaml
   modules:
     <module-id>:
       description: "<one-line description>"
       files:
         - rules/<filename>
   ```

**Divergence merge:**
1. Update the existing template rule file with the new sections from the source
2. No manifest change needed (file is already in core)

### 6. Report results

Show a summary of what was written:
```
## Harvest Complete

Written:
  - base/default: rules/data-privacy.md (new module: data-privacy)
  - web/nextjs: rules/integrations.md (updated module: integrations)

Divergence merged:
  - web/nextjs: rules/ui-conventions.md (+3 sections)

Skipped:
  - project-settings.md (too project-specific)

Next steps:
  - Review and commit changes in wt-project-base and/or wt-project-web
  - Run `wt-project init --project-type web --template nextjs` to verify deployment
```

## Guardrails

- Never write project-specific content to templates — always generalize first
- Never overwrite existing template files without showing the diff and getting approval
- Preserve manifest.yaml structure — only add to modules section, never remove
- If a candidate could go to either base or web, prefer web (more specific is safer)
- Always show the original vs generalized side-by-side before writing
- If the source project has no project-type.yaml, ask the user which type/template to target
