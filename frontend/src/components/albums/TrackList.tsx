import { useState } from 'react'
import {
  ChevronDown, ChevronRight, Disc3, Music, User, Tag, Calendar,
  Fingerprint, Pencil, Save, X, Music2, Volume2, Download,
} from 'lucide-react'
import type { TrackResponse } from '@/types'
import {
  fetchTrackTags, type TrackTags, editTrackTags,
  fetchTrackLyricsAction, getTrackLyrics,
} from '@/services/api'
import { formatDuration, cn } from '@/utils'
import { StatusBadge, LoadingSpinner } from '@/components/common'
import { useAlbumStore } from '@/store/useAlbumStore'
import { useNotificationStore } from '@/store/useNotificationStore'

interface Props {
  tracks: TrackResponse[]
  albumId?: number
}

export function TrackList({ tracks, albumId }: Props) {
  if (tracks.length === 0) {
    return <p className="text-sm text-text-subtle py-4 text-center">No tracks found</p>
  }

  // Group by disc number
  const discs = new Map<number, TrackResponse[]>()
  tracks.forEach((t) => {
    const disc = t.disc_number || 1
    if (!discs.has(disc)) discs.set(disc, [])
    discs.get(disc)!.push(t)
  })

  const multiDisc = discs.size > 1

  return (
    <div className="space-y-4">
      {[...discs.entries()]
        .sort(([a], [b]) => a - b)
        .map(([discNum, discTracks]) => (
          <div key={discNum}>
            {multiDisc && (
              <h4 className="text-xs font-medium text-text-subtle uppercase tracking-wider mb-2 px-2">
                Disc {discNum}
              </h4>
            )}
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-text-subtle uppercase tracking-wider border-b border-surface-400">
                  <th className="w-8 py-2" />
                  <th className="text-right pr-3 py-2 w-10">#</th>
                  <th className="text-left py-2">Title</th>
                  <th className="text-left py-2 hidden sm:table-cell">Artist</th>
                  <th className="text-right py-2 w-16">Duration</th>
                  <th className="text-center py-2 w-12" />
                  <th className="text-right py-2 w-20">Status</th>
                </tr>
              </thead>
              <tbody>
                {discTracks
                  .sort((a, b) => (a.track_number || 0) - (b.track_number || 0))
                  .map((track) => (
                    <TrackRow key={track.id} track={track} albumId={albumId} />
                  ))}
              </tbody>
            </table>
          </div>
        ))}
    </div>
  )
}

function TrackRow({ track, albumId }: { track: TrackResponse; albumId?: number }) {
  const [expanded, setExpanded] = useState(false)
  const [tags, setTags] = useState<TrackTags | null>(null)
  const [loading, setLoading] = useState(false)

  const handleToggle = async () => {
    if (expanded) {
      setExpanded(false)
      return
    }
    if (!tags) {
      setLoading(true)
      try {
        const data = await fetchTrackTags(track.album_id, track.id)
        setTags(data)
      } catch {
        // leave tags null
      } finally {
        setLoading(false)
      }
    }
    setExpanded(true)
  }

  return (
    <>
      <tr
        className="border-b border-surface-400/50 hover:bg-surface-400/20 transition-colors cursor-pointer"
        onClick={handleToggle}
      >
        <td className="py-2 pl-2">
          {loading ? (
            <LoadingSpinner size="sm" />
          ) : expanded ? (
            <ChevronDown className="h-4 w-4 text-text-subtle" />
          ) : (
            <ChevronRight className="h-4 w-4 text-text-subtle" />
          )}
        </td>
        <td className="text-right pr-3 py-2 text-text-subtle tabular-nums">
          {track.track_number || '-'}
        </td>
        <td className="py-2 text-text truncate max-w-[200px]">
          {track.title || 'Unknown'}
        </td>
        <td className="py-2 text-text-muted truncate max-w-[150px] hidden sm:table-cell">
          {track.artist || '-'}
        </td>
        <td className="text-right py-2 text-text-muted tabular-nums">
          {formatDuration(track.duration)}
        </td>
        <td className="text-center py-2">
          <div className="flex items-center justify-center gap-1">
            {track.has_lyrics && (
              <span title={track.lyrics_synced ? 'Synced lyrics' : 'Lyrics'}>
                <Music2 className="h-3.5 w-3.5 text-accent-blue" />
              </span>
            )}
            {track.replaygain_track_gain && (
              <span title={`Gain: ${track.replaygain_track_gain}`}>
                <Volume2 className="h-3.5 w-3.5 text-accent-green" />
              </span>
            )}
          </div>
        </td>
        <td className="text-right py-2">
          <StatusBadge status={track.status as any} />
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7} className="border-b border-surface-400/50">
            <TrackTagsPanel
              tags={tags}
              track={track}
              albumId={albumId}
              onTagsUpdated={(newTags) => setTags(newTags)}
            />
          </td>
        </tr>
      )}
    </>
  )
}

