## Context

The current `generate_startup_guide()` in `dispatcher.py:461-504` detects Node.js project stack and writes inline markdown to worktree CLAUDE.md. This has two problems:
1. Web-specific logic hardcoded in core (violates modular architecture)
2. Main branch CLAUDE.md never gets startup information — only worktrees do

The existing detection logic is solid and well-tested. We're moving it to the profile system and changing the output from inline CLAUDE.md content to a standalone `START.md` file.

## Goals / Non-Goals

**Goals:**
- START.md as a standalone, auto-generated file in project root
- Profile-driven: web module owns the detection, core provides the ABC
- CLAUDE.md references START.md (not inline content)
- Post-merge regeneration keeps START.md current on main

**Non-Goals:**
- Changing what is detected (same: pm, dev, db, test, e2e)
- Adding non-Node.js detection (future work for other profiles)
- Making START.md a static template (it's always generated dynamically)

## Decisions

### 1. File name: `START.md`
Short, obvious, convention-friendly. Lives at project root alongside README.md and CLAUDE.md.
**Alternative considered:** `docs/getting-started.md` — too buried, agents won't find it easily.

### 2. Profile method returns full file content, not structured data
`generate_startup_file(path) -> str` returns the complete markdown string.
**Why:** Simpler than a structured Step dataclass system. Each profile has full control over formatting. If we later need structured data (e.g., for script generation), we can add `generate_startup_steps()` returning a list.
**Alternative considered:** `list[StartupStep]` dataclass — over-engineering for current needs.

### 3. Dispatcher regenerates on every dispatch (not idempotent skip)
Unlike the current `append_startup_guide_to_claudemd()` which skips if section exists, the new flow always regenerates START.md. The main branch state may have changed between dispatches.
**Why:** START.md is auto-generated, so overwriting is safe. No user content to preserve.

### 4. CLAUDE.md reference is a thin pointer
```markdown
## Getting Started
<!-- set-core:managed -->
See [START.md](START.md) for application startup commands.
```
Not inline content — just a reference. This keeps CLAUDE.md clean and avoids merge conflicts.

### 5. Move detection logic to WebProjectType, delete from dispatcher
The `generate_startup_guide()` and `_detect_package_manager()` functions move to `modules/web/set_project_web/profile.py`. The dispatcher calls `profile.generate_startup_file(wt_path)`.
`append_startup_guide_to_claudemd()` is replaced by `write_startup_file()` utility in dispatcher that handles the file write.

### 6. Post-merge: merger calls profile.generate_startup_file() on main
After successful merge in `merger.py`, load the profile and regenerate START.md. This is a single function call — no complex logic needed.

## Risks / Trade-offs

[Risk] START.md gets out of sync if agent manually edits it → Mitigation: auto-generated header warns not to edit, post-merge always regenerates
[Risk] Profile not loadable in merger context → Mitigation: try/except, skip silently if profile load fails
[Risk] Old `## Application Startup` sections in existing projects → Mitigation: leave them, don't migrate. New dispatches will create START.md alongside.

## Migration Plan

1. Add ABC method to `profile_types.py`
2. Implement in `WebProjectType` (copy logic from dispatcher)
3. Update dispatcher to use profile + write START.md
4. Update merger to regenerate post-merge
5. Update deploy.sh to add CLAUDE.md reference
6. Delete old `generate_startup_guide()` from dispatcher
7. No breaking changes — old `## Application Startup` in CLAUDE.md is ignored, not removed
