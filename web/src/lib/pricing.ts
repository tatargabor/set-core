/** Model pricing table and cost estimation utilities. */

// Prices per million tokens (USD)
interface ModelPricing {
  input: number
  output: number
  cacheRead: number
  cacheWrite: number
}

const pricing: Record<string, ModelPricing> = {
  'claude-haiku-4-5-20251001': { input: 0.80, output: 4.00, cacheRead: 0.08, cacheWrite: 1.00 },
  'claude-sonnet-4-20250514': { input: 3.00, output: 15.00, cacheRead: 0.30, cacheWrite: 3.75 },
  'claude-opus-4-20250514': { input: 15.00, output: 75.00, cacheRead: 1.50, cacheWrite: 18.75 },
  // Aliases
  'haiku': { input: 0.80, output: 4.00, cacheRead: 0.08, cacheWrite: 1.00 },
  'sonnet': { input: 3.00, output: 15.00, cacheRead: 0.30, cacheWrite: 3.75 },
  'opus': { input: 15.00, output: 75.00, cacheRead: 1.50, cacheWrite: 18.75 },
}

// Default to sonnet pricing when model unknown
const defaultPricing: ModelPricing = pricing['sonnet']

function resolve(model?: string): ModelPricing {
  if (!model) return defaultPricing
  const lower = model.toLowerCase()
  // Direct match
  if (pricing[lower]) return pricing[lower]
  // Partial match
  if (lower.includes('haiku')) return pricing['haiku']
  if (lower.includes('opus')) return pricing['opus']
  if (lower.includes('sonnet')) return pricing['sonnet']
  return defaultPricing
}

export interface TokenCounts {
  input_tokens?: number
  output_tokens?: number
  cache_read_tokens?: number
  cache_create_tokens?: number
}

/** Estimate cost in USD from token counts and model name. */
export function estimateCost(tokens: TokenCounts, model?: string): number {
  const p = resolve(model)
  const inp = (tokens.input_tokens ?? 0) / 1_000_000 * p.input
  const out = (tokens.output_tokens ?? 0) / 1_000_000 * p.output
  const cacheRead = (tokens.cache_read_tokens ?? 0) / 1_000_000 * p.cacheRead
  const cacheWrite = (tokens.cache_create_tokens ?? 0) / 1_000_000 * p.cacheWrite
  return inp + out + cacheRead + cacheWrite
}

/** Format USD cost as string. */
export function formatCost(usd: number): string {
  if (usd < 0.01) return '<$0.01'
  if (usd < 1) return `$${usd.toFixed(2)}`
  return `$${usd.toFixed(2)}`
}
