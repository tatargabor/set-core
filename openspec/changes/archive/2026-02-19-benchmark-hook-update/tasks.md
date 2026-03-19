## 1. Update init-with-memory.sh

- [x] 1.1 Remove `set-memory-hooks` from the prerequisites check (line 20)
- [x] 1.2 Remove `set-memory-hooks install` call (line 51)
- [x] 1.3 Update the "Done" summary to say "hooks deployed" instead of "hooks installed" (line 122)

## 2. Replace Proactive Memory with Persistent Memory in with-memory.md

- [x] 2.1 Replace the "Proactive Memory" section (lines 49-95) with the "Persistent Memory" section from the main CLAUDE.md — hook-driven automatic recall, cite-from-memory instruction, emphasis-only `remember`
- [x] 2.2 Add a one-line "Recall-then-verify" note after the Persistent Memory section (verify recalled info against codebase before acting)

## 3. Update run-guide.md

- [x] 3.1 Remove `set-memory-hooks` from the Prerequisites list (line 7)
- [x] 3.2 Update the Run B description (line 35) to remove `set-memory-hooks install` reference — describe it as using `wt-deploy-hooks` + hook-driven memory instead
