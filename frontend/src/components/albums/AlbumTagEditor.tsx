import { useState } from 'react'
import { Pencil, Save, X } from 'lucide-react'
import type { AlbumDetail } from '@/types'
import { editAlbumTags } from '@/services/api'
import { useAlbumStore } from '@/store/useAlbumStore'
import { useNotificationStore } from '@/store/useNotificationStore'
import { LoadingSpinner } from '@/components/common'

interface Props {
  album: AlbumDetail
}

export function AlbumTagEditor({ album }: Props) {
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [draft, setDraft] = useState({
    album: album.album || '',
    album_artist: album.artist || '',
    year: album.year?.toString() || '',
    genre: '',
    label: '',
  })
  const fetchAlbum = useAlbumStore((s) => s.fetchAlbum)
  const addToast = useNotificationStore((s) => s.addToast)

  const startEditing = () => {
    setDraft({
      album: album.album || '',
      album_artist: album.artist || '',
      year: album.year?.toString() || '',
      genre: '',
      label: '',
    })
    setEditing(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const payload: Record<string, string | number | null> = {}
      if (draft.album && draft.album !== (album.album || '')) payload.album = draft.album
      if (draft.album_artist && draft.album_artist !== (album.artist || '')) payload.album_artist = draft.album_artist
      if (draft.year && draft.year !== (album.year?.toString() || '')) payload.year = parseInt(draft.year)
      if (draft.genre) payload.genre = draft.genre
      if (draft.label) payload.label = draft.label

      if (Object.keys(payload).length === 0) {
        setEditing(false)
        return
      }

      await editAlbumTags(album.id, payload)
      addToast('success', 'Album tags updated')
      fetchAlbum(album.id)
      setEditing(false)
    } catch {
      addToast('error', 'Failed to update album tags')
    } finally {
      setSaving(false)
    }
  }

  if (!editing) {
    return (
      <button
        onClick={startEditing}
        className="flex items-center gap-2 px-3 py-2 text-sm text-text-muted hover:text-text hover:bg-surface-200 rounded-lg transition-colors"
      >
        <Pencil className="h-4 w-4" />
        Edit Album Tags
      </button>
    )
  }

  return (
    <div className="space-y-3 mt-3 p-4 bg-surface-200/50 rounded-lg border border-surface-400">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">Album</label>
          <input
            type="text"
            value={draft.album}
            onChange={(e) => setDraft((d) => ({ ...d, album: e.target.value }))}
            className="w-full px-3 py-1.5 bg-surface-200 border border-surface-400 rounded-lg text-sm text-text focus:outline-none focus:border-accent-blue transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">Album Artist</label>
          <input
            type="text"
            value={draft.album_artist}
            onChange={(e) => setDraft((d) => ({ ...d, album_artist: e.target.value }))}
            className="w-full px-3 py-1.5 bg-surface-200 border border-surface-400 rounded-lg text-sm text-text focus:outline-none focus:border-accent-blue transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">Year</label>
          <input
            type="number"
            value={draft.year}
            onChange={(e) => setDraft((d) => ({ ...d, year: e.target.value }))}
            className="w-full px-3 py-1.5 bg-surface-200 border border-surface-400 rounded-lg text-sm text-text focus:outline-none focus:border-accent-blue transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">Genre</label>
          <input
            type="text"
            value={draft.genre}
            placeholder="Leave empty to keep current"
            onChange={(e) => setDraft((d) => ({ ...d, genre: e.target.value }))}
            className="w-full px-3 py-1.5 bg-surface-200 border border-surface-400 rounded-lg text-sm text-text placeholder:text-text-subtle focus:outline-none focus:border-accent-blue transition-colors"
          />
        </div>
        <div className="col-span-2">
          <label className="block text-xs font-medium text-text-muted mb-1">Label</label>
          <input
            type="text"
            value={draft.label}
            placeholder="Leave empty to keep current"
            onChange={(e) => setDraft((d) => ({ ...d, label: e.target.value }))}
            className="w-full px-3 py-1.5 bg-surface-200 border border-surface-400 rounded-lg text-sm text-text placeholder:text-text-subtle focus:outline-none focus:border-accent-blue transition-colors"
          />
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <button
          onClick={() => setEditing(false)}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-text-muted hover:text-text rounded-lg hover:bg-surface-300 transition-colors"
        >
          <X className="h-3.5 w-3.5" />
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-accent-blue text-surface-300 rounded-lg hover:opacity-90 transition-opacity"
        >
          {saving ? <LoadingSpinner size="sm" /> : <Save className="h-3.5 w-3.5" />}
          Save
        </button>
      </div>
    </div>
  )
}
