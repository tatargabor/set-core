# Spec: capacitor-nextjs-template

## ADDED Requirements

## IN SCOPE

- Template files for Capacitor + Next.js hybrid app
- capacitor.config.ts template
- Mobile-specific convention rules (.claude/rules/)
- manifest.yaml defining core files, protected files, and modules
- project-knowledge.yaml for mobile context

## OUT OF SCOPE

- iOS native source code (AppDelegate, Share Extension)
- Android native source code
- Capacitor plugin implementations
- CI/CD pipeline templates (fastlane, GitHub Actions)

### Requirement: Template registration

The `MobileProjectType` SHALL register a `capacitor-nextjs` template via `get_templates()`.

#### Scenario: Template listed

- **WHEN** `get_templates()` is called
- **THEN** the result SHALL include a `TemplateInfo` with `id="capacitor-nextjs"` and a valid `template_dir`

#### Scenario: Template directory exists

- **WHEN** `get_template_dir("capacitor-nextjs")` is called
- **THEN** it SHALL return a path to an existing directory containing template files

### Requirement: Capacitor config template

The template SHALL include a `capacitor.config.ts` starter file with sensible defaults.

#### Scenario: Config file deployed

- **WHEN** `set-project init --project-type mobile --template capacitor-nextjs` runs
- **THEN** `capacitor.config.ts` SHALL be created in the project root with `webDir` set to the Next.js build output directory

### Requirement: Mobile convention rules

The template SHALL include mobile-specific convention rules deployed to `.claude/rules/`.

#### Scenario: Rules deployed

- **WHEN** the template is deployed
- **THEN** `.claude/rules/capacitor-conventions.md` SHALL exist with guidance on Capacitor plugin usage, native bridge patterns, and platform-specific code organization

### Requirement: Manifest definition

The template SHALL include a `manifest.yaml` that defines which files are core (always deployed), protected (never overwritten), and optional modules.

#### Scenario: Manifest structure

- **WHEN** the manifest is read
- **THEN** it SHALL list `capacitor.config.ts` as a core file and any user-customizable config files as protected
