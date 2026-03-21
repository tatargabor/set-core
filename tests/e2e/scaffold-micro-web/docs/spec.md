# Micro Web — Minimal Next.js App

A tiny Next.js 14 application with 5 pages, basic navigation, and Playwright E2E tests.
Purpose: validate orchestration pipeline with new programmatic gate enforcement.

## Tech Stack
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS v4
- Playwright for E2E tests
- Vitest for unit tests

## Pages

### 1. Home Page (`/`)
- Hero section with app title "Micro Web"
- Short description paragraph
- Navigation links to all other pages

### 2. About Page (`/about`)
- Company description (lorem ipsum)
- Team section with 3 card placeholders (name, role)

### 3. Contact Page (`/contact`)
- Contact form: name, email, message fields
- Form validation (client-side): all fields required, email format check
- Submit button (no backend — just console.log the data)

### 4. Blog Page (`/blog`)
- List of 3 hardcoded blog posts (title, date, excerpt)
- Each links to a detail page

### 5. Blog Detail Page (`/blog/[slug]`)
- Show full blog post content (hardcoded data)
- Back link to blog list

## Requirements

### Navigation
- REQ-NAV-01: Header with site title and nav links to all 5 top-level pages
- REQ-NAV-02: Active page highlighted in nav
- REQ-NAV-03: Mobile-responsive hamburger menu

### Content
- REQ-CONTENT-01: Home hero section with title and description
- REQ-CONTENT-02: About page with team cards
- REQ-CONTENT-03: Blog list with 3 posts
- REQ-CONTENT-04: Blog detail shows full content for valid slug, 404 for invalid

### Form
- REQ-FORM-01: Contact form with name, email, message
- REQ-FORM-02: Client-side validation (required fields, email format)
- REQ-FORM-03: Submit logs to console (no server action needed)

### Testing
- REQ-TEST-01: Vitest unit tests for form validation logic
- REQ-TEST-02: Playwright E2E: visit each page, verify title/content
- REQ-TEST-03: Playwright E2E: submit contact form, verify validation

## Orchestrator Directives

```yaml
max_parallel: 2
review_before_merge: true
e2e_mode: per_change
time_limit: 2h
```
