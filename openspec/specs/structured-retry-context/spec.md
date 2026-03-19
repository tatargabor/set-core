## ADDED Requirements

### Requirement: Remove truncated raw review output from retry prompt
The review retry prompt SHALL NOT include `current_review_output[:1500]` when `_extract_review_fixes()` produces non-empty structured output. Raw review output SHALL only be included as a fallback when the parser finds zero issues but `has_critical` is True, and in that case SHALL use `[:3000]` instead of `[:1500]`.

#### Scenario: Structured fixes available
- **WHEN** `_extract_review_fixes()` returns non-empty fix instructions
- **THEN** the retry prompt SHALL include only the structured fixes, NOT the raw review output

#### Scenario: Parser finds nothing but critical flagged
- **WHEN** `_extract_review_fixes()` returns empty AND the review flagged critical issues
- **THEN** the retry prompt SHALL include raw review output truncated to 3000 chars as a fallback

#### Scenario: Neither structured nor critical
- **WHEN** `_extract_review_fixes()` returns empty AND no critical issues flagged
- **THEN** the retry prompt SHALL not include raw review output (the review passed)

### Requirement: Parse build errors into structured format
The verifier SHALL include a `_extract_build_errors()` function that parses TypeScript/Next.js build output into structured `file:line: error_code: message` tuples.

#### Scenario: TypeScript errors parsed
- **WHEN** build output contains lines matching `TS\d{4}:` error patterns
- **THEN** `_extract_build_errors()` SHALL extract file path, line number, error code, and message for each error

#### Scenario: Next.js module errors parsed
- **WHEN** build output contains Next.js specific errors (e.g., "Module not found", route export violations)
- **THEN** `_extract_build_errors()` SHALL extract the relevant file path and error description

#### Scenario: Unknown build output format
- **WHEN** build output does not match any known error patterns
- **THEN** `_extract_build_errors()` SHALL return the last 3000 chars of raw output as fallback

### Requirement: Parse test failures into structured format
The verifier SHALL include a `_extract_test_failures()` function that parses Jest/Vitest test output into structured failure records with test name, file, and assertion details.

#### Scenario: Jest failure parsed
- **WHEN** test output contains Jest-style failure blocks (`FAIL`, `Expected`, `Received`)
- **THEN** `_extract_test_failures()` SHALL extract test file, test name, expected value, and received value

#### Scenario: No test failures
- **WHEN** all tests pass
- **THEN** `_extract_test_failures()` SHALL return empty string

### Requirement: Unified retry context format
The verifier SHALL provide a `_build_unified_retry_context()` function that combines build errors, test failures, and review issues into a single structured markdown block used across all retry paths.

#### Scenario: Multiple gate failures combined
- **WHEN** both build errors and review issues exist for a retry
- **THEN** the unified context SHALL include separate sections for each gate type with clear headers

#### Scenario: Single gate failure
- **WHEN** only build errors exist (no review issues, no test failures)
- **THEN** the unified context SHALL include only the build errors section without empty sections for other gates

### Requirement: Re-read instruction in retry prompt
Every retry prompt SHALL include the instruction: "Before fixing, re-read the files listed above. Do NOT rely on your memory of the file contents from previous attempts."

#### Scenario: Re-read instruction present
- **WHEN** any retry prompt is generated (build, test, or review)
- **THEN** the prompt SHALL contain the re-read instruction

### Requirement: Increase review output state storage
The review output stored in change state (`review_output` in extras) SHALL be stored at `[:5000]` instead of `[:2000]` for debugging and history purposes.

#### Scenario: Longer review stored
- **WHEN** a review produces output longer than 2000 chars
- **THEN** up to 5000 chars SHALL be stored in the change state for debugging