function TrackTagsPanel({
  tags,
  track,
  albumId,
  onTagsUpdated,
}: {
  tags: TrackTags | null
  track: TrackResponse
  albumId?: number
  onTagsUpdated: (tags: TrackTags) => void
}) {
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [lyrics, setLyrics] = useState<{ plain: string | null; synced: string | null } | null>(null)
  const [lyricsLoading, setLyricsLoading] = useState(false)
  const [fetchingLyrics, setFetchingLyrics] = useState(false)
  const fetchAlbum = useAlbumStore((s) => s.fetchAlbum)
  const addToast = useNotificationStore((s) => s.addToast)

  if (!tags) {
    return (
      <div className="px-4 py-3 text-sm text-text-subtle">
        Could not read file tags.
      </div>
    )
  }

  const startEditing = () => {
    setDraft({
      title: tags.title || '',
      artist: tags.artist || '',
      album_artist: tags.album_artist || '',
      album: tags.album || '',
      year: tags.year?.toString() || '',
      genre: tags.genre || '',
      track_number: tags.track_number?.toString() || '',
      disc_number: tags.disc_number?.toString() || '',
    })
    setEditing(true)
  }

  const handleSave = async () => {
    if (!albumId) return
    setSaving(true)
    try {
      const payload: Record<string, string | number | null> = {}
      if (draft.title !== (tags.title || '')) payload.title = draft.title || null
      if (draft.artist !== (tags.artist || '')) payload.artist = draft.artist || null
      if (draft.album_artist !== (tags.album_artist || '')) payload.album_artist = draft.album_artist || null
      if (draft.album !== (tags.album || '')) payload.album = draft.album || null
      if (draft.year !== (tags.year?.toString() || '')) payload.year = draft.year ? parseInt(draft.year) : null
      if (draft.genre !== (tags.genre || '')) payload.genre = draft.genre || null
      if (draft.track_number !== (tags.track_number?.toString() || '')) payload.track_number = draft.track_number ? parseInt(draft.track_number) : null
      if (draft.disc_number !== (tags.disc_number?.toString() || '')) payload.disc_number = draft.disc_number ? parseInt(draft.disc_number) : null

      if (Object.keys(payload).length === 0) {
        setEditing(false)
        return
      }

      await editTrackTags(albumId, track.id, payload)
      addToast('success', 'Track tags updated')

      // Refresh tags display
      const updated = await fetchTrackTags(albumId, track.id)
      onTagsUpdated(updated)
      fetchAlbum(albumId)
      setEditing(false)
    } catch {
      addToast('error', 'Failed to update track tags')
    } finally {
      setSaving(false)
    }
  }

  const handleFetchLyrics = async () => {
    if (!albumId) return
    setFetchingLyrics(true)
    try {
      const res = await fetchTrackLyricsAction(albumId, track.id)
      if (res.found) {
        addToast('success', `Lyrics found${res.synced ? ' (synced)' : ''}`)
        fetchAlbum(albumId)
      } else {
        addToast('info', 'No lyrics found')
      }
    } catch {
      addToast('error', 'Failed to fetch lyrics')
    } finally {
      setFetchingLyrics(false)
    }
  }

  const handleShowLyrics = async () => {
    if (!albumId) return
    if (lyrics) {
      setLyrics(null)
      return
    }
    setLyricsLoading(true)
    try {
      const data = await getTrackLyrics(albumId, track.id)
      setLyrics(data)
    } catch {
      addToast('error', 'Failed to read lyrics')
    } finally {
      setLyricsLoading(false)
    }
  }

  const fields = [
    { icon: Music, label: 'Title', value: tags.title, key: 'title' },
    { icon: User, label: 'Artist', value: tags.artist, key: 'artist' },
    { icon: User, label: 'Album Artist', value: tags.album_artist, key: 'album_artist' },
    { icon: Disc3, label: 'Album', value: tags.album, key: 'album' },
    { icon: Calendar, label: 'Year', value: tags.year?.toString(), key: 'year' },
    { icon: Tag, label: 'Genre', value: tags.genre, key: 'genre' },
    { icon: Tag, label: 'Format', value: tags.format, key: '' },
    { icon: Tag, label: 'Track', value: tags.track_number != null ? `${tags.track_number}` + (tags.disc_number != null && tags.disc_number > 1 ? ` (disc ${tags.disc_number})` : '') : null, key: '' },
    { icon: Fingerprint, label: 'MusicBrainz ID', value: tags.musicbrainz_recording_id, key: '' },
    { icon: Disc3, label: 'Cover Embedded', value: tags.has_cover ? 'Yes' : 'No', key: '' },
  ]

  return (
    <div className="px-4 py-3 bg-surface-200/50">
      {!editing ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1.5">
            {fields.map(({ icon: Icon, label, value }) => (
              <div key={label} className="flex items-center gap-2 text-sm">
                <Icon className="h-3.5 w-3.5 text-text-subtle shrink-0" />
                <span className="text-text-subtle min-w-[100px]">{label}:</span>
                <span className={cn('truncate', value ? 'text-text' : 'text-text-subtle italic')}>
                  {value || 'empty'}
                </span>
              </div>
            ))}
            {track.replaygain_track_gain && (
              <div className="flex items-center gap-2 text-sm">
                <Volume2 className="h-3.5 w-3.5 text-text-subtle shrink-0" />
                <span className="text-text-subtle min-w-[100px]">Track Gain:</span>
                <span className="text-text font-mono">{track.replaygain_track_gain}</span>
              </div>
            )}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <p className="text-xs text-text-subtle truncate flex-1" title={tags.path}>
              {tags.path}
            </p>
            {albumId && (
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={startEditing}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-text-muted hover:text-accent-blue hover:bg-accent-blue/10 rounded transition-colors"
                >
                  <Pencil className="h-3 w-3" />
                  Edit
                </button>
                {track.has_lyrics ? (
                  <button
                    onClick={handleShowLyrics}
                    disabled={lyricsLoading}
                    className="flex items-center gap-1 px-2 py-1 text-xs text-accent-blue hover:bg-accent-blue/10 rounded transition-colors"
                  >
                    {lyricsLoading ? <LoadingSpinner size="sm" /> : <Music2 className="h-3 w-3" />}
                    {lyrics ? 'Hide' : 'Lyrics'}
                  </button>
                ) : (
                  <button
                    onClick={handleFetchLyrics}
                    disabled={fetchingLyrics}
                    className="flex items-center gap-1 px-2 py-1 text-xs text-text-muted hover:text-accent-blue hover:bg-accent-blue/10 rounded transition-colors"
                  >
                    {fetchingLyrics ? <LoadingSpinner size="sm" /> : <Download className="h-3 w-3" />}
                    Lyrics
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Lyrics display */}
          {lyrics && (lyrics.synced || lyrics.plain) && (
            <div className="mt-2 p-3 bg-surface-300/50 rounded-lg border border-surface-400">
              <p className="text-[10px] uppercase tracking-wider text-text-subtle mb-1">
                {lyrics.synced ? 'Synced Lyrics' : 'Lyrics'}
              </p>
              <pre className="text-xs text-text whitespace-pre-wrap max-h-48 overflow-y-auto font-sans leading-relaxed">
                {lyrics.synced || lyrics.plain}
              </pre>
            </div>
          )}
        </>
      ) : (
        /* Inline editing mode */
        <div className="space-y-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {[
              { label: 'Title', key: 'title' },
              { label: 'Artist', key: 'artist' },
              { label: 'Album Artist', key: 'album_artist' },
              { label: 'Album', key: 'album' },
              { label: 'Year', key: 'year', type: 'number' },
              { label: 'Genre', key: 'genre' },
              { label: 'Track #', key: 'track_number', type: 'number' },
              { label: 'Disc #', key: 'disc_number', type: 'number' },
            ].map(({ label, key, type }) => (
              <div key={key}>
                <label className="block text-[10px] font-medium text-text-subtle mb-0.5">{label}</label>
                <input
                  type={type || 'text'}
                  value={draft[key] || ''}
                  onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
                  className="w-full px-2 py-1 bg-surface-200 border border-surface-400 rounded text-sm text-text focus:outline-none focus:border-accent-blue transition-colors"
                />
              </div>
            ))}
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button
              onClick={() => setEditing(false)}
              disabled={saving}
              className="flex items-center gap-1 px-2 py-1 text-xs text-text-muted hover:text-text rounded hover:bg-surface-300 transition-colors"
            >
              <X className="h-3 w-3" />
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1 px-2 py-1 text-xs font-medium bg-accent-blue text-surface-300 rounded hover:opacity-90 transition-opacity"
            >
              {saving ? <LoadingSpinner size="sm" /> : <Save className="h-3 w-3" />}
              Save
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
