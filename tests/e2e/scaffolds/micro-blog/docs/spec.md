# Micro Blog — Minimal Next.js Blog App

A tiny Next.js 14 blog application with posts, categories, and search.
Purpose: validate orchestration pipeline with a content-focused web app.

## Tech Stack
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS v4
- Playwright for E2E tests
- Vitest for unit tests

## Pages

### 1. Home Page (`/`)
- Hero section with blog title "Micro Blog"
- Latest 3 posts listed with title, date, excerpt
- Sidebar with category list

### 2. Post Detail Page (`/posts/[slug]`)
- Full post content (hardcoded markdown-style data)
- Author name and publish date
- Back link to home
- Related posts section (2 other posts from same category)

### 3. Category Page (`/categories/[slug]`)
- Category title and description
- List of posts in that category
- Back link to home

### 4. About Page (`/about`)
- Blog description and author bio
- Contact email (mailto link)

### 5. Search Page (`/search`)
- Search input field with real-time filtering
- Filters posts by title and excerpt (client-side)
- Shows "No results" when nothing matches

## Data

Hardcoded array of 6 blog posts across 3 categories:
- **Tech** (2 posts): "Getting Started with Next.js", "TypeScript Tips"
- **Design** (2 posts): "Tailwind CSS Best Practices", "Color Theory Basics"
- **Life** (2 posts): "Remote Work Setup", "Book Recommendations 2024"

## Requirements

### Navigation
- REQ-NAV-01: Header with blog title and nav links (Home, About, Search)
- REQ-NAV-02: Active page highlighted in nav
- REQ-NAV-03: Mobile-responsive hamburger menu

### Content
- REQ-CONTENT-01: Home page shows latest 3 posts with excerpts
- REQ-CONTENT-02: Post detail renders full content with author/date
- REQ-CONTENT-03: Category page lists all posts in category
- REQ-CONTENT-04: Post detail shows 404 for invalid slug
- REQ-CONTENT-05: Related posts section on post detail

### Search
- REQ-SEARCH-01: Search input with real-time client-side filtering
- REQ-SEARCH-02: Filters by title and excerpt text
- REQ-SEARCH-03: Shows "No results found" for empty results

### Sidebar
- REQ-SIDEBAR-01: Category list with post count per category
- REQ-SIDEBAR-02: Category links navigate to category page

### Testing
- REQ-TEST-01: Vitest unit tests for search filtering logic
- REQ-TEST-02: Playwright E2E: visit each page, verify title/content
- REQ-TEST-03: Playwright E2E: search functionality filters correctly
- REQ-TEST-04: Playwright E2E: category navigation works

## Orchestrator Directives

```yaml
max_parallel: 2
review_before_merge: true
e2e_mode: per_change
time_limit: 2h
```
