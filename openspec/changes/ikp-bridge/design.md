## Context

The IKP (Integration Knowledge Pack) system lives at `~/code2/ikp/` as a standalone Python package with 18 packs covering external APIs (Stripe, Billingo, Wise, Gmail, etc.). Each pack has 5 layers: L1 Knowledge, L2 Planning, L3 Implementation (per-language), L4 Testing, L5 Operations.

set-core's orchestration pipeline needs to consume IKP packs at different phases — the decomposer needs L1+L2 for complexity awareness, the dispatcher needs L3 for agent rule injection, and the verify gate needs L4 for test validation. Currently there is no bridge between the two systems.

The design pipeline (`has_design_pipeline`, `detect_design_source`, `get_design_dispatch_context`) provides the exact pattern to follow: a directive controls activation, the profile provides detection, and the dispatcher injects context. IKP follows this same architecture.

## Goals / Non-Goals

**Goals:**
- Provide a thin bridge module that wraps IKP's Python API for set-core consumption
- Support `.ikp.yaml` project config to declare packs and pack source directory
- Add `ikp_pipeline` directive to orchestration config (auto/none)
- Gracefully degrade when the `ikp` package is not installed
- Load specific layers by orchestration phase (decompose → L1+L2, dispatch → L3, verify → L4)

**Non-Goals:**
- L5 Operations / deploy integration (later change)
- IKP MCP server integration
- Pack authoring or generation from set-core
- Automatic pack discovery by scanning spec text (that's `ikp-decomposer-dispatch`)
- Remote pack registry support

## Decisions

### D1: Module placement — `lib/set_orch/ikp_bridge.py` (Layer 1 core)

IKP is not project-type specific — any project can use integration packs regardless of being web/mobile/CLI. The bridge belongs in Layer 1 core, not in modules/web/.

Alternative: Profile hook only (each module wires IKP). Rejected — this would duplicate the same wiring logic across every module and force module authors to know about IKP internals.

### D2: Optional import with graceful skip

Follow the design pipeline pattern: check a directive first, then try to import the ikp package. If the package is not installed, `has_ikp_pipeline()` returns False and all bridge functions return empty results.

```python
def has_ikp_pipeline(project_path: Path, directives: dict | None = None) -> bool:
    dp = (directives or {}).get("ikp_pipeline", "auto")
    if dp == "none":
        return False
    if not _ikp_available():
        return False
    config = load_ikp_config(project_path)
    return config is not None and len(config.packs) > 0
```

The `_ikp_available()` function uses a try/except import. The package is listed as an optional dependency in `pyproject.toml` under `[project.optional-dependencies]`.

### D3: `.ikp.yaml` format — minimal project config

```yaml
ikp: "0.2"
packs:
  - billingo
  - wise-payments
  - google-gmail
packs_dir: ~/code2/ikp/packs
language: typescript
```

Fields:
- `ikp`: Standard version (matches pack format version)
- `packs`: List of pack names to use
- `packs_dir`: Absolute or `~`-expanded path to pack files directory. Required because IKP is not a pip-installed package with a known location.
- `language`: Default implementation language for L3 injection

Location: project root (next to `orchestration.yaml`). The bridge reads this via `load_ikp_config()`.

### D4: Phase-to-layer mapping

| Orchestration phase | IKP layers loaded | Token budget |
|---|---|---|
| decompose | L1 (knowledge) + L2 (planning) | ~3K per pack |
| dispatch | L1 (auth, errors only) + L3 (implementation, language-filtered) | ~3K per pack |
| verify | L4 (testing) + L1 (error catalog) | ~2K per pack |

The bridge exposes `get_context_for_phase(phase, pack_names, language)` which maps internally to the right `load_pack(layers=[...])` call.

### D5: IkpConfig dataclass

```python
@dataclass
class IkpConfig:
    packs: list[str]
    packs_dir: Path
    language: str
    ikp_version: str = "0.2"
```

Loaded once per orchestration run, cached at module level (same pattern as profile loader).

## Risks / Trade-offs

**[Risk] IKP package API changes break the bridge** → Pin to ikp standard version in `.ikp.yaml`. The bridge validates `ikp_version` matches the installed package. If mismatch, log warning and skip.

**[Risk] Large token cost if many packs loaded at decompose time** → Cap at 5 packs maximum in decompose context. Log warning if project declares more. Individual pack summaries are truncated to pack.yaml metadata (capabilities + pitfalls) if combined context exceeds 15K tokens.

**[Risk] `packs_dir` is an absolute path — not portable** → This is acceptable for now (single-developer orchestration). The `~` expansion handles the common case. Future: IKP pip package with discover_packs() default path.

**[Trade-off] Direct import vs subprocess** → Direct import is faster and type-safe but couples set-core to IKP's Python API. Accepted because: (a) both are Python, (b) the API is small and stable (3 functions), (c) subprocess would require stdout parsing. The optional dependency pattern provides the escape hatch.
