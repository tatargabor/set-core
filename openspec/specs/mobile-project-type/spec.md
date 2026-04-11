# Spec: mobile-project-type

## ADDED Requirements

## IN SCOPE

- MobileProjectType class inheriting from WebProjectType
- Capacitor-specific verification rules (config consistency, plugin tracking)
- Capacitor-specific orchestration directives (cap sync, native config serialization)
- iOS build detection (Xcode project, capacitor.config.ts)
- Xcode build gate executor
- Planning rules for mobile decomposition
- Entry point registration via pyproject.toml
- Unit tests for the module

## OUT OF SCOPE

- Android-specific build gates (gradle)
- App Store / TestFlight submission automation
- Native Swift/SwiftUI project support
- React Native or Expo support
- Capacitor plugin marketplace integration
- Device simulator launch automation

### Requirement: Module metadata and inheritance

The mobile module SHALL declare itself as project type `mobile` with parent `web`. It SHALL inherit all verification rules, orchestration directives, and engine integration methods from `WebProjectType`.

#### Scenario: Profile resolution

- **WHEN** a project has `set/plugins/project-type.yaml` with `type: mobile`
- **THEN** `load_profile()` SHALL resolve to `MobileProjectType`
- **THEN** `info.name` SHALL be `"mobile"` and `info.parent` SHALL be `"web"`

#### Scenario: Inherited web rules are present

- **WHEN** `get_verification_rules()` is called on `MobileProjectType`
- **THEN** the result SHALL include all rules from `WebProjectType` (i18n-completeness, route-registered, etc.) plus mobile-specific rules

### Requirement: Capacitor config verification

The module SHALL verify that `capacitor.config.ts` is consistent with the web app configuration.

#### Scenario: Capacitor config exists

- **WHEN** a project contains `capacitor.config.ts`
- **THEN** verification SHALL check that `webDir` points to an existing build output directory

#### Scenario: Missing Capacitor config

- **WHEN** a project does not contain `capacitor.config.ts`
- **THEN** verification SHALL emit a warning that Capacitor is not configured

### Requirement: Capacitor sync directive

The module SHALL include an orchestration directive that runs `npx cap sync` after changes that modify `capacitor.config.ts` or native plugin dependencies.

#### Scenario: Config change triggers sync

- **WHEN** a change modifies `capacitor.config.ts` or adds a Capacitor plugin to `package.json`
- **THEN** the orchestration directive SHALL trigger `npx cap sync` as a post-merge action

### Requirement: iOS build detection

The module SHALL detect iOS build capability by checking for `ios/App/` directory and Xcode project files.

#### Scenario: iOS project detected

- **WHEN** `ios/App/App.xcodeproj` exists in the project
- **THEN** `detect_build_command()` SHALL return a command that includes both `npm run build` and `npx cap sync ios`

#### Scenario: No iOS project

- **WHEN** no `ios/` directory exists
- **THEN** the module SHALL fall back to web-only build detection (inherited behavior)

### Requirement: Native config serialization

The module SHALL serialize changes that modify native project files (`ios/App/`, `android/app/`) to prevent merge conflicts in Xcode/Gradle project files.

#### Scenario: Parallel native changes serialized

- **WHEN** two changes both modify files under `ios/App/`
- **THEN** the orchestration directive SHALL serialize their execution

### Requirement: Planning rules for mobile

The module SHALL provide planning rules that guide the decomposer to separate native changes from web changes.

#### Scenario: Planning rules loaded

- **WHEN** `planning_rules()` is called
- **THEN** the result SHALL include guidance on separating web-only changes from changes that touch native code

### Requirement: Capacitor plugin tracking

The module SHALL include a verification rule that checks Capacitor plugin versions are consistent between `package.json` and the native projects.

#### Scenario: Plugin version mismatch

- **WHEN** `@capacitor/core` version in `package.json` differs significantly from the Capacitor version in `ios/App/Podfile.lock` or SPM packages
- **THEN** verification SHALL emit a warning about potential version mismatch
