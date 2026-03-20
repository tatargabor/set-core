import { useState, useRef, useEffect } from 'react'
import type { ScoreState } from '../../lib/battleScoring'
import Scoreboard from './Scoreboard'

interface Props {
  state: ScoreState
  onSubmitScore?: () => void
  submitStatus?: 'idle' | 'submitting' | 'done' | 'error'
  submitRank?: number | null
}

export default function BattleHeader({ state, onSubmitScore, submitStatus = 'idle', submitRank }: Props) {
  const hearts = Array.from({ length: 3 }, (_, i) => i < state.lives)
  const isNewHigh = state.score > 0 && state.score >= state.highScore
  const [showBoard, setShowBoard] = useState(false)
  const dropRef = useRef<HTMLDivElement>(null)

  // Close on click outside
  useEffect(() => {
    if (!showBoard) return
    const onClick = (e: MouseEvent) => {
      if (dropRef.current && !dropRef.current.contains(e.target as Node)) {
        setShowBoard(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [showBoard])

  return (
    <div className="flex items-center gap-4 px-4 py-2 border-b border-neutral-800 bg-neutral-900/80 shrink-0 relative">
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-neutral-500 uppercase tracking-wider">Score</span>
        <span className="text-sm font-mono font-bold text-neutral-100">{state.score.toLocaleString()}</span>
        {isNewHigh && (
          <span className="text-[9px] font-bold text-yellow-400 animate-pulse">NEW HIGH!</span>
        )}
      </div>

      <div className="flex items-center gap-1">
        <span className="text-[10px] text-neutral-500 uppercase tracking-wider">Hi</span>
        <span className="text-xs font-mono text-neutral-400">{state.highScore.toLocaleString()}</span>
      </div>

      {/* Scoreboard toggle */}
      <button
        onClick={() => setShowBoard(v => !v)}
        className={`text-sm px-1.5 py-0.5 rounded transition-colors ${
          showBoard ? 'bg-yellow-900/50 text-yellow-300' : 'text-neutral-500 hover:text-yellow-400 hover:bg-neutral-800'
        }`}
        title="Scoreboard"
      >
        {'\u{1F3C6}'}
      </button>

      {state.multiplier > 1 && (
        <span className="text-xs font-bold text-cyan-400">x{state.multiplier}</span>
      )}

      {/* Submit score button */}
      {onSubmitScore && state.score > 0 && (
        <button
          onClick={onSubmitScore}
          disabled={submitStatus === 'submitting'}
          className={`text-[10px] px-2 py-0.5 rounded font-medium transition-colors ${
            submitStatus === 'done'
              ? 'bg-green-900/50 text-green-300'
              : submitStatus === 'error'
              ? 'bg-red-900/50 text-red-300 hover:bg-red-900'
              : submitStatus === 'submitting'
              ? 'bg-neutral-800 text-neutral-500'
              : 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700'
          }`}
        >
          {submitStatus === 'done'
            ? `Rank #${submitRank ?? '?'}`
            : submitStatus === 'submitting'
            ? 'Sending...'
            : submitStatus === 'error'
            ? 'Retry'
            : 'Submit'}
        </button>
      )}

      <div className="flex gap-0.5 ml-auto">
        {hearts.map((alive, i) => (
          <span key={i} className={`text-sm ${alive ? 'text-red-500' : 'text-neutral-700'}`}>
            {alive ? '\u2665' : '\u2661'}
          </span>
        ))}
      </div>

      {/* Scoreboard dropdown */}
      {showBoard && (
        <div
          ref={dropRef}
          className="absolute top-full left-0 right-0 z-50 mt-0.5 mx-2 bg-neutral-950 border border-neutral-800 rounded-lg shadow-2xl max-h-80 overflow-y-auto"
        >
          <div className="p-3">
            <Scoreboard />
          </div>
        </div>
      )}
    </div>
  )
}
