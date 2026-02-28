## 1. Planning Guide — Core Structure

- [x] 1.1 Create `docs/planning-guide.md` with introduction, table of contents, and the two input format sections (spec mode and brief mode) with annotated examples
- [x] 1.2 Write the "Scope Isolation" section: parallel-safe vs overlapping scopes, shared file conflict examples, how to declare dependencies for overlapping changes
- [x] 1.3 Write the "Dependencies" section: explicit vs implicit dependencies, common implicit patterns (schema migrations, shared types, barrel exports, package.json, env vars)
- [x] 1.4 Write the "Testing Requirements" section: how to specify test expectations in plan inputs, test infrastructure setup as first change, matching existing test patterns

## 2. Planning Guide — Sizing and Strategy

- [x] 2.1 Write the "Plan Sizing" section: S/M/L complexity guidelines, optimal batch size (4-6 changes), warning signs of oversized changes, when to split
- [x] 2.2 Write the "Phase Splitting" section: how to organize specs into phases, using status markers, `--phase` hint, auto-replan cycle behavior
- [x] 2.3 Write the "Design Rules" section: what to specify (tech stack, API patterns, auth approach, DB access, error handling, naming) vs what to leave open (file paths, variable names, internal decomposition)

## 3. Planning Guide — Web Patterns and Anti-patterns

- [x] 3.1 Write the "Web Project Patterns" section: DB schema changes as separate dependency, auth as foundational layer, API route organization, UI component isolation, deployment platform constraints
- [x] 3.2 Write the "Anti-patterns" section: overlapping scopes without dependencies, missing test requirements, oversized changes, vague scopes, forgetting shared infrastructure, generated file conflicts

## 4. Plan Review Checklist

- [x] 4.1 Create `docs/plan-checklist.md` with standalone checklist covering: scope overlap, dependency completeness, test requirements, sizing, shared file conflicts, infrastructure setup, directive configuration
