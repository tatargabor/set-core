## 1. Save Hook (wt-hook-memory-save)

- [x] 1.1 Replace design.md extraction: use `grep '^\*\*Choice\*\*'` to pull only Choice lines, strip `**Choice**:` prefix, join with `. `, prefix with change name
- [x] 1.2 Remove separate Architecture/Learning memory save (delete the Goals section extraction)
- [x] 1.3 Remove separate Context/commit memory save — fold into the single Decision memory
- [x] 1.4 Add 300-char truncation with `...` suffix
- [x] 1.5 Change memory type to Decision, tags to `change:<name>,phase:apply,source:hook,decisions`
- [x] 1.6 Add fallback: if no design.md, save commit message as the memory content

## 2. Recall Hook (wt-hook-memory-recall)

- [x] 2.1 Add OpenSpec detection: run `openspec list --json` with 5s timeout, parse completed vs pending changes
- [x] 2.2 Build recall query from completed change names instead of prompt text
- [x] 2.3 Rewrite output format: bulleted list with `=== PROJECT MEMORY ===` header and consistency instruction
- [x] 2.4 Add fallback to prompt-based recall when openspec is not available

## 3. wt-loop Reflection (file-based learning capture)

- [x] 3.1 Add reflection instruction to `build_prompt` in `bin/wt-loop`: ask agent to write `.claude/reflection.md` as last step
- [x] 3.2 Add post-iteration reflection processing in `cmd_run`: read `.claude/reflection.md`, save to set-memory, delete file

## 4. Verify

- [x] 4.1 Test save hook manually in benchmark run-b directory: trigger on existing commits, verify single concise memory
- [x] 4.2 Test recall hook manually: verify OpenSpec-aware query and actionable output format
- [x] 4.3 Test reflection flow: create a mock reflection.md and verify wt-loop post-processing saves it
