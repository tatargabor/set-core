# Proposal: mobile-project-type

## Why

set-core currently supports web (Next.js) and example (Dungeon Builder) project types, but has no support for mobile applications. Capacitor-based hybrid apps are a growing pattern — they reuse web codebases (Next.js, Vue, React) and wrap them in native iOS/Android shells. A `mobile` project type extends the existing `web` type with Capacitor-specific gates, verification rules, and templates, enabling orchestrated development of hybrid mobile apps.

## What Changes

- **New `modules/mobile/` plugin** — `MobileProjectType(WebProjectType)` that inherits all web capabilities and adds:
  - Capacitor sync/build verification gates
  - iOS/Android native shell detection
  - Xcode build gate for iOS
  - Share Extension and App Groups awareness
  - Capacitor plugin dependency tracking
- **New `capacitor-nextjs` template** — extends the web/nextjs template with Capacitor config, iOS project structure, and mobile-specific rules
- **Entry point registration** — `pyproject.toml` with `set_tools.project_types` entry for `mobile`
- **Mobile-specific verification rules** — Capacitor config consistency, native entitlements, plugin version checks
- **Mobile-specific orchestration directives** — serialize native config changes, post-merge `cap sync`
- **Planning rules** — mobile-specific decomposition guidance (native vs web changes, platform testing)

- **Core fix: MRO-aware `get_template_dir()`** — the base `ProjectType.get_template_dir()` must walk the MRO so inherited templates resolve to the correct parent module's directory
- **`modules/dev-guide.md`** — developer guide documenting module inheritance patterns, override strategies, and the template system

## Capabilities

### New Capabilities

- `mobile-project-type` — Core mobile project type plugin with verification, directives, and engine integration
- `capacitor-nextjs-template` — Template variant for Capacitor + Next.js hybrid apps
- `module-dev-guide` — Developer documentation for creating new project type modules

### Modified Capabilities

- `profile-loader` — Fix `get_template_dir()` to walk MRO for multi-level inheritance support

## Impact

- **Core**: One method change in `lib/set_orch/profile_types.py` — `get_template_dir()` walks MRO instead of using `type(self)` directly. Required for template inheritance to work across module layers.
- **New module**: `modules/mobile/` (new directory, no changes to existing modules)
- **Web module**: No changes — mobile inherits from it
- **Dependencies**: `modules/mobile/pyproject.toml` depends on `set-project-web` (for inheritance)
- **Documentation**: `modules/dev-guide.md` — new file, no existing docs affected
