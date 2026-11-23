---
paths:
  - "README.md"
---

# README Updates

There is no separate README guide any more: `docs/readme-guide.md` was archived in March 2026
(`docs/archive/readme-guide.md`, stale) and this rule pointed at it for eight months (B-202).
The README itself is the reference for its structure. When updating it:

1. Keep the existing section order (`grep -n '^## ' README.md`); the first section says what
   set-core is TODAY, and the orchestration-era sections are being cut back as
   `fleet-era-consolidation` retires the engine.
2. Run `ls bin/set-*` and check that every CLI the README names still exists, and that no
   retired one (see `templates/core/retired-paths.txt` and `retire-orchestration-cli`) is
   presented as current.
3. English only; no consumer project names (see the release-safety rule and `set-leakscan`).
