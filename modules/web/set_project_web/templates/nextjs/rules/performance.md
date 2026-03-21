---
paths:
  - "src/app/**"
  - "src/components/**"
  - "next.config*"
---
# Performance Conventions

## Core Web Vitals Targets
- **LCP** (Largest Contentful Paint): < 2.5s
- **INP** (Interaction to Next Paint): < 200ms
- **CLS** (Cumulative Layout Shift): < 0.1

## Images
- Always use `next/image` — never raw `<img>` tags
- Set explicit `width` and `height` (or `fill`) to prevent layout shift
- Use `priority` on above-the-fold hero/banner images (LCP optimization)
- Format: let Next.js auto-serve WebP/AVIF — don't manually convert
- Use `sizes` prop for responsive images to avoid oversized downloads

## Fonts
- Use `next/font` for self-hosted fonts — eliminates external font requests
- Set `display: "swap"` to prevent invisible text during font load
- Preload only the weights/styles actually used

## Code Splitting & Lazy Loading
- Use `next/dynamic` for heavy client components not needed on initial render
- Lazy-load below-the-fold content (modals, tabs, carousels)
- Avoid importing large libraries at the top level — dynamic import when possible
- Route-based splitting is automatic with App Router — don't fight it

## Data Fetching
- Fetch data in Server Components — avoid client-side `useEffect` fetches for initial data
- Use `loading.tsx` for streaming SSR — show UI shell while data loads
- Use React `cache()` to deduplicate identical fetches within a render
- Set appropriate `revalidate` for ISR pages — don't default to 0

## Caching Strategy
- Understand the Next.js cache layers: Request Memoization, Data Cache, Full Route Cache, Router Cache
- Use ISR (`revalidate`) for semi-static pages; use `revalidatePath`/`revalidateTag` for on-demand invalidation after mutations
- Set explicit `Cache-Control` headers on API routes: `s-maxage` + `stale-while-revalidate` for CDN-cacheable endpoints; `no-store` for authenticated/sensitive data
- Be intentional about caching — Next.js 15+ does NOT cache by default in many cases

## Bundle Hygiene
- Monitor bundle size — `@next/bundle-analyzer` in devDependencies
- Avoid barrel exports (`index.ts` re-exporting everything) in large modules
- Tree-shake: use named imports, not namespace imports (`import * as`)
- `"use client"` boundary as deep as possible — don't make entire pages client components

## Web Vitals Monitoring
- Use `useReportWebVitals` hook to send CWV data to analytics
- Track LCP, INP, CLS, FCP, TTFB in production
- Set up alerting for regressions beyond the "good" thresholds
