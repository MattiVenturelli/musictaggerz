import type { StatsResponse } from '@/types'
import { cn } from '@/utils'

interface Props {
  stats: StatsResponse
}

const segments = [
  { key: 'tagged_count', label: 'Tagged', color: 'bg-accent-green' },
  { key: 'matching_count', label: 'Matching', color: 'bg-accent-blue' },
  { key: 'needs_review_count', label: 'Review', color: 'bg-accent-peach' },
  { key: 'pending_count', label: 'Pending', color: 'bg-accent-yellow' },
  { key: 'failed_count', label: 'Failed', color: 'bg-accent-red' },
  { key: 'skipped_count', label: 'Skipped', color: 'bg-surface-600' },
] as const

export function ProgressBar({ stats }: Props) {
  const total = stats.total_albums || 1

  return (
    <div className="bg-surface-100 rounded-xl p-5 border border-surface-400">
      <h3 className="text-sm font-medium text-text-muted mb-3">Album Status Breakdown</h3>
      <div className="h-4 rounded-full bg-surface-400 overflow-hidden flex">
        {segments.map(({ key, color }) => {
          const count = stats[key]
          if (count === 0) return null
          return (
            <div
              key={key}
              className={cn('h-full transition-all duration-500', color)}
              style={{ width: `${(count / total) * 100}%` }}
            />
          )
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
        {segments.map(({ key, label, color }) => (
          <div key={key} className="flex items-center gap-1.5 text-xs text-text-muted">
            <div className={cn('h-2.5 w-2.5 rounded-full', color)} />
            {label}: {stats[key]}
          </div>
        ))}
      </div>
    </div>
  )
}
