## Capability: spec-resolution

Short-name spec resolution for the `--spec` flag, enabling `set-orchestrate --spec v12 plan` instead of requiring full paths.

## Requirements

### Requirement: Short-name resolution in find_input()

When `--spec <value>` is provided and the literal path doesn't exist as a file:
1. Try `wt/orchestration/specs/<value>.md`
2. If found, use it as the spec path
3. If not found, error with both paths checked

The resolved absolute path (not the short name) must be stored in `INPUT_PATH` so plan metadata records the actual file location.

### Requirement: Subdirectory resolution

Short names support subdirectories: `--spec archive/v6` resolves to `wt/orchestration/specs/archive/v6.md`. This allows referencing archived specs without typing the full path.

### Requirement: Literal path priority

If the `--spec` value is an existing file path (absolute or relative), use it directly. The wt/ resolution is only a fallback, not a replacement. This preserves backward compatibility with `--spec docs/v8.md`.

### Requirement: Clear error messages

When resolution fails, the error message must show both the literal path and the wt/ path that were checked, so the user knows where to put the file.
