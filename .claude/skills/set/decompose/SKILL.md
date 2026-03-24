Decompose a specification document into an orchestration execution plan.

**Input**: Spec file path (provided as argument or via environment `SPEC_PATH`), optional phase hint via `PHASE_HINT`.

**You are a planning agent.** Your job is to analyze a spec document, explore the codebase, and produce an `orchestration-plan.json` that the orchestrator can dispatch.

## Steps

1. **Read the spec**
   - If `SPEC_PATH` is a **directory** (multi-file spec):
     - Read the master file first (matching `v*-*.md` or `README.md` at root level)
     - Use the Agent tool (Explore) to analyze domains in parallel — one agent per subdirectory
     - Each agent should return: domain summary, key requirements, cross-references to other domains
     - Combine results into a unified view before decomposing
   - If `SPEC_PATH` is a **single file**:
     - If under 200 lines, read it directly
     - If over 200 lines, use the Agent tool (Explore) to analyze sections — do NOT load the entire spec into context
   - Identify completed items (checkboxes, "done" markers) and focus on incomplete work

2. **Read project context** (if files exist, skip gracefully if not)
   - `set/plugins/project-type.yaml` — verification rules, conventions, project type
   - `set/knowledge/project-knowledge.yaml` — cross-cutting files, feature registry
   - `set/requirements/*.yaml` — active requirements (status: captured or planned)
   - `set/orchestration/config.yaml` or `.claude/orchestration.yaml` — directives

3. **Explore the codebase**
   - Use the Agent tool (Explore) to scan for existing implementations matching spec topics
   - Understand what's already built vs what needs to be built
   - Identify shared files that multiple changes would touch (merge hazard)
   - Run multiple Explore agents in parallel for different spec sections

4. **Recall relevant memories**
   ```bash
   set-memory recall "<spec topic>" --tags "phase:planning" --limit 3 --mode hybrid
   ```
   Use the recall MCP tool with `phase:planning` tag. Look for past decomposition learnings, known pitfalls.

5. **Check existing work**
   ```bash
   openspec list --json
   ```
   List existing specs and active changes to avoid duplication.

6. **Check for design tool** (skip if no design MCP available)
   - If a design MCP (figma, penpot, sketch, zeplin) is registered in `.claude/settings.json`, query it for:
     - Frame/page inventory — what screens/views are designed
     - Component hierarchy — shared components, variants
   - Map design frames to planned changes (e.g., `design_ref: "frame:Login"`)
   - If a spec item requires UI but no matching design frame exists, add a `design_gap` ambiguity

7. **Generate the plan**

   Write `orchestration-plan.json` to the project root with this schema:

   ```json
   {
     "phase_detected": "Description of the phase/section being implemented",
     "reasoning": "Why this decomposition — what's the strategy",
     "changes": [
       {
         "name": "kebab-case-name",
         "scope": "Detailed description of what to implement + test requirements",
         "complexity": "S|M|L",
         "change_type": "infrastructure|schema|foundational|feature|cleanup-before|cleanup-after",
         "model": "opus|sonnet",
         "has_manual_tasks": false,
         "depends_on": ["other-change-name"],
         "roadmap_item": "The spec section this implements",
         "design_ref": "frame:PageName or component:ComponentName (optional, from design tool)",
         "spec_files": ["path/relative/to/spec-dir.md"],
         "requirements": ["REQ-DOMAIN-001"],
         "also_affects_reqs": ["REQ-CROSS-001"]
       }
     ],
     "deferred_requirements": [
       {
         "id": "REQ-DOMAIN-002",
         "reason": "Depends on auth system, planned for next phase"
       }
     ],
     "source_items": [
       {
         "id": "SI-1",
         "text": "Description of the spec item",
         "change": "assigned-change-name-or-null"
       }
     ]
   }

   **Note:** `spec_files`, `requirements`, and `also_affects_reqs` are only required when working with a multi-file spec that has been digested (`set/orchestration/digest/` exists). For single-file specs, omit these fields.

   **Source items (single-file mode only):** When there is NO digest directory, generate a `source_items` array listing every identifiable spec item (feature, requirement, task, checkbox) with an assigned change name or `null` if intentionally excluded. Omit `source_items` entirely in digest mode (digest uses `requirements.json` instead).

   **Requirement accounting (digest mode only):** When a digest exists, every requirement in `set/orchestration/digest/requirements.json` MUST be accounted for. Either:
   - Assign it to a change via `requirements[]` or `also_affects_reqs[]`, OR
   - List it in `deferred_requirements[]` with a reason explaining why it is deferred (e.g., dependency on another phase, out of scope for this sprint, intentionally excluded)

   Silent omission of requirements — assigning neither to a change nor to `deferred_requirements` — is a planning error. `validate_plan()` will report unaccounted requirements as errors and block dispatch.
   ```

## Decomposition Rules

**Sizing:**
- S: <10 tasks, M: 10-25 tasks, L: 25+ tasks (prefer splitting L into multiple changes)

**Dependency ordering:**
- Infrastructure/test setup → first
- Schema/migrations → before data-layer or API
- Foundational (auth, shared types) → before features
- cleanup-before → before feature changes in same area
- cleanup-after → last

**Shared resource awareness:**
- If 2+ changes touch the same files, chain via `depends_on`
- Cross-cutting files (from project-knowledge.yaml) are merge hazards — serialize changes touching them

**Model selection:**
- `opus` for all code-writing changes
- `sonnet` ONLY for doc-only changes (zero code modifications)

**Manual tasks:**
- Set `has_manual_tasks: true` for changes needing external intervention (API keys, DNS, OAuth setup)

**Design gap detection:**
- If a design tool is available and a change involves UI, include `design_ref` pointing to the relevant frame
- If the spec describes a page/screen but no matching design frame exists, flag it as a `design_gap` ambiguity in the plan reasoning
- Changes with design gaps can still proceed but the gap is recorded for user resolution

**Project type integration:**
- If `set/plugins/project-type.yaml` exists, use its verification rules to inform change_type and dependency ordering
- Project-type-specific patterns (e.g., "DB migration must be sequential") MUST be reflected

## Context Size Management

- Do NOT read entire large specs into your context — use Agent tool to analyze sections
- Sub-agents should return summaries (key points, requirements), not full file contents
- Project knowledge and requirements files are small — read directly
- Keep your working context focused on the decomposition task

## Output

After writing `orchestration-plan.json`, verify it:
- No circular dependencies
- All `depends_on` reference valid change names within the plan
- Complexity values are S, M, or L
- change_type is one of the valid values
- Every change has a non-empty scope and roadmap_item
- (Digest mode) Every digest requirement is assigned to a change or listed in `deferred_requirements` — none silently omitted
