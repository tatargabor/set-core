# Tasks

**Every task below was completed before this change was written.** This documents shipped
behaviour; the commits are the evidence, and each requirement in the delta specs is already
covered by tests in the repository.

## 1. Contract reader (Layer 1 — `lib/set_orch/project_status.py`)

- [x] 1.1 Envelope validation, refusing an unsupported version before spawning (`86e0bc5e`)
- [x] 1.2 Manifest discovery via the repo-root declaration (`b4a0deff`)
- [x] 1.3 Declared read/write namespaces, with a name in both dropped from both
- [x] 1.4 `primary`, `onDemand` and per-command `timeouts` read from the declaration (`8f91b4b2`, `567b4111`)
- [x] 1.5 `errorClass` vocabulary, documented and gated (`0f88a564`)
- [x] 1.6 Persistence prohibition, with a test asserting a query leaves no file behind

## 2. Transport (`lib/set_orch/api/project_status.py`)

- [x] 2.1 Read endpoint over the declared list; `--eval` refused, undeclared name 404 (`734c445f`)
- [x] 2.2 Gaps reported explicitly, distinct from an empty answer
- [x] 2.3 In-memory-only answer cache with refresh bypass; failures cached on equal terms
- [x] 2.4 Write endpoint restricted to the declared write list, read cache dropped after

## 3. Surface (`web/src/components/StatusValue.tsx`, `web/src/pages/ProjectStatus.tsx`)

- [x] 3.1 Shape-driven rendering with no domain field name recognised (`126c71c8`, `a2eea14a`)
- [x] 3.2 Unknown ≠ zero ≠ success; false is a verdict (`a1975084`)
- [x] 3.3 Renderer's own count says "rows", not a domain-sounding word (`67d64a21`)
- [x] 3.4 Deprecation honoured, hidden count taken from the data
- [x] 3.5 Row actions, declared by the project, never derived
- [x] 3.6 Long lists compacted with the withheld count always stated (`248a76c8`)
- [x] 3.7 Project-declared emphasis (`d54c0807`)
- [x] 3.8 Project-declared section ranking, weight from order (`55554bb8`)

## 4. Enforcement

- [x] 4.1 Gate obliging the living record to name every envelope field the reader consumes (`834bfaaf`)
- [x] 4.2 Gate extended to every `errorClass` value emitted (`0f88a564`)
- [x] 4.3 Gate verifies its own pointer — the document it checks is the one readers are sent to

## 5. This change

- [x] 5.1 Write the three delta specs from the shipped behaviour
- [x] 5.2 Archive so the deltas land in `openspec/specs/`
