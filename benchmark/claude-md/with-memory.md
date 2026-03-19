# CraftBazaar — Multi-Vendor Artisan Marketplace

## Project Setup

- **Stack**: Next.js 14 (App Router) + Prisma + SQLite + TypeScript + Tailwind CSS
- **Dev server**: `PORT=4001 npm run dev`
- **Database**: SQLite (file-based, `prisma/dev.db`)
- **Migrations**: `npx prisma migrate dev`
- **Generate client**: `npx prisma generate` (required after schema changes)
- **Seed**: `npx prisma db seed`
- **Tests**: `npm test`

## Acceptance Testing

Each change has a corresponding test script in `tests/test-NN.sh`. After implementing a change:

1. Start the dev server if not running:
   ```bash
   PORT=4001 npm run dev &
   sleep 3
   ```

2. Run the test for the change you just implemented:
   ```bash
   bash tests/test-NN.sh 4001
   ```

3. If the test fails, fix the issues and re-run until all checks pass.

4. Do NOT commit until the test passes.

**Important**: These tests check API responses, schema structure, and page content. They are the acceptance criteria for each change. **Test scripts are read-only** — fix your code to match the tests, never modify the test files. Later tests include regression checks that verify earlier fixes survived.

## OpenSpec Workflow

This project uses OpenSpec for structured change management. Key commands:

- `openspec list --json` — See all changes and their status
- `/opsx:ff <change-name>` — Create all artifacts for a change
- `/opsx:apply <change-name>` — Implement a change's tasks
- `openspec status --change "<name>" --json` — Check change progress

When implementing a change:
1. Use `/opsx:ff` to create artifacts (proposal, specs, design, tasks)
2. Use `/opsx:apply` to implement the tasks
3. Run `bash tests/test-NN.sh 4001` and fix any failures
4. Commit all work when done

## Persistent Memory

This project uses persistent memory (shodh-memory) across sessions. Memory context is automatically injected into `<system-reminder>` tags in your conversation — **you MUST read and use this context**.

**IMPORTANT: On EVERY prompt, check for injected memory context (system-reminder tags labeled "PROJECT MEMORY", "PROJECT CONTEXT", or "MEMORY: Context for this command"). When present, acknowledge and use it BEFORE doing independent research. If a memory directly answers the user's question or provides a known fix, cite it explicitly (e.g., "From memory: ...") instead of re-investigating from scratch. This applies to every turn, not just the first one.**

**How it works:**
- Session start → relevant memories loaded as system-reminder
- Every prompt → topic-based recall injected as system-reminder
- Every tool use → relevant past experience injected as system-reminder
- Tool errors → past fixes surfaced automatically
- Session end → insights extracted and saved

**Emphasis (use sparingly):**
- `echo "<insight>" | set-memory remember --type <Decision|Learning|Context> --tags source:agent,<topic>` — mark something as HIGH IMPORTANCE
- `set-memory forget <id>` — suppress or correct a wrong memory
- Most things are remembered automatically. Only use `remember` for emphasis.

**Recall-then-verify (CRITICAL):** Memory provides starting points, not final answers. After recalling implementation details, ALWAYS grep or read the current code to verify before acting. Files may have changed since the memory was saved. Do not skip verification even if the recall seems highly relevant — memory-induced overconfidence leads to incomplete implementations.

## Benchmark Task

You are autonomously building CraftBazaar through 12 sequential changes. Each session starts fresh (no conversation history from previous sessions).

**Project spec**: Read `docs/benchmark/project-spec.md` for the full domain description, tech stack, entities, and project structure. Read this before your first change.

**Changes are in three phases:**
- **01-06**: Build the core marketplace (products, cart, vendors, discounts, checkout, order workflow)
- **07-09**: Revision changes — stakeholder changed their mind on earlier decisions
- **10-11**: Feedback changes — design team corrections to UI/UX
- **12**: Sprint retro — fix 12 cross-cutting bugs

**Your workflow each session:**

1. Find the next incomplete change. There are exactly 12 changes (01 through 12):
   ```bash
   ls results/change-*.json 2>/dev/null   # which changes are done
   ls docs/benchmark/[0-9]*.md            # all 12 change definitions
   ```
   A change is done ONLY when its `results/change-NN.json` file exists.
   The `openspec list` "no-tasks" status means NOT STARTED — it still needs `/opsx:ff`.
   Read the next unfinished change definition file. If this is the first change, also read `docs/benchmark/project-spec.md`.

2. **Recall past experience** before starting implementation:
   ```bash
   set-memory recall "<change-name> implementation" --limit 5 --mode hybrid
   ```

3. Implement the change:
   - Run `/opsx:ff <change-name>` to create artifacts
   - Run `/opsx:apply <change-name>` to implement tasks
   - Run `bash tests/test-NN.sh 4001` to verify
   - Fix any test failures and re-run until ALL checks pass
   - The test script automatically creates `results/change-NN.json` when all checks pass

4. Commit all work:
   ```bash
   git add -A && git commit -m "<change-name>: <summary>"
   ```

5. Check if done: you are finished ONLY when `ls results/change-*.json | wc -l` returns 12. If fewer than 12, go back to step 1.

**Important:**
- Work on changes in order (01 → 02 → ... → 12)
- Each change builds on the previous — don't skip ahead
- Changes 07-12 are revisions/corrections — if the memory hook injects a "RE-READ these files" block, you MUST read every listed file BEFORE implementing. Do NOT rely on memory alone for these changes.
- Changes 07-09 REVISE earlier decisions — read them carefully and recall what you built
- Changes 10-11 CORRECT design issues — follow the specific corrections exactly
- Change 12 has 12 bugs to fix — read ALL affected files before implementing any fix
- If you encounter an error, debug and fix it — don't ask for help
- If a previous change's code needs updating for the current change, update it
- Run the acceptance test after each change — do NOT commit until it passes
- Do NOT create `results/change-NN.json` files manually — only the test scripts create them on pass
- Do NOT modify test scripts — they are read-only acceptance criteria
