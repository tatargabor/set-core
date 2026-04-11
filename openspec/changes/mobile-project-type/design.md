# Design: mobile-project-type

## Context

set-core's plugin architecture (`ProjectType` ABC → `CoreProfile` → module subclasses) already supports multi-level inheritance. The web module (`WebProjectType(CoreProfile)`) provides Next.js, Playwright, Prisma, and i18n support. A Capacitor-based mobile app reuses the entire web stack and adds a native shell layer on top.

The mobile module inherits from `WebProjectType` rather than `CoreProfile`, getting all web capabilities for free (Playwright E2E, Prisma gates, i18n directives, planning rules). It only adds what's mobile-specific.

## Goals / Non-Goals

**Goals:**
- Capacitor hybrid app support (iOS + Android via web codebase)
- Xcode build verification gate
- `cap sync` orchestration directive
- Template with Capacitor boilerplate on top of Next.js
- Share Extension / App Groups detection

**Non-Goals:**
- Native Swift/SwiftUI project support (separate future module)
- React Native / Expo support (future template variant, not this change)
- Android-specific build gates (future — focus on iOS first)
- App Store submission automation (out of scope)

## Decisions

### 1. Inherit from WebProjectType, not CoreProfile

**Decision**: `MobileProjectType(WebProjectType)`

**Rationale**: Capacitor apps ARE web apps with a native wrapper. All web verification rules (i18n, routing, cross-cutting), orchestration directives (lockfile serialize, i18n serialize), and engine integration (Playwright, Prisma, test parsing) apply directly. Inheriting avoids ~500 lines of duplication.

**Alternative considered**: Inherit from CoreProfile and compose web features manually — rejected because it would duplicate web logic and drift over time.

### 2. Module structure mirrors web module

**Decision**: Follow the exact same directory layout as `modules/web/`.

```
modules/mobile/
  pyproject.toml
  set_project_mobile/
    __init__.py
    project_type.py
    planning_rules.txt
    gates.py                    # Capacitor/Xcode gate executors
    templates/
      capacitor-nextjs/
        manifest.yaml
        capacitor.config.ts
        rules/
          capacitor-conventions.md
          native-bridge.md
```

**Rationale**: Consistency with existing modules. Developers familiar with web module can navigate mobile module immediately.

### 3. iOS-first, Android later

**Decision**: First version focuses on iOS (Xcode build gate, `cap sync ios`). Android support is additive and can be a follow-up change.

**Rationale**: The driving consumer project is iOS-only. Android gate (`gradle assembleDebug`) follows the same pattern and can be added without breaking changes.

### 4. Template extends web/nextjs via manifest

**Decision**: The `capacitor-nextjs` template includes only mobile-specific files. The web/nextjs template files are deployed first (via `--project-type web --template nextjs`), then mobile-specific files overlay on top.

**Alternative considered**: Duplicate all web/nextjs files into capacitor-nextjs template — rejected because it creates maintenance burden when web template updates.

**How it works**: `set-project init --project-type mobile --template capacitor-nextjs` will:
1. Deploy core rules (from CoreProfile)
2. Deploy web rules (inherited from WebProjectType)
3. Deploy mobile template files (overlay)

This works because `get_template_dir()` resolves per-module, and the init pipeline deploys parent templates first via the inheritance chain.

## Risks / Trade-offs

- **[Risk]** WebProjectType changes may break MobileProjectType → **Mitigation**: Unit tests that instantiate MobileProjectType and call all inherited methods. CI catches breakage.
- **[Risk]** Capacitor CLI version differences across projects → **Mitigation**: Detect version from `@capacitor/core` in package.json, gate commands adapt.
- **[Risk]** Xcode build gate may be slow (30-60s) → **Mitigation**: Make it optional via gate_overrides for non-native changes. Only run when ios/ directory is modified.

## Open Questions

- Should `cap sync` run as post-merge directive or as a dedicated gate? (Leaning: post-merge directive, like npm install)
- Should the template include a basic Share Extension scaffold, or leave that to the spec? (Leaning: leave to spec, keep template minimal)
