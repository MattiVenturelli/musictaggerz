import { useState, useEffect } from 'react'
import { History, RotateCcw, Trash2 } from 'lucide-react'
import type { TagBackupResponse } from '@/types'
import { fetchBackups, restoreBackup, deleteBackup } from '@/services/api'
import { useAlbumStore } from '@/store/useAlbumStore'
import { useNotificationStore } from '@/store/useNotificationStore'
import { ConfirmDialog, LoadingSpinner } from '@/components/common'
import { formatRelativeTime } from '@/utils'

const ACTION_LABELS: Record<string, string> = {
  musicbrainz_tag: 'MusicBrainz Tag',
  manual_edit: 'Manual Edit',
  artwork: 'Artwork',
  lyrics: 'Lyrics',
  replaygain: 'ReplayGain',
  pre_restore: 'Pre-Restore',
}

export function BackupPanel({ albumId }: { albumId: number }) {
  const [backups, setBackups] = useState<TagBackupResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [restoreTarget, setRestoreTarget] = useState<number | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  const [acting, setActing] = useState(false)
  const fetchAlbum = useAlbumStore((s) => s.fetchAlbum)
  const addToast = useNotificationStore((s) => s.addToast)

  const load = async () => {
    setLoading(true)
    try {
      const data = await fetchBackups(albumId)
      setBackups(data)
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (expanded) load()
  }, [expanded, albumId])

  const handleRestore = async () => {
    if (!restoreTarget) return
    setActing(true)
    try {
      await restoreBackup(albumId, restoreTarget)
      addToast('success', 'Backup restored successfully')
      fetchAlbum(albumId)
      load()
    } catch {
      addToast('error', 'Failed to restore backup')
    } finally {
      setActing(false)
      setRestoreTarget(null)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setActing(true)
    try {
      await deleteBackup(albumId, deleteTarget)
      setBackups((b) => b.filter((x) => x.id !== deleteTarget))
      addToast('success', 'Backup deleted')
    } catch {
      addToast('error', 'Failed to delete backup')
    } finally {
      setActing(false)
      setDeleteTarget(null)
    }
  }

  return (
    <>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm text-text-muted hover:text-text transition-colors w-full text-left"
      >
        <History className="h-4 w-4" />
        <span>Tag Backups</span>
        {!expanded && backups.length > 0 && (
          <span className="text-xs text-text-subtle">({backups.length})</span>
        )}
      </button>

      {expanded && (
        <div className="mt-3 space-y-2">
          {loading ? (
            <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
          ) : backups.length === 0 ? (
            <p className="text-xs text-text-subtle py-2">No backups available</p>
          ) : (
            backups.map((b) => (
              <div
                key={b.id}
                className="flex items-center justify-between px-3 py-2 bg-surface-200 rounded-lg border border-surface-400"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-text">
                    {ACTION_LABELS[b.action] || b.action}
                  </p>
                  <p className="text-xs text-text-subtle">
                    {b.track_count} tracks · {formatRelativeTime(b.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => setRestoreTarget(b.id)}
                    disabled={acting}
                    className="p-1.5 text-text-muted hover:text-accent-blue transition-colors"
                    title="Restore"
                  >
                    <RotateCcw className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => setDeleteTarget(b.id)}
                    disabled={acting}
                    className="p-1.5 text-text-muted hover:text-accent-red transition-colors"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      <ConfirmDialog
        open={restoreTarget !== null}
        title="Restore Backup"
        message="This will overwrite the current tags with the backup state. A safety backup of the current state will be created first."
        confirmLabel="Restore"
        onConfirm={handleRestore}
        onCancel={() => setRestoreTarget(null)}
      />
      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete Backup"
        message="This backup will be permanently deleted."
        confirmLabel="Delete"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </>
  )
}
