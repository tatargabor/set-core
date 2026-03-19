Scan project health and interactively address gaps.

**Steps:**

1. Run the audit scan:
   ```bash
   set-audit scan --json
   ```

2. Parse the JSON output and present findings grouped by dimension. For each dimension show:
   - Status indicators (✅/⚠️/❌) for each check
   - For ⚠️ and ❌ items, show the guidance with source pointers

3. After presenting, ask the user which gaps they want to address. Options:
   - Address a specific dimension (e.g., "fix design docs")
   - Address all ❌ items first
   - Skip (just wanted the report)

4. When addressing a gap:
   - Read the source files listed in the guidance
   - Read `lib/audit/reference.md` from the set-core repo for the category description
   - Create project-specific content based on what you find in the ACTUAL codebase
   - Do NOT use templates — read code, document patterns you discover

5. After fixing, re-run `set-audit scan --condensed` to show updated health status.

**Key principle:** set-audit provides evidence and guidance. YOU (the LLM) read the project code and create project-specific content. The scan tells you WHERE to look, the reference tells you WHAT categories to cover, your reading of the code tells you WHAT to write.

**Arguments:** Optionally specify a dimension to focus on (e.g., `/set:audit design-docs`).
