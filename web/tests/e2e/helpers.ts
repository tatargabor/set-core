import { type Page, type APIRequestContext, expect } from '@playwright/test'

export const PROJECT = process.env.E2E_PROJECT!
export const ORCH_BASE = `/p/${PROJECT}/orch`

export interface ChangeInfo {
  name: string
  status: string
  phase?: number
  depends_on?: string[]
  input_tokens?: number
  output_tokens?: number
  test_result?: string | null
  build_result?: string | null
  smoke_result?: string | null
  review_result?: string | null
  spec_coverage_result?: string | null
  session_count?: number
  started_at?: string | null
  completed_at?: string | null
  gate_total_ms?: number
}

export interface StateData {
  status?: string
  changes: ChangeInfo[]
  phases?: Record<string, { status: string }>
}

/** Fetch full orchestration state from the API. */
export async function getApiState(request: APIRequestContext): Promise<StateData> {
  const res = await request.get(`/api/${PROJECT}/state`)
  expect(res.ok()).toBeTruthy()
  return res.json()
}

/** Navigate to a dashboard tab and wait for it to be active. */
export async function navigateToTab(page: Page, tab: string) {
  await page.goto(`${ORCH_BASE}?tab=${tab}`)
  // Wait for the tab button to have the active styling
  await page.waitForSelector(`[data-tab="${tab}"]`, { timeout: 10_000 })
}

/** Mirror of the frontend formatTokens function for assertion comparison. */
export function formatTokens(n?: number | null): string {
  if (!n) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

/** Check if a change has any gate results. */
export function hasGates(c: ChangeInfo): boolean {
  return !!(c.build_result || c.test_result || c.review_result || c.smoke_result || c.spec_coverage_result)
}
