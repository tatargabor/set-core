import type { ChangeInfo } from './api'
import type { ChangeTransition } from './battleTransitions'

// --- Achievement Definitions ---

export type Rarity = 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary'

export interface AchievementDef {
  id: string
  name: string
  emoji: string
  description: string
  rarity: Rarity
  bonus: number
}

export const ACHIEVEMENTS: AchievementDef[] = [
  { id: 'first_blood', name: 'First Blood', emoji: '\u{1FA78}', description: 'First change completed', rarity: 'common', bonus: 100 },
  { id: 'speed_demon', name: 'Speed Demon', emoji: '\u26A1', description: 'Change completed in <5 minutes', rarity: 'rare', bonus: 500 },
  { id: 'flawless', name: 'Flawless', emoji: '\u{1F3AF}', description: 'Change with 0 failures', rarity: 'uncommon', bonus: 300 },
  { id: 'marathon', name: 'Marathon Man', emoji: '\u{1F3C3}', description: 'Orchestration running >2 hours', rarity: 'common', bonus: 100 },
  { id: 'token_miser', name: 'Token Miser', emoji: '\u{1F4B0}', description: 'Change completed with <50k tokens', rarity: 'rare', bonus: 500 },
  { id: 'token_whale', name: 'Token Whale', emoji: '\u{1F433}', description: 'Total tokens exceed 10M', rarity: 'uncommon', bonus: 200 },
  { id: 'on_fire', name: 'On Fire', emoji: '\u{1F525}', description: '3 consecutive first-try completions', rarity: 'rare', bonus: 500 },
  { id: 'rage_quit', name: 'Rage Quit', emoji: '\u{1F480}', description: 'User manually stops orchestration', rarity: 'legendary', bonus: 0 },
  { id: 'clean_sweep', name: 'Clean Sweep', emoji: '\u{1F9F9}', description: 'All changes done with 0 failures', rarity: 'epic', bonus: 1000 },
  { id: 'perfect_run', name: 'Perfect Run', emoji: '\u{1F451}', description: 'Clean Sweep + Token Miser on all', rarity: 'legendary', bonus: 2000 },
  { id: 'bug_squasher', name: 'Bug Squasher', emoji: '\u{1F41B}', description: '5+ failed changes recovered', rarity: 'uncommon', bonus: 300 },
  { id: 'phase_complete', name: 'Phase Complete', emoji: '\u{1F4E6}', description: 'All changes in a phase completed', rarity: 'common', bonus: 200 },
  { id: 'parallel_power', name: 'Parallel Power', emoji: '\u{1F30A}', description: '3+ changes running simultaneously', rarity: 'uncommon', bonus: 300 },
  { id: 'coffee_break', name: 'Coffee Break', emoji: '\u2615', description: '15+ minutes idle on dashboard', rarity: 'common', bonus: 50 },
  { id: 'comeback_kid', name: 'Comeback Kid', emoji: '\u{1F4AA}', description: 'Change failed 2+ times then completed', rarity: 'rare', bonus: 500 },
]

// --- Score State ---

export interface ScoreState {
  score: number
  highScore: number
  lives: number
  multiplier: number
  achievements: string[]
  failureCount: number
  consecutiveFirstTry: number
  totalTokens: number
  completedChanges: number
  recoveredChanges: number
  changeFailCounts: Record<string, number>
}

export function createScoreState(): ScoreState {
  return {
    score: 0,
    highScore: 0,
    lives: 3,
    multiplier: 1,
    achievements: [],
    failureCount: 0,
    consecutiveFirstTry: 0,
    totalTokens: 0,
    completedChanges: 0,
    recoveredChanges: 0,
    changeFailCounts: {},
  }
}

export interface ScoreEvent {
  points: number
  reason: string
  achievement?: AchievementDef
}

// --- Score Engine ---

