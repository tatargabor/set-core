# Spec: v0 Fixture Renderer (delta)

## ADDED Requirements

**IN SCOPE:** build-time content substitution for v0-export; placeholder string substitution from `content-fixtures.yaml`; mock data layer injection; headless build of substituted copy for screenshot capture; substitution config schema and per-scaffold authoring.

**OUT OF SCOPE:** runtime content injection (build-time only); database-backed fixtures (file-driven only); image asset substitution (uses placeholder URLs from fixtures or v0 defaults); multi-language fixture rendering (one language per render run).

### Requirement: content-fixtures.yaml format

The fixture renderer SHALL accept an optional fixtures file. The file is authored in the scaffold at `<scaffold>/docs/content-fixtures.yaml` and deployed by the runner to the consumer project at `<project>/.set-orch/v0-fixtures.yaml`. The renderer reads from the consumer-project location at gate time. When the file MUST conform to the documented schema (string_replacements, mock_data, data_imports, language). When absent, the renderer SHALL emit a WARNING and proceed with v0-export as-is.

#### Scenario: fixtures.yaml structure
- **GIVEN** the fixtures file exists at `<project>/.set-orch/v0-fixtures.yaml` (deployed from `<scaffold>/docs/content-fixtures.yaml`)
- **THEN** the file SHALL conform to the schema:
  ```yaml
  language: hu
  string_replacements:
    - find: "Sample Coffee"
      replace: "Ethiopia Yirgacheffe"
    - find: "Lorem ipsum"
      replace: "Specialty kávé válogatott szemekből..."
  mock_data:
    products: <path-to-json-fixture>
    stories: <path-to-json-fixture>
  data_imports:
    - target: "v0-export/lib/mock-products.ts"
      source: "<scaffold>/docs/fixtures/products.json"
  ```

#### Scenario: Missing fixtures file when design declared (HARD FAIL)
- **GIVEN** `detect_design_source() == "v0"` (design IS declared)
- **WHEN** no fixtures file exists at `<project>/.set-orch/v0-fixtures.yaml`
- **THEN** the renderer raises `FixturesMissingError` with the expected path
- **AND** the fidelity gate translates this into status `fixtures-missing` and BLOCKS merge (per design D8 fail-loud principle)
- **AND** there is NO auto-warn-only fallback — the only override is explicit `gates.design-fidelity.warn_only: true` config

#### Scenario: Missing fixtures file when design absent (graceful)
- **GIVEN** `detect_design_source() == "none"` — project did not declare a design source
- **WHEN** the renderer is invoked at all (it normally wouldn't be in this state, but defensive code path)
- **THEN** it returns gracefully with no error (no work to do; fidelity gate would have already skipped)

### Requirement: Placeholder string substitution

The renderer SHALL apply string replacements from fixtures to all `.tsx`, `.ts`, `.jsx`, `.js` files in the temp v0-export copy.

#### Scenario: Substitute string in TSX
- **GIVEN** a v0 page contains `<h1>Sample Coffee</h1>`
- **AND** fixtures specify `find: "Sample Coffee", replace: "Ethiopia Yirgacheffe"`
- **WHEN** substitution runs
- **THEN** the file in the temp copy contains `<h1>Ethiopia Yirgacheffe</h1>`
- **AND** the original v0-export is NOT modified

#### Scenario: Multiple matches in same file
- **GIVEN** a file contains 3 instances of `"Lorem ipsum"`
- **WHEN** substitution runs
- **THEN** all 3 instances are replaced

#### Scenario: No-match logged at debug
- **GIVEN** a fixture entry has no occurrences in v0-export
- **WHEN** substitution runs
- **THEN** a DEBUG log notes the unused entry with file count `0`
- **AND** substitution does NOT fail

### Requirement: Mock data layer injection

The renderer SHALL inject mock data files into v0-export's data imports so v0 components render with project seed data.

#### Scenario: Inject products fixture
- **GIVEN** fixtures specify `data_imports: - target: lib/mock-products.ts, source: products.json`
- **WHEN** substitution runs
- **THEN** the temp copy's `lib/mock-products.ts` is replaced with content that exports the parsed `products.json` as a default export
- **AND** v0 components importing from `lib/mock-products.ts` receive the project's HU products

#### Scenario: Target file does not exist in v0-export
- **GIVEN** a `data_imports` target points to a file not present in v0-export
- **WHEN** substitution runs
- **THEN** the file is created at the target path (so v0 components that import it for the first time work)
- **AND** an INFO log notes the new injection

### Requirement: Headless build of fixture-substituted copy

The renderer SHALL execute `pnpm install --frozen-lockfile && pnpm build && pnpm start` in the substituted temp copy and expose the running server URL.

#### Scenario: Build succeeds, server starts
- **WHEN** the build completes successfully
- **THEN** `pnpm start` is launched in background on a port chosen from a free-port range
- **AND** the renderer waits for the server to respond to `GET /` with HTTP 200 (timeout 30s)
- **AND** returns the base URL for screenshot capture

#### Scenario: Build fails
- **WHEN** `pnpm build` exits non-zero
- **THEN** the renderer captures stderr
- **AND** raises a `ReferenceBuildError` with the captured output
- **AND** the fidelity gate handles the error per its retry policy

#### Scenario: Server cleanup
- **WHEN** screenshot capture finishes (or errors)
- **THEN** the renderer terminates the background server (SIGTERM, then SIGKILL after 5s)
- **AND** the temp directory is removed (unless `--keep-temp` debug flag is set)

### Requirement: Idempotent and concurrent-safe

Multiple fidelity gate invocations SHALL be able to run concurrently without interfering.

#### Scenario: Concurrent invocations
- **WHEN** two fidelity gate runs start simultaneously
- **THEN** each gets its own temp directory (e.g. `<tmp>/v0-renderer-<uuid>/`)
- **AND** each picks a distinct port for `pnpm start`
- **AND** neither interferes with the other's output

### Requirement: Caching of pnpm install layer

To reduce gate latency, the renderer SHALL share a `node_modules` cache across gate runs when the v0-export `pnpm-lock.yaml` is unchanged. The cache SHALL be safe for concurrent gate runs.

#### Scenario: Cache hit (copy-on-write semantics)
- **GIVEN** a previous gate run cached `node_modules` for v0-export with lockfile hash `abc123`
- **AND** the current v0-export has the same lockfile hash
- **WHEN** the renderer prepares the temp copy
- **THEN** `node_modules` is COPIED from the cache (cp `--reflink=auto` on Linux, plain copy on other systems) into the temp copy
- **AND** symlinks are NOT used (concurrent gate runs would otherwise race when pnpm post-install scripts mutate the directory)
- **AND** `pnpm install --frozen-lockfile --prefer-offline` runs to fast-validate and complete any deferred steps without re-downloading

#### Scenario: Concurrent gate runs do not corrupt cache
- **GIVEN** two gate runs start simultaneously, both with the same lockfile hash
- **WHEN** both copy `node_modules` from the cache
- **THEN** each gets its own copy in its own temp directory
- **AND** post-install scripts mutating `node_modules` in one run do NOT affect the other
- **AND** the cache itself is treated as read-only during this period

#### Scenario: Cache miss invalidates and rebuilds
- **GIVEN** the cached lockfile hash differs from current v0-export
- **WHEN** the renderer prepares the temp copy
- **THEN** the cache is invalidated atomically (write a new cache entry under a new hash, then atomically swap the "current" pointer)
- **AND** `pnpm install --frozen-lockfile` runs fresh and updates the cache
- **AND** old cache entries are pruned by an LRU policy (keep last 3 hashes per scaffold)
