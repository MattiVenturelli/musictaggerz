import { Tag, Search, SkipForward, AlertCircle, FolderSearch, Disc3 } from 'lucide-react'
import type { ActivityLogResponse } from '@/types'
import { formatRelativeTime, cn } from '@/utils'

interface Props {
  activities: ActivityLogResponse[]
}

const actionConfig: Record<string, { icon: typeof Tag; color: string }> = {
  tagged: { icon: Tag, color: 'text-accent-green' },
  matched: { icon: Search, color: 'text-accent-blue' },
  skipped: { icon: SkipForward, color: 'text-text-subtle' },
  failed: { icon: AlertCircle, color: 'text-accent-red' },
  scanned: { icon: FolderSearch, color: 'text-accent-teal' },
  retag_requested: { icon: Disc3, color: 'text-accent-mauve' },
}

const defaultConfig = { icon: Disc3, color: 'text-text-subtle' }

export function ActivityFeed({ activities }: Props) {
  if (activities.length === 0) {
    return (
      <div className="text-center py-8 text-text-subtle text-sm">
        No recent activity
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {activities.map((activity) => {
        const config = actionConfig[activity.action] || defaultConfig
        const Icon = config.icon
        return (
          <div
            key={activity.id}
            className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-surface-400/30 transition-colors"
          >
            <Icon className={cn('h-4 w-4 shrink-0', config.color)} />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-text truncate">
                <span className="font-medium capitalize">{activity.action.replace('_', ' ')}</span>
                {activity.details && (
                  <span className="text-text-muted"> - {activity.details}</span>
                )}
              </p>
            </div>
            <span className="text-xs text-text-subtle shrink-0">
              {formatRelativeTime(activity.timestamp)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
