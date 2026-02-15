import { useState } from 'react'
import { Tag, SkipForward, RefreshCw, Trash2 } from 'lucide-react'
import type { AlbumDetail, MatchCandidateResponse } from '@/types'
import { ConfidenceIndicator, ConfirmDialog } from '@/components/common'
import { useAlbumStore } from '@/store/useAlbumStore'
import { useNotificationStore } from '@/store/useNotificationStore'
import { cn } from '@/utils'

interface Props {
  album: AlbumDetail
}

export function MatchReviewPanel({ album }: Props) {
  const { tagAlbum, retagAlbum, skipAlbum, deleteAlbum, fetchAlbum } = useAlbumStore()
  const addToast = useNotificationStore((s) => s.addToast)
  const [selectedCandidate, setSelectedCandidate] = useState<string | null>(
    album.match_candidates.find((c) => c.is_selected)?.musicbrainz_release_id || null
  )
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)

  const handleAction = async (action: () => Promise<void>, successMsg: string) => {
    setBusy(true)
    try {
      await action()
      addToast('success', successMsg)
      fetchAlbum(album.id)
    } catch {
      addToast('error', 'Action failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Error banner */}
      {album.error_message && (
        <div className="bg-accent-red/10 border border-accent-red/30 rounded-lg p-3 text-sm text-accent-red">
          {album.error_message}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => handleAction(() => tagAlbum(album.id, selectedCandidate || undefined), 'Tagging queued')}
          disabled={busy}
          className="flex items-center gap-2 px-4 py-2 bg-accent-green text-surface-300 rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          <Tag className="h-4 w-4" />
          Tag{selectedCandidate ? ' with Selected' : ''}
        </button>
        <button
          onClick={() => handleAction(() => skipAlbum(album.id), 'Album skipped')}
          disabled={busy}
          className="flex items-center gap-2 px-4 py-2 bg-surface-400 text-text rounded-lg text-sm font-medium hover:bg-surface-500 disabled:opacity-50 transition-colors"
        >
          <SkipForward className="h-4 w-4" />
          Skip
        </button>
        <button
          onClick={() => handleAction(() => retagAlbum(album.id), 'Re-match queued')}
          disabled={busy}
          className="flex items-center gap-2 px-4 py-2 bg-accent-blue/15 text-accent-blue rounded-lg text-sm font-medium hover:bg-accent-blue/25 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Re-match
        </button>
        <button
          onClick={() => setConfirmDelete(true)}
          disabled={busy}
          className="flex items-center gap-2 px-4 py-2 bg-accent-red/15 text-accent-red rounded-lg text-sm font-medium hover:bg-accent-red/25 disabled:opacity-50 transition-colors"
        >
          <Trash2 className="h-4 w-4" />
          Remove
        </button>
      </div>

      {/* Match candidates */}
      {album.match_candidates.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-text-muted mb-2">Match Candidates</h3>
          <div className="space-y-2">
            {album.match_candidates
              .sort((a, b) => b.confidence - a.confidence)
              .map((candidate) => (
                <CandidateRow
                  key={candidate.id}
                  candidate={candidate}
                  selected={selectedCandidate === candidate.musicbrainz_release_id}
                  onSelect={() => setSelectedCandidate(candidate.musicbrainz_release_id)}
                  currentAlbum={album}
                />
              ))}
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete}
        title="Remove Album"
        message="This will remove the album from the database. Audio files will NOT be deleted."
        confirmLabel="Remove"
        onConfirm={() => {
          setConfirmDelete(false)
          handleAction(() => deleteAlbum(album.id), 'Album removed')
        }}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  )
}

function CandidateRow({
  candidate,
  selected,
  onSelect,
  currentAlbum,
}: {
  candidate: MatchCandidateResponse
  selected: boolean
  onSelect: () => void
  currentAlbum: AlbumDetail
}) {
  const artistChanged = candidate.artist && candidate.artist !== currentAlbum.artist
  const albumChanged = candidate.album && candidate.album !== currentAlbum.album
  const yearChanged = candidate.year && candidate.year !== currentAlbum.year

  return (
    <button
      onClick={onSelect}
      className={cn(
        'w-full text-left rounded-lg border p-3 transition-colors',
        selected
          ? 'border-accent-blue bg-accent-blue/5'
          : 'border-surface-400 hover:border-surface-500 bg-surface-200'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-text truncate">
              {candidate.album || 'Unknown'}
            </p>
            {albumChanged && (
              <span className="text-[10px] px-1 py-0.5 rounded bg-accent-yellow/15 text-accent-yellow shrink-0">
                changed
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-xs text-text-muted truncate">
              {candidate.artist || 'Unknown'}
              {candidate.year ? ` (${candidate.year})` : ''}
            </p>
            {artistChanged && (
              <span className="text-[10px] px-1 py-0.5 rounded bg-accent-yellow/15 text-accent-yellow shrink-0">
                changed
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-1.5 text-xs text-text-subtle">
            {candidate.track_count != null && <span>{candidate.track_count} tracks</span>}
            {candidate.country && <span>{candidate.country}</span>}
            {candidate.media && <span>{candidate.media}</span>}
            {candidate.label && <span>{candidate.label}</span>}
          </div>
        </div>
        <ConfidenceIndicator confidence={candidate.confidence} />
      </div>
    </button>
  )
}
