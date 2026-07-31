import { useRef, useEffect, useState } from 'react'

interface Props {
  lines: string[]
}

function lineColor(line: string): string {
  if (line.includes('ERROR')) return 'text-red-400'
  if (line.includes('WARN')) return 'text-yellow-400'
  if (line.includes('REPLAN')) return 'text-cyan-400'
  if (line.includes('CHECKPOINT')) return 'text-yellow-300'
  return 'text-fg-muted'
}

export default function LogStream({ lines }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [lines, autoScroll])

  const handleScroll = () => {
    if (!containerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50)
  }

  return (
    <div className="relative h-full flex flex-col">
      <div className="flex items-center justify-between px-3 py-1 border-b border-surface-line bg-surface-panel/50">
        <span className="text-sm text-fg-faint font-medium">Log</span>
        <span className="text-sm text-fg-ghost">{lines.length} lines</span>
      </div>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-auto p-2 text-sm leading-5"
      >
        {lines.map((line, i) => (
          <div key={i} className={lineColor(line)}>
            {line}
          </div>
        ))}
      </div>
      {!autoScroll && (
        <button
          onClick={() => {
            setAutoScroll(true)
            if (containerRef.current) {
              containerRef.current.scrollTop = containerRef.current.scrollHeight
            }
          }}
          className="absolute bottom-3 right-3 px-2 py-1 text-sm bg-surface-raised text-fg-normal rounded hover:bg-surface-strong"
        >
          Jump to bottom
        </button>
      )}
    </div>
  )
}