export function processTransition(
  state: ScoreState,
  transition: ChangeTransition,
  allChanges: ChangeInfo[],
): ScoreEvent[] {
  const events: ScoreEvent[] = []
  const { name, to, change } = transition

  // Calculate multiplier
  const runningCount = allChanges.filter(c =>
    ['running', 'implementing', 'verifying'].includes(c.status)
  ).length
  state.multiplier = runningCount >= 3 ? 3 : runningCount >= 2 ? 2 : 1

  // Completion
  if (['done', 'merged', 'completed'].includes(to)) {
    const fails = state.changeFailCounts[name] ?? 0
    let base = fails === 0 ? 1000 : fails === 1 ? 500 : 250
    base *= state.multiplier
    events.push({ points: base, reason: `${name} landed${fails > 0 ? ` (${fails} retries)` : ' first try!'}` })
    state.score += base
    state.completedChanges++

    // Verify bonus
    if (change.test_result === 'pass') {
      const bonus = 100 * state.multiplier
      events.push({ points: bonus, reason: 'Test gate passed' })
      state.score += bonus
    }
    if (change.build_result === 'pass') {
      const bonus = 100 * state.multiplier
      events.push({ points: bonus, reason: 'Build gate passed' })
      state.score += bonus
    }
    if (change.review_result === 'pass') {
      const bonus = 100 * state.multiplier
      events.push({ points: bonus, reason: 'Review gate passed' })
      state.score += bonus
    }

    // Token efficiency
    const totalTok = (change.input_tokens ?? 0) + (change.output_tokens ?? 0)
    if (totalTok > 0 && totalTok < 50000) {
      const bonus = 500 * state.multiplier
      events.push({ points: bonus, reason: 'Token Miser bonus (<50k)' })
      state.score += bonus
    } else if (totalTok > 0 && totalTok < 100000) {
      const bonus = 200 * state.multiplier
      events.push({ points: bonus, reason: 'Token efficient (<100k)' })
      state.score += bonus
    }

    // Duration bonus
    if (change.started_at) {
      const elapsed = (Date.now() - new Date(change.started_at).getTime()) / 1000
      if (elapsed < 300) {
        const bonus = 300 * state.multiplier
        events.push({ points: bonus, reason: 'Speed Demon (<5min)' })
        state.score += bonus
      }
    }

    // Consecutive first try
    if (fails === 0) {
      state.consecutiveFirstTry++
    } else {
      state.consecutiveFirstTry = 0
      if (fails >= 2) state.recoveredChanges++
    }
  }

  // Failure
  if (['failed', 'verify-failed'].includes(to)) {
    state.changeFailCounts[name] = (state.changeFailCounts[name] ?? 0) + 1
    state.failureCount++
    events.push({ points: -200, reason: `${name} exploded!` })
    state.score -= 200

    // Lives
    if (state.failureCount % 3 === 0) {
      state.lives = Math.max(0, state.lives - 1)
    }
  }

  // Update total tokens
  state.totalTokens = allChanges.reduce((sum, c) => sum + (c.input_tokens ?? 0) + (c.output_tokens ?? 0), 0)

  // High score
  if (state.score > state.highScore) {
    state.highScore = state.score
  }

  // Check achievements
  const newAchievements = checkAchievements(state, transition, allChanges)
  for (const a of newAchievements) {
    state.achievements.push(a.id)
    state.score += a.bonus
    events.push({ points: a.bonus, reason: `Achievement: ${a.name}`, achievement: a })
  }

  return events
}

function checkAchievements(
  state: ScoreState,
  transition: ChangeTransition,
  allChanges: ChangeInfo[],
): AchievementDef[] {
  const unlocked: AchievementDef[] = []
  const has = (id: string) => state.achievements.includes(id)
  const { to, change } = transition

  if (!has('first_blood') && state.completedChanges >= 1) {
    unlocked.push(ACHIEVEMENTS.find(a => a.id === 'first_blood')!)
  }

  if (!has('speed_demon') && ['done', 'merged', 'completed'].includes(to) && change.started_at) {
    const elapsed = (Date.now() - new Date(change.started_at).getTime()) / 1000
    if (elapsed < 300) unlocked.push(ACHIEVEMENTS.find(a => a.id === 'speed_demon')!)
  }

  if (!has('flawless') && ['done', 'merged', 'completed'].includes(to) && (state.changeFailCounts[transition.name] ?? 0) === 0) {
    unlocked.push(ACHIEVEMENTS.find(a => a.id === 'flawless')!)
  }

  if (!has('token_miser') && ['done', 'merged', 'completed'].includes(to)) {
    const tok = (change.input_tokens ?? 0) + (change.output_tokens ?? 0)
    if (tok > 0 && tok < 50000) unlocked.push(ACHIEVEMENTS.find(a => a.id === 'token_miser')!)
  }

  if (!has('token_whale') && state.totalTokens >= 10_000_000) {
    unlocked.push(ACHIEVEMENTS.find(a => a.id === 'token_whale')!)
  }

  if (!has('on_fire') && state.consecutiveFirstTry >= 3) {
    unlocked.push(ACHIEVEMENTS.find(a => a.id === 'on_fire')!)
  }

  if (!has('bug_squasher') && state.recoveredChanges >= 5) {
    unlocked.push(ACHIEVEMENTS.find(a => a.id === 'bug_squasher')!)
  }

  if (!has('parallel_power')) {
    const running = allChanges.filter(c => ['running', 'implementing', 'verifying'].includes(c.status)).length
    if (running >= 3) unlocked.push(ACHIEVEMENTS.find(a => a.id === 'parallel_power')!)
  }

  if (!has('comeback_kid') && ['done', 'merged', 'completed'].includes(to) && (state.changeFailCounts[transition.name] ?? 0) >= 2) {
    unlocked.push(ACHIEVEMENTS.find(a => a.id === 'comeback_kid')!)
  }

  // Clean sweep: all changes done, 0 total failures
  if (!has('clean_sweep') && allChanges.length > 0) {
    const allDone = allChanges.every(c => ['done', 'merged', 'completed', 'skip_merged', 'skipped'].includes(c.status))
    if (allDone && state.failureCount === 0) {
      unlocked.push(ACHIEVEMENTS.find(a => a.id === 'clean_sweep')!)
    }
  }

  return unlocked
}

// --- Persistence ---

export function saveScore(project: string, state: ScoreState) {
  try {
    localStorage.setItem(`set-battle-score-${project}`, JSON.stringify({
      highScore: state.highScore,
      achievements: state.achievements,
    }))
  } catch { /* quota exceeded */ }
}

export function loadScore(project: string): { highScore: number; achievements: string[] } {
  try {
    const raw = localStorage.getItem(`set-battle-score-${project}`)
    if (raw) {
      const data = JSON.parse(raw)
      return { highScore: data.highScore ?? 0, achievements: data.achievements ?? [] }
    }
  } catch { /* parse error */ }
  return { highScore: 0, achievements: [] }
}
