import { useState } from 'react'
import { ChevronDown, ChevronRight, Disc3, Music, User, Tag, Calendar, Fingerprint } from 'lucide-react'
import type { TrackResponse } from '@/types'
import { fetchTrackTags, type TrackTags } from '@/services/api'
import { formatDuration, cn } from '@/utils'
import { StatusBadge, LoadingSpinner } from '@/components/common'

interface Props {
  tracks: TrackResponse[]
}

export function TrackList({ tracks }: Props) {
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
                  <th className="text-right py-2 w-20">Status</th>
                </tr>
              </thead>
              <tbody>
                {discTracks
                  .sort((a, b) => (a.track_number || 0) - (b.track_number || 0))
                  .map((track) => (
                    <TrackRow key={track.id} track={track} />
                  ))}
              </tbody>
            </table>
          </div>
        ))}
    </div>
  )
}

function TrackRow({ track }: { track: TrackResponse }) {
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
        <td className="text-right py-2">
          <StatusBadge status={track.status as any} />
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={6} className="border-b border-surface-400/50">
            <TrackTagsPanel tags={tags} />
          </td>
        </tr>
      )}
    </>
  )
}

function TrackTagsPanel({ tags }: { tags: TrackTags | null }) {
  if (!tags) {
    return (
      <div className="px-4 py-3 text-sm text-text-subtle">
        Could not read file tags.
      </div>
    )
  }

  const fields = [
    { icon: Music, label: 'Title', value: tags.title },
    { icon: User, label: 'Artist', value: tags.artist },
    { icon: User, label: 'Album Artist', value: tags.album_artist },
    { icon: Disc3, label: 'Album', value: tags.album },
    { icon: Calendar, label: 'Year', value: tags.year?.toString() },
    { icon: Tag, label: 'Genre', value: tags.genre },
    { icon: Tag, label: 'Format', value: tags.format },
    { icon: Tag, label: 'Track', value: tags.track_number != null ? `${tags.track_number}` + (tags.disc_number != null && tags.disc_number > 1 ? ` (disc ${tags.disc_number})` : '') : null },
    { icon: Fingerprint, label: 'MusicBrainz ID', value: tags.musicbrainz_recording_id },
    { icon: Disc3, label: 'Cover Embedded', value: tags.has_cover ? 'Yes' : 'No' },
  ]

  return (
    <div className="px-4 py-3 bg-surface-200/50">
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
      </div>
      <p className="mt-2 text-xs text-text-subtle truncate" title={tags.path}>
        {tags.path}
      </p>
    </div>
  )
}
