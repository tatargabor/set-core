# web-build-time-quality-gates Specification

## Purpose
TBD - created by archiving change web-build-time-quality-gates. Update Purpose after archive.

## Requirements

### Requirement: ESLint configuration SHALL fail builds on raw `<img>` tags
The web project type SHALL deploy an ESLint flat configuration that enables `@next/next/no-img-element` at error severity for `src/app/**/*.{ts,tsx}` so that `pnpm lint --max-warnings=0` exits non-zero whenever a raw `<img>` element appears.

#### Scenario: Raw `<img>` tag fails lint
- **WHEN** a TSX file under `src/app/` contains `<img src="/foo.png" />`
- **AND** `pnpm lint --max-warnings=0` runs
- **THEN** the lint process SHALL exit with a non-zero status
- **AND** the output SHALL identify the offending file, line, and rule name `@next/next/no-img-element`

#### Scenario: `<Image>` component does not trigger the rule
- **WHEN** a TSX file imports `Image` from `next/image` and uses `<Image src="/foo.png" alt="" width={1} height={1} />`
- **AND** `pnpm lint --max-warnings=0` runs
- **THEN** the lint process SHALL exit zero with no diagnostic for that file

### Requirement: ESLint configuration SHALL fail builds on hardcoded JSX strings inside locale-routed pages
The web project type SHALL deploy an ESLint configuration that, for files matching `src/app/[locale]/**/*.{ts,tsx}`, treats user-visible literal strings inside JSX as errors via `eslint-plugin-i18next/no-literal-string`. Attribute values for `className`, `id`, `key`, `aria-*`, and `data-*` SHALL be ignored by the rule.

#### Scenario: Hardcoded user-visible string fails lint
- **WHEN** a TSX file at `src/app/[locale]/about/page.tsx` contains `<p>Welcome</p>`
- **AND** `pnpm lint --max-warnings=0` runs
- **THEN** the lint process SHALL exit non-zero
- **AND** the diagnostic SHALL name `i18next/no-literal-string`

#### Scenario: Ignored attributes do not trigger the rule
- **WHEN** a TSX file under `src/app/[locale]/` contains `<div className="card" data-testid="hero" aria-label="welcome" />`
- **AND** `pnpm lint --max-warnings=0` runs
- **THEN** the lint process SHALL exit zero with no diagnostic for those attribute values

#### Scenario: Strings outside the locale tree are not enforced
- **WHEN** a TSX file at `src/app/api/route.ts` returns `Response.json({ status: "ok" })`
- **AND** `pnpm lint --max-warnings=0` runs
- **THEN** the literal `"ok"` SHALL not produce an `i18next/no-literal-string` diagnostic

### Requirement: i18n completeness script SHALL detect missing translation keys
The web project type SHALL deploy `scripts/check-i18n-completeness.ts`, runnable via `pnpm check:i18n`, that loads every `messages/<locale>.json` file, walks every `useTranslations()` and `getTranslations()` call site under `src/`, and asserts every `(locale, dotted_key)` resolution exists in every locale file. The dotted key is `<namespace>.<key>` where `<namespace>` is the binding's argument and `<key>` is the literal first argument to `t()` from that binding (resolved per-binding-scope).

#### Scenario: Missing namespace key in one locale fails the script
- **WHEN** `useTranslations("checkout")` is called in `src/app/[locale]/checkout/page.tsx`
- **AND** the call site uses `t("title")`
- **AND** `messages/en.json` contains the `checkout.title` key but `messages/hu.json` does not
- **AND** `pnpm check:i18n` runs
- **THEN** the script SHALL exit with a non-zero status
- **AND** the output SHALL list the locale, the dotted key, and the source file:line

#### Scenario: Missing key under a present namespace fails the script
- **WHEN** a TSX file calls `t("welcome")` from `useTranslations("home")`
- **AND** `messages/hu.json` has a `home` namespace but no `welcome` child key
- **AND** `pnpm check:i18n` runs
- **THEN** the script SHALL exit non-zero
- **AND** the output SHALL identify the missing locale and dotted key

#### Scenario: Complete coverage exits zero with a count summary
- **WHEN** every dotted key resolves in every configured locale
- **AND** `pnpm check:i18n` runs
- **THEN** the script SHALL exit zero
- **AND** the output SHALL include a single INFO line stating files scanned, unique keys, and locales checked

### Requirement: Pre-commit hook SHALL block violating commits
The web project type SHALL deploy a Husky pre-commit hook at `.husky/pre-commit` that runs `pnpm lint-staged` (configured to run `eslint --max-warnings=0 --no-warn-ignored` over staged `*.{ts,tsx}` files in `src/`) followed by `pnpm check:i18n`. Either non-zero exit aborts the commit. The `package.json` SHALL declare a `prepare` script that invokes `husky` so the hook installs on `pnpm install`.

#### Scenario: Staged hardcoded string aborts the commit
- **WHEN** an agent stages a TSX file under `src/app/[locale]/` containing a hardcoded JSX string
- **AND** the agent runs `git commit -m "feat: add foo"`
- **THEN** the husky pre-commit hook SHALL run and exit non-zero
- **AND** no commit SHALL be created

#### Scenario: Compliant change commits successfully
- **WHEN** an agent stages a TSX file that uses `useTranslations()` correctly and includes the matching keys in every locale
- **AND** the agent runs `git commit -m "feat: add bar"`
- **THEN** the husky pre-commit hook SHALL exit zero
- **AND** the commit SHALL be created

### Requirement: Admin-route server-side auth pattern SHALL be documented as canonical
The web project type SHALL include a section in the deployed `auth-conventions.md` titled "Required admin-route server-side check". The section SHALL specify that `src/app/[locale]/admin/**/page.tsx` and `src/app/[locale]/admin/**/layout.tsx` MUST begin with the canonical pattern that calls `auth()` once, redirects to login when no session is present, and redirects to a non-admin landing page when the session role is not `ADMIN`. The section SHALL state that middleware-only enforcement is insufficient because of the Next.js Router Cache bypass on client-side navigation. Examples SHALL use generic locale prefixes and no consumer project name.

#### Scenario: Admin page lacking the inline check is flagged in review
- **WHEN** a review reviewer reads the deployed `auth-conventions.md`
- **THEN** the reviewer SHALL find a single canonical snippet for the admin-route check
- **AND** the snippet SHALL be copy-pasteable verbatim into a `page.tsx` or `layout.tsx`
- **AND** the section SHALL explain why middleware alone is insufficient

#### Scenario: Documentation does not name a consumer project
- **WHEN** the deployed `auth-conventions.md` is searched for any consumer project name
- **THEN** no match SHALL be found
- **AND** examples SHALL use generic locale prefixes such as `/hu` or `/en`
