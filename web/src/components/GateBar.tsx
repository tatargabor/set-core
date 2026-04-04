interface Props {
  test_result?: string
  smoke_result?: string
  e2e_result?: string
  review_result?: string
  build_result?: string
  spec_coverage_result?: string
  hasScreenshots?: boolean
  onScreenshots?: (e: React.MouseEvent) => void
}

const gateLabels: Record<string, string> = {
  test: 'T',
  build: 'B',
  review: 'R',
  smoke: 'S',
  e2e: 'E',
  spec_coverage: 'SC',
}

const statusStyle: Record<string, string> = {
  pass: 'bg-green-900 text-green-300',
  fail: 'bg-red-900 text-red-300',
  critical: 'bg-red-800 text-red-200',
  redispatch: 'bg-amber-900 text-amber-300',
  skip: 'bg-neutral-800 text-neutral-500',
  skip_merged: 'bg-neutral-800 text-neutral-500',
  pending: 'bg-neutral-800 text-neutral-600',
}

export default function GateBar({ test_result, smoke_result, e2e_result, review_result, build_result, spec_coverage_result, hasScreenshots, onScreenshots }: Props) {
  const gates = [
    { name: 'build', status: build_result },
    { name: 'test', status: test_result },
    { name: 'review', status: review_result },
    { name: 'e2e', status: e2e_result },
    { name: 'smoke', status: smoke_result },
    { name: 'spec_coverage', status: spec_coverage_result ? (spec_coverage_result === 'timeout' ? 'fail' : spec_coverage_result) : undefined },
  ].filter((g) => g.status)

  if (gates.length === 0) {
    return <span className="text-neutral-600 text-sm">—</span>
  }

  return (
    <div className="flex gap-0.5 items-center">
      {gates.map((g) => (
        <span
          key={g.name}
          title={`${g.name}: ${g.status}`}
          className={`w-5 h-5 flex items-center justify-center rounded text-sm font-bold ${statusStyle[g.status!] ?? statusStyle.pending}`}
        >
          {gateLabels[g.name] ?? g.name.charAt(0).toUpperCase()}
        </span>
      ))}
      {hasScreenshots && (
        <button
          onClick={onScreenshots}
          title="View screenshots"
          className="ml-0.5 w-5 h-5 flex items-center justify-center rounded text-sm text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800 transition-colors"
        >
          cam
        </button>
      )}
    </div>
  )
}
