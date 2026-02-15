import { useEffect } from 'react'
import { Disc3, Tag, AlertTriangle, Eye, FolderSearch, Play } from 'lucide-react'
import { useStatsStore } from '@/store/useStatsStore'
import { useAlbumStore } from '@/store/useAlbumStore'
import { useNotificationStore } from '@/store/useNotificationStore'
import { LoadingSpinner } from '@/components/common'
import { StatCard } from './StatCard'
import { ProgressBar } from './ProgressBar'
import { ActivityFeed } from './ActivityFeed'

export function DashboardPage() {
  const { stats, loading, fetchStats } = useStatsStore()
  const triggerScan = useAlbumStore((s) => s.triggerScan)
  const batchTagPending = useAlbumStore((s) => s.batchTagPending)
  const addToast = useNotificationStore((s) => s.addToast)

  useEffect(() => {
    fetchStats()
  }, [fetchStats])

  const handleScan = async () => {
    try {
      await triggerScan()
      addToast('info', 'Scan started...')
    } catch {
      addToast('error', 'Failed to start scan')
    }
  }

  const handleTagAllPending = async () => {
    try {
      await batchTagPending()
      addToast('info', 'Queued all pending albums for tagging')
      fetchStats()
    } catch {
      addToast('error', 'Failed to queue pending albums')
    }
  }

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const s = stats || {
    total_albums: 0,
    tagged_count: 0,
    pending_count: 0,
    matching_count: 0,
    needs_review_count: 0,
    failed_count: 0,
    skipped_count: 0,
    queue_size: 0,
    is_processing: false,
    recent_activity: [],
  }

  return (
    <div className="max-w-6xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text">Dashboard</h1>
        <div className="flex items-center gap-2">
          {(s.pending_count + s.needs_review_count) > 0 && (
            <button
              onClick={handleTagAllPending}
              className="flex items-center gap-2 px-4 py-2 bg-accent-green text-surface-300 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
            >
              <Play className="h-4 w-4" />
              Tag All ({s.pending_count + s.needs_review_count})
            </button>
          )}
          <button
            onClick={handleScan}
            className="flex items-center gap-2 px-4 py-2 bg-accent-blue text-surface-300 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
          >
            <FolderSearch className="h-4 w-4" />
            Scan Now
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Disc3} title="Total Albums" value={s.total_albums} color="text-accent-lavender" href="/albums" />
        <StatCard icon={Tag} title="Tagged" value={s.tagged_count} color="text-accent-green" href="/albums?status=tagged" />
        <StatCard icon={Eye} title="Needs Review" value={s.needs_review_count} color="text-accent-peach" href="/albums?status=needs_review" />
        <StatCard icon={AlertTriangle} title="Failed" value={s.failed_count} color="text-accent-red" href="/albums?status=failed" />
      </div>

      <ProgressBar stats={s} />

      <div className="bg-surface-100 rounded-xl border border-surface-400">
        <div className="px-5 py-4 border-b border-surface-400">
          <h3 className="text-sm font-medium text-text-muted">Recent Activity</h3>
        </div>
        <div className="p-2 max-h-96 overflow-y-auto">
          <ActivityFeed activities={s.recent_activity} />
        </div>
      </div>

      {s.is_processing && (
        <div className="flex items-center gap-2 text-sm text-accent-blue">
          <LoadingSpinner size="sm" />
          Processing queue ({s.queue_size} remaining)
        </div>
      )}
    </div>
  )
}
