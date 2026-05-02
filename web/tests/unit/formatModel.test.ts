import { describe, it, expect } from 'vitest'
import { displayModel, modelFamily } from '../../src/lib/formatModel'

describe('displayModel', () => {
  it('strips claude- prefix from full IDs', () => {
    expect(displayModel('claude-opus-4-7')).toBe('opus-4-7')
    expect(displayModel('claude-opus-4-6')).toBe('opus-4-6')
    expect(displayModel('claude-sonnet-4-6')).toBe('sonnet-4-6')
  })

  it('drops the haiku date suffix', () => {
    expect(displayModel('claude-haiku-4-5-20251001')).toBe('haiku-4-5')
  })

  it('converts [1m] suffix to -1m', () => {
    expect(displayModel('claude-opus-4-7[1m]')).toBe('opus-4-7-1m')
    expect(displayModel('claude-opus-4-6[1m]')).toBe('opus-4-6-1m')
    expect(displayModel('claude-sonnet-4-6[1m]')).toBe('sonnet-4-6-1m')
  })

  it('passes through short alias names unchanged', () => {
    expect(displayModel('opus')).toBe('opus')
    expect(displayModel('sonnet')).toBe('sonnet')
    expect(displayModel('haiku')).toBe('haiku')
  })

  it('passes through explicit short pins unchanged', () => {
    expect(displayModel('opus-4-6')).toBe('opus-4-6')
    expect(displayModel('opus-4-7')).toBe('opus-4-7')
    expect(displayModel('opus-4-6-1m')).toBe('opus-4-6-1m')
  })

  it('handles empty / undefined gracefully', () => {
    expect(displayModel(undefined)).toBe('')
    expect(displayModel('')).toBe('')
  })
})

describe('modelFamily', () => {
  it('returns family-only for full IDs', () => {
    expect(modelFamily('claude-opus-4-7')).toBe('opus')
    expect(modelFamily('claude-sonnet-4-6')).toBe('sonnet')
    expect(modelFamily('claude-haiku-4-5-20251001')).toBe('haiku')
  })

  it('handles short pins', () => {
    expect(modelFamily('opus-4-6')).toBe('opus')
    expect(modelFamily('sonnet-4-6')).toBe('sonnet')
  })

  it('handles 1M variants', () => {
    expect(modelFamily('claude-opus-4-7[1m]')).toBe('opus')
  })

  it('returns the input unchanged for unknown families', () => {
    expect(modelFamily('gpt-4')).toBe('gpt-4')
  })

  it('handles empty / undefined gracefully', () => {
    expect(modelFamily(undefined)).toBe('')
    expect(modelFamily('')).toBe('')
  })
})
