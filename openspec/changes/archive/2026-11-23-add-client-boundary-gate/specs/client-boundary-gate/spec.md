## IN SCOPE
- Static analysis of `.ts`/`.tsx` files under the consumer project's `src/` and `app/` directories for Next.js App Router client/server boundary violations.
- Detection of non-component, non-type imports from `"use client"` files into server modules.
- Structured violation reporting: file path, line number, imported symbol, and target module, formatted for consumption by the agent via `retry_context`.
- Integration as a pre-build gate in the web profile pipeline.

## OUT OF SCOPE
- Full TypeScript type checking or type-aware analysis (that remains the responsibility of `next build`).
- Enforcing the inverse direction (client importing `server-only` code — handled by Next.js `server-only` package at build time).
- Files outside `src/` and `app/` (e.g., `tests/`, `scripts/`, `node_modules/`).
- Custom ESLint rules or IDE integration (separate future work).
- Auto-fixing violations (retry_context guides the agent; no automatic code rewriting in this iteration).

## ADDED Requirements

### Requirement: Client-boundary gate detects server-to-client function imports

The `client-boundary` gate SHALL scan every `.ts` and `.tsx` file under the project's `src/` and `app/` directories, and flag as a VIOLATION any import in a server module (a file that does NOT begin with `"use client"` or `'use client'` as its first non-comment statement) that names a non-type, non-capitalized symbol whose import target resolves to a client module (a file whose first non-comment statement IS `"use client"` or `'use client'`).

#### Scenario: Server component imports function from client file

- **GIVEN** `src/components/foo.tsx` without `"use client"` containing `import { parseX } from "./bar"`
- **AND** `src/components/bar.tsx` whose first statement is `"use client";` and that exports `function parseX()`
- **WHEN** the client-boundary gate runs
- **THEN** it SHALL report a VIOLATION with `file="src/components/foo.tsx"`, `line=<import line>`, `symbol="parseX"`, `target_module="src/components/bar.tsx"`
- **AND** the gate's `client_boundary_result` field SHALL be `"fail"`

#### Scenario: Server component imports Component (capitalized) from client file — allowed

- **GIVEN** `src/components/foo.tsx` without `"use client"` containing `import { Button } from "./button"`
- **AND** `src/components/button.tsx` whose first statement is `"use client";`
- **WHEN** the gate runs
- **THEN** it SHALL NOT report a violation for this import (capitalized identifier = JSX component convention)

#### Scenario: Type-only import from client file — allowed

- **GIVEN** a server file containing `import type { Props } from "./button"`
- **AND** `button.tsx` is a `"use client"` module
- **WHEN** the gate runs
- **THEN** it SHALL NOT report a violation (type imports are erased at compile time)

#### Scenario: Inline type import alongside component — allowed

- **GIVEN** a server file containing `import { type Props, Button } from "./button"`
- **WHEN** the gate runs
- **THEN** it SHALL NOT report a violation for either `Props` or `Button`

#### Scenario: Inline type import alongside function — function flagged

- **GIVEN** a server file containing `import { type Props, parseX } from "./bar"`
- **AND** `bar.tsx` is a `"use client"` module
- **WHEN** the gate runs
- **THEN** it SHALL report a violation for `parseX` only, NOT for `Props`

#### Scenario: Namespace import from client file — flagged

- **GIVEN** a server file containing `import * as lib from "./client-mod"`
- **AND** `client-mod` is a `"use client"` module
- **WHEN** the gate runs
- **THEN** it SHALL report a violation (namespace import may reach any export, including non-components)

#### Scenario: Side-effect-only import — allowed

- **GIVEN** a server file containing `import "./client-mod"` (no specifiers)
- **WHEN** the gate runs
- **THEN** it SHALL NOT report a violation

#### Scenario: Client-to-client import — not checked

- **GIVEN** `src/components/a.tsx` begins with `"use client";` and imports `import { parseX } from "./b"`
- **AND** `src/components/b.tsx` also begins with `"use client";`
- **WHEN** the gate runs
- **THEN** it SHALL NOT report a violation (both sides are client; no boundary crossed)

### Requirement: Client-boundary gate resolves import paths using tsconfig paths

The gate SHALL read `tsconfig.json` from the project root once per gate run and use `compilerOptions.paths` for alias resolution. Supported resolution order for a given import specifier:
1. If the specifier begins with `./` or `../`, resolve relative to the importer's directory.
2. If the specifier matches any key in `compilerOptions.paths`, substitute accordingly and resolve relative to the project root (or `compilerOptions.baseUrl` if set).
3. If the specifier is bare (e.g., `react`, `next/image`), skip (not a source file).

Once resolved, the gate SHALL try `<resolved>.tsx`, `<resolved>.ts`, `<resolved>/index.tsx`, `<resolved>/index.ts` in order and use the first match.

#### Scenario: Relative import resolved

- **GIVEN** importer at `src/components/foo.tsx`, import specifier `"./bar"`
- **WHEN** the gate resolves
- **THEN** it SHALL locate `src/components/bar.tsx` (or `.ts`)

#### Scenario: Alias import resolved via tsconfig paths

- **GIVEN** `tsconfig.json` has `"paths": { "@/*": ["./src/*"] }`
- **AND** import specifier `"@/components/bar"`
- **WHEN** the gate resolves
- **THEN** it SHALL locate `src/components/bar.tsx` (or `.ts`)

#### Scenario: Bare module specifier skipped

- **GIVEN** import specifier `"next/image"`
- **WHEN** the gate resolves
- **THEN** it SHALL skip the import and NOT attempt to analyze it

#### Scenario: Unresolvable import logged and skipped

- **GIVEN** an import specifier that does not match any relative path, alias, or bare module pattern recognized by the resolver
- **WHEN** the gate encounters it
- **THEN** it SHALL log a WARNING with the file, line, and specifier
- **AND** it SHALL NOT fail the gate for this import alone

### Requirement: Client-boundary gate emits actionable retry_context on failure

When the gate fails, it SHALL produce a human-readable violation report and persist a structured `client_boundary_violations` list to the change state.

The report SHALL:
- Summarize the number of files and imports affected.
- For each violation, show: `<file>:<line>`, the exact import statement, a one-line explanation of why it fails, and a FIX hint.

The structured list SHALL contain one entry per violation with keys: `file`, `line`, `import`, `target_module`, `symbol`.

#### Scenario: Failure report is actionable

- **GIVEN** one violation in `src/components/layout.tsx:13` importing `parseX` from `./variant-selector`
- **WHEN** the gate fails
- **THEN** the retry_context text SHALL contain the file, line, import statement, target module path, symbol name, and a FIX hint that names the pattern ("move parseX to a non-use-client module and import it from both sides")

#### Scenario: Structured violations persisted

- **WHEN** the gate fails with N violations
- **THEN** the change state SHALL contain `client_boundary_violations` as a list of N dicts, each with `file`, `line`, `import`, `target_module`, `symbol`

### Requirement: Client-boundary gate finishes in reasonable time

The gate SHALL complete within 1 second on any scaffold with fewer than 2000 source files under `src/` + `app/`, measured end-to-end (read, parse, resolve, report).

#### Scenario: Typical scaffold

- **GIVEN** a scaffold with 800 `.tsx` files and 200 `.ts` files under `src/`
- **WHEN** the gate runs
- **THEN** `gate_client_boundary_ms` SHALL be ≤ 1000
