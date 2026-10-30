/**
 * The Now card's translation layer (fleet-now-card 7.9).
 *
 * The compile-time guard (`Record<MsgKey, Msg>`) is the first line; this is the second, at
 * run time, so a dictionary that drifts is a red test and not a key printed on the card.
 */
import { describe, expect, it } from 'vitest'
import { DICTIONARIES, asLocale, makeT, t } from '../../src/lib/nowI18n'
import type { MsgKey } from '../../src/lib/nowI18n'
import { checkView, emptyMessage, gapMarkers, goalsNotes, hoursAgo, laterChoices } from '../../src/lib/nowCard'
import type { GoalsPayload, NowPayload } from '../../src/lib/nowCard'

describe('the dictionaries', () => {
  it('hu has every en key and no other', () => {
    const en = Object.keys(DICTIONARIES.en).sort()
    const hu = Object.keys(DICTIONARIES.hu).sort()
    expect(hu.filter(k => !en.includes(k))).toEqual([])
    expect(en.filter(k => !hu.includes(k))).toEqual([])
    expect(en.length).toBeGreaterThan(150)
  })

  it('no hu entry is empty, and every placeholder in en is kept in hu', () => {
    const holes = (m: unknown) => {
      const texts = typeof m === 'string' ? [m] : Object.values(m as Record<string, string>)
      return new Set(texts.flatMap(x => x.match(/\{\w+\}/g) ?? []))
    }
    for (const key of Object.keys(DICTIONARIES.en) as MsgKey[]) {
      const hu = DICTIONARIES.hu[key]
      expect(typeof hu === 'string' ? hu.trim() : hu, key).toBeTruthy()
      expect([...holes(hu)].sort(), key).toEqual([...holes(DICTIONARIES.en[key])].sort())
    }
  })
})

describe('t', () => {
  it('interpolates {name}, and leaves a missing placeholder visible', () => {
    expect(t('en', 'card.resume', { note: 'step 2' })).toBe('Resume: step 2')
    expect(t('hu', 'card.resume', { note: 'step 2' })).toBe('Folytatás: step 2')
    expect(t('en', 'card.resume')).toBe('Resume: {note}')
  })

  it('English chooses one/other by n; Hungarian keeps the noun singular after a number', () => {
    expect(t('en', 'goals.count', { n: 1 })).toBe('1 goal')
    expect(t('en', 'goals.count', { n: 3 })).toBe('3 goals')
    expect(t('en', 'goals.count', { n: 0 })).toBe('0 goals')
    expect(t('hu', 'goals.count', { n: 1 })).toBe('1 cél')
    expect(t('hu', 'goals.count', { n: 3 })).toBe('3 cél')
    expect(t('hu', 'goals.openCards', { n: 2 })).toBe('2 nyitott kártya')
    expect(t('hu', 'card.more', { n: 4 })).toBe('még 4')
  })

  it('an unknown locale reads as English; makeT binds one', () => {
    expect(asLocale('hu')).toBe('hu')
    expect(asLocale('de')).toBe('en')
    expect(asLocale(undefined)).toBe('en')
    expect(makeT('hu')('card.done')).toBe('Kész')
    expect(makeT('en')('card.done')).toBe('Done')
  })
})

describe('the helpers follow the locale and leave the publisher\'s text alone', () => {
  const base = {
    sources: [{ name: 'owner-queue', measured: false, reason: 'publisher said: timeout', count: null }],
    publisher: { state: 'ok', project: 'pub', candidates: [], reason: null, acceptsActions: true },
    unreadSources: [], partial: true, stale: true, rankingAgeSeconds: 2 * 3600, malformed: 0,
    cue: { play: false, reason: null, variant: null, slowed: false, intervalSeconds: 600 },
    unmeasured: 1, mutedHidden: 0,
  } as unknown as NowPayload

  it('gap markers and the empty state', () => {
    expect(gapMarkers(base).map(m => m.text)).toEqual([
      '1 source could not be read: owner-queue — publisher said: timeout', 'Queue is partial', 'ranked 2 h ago'])
    expect(gapMarkers(base, 'hu').map(m => m.text)).toEqual([
      '1 forrás nem olvasható: owner-queue — publisher said: timeout', 'A sor hiányos', 'rangsorolva 2 órája'])
    expect(emptyMessage(base, 'hu')).toBe('Nincs mit mutatni — de 1 forrás nem olvasható.')
    expect(hoursAgo(600, 'hu')).toBe('10 perce')
  })

  it('later choices, checks and goal notes', () => {
    expect(laterChoices(new Date(), 'hu').map(c => c.label)).toEqual(['15 perc', '1 óra', '2 óra', '4 óra', 'Holnap'])
    const v = checkView({ state: 'stale', evidence: 'sent on 10-29' }, new Date(), 'hu')!
    expect(v.label).toBe('Már nem aktuális — ellenőrizve')
    expect(v.evidence).toBe('sent on 10-29')
    const g = { partial: false, unreadSources: [], stale: false, ageSeconds: null, malformedGoals: 2, malformedAdvice: 1 } as unknown as GoalsPayload
    expect(goalsNotes(g, 'hu')).toEqual(['2 cél és 1 javaslat olvashatatlan, kihagyva'])
  })
})
