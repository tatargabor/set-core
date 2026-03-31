# Design: design-make-parser

## Decisions

### D1: Python parser, not bash
The .make file is a ZIP containing JSON (ai_chat.json). Python handles ZIP + JSON natively. The parser lives in `lib/set_orch/design_parser.py` with a thin `bin/set-design-sync` bash wrapper.

### D2: DesignParser base class for extensibility
`DesignParser` ABC with `parse(path) -> DesignSystem` method. `MakeParser` implements it for .make files. Future parsers (FigmaApiParser, PenpotParser) extend the same base. Format detection in the CLI layer, not the parser.

### D3: Spec sync uses marker-based replacement
The `## Design Reference` section is delimited — the tool finds it by heading and replaces everything until the next `## ` heading or EOF. This makes re-runs idempotent and safe.

### D4: design-system.md is the canonical design source
Once generated, `design-system.md` is the single source for the dispatch pipeline. The dispatcher reads it directly (structured markdown → easy to parse sections). No need to convert to JSON or YAML.

### D5: --spec-dir is explicit, not auto-detected
The user must specify where the specs are. This prevents accidental modification of files outside the intended scope. The spec dir can be the same directory as the .make file or different.

### D6: bridge.sh fallback chain, not replacement
The existing `design_context_for_dispatch()` is enhanced with a fallback chain, not replaced. If `design-system.md` exists → use it. If not → existing snapshot logic. This means the tool is optional — projects without .make files still work.

## File Map

| File | Action | Description |
|------|--------|-------------|
| `lib/set_orch/design_parser.py` | New | DesignParser ABC + MakeParser + DesignSystem dataclass |
| `bin/set-design-sync` | New | CLI wrapper (bash) — arg parsing, calls Python parser |
| `lib/design/bridge.sh` | Modify | design_context_for_dispatch() fallback to design-system.md |
| `docs/guide/design-integration.md` | New | Full guide: Figma Make → design-system.md → sentinel |
| `docs/guide/orchestration.md` | Modify | Add "Pre-Run Checklist" section |
| `docs/guide/sentinel.md` | Modify | Add "Spec Quality Prerequisites" section |
