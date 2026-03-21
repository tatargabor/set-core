---
description: Next.js performance and data fetching patterns
globs:
  - "src/app/**/*.{ts,tsx}"
  - "app/**/*.{ts,tsx}"
  - "src/components/**/*.{ts,tsx}"
---

# Next.js Patterns

## 1. force-dynamic Anti-Pattern

Never use `export const dynamic = 'force-dynamic'` on pages with mixed static and dynamic content. It disables all caching for the entire page.

**Wrong — blanket force-dynamic because one section needs fresh data:**
```typescript
// Kills SSG/ISR for the ENTIRE page — all sections re-rendered on every request
export const dynamic = 'force-dynamic'

export default async function HomePage() {
  const products = await getProducts()         // these could be cached
  const categories = await getCategories()     // these could be cached
  const testimonials = await getTestimonials() // only this needs fresh data
  return <><Products /><Categories /><Testimonials /></>
}
```

**Correct — targeted caching for the dynamic parts only:**
```typescript
// Option A: ISR — entire page revalidates periodically
export const revalidate = 300  // 5-minute ISR

// Option B: per-query caching for the dynamic section
import { unstable_cache } from 'next/cache'
const getCachedTestimonials = unstable_cache(
  async () => db.review.findMany({ where: { featured: true } }),
  ['testimonials'],
  { revalidate: 300 }
)

// Option C: client-side fetch for the dynamic section, keep page static
// Use a client component with useEffect for testimonials only
```

**The rule:** Reserve `force-dynamic` for pages where EVERY byte must be personalized on every request (e.g., user dashboard with real-time data). For pages with mixed content, use ISR (`revalidate`), per-query caching (`unstable_cache`), or Suspense boundaries with streaming.

## 2. Server Actions in Client Effects

Prefer fetching data in server components and passing as props. If a server action must be called from a client `useEffect`, always wrap in try/catch with loading and error states.

**Wrong — server action in useEffect without error handling or auth scoping:**
```typescript
'use client'
export default function OrderDetail({ orderId }: { orderId: string }) {
  const [returnReq, setReturnReq] = useState(null)
  useEffect(() => {
    // No try/catch — unhandled rejection if server action fails
    // orderId comes from URL params — user can tamper with it
    getReturnRequest(orderId).then(setReturnReq)
  }, [orderId])
}
```

**Correct — server component fetch (preferred) or guarded client fetch:**
```typescript
// Option A (preferred): fetch in server component, pass as props
export default async function OrderDetail({ params }: { params: { id: string } }) {
  const user = await getCurrentUser()
  const order = await db.order.findUnique({ where: { id: params.id, userId: user.id } })
  const returnReq = await db.returnRequest.findFirst({
    where: { orderId: order.id, order: { userId: user.id } }
  })
  return <OrderDetailClient order={order} returnRequest={returnReq} />
}

// Option B: if client-side fetch is necessary
'use client'
export default function OrderDetail({ orderId }: { orderId: string }) {
  const [returnReq, setReturnReq] = useState(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    getReturnRequest(orderId)
      .then(setReturnReq)
      .catch(() => setError("Failed to load return request"))
      .finally(() => setLoading(false))
  }, [orderId])
}
```

**The rule:** Data fetching belongs in server components whenever possible. If a server action must be called from `useEffect`: (1) wrap in try/catch with error state, (2) show loading indicator, (3) ensure the server action internally scopes by userId — the ID comes from URL params the user controls.
